"""Tests for VM API endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from mikrom.models.vm import VM, VMStatus
from mikrom.models.user import User
from mikrom.core.security import get_password_hash


@pytest.mark.asyncio
async def test_create_vm_unauthorized(client: AsyncClient) -> None:
    """Test creating a VM without authentication."""
    response = await client.post(
        "/api/v1/vms",
        json={
            "name": "test-vm",
            "vcpu_count": 2,
            "memory_mb": 2048,
        },
    )
    assert response.status_code == 401
    response = await client.post(
        "/api/v1/vms",
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
        "/api/v1/vms",
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
        "/api/v1/vms",
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
        "/api/v1/vms",
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
        "/api/v1/vms?page=1&page_size=10",
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
    response = await client.get("/api/v1/vms")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_vms_pagination(
    client: AsyncClient, test_user: User, db_session: AsyncSession
) -> None:
    """Test VM list pagination."""
    assert test_user.id is not None
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
        "/api/v1/vms?page=1&page_size=10",
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
        "/api/v1/vms?page=2&page_size=10",
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
        "/api/v1/vms",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 0
    assert data["total"] == 0


# ============================================================================
# SUPERUSER FUNCTIONALITY TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_superuser_can_see_all_vms(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test that superusers can see all VMs from all users."""
    # Create superuser
    superuser = User(
        email="admin@example.com",
        username="admin",
        hashed_password=get_password_hash("admin123"),
        full_name="Admin User",
        is_superuser=True,
    )
    db_session.add(superuser)
    await db_session.commit()
    await db_session.refresh(superuser)
    assert superuser.id is not None
    assert superuser.id is not None

    # Create regular user 1
    user1 = User(
        email="user1@example.com",
        username="user1",
        hashed_password=get_password_hash("password123"),
        full_name="User One",
    )
    db_session.add(user1)
    await db_session.commit()
    await db_session.refresh(user1)
    assert user1.id is not None
    assert user1.id is not None

    # Create regular user 2
    user2 = User(
        email="user2@example.com",
        username="user2",
        hashed_password=get_password_hash("password123"),
        full_name="User Two",
    )
    db_session.add(user2)
    await db_session.commit()
    await db_session.refresh(user2)
    assert user2.id is not None
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

    # Login as superuser
    login_response = await client.post(
        "/api/v1/auth/login",
        data={
            "username": "admin",
            "password": "admin123",
        },
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    # Superuser should see all 5 VMs
    response = await client.get(
        "/api/v1/vms?page=1&page_size=10",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 5  # All VMs from both users
    assert len(data["items"]) == 5

    # Verify VMs from both users are present
    vm_ids = {vm["vm_id"] for vm in data["items"]}
    assert "srv-user1-0000" in vm_ids
    assert "srv-user2-0000" in vm_ids


@pytest.mark.asyncio
async def test_regular_user_only_sees_own_vms(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test that regular users only see their own VMs, not others'."""
    # Create user 1
    user1 = User(
        email="user1@example.com",
        username="user1",
        hashed_password=get_password_hash("password123"),
        full_name="User One",
        is_superuser=False,
    )
    db_session.add(user1)
    await db_session.commit()
    await db_session.refresh(user1)
    assert user1.id is not None
    assert user1.id is not None

    # Create user 2
    user2 = User(
        email="user2@example.com",
        username="user2",
        hashed_password=get_password_hash("password123"),
        full_name="User Two",
        is_superuser=False,
    )
    db_session.add(user2)
    await db_session.commit()
    await db_session.refresh(user2)
    assert user2.id is not None
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

    # Login as user1
    login_response = await client.post(
        "/api/v1/auth/login",
        data={
            "username": "user1",
            "password": "password123",
        },
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    # User1 should only see their own 3 VMs
    response = await client.get(
        "/api/v1/vms?page=1&page_size=10",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3  # Only user1's VMs
    assert len(data["items"]) == 3

    # Verify only user1's VMs are returned
    vm_ids = {vm["vm_id"] for vm in data["items"]}
    assert "srv-user1-0000" in vm_ids
    assert "srv-user1-0001" in vm_ids
    assert "srv-user1-0002" in vm_ids
    assert "srv-user2-0000" not in vm_ids  # User2's VMs not visible


@pytest.mark.asyncio
async def test_superuser_can_get_other_users_vm(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test that superuser can get details of any user's VM."""
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

    # Login as superuser
    login_response = await client.post(
        "/api/v1/auth/login",
        data={
            "username": "admin",
            "password": "admin123",
        },
    )
    token = login_response.json()["access_token"]

    # Superuser should be able to get the user's VM
    response = await client.get(
        f"/api/v1/vms/{vm.vm_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["vm_id"] == "srv-uservm"
    assert data["name"] == "user-vm"


@pytest.mark.asyncio
async def test_superuser_can_update_other_users_vm(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test that superuser can update any user's VM."""
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

    # Login as superuser
    login_response = await client.post(
        "/api/v1/auth/login",
        data={
            "username": "admin",
            "password": "admin123",
        },
    )
    token = login_response.json()["access_token"]

    # Superuser should be able to update the user's VM
    response = await client.patch(
        f"/api/v1/vms/{vm.vm_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "updated-by-admin",
            "description": "Updated by superuser",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "updated-by-admin"
    assert data["description"] == "Updated by superuser"


@pytest.mark.asyncio
async def test_superuser_can_delete_other_users_vm(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test that superuser can delete any user's VM."""
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

    # Login as superuser
    login_response = await client.post(
        "/api/v1/auth/login",
        data={
            "username": "admin",
            "password": "admin123",
        },
    )
    token = login_response.json()["access_token"]

    # Superuser should be able to delete the user's VM
    response = await client.delete(
        f"/api/v1/vms/{vm.vm_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 202  # Accepted (async delete with Celery)


@pytest.mark.asyncio
async def test_superuser_pagination_shows_all_users_vms(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Test that pagination works correctly for superusers seeing all VMs."""
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

    # Create multiple users with VMs
    for user_idx in range(3):
        user = User(
            email=f"user{user_idx}@example.com",
            username=f"user{user_idx}",
            hashed_password=get_password_hash("password123"),
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        assert user.id is not None

        # Create 5 VMs per user = 15 VMs total
        for vm_idx in range(5):
            vm = VM(
                vm_id=f"srv-user{user_idx}-vm{vm_idx}",
                name=f"user{user_idx}-vm-{vm_idx}",
                vcpu_count=2,
                memory_mb=2048,
                status=VMStatus.RUNNING,
                user_id=user.id,
            )
            db_session.add(vm)

    await db_session.commit()

    # Login as superuser
    login_response = await client.post(
        "/api/v1/auth/login",
        data={
            "username": "admin",
            "password": "admin123",
        },
    )
    token = login_response.json()["access_token"]

    # Get first page (10 VMs)
    response = await client.get(
        "/api/v1/vms?page=1&page_size=10",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 15  # All VMs from all users
    assert len(data["items"]) == 10  # Page size limit
    assert data["total_pages"] == 2

    # Get second page (5 VMs)
    response = await client.get(
        "/api/v1/vms?page=2&page_size=10",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 5  # Remaining VMs
    assert data["page"] == 2


# ============================================================================
# VM OPERATIONS TESTS (stop/start/restart)
# ============================================================================


@pytest.mark.asyncio
async def test_stop_vm(
    client: AsyncClient, test_user: User, db_session: AsyncSession
) -> None:
    """Test stopping a running VM."""
    assert test_user.id is not None

    # Create a running VM
    vm = VM(
        vm_id="srv-running",
        name="running-vm",
        vcpu_count=2,
        memory_mb=2048,
        status=VMStatus.RUNNING,
        host="hypervisor1.example.com",
        user_id=test_user.id,
    )
    db_session.add(vm)
    await db_session.commit()

    # Login
    login_response = await client.post(
        "/api/v1/auth/login",
        data={"username": "testuser", "password": "password123"},
    )
    token = login_response.json()["access_token"]

    # Stop VM
    response = await client.post(
        f"/api/v1/vms/{vm.vm_id}/stop",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 202  # Accepted
    data = response.json()
    assert data["vm_id"] == "srv-running"
    assert data["status"] == "stopping"


@pytest.mark.asyncio
async def test_stop_vm_not_running(
    client: AsyncClient, test_user: User, db_session: AsyncSession
) -> None:
    """Test stopping a VM that's not running."""
    assert test_user.id is not None

    # Create a stopped VM
    vm = VM(
        vm_id="srv-stopped",
        name="stopped-vm",
        vcpu_count=2,
        memory_mb=2048,
        status=VMStatus.STOPPED,
        user_id=test_user.id,
    )
    db_session.add(vm)
    await db_session.commit()

    # Login
    login_response = await client.post(
        "/api/v1/auth/login",
        data={"username": "testuser", "password": "password123"},
    )
    token = login_response.json()["access_token"]

    # Try to stop already stopped VM
    response = await client.post(
        f"/api/v1/vms/{vm.vm_id}/stop",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409  # Conflict


@pytest.mark.asyncio
async def test_start_vm(
    client: AsyncClient, test_user: User, db_session: AsyncSession
) -> None:
    """Test starting a stopped VM."""
    assert test_user.id is not None

    # Create a stopped VM
    vm = VM(
        vm_id="srv-tosstart",
        name="start-vm",
        vcpu_count=2,
        memory_mb=2048,
        status=VMStatus.STOPPED,
        host="hypervisor1.example.com",
        user_id=test_user.id,
    )
    db_session.add(vm)
    await db_session.commit()

    # Login
    login_response = await client.post(
        "/api/v1/auth/login",
        data={"username": "testuser", "password": "password123"},
    )
    token = login_response.json()["access_token"]

    # Start VM
    response = await client.post(
        f"/api/v1/vms/{vm.vm_id}/start",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 202  # Accepted
    data = response.json()
    assert data["vm_id"] == "srv-tosstart"
    assert data["status"] == "starting"


@pytest.mark.asyncio
async def test_start_vm_already_running(
    client: AsyncClient, test_user: User, db_session: AsyncSession
) -> None:
    """Test starting a VM that's already running."""
    assert test_user.id is not None

    # Create a running VM
    vm = VM(
        vm_id="srv-alreadyrunning",
        name="running-vm",
        vcpu_count=2,
        memory_mb=2048,
        status=VMStatus.RUNNING,
        user_id=test_user.id,
    )
    db_session.add(vm)
    await db_session.commit()

    # Login
    login_response = await client.post(
        "/api/v1/auth/login",
        data={"username": "testuser", "password": "password123"},
    )
    token = login_response.json()["access_token"]

    # Try to start already running VM
    response = await client.post(
        f"/api/v1/vms/{vm.vm_id}/start",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409  # Conflict


@pytest.mark.asyncio
async def test_restart_vm(
    client: AsyncClient, test_user: User, db_session: AsyncSession
) -> None:
    """Test restarting a running VM."""
    assert test_user.id is not None

    # Create a running VM
    vm = VM(
        vm_id="srv-torestart",
        name="restart-vm",
        vcpu_count=2,
        memory_mb=2048,
        status=VMStatus.RUNNING,
        host="hypervisor1.example.com",
        user_id=test_user.id,
    )
    db_session.add(vm)
    await db_session.commit()

    # Login
    login_response = await client.post(
        "/api/v1/auth/login",
        data={"username": "testuser", "password": "password123"},
    )
    token = login_response.json()["access_token"]

    # Restart VM
    response = await client.post(
        f"/api/v1/vms/{vm.vm_id}/restart",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 202  # Accepted
    data = response.json()
    assert data["vm_id"] == "srv-torestart"
    assert data["status"] == "restarting"


@pytest.mark.asyncio
async def test_restart_vm_not_running(
    client: AsyncClient, test_user: User, db_session: AsyncSession
) -> None:
    """Test restarting a VM that's not running."""
    assert test_user.id is not None

    # Create a stopped VM
    vm = VM(
        vm_id="srv-notrunning",
        name="notrunning-vm",
        vcpu_count=2,
        memory_mb=2048,
        status=VMStatus.STOPPED,
        user_id=test_user.id,
    )
    db_session.add(vm)
    await db_session.commit()

    # Login
    login_response = await client.post(
        "/api/v1/auth/login",
        data={"username": "testuser", "password": "password123"},
    )
    token = login_response.json()["access_token"]

    # Try to restart stopped VM
    response = await client.post(
        f"/api/v1/vms/{vm.vm_id}/restart",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409  # Conflict


@pytest.mark.asyncio
async def test_delete_vm_with_status_check(
    client: AsyncClient, test_user: User, db_session: AsyncSession
) -> None:
    """Test deleting a VM and verify status transitions."""
    assert test_user.id is not None

    # Create a VM
    vm = VM(
        vm_id="srv-todelete",
        name="delete-vm",
        vcpu_count=2,
        memory_mb=2048,
        status=VMStatus.RUNNING,
        user_id=test_user.id,
    )
    db_session.add(vm)
    await db_session.commit()

    # Login
    login_response = await client.post(
        "/api/v1/auth/login",
        data={"username": "testuser", "password": "password123"},
    )
    token = login_response.json()["access_token"]

    # Delete VM
    response = await client.delete(
        f"/api/v1/vms/{vm.vm_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 202  # Accepted
    data = response.json()
    assert data["vm_id"] == "srv-todelete"
    assert data["status"] == "deleting"


@pytest.mark.asyncio
async def test_delete_vm_already_deleting(
    client: AsyncClient, test_user: User, db_session: AsyncSession
) -> None:
    """Test deleting a VM that's already being deleted."""
    assert test_user.id is not None

    # Create a VM with deleting status
    vm = VM(
        vm_id="srv-alreadydeleting",
        name="deleting-vm",
        vcpu_count=2,
        memory_mb=2048,
        status=VMStatus.DELETING,
        user_id=test_user.id,
    )
    db_session.add(vm)
    await db_session.commit()

    # Login
    login_response = await client.post(
        "/api/v1/auth/login",
        data={"username": "testuser", "password": "password123"},
    )
    token = login_response.json()["access_token"]

    # Try to delete already deleting VM
    response = await client.delete(
        f"/api/v1/vms/{vm.vm_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 409  # Conflict


@pytest.mark.asyncio
async def test_vm_operation_on_nonexistent_vm(
    client: AsyncClient, test_user: User
) -> None:
    """Test VM operations on non-existent VM."""
    # Login
    login_response = await client.post(
        "/api/v1/auth/login",
        data={"username": "testuser", "password": "password123"},
    )
    token = login_response.json()["access_token"]

    # Try to stop non-existent VM
    response = await client.post(
        "/api/v1/vms/srv-nonexistent/stop",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404

    # Try to start non-existent VM
    response = await client.post(
        "/api/v1/vms/srv-nonexistent/start",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404

    # Try to restart non-existent VM
    response = await client.post(
        "/api/v1/vms/srv-nonexistent/restart",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404
