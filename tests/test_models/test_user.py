"""Tests for database models."""

import pytest
from datetime import datetime
from sqlmodel import Session, create_engine, SQLModel, select

from mikrom.models.user import User
from mikrom.core.security import get_password_hash


@pytest.fixture
def test_engine():
    """Create a test database engine."""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def test_session(test_engine):
    """Create a test database session."""
    with Session(test_engine) as session:
        yield session


def test_user_model_creation(test_session: Session) -> None:
    """Test creating a user model."""
    user = User(
        email="test@example.com",
        username="testuser",
        hashed_password=get_password_hash("password123"),
        full_name="Test User",
    )

    test_session.add(user)
    test_session.commit()
    test_session.refresh(user)

    assert user.id is not None
    assert user.email == "test@example.com"
    assert user.username == "testuser"
    assert user.full_name == "Test User"
    assert user.is_active is True
    assert user.is_superuser is False


def test_user_model_timestamps(test_session: Session) -> None:
    """Test that timestamps are automatically set."""
    user = User(
        email="test@example.com",
        username="testuser",
        hashed_password=get_password_hash("password123"),
    )

    test_session.add(user)
    test_session.commit()
    test_session.refresh(user)

    assert user.created_at is not None
    assert user.updated_at is not None
    assert isinstance(user.created_at, datetime)
    assert isinstance(user.updated_at, datetime)


def test_user_model_default_values(test_session: Session) -> None:
    """Test default values for user model."""
    user = User(
        email="test@example.com",
        username="testuser",
        hashed_password=get_password_hash("password123"),
    )

    test_session.add(user)
    test_session.commit()
    test_session.refresh(user)

    # Check defaults
    assert user.is_active is True
    assert user.is_superuser is False
    assert user.full_name is None


def test_user_model_unique_email(test_session: Session) -> None:
    """Test that email must be unique."""
    user1 = User(
        email="test@example.com",
        username="testuser1",
        hashed_password=get_password_hash("password123"),
    )

    user2 = User(
        email="test@example.com",
        username="testuser2",
        hashed_password=get_password_hash("password123"),
    )

    test_session.add(user1)
    test_session.commit()

    test_session.add(user2)
    with pytest.raises(Exception):  # SQLAlchemy will raise IntegrityError
        test_session.commit()


def test_user_model_unique_username(test_session: Session) -> None:
    """Test that username must be unique."""
    user1 = User(
        email="test1@example.com",
        username="testuser",
        hashed_password=get_password_hash("password123"),
    )

    user2 = User(
        email="test2@example.com",
        username="testuser",
        hashed_password=get_password_hash("password123"),
    )

    test_session.add(user1)
    test_session.commit()

    test_session.add(user2)
    with pytest.raises(Exception):  # SQLAlchemy will raise IntegrityError
        test_session.commit()


def test_user_model_superuser(test_session: Session) -> None:
    """Test creating a superuser."""
    user = User(
        email="admin@example.com",
        username="admin",
        hashed_password=get_password_hash("admin123"),
        is_superuser=True,
    )

    test_session.add(user)
    test_session.commit()
    test_session.refresh(user)

    assert user.is_superuser is True
    assert user.is_active is True


def test_user_model_inactive_user(test_session: Session) -> None:
    """Test creating an inactive user."""
    user = User(
        email="inactive@example.com",
        username="inactive",
        hashed_password=get_password_hash("password123"),
        is_active=False,
    )

    test_session.add(user)
    test_session.commit()
    test_session.refresh(user)

    assert user.is_active is False


def test_user_model_query_by_email(test_session: Session) -> None:
    """Test querying user by email."""
    user = User(
        email="test@example.com",
        username="testuser",
        hashed_password=get_password_hash("password123"),
    )

    test_session.add(user)
    test_session.commit()

    # Query by email using session.exec() instead of session.query()
    statement = select(User).where(User.email == "test@example.com")
    found_user = test_session.exec(statement).first()

    assert found_user is not None
    assert found_user.email == "test@example.com"
    assert found_user.username == "testuser"


def test_user_model_query_by_username(test_session: Session) -> None:
    """Test querying user by username."""
    user = User(
        email="test@example.com",
        username="testuser",
        hashed_password=get_password_hash("password123"),
    )

    test_session.add(user)
    test_session.commit()

    # Query by username using session.exec() instead of session.query()
    statement = select(User).where(User.username == "testuser")
    found_user = test_session.exec(statement).first()

    assert found_user is not None
    assert found_user.username == "testuser"
    assert found_user.email == "test@example.com"


def test_user_model_update(test_session: Session) -> None:
    """Test updating user model."""
    user = User(
        email="test@example.com",
        username="testuser",
        hashed_password=get_password_hash("password123"),
        full_name="Old Name",
    )

    test_session.add(user)
    test_session.commit()
    test_session.refresh(user)

    # Update user
    user.full_name = "New Name"
    test_session.commit()
    test_session.refresh(user)

    assert user.full_name == "New Name"
    # updated_at should change (though we need to check if onupdate is working)
    # This depends on the TimestampModel implementation


def test_user_model_delete(test_session: Session) -> None:
    """Test deleting user model."""
    user = User(
        email="test@example.com",
        username="testuser",
        hashed_password=get_password_hash("password123"),
    )

    test_session.add(user)
    test_session.commit()
    user_id = user.id

    # Delete user
    test_session.delete(user)
    test_session.commit()

    # Query should return None using session.exec() instead of session.query()
    statement = select(User).where(User.id == user_id)
    found_user = test_session.exec(statement).first()
    assert found_user is None


def test_user_model_required_fields(test_session: Session) -> None:
    """Test that required fields must be provided."""
    # Missing email
    with pytest.raises(Exception):
        user = User(
            username="testuser",
            hashed_password=get_password_hash("password123"),
        )
        test_session.add(user)
        test_session.commit()

    test_session.rollback()

    # Missing username
    with pytest.raises(Exception):
        user = User(
            email="test@example.com",
            hashed_password=get_password_hash("password123"),
        )
        test_session.add(user)
        test_session.commit()

    test_session.rollback()

    # Missing hashed_password
    with pytest.raises(Exception):
        user = User(
            email="test@example.com",
            username="testuser",
        )
        test_session.add(user)
        test_session.commit()
