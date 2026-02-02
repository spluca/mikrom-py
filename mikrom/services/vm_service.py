"""VM management service."""

import secrets
from typing import Optional, List
from sqlmodel import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from mikrom.models import VM, User, VMStatus
from mikrom.config import settings
from mikrom.events.publisher import EventPublisher
from mikrom.utils.logger import get_logger
from mikrom.utils.context import set_context
from mikrom.utils.telemetry import get_tracer, add_span_attributes
from mikrom.worker.tasks import (
    create_vm_task,
    delete_vm_task,
    stop_vm_task,
    start_vm_task,
    restart_vm_task,
)

logger = get_logger(__name__)
tracer = get_tracer()


class VMService:
    """Service for VM management operations."""

    def __init__(self):
        """Initialize service."""
        pass

    def generate_vm_id(self) -> str:
        """Generate unique VM ID."""
        return f"srv-{secrets.token_hex(4)}"

    async def create_vm(
        self,
        session: AsyncSession,
        user: User,
        name: str,
        vcpu_count: int,
        memory_mb: int,
        description: Optional[str] = None,
        kernel_path: Optional[str] = None,
    ) -> VM:
        """
        Create a new VM (queues background task).

        Args:
            session: Database session
            user: Owner user
            name: VM name
            vcpu_count: Number of vCPUs
            memory_mb: Memory in MB
            description: Optional description
            kernel_path: Optional custom kernel

        Returns:
            VM model with status='pending'
        """
        with tracer.start_as_current_span("service.vm.create") as _span:
            # Generate unique VM ID
            vm_id = self.generate_vm_id()

            # Set context
            set_context(vm_id=vm_id)
            add_span_attributes(
                **{
                    "vm.id": vm_id,
                    "vm.name": name,
                    "vm.vcpu_count": vcpu_count,
                    "vm.memory_mb": memory_mb,
                    "user.id": user.id,
                }
            )

            # Create VM record in database
            with tracer.start_as_current_span("service.vm.create.db_insert"):
                logger.info(
                    "Inserting VM record in database",
                    extra={
                        "vm_name": name,
                        "vcpu_count": vcpu_count,
                        "memory_mb": memory_mb,
                        "user_id": user.id,
                        "user_name": user.username,
                    },
                )

                vm = VM(
                    vm_id=vm_id,
                    name=name,
                    description=description,
                    vcpu_count=vcpu_count,
                    memory_mb=memory_mb,
                    user_id=user.id,
                    status=VMStatus.PENDING,
                    kernel_path=kernel_path,
                )

                session.add(vm)
                await session.commit()
                await session.refresh(vm)

                add_span_attributes(**{"vm.db_id": vm.id})

            logger.info(
                "VM record created",
                extra={
                    "vm_db_id": vm.id,
                    "status": vm.status,
                },
            )

            # Publish VM created event
            await EventPublisher.publish_vm_event(
                vm_id=vm_id,
                event_type="vm.created",
                data={
                    "name": name,
                    "status": vm.status,
                    "user_id": vm.user_id,
                    "vcpu_count": vcpu_count,
                    "memory_mb": memory_mb,
                },
            )

            # Queue background task to actually create the VM
            with tracer.start_as_current_span("service.vm.create.queue_job"):
                logger.info("Queueing VM creation background job")

                result = create_vm_task.delay(
                    vm.id,
                    vcpu_count,
                    memory_mb,
                    kernel_path,
                    settings.FIRECRACKER_DEFAULT_HOST,
                )

                logger.info("VM creation job queued", extra={"job_id": result.id})

            return vm

    async def get_user_vms(
        self, session: AsyncSession, user: User, offset: int = 0, limit: int = 10
    ) -> tuple[List[VM], int]:
        """
        Get user's VMs with pagination.

        Superusers can see all VMs, regular users only see their own.

        Args:
            session: Database session
            user: User
            offset: Pagination offset
            limit: Pagination limit

        Returns:
            Tuple of (VMs list, total count)
        """
        # Get VMs (superusers see all VMs)
        statement = select(VM).offset(offset).limit(limit).order_by(desc(VM.created_at))

        if not user.is_superuser:
            statement = statement.where(VM.user_id == user.id)

        result = await session.execute(statement)
        vms = list(result.scalars().all())

        # Get total count (superusers count all VMs)
        count_statement = select(func.count()).select_from(VM)

        if not user.is_superuser:
            count_statement = count_statement.where(VM.user_id == user.id)

        count_result = await session.execute(count_statement)
        total = count_result.scalar_one()

        return vms, total

    async def get_vm_by_id(
        self, session: AsyncSession, vm_id: str, user: User
    ) -> Optional[VM]:
        """
        Get VM by vm_id (only if owned by user or user is superuser).

        Args:
            session: Database session
            vm_id: VM identifier (srv-xxxxxxxx)
            user: User

        Returns:
            VM or None
        """
        statement = select(VM).where(VM.vm_id == vm_id)
        result = await session.execute(statement)
        vm = result.scalar_one_or_none()

        if not vm:
            return None

        # Check ownership (allow superusers to access any VM)
        if vm.user_id != user.id and not user.is_superuser:
            return None

        return vm

    async def delete_vm(self, session: AsyncSession, vm: VM) -> None:
        """
        Delete a VM (queues background task).

        Args:
            session: Database session
            vm: VM to delete
        """
        with tracer.start_as_current_span("service.vm.delete") as _span:
            add_span_attributes(
                **{
                    "vm.id": vm.vm_id,
                    "vm.db_id": vm.id,
                }
            )

            logger.info("Queueing VM deletion", extra={"vm_id": vm.vm_id})

            # Update status to deleting
            with tracer.start_as_current_span("service.vm.delete.update_status"):
                vm.status = VMStatus.DELETING
                session.add(vm)
                await session.commit()

                logger.info("VM status updated to deleting", extra={"vm_id": vm.vm_id})

            # Queue background task
            with tracer.start_as_current_span("service.vm.delete.queue_job"):
                result = delete_vm_task.delay(
                    vm.id,
                    vm.vm_id,
                    vm.host,
                )

                logger.info(
                    "VM deletion job queued",
                    extra={"job_id": result.id, "vm_id": vm.vm_id},
                )

    async def close(self):
        """Close service resources."""
        # No resources to close with Celery (it manages its own connections)
        pass

    async def stop_vm(self, session: AsyncSession, vm: VM) -> None:
        """
        Stop a VM (queues background task).

        Args:
            session: Database session
            vm: VM to stop
        """
        with tracer.start_as_current_span("service.vm.stop") as _span:
            add_span_attributes(**{"vm.id": vm.vm_id, "vm.db_id": vm.id})

            logger.info("Queueing VM stop", extra={"vm_id": vm.vm_id})

            # Update status to stopping
            with tracer.start_as_current_span("service.vm.stop.update_status"):
                vm.status = VMStatus.STOPPING
                session.add(vm)
                await session.commit()

                logger.info("VM status updated to stopping", extra={"vm_id": vm.vm_id})

            # Queue background task
            with tracer.start_as_current_span("service.vm.stop.queue_job"):
                result = stop_vm_task.delay(
                    vm.id,
                    vm.vm_id,
                    vm.host,
                )

                logger.info(
                    "VM stop job queued",
                    extra={"job_id": result.id, "vm_id": vm.vm_id},
                )

    async def start_vm(self, session: AsyncSession, vm: VM) -> None:
        """
        Start a VM (queues background task).

        Args:
            session: Database session
            vm: VM to start
        """
        with tracer.start_as_current_span("service.vm.start") as _span:
            add_span_attributes(**{"vm.id": vm.vm_id, "vm.db_id": vm.id})

            logger.info("Queueing VM start", extra={"vm_id": vm.vm_id})

            # Update status to starting
            with tracer.start_as_current_span("service.vm.start.update_status"):
                vm.status = VMStatus.STARTING
                session.add(vm)
                await session.commit()

                logger.info("VM status updated to starting", extra={"vm_id": vm.vm_id})

            # Queue background task
            with tracer.start_as_current_span("service.vm.start.queue_job"):
                result = start_vm_task.delay(
                    vm.id,
                    vm.vm_id,
                    vm.vcpu_count,
                    vm.memory_mb,
                    vm.kernel_path,
                    vm.host,
                )

                logger.info(
                    "VM start job queued",
                    extra={"job_id": result.id, "vm_id": vm.vm_id},
                )

    async def restart_vm(self, session: AsyncSession, vm: VM) -> None:
        """
        Restart a VM (queues stop then start tasks).

        Args:
            session: Database session
            vm: VM to restart
        """
        with tracer.start_as_current_span("service.vm.restart") as _span:
            add_span_attributes(**{"vm.id": vm.vm_id, "vm.db_id": vm.id})

            logger.info("Queueing VM restart", extra={"vm_id": vm.vm_id})

            # Update status to restarting
            with tracer.start_as_current_span("service.vm.restart.update_status"):
                vm.status = VMStatus.RESTARTING
                session.add(vm)
                await session.commit()

                logger.info(
                    "VM status updated to restarting", extra={"vm_id": vm.vm_id}
                )

            # Queue restart task (will stop then start)
            with tracer.start_as_current_span("service.vm.restart.queue_job"):
                result = restart_vm_task.delay(
                    vm.id,
                    vm.vm_id,
                    vm.vcpu_count,
                    vm.memory_mb,
                    vm.kernel_path,
                    vm.host,
                )

                logger.info(
                    "VM restart job queued",
                    extra={"job_id": result.id, "vm_id": vm.vm_id},
                )
