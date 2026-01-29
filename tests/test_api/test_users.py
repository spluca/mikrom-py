"""Tests for user endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_users(client: AsyncClient) -> None:
    """Test listing users with pagination."""
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

    # List users
    response = await client.get(
        "/api/v1/users?skip=0&limit=10",
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
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_list_users_unauthorized(client: AsyncClient) -> None:
    """Test listing users without authentication."""
    response = await client.get("/api/v1/users")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_user_by_id(client: AsyncClient) -> None:
    """Test getting a specific user by ID."""
    # Register and login
    register_response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "test@example.com",
            "username": "testuser",
            "password": "testpassword123",
            "full_name": "Test User",
        },
    )
    user_id = register_response.json()["id"]

    login_response = await client.post(
        "/api/v1/auth/login",
        data={
            "username": "testuser",
            "password": "testpassword123",
        },
    )
    token = login_response.json()["access_token"]

    # Get user by ID
    response = await client.get(
        f"/api/v1/users/{user_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == user_id
    assert data["email"] == "test@example.com"
    assert data["username"] == "testuser"
    assert data["full_name"] == "Test User"


@pytest.mark.asyncio
async def test_get_nonexistent_user(client: AsyncClient) -> None:
    """Test getting a user that doesn't exist."""
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

    # Try to get nonexistent user
    response = await client.get(
        "/api/v1/users/99999",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_user(client: AsyncClient) -> None:
    """Test updating user information."""
    # Register and login
    register_response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "test@example.com",
            "username": "testuser",
            "password": "testpassword123",
            "full_name": "Test User",
        },
    )
    user_id = register_response.json()["id"]

    login_response = await client.post(
        "/api/v1/auth/login",
        data={
            "username": "testuser",
            "password": "testpassword123",
        },
    )
    token = login_response.json()["access_token"]

    # Update user
    response = await client.put(
        f"/api/v1/users/{user_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "full_name": "Updated User",
            "email": "updated@example.com",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["full_name"] == "Updated User"
    assert data["email"] == "updated@example.com"


@pytest.mark.asyncio
async def test_update_other_user_forbidden(client: AsyncClient) -> None:
    """Test that a user cannot update another user's information."""
    # Register first user
    first_user_response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "user1@example.com",
            "username": "user1",
            "password": "password123",
        },
    )
    first_user_id = first_user_response.json()["id"]

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

    # Try to update first user
    response = await client.put(
        f"/api/v1/users/{first_user_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "full_name": "Hacked User",
        },
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_delete_user_as_superuser(client: AsyncClient) -> None:
    """Test deleting a user as a superuser."""
    # This test would require creating a superuser fixture
    # For now, we'll skip it or create a superuser in the test
    pass


@pytest.mark.asyncio
async def test_update_user_password(client: AsyncClient) -> None:
    """Test updating user password."""
    # Register and login
    register_response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "test@example.com",
            "username": "testuser",
            "password": "oldpassword123",
        },
    )
    user_id = register_response.json()["id"]

    login_response = await client.post(
        "/api/v1/auth/login",
        data={
            "username": "testuser",
            "password": "oldpassword123",
        },
    )
    token = login_response.json()["access_token"]

    # Update password
    response = await client.put(
        f"/api/v1/users/{user_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "password": "newpassword123",
        },
    )
    assert response.status_code == 200

    # Try to login with old password (should fail)
    old_login_response = await client.post(
        "/api/v1/auth/login",
        data={
            "username": "testuser",
            "password": "oldpassword123",
        },
    )
    assert old_login_response.status_code == 401

    # Try to login with new password (should succeed)
    new_login_response = await client.post(
        "/api/v1/auth/login",
        data={
            "username": "testuser",
            "password": "newpassword123",
        },
    )
    assert new_login_response.status_code == 200


@pytest.mark.asyncio
async def test_pagination_parameters(client: AsyncClient) -> None:
    """Test different pagination parameters."""
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

    # Test with different page and page_size values
    response = await client.get(
        "/api/v1/users?page=1&page_size=5",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["page_size"] == 5

    # Test with page > 1
    response = await client.get(
        "/api/v1/users?page=2&page_size=10",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
