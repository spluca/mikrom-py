"""Dependencies for API endpoints."""

from typing import Annotated, AsyncGenerator, Optional

from fastapi import Depends, HTTPException, status, Query
from fastapi.security import OAuth2PasswordBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from mikrom.config import settings
from mikrom.core.security import verify_token
from mikrom.core.exceptions import AuthenticationError
from mikrom.database import get_async_session
from mikrom.models import User

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_db() -> AsyncSession:
    """Get database session."""
    async for session in get_async_session():
        yield session


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Get current authenticated user from JWT token."""
    # Verify token
    user_id = verify_token(token, token_type="access")
    if user_id is None:
        raise AuthenticationError("Could not validate credentials")

    # Get user from database
    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()

    if user is None:
        raise AuthenticationError("User not found")

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )

    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Get current active user."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    return current_user


async def get_current_superuser(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Get current superuser."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions. Superuser required.",
        )
    return current_user


async def get_current_user_from_token(
    token: Annotated[Optional[str], Query()] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
) -> User:
    """
    Get current user from token in query parameter.

    This is used for SSE endpoints where Authorization header is not supported.
    """
    if not token:
        raise AuthenticationError("Token required in query parameter")

    # Verify token
    user_id = verify_token(token, token_type="access")
    if user_id is None:
        raise AuthenticationError("Could not validate credentials")

    # Get user from database
    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()

    if user is None:
        raise AuthenticationError("User not found")

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )

    return user


async def get_redis() -> AsyncGenerator[Redis, None]:
    """Get Redis connection for streaming."""
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        yield redis
    finally:
        await redis.close()
