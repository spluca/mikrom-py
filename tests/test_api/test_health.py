"""Tests for health check endpoint."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check_healthy(client: AsyncClient) -> None:
    """Test health check endpoint returns healthy status."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["healthy", "degraded"]
    assert "version" in data
    assert "database" in data


@pytest.mark.asyncio
async def test_health_check_structure(client: AsyncClient) -> None:
    """Test health check response structure."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()

    # Check all required fields are present
    assert "status" in data
    assert "version" in data
    assert "database" in data

    # Check types
    assert isinstance(data["status"], str)
    assert isinstance(data["version"], str)
    assert isinstance(data["database"], str)


@pytest.mark.asyncio
async def test_health_check_version(client: AsyncClient) -> None:
    """Test health check returns correct version."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["version"] == "1.0.0"


@pytest.mark.asyncio
async def test_health_check_no_auth_required(client: AsyncClient) -> None:
    """Test health check doesn't require authentication."""
    # Health check should be accessible without auth
    response = await client.get("/api/v1/health")
    assert response.status_code == 200

    # Should not return 401 Unauthorized
    assert response.status_code != 401
