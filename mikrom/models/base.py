"""Base model with common fields for all database models."""

from datetime import datetime

from sqlmodel import Field, SQLModel


class TimestampModel(SQLModel):
    """Base model with created_at and updated_at timestamps."""

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        nullable=False,
        description="Timestamp when the record was created",
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        nullable=False,
        sa_column_kwargs={"onupdate": datetime.utcnow},
        description="Timestamp when the record was last updated",
    )
