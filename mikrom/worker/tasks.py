"""Background tasks for VM operations with enhanced logging and tracing."""

import asyncio
from typing import Optional
from datetime import datetime, UTC
from sqlmodel import Session, select, and_
from celery.exceptions import SoftTimeLimitExceeded

from mikrom.celery_app import celery_app
from mikrom.database import sync_engine
from mikrom.models import VM, IpPool, IpAllocation
from mikrom.services.ippool_service import (
    IPPoolService,
)  # Direct import to avoid circular dependency
from mikrom.clients.firecracker import FirecrackerClient
from mikrom.events.publisher import EventPublisher
from mikrom.utils.logger import get_logger, log_timer
from mikrom.utils.context import set_context
from mikrom.utils.telemetry import get_tracer, add_span_attributes, add_span_event
from mikrom.config import settings

logger = get_logger(__name__)
tracer = get_tracer()


def _run_async(coro):
    """
    Run an async coroutine, handling both cases:
    - When called from sync context (Celery worker): use asyncio.run()
    - When called from async context (tests): await the coroutine directly

    This allows the same code to work in both Celery workers and async tests.
    """
    try:
        # Try to get the running event loop
        asyncio.get_running_loop()
        # If we're here, there's already a loop running (e.g., pytest-asyncio)
        # We need to create a task in the existing loop
        import nest_asyncio

        nest_asyncio.apply()
        return asyncio.run(coro)
    except RuntimeError:
        # No event loop running, we can use asyncio.run() safely
        return asyncio.run(coro)
    except RuntimeError:
        # No event loop running, we can use asyncio.run() safely
        return asyncio.run(coro)


