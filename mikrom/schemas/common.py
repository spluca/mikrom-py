"""Common schemas used across the application."""

from typing import Generic, TypeVar, List
from pydantic import BaseModel, Field


T = TypeVar("T")


class ResponseMessage(BaseModel):
    """Generic response message schema."""

    message: str = Field(..., description="Response message")


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response schema."""

    items: List[T] = Field(..., description="List of items")
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number", ge=1)
    page_size: int = Field(..., description="Number of items per page", ge=1)
    total_pages: int = Field(..., description="Total number of pages")


class HealthCheckResponse(BaseModel):
    """Health check response schema."""

    status: str = Field(..., description="Service status", examples=["healthy"])
    version: str = Field(..., description="API version", examples=["1.0.0"])
    database: str = Field(..., description="Database status", examples=["connected"])
