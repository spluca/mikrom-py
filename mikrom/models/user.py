"""User model for authentication and user management."""

from typing import Optional, List, TYPE_CHECKING
from sqlmodel import Field, Relationship

from mikrom.models.base import TimestampModel

if TYPE_CHECKING:
    from mikrom.models.vm import VM


class User(TimestampModel, table=True):
    """User database model."""

    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(
        unique=True,
        index=True,
        nullable=False,
        max_length=255,
        description="User email address",
    )
    username: str = Field(
        unique=True,
        index=True,
        nullable=False,
        max_length=50,
        description="Unique username",
    )
    hashed_password: str = Field(
        nullable=False,
        description="Hashed password using bcrypt",
    )
    full_name: Optional[str] = Field(
        default=None,
        max_length=255,
        description="User's full name",
    )
    is_active: bool = Field(
        default=True,
        nullable=False,
        description="Whether the user account is active",
    )
    is_superuser: bool = Field(
        default=False,
        nullable=False,
        description="Whether the user has superuser privileges",
    )

    # Relationships
    vms: List["VM"] = Relationship(back_populates="user")