# Wrapper interno para convertir funciones async a sync para Celery
async def _create_vm_task_async(
    self,
    vm_db_id: int,
    vcpu_count: int,
    memory_mb: int,
    kernel_path: Optional[str] = None,
    host: Optional[str] = None,
) -> dict:
    """
    Background task to create and start a VM.

    Args:
        self: Celery task instance
        vm_db_id: Database ID of VM record
        vcpu_count: Number of vCPUs
        memory_mb: Memory in MB
        kernel_path: Optional kernel path
        host: Optional target host

    Returns:
        dict with results
    """
    with tracer.start_as_current_span("background.create_vm") as span:
        # Add Celery task ID to span
        add_span_attributes(**{"celery.task_id": self.request.id})

        # Get VM info from database
        with Session(sync_engine) as session:
            vm = session.get(VM, vm_db_id)
            if not vm:
                raise ValueError(f"VM {vm_db_id} not found in database")

            vm_id = vm.vm_id
            vm_name = vm.name

        # Set context for logging
        set_context(action="vm.create.background", vm_id=vm_id)
        add_span_attributes(
            **{
                "vm.id": vm_id,
                "vm.db_id": vm_db_id,
                "vm.name": vm_name,
                "vm.vcpu_count": vcpu_count,
                "vm.memory_mb": memory_mb,
            }
        )

        logger.info(
            "Starting VM creation background task",
            extra={
                "vm_db_id": vm_db_id,
                "vm_name": vm_name,
                "vcpu_count": vcpu_count,
                "memory_mb": memory_mb,
                "host": host,
            },
        )

        IPPoolService()
        firecracker = FirecrackerClient()

        try:
            # Step 1: Allocate IP
            with (
                tracer.start_as_current_span("vm.allocate_ip"),
                log_timer("allocate_ip", logger),
            ):
                logger.info("Allocating IP address")
                # Allocate IP using sync session
                with Session(sync_engine) as db_session:
                    # Get pool
                    pool = db_session.exec(
                        select(IpPool).where(
                            and_(
                                IpPool.name == settings.IPPOOL_DEFAULT_POOL_NAME,
                                IpPool.is_active,
                            )
                        )
                    ).first()

                    if not pool:
                        raise ValueError(
                            f"IP pool '{settings.IPPOOL_DEFAULT_POOL_NAME}' not found"
                        )

                    # Check if VM already has active allocation (idempotent)
                    existing = db_session.exec(
                        select(IpAllocation).where(
                            and_(
                                IpAllocation.vm_id == vm_id,
                                IpAllocation.is_active,
                            )
                        )
                    ).first()

                    if existing:
                        logger.info(
                            "VM already has active IP allocation",
                            extra={"ip": existing.ip_address},
                        )
                        ip_address = existing.ip_address
                    else:
                        # Find first available IP
                        from mikrom.services.ippool_service import (
                            _ip_to_int,
                            _int_to_ip,
                        )

                        start_int = _ip_to_int(pool.start_ip)
                        end_int = _ip_to_int(pool.end_ip)

                        # Get all allocated IPs
                        allocated_ips = {
                            row[0]
                            for row in db_session.exec(
                                select(IpAllocation.ip_address).where(
                                    and_(
                                        IpAllocation.pool_id == pool.id,
                                        IpAllocation.is_active,
                                    )
                                )
                            ).all()
                        }

                        # Find first available
                        available_ip = None
                        for ip_int in range(start_int, end_int + 1):
                            ip_str = _int_to_ip(ip_int)
                            if ip_str not in allocated_ips:
                                available_ip = ip_str
                                break

                        if not available_ip:
                            raise ValueError(
                                f"No available IPs in pool '{settings.IPPOOL_DEFAULT_POOL_NAME}'"
                            )

                        # Create allocation
                        allocation = IpAllocation(
                            pool_id=pool.id,
                            vm_id=vm_id,
                            ip_address=available_ip,
                            is_active=True,
                            allocated_at=datetime.now(UTC),
                        )
                        db_session.add(allocation)
                        db_session.commit()
                        ip_address = available_ip
                        logger.info("New IP allocated", extra={"ip": ip_address})

                add_span_event("ip_allocated", {"ip": ip_address})
                logger.info("IP allocated successfully", extra={"ip": ip_address})

            # Update VM with IP
            with tracer.start_as_current_span("vm.update_ip"):
                with Session(sync_engine) as session:
                    vm = session.get(VM, vm_db_id)
                    vm.ip_address = ip_address
                    vm.status = "provisioning"
                    session.add(vm)
                    session.commit()

                    # Get user_id for event
                    user_id = vm.user_id

                logger.info(
                    "VM status updated to provisioning", extra={"ip": ip_address}
                )

                # Publish status change event
                EventPublisher.publish_vm_event_sync(
                    vm_id=vm_id,
                    event_type="vm.status_change",
                    data={
                        "status": "provisioning",
                        "ip_address": ip_address,
                        "user_id": user_id,
                    },
                )

            # Step 2: Start VM with Firecracker
            with (
                tracer.start_as_current_span("vm.start_firecracker"),
                log_timer("start_firecracker", logger),
            ):
                logger.info("Starting Firecracker VM")
                result = await firecracker.start_vm(
                    vm_id=vm_id,
                    vcpu_count=vcpu_count,
                    memory_mb=memory_mb,
                    kernel_path=kernel_path,
                    limit=host,
                )

                add_span_event("vm_started", {"result": result.get("status")})
                logger.info(
                    "Firecracker VM started successfully", extra={"result": result}
                )

            # Step 3: Update VM status to running
            with tracer.start_as_current_span("vm.update_status"):
                with Session(sync_engine) as session:
                    vm = session.get(VM, vm_db_id)
                    vm.status = "running"
                    vm.host = host
                    vm.kernel_path = kernel_path
                    vm.error_message = None
                    session.add(vm)
                    session.commit()

                    # Get user_id for event
                    user_id = vm.user_id

                logger.info("VM status updated to running")

                # Publish status change event
                EventPublisher.publish_vm_event_sync(
                    vm_id=vm_id,
                    event_type="vm.status_change",
                    data={
                        "status": "running",
                        "ip_address": ip_address,
                        "host": host,
                        "user_id": user_id,
                    },
                )

            logger.info(
                "VM created successfully",
                extra={
                    "ip_address": ip_address,
                    "host": host,
                    "status": "running",
                },
            )

            return {
                "success": True,
                "vm_id": vm_id,
                "ip_address": ip_address,
                "status": "running",
            }

        except SoftTimeLimitExceeded:
            # Task is approaching time limit, cleanup gracefully
            logger.warning(
                "VM creation task approaching time limit, cleaning up",
                extra={"vm_db_id": vm_db_id},
            )
            span.add_event("soft_time_limit_exceeded")

            # Update VM status to error
            with Session(sync_engine) as session:
                vm = session.get(VM, vm_db_id)
                if vm:
                    vm.status = "error"
                    vm.error_message = (
                        "Task timed out - operation took too long to complete"
                    )
                    session.add(vm)
                    session.commit()

            # Try to cleanup IP if allocated
            try:
                if vm_id:
                    logger.info("Attempting to cleanup IP allocation after timeout")
                    with Session(sync_engine) as db_session:
                        allocation = db_session.exec(
                            select(IpAllocation).where(
                                and_(
                                    IpAllocation.vm_id == vm_id,
                                    IpAllocation.is_active,
                                )
                            )
                        ).first()
                        if allocation:
                            allocation.is_active = False
                            allocation.released_at = datetime.utcnow()
                            db_session.add(allocation)
                            db_session.commit()
            except Exception as cleanup_error:
                logger.error(
                    "IP cleanup failed after timeout",
                    extra={"error": str(cleanup_error)},
                )

            raise

        except Exception as e:
            logger.error(
                "VM creation failed",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
            span.record_exception(e)

            # Update VM status to error
            with Session(sync_engine) as session:
                vm = session.get(VM, vm_db_id)
                if vm:
                    vm.status = "error"
                    vm.error_message = str(e)
                    session.add(vm)
                    session.commit()

                    # Get user_id for event
                    user_id = vm.user_id

                    # Publish error event
                    EventPublisher.publish_vm_event_sync(
                        vm_id=vm_id,
                        event_type="vm.status_change",
                        data={
                            "status": "error",
                            "error_message": str(e),
                            "user_id": user_id,
                        },
                    )

            # Try to cleanup IP if allocated
            try:
                if vm_id:
                    logger.info("Attempting to cleanup IP allocation")
                    with Session(sync_engine) as db_session:
                        allocation = db_session.exec(
                            select(IpAllocation).where(
                                and_(
                                    IpAllocation.vm_id == vm_id,
                                    IpAllocation.is_active,
                                )
                            )
                        ).first()
                        if allocation:
                            allocation.is_active = False
                            allocation.released_at = datetime.now(UTC)
                            db_session.add(allocation)
                            db_session.commit()
                    logger.info("IP cleanup successful")
            except Exception as cleanup_error:
                logger.error(
                    "IP cleanup failed",
                    extra={
                        "error": str(cleanup_error),
                        "error_type": type(cleanup_error).__name__,
                    },
                )

            raise

        finally:
            # No more cleanup needed for ippool (no client to close)
            pass


@celery_app.task(name="create_vm_task", bind=True, max_retries=3)
def create_vm_task(
    self,
    vm_db_id: int,
    vcpu_count: int,
    memory_mb: int,
    kernel_path: Optional[str] = None,
    host: Optional[str] = None,
) -> dict:
    """Sync wrapper for create_vm_task that runs the async version."""
    return _run_async(
        _create_vm_task_async(self, vm_db_id, vcpu_count, memory_mb, kernel_path, host)
    )


async def _delete_vm_task_async(
    self, vm_db_id: int, vm_id: str, host: Optional[str] = None
) -> dict:
    """
    Background task to delete a VM.

    Args:
        self: Celery task instance
        vm_db_id: Database ID of VM record
        vm_id: Firecracker VM ID
        host: Optional target host

    Returns:
        dict with results
    """
    with tracer.start_as_current_span("background.delete_vm") as span:
        # Add Celery task ID to span
        add_span_attributes(**{"celery.task_id": self.request.id})

        # Set context
        set_context(action="vm.delete.background", vm_id=vm_id)
        add_span_attributes(**{"vm.id": vm_id, "vm.db_id": vm_db_id})

        logger.info(
            "Starting VM deletion background task",
            extra={"vm_db_id": vm_db_id, "host": host},
        )

        IPPoolService()
        firecracker = FirecrackerClient()

        try:
            # Update status to deleting
            with tracer.start_as_current_span("vm.update_status"):
                with Session(sync_engine) as session:
                    vm = session.get(VM, vm_db_id)
                    if vm:
                        vm.status = "deleting"
                        session.add(vm)
                        session.commit()
                        logger.info("VM status updated to deleting")

            # Step 1: Cleanup VM with Firecracker
            with (
                tracer.start_as_current_span("vm.cleanup_firecracker"),
                log_timer("cleanup_firecracker", logger),
            ):
                logger.info("Cleaning up Firecracker VM")
                try:
                    await firecracker.cleanup_vm(vm_id, limit=host)
                    add_span_event("vm_cleaned_up")
                    logger.info("Firecracker cleanup successful")
                except Exception as e:
                    logger.warning(
                        "Firecracker cleanup failed (continuing)",
                        extra={"error": str(e), "error_type": type(e).__name__},
                    )

            # Step 2: Release IP
            with (
                tracer.start_as_current_span("vm.release_ip"),
                log_timer("release_ip", logger),
            ):
                logger.info("Releasing IP address")
                try:
                    with Session(sync_engine) as db_session:
                        allocation = db_session.exec(
                            select(IpAllocation).where(
                                and_(
                                    IpAllocation.vm_id == vm_id,
                                    IpAllocation.is_active,
                                )
                            )
                        ).first()
                        if allocation:
                            allocation.is_active = False
                            allocation.released_at = datetime.now(UTC)
                            db_session.add(allocation)
                            db_session.commit()
                    add_span_event("ip_released")
                    logger.info("IP released successfully")
                except Exception as e:
                    logger.warning(
                        "IP release failed (continuing)",
                        extra={"error": str(e), "error_type": type(e).__name__},
                    )

            # Step 3: Delete from database
            with tracer.start_as_current_span("vm.delete_db"):
                with Session(sync_engine) as session:
                    vm = session.get(VM, vm_db_id)
                    if vm:
                        session.delete(vm)
                        session.commit()
                        logger.info("VM deleted from database")

            logger.info("VM deleted successfully")

            return {"success": True, "vm_id": vm_id, "status": "deleted"}

        except Exception as e:
            logger.error(
                "VM deletion failed",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
            span.record_exception(e)

            # Update status back to error
            with Session(sync_engine) as session:
                vm = session.get(VM, vm_db_id)
                if vm:
                    vm.status = "error"
                    vm.error_message = f"Deletion failed: {str(e)}"
                    session.add(vm)
                    session.commit()

            raise

        finally:
            # No more cleanup needed for ippool (no client to close)
            pass


@celery_app.task(name="delete_vm_task", bind=True, max_retries=3)
def delete_vm_task(self, vm_db_id: int, vm_id: str, host: Optional[str] = None) -> dict:
    """Sync wrapper for delete_vm_task that runs the async version."""
    return _run_async(_delete_vm_task_async(self, vm_db_id, vm_id, host))


async def _stop_vm_task_async(
    self, vm_db_id: int, vm_id: str, host: Optional[str] = None
) -> dict:
    """
    Background task to stop a VM.

    Args:
        self: Celery task instance
        vm_db_id: Database ID of VM record
        vm_id: Firecracker VM ID
        host: Optional target host

    Returns:
        dict with results
    """
    with tracer.start_as_current_span("background.stop_vm") as span:
        add_span_attributes(**{"celery.task_id": self.request.id})
        set_context(action="vm.stop.background", vm_id=vm_id)
        add_span_attributes(**{"vm.id": vm_id, "vm.db_id": vm_db_id})

        logger.info(
            "Starting VM stop background task",
            extra={"vm_db_id": vm_db_id, "host": host},
        )

        firecracker = FirecrackerClient()

        try:
            # Step 1: Stop VM with Firecracker
            with (
                tracer.start_as_current_span("vm.stop_firecracker"),
                log_timer("stop_firecracker", logger),
            ):
                logger.info("Stopping Firecracker VM")
                try:
                    await firecracker.stop_vm(vm_id, limit=host)
                    add_span_event("vm_stopped")
                    logger.info("Firecracker stop successful")
                except Exception as e:
                    logger.error(
                        "Firecracker stop failed",
                        extra={"error": str(e), "error_type": type(e).__name__},
                    )
                    raise

            # Step 2: Update status to stopped
            with tracer.start_as_current_span("vm.update_status"):
                with Session(sync_engine) as session:
                    vm = session.get(VM, vm_db_id)
                    if vm:
                        vm.status = "stopped"
                        session.add(vm)
                        session.commit()
                        logger.info("VM status updated to stopped")

            logger.info("VM stopped successfully")
            return {"success": True, "vm_id": vm_id, "status": "stopped"}

        except Exception as e:
            logger.error(
                "VM stop failed",
                extra={"error": str(e), "error_type": type(e).__name__},
            )
            span.record_exception(e)

            # Update status to error
            with Session(sync_engine) as session:
                vm = session.get(VM, vm_db_id)
                if vm:
                    vm.status = "error"
                    vm.error_message = f"Stop failed: {str(e)}"
                    session.add(vm)
                    session.commit()

            raise


@celery_app.task(name="stop_vm_task", bind=True, max_retries=3)
def stop_vm_task(self, vm_db_id: int, vm_id: str, host: Optional[str] = None) -> dict:
    """Sync wrapper for stop_vm_task that runs the async version."""
    return _run_async(_stop_vm_task_async(self, vm_db_id, vm_id, host))


async def _start_vm_task_async(
    self,
    vm_db_id: int,
    vm_id: str,
    vcpu_count: int,
    memory_mb: int,
    kernel_path: Optional[str] = None,
    host: Optional[str] = None,
) -> dict:
    """
    Background task to start a VM.

    Args:
        self: Celery task instance
        vm_db_id: Database ID of VM record
        vm_id: Firecracker VM ID
        vcpu_count: Number of vCPUs
        memory_mb: Memory in MB
        kernel_path: Optional custom kernel
        host: Optional target host

    Returns:
        dict with results
    """
    with tracer.start_as_current_span("background.start_vm") as span:
        add_span_attributes(**{"celery.task_id": self.request.id})
        set_context(action="vm.start.background", vm_id=vm_id)
        add_span_attributes(**{"vm.id": vm_id, "vm.db_id": vm_db_id})

        logger.info(
            "Starting VM start background task",
            extra={"vm_db_id": vm_db_id, "host": host},
        )

        firecracker = FirecrackerClient()

        try:
            # Get VM IP from database
            with Session(sync_engine) as session:
                vm = session.get(VM, vm_db_id)
                if not vm:
                    raise ValueError(f"VM {vm_db_id} not found")
                ip_address = vm.ip_address

            if not ip_address:
                raise ValueError("VM has no IP address allocated")

            # Step 1: Start VM with Firecracker
            with (
                tracer.start_as_current_span("vm.start_firecracker"),
                log_timer("start_firecracker", logger),
            ):
                logger.info("Starting Firecracker VM")
                await firecracker.start_vm(
                    vm_id=vm_id,
                    vcpu_count=vcpu_count,
                    memory_mb=memory_mb,
                    kernel_path=kernel_path,
                    limit=host,
                )
                add_span_event("vm_started")
                logger.info("Firecracker VM started successfully")

            # Step 2: Update status to running
            with tracer.start_as_current_span("vm.update_status"):
                with Session(sync_engine) as session:
                    vm = session.get(VM, vm_db_id)
                    if vm:
                        vm.status = "running"
                        vm.host = host or "firecracker-01"
                        session.add(vm)
                        session.commit()
                        logger.info("VM status updated to running")

            logger.info("VM started successfully")
            return {
                "success": True,
                "vm_id": vm_id,
                "ip_address": ip_address,
                "status": "running",
            }

        except Exception as e:
            logger.error(
                "VM start failed",
                extra={"error": str(e), "error_type": type(e).__name__},
            )
            span.record_exception(e)

            # Update status to error
            with Session(sync_engine) as session:
                vm = session.get(VM, vm_db_id)
                if vm:
                    vm.status = "error"
                    vm.error_message = f"Start failed: {str(e)}"
                    session.add(vm)
                    session.commit()

            raise

        finally:
            # No more cleanup needed
            pass


@celery_app.task(name="start_vm_task", bind=True, max_retries=3)
def start_vm_task(
    self,
    vm_db_id: int,
    vm_id: str,
    vcpu_count: int,
    memory_mb: int,
    kernel_path: Optional[str] = None,
    host: Optional[str] = None,
) -> dict:
    """Sync wrapper for start_vm_task that runs the async version."""
    return _run_async(
        _start_vm_task_async(
            self, vm_db_id, vm_id, vcpu_count, memory_mb, kernel_path, host
        )
    )


async def _restart_vm_task_async(
    self,
    vm_db_id: int,
    vm_id: str,
    vcpu_count: int,
    memory_mb: int,
    kernel_path: Optional[str] = None,
    host: Optional[str] = None,
) -> dict:
    """
    Background task to restart a VM.

    Args:
        self: Celery task instance
        vm_db_id: Database ID of VM record
        vm_id: Firecracker VM ID
        vcpu_count: Number of vCPUs
        memory_mb: Memory in MB
        kernel_path: Optional custom kernel
        host: Optional target host

    Returns:
        dict with results
    """
    with tracer.start_as_current_span("background.restart_vm") as span:
        add_span_attributes(**{"celery.task_id": self.request.id})
        set_context(action="vm.restart.background", vm_id=vm_id)
        add_span_attributes(**{"vm.id": vm_id, "vm.db_id": vm_db_id})

        logger.info(
            "Starting VM restart background task",
            extra={"vm_db_id": vm_db_id, "host": host},
        )

        try:
            # Step 1: Stop the VM
            logger.info("Stopping VM as part of restart")
            await stop_vm_task(vm_db_id, vm_id, host)

            # Step 2: Wait a moment
            import asyncio

            await asyncio.sleep(2)

            # Step 3: Start the VM
            logger.info("Starting VM as part of restart")
            start_result = await start_vm_task(
                vm_db_id, vm_id, vcpu_count, memory_mb, kernel_path, host
            )

            logger.info("VM restarted successfully")
            return {
                "success": True,
                "vm_id": vm_id,
                "status": "running",
                "ip_address": start_result.get("ip_address"),
            }

        except Exception as e:
            logger.error(
                "VM restart failed",
                extra={"error": str(e), "error_type": type(e).__name__},
            )
            span.record_exception(e)

            # Update status to error
            with Session(sync_engine) as session:
                vm = session.get(VM, vm_db_id)
                if vm:
                    vm.status = "error"
                    vm.error_message = f"Restart failed: {str(e)}"
                    session.add(vm)
                    session.commit()

            raise


@celery_app.task(name="restart_vm_task", bind=True, max_retries=3)
def restart_vm_task(
    self,
    vm_db_id: int,
    vm_id: str,
    vcpu_count: int,
    memory_mb: int,
    kernel_path: Optional[str] = None,
    host: Optional[str] = None,
) -> dict:
    """Sync wrapper for restart_vm_task that runs the async version."""
    return _run_async(
        _restart_vm_task_async(
            self, vm_db_id, vm_id, vcpu_count, memory_mb, kernel_path, host
        )
    )
