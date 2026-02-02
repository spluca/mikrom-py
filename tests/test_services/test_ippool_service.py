"""Tests for IP Pool service."""

import pytest
from sqlmodel import Session, select

from mikrom.models import IpPool, IpAllocation
from mikrom.models.vm import VM, VMStatus
from mikrom.models.user import User
from mikrom.services.ippool_service import (
    IPPoolService,
    IPPoolNotFound,
    NoAvailableIPs,
    InvalidNetwork,
    _calculate_available_ips,
    _ip_to_int,
    _int_to_ip,
)


class TestHelperFunctions:
    """Test helper functions."""

    def test_calculate_available_ips_success(self):
        """Test successful IP range calculation."""
        start_ip, end_ip = _calculate_available_ips(
            network="172.16.0",
            cidr="172.16.0.0/24",
            gateway="172.16.0.1",
        )
        assert start_ip == "172.16.0.2"
        assert end_ip == "172.16.0.254"

    def test_calculate_available_ips_small_network(self):
        """Test calculation with small network."""
        start_ip, end_ip = _calculate_available_ips(
            network="10.0.0",
            cidr="10.0.0.0/29",  # /29 = 8 IPs total, 6 usable
            gateway="10.0.0.1",
        )
        assert start_ip == "10.0.0.2"
        assert end_ip == "10.0.0.6"

    def test_calculate_available_ips_invalid_cidr(self):
        """Test with invalid CIDR."""
        with pytest.raises(InvalidNetwork, match="Invalid network configuration"):
            _calculate_available_ips(
                network="172.16.0",
                cidr="invalid-cidr",
                gateway="172.16.0.1",
            )

    def test_calculate_available_ips_invalid_gateway(self):
        """Test with invalid gateway."""
        with pytest.raises(InvalidNetwork, match="Invalid network configuration"):
            _calculate_available_ips(
                network="172.16.0",
                cidr="172.16.0.0/24",
                gateway="invalid-gateway",
            )

    def test_calculate_available_ips_no_usable_hosts(self):
        """Test with network that has no usable hosts."""
        with pytest.raises(
            InvalidNetwork, match="No available IPs after excluding gateway"
        ):
            _calculate_available_ips(
                network="172.16.0",
                cidr="172.16.0.1/32",  # Single host, no range
                gateway="172.16.0.1",
            )

    def test_ip_to_int(self):
        """Test IP to integer conversion."""
        assert _ip_to_int("172.16.0.1") == 2886729729
        assert _ip_to_int("192.168.1.1") == 3232235777
        assert _ip_to_int("10.0.0.1") == 167772161

    def test_int_to_ip(self):
        """Test integer to IP conversion."""
        assert _int_to_ip(2886729729) == "172.16.0.1"
        assert _int_to_ip(3232235777) == "192.168.1.1"
        assert _int_to_ip(167772161) == "10.0.0.1"

    def test_ip_conversion_round_trip(self):
        """Test converting IP to int and back."""
        ip = "192.168.100.50"
        assert _int_to_ip(_ip_to_int(ip)) == ip


