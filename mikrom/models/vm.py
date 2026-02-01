"""VM model for Firecracker microVM management."""

from enum import Enum
from typing import Optional, TYPE_CHECKING
from sqlmodel import Field, Relationship

from mikrom.models.base import TimestampModel

if TYPE_CHECKING:
    from mikrom.models.user import User


class VMStatus(str, Enum):
    """VM status enumeration."""

    PENDING = "pending"
    PROVISIONING = "provisioning"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"
    DELETING = "deleting"


class VM(TimestampModel, table=True):
    """Firecracker VM database model."""

    __tablename__ = "vms"

    # Primary key
    id: Optional[int] = Field(default=None, primary_key=True)

    # VM identification
    vm_id: str = Field(
        unique=True,
        index=True,
        nullable=False,
        max_length=50,
        description="Unique VM identifier (e.g., srv-a1b2c3d4)",
    )
    name: str = Field(
        nullable=False,
        max_length=64,
        description="Human-readable VM name",
    )
    description: Optional[str] = Field(
        default=None,
        max_length=500,
        description="VM description",
    )

    # Resources
    vcpu_count: int = Field(
        default=1,
        ge=1,
        le=32,
        description="Number of virtual CPUs",
    )
    memory_mb: int = Field(
        default=512,
        ge=128,
        le=32768,
        description="Memory size in MB",
    )

    # Network
    ip_address: Optional[str] = Field(
        default=None,
        index=True,
        max_length=15,
        description="Assigned IP address",
    )

    # State
    status: VMStatus = Field(
        default=VMStatus.PENDING,
        max_length=20,
        description="VM status: pending, provisioning, running, stopped, error, deleting",
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Error message if status is 'error'",
    )

    # Infrastructure
    host: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Host machine running this VM",
    )
    kernel_path: Optional[str] = Field(
        default=None,
        description="Path to kernel on host",
    )
    rootfs_path: Optional[str] = Field(
        default=None,
        description="Path to rootfs on host",
    )

    # Ownership
    user_id: int = Field(
        foreign_key="users.id",
        nullable=False,
        index=True,
        description="Owner user ID",
    )

    # Relationships
    user: "User" = Relationship(back_populates="vms")
