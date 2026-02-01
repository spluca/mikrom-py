"""Background tasks for VM operations."""

import secrets
from typing import Optional
from sqlmodel import Session, select

from mikrom.database import sync_engine
from mikrom.models import VM
from mikrom.clients.ippool import IPPoolClient
from mikrom.clients.firecracker import FirecrackerClient
from mikrom.utils.logger import get_logger

logger = get_logger(__name__)


async def create_vm_task(
    ctx: dict,
    vm_db_id: int,
    vcpu_count: int,
    memory_mb: int,
    kernel_path: Optional[str] = None,
    host: Optional[str] = None,
) -> dict:
    """
    Background task to create and start a VM.

    Args:
        ctx: arq context
        vm_db_id: Database ID of VM record
        vcpu_count: Number of vCPUs
        memory_mb: Memory in MB
        kernel_path: Optional kernel path
        host: Optional target host

    Returns:
        dict with results
    """
    logger.info(f"Starting VM creation task for VM ID {vm_db_id}")

    ippool = IPPoolClient()
    firecracker = FirecrackerClient()

    try:
        # Get VM from database
        with Session(sync_engine) as session:
            vm = session.get(VM, vm_db_id)
            if not vm:
                raise ValueError(f"VM {vm_db_id} not found in database")

            vm_id = vm.vm_id
            vm_name = vm.name

            logger.info(f"Creating VM {vm_id} ({vm_name})")

        # Step 1: Allocate IP
        logger.info(f"Allocating IP for VM {vm_id}")
        ip_info = await ippool.allocate_ip(vm_id, vm_name)
        ip_address = ip_info["ip"]

        # Update VM with IP
        with Session(sync_engine) as session:
            vm = session.get(VM, vm_db_id)
            vm.ip_address = ip_address
            vm.status = "provisioning"
            session.add(vm)
            session.commit()

        # Step 2: Start VM with Firecracker
        logger.info(f"Starting Firecracker VM {vm_id}")
        result = await firecracker.start_vm(
            vm_id=vm_id,
            vcpu_count=vcpu_count,
            memory_mb=memory_mb,
            kernel_path=kernel_path,
            limit=host,
        )

        # Step 3: Update VM status to running
        with Session(sync_engine) as session:
            vm = session.get(VM, vm_db_id)
            vm.status = "running"
            vm.host = host
            vm.kernel_path = kernel_path
            vm.error_message = None
            session.add(vm)
            session.commit()

        logger.info(f"VM {vm_id} created successfully at {ip_address}")

        return {
            "success": True,
            "vm_id": vm_id,
            "ip_address": ip_address,
            "status": "running",
        }

    except Exception as e:
        logger.error(f"Failed to create VM {vm_db_id}: {str(e)}")

        # Update VM status to error
        with Session(sync_engine) as session:
            vm = session.get(VM, vm_db_id)
            if vm:
                vm.status = "error"
                vm.error_message = str(e)
                session.add(vm)
                session.commit()

        # Try to cleanup IP if allocated
        try:
            if vm_id:
                await ippool.release_ip(vm_id)
        except Exception as cleanup_error:
            logger.error(f"Failed to cleanup IP: {str(cleanup_error)}")

        raise

    finally:
        await ippool.close()


async def delete_vm_task(
    ctx: dict, vm_db_id: int, vm_id: str, host: Optional[str] = None
) -> dict:
    """
    Background task to delete a VM.

    Args:
        ctx: arq context
        vm_db_id: Database ID of VM record
        vm_id: Firecracker VM ID
        host: Optional target host

    Returns:
        dict with results
    """
    logger.info(f"Starting VM deletion task for VM {vm_id}")

    ippool = IPPoolClient()
    firecracker = FirecrackerClient()

    try:
        # Update status to deleting
        with Session(sync_engine) as session:
            vm = session.get(VM, vm_db_id)
            if vm:
                vm.status = "deleting"
                session.add(vm)
                session.commit()

        # Step 1: Cleanup VM with Firecracker
        logger.info(f"Cleaning up Firecracker VM {vm_id}")
        try:
            await firecracker.cleanup_vm(vm_id, limit=host)
        except Exception as e:
            logger.warning(f"Firecracker cleanup failed (continuing): {e}")

        # Step 2: Release IP
        logger.info(f"Releasing IP for VM {vm_id}")
        try:
            await ippool.release_ip(vm_id)
        except Exception as e:
            logger.warning(f"IP release failed (continuing): {e}")

        # Step 3: Delete from database
        with Session(sync_engine) as session:
            vm = session.get(VM, vm_db_id)
            if vm:
                session.delete(vm)
                session.commit()

        logger.info(f"VM {vm_id} deleted successfully")

        return {"success": True, "vm_id": vm_id, "status": "deleted"}

    except Exception as e:
        logger.error(f"Failed to delete VM {vm_id}: {str(e)}")

        # Update status back to error
        with Session(sync_engine) as session:
            vm = session.get(VM, vm_db_id)
            if vm:
                vm.status = "error"
                vm.error_message = f"Deletion failed: {str(e)}"
                session.add(vm)
                session.commit()

        raise

    finally:
        await ippool.close()
