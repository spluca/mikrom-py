"""IP Pool model for network management."""

from typing import Optional, List, TYPE_CHECKING
from sqlmodel import Field, Relationship

from mikrom.models.base import TimestampModel

if TYPE_CHECKING:
    from mikrom.models.ip_allocation import IpAllocation


class IpPool(TimestampModel, table=True):
    """IP Pool configuration for managing network IP ranges."""

    __tablename__ = "ip_pools"

    # Primary key
    id: Optional[int] = Field(default=None, primary_key=True)

    # Pool identification
    name: str = Field(
        unique=True,
        index=True,
        max_length=64,
        nullable=False,
        description="Unique pool name (e.g., 'default', 'production')",
    )

    # Network configuration
    network: str = Field(
        max_length=15,
        nullable=False,
        description="Network prefix (e.g., '172.16.0')",
    )
    cidr: str = Field(
        max_length=18,
        nullable=False,
        description="Network CIDR (e.g., '172.16.0.0/24')",
    )
    gateway: str = Field(
        max_length=15,
        nullable=False,
        description="Gateway IP address (e.g., '172.16.0.1')",
    )

    # IP range
    start_ip: str = Field(
        max_length=15,
        nullable=False,
        description="First assignable IP (e.g., '172.16.0.2')",
    )
    end_ip: str = Field(
        max_length=15,
        nullable=False,
        description="Last assignable IP (e.g., '172.16.0.254')",
    )

    # Status
    is_active: bool = Field(
        default=True,
        index=True,
        description="Whether this pool is active",
    )

    # Metadata
    description: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Pool description",
    )

    # Relationships
    allocations: List["IpAllocation"] = Relationship(
        back_populates="pool",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
