"""Database connection and session management."""

from typing import AsyncGenerator, Generator

from sqlmodel import create_engine, Session, SQLModel
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from mikrom.config import settings

# Create synchronous engine for Alembic migrations
sync_engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DATABASE_ECHO,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# Create async engine for FastAPI
async_database_url = settings.DATABASE_URL.replace(
    "postgresql://", "postgresql+asyncpg://"
)

async_engine = create_async_engine(
    async_database_url,
    echo=settings.DATABASE_ECHO,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# Create async session factory
async_session_maker = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


def create_db_and_tables() -> None:
    """Create all database tables. Used for testing and initial setup."""
    SQLModel.metadata.create_all(sync_engine)


def get_session() -> Generator[Session, None, None]:
    """Get a synchronous database session. Used primarily for migrations."""
    with Session(sync_engine) as session:
        yield session


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Get an async database session for FastAPI endpoints."""
    async with async_session_maker() as session:
        yield session
