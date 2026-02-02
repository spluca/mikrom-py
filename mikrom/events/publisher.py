"""Event publisher for Redis Pub/Sub."""

import json
import time
from typing import Optional

from redis.asyncio import Redis
from redis import Redis as SyncRedis

from mikrom.config import settings
from mikrom.utils.logger import get_logger

logger = get_logger(__name__)


class EventPublisher:
    """Publish events to Redis channels for real-time updates."""

    CHANNELS = {
        "VM_EVENTS": "vm.events",
        "SYSTEM_EVENTS": "system.events",
    }

    @classmethod
    async def publish_vm_event(
        cls,
        vm_id: str,
        event_type: str,
        data: dict,
        redis: Optional[Redis] = None,
    ):
        """
        Publish VM event (async version).

        Args:
            vm_id: VM identifier
            event_type: Event type (vm.status_change, vm.created, vm.deleted, etc.)
            data: Event data
            redis: Optional Redis connection (will create new if not provided)
        """
        close_redis = False
        if redis is None:
            redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
            close_redis = True

        try:
            message = {
                "event": event_type,
                "vm_id": vm_id,
                "timestamp": time.time(),
                **data,
            }

            channel = cls.CHANNELS["VM_EVENTS"]
            subscribers = await redis.publish(channel, json.dumps(message))

            logger.debug(
                f"Published event to {channel}",
                extra={
                    "vm_id": vm_id,
                    "event_type": event_type,
                    "subscribers": subscribers,
                },
            )

        except Exception as e:
            logger.error(
                "Failed to publish event",
                extra={"error": str(e), "vm_id": vm_id, "event_type": event_type},
            )

        finally:
            if close_redis:
                await redis.close()

    @classmethod
    def publish_vm_event_sync(cls, vm_id: str, event_type: str, data: dict):
        """
        Synchronous version for Celery workers.

        Args:
            vm_id: VM identifier
            event_type: Event type
            data: Event data
        """
        redis = None
        try:
            redis = SyncRedis.from_url(settings.REDIS_URL, decode_responses=True)

            message = {
                "event": event_type,
                "vm_id": vm_id,
                "timestamp": time.time(),
                **data,
            }

            channel = cls.CHANNELS["VM_EVENTS"]
            subscribers = redis.publish(channel, json.dumps(message))

            logger.debug(
                f"Published event to {channel}",
                extra={
                    "vm_id": vm_id,
                    "event_type": event_type,
                    "subscribers": subscribers,
                },
            )

        except Exception as e:
            logger.error(
                "Failed to publish event",
                extra={"error": str(e), "vm_id": vm_id, "event_type": event_type},
            )

        finally:
            if redis:
                redis.close()

    @classmethod
    async def publish_system_event(
        cls, event_type: str, data: dict, redis: Optional[Redis] = None
    ):
        """
        Publish system event (async version).

        Args:
            event_type: Event type
            data: Event data
            redis: Optional Redis connection
        """
        close_redis = False
        if redis is None:
            redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
            close_redis = True

        try:
            message = {
                "event": event_type,
                "timestamp": time.time(),
                **data,
            }

            channel = cls.CHANNELS["SYSTEM_EVENTS"]
            subscribers = await redis.publish(channel, json.dumps(message))

            logger.debug(
                f"Published system event to {channel}",
                extra={"event_type": event_type, "subscribers": subscribers},
            )

        except Exception as e:
            logger.error(
                "Failed to publish system event",
                extra={"error": str(e), "event_type": event_type},
            )

        finally:
            if close_redis:
                await redis.close()
