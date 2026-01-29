"""User management endpoints (CRUD operations)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, func

from mikrom.api.deps import get_db, get_current_user, get_current_superuser
from mikrom.core.security import get_password_hash
from mikrom.core.exceptions import NotFoundError, ConflictError, PermissionDeniedError
from mikrom.models import User
from mikrom.schemas import UserResponse, UserUpdate, PaginatedResponse

router = APIRouter()


@router.get("", response_model=PaginatedResponse[UserResponse])
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
) -> PaginatedResponse[UserResponse]:
    """
    List all users with pagination.

    Requires authentication. Regular users can only see active users,
    superusers can see all users.
    """
    # Calculate offset
    offset = (page - 1) * page_size

    # Build query
    query = select(User)
    if not current_user.is_superuser:
        query = query.where(User.is_active)

    # Get total count
    count_query = select(func.count()).select_from(User)
    if not current_user.is_superuser:
        count_query = count_query.where(User.is_active)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Get paginated users
    query = query.offset(offset).limit(page_size)
    result = await db.execute(query)
    users = list(result.scalars().all())

    # Calculate total pages
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    return PaginatedResponse(
        items=users,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """
    Get user by ID.

    Users can get their own information. Superusers can get any user's information.
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise NotFoundError("User not found")

    # Check permissions
    if not current_user.is_superuser and current_user.id != user_id:
        raise PermissionDeniedError("Not enough permissions")

    return user


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_update: UserUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """
    Update user information.

    Users can update their own information. Superusers can update any user.
    Regular users cannot change their is_active or is_superuser status.
    """
    # Get user
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise NotFoundError("User not found")

    # Check permissions
    if not current_user.is_superuser and current_user.id != user_id:
        raise PermissionDeniedError("Not enough permissions")

    # Update fields
    update_data = user_update.model_dump(exclude_unset=True)

    # Regular users cannot change these fields
    if not current_user.is_superuser:
        update_data.pop("is_active", None)
        update_data.pop("is_superuser", None)

    # Check for email uniqueness if updating
    if "email" in update_data and update_data["email"] != user.email:
        email_result = await db.execute(
            select(User).where(User.email == update_data["email"])
        )
        if email_result.scalar_one_or_none():
            raise ConflictError("Email already registered")

    # Check for username uniqueness if updating
    if "username" in update_data and update_data["username"] != user.username:
        username_result = await db.execute(
            select(User).where(User.username == update_data["username"])
        )
        if username_result.scalar_one_or_none():
            raise ConflictError("Username already taken")

    # Hash password if updating
    if "password" in update_data:
        update_data["hashed_password"] = get_password_hash(update_data.pop("password"))

    # Apply updates
    for field, value in update_data.items():
        setattr(user, field, value)

    db.add(user)
    await db.commit()
    await db.refresh(user)

    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_superuser)],
) -> None:
    """
    Delete user (hard delete).

    Only superusers can delete users.
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise NotFoundError("User not found")

    # Prevent deleting yourself
    if user.id == current_user.id:
        raise PermissionDeniedError("Cannot delete your own account")

    await db.delete(user)
    await db.commit()
