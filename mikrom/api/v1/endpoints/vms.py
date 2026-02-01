"""VM management endpoints."""

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
import math

from mikrom.api.deps import get_db, get_current_active_user
from mikrom.models import User, VMStatus
from mikrom.schemas.vm import (
    VMCreate,
    VMUpdate,
    VMResponse,
    VMListResponse,
)
from mikrom.services.vm_service import VMService
from mikrom.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


def get_vm_service():
    """Get VM service instance."""
    return VMService()


@router.post(
    "/",
    response_model=VMResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new VM",
    description="Create a new Firecracker microVM. The VM will be created asynchronously.",
)
async def create_vm(
    vm_data: VMCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    vm_service: Annotated[VMService, Depends(get_vm_service)],
):
    """Create a new VM."""
    try:
        # Create VM (starts background task)
        vm = await vm_service.create_vm(
            session=session,
            user=current_user,
            name=vm_data.name,
            vcpu_count=vm_data.vcpu_count,
            memory_mb=vm_data.memory_mb,
            description=vm_data.description,
        )

        return vm

    except Exception as e:
        logger.error(f"Failed to create VM: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create VM: {str(e)}",
        )


@router.get(
    "/",
    response_model=VMListResponse,
    summary="List VMs",
    description="List all VMs owned by the current user (superusers see all VMs).",
)
async def list_vms(
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    vm_service: Annotated[VMService, Depends(get_vm_service)],
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
):
    """List user's VMs with pagination."""
    offset = (page - 1) * page_size

    vms, total = await vm_service.get_user_vms(
        session=session, user=current_user, offset=offset, limit=page_size
    )

    total_pages = math.ceil(total / page_size) if total > 0 else 0

    return VMListResponse(
        items=vms,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get(
    "/{vm_id}",
    response_model=VMResponse,
    summary="Get VM details",
    description="Get details of a specific VM.",
)
async def get_vm(
    vm_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    vm_service: Annotated[VMService, Depends(get_vm_service)],
):
    """Get VM details."""
    vm = await vm_service.get_vm_by_id(session, vm_id, current_user)

    if not vm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="VM not found"
        )

    return vm


@router.patch(
    "/{vm_id}",
    response_model=VMResponse,
    summary="Update VM",
    description="Update VM name and/or description.",
)
async def update_vm(
    vm_id: str,
    vm_data: VMUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    vm_service: Annotated[VMService, Depends(get_vm_service)],
):
    """Update VM metadata."""
    vm = await vm_service.get_vm_by_id(session, vm_id, current_user)

    if not vm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="VM not found"
        )

    # Update fields
    if vm_data.name is not None:
        vm.name = vm_data.name
    if vm_data.description is not None:
        vm.description = vm_data.description

    session.add(vm)
    await session.commit()
    await session.refresh(vm)

    return vm


@router.delete(
    "/{vm_id}",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Delete VM",
    description="Delete a VM. The deletion will be performed asynchronously.",
)
async def delete_vm(
    vm_id: str,
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    vm_service: Annotated[VMService, Depends(get_vm_service)],
):
    """Delete a VM."""
    vm = await vm_service.get_vm_by_id(session, vm_id, current_user)

    if not vm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="VM not found"
        )

    # Can't delete if already deleting
    if vm.status == VMStatus.DELETING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="VM is already being deleted"
        )

    await vm_service.delete_vm(session, vm)

    return {"message": "VM deletion queued", "vm_id": vm.vm_id, "status": "deleting"}
