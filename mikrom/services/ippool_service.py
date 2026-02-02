"""IP Pool management service."""

import ipaddress
from datetime import datetime, UTC
from typing import Optional, Dict, Any

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlmodel import Session

from mikrom.models import IpPool, IpAllocation
from mikrom.utils.logger import get_logger
from mikrom.utils.telemetry import get_tracer, add_span_attributes

logger = get_logger(__name__)
tracer = get_tracer()


# Exception classes
class IPPoolError(Exception):
    """Base exception for IP pool errors."""

    pass


class IPPoolNotFound(IPPoolError):
    """IP pool not found."""

    pass


class NoAvailableIPs(IPPoolError):
    """No available IPs in the pool."""

    pass


class VMAlreadyHasIP(IPPoolError):
    """VM already has an active IP allocation."""

    pass


class InvalidNetwork(IPPoolError):
    """Invalid network configuration."""

    pass


# Helper functions
def _calculate_available_ips(network: str, cidr: str, gateway: str) -> tuple[str, str]:
    """
    Calculate start_ip and end_ip from CIDR.

    Args:
        network: Network prefix (e.g., "172.16.0")
        cidr: CIDR notation (e.g., "172.16.0.0/24")
        gateway: Gateway IP (e.g., "172.16.0.1")

    Returns:
        Tuple of (start_ip, end_ip)

    Raises:
        InvalidNetwork: If CIDR or gateway is invalid
    """
    try:
        net = ipaddress.IPv4Network(cidr, strict=False)
        gateway_ip = ipaddress.IPv4Address(gateway)

        # Get all usable hosts (excludes network and broadcast)
        hosts = list(net.hosts())

        if not hosts:
            raise InvalidNetwork(f"Network {cidr} has no usable hosts")

        # Exclude gateway from the pool
        available_hosts = [h for h in hosts if h != gateway_ip]

        if not available_hosts:
            raise InvalidNetwork(f"No available IPs after excluding gateway {gateway}")

        return (str(available_hosts[0]), str(available_hosts[-1]))

    except (ipaddress.AddressValueError, ipaddress.NetmaskValueError) as e:
        raise InvalidNetwork(f"Invalid network configuration: {e}") from e


def _ip_to_int(ip: str) -> int:
    """
    Convert IP string to integer for sorting.

    Args:
        ip: IP address string (e.g., "172.16.0.5")

    Returns:
        Integer representation of IP
    """
    return int(ipaddress.IPv4Address(ip))


def _int_to_ip(ip_int: int) -> str:
    """
    Convert integer back to IP string.

    Args:
        ip_int: Integer representation of IP

    Returns:
        IP address string
    """
    return str(ipaddress.IPv4Address(ip_int))


