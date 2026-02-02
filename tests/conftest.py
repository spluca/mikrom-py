"""Pytest configuration and fixtures."""

from typing import AsyncGenerator, Generator
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import create_engine
from sqlmodel import SQLModel, Session
from opentelemetry import trace

from mikrom.main import app
from mikrom.api.deps import get_db
from mikrom.config import settings
from mikrom.models.user import User
from mikrom.models.vm import VM, VMStatus
from mikrom.core.security import get_password_hash

# Test database URL (use different database for tests)
TEST_DATABASE_URL = settings.DATABASE_URL.replace(
    "/mikrom_db", "/mikrom_test_db"
).replace("postgresql://", "postgresql+asyncpg://")

# Sync database URL for sync tests
TEST_DATABASE_URL_SYNC = settings.DATABASE_URL.replace("/mikrom_db", "/mikrom_test_db")


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for each test."""
    # Create engine for this test
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
        poolclass=None,  # Disable pooling to avoid event loop issues
    )

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    # Create session
    async_session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    # Provide session
    async with async_session_maker() as session:
        yield session

    # Drop tables
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)

    # Dispose engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create a test client with a test database session."""

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def sync_session() -> Generator[Session, None, None]:
    """Create a sync database session for sync tests (like ippool_service tests)."""
    # Create engine
    engine = create_engine(
        TEST_DATABASE_URL_SYNC,
        echo=False,
        pool_pre_ping=True,
    )

    # Create tables
    SQLModel.metadata.create_all(engine)

    # Create session
    with Session(engine) as session:
        yield session

    # Drop tables
    SQLModel.metadata.drop_all(engine)

    # Dispose engine
    engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user for VM relationships."""
    user = User(
        email="test@example.com",
        username="testuser",
        hashed_password=get_password_hash("password123"),
        full_name="Test User",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture(scope="function")
async def test_vm(db_session: AsyncSession, test_user: User) -> VM:
    """Create a test VM for endpoint tests."""
    vm = VM(
        vm_id="srv-test1234",
        name="test-vm",
        description="Test VM for integration tests",
        vcpu_count=2,
        memory_mb=2048,
        ip_address="192.168.1.100",
        status=VMStatus.RUNNING,
        host="hypervisor1.example.com",
        user_id=test_user.id,
    )
    db_session.add(vm)
    await db_session.commit()
    await db_session.refresh(vm)
    return vm


@pytest.fixture(scope="session", autouse=True)
def shutdown_tracer_provider():
    """Shutdown OpenTelemetry TracerProvider after all tests complete.

    This fixture ensures that the BatchSpanProcessor's background thread
    is properly shut down before pytest closes stdout/stderr, preventing
    "I/O operation on closed file" errors.
    """
    yield

    # Force shutdown of the tracer provider after all tests
    try:
        tracer_provider = trace.get_tracer_provider()
        if hasattr(tracer_provider, "force_flush"):
            # Flush pending spans first
            tracer_provider.force_flush(timeout_millis=5000)
        if hasattr(tracer_provider, "shutdown"):
            # Then shutdown the provider
            tracer_provider.shutdown()
    except Exception:
        # Ignore any errors during shutdown
        pass
