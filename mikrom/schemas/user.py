"""User schemas for request/response validation."""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class UserBase(BaseModel):
    """Base user schema with common fields."""

    email: EmailStr = Field(
        ..., description="User email address", examples=["user@example.com"]
    )
    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        pattern="^[a-zA-Z0-9_-]+$",
        description="Unique username (alphanumeric, underscore, hyphen)",
        examples=["john_doe"],
    )
    full_name: Optional[str] = Field(
        default=None,
        max_length=255,
        description="User's full name",
        examples=["John Doe"],
    )


class UserCreate(UserBase):
    """Schema for creating a new user."""

    password: str = Field(
        ...,
        min_length=8,
        max_length=100,
        description="User password (minimum 8 characters)",
        examples=["SecureP@ssw0rd"],
    )


class UserUpdate(BaseModel):
    """Schema for updating user information."""

    email: Optional[EmailStr] = Field(default=None, description="User email address")
    username: Optional[str] = Field(
        default=None,
        min_length=3,
        max_length=50,
        pattern="^[a-zA-Z0-9_-]+$",
        description="Unique username",
    )
    full_name: Optional[str] = Field(
        default=None, max_length=255, description="User's full name"
    )
    password: Optional[str] = Field(
        default=None,
        min_length=8,
        max_length=100,
        description="New password",
    )
    is_active: Optional[bool] = Field(default=None, description="Account active status")


class UserResponse(UserBase):
    """Schema for user response (public information)."""

    id: int = Field(..., description="User ID")
    is_active: bool = Field(..., description="Whether the account is active")
    is_superuser: bool = Field(..., description="Whether the user is a superuser")
    created_at: datetime = Field(..., description="Account creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = ConfigDict(from_attributes=True)


class UserLogin(BaseModel):
    """Schema for user login."""

    username: str = Field(..., description="Username or email", examples=["john_doe"])
    password: str = Field(..., description="User password", examples=["SecureP@ssw0rd"])
