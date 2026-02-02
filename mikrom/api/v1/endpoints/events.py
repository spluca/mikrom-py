"""Real-time event streaming endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from redis.asyncio import Redis

from mikrom.api.deps import get_current_user_from_token, get_redis
from mikrom.models import User
from mikrom.events.sse import sse_generator
from mikrom.events.publisher import EventPublisher
from mikrom.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/vms")
async def stream_vm_events(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user_from_token)],
    redis: Annotated[Redis, Depends(get_redis)],
):
    """
    Stream VM events via Server-Sent Events (SSE).

    This endpoint provides real-time updates for VM status changes.

    Authentication:
        Token must be provided as query parameter: ?token=your_access_token

    Events sent:
        - connection: Initial connection established
        - heartbeat: Periodic keepalive messages (every 30s)
        - vm.status_change: When VM status changes
        - vm.created: When new VM is created
        - vm.deleted: When VM is deleted

    Event format:
        event: vm.status_change
        data: {"event": "vm.status_change", "vm_id": "...", "status": "running", ...}

    Note:
        Client should filter events by vm.user_id to only show their VMs
        (unless the user is a superuser).
    """
    logger.info(
        "Client connected to VM events stream",
        extra={"user_id": current_user.id, "username": current_user.username},
    )

    return StreamingResponse(
        sse_generator(
            request=request,
            redis=redis,
            channel=EventPublisher.CHANNELS["VM_EVENTS"],
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
