"""Main router for API v1."""

from fastapi import APIRouter

from mikrom.api.v1.endpoints import auth, users, health

# Create main API v1 router
api_router = APIRouter()

# Include endpoint routers
api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["Authentication"],
)

api_router.include_router(
    users.router,
    prefix="/users",
    tags=["Users"],
)

api_router.include_router(
    health.router,
    prefix="/health",
    tags=["Health"],
)
