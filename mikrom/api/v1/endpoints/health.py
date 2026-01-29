"""Health check endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from mikrom import __version__
from mikrom.api.deps import get_db
from mikrom.schemas import HealthCheckResponse

router = APIRouter()


@router.get("", response_model=HealthCheckResponse)
async def health_check(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HealthCheckResponse:
    """
    Health check endpoint.

    Returns the status of the API and database connection.
    Useful for monitoring and orchestration systems.
    """
    # Check database connection
    try:
        await db.execute(text("SELECT 1"))
        database_status = "connected"
    except Exception as e:
        database_status = f"error: {str(e)}"

    return HealthCheckResponse(
        status="healthy" if database_status == "connected" else "degraded",
        version=__version__,
        database=database_status,
    )
