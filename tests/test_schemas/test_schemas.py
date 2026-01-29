"""Tests for configuration and schemas."""

import pytest
from pydantic import ValidationError

from mikrom.schemas.user import UserCreate, UserUpdate, UserResponse, UserLogin
from mikrom.schemas.token import Token, TokenPayload, RefreshTokenRequest
from mikrom.schemas.common import (
    ResponseMessage,
    PaginatedResponse,
    HealthCheckResponse,
)


# Tests for User Schemas


def test_user_create_valid() -> None:
    """Test creating a valid UserCreate schema."""
    user_data = {
        "email": "test@example.com",
        "username": "testuser",
        "password": "password123",
        "full_name": "Test User",
    }
    user = UserCreate(**user_data)

    assert user.email == "test@example.com"
    assert user.username == "testuser"
    assert user.password == "password123"
    assert user.full_name == "Test User"


def test_user_create_without_full_name() -> None:
    """Test creating UserCreate without optional full_name."""
    user_data = {
        "email": "test@example.com",
        "username": "testuser",
        "password": "password123",
    }
    user = UserCreate(**user_data)

    assert user.full_name is None


def test_user_create_invalid_email() -> None:
    """Test creating UserCreate with invalid email."""
    user_data = {
        "email": "invalid-email",
        "username": "testuser",
        "password": "password123",
    }

    with pytest.raises(ValidationError):
        UserCreate(**user_data)


def test_user_create_missing_required_fields() -> None:
    """Test creating UserCreate with missing required fields."""
    # Missing email
    with pytest.raises(ValidationError):
        UserCreate(username="testuser", password="password123")

    # Missing username
    with pytest.raises(ValidationError):
        UserCreate(email="test@example.com", password="password123")

    # Missing password
    with pytest.raises(ValidationError):
        UserCreate(email="test@example.com", username="testuser")


def test_user_update_partial() -> None:
    """Test updating user with partial data."""
    update_data = {"full_name": "New Name"}
    user_update = UserUpdate(**update_data)

    assert user_update.full_name == "New Name"
    assert user_update.email is None
    assert user_update.password is None


def test_user_update_all_fields() -> None:
    """Test updating all user fields."""
    update_data = {
        "email": "newemail@example.com",
        "username": "newusername",
        "full_name": "New Name",
        "password": "newpassword123",
    }
    user_update = UserUpdate(**update_data)

    assert user_update.email == "newemail@example.com"
    assert user_update.username == "newusername"
    assert user_update.full_name == "New Name"
    assert user_update.password == "newpassword123"


def test_user_response_schema() -> None:
    """Test UserResponse schema."""
    user_data = {
        "id": 1,
        "email": "test@example.com",
        "username": "testuser",
        "full_name": "Test User",
        "is_active": True,
        "is_superuser": False,
        "created_at": "2024-01-01T00:00:00",
        "updated_at": "2024-01-01T00:00:00",
    }
    user = UserResponse(**user_data)

    assert user.id == 1
    assert user.email == "test@example.com"
    assert user.username == "testuser"
    assert user.is_active is True
    assert user.is_superuser is False


def test_user_login_with_username() -> None:
    """Test UserLogin schema with username."""
    login_data = {
        "username": "testuser",
        "password": "password123",
    }
    login = UserLogin(**login_data)

    assert login.username == "testuser"
    assert login.password == "password123"


def test_user_login_with_email() -> None:
    """Test UserLogin schema with email as username."""
    login_data = {
        "username": "test@example.com",
        "password": "password123",
    }
    login = UserLogin(**login_data)

    assert login.username == "test@example.com"


# Tests for Token Schemas


def test_token_schema() -> None:
    """Test Token schema."""
    token_data = {
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "token_type": "bearer",
    }
    token = Token(**token_data)

    assert token.access_token == token_data["access_token"]
    assert token.refresh_token == token_data["refresh_token"]
    assert token.token_type == "bearer"


def test_token_payload_schema() -> None:
    """Test TokenPayload schema."""
    payload_data = {
        "sub": "123",
        "exp": 1234567890,
        "type": "access",
    }
    payload = TokenPayload(**payload_data)

    assert payload.sub == "123"
    assert payload.exp == 1234567890
    assert payload.type == "access"


def test_refresh_token_request() -> None:
    """Test RefreshTokenRequest schema."""
    request_data = {
        "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    }
    request = RefreshTokenRequest(**request_data)

    assert request.refresh_token == request_data["refresh_token"]


# Tests for Common Schemas


def test_response_message() -> None:
    """Test ResponseMessage schema."""
    message = ResponseMessage(message="Operation successful")

    assert message.message == "Operation successful"


def test_paginated_response() -> None:
    """Test PaginatedResponse schema."""
    items = [{"id": 1, "name": "Item 1"}, {"id": 2, "name": "Item 2"}]
    paginated = PaginatedResponse(
        items=items,
        total=10,
        page=1,
        page_size=2,
        total_pages=5,
    )

    assert len(paginated.items) == 2
    assert paginated.total == 10
    assert paginated.page == 1
    assert paginated.page_size == 2
    assert paginated.total_pages == 5


def test_health_check_response() -> None:
    """Test HealthCheckResponse schema."""
    health = HealthCheckResponse(
        status="healthy",
        version="1.0.0",
        database="connected",
    )

    assert health.status == "healthy"
    assert health.version == "1.0.0"
    assert health.database == "connected"


def test_health_check_response_degraded() -> None:
    """Test HealthCheckResponse with degraded status."""
    health = HealthCheckResponse(
        status="degraded",
        version="1.0.0",
        database="error: connection failed",
    )

    assert health.status == "degraded"
    assert "error" in health.database
