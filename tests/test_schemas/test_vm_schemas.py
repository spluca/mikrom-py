"""Tests for VM schemas."""

import pytest
from pydantic import ValidationError

from mikrom.schemas.vm import (
    VMCreate,
    VMUpdate,
    VMResponse,
    VMListResponse,
    VMStatusResponse,
)
from mikrom.models.vm import VMStatus


# Tests for VMCreate Schema


def test_vm_create_valid() -> None:
    """Test creating a valid VMCreate schema."""
    vm_data = {
        "name": "test-vm",
        "description": "Test VM",
        "vcpu_count": 2,
        "memory_mb": 2048,
    }
    vm = VMCreate(**vm_data)

    assert vm.name == "test-vm"
    assert vm.description == "Test VM"
    assert vm.vcpu_count == 2
    assert vm.memory_mb == 2048


def test_vm_create_without_description() -> None:
    """Test creating VMCreate without optional description."""
    vm_data = {
        "name": "test-vm",
        "vcpu_count": 2,
        "memory_mb": 2048,
    }
    vm = VMCreate(**vm_data)

    assert vm.description is None


def test_vm_create_default_resources() -> None:
    """Test VMCreate with default resource values."""
    vm_data = {
        "name": "test-vm",
    }
    vm = VMCreate(**vm_data)

    assert vm.vcpu_count == 1
    assert vm.memory_mb == 512


def test_vm_create_name_validation() -> None:
    """Test VMCreate name validation (alphanumeric and hyphens only)."""
    # Valid names
    valid_names = ["test-vm", "vm123", "my-test-vm-1", "vm"]
    for name in valid_names:
        vm = VMCreate(name=name)
        assert vm.name == name

    # Invalid names (with special characters or spaces)
    invalid_names = ["test vm", "test@vm", "test_vm", "test.vm", "test/vm"]
    for name in invalid_names:
        with pytest.raises(ValidationError):
            VMCreate(name=name)


def test_vm_create_name_length() -> None:
    """Test VMCreate name length validation."""
    # Too short (less than 1 character)
    with pytest.raises(ValidationError):
        VMCreate(name="")

    # Too long (more than 64 characters)
    with pytest.raises(ValidationError):
        VMCreate(name="a" * 65)

    # Valid length
    vm = VMCreate(name="a" * 64)
    assert len(vm.name) == 64


def test_vm_create_vcpu_count_validation() -> None:
    """Test VMCreate vcpu_count validation."""
    # Too low (less than 1)
    with pytest.raises(ValidationError):
        VMCreate(name="test-vm", vcpu_count=0)

    # Too high (more than 32)
    with pytest.raises(ValidationError):
        VMCreate(name="test-vm", vcpu_count=33)

    # Valid range
    for vcpu in [1, 2, 4, 8, 16, 32]:
        vm = VMCreate(name="test-vm", vcpu_count=vcpu)
        assert vm.vcpu_count == vcpu


def test_vm_create_memory_validation() -> None:
    """Test VMCreate memory_mb validation."""
    # Too low (less than 128 MB)
    with pytest.raises(ValidationError):
        VMCreate(name="test-vm", memory_mb=127)

    # Too high (more than 32768 MB)
    with pytest.raises(ValidationError):
        VMCreate(name="test-vm", memory_mb=32769)

    # Valid range
    for memory in [128, 512, 1024, 2048, 4096, 8192, 16384, 32768]:
        vm = VMCreate(name="test-vm", memory_mb=memory)
        assert vm.memory_mb == memory


def test_vm_create_missing_required_fields() -> None:
    """Test creating VMCreate with missing required fields."""
    # Missing name
    with pytest.raises(ValidationError):
        VMCreate(vcpu_count=2, memory_mb=2048)


# Tests for VMUpdate Schema


def test_vm_update_valid() -> None:
    """Test creating a valid VMUpdate schema."""
    update_data = {
        "name": "updated-vm",
        "description": "Updated description",
    }
    vm_update = VMUpdate(**update_data)

    assert vm_update.name == "updated-vm"
    assert vm_update.description == "Updated description"


