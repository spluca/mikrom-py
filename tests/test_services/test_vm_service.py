"""Tests for VM Service."""

import pytest
from unittest.mock import patch, Mock
from sqlalchemy.ext.asyncio import AsyncSession

from mikrom.models.vm import VM, VMStatus
from mikrom.models.user import User
from mikrom.services.vm_service import VMService
from mikrom.core.security import get_password_hash


@pytest.mark.asyncio
async def test_generate_vm_id() -> None:
    """Test VM ID generation."""
    service = VMService()
    vm_id = service.generate_vm_id()

    assert vm_id.startswith("srv-")
    assert len(vm_id) == 12  # srv- (4) + hex (8)

    # Generate multiple IDs to ensure uniqueness
    ids = {service.generate_vm_id() for _ in range(100)}
    assert len(ids) == 100  # All unique


@pytest.mark.asyncio
async def test_get_user_vms_superuser_sees_all(db_session: AsyncSession) -> None:
    """Test that superusers see all VMs from all users."""
    service = VMService()

    # Create superuser
    superuser = User(
        email="admin@example.com",
        username="admin",
        hashed_password=get_password_hash("admin123"),
        is_superuser=True,
    )
    db_session.add(superuser)
    await db_session.commit()
    await db_session.refresh(superuser)
    assert superuser.id is not None

    # Create regular users
    user1 = User(
        email="user1@example.com",
        username="user1",
        hashed_password=get_password_hash("password123"),
    )
    db_session.add(user1)
    await db_session.commit()
    await db_session.refresh(user1)
    assert user1.id is not None

    user2 = User(
        email="user2@example.com",
        username="user2",
        hashed_password=get_password_hash("password123"),
    )
    db_session.add(user2)
    await db_session.commit()
    await db_session.refresh(user2)
    assert user2.id is not None

    # Create VMs for user1
    for i in range(3):
        vm = VM(
            vm_id=f"srv-user1-{i:04d}",
            name=f"user1-vm-{i}",
            vcpu_count=2,
            memory_mb=2048,
            status=VMStatus.RUNNING,
            user_id=user1.id,
        )
        db_session.add(vm)

    # Create VMs for user2
    for i in range(2):
        vm = VM(
            vm_id=f"srv-user2-{i:04d}",
            name=f"user2-vm-{i}",
            vcpu_count=2,
            memory_mb=2048,
            status=VMStatus.RUNNING,
            user_id=user2.id,
        )
        db_session.add(vm)

    await db_session.commit()

    # Superuser should see all 5 VMs
    vms, total = await service.get_user_vms(db_session, superuser, offset=0, limit=10)

    assert total == 5  # All VMs from both users
    assert len(vms) == 5

    # Verify VMs from both users are present
    vm_ids = {vm.vm_id for vm in vms}
    assert "srv-user1-0000" in vm_ids
    assert "srv-user2-0000" in vm_ids


@pytest.mark.asyncio
async def test_get_user_vms_regular_user_filtered(db_session: AsyncSession) -> None:
    """Test that regular users only see their own VMs."""
    service = VMService()

    # Create user 1
    user1 = User(
        email="user1@example.com",
        username="user1",
        hashed_password=get_password_hash("password123"),
        is_superuser=False,
    )
    db_session.add(user1)
    await db_session.commit()
    await db_session.refresh(user1)
    assert user1.id is not None

    # Create user 2
    user2 = User(
        email="user2@example.com",
        username="user2",
        hashed_password=get_password_hash("password123"),
        is_superuser=False,
    )
    db_session.add(user2)
    await db_session.commit()
    await db_session.refresh(user2)
    assert user2.id is not None

    # Create VMs for user1
    for i in range(3):
        vm = VM(
            vm_id=f"srv-user1-{i:04d}",
            name=f"user1-vm-{i}",
            vcpu_count=2,
            memory_mb=2048,
            status=VMStatus.RUNNING,
            user_id=user1.id,
        )
        db_session.add(vm)

    # Create VMs for user2
    for i in range(2):
        vm = VM(
            vm_id=f"srv-user2-{i:04d}",
            name=f"user2-vm-{i}",
            vcpu_count=2,
            memory_mb=2048,
            status=VMStatus.RUNNING,
            user_id=user2.id,
        )
        db_session.add(vm)

    await db_session.commit()

    # User1 should only see their own 3 VMs
    vms, total = await service.get_user_vms(db_session, user1, offset=0, limit=10)

    assert total == 3  # Only user1's VMs
    assert len(vms) == 3

    # Verify only user1's VMs are returned
    vm_ids = {vm.vm_id for vm in vms}
    assert "srv-user1-0000" in vm_ids
    assert "srv-user1-0001" in vm_ids
    assert "srv-user1-0002" in vm_ids
    assert "srv-user2-0000" not in vm_ids  # User2's VMs not visible


