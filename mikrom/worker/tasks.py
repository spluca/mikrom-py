"""Background tasks for VM operations with enhanced logging and tracing."""

from typing import Optional
from sqlmodel import Session

from mikrom.database import sync_engine
from mikrom.models import VM
from mikrom.clients.ippool import IPPoolClient
from mikrom.clients.firecracker import FirecrackerClient
from mikrom.utils.logger import get_logger, log_timer
from mikrom.utils.context import set_context
from mikrom.utils.telemetry import get_tracer, add_span_attributes, add_span_event

logger = get_logger(__name__)
tracer = get_tracer()


async def create_vm_task(
    ctx: dict,
    vm_db_id: int,
    vcpu_count: int,
    memory_mb: int,
    kernel_path: Optional[str] = None,
    host: Optional[str] = None,
) -> dict:
    """
    Background task to create and start a VM.

    Args:
        ctx: arq context
        vm_db_id: Database ID of VM record
        vcpu_count: Number of vCPUs
        memory_mb: Memory in MB
        kernel_path: Optional kernel path
        host: Optional target host

    Returns:
        dict with results
    """
    with tracer.start_as_current_span("background.create_vm") as span:
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

        ippool = IPPoolClient()
        firecracker = FirecrackerClient()

        try:
            # Step 1: Allocate IP
            with (
                tracer.start_as_current_span("vm.allocate_ip"),
                log_timer("allocate_ip", logger),
            ):
                logger.info("Allocating IP address")
                ip_info = await ippool.allocate_ip(vm_id, vm_name)
                ip_address = ip_info["ip"]

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

                logger.info(
                    "VM status updated to provisioning", extra={"ip": ip_address}
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

                logger.info("VM status updated to running")

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

            # Try to cleanup IP if allocated
            try:
                if vm_id:
                    logger.info("Attempting to cleanup IP allocation")
                    await ippool.release_ip(vm_id)
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
            await ippool.close()


async def delete_vm_task(
    ctx: dict, vm_db_id: int, vm_id: str, host: Optional[str] = None
) -> dict:
    """
    Background task to delete a VM.

    Args:
        ctx: arq context
        vm_db_id: Database ID of VM record
        vm_id: Firecracker VM ID
        host: Optional target host

    Returns:
        dict with results
    """
    with tracer.start_as_current_span("background.delete_vm") as span:
        # Set context
        set_context(action="vm.delete.background", vm_id=vm_id)
        add_span_attributes(**{"vm.id": vm_id, "vm.db_id": vm_db_id})

        logger.info(
            "Starting VM deletion background task",
            extra={"vm_db_id": vm_db_id, "host": host},
        )

        ippool = IPPoolClient()
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
                    await ippool.release_ip(vm_id)
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
            await ippool.close()


async def stop_vm_task(
    ctx: dict, vm_db_id: int, vm_id: str, host: Optional[str] = None
) -> dict:
    """
    Background task to stop a VM.

    Args:
        ctx: arq context
        vm_db_id: Database ID of VM record
        vm_id: Firecracker VM ID
        host: Optional target host

    Returns:
        dict with results
    """
    with tracer.start_as_current_span("background.stop_vm") as span:
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
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__},
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


async def start_vm_task(
    ctx: dict,
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
        ctx: arq context
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
        set_context(action="vm.start.background", vm_id=vm_id)
        add_span_attributes(**{"vm.id": vm_id, "vm.db_id": vm_db_id})

        logger.info(
            "Starting VM start background task",
            extra={"vm_db_id": vm_db_id, "host": host},
        )

        firecracker = FirecrackerClient()
        ippool = IPPoolClient()

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
            await ippool.close()


async def restart_vm_task(
    ctx: dict,
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
        ctx: arq context
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
        set_context(action="vm.restart.background", vm_id=vm_id)
        add_span_attributes(**{"vm.id": vm_id, "vm.db_id": vm_db_id})

        logger.info(
            "Starting VM restart background task",
            extra={"vm_db_id": vm_db_id, "host": host},
        )

        try:
            # Step 1: Stop the VM
            logger.info("Stopping VM as part of restart")
            await stop_vm_task(ctx, vm_db_id, vm_id, host)

            # Step 2: Wait a moment
            import asyncio
            await asyncio.sleep(2)

            # Step 3: Start the VM
            logger.info("Starting VM as part of restart")
            start_result = await start_vm_task(
                ctx, vm_db_id, vm_id, vcpu_count, memory_mb, kernel_path, host
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