def test_vm_update_partial() -> None:
    """Test updating VM with partial data."""
    # Only name
    update = VMUpdate(name="new-name")
    assert update.name == "new-name"
    assert update.description is None

    # Only description
    update = VMUpdate(description="New description")
    assert update.name is None
    assert update.description == "New description"


def test_vm_update_empty() -> None:
    """Test creating empty VMUpdate (all fields optional)."""
    update = VMUpdate()
    assert update.name is None
    assert update.description is None


def test_vm_update_name_validation() -> None:
    """Test VMUpdate name validation."""
    # Valid names
    update = VMUpdate(name="updated-vm")
    assert update.name == "updated-vm"

    # Invalid names
    with pytest.raises(ValidationError):
        VMUpdate(name="invalid name")


# Tests for VMResponse Schema


def test_vm_response_valid() -> None:
    """Test creating a valid VMResponse schema."""
    vm_data = {
        "id": 1,
        "vm_id": "srv-12345678",
        "name": "test-vm",
        "description": "Test VM",
        "vcpu_count": 2,
        "memory_mb": 2048,
        "ip_address": "192.168.1.100",
        "status": VMStatus.RUNNING,
        "error_message": None,
        "host": "hypervisor1.example.com",
        "kernel_path": "/var/lib/firecracker/kernels/vmlinux-5.10",
        "rootfs_path": "/var/lib/firecracker/rootfs/ubuntu-20.04.ext4",
        "user_id": 1,
        "created_at": "2024-01-01T00:00:00",
        "updated_at": "2024-01-01T00:00:00",
    }
    vm = VMResponse(**vm_data)

    assert vm.id == 1
    assert vm.vm_id == "srv-12345678"
    assert vm.name == "test-vm"
    assert vm.vcpu_count == 2
    assert vm.memory_mb == 2048
    assert vm.status == VMStatus.RUNNING


def test_vm_response_minimal() -> None:
    """Test VMResponse with minimal fields (optional fields as None)."""
    vm_data = {
        "id": 1,
        "vm_id": "srv-12345678",
        "name": "test-vm",
        "description": None,
        "vcpu_count": 1,
        "memory_mb": 512,
        "ip_address": None,
        "status": VMStatus.PENDING,
        "error_message": None,
        "host": None,
        "kernel_path": None,
        "rootfs_path": None,
        "user_id": 1,
        "created_at": "2024-01-01T00:00:00",
        "updated_at": "2024-01-01T00:00:00",
    }
    vm = VMResponse(**vm_data)

    assert vm.id == 1
    assert vm.vm_id == "srv-12345678"
    assert vm.name == "test-vm"
    assert vm.description is None
    assert vm.ip_address is None


def test_vm_response_error_state() -> None:
    """Test VMResponse with error status and error message."""
    vm_data = {
        "id": 1,
        "vm_id": "srv-12345678",
        "name": "test-vm",
        "description": None,
        "vcpu_count": 1,
        "memory_mb": 512,
        "ip_address": None,
        "status": VMStatus.ERROR,
        "error_message": "Failed to allocate IP address",
        "host": None,
        "kernel_path": None,
        "rootfs_path": None,
        "user_id": 1,
        "created_at": "2024-01-01T00:00:00",
        "updated_at": "2024-01-01T00:00:00",
    }
    vm = VMResponse(**vm_data)

    assert vm.status == VMStatus.ERROR
    assert vm.error_message == "Failed to allocate IP address"


def test_vm_response_all_statuses() -> None:
    """Test VMResponse with all possible VM statuses."""
    statuses = [
        VMStatus.PENDING,
        VMStatus.PROVISIONING,
        VMStatus.RUNNING,
        VMStatus.STOPPED,
        VMStatus.ERROR,
        VMStatus.DELETING,
    ]

    for status in statuses:
        vm_data = {
            "id": 1,
            "vm_id": "srv-12345678",
            "name": "test-vm",
            "description": None,
            "vcpu_count": 1,
            "memory_mb": 512,
            "ip_address": None,
            "status": status,
            "error_message": None,
            "host": None,
            "kernel_path": None,
            "rootfs_path": None,
            "user_id": 1,
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
        }
        vm = VMResponse(**vm_data)
        assert vm.status == status


