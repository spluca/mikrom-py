"""IP Allocation model for tracking IP assignments to VMs."""

from typing import Optional, TYPE_CHECKING
from datetime import datetime
from sqlmodel import Field, Relationship, Index
from sqlalchemy import UniqueConstraint

from mikrom.models.base import TimestampModel

if TYPE_CHECKING:
    from mikrom.models.ip_pool import IpPool


class IpAllocation(TimestampModel, table=True):
    """IP allocation tracking for VMs."""

    __tablename__ = "ip_allocations"

    # Primary key
    id: Optional[int] = Field(default=None, primary_key=True)

    # Foreign keys
    pool_id: int = Field(
        foreign_key="ip_pools.id",
        index=True,
        nullable=False,
        description="IP pool this allocation belongs to",
    )
    vm_id: str = Field(
        foreign_key="vms.vm_id",
        index=True,
        nullable=False,
        max_length=50,
        description="VM identifier",
    )

    # Allocation details
    ip_address: str = Field(
        max_length=15,
        index=True,
        nullable=False,
        description="Allocated IP address",
    )

    # Status
    is_active: bool = Field(
        default=True,
        index=True,
        description="Whether this allocation is active",
    )

    # Timestamps
    allocated_at: datetime = Field(
        default_factory=datetime.utcnow,
        nullable=False,
        description="When the IP was allocated",
    )
    released_at: Optional[datetime] = Field(
        default=None,
        description="When the IP was released (NULL if active)",
    )

    # Relationships
    pool: "IpPool" = Relationship(back_populates="allocations")

    # Table constraints and indexes
    __table_args__ = (
        # Ensure unique active allocations per pool/IP
        UniqueConstraint(
            "pool_id",
            "ip_address",
            "is_active",
            name="uq_pool_ip_active",
        ),
        # Ensure unique active allocation per VM
        Index("ix_vm_id_active", "vm_id", "is_active"),
        # Index for querying available IPs
        Index("ix_pool_active", "pool_id", "is_active"),
    )
