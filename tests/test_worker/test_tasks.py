"""Tests for worker tasks."""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from mikrom.models.vm import VM, VMStatus
from mikrom.models.user import User
from mikrom.core.security import get_password_hash
from mikrom.worker.tasks import (
    _create_vm_task_async,
    _delete_vm_task_async,
    _stop_vm_task_async,
    _start_vm_task_async,
    _restart_vm_task_async,
)


class MockCeleryRequest:
    """Mock Celery task request object."""

    def __init__(self, task_id="test-task-123"):
        self.id = task_id


class MockCeleryTask:
    """Mock Celery task object with request."""

    def __init__(self, task_id="test-task-123"):
        self.request = MockCeleryRequest(task_id)


# ===========================================
# Tests for create_vm_task
# ===========================================


@pytest.mark.asyncio
@patch("mikrom.worker.tasks.FirecrackerClient")
@patch("mikrom.worker.tasks.Session")
async def test_create_vm_task_success(
    mock_session_class: Mock,
    mock_firecracker_class: Mock,
    db_session: AsyncSession,
) -> None:
    """Test successful VM creation task."""
    from mikrom.models.ip_pool import IpPool
    from mikrom.models.ip_allocation import IpAllocation

    # Create test user and VM
    user = User(
        email="user@example.com",
        username="user",
        hashed_password=get_password_hash("password123"),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    assert user.id is not None

    vm = VM(
        vm_id="srv-test123",
        name="test-vm",
        vcpu_count=2,
        memory_mb=2048,
        status=VMStatus.PENDING,
        user_id=user.id,
    )
    db_session.add(vm)
    await db_session.commit()
    await db_session.refresh(vm)

    # Setup mocks for IP allocation
    mock_pool = IpPool(
        id=1,
        name="default",
        network="172.16.0",
        cidr="172.16.0.0/24",
        gateway="172.16.0.1",
        start_ip="172.16.0.2",
        end_ip="172.16.0.254",
        is_active=True,
    )

    IpAllocation(
        id=1,
        pool_id=1,
        vm_id="srv-test123",
        ip_address="192.168.1.100",
        is_active=True,
    )

    # Setup mock session
    mock_session = MagicMock()
    mock_session.get.return_value = vm

    # Mock exec() to return different results for different queries
    mock_exec_result = MagicMock()

    # First call: get pool (returns pool)
    # Second call: check existing allocation (returns None - no existing)
    # Third call: get allocated IPs (returns empty set)
    mock_exec_result.first.side_effect = [mock_pool, None]
    mock_exec_result.all.return_value = []  # No allocated IPs
    mock_session.exec.return_value = mock_exec_result

    mock_session_class.return_value.__enter__.return_value = mock_session

    mock_firecracker = AsyncMock()
    mock_firecracker.start_vm = AsyncMock(return_value={"status": "successful"})
    mock_firecracker_class.return_value = mock_firecracker

    # Create mock task
    mock_task = MockCeleryTask()

    # Execute task
    result = await _create_vm_task_async(
        mock_task,
        vm_db_id=vm.id,
        vcpu_count=2,
        memory_mb=2048,
        kernel_path=None,
        host="test-host",
    )

    # Verify result
    assert result["success"] is True
    assert result["vm_id"] == "srv-test123"
    assert result["ip_address"] == "172.16.0.2"  # First available IP
    assert result["status"] == "running"

    # Verify Firecracker was called
    mock_firecracker.start_vm.assert_called_once()
    call_kwargs = mock_firecracker.start_vm.call_args.kwargs
    assert call_kwargs["vm_id"] == "srv-test123"
    assert call_kwargs["vcpu_count"] == 2
    assert call_kwargs["memory_mb"] == 2048


@pytest.mark.asyncio
@patch("mikrom.worker.tasks.FirecrackerClient")
@patch("mikrom.worker.tasks.Session")
async def test_create_vm_task_ip_allocation_failure(
    mock_session_class: Mock,
    mock_firecracker_class: Mock,
    db_session: AsyncSession,
) -> None:
    """Test VM creation task when IP allocation fails."""
    from mikrom.models.ip_pool import IpPool

    # Create test user and VM
    user = User(
        email="user@example.com",
        username="user",
        hashed_password=get_password_hash("password123"),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    assert user.id is not None

    vm = VM(
        vm_id="srv-test123",
        name="test-vm",
        vcpu_count=2,
        memory_mb=2048,
        status=VMStatus.PENDING,
        user_id=user.id,
    )
    db_session.add(vm)
    await db_session.commit()
    await db_session.refresh(vm)

    # Setup mocks - pool with all IPs allocated
    mock_pool = IpPool(
        id=1,
        name="default",
        network="172.16.0",
        cidr="172.16.0.0/24",
        gateway="172.16.0.1",
        start_ip="172.16.0.2",
        end_ip="172.16.0.3",  # Only 2 IPs available
        is_active=True,
    )

    mock_session = MagicMock()
    mock_session.get.return_value = vm

    # Mock exec() to simulate pool exhaustion
    mock_exec_result = MagicMock()

    # First call: get pool (returns pool)
    # Second call: check existing allocation (returns None)
    # Third call: get allocated IPs (returns all IPs in range)
    mock_exec_result.first.side_effect = [mock_pool, None]
    mock_exec_result.all.return_value = [
        ("172.16.0.2",),
        ("172.16.0.3",),
    ]  # All IPs allocated
    mock_session.exec.return_value = mock_exec_result

    mock_session_class.return_value.__enter__.return_value = mock_session

    mock_task = MockCeleryTask()

    # Execute task - should raise exception
    with pytest.raises(Exception, match="No available IPs in pool"):
        await _create_vm_task_async(
            mock_task,
            vm_db_id=vm.id,
            vcpu_count=2,
            memory_mb=2048,
        )

    # Verify VM status was set to error (via mock session)
    mock_session.add.assert_called()
    mock_session.commit.assert_called()


@pytest.mark.asyncio
@patch("mikrom.worker.tasks.FirecrackerClient")
@patch("mikrom.worker.tasks.Session")
async def test_create_vm_task_firecracker_failure(
    mock_session_class: Mock,
    mock_firecracker_class: Mock,
    db_session: AsyncSession,
) -> None:
    """Test VM creation task when Firecracker start fails."""
    # Create test user and VM
    user = User(
        email="user@example.com",
        username="user",
        hashed_password=get_password_hash("password123"),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    assert user.id is not None

    vm = VM(
        vm_id="srv-test123",
        name="test-vm",
        vcpu_count=2,
        memory_mb=2048,
        status=VMStatus.PENDING,
        user_id=user.id,
    )
    db_session.add(vm)
    await db_session.commit()
    await db_session.refresh(vm)

    # Setup mocks
    mock_session = MagicMock()
    mock_session.get.return_value = vm
    mock_session_class.return_value.__enter__.return_value = mock_session

    mock_firecracker = AsyncMock()
    mock_firecracker.start_vm = AsyncMock(
        side_effect=Exception("Firecracker start failed")
    )
    mock_firecracker_class.return_value = mock_firecracker

    mock_task = MockCeleryTask()

    # Execute task - should raise exception
    with pytest.raises(Exception, match="Firecracker start failed"):
        await _create_vm_task_async(
            mock_task,
            vm_db_id=vm.id,
            vcpu_count=2,
            memory_mb=2048,
        )

    # Verify IP cleanup was attempted


@pytest.mark.asyncio
@patch("mikrom.worker.tasks.Session")
async def test_create_vm_task_vm_not_found(
    mock_session_class: Mock,
) -> None:
    """Test VM creation task when VM record is not found."""
    # Setup mocks
    mock_session = MagicMock()
    mock_session.get.return_value = None  # VM not found
    mock_session_class.return_value.__enter__.return_value = mock_session

    mock_task = MockCeleryTask()

    # Execute task - should raise ValueError
    with pytest.raises(ValueError, match="not found in database"):
        await _create_vm_task_async(
            mock_task,
            vm_db_id=999,
            vcpu_count=2,
            memory_mb=2048,
        )


# ===========================================
# Tests for delete_vm_task
# ===========================================


@pytest.mark.asyncio
@patch("mikrom.worker.tasks.FirecrackerClient")
@patch("mikrom.worker.tasks.Session")
async def test_delete_vm_task_success(
    mock_session_class: Mock,
    mock_firecracker_class: Mock,
    db_session: AsyncSession,
) -> None:
    """Test successful VM deletion task."""
    # Create test user and VM
    user = User(
        email="user@example.com",
        username="user",
        hashed_password=get_password_hash("password123"),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    assert user.id is not None

    vm = VM(
        vm_id="srv-delete123",
        name="delete-vm",
        vcpu_count=2,
        memory_mb=2048,
        status=VMStatus.RUNNING,
        user_id=user.id,
        ip_address="192.168.1.100",
    )
    db_session.add(vm)
    await db_session.commit()
    await db_session.refresh(vm)

    # Setup mocks
    mock_session = MagicMock()
    mock_session.get.return_value = vm
    mock_session_class.return_value.__enter__.return_value = mock_session

    mock_firecracker = AsyncMock()
    mock_firecracker.cleanup_vm = AsyncMock()
    mock_firecracker_class.return_value = mock_firecracker

    mock_task = MockCeleryTask()

    # Execute task
    result = await _delete_vm_task_async(
        mock_task,
        vm_db_id=vm.id,
        vm_id="srv-delete123",
        host="test-host",
    )

    # Verify result
    assert result["success"] is True
    assert result["vm_id"] == "srv-delete123"
    assert result["status"] == "deleted"

    # Verify Firecracker cleanup was called
    mock_firecracker.cleanup_vm.assert_called_once_with(
        "srv-delete123", limit="test-host"
    )

    # Verify IP was released

    # Verify VM was deleted from database
    mock_session.delete.assert_called_once()


@pytest.mark.asyncio
@patch("mikrom.worker.tasks.FirecrackerClient")
@patch("mikrom.worker.tasks.Session")
async def test_delete_vm_task_firecracker_failure_continues(
    mock_session_class: Mock,
    mock_firecracker_class: Mock,
    db_session: AsyncSession,
) -> None:
    """Test delete task continues even if Firecracker cleanup fails."""
    # Create test user and VM
    user = User(
        email="user@example.com",
        username="user",
        hashed_password=get_password_hash("password123"),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    assert user.id is not None

    vm = VM(
        vm_id="srv-delete123",
        name="delete-vm",
        vcpu_count=2,
        memory_mb=2048,
        status=VMStatus.RUNNING,
        user_id=user.id,
    )
    db_session.add(vm)
    await db_session.commit()
    await db_session.refresh(vm)

    # Setup mocks
    mock_session = MagicMock()
    mock_session.get.return_value = vm
    mock_session_class.return_value.__enter__.return_value = mock_session

    # Firecracker cleanup fails but should not stop deletion
    mock_firecracker = AsyncMock()
    mock_firecracker.cleanup_vm = AsyncMock(
        side_effect=Exception("Firecracker cleanup failed")
    )
    mock_firecracker_class.return_value = mock_firecracker

    mock_task = MockCeleryTask()

    # Execute task - should succeed despite Firecracker failure
    result = await _delete_vm_task_async(
        mock_task,
        vm_db_id=vm.id,
        vm_id="srv-delete123",
    )

    # Verify deletion still succeeded
    assert result["success"] is True
    assert result["status"] == "deleted"

    # Verify IP was still released

    # Verify VM was still deleted
    mock_session.delete.assert_called_once()


# ===========================================
# Tests for stop_vm_task
# ===========================================


@pytest.mark.asyncio
@patch("mikrom.worker.tasks.FirecrackerClient")
@patch("mikrom.worker.tasks.Session")
async def test_stop_vm_task_success(
    mock_session_class: Mock,
    mock_firecracker_class: Mock,
    db_session: AsyncSession,
) -> None:
    """Test successful VM stop task."""
    # Create test user and VM
    user = User(
        email="user@example.com",
        username="user",
        hashed_password=get_password_hash("password123"),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    assert user.id is not None

    vm = VM(
        vm_id="srv-stop123",
        name="stop-vm",
        vcpu_count=2,
        memory_mb=2048,
        status=VMStatus.RUNNING,
        user_id=user.id,
    )
    db_session.add(vm)
    await db_session.commit()
    await db_session.refresh(vm)

    # Setup mocks
    mock_session = MagicMock()
    mock_session.get.return_value = vm
    mock_session_class.return_value.__enter__.return_value = mock_session

    mock_firecracker = AsyncMock()
    mock_firecracker.stop_vm = AsyncMock()
    mock_firecracker_class.return_value = mock_firecracker

    mock_task = MockCeleryTask()

    # Execute task
    result = await _stop_vm_task_async(
        mock_task,
        vm_db_id=vm.id,
        vm_id="srv-stop123",
        host="test-host",
    )

    # Verify result
    assert result["success"] is True
    assert result["vm_id"] == "srv-stop123"
    assert result["status"] == "stopped"

    # Verify Firecracker stop was called
    mock_firecracker.stop_vm.assert_called_once_with("srv-stop123", limit="test-host")


@pytest.mark.asyncio
@patch("mikrom.worker.tasks.FirecrackerClient")
@patch("mikrom.worker.tasks.Session")
async def test_stop_vm_task_failure(
    mock_session_class: Mock,
    mock_firecracker_class: Mock,
    db_session: AsyncSession,
) -> None:
    """Test VM stop task when Firecracker stop fails."""
    # Create test user and VM
    user = User(
        email="user@example.com",
        username="user",
        hashed_password=get_password_hash("password123"),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    assert user.id is not None

    vm = VM(
        vm_id="srv-stop123",
        name="stop-vm",
        vcpu_count=2,
        memory_mb=2048,
        status=VMStatus.RUNNING,
        user_id=user.id,
    )
    db_session.add(vm)
    await db_session.commit()
    await db_session.refresh(vm)

    # Setup mocks
    mock_session = MagicMock()
    mock_session.get.return_value = vm
    mock_session_class.return_value.__enter__.return_value = mock_session

    mock_firecracker = AsyncMock()
    mock_firecracker.stop_vm = AsyncMock(side_effect=Exception("Stop failed"))
    mock_firecracker_class.return_value = mock_firecracker

    mock_task = MockCeleryTask()

    # Execute task - should raise exception
    with pytest.raises(Exception, match="Stop failed"):
        await _stop_vm_task_async(
            mock_task,
            vm_db_id=vm.id,
            vm_id="srv-stop123",
        )

    # Verify VM status was set to error
    mock_session.add.assert_called()
    mock_session.commit.assert_called()


# ===========================================
# Tests for start_vm_task
# ===========================================


@pytest.mark.asyncio
@patch("mikrom.worker.tasks.FirecrackerClient")
@patch("mikrom.worker.tasks.Session")
async def test_start_vm_task_success(
    mock_session_class: Mock,
    mock_firecracker_class: Mock,
    db_session: AsyncSession,
) -> None:
    """Test successful VM start task."""
    # Create test user and VM
    user = User(
        email="user@example.com",
        username="user",
        hashed_password=get_password_hash("password123"),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    assert user.id is not None

    vm = VM(
        vm_id="srv-start123",
        name="start-vm",
        vcpu_count=2,
        memory_mb=2048,
        status=VMStatus.STOPPED,
        user_id=user.id,
        ip_address="192.168.1.100",
    )
    db_session.add(vm)
    await db_session.commit()
    await db_session.refresh(vm)

    # Setup mocks
    mock_session = MagicMock()
    mock_session.get.return_value = vm
    mock_session_class.return_value.__enter__.return_value = mock_session

    mock_firecracker = AsyncMock()
    mock_firecracker.start_vm = AsyncMock()
    mock_firecracker_class.return_value = mock_firecracker

    mock_task = MockCeleryTask()

    # Execute task
    result = await _start_vm_task_async(
        mock_task,
        vm_db_id=vm.id,
        vm_id="srv-start123",
        vcpu_count=2,
        memory_mb=2048,
        host="test-host",
    )

    # Verify result
    assert result["success"] is True
    assert result["vm_id"] == "srv-start123"
    assert result["status"] == "running"
    assert result["ip_address"] == "192.168.1.100"

    # Verify Firecracker start was called
    mock_firecracker.start_vm.assert_called_once()


@pytest.mark.asyncio
@patch("mikrom.worker.tasks.FirecrackerClient")
@patch("mikrom.worker.tasks.Session")
async def test_start_vm_task_no_ip_address(
    mock_session_class: Mock,
    mock_firecracker_class: Mock,
    db_session: AsyncSession,
) -> None:
    """Test VM start task when VM has no IP address."""
    # Create test user and VM
    user = User(
        email="user@example.com",
        username="user",
        hashed_password=get_password_hash("password123"),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    assert user.id is not None

    vm = VM(
        vm_id="srv-start123",
        name="start-vm",
        vcpu_count=2,
        memory_mb=2048,
        status=VMStatus.STOPPED,
        user_id=user.id,
        ip_address=None,  # No IP address
    )
    db_session.add(vm)
    await db_session.commit()
    await db_session.refresh(vm)

    # Setup mocks
    mock_session = MagicMock()
    mock_session.get.return_value = vm
    mock_session_class.return_value.__enter__.return_value = mock_session

    mock_firecracker = AsyncMock()
    mock_firecracker_class.return_value = mock_firecracker

    mock_task = MockCeleryTask()

    # Execute task - should raise ValueError
    with pytest.raises(ValueError, match="no IP address"):
        await _start_vm_task_async(
            mock_task,
            vm_db_id=vm.id,
            vm_id="srv-start123",
            vcpu_count=2,
            memory_mb=2048,
        )


# ===========================================
# Tests for restart_vm_task
# ===========================================


@pytest.mark.asyncio
@patch("mikrom.worker.tasks.stop_vm_task")
@patch("mikrom.worker.tasks.start_vm_task")
@patch("mikrom.worker.tasks.Session")
async def test_restart_vm_task_success(
    mock_session_class: Mock,
    mock_start_task: Mock,
    mock_stop_task: Mock,
    db_session: AsyncSession,
) -> None:
    """Test successful VM restart task."""
    # Create test user and VM
    user = User(
        email="user@example.com",
        username="user",
        hashed_password=get_password_hash("password123"),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    assert user.id is not None

    vm = VM(
        vm_id="srv-restart123",
        name="restart-vm",
        vcpu_count=2,
        memory_mb=2048,
        status=VMStatus.RUNNING,
        user_id=user.id,
    )
    db_session.add(vm)
    await db_session.commit()
    await db_session.refresh(vm)

    # Setup mocks
    mock_session = MagicMock()
    mock_session.get.return_value = vm
    mock_session_class.return_value.__enter__.return_value = mock_session

    # Mock as AsyncMock so they can be awaited
    mock_stop_task.return_value = AsyncMock(
        return_value={"success": True, "status": "stopped"}
    )()
    mock_start_task.return_value = AsyncMock(
        return_value={
            "success": True,
            "status": "running",
            "ip_address": "192.168.1.100",
        }
    )()

    mock_task = MockCeleryTask()

    # Execute task
    result = await _restart_vm_task_async(
        mock_task,
        vm_db_id=vm.id,
        vm_id="srv-restart123",
        vcpu_count=2,
        memory_mb=2048,
        host="test-host",
    )

    # Verify result
    assert result["success"] is True
    assert result["vm_id"] == "srv-restart123"
    assert result["status"] == "running"

    # Verify stop and start were called in sequence
    assert mock_stop_task.called
    assert mock_start_task.called


@pytest.mark.asyncio
@patch("mikrom.worker.tasks.stop_vm_task")
@patch("mikrom.worker.tasks.Session")
async def test_restart_vm_task_stop_failure(
    mock_session_class: Mock,
    mock_stop_task: Mock,
    db_session: AsyncSession,
) -> None:
    """Test VM restart task when stop fails."""
    # Create test user and VM
    user = User(
        email="user@example.com",
        username="user",
        hashed_password=get_password_hash("password123"),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    assert user.id is not None

    vm = VM(
        vm_id="srv-restart123",
        name="restart-vm",
        vcpu_count=2,
        memory_mb=2048,
        status=VMStatus.RUNNING,
        user_id=user.id,
    )
    db_session.add(vm)
    await db_session.commit()
    await db_session.refresh(vm)

    # Setup mocks
    mock_session = MagicMock()
    mock_session.get.return_value = vm
    mock_session_class.return_value.__enter__.return_value = mock_session

    mock_stop_task.side_effect = Exception("Stop failed")

    mock_task = MockCeleryTask()

    # Execute task - should raise exception
    with pytest.raises(Exception, match="Stop failed"):
        await _restart_vm_task_async(
            mock_task,
            vm_db_id=vm.id,
            vm_id="srv-restart123",
            vcpu_count=2,
            memory_mb=2048,
        )

    # Verify VM status was set to error
    mock_session.add.assert_called()
    mock_session.commit.assert_called()
