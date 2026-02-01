"""Client for IP Pool API."""

import httpx
from typing import Optional
from mikrom.config import settings
from mikrom.utils.logger import get_logger

logger = get_logger(__name__)


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
        try:
            logger.info(f"Allocating IP for VM {vm_id}")

            response = await self.client.post(
                "/api/v1/ip/allocate", json={"vm_id": vm_id, "hostname": hostname}
            )
            response.raise_for_status()

            data = response.json()
            logger.info(f"Allocated IP {data['ip']} for VM {vm_id}")
            return data

        except httpx.HTTPStatusError as e:
            error_msg = f"Failed to allocate IP: {e.response.text}"
            logger.error(error_msg)
            raise IPPoolError(error_msg) from e
        except httpx.RequestError as e:
            error_msg = f"IP Pool API request failed: {str(e)}"
            logger.error(error_msg)
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
        try:
            logger.info(f"Releasing IP for VM {vm_id}")

            response = await self.client.delete(f"/api/v1/ip/release/{vm_id}")
            response.raise_for_status()

            data = response.json()
            logger.info(f"Released IP for VM {vm_id}")
            return data

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"No IP allocation found for VM {vm_id}")
                return {"message": "No allocation found", "vm_id": vm_id}
            error_msg = f"Failed to release IP: {e.response.text}"
            logger.error(error_msg)
            raise IPPoolError(error_msg) from e
        except httpx.RequestError as e:
            error_msg = f"IP Pool API request failed: {str(e)}"
            logger.error(error_msg)
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
        try:
            response = await self.client.get(f"/api/v1/ip/{vm_id}")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise IPPoolError(f"Failed to get IP info: {e.response.text}") from e

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
