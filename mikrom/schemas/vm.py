"""VM schemas for request/response validation."""

from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime
import re

from mikrom.models.vm import VMStatus


class VMCreate(BaseModel):
    """Schema for creating a new VM."""

    name: str = Field(
        min_length=1,
        max_length=64,
        description="VM name",
        examples=["my-dev-server", "test-vm-01"],
    )
    description: Optional[str] = Field(
        default=None, max_length=500, description="VM description"
    )
    vcpu_count: int = Field(
        default=1, ge=1, le=32, description="Number of vCPUs (1-32)"
    )
    memory_mb: int = Field(
        default=512, ge=128, le=32768, description="Memory in MB (128-32768)"
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate VM name format."""
        if not re.match(r"^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?$", v):
            raise ValueError(
                "Name must start/end with alphanumeric, can contain hyphens in between"
            )
        return v


class VMUpdate(BaseModel):
    """Schema for updating a VM."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=64)
    description: Optional[str] = Field(default=None, max_length=500)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        """Validate VM name format."""
        if v is not None:
            if not re.match(r"^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?$", v):
                raise ValueError(
                    "Name must start/end with alphanumeric, "
                    "can contain hyphens in between"
                )
        return v


class VMResponse(BaseModel):
    """Schema for VM response."""

    id: int
    vm_id: str
    name: str
    description: Optional[str]
    vcpu_count: int
    memory_mb: int
    ip_address: Optional[str]
    status: VMStatus
    error_message: Optional[str]
    host: Optional[str]
    user_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class VMListResponse(BaseModel):
    """Schema for paginated VM list."""

    items: list[VMResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class VMStatusResponse(BaseModel):
    """Schema for VM status check."""

    vm_id: str
    status: VMStatus
    message: str