class TestIPPoolService:
    """Test IP Pool service."""

    @pytest.fixture
    def ippool_service(self):
        """Create IP pool service instance."""
        return IPPoolService()

    @pytest.fixture
    def test_user(self, sync_session: Session):
        """Create a test user."""
        user = User(
            username="testuser",
            email="test@example.com",
            hashed_password="dummy_hash",
            is_active=True,
        )
        sync_session.add(user)
        sync_session.commit()
        sync_session.refresh(user)
        return user

    @pytest.fixture
    def test_vms(self, sync_session: Session, test_user: User):
        """Create test VM records."""
        assert test_user.id is not None, "Test user must have an ID"
        vms = []
        for i in range(1, 11):  # Create 10 VMs (vm-001 to vm-010)
            vm = VM(
                vm_id=f"vm-{i:03d}",
                name=f"Test VM {i}",
                vcpu_count=1,
                memory_mb=512,
                status=VMStatus.PENDING,
                user_id=test_user.id,
            )
            sync_session.add(vm)
            vms.append(vm)
        sync_session.commit()
        return vms

    @pytest.fixture
    def test_pool(self, sync_session: Session):
        """Create a test IP pool."""
        pool = IpPool(
            name="test-pool",
            network="192.168.1",
            cidr="192.168.1.0/24",
            gateway="192.168.1.1",
            start_ip="192.168.1.2",
            end_ip="192.168.1.10",  # Small range for testing
            is_active=True,
            description="Test pool",
        )
        sync_session.add(pool)
        sync_session.commit()
        sync_session.refresh(pool)
        return pool

    @pytest.fixture
    def small_pool(self, sync_session: Session):
        """Create a small IP pool with only 2 IPs."""
        pool = IpPool(
            name="small-pool",
            network="10.0.0",
            cidr="10.0.0.0/30",
            gateway="10.0.0.1",
            start_ip="10.0.0.2",
            end_ip="10.0.0.3",
            is_active=True,
            description="Small test pool",
        )
        sync_session.add(pool)
        sync_session.commit()
        sync_session.refresh(pool)
        return pool

    def test_allocate_ip_success(
        self,
        sync_session: Session,
        test_pool: IpPool,
        test_vms: list,
        ippool_service: IPPoolService,
    ):
        """Test successful IP allocation."""
        # Allocate IP
        allocation = ippool_service._allocate_ip_sync(
            session=sync_session, vm_id="vm-001", pool_name="test-pool"
        )

        assert allocation is not None
        assert allocation.vm_id == "vm-001"
        assert allocation.pool_id == test_pool.id
        assert allocation.ip_address == "192.168.1.2"  # First available IP
        assert allocation.is_active is True
        assert allocation.allocated_at is not None

    def test_allocate_ip_idempotent(
        self,
        sync_session: Session,
        test_pool: IpPool,
        test_vms: list,
        ippool_service: IPPoolService,
    ):
        """Test that allocating twice returns same IP."""
        # First allocation
        allocation1 = ippool_service._allocate_ip_sync(
            session=sync_session, vm_id="vm-001", pool_name="test-pool"
        )
        first_ip = allocation1.ip_address

        # Second allocation - should return same IP
        allocation2 = ippool_service._allocate_ip_sync(
            session=sync_session, vm_id="vm-001", pool_name="test-pool"
        )

        assert allocation2.ip_address == first_ip
        assert allocation2.id == allocation1.id

        # Verify only one allocation exists
        allocations = sync_session.exec(
            select(IpAllocation).where(
                IpAllocation.vm_id == "vm-001", IpAllocation.is_active
            )
        ).all()
        assert len(allocations) == 1

    def test_allocate_ip_multiple_vms(
        self,
        sync_session: Session,
        test_pool: IpPool,
        test_vms: list,
        ippool_service: IPPoolService,
    ):
        """Test allocating IPs to multiple VMs."""
        # Allocate to 3 VMs
        vm_ids = ["vm-001", "vm-002", "vm-003"]
        allocations = []

        for vm_id in vm_ids:
            allocation = ippool_service._allocate_ip_sync(
                session=sync_session, vm_id=vm_id, pool_name="test-pool"
            )
            allocations.append(allocation)

        # Verify all got different IPs
        ips = [a.ip_address for a in allocations]
        assert len(ips) == len(set(ips))  # All unique
        assert ips[0] == "192.168.1.2"
        assert ips[1] == "192.168.1.3"
        assert ips[2] == "192.168.1.4"

    def test_allocate_ip_pool_not_found(
        self, sync_session: Session, test_vms: list, ippool_service: IPPoolService
    ):
        """Test allocation when pool doesn't exist."""
        with pytest.raises(IPPoolNotFound, match="IP pool 'nonexistent' not found"):
            ippool_service._allocate_ip_sync(
                session=sync_session, vm_id="vm-001", pool_name="nonexistent"
            )

    def test_allocate_ip_pool_exhausted(
        self,
        sync_session: Session,
        small_pool: IpPool,
        test_vms: list,
        ippool_service: IPPoolService,
    ):
        """Test allocation when pool is exhausted."""
        # Allocate both IPs
        ippool_service._allocate_ip_sync(
            session=sync_session, vm_id="vm-001", pool_name="small-pool"
        )
        ippool_service._allocate_ip_sync(
            session=sync_session, vm_id="vm-002", pool_name="small-pool"
        )

        # Try to allocate third IP - should fail
        with pytest.raises(NoAvailableIPs, match="No available IPs in pool"):
            ippool_service._allocate_ip_sync(
                session=sync_session, vm_id="vm-003", pool_name="small-pool"
            )

    def test_release_ip_success(
        self,
        sync_session: Session,
        test_pool: IpPool,
        test_vms: list,
        ippool_service: IPPoolService,
    ):
        """Test successful IP release."""
        # Allocate IP first
        allocation = ippool_service._allocate_ip_sync(
            session=sync_session, vm_id="vm-001", pool_name="test-pool"
        )

        # Release IP
        result = ippool_service._release_ip_sync(session=sync_session, vm_id="vm-001")

        assert result is True

        # Verify allocation is marked inactive
        allocation = sync_session.exec(
            select(IpAllocation).where(IpAllocation.vm_id == "vm-001")
        ).first()
        assert allocation is not None
        assert allocation.is_active is False
        assert allocation.released_at is not None

    def test_release_ip_not_found(
        self, sync_session: Session, ippool_service: IPPoolService
    ):
        """Test releasing IP that doesn't exist."""
        result = ippool_service._release_ip_sync(
            session=sync_session, vm_id="nonexistent"
        )
        assert result is False

    def test_release_ip_allows_reallocation(
        self,
        sync_session: Session,
        test_pool: IpPool,
        test_vms: list,
        ippool_service: IPPoolService,
    ):
        """Test that released IP can be reallocated."""
        # Allocate IP
        allocation1 = ippool_service._allocate_ip_sync(
            session=sync_session, vm_id="vm-001", pool_name="test-pool"
        )
        ip1 = allocation1.ip_address

        # Release IP
        ippool_service._release_ip_sync(session=sync_session, vm_id="vm-001")

        # Allocate to different VM - should get same IP
        allocation2 = ippool_service._allocate_ip_sync(
            session=sync_session, vm_id="vm-002", pool_name="test-pool"
        )
        ip2 = allocation2.ip_address

        assert ip2 == ip1

    def test_get_allocation_success(
        self,
        sync_session: Session,
        test_pool: IpPool,
        test_vms: list,
        ippool_service: IPPoolService,
    ):
        """Test getting allocation info."""
        # Allocate IP
        ippool_service._allocate_ip_sync(
            session=sync_session, vm_id="vm-001", pool_name="test-pool"
        )

        # Get allocation
        allocation = ippool_service._get_allocation_sync(
            session=sync_session, vm_id="vm-001"
        )

        assert allocation is not None
        assert allocation.vm_id == "vm-001"
        assert allocation.is_active is True

    def test_get_allocation_not_found(
        self, sync_session: Session, ippool_service: IPPoolService
    ):
        """Test getting non-existent allocation."""
        allocation = ippool_service._get_allocation_sync(
            session=sync_session, vm_id="nonexistent"
        )
        assert allocation is None

    def test_get_allocation_ignores_inactive(
        self,
        sync_session: Session,
        test_pool: IpPool,
        test_vms: list,
        ippool_service: IPPoolService,
    ):
        """Test that get_allocation ignores released IPs."""
        # Allocate and release
        ippool_service._allocate_ip_sync(
            session=sync_session, vm_id="vm-001", pool_name="test-pool"
        )
        ippool_service._release_ip_sync(session=sync_session, vm_id="vm-001")

        # Should not find active allocation
        allocation = ippool_service._get_allocation_sync(
            session=sync_session, vm_id="vm-001"
        )
        assert allocation is None

    def test_get_pool_stats_empty_pool(
        self, sync_session: Session, test_pool: IpPool, ippool_service: IPPoolService
    ):
        """Test pool stats with no allocations."""
        stats = ippool_service._get_pool_stats_sync(
            session=sync_session, pool_name="test-pool"
        )

        assert stats["pool_name"] == "test-pool"
        assert stats["total_ips"] == 9  # .2 to .10 inclusive
        assert stats["allocated"] == 0
        assert stats["available"] == 9
        assert stats["utilization_percent"] == 0.0

    def test_get_pool_stats_with_allocations(
        self,
        sync_session: Session,
        test_pool: IpPool,
        test_vms: list,
        ippool_service: IPPoolService,
    ):
        """Test pool stats with some allocations."""
        # Allocate 3 IPs
        for i in range(1, 4):
            ippool_service._allocate_ip_sync(
                session=sync_session, vm_id=f"vm-{i:03d}", pool_name="test-pool"
            )

        stats = ippool_service._get_pool_stats_sync(
            session=sync_session, pool_name="test-pool"
        )

        assert stats["total_ips"] == 9
        assert stats["allocated"] == 3
        assert stats["available"] == 6
        assert stats["utilization_percent"] == pytest.approx(33.33, rel=0.01)

    def test_get_pool_stats_full_pool(
        self,
        sync_session: Session,
        small_pool: IpPool,
        test_vms: list,
        ippool_service: IPPoolService,
    ):
        """Test pool stats when fully allocated."""
        # Allocate both IPs
        ippool_service._allocate_ip_sync(
            session=sync_session, vm_id="vm-001", pool_name="small-pool"
        )
        ippool_service._allocate_ip_sync(
            session=sync_session, vm_id="vm-002", pool_name="small-pool"
        )

        stats = ippool_service._get_pool_stats_sync(
            session=sync_session, pool_name="small-pool"
        )

        assert stats["total_ips"] == 2
        assert stats["allocated"] == 2
        assert stats["available"] == 0
        assert stats["utilization_percent"] == 100.0

    def test_get_pool_stats_pool_not_found(
        self, sync_session: Session, ippool_service: IPPoolService
    ):
        """Test pool stats for non-existent pool."""
        with pytest.raises(IPPoolNotFound, match="IP pool 'nonexistent' not found"):
            ippool_service._get_pool_stats_sync(
                session=sync_session, pool_name="nonexistent"
            )

    def test_get_pool_stats_ignores_released(
        self,
        sync_session: Session,
        test_pool: IpPool,
        test_vms: list,
        ippool_service: IPPoolService,
    ):
        """Test that stats ignore released IPs."""
        # Allocate 2 IPs
        ippool_service._allocate_ip_sync(
            session=sync_session, vm_id="vm-001", pool_name="test-pool"
        )
        ippool_service._allocate_ip_sync(
            session=sync_session, vm_id="vm-002", pool_name="test-pool"
        )

        # Release one
        ippool_service._release_ip_sync(session=sync_session, vm_id="vm-001")

        stats = ippool_service._get_pool_stats_sync(
            session=sync_session, pool_name="test-pool"
        )

        # Should only count active allocation
        assert stats["allocated"] == 1
        assert stats["available"] == 8