# Tests for VMListResponse Schema


def test_vm_list_response_valid() -> None:
    """Test creating a valid VMListResponse schema."""
    vm_item = {
        "id": 1,
        "vm_id": "srv-12345678",
        "name": "test-vm",
        "description": None,
        "vcpu_count": 1,
        "memory_mb": 512,
        "ip_address": None,
        "status": VMStatus.RUNNING,
        "error_message": None,
        "host": None,
        "kernel_path": None,
        "rootfs_path": None,
        "user_id": 1,
        "created_at": "2024-01-01T00:00:00",
        "updated_at": "2024-01-01T00:00:00",
    }

    list_data = {
        "items": [vm_item, vm_item],
        "total": 2,
        "page": 1,
        "page_size": 10,
        "total_pages": 1,
    }
    vm_list = VMListResponse(**list_data)

    assert len(vm_list.items) == 2
    assert vm_list.total == 2
    assert vm_list.page == 1
    assert vm_list.page_size == 10
    assert vm_list.total_pages == 1


def test_vm_list_response_empty() -> None:
    """Test VMListResponse with no items."""
    list_data = {
        "items": [],
        "total": 0,
        "page": 1,
        "page_size": 10,
        "total_pages": 0,
    }
    vm_list = VMListResponse(**list_data)

    assert len(vm_list.items) == 0
    assert vm_list.total == 0
    assert vm_list.total_pages == 0


def test_vm_list_response_pagination() -> None:
    """Test VMListResponse pagination metadata."""
    vm_item = {
        "id": 1,
        "vm_id": "srv-12345678",
        "name": "test-vm",
        "description": None,
        "vcpu_count": 1,
        "memory_mb": 512,
        "ip_address": None,
        "status": VMStatus.RUNNING,
        "error_message": None,
        "host": None,
        "kernel_path": None,
        "rootfs_path": None,
        "user_id": 1,
        "created_at": "2024-01-01T00:00:00",
        "updated_at": "2024-01-01T00:00:00",
    }

    # Page 2 of 5 (10 items per page, 50 total)
    list_data = {
        "items": [vm_item] * 10,
        "total": 50,
        "page": 2,
        "page_size": 10,
        "total_pages": 5,
    }
    vm_list = VMListResponse(**list_data)

    assert vm_list.page == 2
    assert vm_list.total_pages == 5
    assert vm_list.page_size == 10


# Tests for VMStatusResponse Schema


def test_vm_status_response_valid() -> None:
    """Test creating a valid VMStatusResponse schema."""
    status_data = {
        "vm_id": "srv-12345678",
        "status": VMStatus.RUNNING,
        "message": "VM is running successfully",
    }
    status_response = VMStatusResponse(**status_data)

    assert status_response.vm_id == "srv-12345678"
    assert status_response.status == VMStatus.RUNNING
    assert status_response.message == "VM is running successfully"


def test_vm_status_response_error() -> None:
    """Test VMStatusResponse with error status."""
    status_data = {
        "vm_id": "srv-12345678",
        "status": VMStatus.ERROR,
        "message": "Failed to start VM: insufficient resources",
    }
    status_response = VMStatusResponse(**status_data)

    assert status_response.status == VMStatus.ERROR
    assert "insufficient resources" in status_response.message


def test_vm_status_response_all_statuses() -> None:
    """Test VMStatusResponse with all possible statuses."""
    statuses = [
        VMStatus.PENDING,
        VMStatus.PROVISIONING,
        VMStatus.RUNNING,
        VMStatus.STOPPED,
        VMStatus.ERROR,
        VMStatus.DELETING,
    ]

    for status in statuses:
        status_data = {
            "vm_id": "srv-12345678",
            "status": status,
            "message": f"VM is {status.value}",
        }
        status_response = VMStatusResponse(**status_data)
        assert status_response.status == status
