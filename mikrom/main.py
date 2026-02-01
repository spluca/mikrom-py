"""Main FastAPI application."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from mikrom import __version__
from mikrom.config import settings
from mikrom.utils.logger import setup_logging, get_logger
from mikrom.utils.telemetry import setup_telemetry, instrument_app
from mikrom.middleware.rate_limit import limiter
from mikrom.middleware.logging import LoggingMiddleware
from mikrom.api.v1.router import api_router

# Setup logging and telemetry
setup_logging()
setup_telemetry()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan events."""
    # Startup
    logger.info(
        f"Starting {settings.PROJECT_NAME}",
        extra={
            "version": __version__,
            "environment": settings.ENVIRONMENT,
            "debug": settings.DEBUG,
            "api_prefix": settings.API_V1_PREFIX,
        },
    )

    # Instrument FastAPI app with OpenTelemetry
    instrument_app(app)

    yield

    # Shutdown
    logger.info(f"Shutting down {settings.PROJECT_NAME}")


# Create FastAPI application
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=__version__,
    description="REST API built with FastAPI, SQLModel, and PostgreSQL",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
    debug=settings.DEBUG,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add custom middleware
app.add_middleware(LoggingMiddleware)

# Add rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Include API routers
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/", tags=["Root"])
async def root() -> dict:
    """Root endpoint with API information."""
    return {
        "name": settings.PROJECT_NAME,
        "version": __version__,
        "environment": settings.ENVIRONMENT,
        "docs_url": "/docs",
        "redoc_url": "/redoc",
        "openapi_url": "/openapi.json",
        "health_check": f"{settings.API_V1_PREFIX}/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "mikrom.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
