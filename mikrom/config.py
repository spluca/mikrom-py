"""Application configuration using Pydantic Settings."""

from typing import List
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API Configuration
    PROJECT_NAME: str = "Mikrom API"
    VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"

    # Database Configuration
    DATABASE_URL: str
    DATABASE_ECHO: bool = False

    # Security Configuration
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS Configuration
    BACKEND_CORS_ORIGINS: List[str] = []

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | List[str]) -> List[str]:
        """Parse CORS origins from string or list."""
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, list):
            return v
        elif isinstance(v, str):
            import json

            return json.loads(v)
        raise ValueError(v)

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"  # json or console

    # OpenTelemetry Configuration
    OTEL_SERVICE_NAME: str = "mikrom-api"
    OTEL_TRACE_SAMPLE_RATE: float = 1.0  # 1.0 = 100% sampling
    OTEL_EXPORT_CONSOLE: bool = True

    # Redis/Celery configuration
    REDIS_URL: str = "redis://localhost:6379"
    CELERY_QUEUE_NAME: str = "mikrom:queue"

    # Celery Worker Configuration
    CELERY_WORKER_POOL: str = "prefork"  # prefork, threads, gevent, solo
    CELERY_WORKER_CONCURRENCY: int = 4  # Number of worker processes/threads
    CELERY_TASK_SOFT_TIME_LIMIT: int = 180  # 3 minutes - soft limit (warning)
    CELERY_TASK_HARD_TIME_LIMIT: int = 240  # 4 minutes - hard limit (force kill)

    # Flower monitoring
    FLOWER_BASIC_AUTH: str = "admin:changeme"
    FLOWER_PORT: int = 5555

    # IP Pool configuration
    IPPOOL_API_URL: str = "http://localhost:8090"

    # Firecracker configuration
    FIRECRACKER_DEPLOY_PATH: str = "/path/to/firecracker-deploy"
    FIRECRACKER_DEFAULT_HOST: str | None = None

    # Ansible Configuration
    ANSIBLE_PLAYBOOK_TIMEOUT: int = 120  # 2 minutes - playbook execution timeout
    ANSIBLE_SSH_TIMEOUT: int = 30  # 30 seconds - SSH connection timeout

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


# Global settings instance
settings = Settings()
