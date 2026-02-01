"""Tests for VM database model."""

import pytest
from datetime import datetime
from sqlmodel import Session, create_engine, SQLModel, select

from mikrom.models.user import User
from mikrom.models.vm import VM, VMStatus
from mikrom.core.security import get_password_hash


@pytest.fixture
def test_engine():
    """Create a test database engine."""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def test_session(test_engine):
    """Create a test database session."""
    with Session(test_engine) as session:
        yield session


@pytest.fixture
def test_user(test_session: Session) -> User:
    """Create a test user for VM relationships."""
    user = User(
        email="test@example.com",
        username="testuser",
        hashed_password=get_password_hash("password123"),
    )
    test_session.add(user)
    test_session.commit()
    test_session.refresh(user)
    return user


def test_vm_model_creation(test_session: Session, test_user: User) -> None:
    """Test creating a VM model."""
    vm = VM(
        vm_id="srv-12345678",
        name="test-vm",
        description="Test VM",
        vcpu_count=2,
        memory_mb=2048,
        status=VMStatus.PENDING,
        user_id=test_user.id,
    )

    test_session.add(vm)
    test_session.commit()
    test_session.refresh(vm)

    assert vm.id is not None
    assert vm.vm_id == "srv-12345678"
    assert vm.name == "test-vm"
    assert vm.description == "Test VM"
    assert vm.vcpu_count == 2
    assert vm.memory_mb == 2048
    assert vm.status == VMStatus.PENDING
    assert vm.user_id == test_user.id


def test_vm_model_timestamps(test_session: Session, test_user: User) -> None:
    """Test that timestamps are automatically set."""
    vm = VM(
        vm_id="srv-12345678",
        name="test-vm",
        vcpu_count=2,
        memory_mb=2048,
        status=VMStatus.PENDING,
        user_id=test_user.id,
    )

    test_session.add(vm)
    test_session.commit()
    test_session.refresh(vm)

    assert vm.created_at is not None
    assert vm.updated_at is not None
    assert isinstance(vm.created_at, datetime)
    assert isinstance(vm.updated_at, datetime)


def test_vm_model_status_enum(test_session: Session, test_user: User) -> None:
    """Test VM status enum values."""
    statuses = [
        VMStatus.PENDING,
        VMStatus.PROVISIONING,
        VMStatus.RUNNING,
        VMStatus.STOPPED,
        VMStatus.ERROR,
        VMStatus.DELETING,
    ]

    for status in statuses:
        vm = VM(
            vm_id=f"srv-{status.value}",
            name=f"test-vm-{status.value}",
            vcpu_count=1,
            memory_mb=512,
            status=status,
            user_id=test_user.id,
        )
        test_session.add(vm)
        test_session.commit()
        test_session.refresh(vm)

        assert vm.status == status


def test_vm_model_unique_vm_id(test_session: Session, test_user: User) -> None:
    """Test that vm_id must be unique."""
    vm1 = VM(
        vm_id="srv-12345678",
        name="test-vm-1",
        vcpu_count=1,
        memory_mb=512,
        status=VMStatus.PENDING,
        user_id=test_user.id,
    )

    vm2 = VM(
        vm_id="srv-12345678",
        name="test-vm-2",
        vcpu_count=1,
        memory_mb=512,
        status=VMStatus.PENDING,
        user_id=test_user.id,
    )

    test_session.add(vm1)
    test_session.commit()

    test_session.add(vm2)
    with pytest.raises(Exception):  # SQLAlchemy will raise IntegrityError
        test_session.commit()


def test_vm_model_user_relationship(test_session: Session, test_user: User) -> None:
    """Test VM-User relationship."""
    vm = VM(
        vm_id="srv-12345678",
        name="test-vm",
        vcpu_count=2,
        memory_mb=2048,
        status=VMStatus.PENDING,
        user_id=test_user.id,
    )

    test_session.add(vm)
    test_session.commit()
    test_session.refresh(vm)

    # Query user and check VMs
    statement = select(User).where(User.id == test_user.id)
    user = test_session.exec(statement).first()

    assert user is not None
    assert len(user.vms) == 1
    assert user.vms[0].vm_id == "srv-12345678"
    assert user.vms[0].name == "test-vm"


def test_vm_model_optional_fields(test_session: Session, test_user: User) -> None:
    """Test that optional fields can be None."""
    vm = VM(
        vm_id="srv-12345678",
        name="test-vm",
        vcpu_count=2,
        memory_mb=2048,
        status=VMStatus.PENDING,
        user_id=test_user.id,
    )

    test_session.add(vm)
    test_session.commit()
    test_session.refresh(vm)

    assert vm.description is None
    assert vm.ip_address is None
    assert vm.error_message is None
    assert vm.host is None
    assert vm.kernel_path is None
    assert vm.rootfs_path is None


def test_vm_model_with_all_fields(test_session: Session, test_user: User) -> None:
    """Test creating a VM with all fields populated."""
    vm = VM(
        vm_id="srv-12345678",
        name="test-vm",
        description="Full test VM",
        vcpu_count=4,
        memory_mb=4096,
        ip_address="192.168.1.100",
        status=VMStatus.RUNNING,
        error_message=None,
        host="hypervisor1.example.com",
        kernel_path="/var/lib/firecracker/kernels/vmlinux-5.10",
        rootfs_path="/var/lib/firecracker/rootfs/ubuntu-20.04.ext4",
        user_id=test_user.id,
    )

    test_session.add(vm)
    test_session.commit()
    test_session.refresh(vm)

    assert vm.vm_id == "srv-12345678"
    assert vm.name == "test-vm"
    assert vm.description == "Full test VM"
    assert vm.vcpu_count == 4
    assert vm.memory_mb == 4096
    assert vm.ip_address == "192.168.1.100"
    assert vm.status == VMStatus.RUNNING
    assert vm.host == "hypervisor1.example.com"
    assert vm.kernel_path == "/var/lib/firecracker/kernels/vmlinux-5.10"
    assert vm.rootfs_path == "/var/lib/firecracker/rootfs/ubuntu-20.04.ext4"


