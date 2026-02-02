"""Server-Sent Events utilities."""

import asyncio
import json
from typing import AsyncGenerator, Optional

from fastapi import Request
from redis.asyncio import Redis

from mikrom.utils.logger import get_logger

logger = get_logger(__name__)


class SSEMessage:
    """SSE message format following the SSE specification."""

    def __init__(
        self,
        data: dict,
        event: Optional[str] = None,
        id: Optional[str] = None,
        retry: Optional[int] = None,
    ):
        """
        Initialize SSE message.

        Args:
            data: Message data (will be JSON encoded)
            event: Event type (optional)
            id: Message ID (optional)
            retry: Reconnection time in milliseconds (optional)
        """
        self.data = data
        self.event = event
        self.id = id
        self.retry = retry

    def encode(self) -> str:
        """
        Encode message in SSE format.

        Format:
            event: event_name\n
            id: message_id\n
            retry: 3000\n
            data: {"key": "value"}\n\n
        """
        message = ""

        if self.event:
            message += f"event: {self.event}\n"

        if self.id:
            message += f"id: {self.id}\n"

        if self.retry:
            message += f"retry: {self.retry}\n"

        message += f"data: {json.dumps(self.data)}\n\n"
        return message


async def sse_generator(
    request: Request,
    redis: Redis,
    channel: str,
    heartbeat_interval: int = 30,
) -> AsyncGenerator[str, None]:
    """
    Generate SSE stream from Redis Pub/Sub.

    Args:
        request: FastAPI request (to check if client disconnected)
        redis: Redis connection
        channel: Redis channel to subscribe
        heartbeat_interval: Seconds between heartbeat messages

    Yields:
        SSE formatted messages
    """
    pubsub = redis.pubsub()

    try:
        await pubsub.subscribe(channel)
        logger.info(f"Client subscribed to channel: {channel}")

        # Send initial connection message
        yield SSEMessage(
            data={"type": "connected", "channel": channel},
            event="connection",
            retry=3000,  # Retry after 3 seconds if disconnected
        ).encode()

        # Heartbeat tracking
        last_heartbeat = asyncio.get_event_loop().time()

        while True:
            # Check if client disconnected
            if await request.is_disconnected():
                logger.info("Client disconnected from SSE stream")
                break

            # Send heartbeat
            current_time = asyncio.get_event_loop().time()
            if current_time - last_heartbeat > heartbeat_interval:
                yield SSEMessage(
                    data={"type": "heartbeat", "timestamp": current_time},
                    event="heartbeat",
                ).encode()
                last_heartbeat = current_time

            # Get message from Redis with timeout
            try:
                message = await asyncio.wait_for(
                    pubsub.get_message(ignore_subscribe_messages=True), timeout=1.0
                )

                if message and message["type"] == "message":
                    # Parse and forward message
                    try:
                        data = json.loads(message["data"])
                        event_type = data.get("event", "message")

                        yield SSEMessage(data=data, event=event_type).encode()

                        logger.debug(
                            "Forwarded message to client",
                            extra={"event": event_type, "channel": channel},
                        )
                    except json.JSONDecodeError as e:
                        logger.error(
                            "Failed to parse Redis message",
                            extra={"error": str(e), "message": message},
                        )

            except asyncio.TimeoutError:
                # No message, continue loop
                continue

    except Exception as e:
        logger.error("Error in SSE generator", extra={"error": str(e)})
        # Send error message to client
        yield SSEMessage(
            data={"type": "error", "message": "Internal server error"},
            event="error",
        ).encode()

    finally:
        try:
            await pubsub.unsubscribe(channel)
            await pubsub.close()
            logger.info(f"Client unsubscribed from channel: {channel}")
        except Exception as e:
            logger.error("Error closing pubsub", extra={"error": str(e)})
