"""VM management service."""

import secrets
from typing import Optional, List
from sqlmodel import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from arq import create_pool
from arq.connections import ArqRedis

from mikrom.models import VM, User, VMStatus
from mikrom.config import settings
from mikrom.utils.logger import get_logger
from mikrom.utils.context import set_context, operation_context
from mikrom.utils.telemetry import get_tracer, add_span_attributes
from mikrom.worker.settings import get_redis_settings

logger = get_logger(__name__)
tracer = get_tracer()


class VMService:
    """Service for VM management operations."""

    def __init__(self):
        """Initialize service."""
        self._redis: Optional[ArqRedis] = None

    async def get_redis_pool(self) -> ArqRedis:
        """Get or create Redis pool for arq."""
        if self._redis is None:
            from mikrom.config import settings as app_settings

            self._redis = await create_pool(
                get_redis_settings(), default_queue_name=app_settings.ARQ_QUEUE_NAME
            )
        return self._redis

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
        with tracer.start_as_current_span("service.vm.create") as span:
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
                        "name": name,
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

            # Queue background task to actually create the VM
            with tracer.start_as_current_span("service.vm.create.queue_job"):
                logger.info("Queueing VM creation background job")

                redis = await self.get_redis_pool()
                job = await redis.enqueue_job(
                    "create_vm_task",
                    vm.id,
                    vcpu_count,
                    memory_mb,
                    kernel_path,
                    settings.FIRECRACKER_DEFAULT_HOST,
                )

                if job:
                    logger.info("VM creation job queued", extra={"job_id": job.job_id})
                else:
                    logger.warning("Job enqueued but no job ID returned")

            return vm

    async def get_user_vms(
        self, session: AsyncSession, user: User, offset: int = 0, limit: int = 10
    ) -> tuple[List[VM], int]:
        """
        Get user's VMs with pagination.

        Args:
            session: Database session
            user: User
            offset: Pagination offset
            limit: Pagination limit

        Returns:
            Tuple of (VMs list, total count)
        """
        # Get VMs
        statement = (
            select(VM)
            .where(VM.user_id == user.id)
            .offset(offset)
            .limit(limit)
            .order_by(VM.created_at.desc())
        )
        result = await session.execute(statement)
        vms = list(result.scalars().all())

        # Get total count
        count_statement = (
            select(func.count()).select_from(VM).where(VM.user_id == user.id)
        )
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
        with tracer.start_as_current_span("service.vm.delete") as span:
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
                redis = await self.get_redis_pool()
                job = await redis.enqueue_job(
                    "delete_vm_task",
                    vm.id,
                    vm.vm_id,
                    vm.host,
                )

                if job:
                    logger.info(
                        "VM deletion job queued",
                        extra={"job_id": job.job_id, "vm_id": vm.vm_id},
                    )
                else:
                    logger.warning(
                        "Job enqueued but no job ID returned", extra={"vm_id": vm.vm_id}
                    )

    async def close(self):
        """Close service resources."""
        if self._redis:
            await self._redis.close()
