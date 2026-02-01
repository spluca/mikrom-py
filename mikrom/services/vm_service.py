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

logger = get_logger(__name__)


class VMService:
    """Service for VM management operations."""

    def __init__(self):
        """Initialize service."""
        self._redis: Optional[ArqRedis] = None

    async def get_redis_pool(self) -> ArqRedis:
        """Get or create Redis pool for arq."""
        if self._redis is None:
            self._redis = await create_pool(
                settings.REDIS_URL,
                job_timeout=300,
                keep_result=3600,
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
        # Generate unique VM ID
        vm_id = self.generate_vm_id()

        # Create VM record in database
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

        logger.info(f"Created VM record {vm.id} ({vm_id}) for user {user.username}")

        # Queue background task to actually create the VM
        redis = await self.get_redis_pool()
        job = await redis.enqueue_job(
            "create_vm_task",
            vm.id,
            vcpu_count,
            memory_mb,
            kernel_path,
            settings.FIRECRACKER_DEFAULT_HOST,
        )

        logger.info(f"Queued VM creation job {job.job_id} for VM {vm_id}")

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
        logger.info(f"Queueing deletion for VM {vm.vm_id}")

        # Update status to deleting
        vm.status = VMStatus.DELETING
        session.add(vm)
        await session.commit()

        # Queue background task
        redis = await self.get_redis_pool()
        job = await redis.enqueue_job(
            "delete_vm_task",
            vm.id,
            vm.vm_id,
            vm.host,
        )

        logger.info(f"Queued VM deletion job {job.job_id} for VM {vm.vm_id}")

    async def close(self):
        """Close service resources."""
        if self._redis:
            await self._redis.close()