@pytest.mark.asyncio
async def test_get_user_vms_pagination_superuser(db_session: AsyncSession) -> None:
    """Test pagination works correctly for superusers."""
    service = VMService()

    # Create superuser
    superuser = User(
        email="admin@example.com",
        username="admin",
        hashed_password=get_password_hash("admin123"),
        is_superuser=True,
    )
    db_session.add(superuser)
    await db_session.commit()
    await db_session.refresh(superuser)
    assert superuser.id is not None

    # Create regular user
    user = User(
        email="user@example.com",
        username="user",
        hashed_password=get_password_hash("password123"),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    assert user.id is not None

    # Create 15 VMs
    for i in range(15):
        vm = VM(
            vm_id=f"srv-test-{i:04d}",
            name=f"test-vm-{i}",
            vcpu_count=2,
            memory_mb=2048,
            status=VMStatus.RUNNING,
            user_id=user.id,
        )
        db_session.add(vm)

    await db_session.commit()

    # First page (10 VMs)
    vms, total = await service.get_user_vms(db_session, superuser, offset=0, limit=10)
    assert total == 15
    assert len(vms) == 10

    # Second page (5 VMs)
    vms, total = await service.get_user_vms(db_session, superuser, offset=10, limit=10)
    assert total == 15
    assert len(vms) == 5


@pytest.mark.asyncio
async def test_get_user_vms_pagination_regular_user(db_session: AsyncSession) -> None:
    """Test pagination works correctly for regular users."""
    service = VMService()

    # Create user
    user = User(
        email="user@example.com",
        username="user",
        hashed_password=get_password_hash("password123"),
        is_superuser=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    assert user.id is not None

    # Create 15 VMs for this user
    for i in range(15):
        vm = VM(
            vm_id=f"srv-test-{i:04d}",
            name=f"test-vm-{i}",
            vcpu_count=2,
            memory_mb=2048,
            status=VMStatus.RUNNING,
            user_id=user.id,
        )
        db_session.add(vm)

    await db_session.commit()

    # First page (10 VMs)
    vms, total = await service.get_user_vms(db_session, user, offset=0, limit=10)
    assert total == 15
    assert len(vms) == 10

    # Second page (5 VMs)
    vms, total = await service.get_user_vms(db_session, user, offset=10, limit=10)
    assert total == 15
    assert len(vms) == 5


@pytest.mark.asyncio
async def test_get_vm_by_id_superuser_can_access_any(db_session: AsyncSession) -> None:
    """Test that superuser can access any user's VM by ID."""
    service = VMService()

    # Create superuser
    superuser = User(
        email="admin@example.com",
        username="admin",
        hashed_password=get_password_hash("admin123"),
        is_superuser=True,
    )
    db_session.add(superuser)
    await db_session.commit()
    await db_session.refresh(superuser)

    # Create regular user
    user = User(
        email="user@example.com",
        username="user",
        hashed_password=get_password_hash("password123"),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    assert user.id is not None

    # Create VM for regular user
    vm = VM(
        vm_id="srv-uservm",
        name="user-vm",
        vcpu_count=2,
        memory_mb=2048,
        status=VMStatus.RUNNING,
        user_id=user.id,
    )
    db_session.add(vm)
    await db_session.commit()

    # Superuser should be able to get user's VM
    result = await service.get_vm_by_id(db_session, "srv-uservm", superuser)

    assert result is not None
    assert result.vm_id == "srv-uservm"
    assert result.name == "user-vm"


@pytest.mark.asyncio
async def test_get_vm_by_id_regular_user_cannot_access_others(
    db_session: AsyncSession,
) -> None:
    """Test that regular users cannot access other users' VMs."""
    service = VMService()

    # Create user 1
    user1 = User(
        email="user1@example.com",
        username="user1",
        hashed_password=get_password_hash("password123"),
    )
    db_session.add(user1)
    await db_session.commit()
    await db_session.refresh(user1)
    assert user1.id is not None

    # Create user 2
    user2 = User(
        email="user2@example.com",
        username="user2",
        hashed_password=get_password_hash("password123"),
    )
    db_session.add(user2)
    await db_session.commit()
    await db_session.refresh(user2)
    assert user2.id is not None

    # Create VM for user1
    vm = VM(
        vm_id="srv-user1vm",
        name="user1-vm",
        vcpu_count=2,
        memory_mb=2048,
        status=VMStatus.RUNNING,
        user_id=user1.id,
    )
    db_session.add(vm)
    await db_session.commit()

    # User2 should NOT be able to get user1's VM
    result = await service.get_vm_by_id(db_session, "srv-user1vm", user2)

    assert result is None  # Access denied


@pytest.mark.asyncio
async def test_get_vm_by_id_user_can_access_own(db_session: AsyncSession) -> None:
    """Test that users can access their own VMs."""
    service = VMService()

    # Create user
    user = User(
        email="user@example.com",
        username="user",
        hashed_password=get_password_hash("password123"),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    assert user.id is not None

    # Create VM for user
    vm = VM(
        vm_id="srv-myvm",
        name="my-vm",
        vcpu_count=2,
        memory_mb=2048,
        status=VMStatus.RUNNING,
        user_id=user.id,
    )
    db_session.add(vm)
    await db_session.commit()

    # User should be able to get their own VM
    result = await service.get_vm_by_id(db_session, "srv-myvm", user)

    assert result is not None
    assert result.vm_id == "srv-myvm"
    assert result.name == "my-vm"


@pytest.mark.asyncio
async def test_get_vm_by_id_nonexistent(db_session: AsyncSession) -> None:
    """Test getting a VM that doesn't exist."""
    service = VMService()

    # Create user
    user = User(
        email="user@example.com",
        username="user",
        hashed_password=get_password_hash("password123"),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Try to get non-existent VM
    result = await service.get_vm_by_id(db_session, "srv-nonexist", user)

    assert result is None


# ===========================================
# Tests for VM Lifecycle Operations
# ===========================================


@pytest.mark.asyncio
@patch("mikrom.services.vm_service.create_vm_task.delay")
async def test_create_vm_queues_task(
    mock_delay: Mock, db_session: AsyncSession
) -> None:
    """Test that create_vm creates DB record and queues Celery task."""
    # Setup mock
    mock_delay.return_value = Mock(id="task-123")

    service = VMService()

    # Create user
    user = User(
        email="user@example.com",
        username="user",
        hashed_password=get_password_hash("password123"),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    assert user.id is not None

    # Create VM
    vm = await service.create_vm(
        db_session,
        user,
        name="test-vm",
        vcpu_count=2,
        memory_mb=2048,
        description="Test VM",
    )

    # Verify VM record was created with correct status
    assert vm.id is not None
    assert vm.vm_id.startswith("srv-")
    assert vm.name == "test-vm"
    assert vm.vcpu_count == 2
    assert vm.memory_mb == 2048
    assert vm.description == "Test VM"
    assert vm.status == VMStatus.PENDING
    assert vm.user_id == user.id

    # Verify Celery task was queued
    mock_delay.assert_called_once()
    call_args = mock_delay.call_args[0]
    assert call_args[0] == vm.id  # VM DB ID
    assert call_args[1] == 2  # vcpu_count
    assert call_args[2] == 2048  # memory_mb
    assert call_args[3] is None  # kernel_path (not provided)


@pytest.mark.asyncio
@patch("mikrom.services.vm_service.create_vm_task.delay")
async def test_create_vm_with_custom_kernel(
    mock_delay: Mock, db_session: AsyncSession
) -> None:
    """Test creating VM with custom kernel path."""
    mock_delay.return_value = Mock(id="task-456")

    service = VMService()

    # Create user
    user = User(
        email="user@example.com",
        username="user",
        hashed_password=get_password_hash("password123"),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    assert user.id is not None

    # Create VM with custom kernel
    vm = await service.create_vm(
        db_session,
        user,
        name="kernel-vm",
        vcpu_count=4,
        memory_mb=4096,
        kernel_path="/custom/kernel/vmlinux",
    )

    # Verify VM was created with kernel path
    assert vm.kernel_path == "/custom/kernel/vmlinux"
    assert vm.status == VMStatus.PENDING

    # Verify task was called with kernel path
    mock_delay.assert_called_once()
    call_args = mock_delay.call_args[0]
    assert call_args[3] == "/custom/kernel/vmlinux"


@pytest.mark.asyncio
@patch("mikrom.services.vm_service.delete_vm_task.delay")
async def test_delete_vm_queues_task(
    mock_delay: Mock, db_session: AsyncSession
) -> None:
    """Test that delete_vm updates status and queues Celery task."""
    mock_delay.return_value = Mock(id="task-delete-123")

    service = VMService()

    # Create user
    user = User(
        email="user@example.com",
        username="user",
        hashed_password=get_password_hash("password123"),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    assert user.id is not None

    # Create VM
    vm = VM(
        vm_id="srv-test",
        name="test-vm",
        vcpu_count=2,
        memory_mb=2048,
        status=VMStatus.RUNNING,
        user_id=user.id,
        host="test-host.example.com",
    )
    db_session.add(vm)
    await db_session.commit()
    await db_session.refresh(vm)

    original_status = vm.status

    # Delete VM
    await service.delete_vm(db_session, vm)

    # Verify status was updated to DELETING
    await db_session.refresh(vm)
    assert vm.status == VMStatus.DELETING
    assert original_status == VMStatus.RUNNING  # Was running before

    # Verify Celery task was queued
    mock_delay.assert_called_once()
    call_args = mock_delay.call_args[0]
    assert call_args[0] == vm.id  # VM DB ID
    assert call_args[1] == "srv-test"  # vm_id
    assert call_args[2] == "test-host.example.com"  # host


@pytest.mark.asyncio
@patch("mikrom.services.vm_service.stop_vm_task.delay")
async def test_stop_vm_queues_task(mock_delay: Mock, db_session: AsyncSession) -> None:
    """Test that stop_vm updates status and queues Celery task."""
    mock_delay.return_value = Mock(id="task-stop-123")

    service = VMService()

    # Create user
    user = User(
        email="user@example.com",
        username="user",
        hashed_password=get_password_hash("password123"),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    assert user.id is not None

    # Create running VM
    vm = VM(
        vm_id="srv-running",
        name="running-vm",
        vcpu_count=2,
        memory_mb=2048,
        status=VMStatus.RUNNING,
        user_id=user.id,
        host="test-host.example.com",
    )
    db_session.add(vm)
    await db_session.commit()
    await db_session.refresh(vm)

    # Stop VM
    await service.stop_vm(db_session, vm)

    # Verify status was updated to STOPPING
    await db_session.refresh(vm)
    assert vm.status == VMStatus.STOPPING

    # Verify Celery task was queued
    mock_delay.assert_called_once()
    call_args = mock_delay.call_args[0]
    assert call_args[0] == vm.id
    assert call_args[1] == "srv-running"
    assert call_args[2] == "test-host.example.com"


@pytest.mark.asyncio
@patch("mikrom.services.vm_service.start_vm_task.delay")
async def test_start_vm_queues_task(mock_delay: Mock, db_session: AsyncSession) -> None:
    """Test that start_vm updates status and queues Celery task."""
    mock_delay.return_value = Mock(id="task-start-123")

    service = VMService()

    # Create user
    user = User(
        email="user@example.com",
        username="user",
        hashed_password=get_password_hash("password123"),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    assert user.id is not None

    # Create stopped VM
    vm = VM(
        vm_id="srv-stopped",
        name="stopped-vm",
        vcpu_count=4,
        memory_mb=4096,
        status=VMStatus.STOPPED,
        user_id=user.id,
        host="test-host.example.com",
        kernel_path="/custom/kernel",
    )
    db_session.add(vm)
    await db_session.commit()
    await db_session.refresh(vm)

    # Start VM
    await service.start_vm(db_session, vm)

    # Verify status was updated to STARTING
    await db_session.refresh(vm)
    assert vm.status == VMStatus.STARTING

    # Verify Celery task was queued with all parameters
    mock_delay.assert_called_once()
    call_args = mock_delay.call_args[0]
    assert call_args[0] == vm.id  # VM DB ID
    assert call_args[1] == "srv-stopped"  # vm_id
    assert call_args[2] == 4  # vcpu_count
    assert call_args[3] == 4096  # memory_mb
    assert call_args[4] == "/custom/kernel"  # kernel_path
    assert call_args[5] == "test-host.example.com"  # host


@pytest.mark.asyncio
@patch("mikrom.services.vm_service.restart_vm_task.delay")
async def test_restart_vm_queues_task(
    mock_delay: Mock, db_session: AsyncSession
) -> None:
    """Test that restart_vm updates status and queues Celery task."""
    mock_delay.return_value = Mock(id="task-restart-123")

    service = VMService()

    # Create user
    user = User(
        email="user@example.com",
        username="user",
        hashed_password=get_password_hash("password123"),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    assert user.id is not None

    # Create running VM
    vm = VM(
        vm_id="srv-restart",
        name="restart-vm",
        vcpu_count=2,
        memory_mb=2048,
        status=VMStatus.RUNNING,
        user_id=user.id,
        host="test-host.example.com",
    )
    db_session.add(vm)
    await db_session.commit()
    await db_session.refresh(vm)

    # Restart VM
    await service.restart_vm(db_session, vm)

    # Verify status was updated to RESTARTING
    await db_session.refresh(vm)
    assert vm.status == VMStatus.RESTARTING

    # Verify Celery task was queued
    mock_delay.assert_called_once()
    call_args = mock_delay.call_args[0]
    assert call_args[0] == vm.id
    assert call_args[1] == "srv-restart"
    assert call_args[2] == 2  # vcpu_count
    assert call_args[3] == 2048  # memory_mb


@pytest.mark.asyncio
@patch("mikrom.services.vm_service.create_vm_task.delay")
async def test_create_vm_generates_unique_ids(
    mock_delay: Mock, db_session: AsyncSession
) -> None:
    """Test that multiple VM creations generate unique IDs."""
    mock_delay.return_value = Mock(id="task-123")

    service = VMService()

    # Create user
    user = User(
        email="user@example.com",
        username="user",
        hashed_password=get_password_hash("password123"),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    assert user.id is not None

    # Create multiple VMs
    vm_ids = set()
    for i in range(5):
        vm = await service.create_vm(
            db_session,
            user,
            name=f"test-vm-{i}",
            vcpu_count=2,
            memory_mb=2048,
        )
        vm_ids.add(vm.vm_id)

    # All IDs should be unique
    assert len(vm_ids) == 5

    # All should start with srv-
    assert all(vm_id.startswith("srv-") for vm_id in vm_ids)
