"""Client for IP Pool API with enhanced logging and tracing."""

import httpx
from typing import Optional
from mikrom.config import settings
from mikrom.utils.logger import get_logger, log_timer
from mikrom.utils.telemetry import get_tracer, add_span_attributes, add_span_event

logger = get_logger(__name__)
tracer = get_tracer()


class IPPoolError(Exception):
    """IP Pool API error."""

    pass


class IPPoolClient:
    """Async client for IP Pool API."""

    def __init__(self, base_url: Optional[str] = None):
        """Initialize client."""
        self.base_url = base_url or settings.IPPOOL_API_URL
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=30.0)

    async def allocate_ip(self, vm_id: str, hostname: Optional[str] = None) -> dict:
        """
        Allocate IP address for a VM.

        Args:
            vm_id: Unique VM identifier
            hostname: Optional hostname for the VM

        Returns:
            dict with 'ip', 'vm_id', 'hostname', 'allocated_at'

        Raises:
            IPPoolError: If allocation fails
        """
        with tracer.start_as_current_span("ippool.allocate") as span:
            add_span_attributes(
                **{
                    "ippool.operation": "allocate",
                    "ippool.vm_id": vm_id,
                    "ippool.hostname": hostname or "none",
                }
            )

            logger.info(
                "Allocating IP address", extra={"vm_id": vm_id, "hostname": hostname}
            )

            try:
                with log_timer("ippool_allocate", logger):
                    response = await self.client.post(
                        "/api/v1/ip/allocate",
                        json={"vm_id": vm_id, "hostname": hostname},
                    )
                    response.raise_for_status()

                data = response.json()
                ip_address = data.get("ip")

                add_span_attributes(**{"ippool.ip": ip_address})
                add_span_event("ip_allocated", {"ip": ip_address})

                logger.info(
                    "IP allocated successfully",
                    extra={
                        "vm_id": vm_id,
                        "ip": ip_address,
                        "hostname": data.get("hostname"),
                    },
                )

                return data

            except httpx.HTTPStatusError as e:
                error_msg = f"Failed to allocate IP: {e.response.text}"
                logger.error(
                    "IP allocation failed",
                    extra={
                        "vm_id": vm_id,
                        "status_code": e.response.status_code,
                        "error": e.response.text,
                        "error_type": "HTTPStatusError",
                    },
                )
                span.record_exception(e)
                raise IPPoolError(error_msg) from e

            except httpx.RequestError as e:
                error_msg = f"IP Pool API request failed: {str(e)}"
                logger.error(
                    "IP Pool API request failed",
                    extra={
                        "vm_id": vm_id,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                )
                span.record_exception(e)
                raise IPPoolError(error_msg) from e

    async def release_ip(self, vm_id: str) -> dict:
        """
        Release IP address for a VM.

        Args:
            vm_id: Unique VM identifier

        Returns:
            dict with 'message', 'vm_id', 'ip'

        Raises:
            IPPoolError: If release fails
        """
        with tracer.start_as_current_span("ippool.release") as span:
            add_span_attributes(
                **{
                    "ippool.operation": "release",
                    "ippool.vm_id": vm_id,
                }
            )

            logger.info("Releasing IP address", extra={"vm_id": vm_id})

            try:
                with log_timer("ippool_release", logger):
                    response = await self.client.delete(f"/api/v1/ip/release/{vm_id}")
                    response.raise_for_status()

                data = response.json()
                released_ip = data.get("ip")

                add_span_attributes(**{"ippool.ip": released_ip})
                add_span_event("ip_released", {"ip": released_ip})

                logger.info(
                    "IP released successfully",
                    extra={"vm_id": vm_id, "ip": released_ip},
                )

                return data

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    logger.warning(
                        "No IP allocation found for VM",
                        extra={"vm_id": vm_id, "status_code": 404},
                    )
                    return {"message": "No allocation found", "vm_id": vm_id}

                error_msg = f"Failed to release IP: {e.response.text}"
                logger.error(
                    "IP release failed",
                    extra={
                        "vm_id": vm_id,
                        "status_code": e.response.status_code,
                        "error": e.response.text,
                        "error_type": "HTTPStatusError",
                    },
                )
                span.record_exception(e)
                raise IPPoolError(error_msg) from e

            except httpx.RequestError as e:
                error_msg = f"IP Pool API request failed: {str(e)}"
                logger.error(
                    "IP Pool API request failed",
                    extra={
                        "vm_id": vm_id,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                )
                span.record_exception(e)
                raise IPPoolError(error_msg) from e

    async def get_ip_info(self, vm_id: str) -> dict | None:
        """
        Get IP allocation info for a VM.

        Args:
            vm_id: Unique VM identifier

        Returns:
            dict with allocation info or None if not found

        Raises:
            IPPoolError: If request fails
        """
        with tracer.start_as_current_span("ippool.get_info") as span:
            add_span_attributes(
                **{
                    "ippool.operation": "get_info",
                    "ippool.vm_id": vm_id,
                }
            )

            try:
                response = await self.client.get(f"/api/v1/ip/{vm_id}")
                response.raise_for_status()

                data = response.json()
                logger.info(
                    "IP info retrieved", extra={"vm_id": vm_id, "ip": data.get("ip")}
                )

                return data

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    logger.info("No IP allocation found", extra={"vm_id": vm_id})
                    return None

                logger.error(
                    "Failed to get IP info",
                    extra={
                        "vm_id": vm_id,
                        "status_code": e.response.status_code,
                        "error": e.response.text,
                    },
                )
                span.record_exception(e)
                raise IPPoolError(f"Failed to get IP info: {e.response.text}") from e

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
