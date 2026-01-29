"""Tests for security module (Argon2 hashing and JWT tokens)."""

from datetime import timedelta

from mikrom.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    create_refresh_token,
    verify_token,
)


def test_password_hashing() -> None:
    """Test password hashing with Argon2."""
    password = "mysecretpassword123"
    hashed = get_password_hash(password)

    # Hash should be different from plain password
    assert hashed != password

    # Hash should start with $argon2id$ (Argon2id variant)
    assert hashed.startswith("$argon2id$")

    # Hash should be reasonably long
    assert len(hashed) > 50


def test_password_verification_success() -> None:
    """Test successful password verification."""
    password = "mysecretpassword123"
    hashed = get_password_hash(password)

    # Correct password should verify
    assert verify_password(password, hashed) is True


def test_password_verification_failure() -> None:
    """Test failed password verification."""
    password = "mysecretpassword123"
    wrong_password = "wrongpassword456"
    hashed = get_password_hash(password)

    # Wrong password should not verify
    assert verify_password(wrong_password, hashed) is False


def test_password_hashing_deterministic() -> None:
    """Test that same password produces different hashes (salt)."""
    password = "mysecretpassword123"
    hash1 = get_password_hash(password)
    hash2 = get_password_hash(password)

    # Different hashes due to different salts
    assert hash1 != hash2

    # But both should verify the same password
    assert verify_password(password, hash1) is True
    assert verify_password(password, hash2) is True


def test_empty_password() -> None:
    """Test hashing and verifying empty password."""
    password = ""
    hashed = get_password_hash(password)

    assert verify_password(password, hashed) is True
    assert verify_password("notmpty", hashed) is False


def test_long_password() -> None:
    """Test hashing long passwords (Argon2 has no 72-byte limit like bcrypt)."""
    # Create a very long password (more than bcrypt's 72-byte limit)
    password = "a" * 200
    hashed = get_password_hash(password)

    # Should hash and verify successfully
    assert verify_password(password, hashed) is True

    # Slightly different password should not verify
    wrong_password = "a" * 199 + "b"
    assert verify_password(wrong_password, hashed) is False


def test_unicode_password() -> None:
    """Test hashing passwords with unicode characters."""
    password = "contraseña🔐密码"
    hashed = get_password_hash(password)

    assert verify_password(password, hashed) is True
    assert verify_password("wrongpassword", hashed) is False


def test_create_access_token() -> None:
    """Test creating an access token."""
    user_id = "123"
    token = create_access_token(subject=user_id)

    # Token should be a non-empty string
    assert isinstance(token, str)
    assert len(token) > 0

    # Token should have 3 parts (header.payload.signature)
    assert token.count(".") == 2


def test_create_access_token_with_expiration() -> None:
    """Test creating an access token with custom expiration."""
    user_id = "123"
    expires_delta = timedelta(minutes=15)
    token = create_access_token(subject=user_id, expires_delta=expires_delta)

    assert isinstance(token, str)
    assert len(token) > 0


def test_create_refresh_token() -> None:
    """Test creating a refresh token."""
    user_id = "123"
    token = create_refresh_token(subject=user_id)

    # Token should be a non-empty string
    assert isinstance(token, str)
    assert len(token) > 0

    # Token should have 3 parts
    assert token.count(".") == 2


def test_create_refresh_token_with_expiration() -> None:
    """Test creating a refresh token with custom expiration."""
    user_id = "123"
    expires_delta = timedelta(days=14)
    token = create_refresh_token(subject=user_id, expires_delta=expires_delta)

    assert isinstance(token, str)
    assert len(token) > 0


def test_verify_access_token() -> None:
    """Test verifying a valid access token."""
    user_id = "123"
    token = create_access_token(subject=user_id)

    # Verify token
    verified_user_id = verify_token(token, token_type="access")

    assert verified_user_id == user_id


def test_verify_refresh_token() -> None:
    """Test verifying a valid refresh token."""
    user_id = "456"
    token = create_refresh_token(subject=user_id)

    # Verify token with correct type
    verified_user_id = verify_token(token, token_type="refresh")

    assert verified_user_id == user_id


def test_verify_token_wrong_type() -> None:
    """Test that access token fails when verified as refresh token."""
    user_id = "123"
    access_token = create_access_token(subject=user_id)

    # Try to verify access token as refresh token (should fail)
    verified_user_id = verify_token(access_token, token_type="refresh")

    assert verified_user_id is None


def test_verify_invalid_token() -> None:
    """Test verifying an invalid token."""
    invalid_token = "invalid.token.here"

    verified_user_id = verify_token(invalid_token, token_type="access")

    assert verified_user_id is None


def test_verify_malformed_token() -> None:
    """Test verifying a malformed token."""
    malformed_token = "notavalidtoken"

    verified_user_id = verify_token(malformed_token, token_type="access")

    assert verified_user_id is None


def test_verify_empty_token() -> None:
    """Test verifying an empty token."""
    verified_user_id = verify_token("", token_type="access")

    assert verified_user_id is None


def test_token_contains_correct_subject() -> None:
    """Test that token contains the correct subject."""
    user_ids = ["1", "123", "abc123", "user@example.com"]

    for user_id in user_ids:
        token = create_access_token(subject=user_id)
        verified_user_id = verify_token(token, token_type="access")
        assert verified_user_id == user_id


def test_different_tokens_for_different_users() -> None:
    """Test that different users get different tokens."""
    token1 = create_access_token(subject="user1")
    token2 = create_access_token(subject="user2")

    # Tokens should be different
    assert token1 != token2

    # Each token should verify to its own user
    assert verify_token(token1, token_type="access") == "user1"
    assert verify_token(token2, token_type="access") == "user2"