def test_vm_model_query_by_vm_id(test_session: Session, test_user: User) -> None:
    """Test querying VM by vm_id."""
    vm = VM(
        vm_id="srv-12345678",
        name="test-vm",
        vcpu_count=2,
        memory_mb=2048,
        status=VMStatus.PENDING,
        user_id=test_user.id,
    )

    test_session.add(vm)
    test_session.commit()

    # Query by vm_id
    statement = select(VM).where(VM.vm_id == "srv-12345678")
    found_vm = test_session.exec(statement).first()

    assert found_vm is not None
    assert found_vm.vm_id == "srv-12345678"
    assert found_vm.name == "test-vm"


def test_vm_model_query_by_user(test_session: Session, test_user: User) -> None:
    """Test querying VMs by user."""
    # Create multiple VMs for the user
    for i in range(3):
        vm = VM(
            vm_id=f"srv-1234567{i}",
            name=f"test-vm-{i}",
            vcpu_count=1,
            memory_mb=512,
            status=VMStatus.PENDING,
            user_id=test_user.id,
        )
        test_session.add(vm)

    test_session.commit()

    # Query VMs by user
    statement = select(VM).where(VM.user_id == test_user.id)
    user_vms = test_session.exec(statement).all()

    assert len(user_vms) == 3
    assert all(vm.user_id == test_user.id for vm in user_vms)


def test_vm_model_query_by_status(test_session: Session, test_user: User) -> None:
    """Test querying VMs by status."""
    # Create VMs with different statuses
    vm1 = VM(
        vm_id="srv-12345671",
        name="pending-vm",
        vcpu_count=1,
        memory_mb=512,
        status=VMStatus.PENDING,
        user_id=test_user.id,
    )
    vm2 = VM(
        vm_id="srv-12345672",
        name="running-vm",
        vcpu_count=1,
        memory_mb=512,
        status=VMStatus.RUNNING,
        user_id=test_user.id,
    )

    test_session.add(vm1)
    test_session.add(vm2)
    test_session.commit()

    # Query running VMs
    statement = select(VM).where(VM.status == VMStatus.RUNNING)
    running_vms = test_session.exec(statement).all()

    assert len(running_vms) == 1
    assert running_vms[0].name == "running-vm"


def test_vm_model_update(test_session: Session, test_user: User) -> None:
    """Test updating VM model."""
    vm = VM(
        vm_id="srv-12345678",
        name="test-vm",
        vcpu_count=2,
        memory_mb=2048,
        status=VMStatus.PENDING,
        user_id=test_user.id,
    )

    test_session.add(vm)
    test_session.commit()
    test_session.refresh(vm)

    # Update VM
    vm.status = VMStatus.RUNNING
    vm.ip_address = "192.168.1.100"
    test_session.commit()
    test_session.refresh(vm)

    assert vm.status == VMStatus.RUNNING
    assert vm.ip_address == "192.168.1.100"


def test_vm_model_delete(test_session: Session, test_user: User) -> None:
    """Test deleting VM model."""
    vm = VM(
        vm_id="srv-12345678",
        name="test-vm",
        vcpu_count=2,
        memory_mb=2048,
        status=VMStatus.PENDING,
        user_id=test_user.id,
    )

    test_session.add(vm)
    test_session.commit()
    vm_id = vm.id

    # Delete VM
    test_session.delete(vm)
    test_session.commit()

    # Query should return None
    statement = select(VM).where(VM.id == vm_id)
    found_vm = test_session.exec(statement).first()
    assert found_vm is None


def test_vm_model_required_fields(test_session: Session, test_user: User) -> None:
    """Test that required fields must be provided."""
    # Missing vm_id
    with pytest.raises(Exception):
        vm = VM(
            name="test-vm",
            vcpu_count=2,
            memory_mb=2048,
            status=VMStatus.PENDING,
            user_id=test_user.id,
        )
        test_session.add(vm)
        test_session.commit()

    test_session.rollback()

    # Missing name
    with pytest.raises(Exception):
        vm = VM(
            vm_id="srv-12345678",
            vcpu_count=2,
            memory_mb=2048,
            status=VMStatus.PENDING,
            user_id=test_user.id,
        )
        test_session.add(vm)
        test_session.commit()

    test_session.rollback()

    # Missing user_id
    with pytest.raises(Exception):
        vm = VM(
            vm_id="srv-12345678",
            name="test-vm",
            vcpu_count=2,
            memory_mb=2048,
            status=VMStatus.PENDING,
        )
        test_session.add(vm)
        test_session.commit()


def test_vm_model_error_state(test_session: Session, test_user: User) -> None:
    """Test VM in error state with error message."""
    vm = VM(
        vm_id="srv-12345678",
        name="test-vm",
        vcpu_count=2,
        memory_mb=2048,
        status=VMStatus.ERROR,
        error_message="Failed to allocate IP address",
        user_id=test_user.id,
    )

    test_session.add(vm)
    test_session.commit()
    test_session.refresh(vm)

    assert vm.status == VMStatus.ERROR
    assert vm.error_message == "Failed to allocate IP address"
