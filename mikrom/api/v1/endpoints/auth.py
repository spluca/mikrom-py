"""Authentication endpoints: login, register, refresh token."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from mikrom.api.deps import get_db, get_current_user
from mikrom.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    verify_token,
)
from mikrom.core.exceptions import AuthenticationError, ConflictError
from mikrom.models import User
from mikrom.schemas import (
    Token,
    UserCreate,
    UserResponse,
    UserLogin,
    RefreshTokenRequest,
)

router = APIRouter()


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
async def register(
    user_in: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """
    Register a new user.

    Creates a new user account with the provided credentials.
    The password is hashed before storing in the database.
    """
    # Check if user already exists by email
    result = await db.execute(select(User).where(User.email == user_in.email))
    if result.scalar_one_or_none():
        raise ConflictError("Email already registered")

    # Check if username already exists
    result = await db.execute(select(User).where(User.username == user_in.username))
    if result.scalar_one_or_none():
        raise ConflictError("Username already taken")

    # Create new user
    user = User(
        email=user_in.email,
        username=user_in.username,
        full_name=user_in.full_name,
        hashed_password=get_password_hash(user_in.password),
        is_active=True,
        is_superuser=False,
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    return user


@router.post("/login", response_model=Token)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Token:
    """
    OAuth2 compatible token login.

    Get an access token for future requests using username and password.
    The username field can accept either username or email.
    """
    # Try to find user by username or email
    result = await db.execute(
        select(User).where(
            (User.username == form_data.username) | (User.email == form_data.username)
        )
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise AuthenticationError("Incorrect username or password")

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )

    # Create tokens
    access_token = create_access_token(subject=user.id)
    refresh_token = create_refresh_token(subject=user.id)

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
    )


@router.post("/login/json", response_model=Token)
async def login_json(
    user_login: UserLogin,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Token:
    """
    JSON-based login endpoint.

    Alternative to OAuth2 password flow, accepts JSON body.
    """
    # Try to find user by username or email
    result = await db.execute(
        select(User).where(
            (User.username == user_login.username) | (User.email == user_login.username)
        )
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(user_login.password, user.hashed_password):
        raise AuthenticationError("Incorrect username or password")

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )

    # Create tokens
    access_token = create_access_token(subject=user.id)
    refresh_token = create_refresh_token(subject=user.id)

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
    )


@router.post("/refresh", response_model=Token)
async def refresh_token(
    refresh_request: RefreshTokenRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Token:
    """
    Refresh access token.

    Get a new access token using a valid refresh token.
    """
    # Verify refresh token
    user_id = verify_token(refresh_request.refresh_token, token_type="refresh")
    if user_id is None:
        raise AuthenticationError("Invalid refresh token")

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

    # Create new tokens
    access_token = create_access_token(subject=user.id)
    new_refresh_token = create_refresh_token(subject=user.id)

    return Token(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """
    Get current user information.

    Returns the profile information of the authenticated user.
    """
    return current_user
