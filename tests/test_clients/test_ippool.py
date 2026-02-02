"""Tests for IPPoolClient."""

import pytest
from unittest.mock import AsyncMock, patch, Mock
import httpx

from mikrom.clients.ippool import IPPoolClient, IPPoolError


@pytest.fixture
def ippool_client():
    """Create IPPoolClient for testing."""
    return IPPoolClient(base_url="http://testippool:8090")


@pytest.mark.asyncio
@patch("mikrom.clients.ippool.httpx.AsyncClient")
async def test_allocate_ip_success(mock_async_client_class, ippool_client):
    """Test successful IP allocation."""
    # Mock response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "ip": "192.168.1.100",
        "vm_id": "srv-test123",
        "hostname": "testvm",
        "allocated_at": "2024-02-02T12:00:00",
    }

    # Mock client instance
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_async_client_class.return_value = mock_client

    # Create new client with mocked httpx.AsyncClient
    client = IPPoolClient(base_url="http://testippool:8090")

    result = await client.allocate_ip(vm_id="srv-test123", hostname="testvm")

    assert result["ip"] == "192.168.1.100"
    assert result["vm_id"] == "srv-test123"
    assert result["hostname"] == "testvm"

    # Verify API was called correctly
    mock_client.post.assert_called_once_with(
        "/api/v1/ip/allocate", json={"vm_id": "srv-test123", "hostname": "testvm"}
    )


@pytest.mark.asyncio
@patch("mikrom.clients.ippool.httpx.AsyncClient")
async def test_allocate_ip_without_hostname(mock_async_client_class):
    """Test IP allocation without hostname."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "ip": "192.168.1.101",
        "vm_id": "srv-test124",
        "hostname": None,
        "allocated_at": "2024-02-02T12:00:00",
    }

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_async_client_class.return_value = mock_client

    client = IPPoolClient(base_url="http://testippool:8090")
    result = await client.allocate_ip(vm_id="srv-test124")

    assert result["ip"] == "192.168.1.101"

    # Verify hostname was passed as None
    call_args = mock_client.post.call_args
    assert call_args.kwargs["json"]["hostname"] is None


@pytest.mark.asyncio
@patch("mikrom.clients.ippool.httpx.AsyncClient")
async def test_allocate_ip_http_error(mock_async_client_class):
    """Test IP allocation with HTTP error."""
    mock_response = Mock()
    mock_response.status_code = 400
    mock_response.text = "No IPs available"

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.post.return_value.raise_for_status = Mock(
        side_effect=httpx.HTTPStatusError(
            "Bad Request", request=Mock(), response=mock_response
        )
    )
    mock_async_client_class.return_value = mock_client

    client = IPPoolClient(base_url="http://testippool:8090")

    with pytest.raises(IPPoolError, match="Failed to allocate IP"):
        await client.allocate_ip(vm_id="srv-test123")


@pytest.mark.asyncio
async def test_release_ip_success():
    """Test successful IP release."""
    client = IPPoolClient(base_url="http://testippool:8090")

    # Mock the delete method
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json = Mock(
        return_value={"message": "IP released", "ip": "192.168.1.100"}
    )

    client.client.delete = AsyncMock(return_value=mock_response)

    result = await client.release_ip(vm_id="srv-test123")

    assert result["message"] == "IP released"
    assert result["ip"] == "192.168.1.100"

    # Verify API was called correctly
    client.client.delete.assert_called_once_with("/api/v1/ip/release/srv-test123")


@pytest.mark.asyncio
async def test_release_ip_not_found():
    """Test IP release when VM not found (404 is handled gracefully)."""
    client = IPPoolClient(base_url="http://testippool:8090")

    # Mock the delete method to raise HTTPStatusError with 404
    mock_response = Mock()
    mock_response.status_code = 404
    mock_response.text = "VM not found"

    http_error = httpx.HTTPStatusError(
        "Not Found", request=Mock(), response=mock_response
    )
    http_error.response = mock_response  # Ensure response is accessible

    client.client.delete = AsyncMock(return_value=mock_response)
    mock_response.raise_for_status = Mock(side_effect=http_error)

    # 404 is handled gracefully and returns a dict instead of raising
    result = await client.release_ip(vm_id="srv-nonexistent")

    assert result["message"] == "No allocation found"
    assert result["vm_id"] == "srv-nonexistent"


@pytest.mark.asyncio
@patch("mikrom.clients.ippool.httpx.AsyncClient")
async def test_get_ip_info_success(mock_async_client_class):
    """Test getting IP info for a VM."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "ip": "192.168.1.100",
        "vm_id": "srv-test123",
        "hostname": "testvm",
        "allocated_at": "2024-02-02T12:00:00",
    }

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_async_client_class.return_value = mock_client

    client = IPPoolClient(base_url="http://testippool:8090")
    result = await client.get_ip_info(vm_id="srv-test123")

    assert result["ip"] == "192.168.1.100"
    assert result["vm_id"] == "srv-test123"

    # Verify API was called correctly
    mock_client.get.assert_called_once_with("/api/v1/ip/srv-test123")


@pytest.mark.asyncio
@patch("mikrom.clients.ippool.httpx.AsyncClient")
async def test_connection_error(mock_async_client_class):
    """Test handling of connection errors."""
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
    mock_async_client_class.return_value = mock_client

    client = IPPoolClient(base_url="http://testippool:8090")

    with pytest.raises(IPPoolError, match="IP Pool API request failed"):
        await client.allocate_ip(vm_id="srv-test123")


@pytest.mark.asyncio
@patch("mikrom.clients.ippool.httpx.AsyncClient")
async def test_timeout_error(mock_async_client_class):
    """Test handling of timeout errors."""
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Request timeout"))
    mock_async_client_class.return_value = mock_client

    client = IPPoolClient(base_url="http://testippool:8090")

    with pytest.raises(IPPoolError):
        await client.allocate_ip(vm_id="srv-test123")


def test_client_initialization():
    """Test client initialization with different URLs."""
    # Default URL
    client1 = IPPoolClient()
    assert client1.base_url is not None

    # Custom URL
    client2 = IPPoolClient(base_url="http://custom:8090")
    assert client2.base_url == "http://custom:8090"
