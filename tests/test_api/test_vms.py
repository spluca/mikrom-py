"""Tests for VM API endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from mikrom.models.vm import VM, VMStatus
from mikrom.models.user import User


@pytest.mark.asyncio
async def test_create_vm_unauthorized(client: AsyncClient) -> None:
    """Test creating a VM without authentication."""
    response = await client.post(
        "/api/v1/vms/",
        json={
            "name": "test-vm",
            "vcpu_count": 2,
            "memory_mb": 2048,
        },
    )
    assert response.status_code == 401
    response = await client.post(
        "/api/v1/vms/",
        json={
            "name": "test-vm",
            "vcpu_count": 2,
            "memory_mb": 2048,
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_vm_invalid_name(client: AsyncClient) -> None:
    """Test creating a VM with invalid name."""
    # Register and login
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "test@example.com",
            "username": "testuser",
            "password": "testpassword123",
        },
    )

    login_response = await client.post(
        "/api/v1/auth/login",
        data={
            "username": "testuser",
            "password": "testpassword123",
        },
    )
    token = login_response.json()["access_token"]

    # Create VM with invalid name (spaces and special characters)
    response = await client.post(
        "/api/v1/vms/",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "invalid name!@#",
            "vcpu_count": 2,
            "memory_mb": 2048,
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_vm_invalid_resources(client: AsyncClient) -> None:
    """Test creating a VM with invalid resource limits."""
    # Register and login
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "test@example.com",
            "username": "testuser",
            "password": "testpassword123",
        },
    )

    login_response = await client.post(
        "/api/v1/auth/login",
        data={
            "username": "testuser",
            "password": "testpassword123",
        },
    )
    token = login_response.json()["access_token"]

    # Too many vCPUs
    response = await client.post(
        "/api/v1/vms/",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "test-vm",
            "vcpu_count": 100,
            "memory_mb": 2048,
        },
    )
    assert response.status_code == 422

    # Too little memory
    response = await client.post(
        "/api/v1/vms/",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "test-vm",
            "vcpu_count": 2,
            "memory_mb": 50,
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_vms(client: AsyncClient, test_user: User, test_vm: VM) -> None:
    """Test listing VMs with pagination."""
    # Login
    login_response = await client.post(
        "/api/v1/auth/login",
        data={
            "username": "testuser",
            "password": "password123",
        },
    )
    token = login_response.json()["access_token"]

    # List VMs
    response = await client.get(
        "/api/v1/vms/?page=1&page_size=10",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "page_size" in data
    assert "total_pages" in data
    assert len(data["items"]) >= 1
    assert data["items"][0]["vm_id"] == "srv-test1234"


@pytest.mark.asyncio
async def test_list_vms_unauthorized(client: AsyncClient) -> None:
    """Test listing VMs without authentication."""
    response = await client.get("/api/v1/vms/")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_vms_pagination(
    client: AsyncClient, test_user: User, db_session: AsyncSession
) -> None:
    """Test VM list pagination."""
    # Create multiple VMs
    for i in range(15):
        vm = VM(
            vm_id=f"srv-test{i:04d}",
            name=f"test-vm-{i}",
            vcpu_count=1,
            memory_mb=512,
            status=VMStatus.RUNNING,
            user_id=test_user.id,
        )
        db_session.add(vm)
    await db_session.commit()

    # Login
    login_response = await client.post(
        "/api/v1/auth/login",
        data={
            "username": "testuser",
            "password": "password123",
        },
    )
    token = login_response.json()["access_token"]

    # Get first page
    response = await client.get(
        "/api/v1/vms/?page=1&page_size=10",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 10
    assert data["total"] == 15
    assert data["page"] == 1
    assert data["total_pages"] == 2

    # Get second page
    response = await client.get(
        "/api/v1/vms/?page=2&page_size=10",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 5
    assert data["page"] == 2


@pytest.mark.asyncio
async def test_get_vm_by_id(client: AsyncClient, test_user: User, test_vm: VM) -> None:
    """Test getting a specific VM by ID."""
    # Login
    login_response = await client.post(
        "/api/v1/auth/login",
        data={
            "username": "testuser",
            "password": "password123",
        },
    )
    token = login_response.json()["access_token"]

    # Get VM by vm_id
    response = await client.get(
        f"/api/v1/vms/{test_vm.vm_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["vm_id"] == test_vm.vm_id
    assert data["name"] == test_vm.name
    assert data["vcpu_count"] == test_vm.vcpu_count
    assert data["memory_mb"] == test_vm.memory_mb


@pytest.mark.asyncio
async def test_get_vm_unauthorized(client: AsyncClient, test_vm: VM) -> None:
    """Test getting a VM without authentication."""
    response = await client.get(f"/api/v1/vms/{test_vm.vm_id}")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_nonexistent_vm(client: AsyncClient, test_user: User) -> None:
    """Test getting a VM that doesn't exist."""
    # Login
    login_response = await client.post(
        "/api/v1/auth/login",
        data={
            "username": "testuser",
            "password": "password123",
        },
    )
    token = login_response.json()["access_token"]

    # Try to get nonexistent VM
    response = await client.get(
        "/api/v1/vms/srv-nonexist",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_vm_other_user_forbidden(
    client: AsyncClient, test_vm: VM, db_session: AsyncSession
) -> None:
    """Test that a user cannot get another user's VM."""
    # Register second user
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "user2@example.com",
            "username": "user2",
            "password": "password123",
        },
    )

    # Login as second user
    login_response = await client.post(
        "/api/v1/auth/login",
        data={
            "username": "user2",
            "password": "password123",
        },
    )
    token = login_response.json()["access_token"]

    # Try to get first user's VM
    response = await client.get(
        f"/api/v1/vms/{test_vm.vm_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404  # Should not reveal existence


@pytest.mark.asyncio
async def test_update_vm(client: AsyncClient, test_user: User, test_vm: VM) -> None:
    """Test updating a VM."""
    # Login
    login_response = await client.post(
        "/api/v1/auth/login",
        data={
            "username": "testuser",
            "password": "password123",
        },
    )
    token = login_response.json()["access_token"]

    # Update VM
    response = await client.patch(
        f"/api/v1/vms/{test_vm.vm_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "updated-vm",
            "description": "Updated description",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "updated-vm"
    assert data["description"] == "Updated description"


@pytest.mark.asyncio
async def test_update_vm_partial(
    client: AsyncClient, test_user: User, test_vm: VM
) -> None:
    """Test partially updating a VM."""
    # Login
    login_response = await client.post(
        "/api/v1/auth/login",
        data={
            "username": "testuser",
            "password": "password123",
        },
    )
    token = login_response.json()["access_token"]

    # Update only name
    response = await client.patch(
        f"/api/v1/vms/{test_vm.vm_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "new-name"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "new-name"
    assert data["description"] == test_vm.description  # Should remain unchanged


@pytest.mark.asyncio
async def test_update_vm_unauthorized(client: AsyncClient, test_vm: VM) -> None:
    """Test updating a VM without authentication."""
    response = await client.patch(
        f"/api/v1/vms/{test_vm.vm_id}",
        json={"name": "hacked"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_update_vm_other_user_forbidden(client: AsyncClient, test_vm: VM) -> None:
    """Test that a user cannot update another user's VM."""
    # Register second user
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "user2@example.com",
            "username": "user2",
            "password": "password123",
        },
    )

    # Login as second user
    login_response = await client.post(
        "/api/v1/auth/login",
        data={
            "username": "user2",
            "password": "password123",
        },
    )
    token = login_response.json()["access_token"]

    # Try to update first user's VM
    response = await client.patch(
        f"/api/v1/vms/{test_vm.vm_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "hacked"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_delete_vm_unauthorized(client: AsyncClient, test_vm: VM) -> None:
    """Test deleting a VM without authentication."""
    response = await client.delete(f"/api/v1/vms/{test_vm.vm_id}")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_delete_nonexistent_vm(client: AsyncClient, test_user: User) -> None:
    """Test deleting a VM that doesn't exist."""
    # Login
    login_response = await client.post(
        "/api/v1/auth/login",
        data={
            "username": "testuser",
            "password": "password123",
        },
    )
    token = login_response.json()["access_token"]

    # Try to delete nonexistent VM
    response = await client.delete(
        "/api/v1/vms/srv-nonexist",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_vm_other_user_forbidden(client: AsyncClient, test_vm: VM) -> None:
    """Test that a user cannot delete another user's VM."""
    # Register second user
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "user2@example.com",
            "username": "user2",
            "password": "password123",
        },
    )

    # Login as second user
    login_response = await client.post(
        "/api/v1/auth/login",
        data={
            "username": "user2",
            "password": "password123",
        },
    )
    token = login_response.json()["access_token"]

    # Try to delete first user's VM
    response = await client.delete(
        f"/api/v1/vms/{test_vm.vm_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_vms_only_shows_own(
    client: AsyncClient, test_user: User, test_vm: VM, db_session: AsyncSession
) -> None:
    """Test that users only see their own VMs in the list."""
    # Register second user
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "user2@example.com",
            "username": "user2",
            "password": "password123",
        },
    )

    # Login as second user and get their ID
    login_response = await client.post(
        "/api/v1/auth/login",
        data={
            "username": "user2",
            "password": "password123",
        },
    )
    token = login_response.json()["access_token"]

    # List VMs for second user (should be empty)
    response = await client.get(
        "/api/v1/vms/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 0
    assert data["total"] == 0