class IPPoolService:
    """Service for IP pool management operations."""

    def __init__(self):
        """Initialize service."""
        pass

    async def allocate_ip(
        self,
        session: AsyncSession,
        vm_id: str,
        pool_name: str = "default",
    ) -> Dict[str, Any]:
        """
        Allocate IP from pool for a VM.

        This operation is idempotent - if VM already has an active allocation,
        returns that allocation instead of creating a new one.

        Args:
            session: Database session
            vm_id: VM identifier
            pool_name: Name of the IP pool to allocate from

        Returns:
            Dictionary with ip, gateway, network, and pool name

        Raises:
            IPPoolNotFound: If the specified pool doesn't exist
            NoAvailableIPs: If no IPs are available in the pool
        """
        with tracer.start_as_current_span("service.ippool.allocate") as _span:
            add_span_attributes(
                **{
                    "vm.id": vm_id,
                    "ippool.name": pool_name,
                }
            )

            logger.info(
                "Allocating IP for VM",
                extra={"vm_id": vm_id, "pool_name": pool_name},
            )

            # Check if VM already has active allocation (idempotent)
            existing = await self.get_allocation(session, vm_id)
            if existing:
                logger.info(
                    "VM already has active IP allocation",
                    extra={
                        "vm_id": vm_id,
                        "ip_address": existing.ip_address,
                        "pool_id": existing.pool_id,
                    },
                )
                # Load the pool relationship
                await session.refresh(existing, ["pool"])
                return {
                    "ip": existing.ip_address,
                    "gateway": existing.pool.gateway,
                    "network": existing.pool.cidr,
                    "pool": existing.pool.name,
                }

            # Get pool with lock to prevent concurrent allocations
            stmt = (
                select(IpPool)
                .where(and_(IpPool.name == pool_name, IpPool.is_active))
                .with_for_update()
            )
            result = await session.execute(stmt)
            pool = result.scalar_one_or_none()

            if not pool:
                logger.error(
                    "IP pool not found or not active",
                    extra={"pool_name": pool_name},
                )
                raise IPPoolNotFound(f"IP pool '{pool_name}' not found or not active")

            # Find first available IP
            # Convert IP range to integers for iteration
            start_int = _ip_to_int(pool.start_ip)
            end_int = _ip_to_int(pool.end_ip)

            # Query for all active allocations in this pool
            alloc_stmt = select(IpAllocation.ip_address).where(
                and_(
                    IpAllocation.pool_id == pool.id,
                    IpAllocation.is_active,
                )
            )
            result = await session.execute(alloc_stmt)
            allocated_ips = {row[0] for row in result.all()}

            logger.debug(
                "Finding available IP",
                extra={
                    "pool_id": pool.id,
                    "start_ip": pool.start_ip,
                    "end_ip": pool.end_ip,
                    "allocated_count": len(allocated_ips),
                },
            )

            # Find first available IP
            available_ip = None
            for ip_int in range(start_int, end_int + 1):
                ip_str = _int_to_ip(ip_int)
                if ip_str not in allocated_ips:
                    available_ip = ip_str
                    break

            if not available_ip:
                total_ips = end_int - start_int + 1
                logger.error(
                    "No available IPs in pool",
                    extra={
                        "pool_name": pool_name,
                        "pool_id": pool.id,
                        "total_ips": total_ips,
                        "allocated_ips": len(allocated_ips),
                    },
                )
                raise NoAvailableIPs(
                    f"No available IPs in pool '{pool_name}' ({len(allocated_ips)}/{total_ips} allocated)"
                )

            # Create allocation record
            allocation = IpAllocation(
                pool_id=pool.id,
                vm_id=vm_id,
                ip_address=available_ip,
                is_active=True,
                allocated_at=datetime.utcnow(),
            )
            session.add(allocation)
            await session.commit()
            await session.refresh(allocation)

            logger.info(
                "IP allocated successfully",
                extra={
                    "vm_id": vm_id,
                    "ip_address": available_ip,
                    "pool_name": pool_name,
                    "allocation_id": allocation.id,
                },
            )

            return {
                "ip": available_ip,
                "gateway": pool.gateway,
                "network": pool.cidr,
                "pool": pool.name,
            }

    async def release_ip(
        self,
        session: AsyncSession,
        vm_id: str,
    ) -> bool:
        """
        Release IP allocation for a VM.

        Args:
            session: Database session
            vm_id: VM identifier

        Returns:
            True if IP was released, False if no allocation found
        """
        with tracer.start_as_current_span("service.ippool.release") as _span:
            add_span_attributes(**{"vm.id": vm_id})

            logger.info("Releasing IP for VM", extra={"vm_id": vm_id})

            # Find active allocation
            stmt = select(IpAllocation).where(
                and_(
                    IpAllocation.vm_id == vm_id,
                    IpAllocation.is_active,
                )
            )
            result = await session.execute(stmt)
            allocation = result.scalar_one_or_none()

            if not allocation:
                logger.warning(
                    "No active IP allocation found for VM",
                    extra={"vm_id": vm_id},
                )
                return False

            # Mark as inactive and set release timestamp
            allocation.is_active = False
            allocation.released_at = datetime.utcnow()
            session.add(allocation)
            await session.commit()

            logger.info(
                "IP released successfully",
                extra={
                    "vm_id": vm_id,
                    "ip_address": allocation.ip_address,
                    "allocation_id": allocation.id,
                },
            )

            return True

    async def get_allocation(
        self,
        session: AsyncSession,
        vm_id: str,
    ) -> Optional[IpAllocation]:
        """
        Get active IP allocation for a VM.

        Args:
            session: Database session
            vm_id: VM identifier

        Returns:
            IpAllocation if found, None otherwise
        """
        stmt = (
            select(IpAllocation)
            .where(
                and_(
                    IpAllocation.vm_id == vm_id,
                    IpAllocation.is_active,
                )
            )
            .options(selectinload(IpAllocation.pool))
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_pool_stats(
        self,
        session: AsyncSession,
        pool_name: str = "default",
    ) -> Dict[str, Any]:
        """
        Get statistics for an IP pool.

        Args:
            session: Database session
            pool_name: Name of the IP pool

        Returns:
            Dictionary with total, allocated, available, and usage percentage

        Raises:
            IPPoolNotFound: If pool doesn't exist
        """
        with tracer.start_as_current_span("service.ippool.stats") as _span:
            add_span_attributes(**{"ippool.name": pool_name})

            # Get pool
            stmt = select(IpPool).where(IpPool.name == pool_name)
            result = await session.execute(stmt)
            pool = result.scalar_one_or_none()

            if not pool:
                raise IPPoolNotFound(f"IP pool '{pool_name}' not found")

            # Calculate total IPs
            start_int = _ip_to_int(pool.start_ip)
            end_int = _ip_to_int(pool.end_ip)
            total_ips = end_int - start_int + 1

            # Count allocated IPs
            alloc_stmt = select(func.count(IpAllocation.id)).where(
                and_(
                    IpAllocation.pool_id == pool.id,
                    IpAllocation.is_active,
                )
            )
            result = await session.execute(alloc_stmt)
            allocated = result.scalar_one()

            available = total_ips - allocated
            usage = (allocated / total_ips) if total_ips > 0 else 0.0

            stats = {
                "pool_name": pool_name,
                "total": total_ips,
                "allocated": allocated,
                "available": available,
                "usage": round(usage, 3),
                "network": pool.cidr,
                "gateway": pool.gateway,
                "is_active": pool.is_active,
            }

            logger.debug("Pool statistics retrieved", extra=stats)

            return stats

    async def create_pool(
        self,
        session: AsyncSession,
        name: str,
        network: str,
        cidr: str,
        gateway: str,
        description: Optional[str] = None,
    ) -> IpPool:
        """
        Create a new IP pool.

        Args:
            session: Database session
            name: Pool name (must be unique)
            network: Network prefix (e.g., "172.16.0")
            cidr: CIDR notation (e.g., "172.16.0.0/24")
            gateway: Gateway IP address
            description: Optional description

        Returns:
            Created IpPool object

        Raises:
            InvalidNetwork: If network configuration is invalid
        """
        with tracer.start_as_current_span("service.ippool.create_pool") as _span:
            add_span_attributes(
                **{
                    "ippool.name": name,
                    "ippool.cidr": cidr,
                }
            )

            logger.info(
                "Creating new IP pool",
                extra={
                    "name": name,
                    "network": network,
                    "cidr": cidr,
                    "gateway": gateway,
                },
            )

            # Calculate start and end IPs
            start_ip, end_ip = _calculate_available_ips(network, cidr, gateway)

            # Create pool
            pool = IpPool(
                name=name,
                network=network,
                cidr=cidr,
                gateway=gateway,
                start_ip=start_ip,
                end_ip=end_ip,
                is_active=True,
                description=description,
            )

            session.add(pool)
            await session.commit()
            await session.refresh(pool)

            logger.info(
                "IP pool created successfully",
                extra={
                    "pool_id": pool.id,
                    "pool_name": name,
                    "start_ip": start_ip,
                    "end_ip": end_ip,
                },
            )

            return pool

    # Sync methods for testing
    def _allocate_ip_sync(
        self, session: Session, vm_id: str, pool_name: str = "default"
    ) -> IpAllocation:
        """
        Sync version of allocate_ip for testing.

        Args:
            session: Sync database session
            vm_id: VM identifier
            pool_name: Name of the IP pool

        Returns:
            IpAllocation object

        Raises:
            IPPoolNotFound: If pool doesn't exist
            NoAvailableIPs: If no IPs available
        """
        # Get pool
        statement = (
            select(IpPool)
            .where(IpPool.name == pool_name)
            .where(IpPool.is_active)
        )
        result = session.exec(statement)
        pool_row = result.first()

        if not pool_row:
            raise IPPoolNotFound(f"IP pool '{pool_name}' not found")

        # Extract IpPool object from Row (sqlalchemy returns Row objects from session.exec)
        pool = pool_row[0]

        # Check if VM already has active allocation
        statement = (
            select(IpAllocation)
            .where(IpAllocation.vm_id == vm_id)
            .where(IpAllocation.is_active)
        )
        existing_row = session.exec(statement).first()

        if existing_row:
            return existing_row[0]

        # Get all allocated IPs
        statement = (
            select(IpAllocation.ip_address)
            .where(IpAllocation.pool_id == pool.id)
            .where(IpAllocation.is_active)
        )
        results = session.exec(statement).all()
        # Extract IP addresses from Row objects
        # When selecting a single column, Row[0] gives us the value directly
        allocated_ips = {str(row[0]) for row in results}

        # Find first available IP
        start_int = _ip_to_int(pool.start_ip)
        end_int = _ip_to_int(pool.end_ip)

        available_ip = None
        for ip_int in range(start_int, end_int + 1):
            ip_str = _int_to_ip(ip_int)
            if ip_str not in allocated_ips:
                available_ip = ip_str
                break

        if not available_ip:
            raise NoAvailableIPs(f"No available IPs in pool '{pool_name}'")

        # Create allocation
        allocation = IpAllocation(
            pool_id=pool.id,
            vm_id=vm_id,
            ip_address=available_ip,
            is_active=True,
            allocated_at=datetime.now(UTC),
        )

        session.add(allocation)
        session.commit()
        session.refresh(allocation)

        return allocation

    def _release_ip_sync(self, session: Session, vm_id: str) -> bool:
        """
        Sync version of release_ip for testing.

        Args:
            session: Sync database session
            vm_id: VM identifier

        Returns:
            True if released, False if not found
        """
        allocation_row = session.exec(
            select(IpAllocation).where(
                IpAllocation.vm_id == vm_id, IpAllocation.is_active
            )
        ).first()

        if not allocation_row:
            return False

        allocation = allocation_row[0]

        allocation.is_active = False
        allocation.released_at = datetime.now(UTC)
        session.add(allocation)
        session.commit()

        return True

    def _get_allocation_sync(
        self, session: Session, vm_id: str
    ) -> Optional[IpAllocation]:
        """
        Sync version of get_allocation for testing.

        Args:
            session: Sync database session
            vm_id: VM identifier

        Returns:
            IpAllocation if found, None otherwise
        """
        allocation_row = session.exec(
            select(IpAllocation).where(
                IpAllocation.vm_id == vm_id, IpAllocation.is_active
            )
        ).first()

        if not allocation_row:
            return None

        return allocation_row[0]

    def _get_pool_stats_sync(self, session: Session, pool_name: str) -> Dict[str, Any]:
        """
        Sync version of get_pool_stats for testing.

        Args:
            session: Sync database session
            pool_name: Name of the pool

        Returns:
            Dictionary with pool statistics

        Raises:
            IPPoolNotFound: If pool doesn't exist
        """
        pool_row = session.exec(
            select(IpPool).where(IpPool.name == pool_name, IpPool.is_active)
        ).first()

        if not pool_row:
            raise IPPoolNotFound(f"IP pool '{pool_name}' not found")

        pool = pool_row[0]

        # Calculate total IPs
        start_int = _ip_to_int(pool.start_ip)
        end_int = _ip_to_int(pool.end_ip)
        total_ips = end_int - start_int + 1

        # Count allocated IPs
        allocated_row = session.exec(
            select(func.count(IpAllocation.id)).where(
                IpAllocation.pool_id == pool.id, IpAllocation.is_active
            )
        ).one()

        # Extract count from Row object (sync session returns Row)
        # Check if it's already an integer, otherwise extract from Row
        if isinstance(allocated_row, int):
            allocated = allocated_row
        else:
            allocated = allocated_row[0]

        available = total_ips - allocated
        utilization = (allocated / total_ips * 100) if total_ips > 0 else 0

        return {
            "pool_name": pool.name,
            "network": pool.network,
            "cidr": pool.cidr,
            "gateway": pool.gateway,
            "start_ip": pool.start_ip,
            "end_ip": pool.end_ip,
            "total_ips": total_ips,
            "allocated": allocated,
            "available": available,
            "utilization_percent": round(utilization, 2),
        }
