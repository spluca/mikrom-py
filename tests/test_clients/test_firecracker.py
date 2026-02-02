"""Tests for FirecrackerClient."""

import pytest
from unittest.mock import Mock, patch

from mikrom.clients.firecracker import FirecrackerClient, FirecrackerError


@pytest.fixture
def mock_deploy_path(tmp_path):
    """Create temporary deploy path with required playbooks."""
    deploy_path = tmp_path / "firecracker-deploy"
    deploy_path.mkdir()

    # Create required playbooks
    (deploy_path / "start-vm.yml").touch()
    (deploy_path / "stop-vm.yml").touch()
    (deploy_path / "cleanup-vm.yml").touch()

    return deploy_path


@pytest.fixture
def firecracker_client(mock_deploy_path):
    """Create FirecrackerClient with mock deploy path."""
    return FirecrackerClient(deploy_path=mock_deploy_path)


def test_init_with_valid_path(mock_deploy_path):
    """Test client initialization with valid deploy path."""
    client = FirecrackerClient(deploy_path=mock_deploy_path)
    assert client.deploy_path == mock_deploy_path


def test_init_with_missing_path(tmp_path):
    """Test client initialization with missing deploy path."""
    nonexistent_path = tmp_path / "nonexistent"

    with pytest.raises(FirecrackerError, match="does not exist"):
        FirecrackerClient(deploy_path=nonexistent_path)


def test_init_with_missing_playbooks(tmp_path):
    """Test client initialization with missing required playbooks."""
    deploy_path = tmp_path / "firecracker-deploy"
    deploy_path.mkdir()

    # Create only one playbook (missing others)
    (deploy_path / "start-vm.yml").touch()

    with pytest.raises(FirecrackerError, match="Required playbook not found"):
        FirecrackerClient(deploy_path=deploy_path)


@patch("mikrom.clients.firecracker.ansible_runner.run")
def test_run_playbook_success(mock_ansible_run, firecracker_client):
    """Test successful playbook execution."""
    # Mock successful runner
    mock_runner = Mock()
    mock_runner.status = "successful"
    mock_runner.rc = 0
    mock_runner.stats = {"ok": 1, "changed": 1}
    mock_ansible_run.return_value = mock_runner

    result = firecracker_client._run_playbook(
        playbook="start-vm.yml",
        extravars={"vm_id": "srv-test", "vcpu_count": 2},
        limit="testhost",
    )

    assert result.status == "successful"
    assert result.rc == 0

    # Verify ansible_runner was called correctly
    mock_ansible_run.assert_called_once()
    call_kwargs = mock_ansible_run.call_args.kwargs
    assert call_kwargs["playbook"] == "start-vm.yml"
    assert call_kwargs["extravars"]["vm_id"] == "srv-test"
    assert call_kwargs["limit"] == "testhost"


@patch("mikrom.clients.firecracker.ansible_runner.run")
def test_run_playbook_failure(mock_ansible_run, firecracker_client):
    """Test playbook execution failure."""
    # Mock failed runner
    mock_runner = Mock()
    mock_runner.status = "failed"
    mock_runner.rc = 2
    mock_runner.stats = {"ok": 0, "failed": 1}
    mock_ansible_run.return_value = mock_runner

    with pytest.raises(FirecrackerError, match="failed with status"):
        firecracker_client._run_playbook(
            playbook="start-vm.yml",
            extravars={"vm_id": "srv-test"},
        )


@patch.object(FirecrackerClient, "_run_playbook")
@pytest.mark.asyncio
async def test_start_vm(mock_run_playbook, firecracker_client):
    """Test starting a VM."""
    mock_runner = Mock()
    mock_runner.status = "successful"
    mock_runner._extracted_stats = {"ok": 1}
    mock_run_playbook.return_value = mock_runner

    result = await firecracker_client.start_vm(
        vm_id="srv-test123",
        vcpu_count=2,
        memory_mb=2048,
        limit="hypervisor1.example.com",
    )

    assert result["status"] == "successful"
    assert result["stats"] == {"ok": 1}

    # Verify playbook was called with correct parameters
    mock_run_playbook.assert_called_once()
    call_args = mock_run_playbook.call_args
    assert call_args[0][0] == "start-vm.yml"  # First positional arg
    extravars = call_args[0][1]  # Second positional arg (dict)
    assert extravars["fc_vm_id"] == "srv-test123"
    assert extravars["fc_vcpu_count"] == 2
    assert extravars["fc_mem_size_mib"] == 2048
    assert call_args[0][2] == "hypervisor1.example.com"  # Third positional arg (limit)


@patch.object(FirecrackerClient, "_run_playbook")
@pytest.mark.asyncio
async def test_start_vm_with_custom_kernel(mock_run_playbook, firecracker_client):
    """Test starting a VM with custom kernel."""
    mock_runner = Mock()
    mock_runner.status = "successful"
    mock_runner._extracted_stats = {"ok": 1}
    mock_run_playbook.return_value = mock_runner

    await firecracker_client.start_vm(
        vm_id="srv-test123",
        vcpu_count=2,
        memory_mb=2048,
        kernel_path="/custom/kernel.bin",
        limit="hypervisor1.example.com",
    )

    call_args = mock_run_playbook.call_args
    extravars = call_args[0][1]
    assert extravars["fc_kernel_path"] == "/custom/kernel.bin"


@patch.object(FirecrackerClient, "_run_playbook")
@pytest.mark.asyncio
async def test_stop_vm(mock_run_playbook, firecracker_client):
    """Test stopping a VM."""
    mock_runner = Mock()
    mock_runner.status = "successful"
    mock_runner._extracted_stats = {"ok": 1}
    mock_run_playbook.return_value = mock_runner

    result = await firecracker_client.stop_vm(
        vm_id="srv-test123",
        limit="hypervisor1.example.com",
    )

    assert result["status"] == "successful"

    # Verify playbook was called correctly
    call_args = mock_run_playbook.call_args
    assert call_args[0][0] == "stop-vm.yml"
    extravars = call_args[0][1]
    assert extravars["fc_vm_id"] == "srv-test123"
    assert call_args[0][2] == "hypervisor1.example.com"


@patch.object(FirecrackerClient, "_run_playbook")
@pytest.mark.asyncio
async def test_cleanup_vm(mock_run_playbook, firecracker_client):
    """Test cleaning up a VM."""
    mock_runner = Mock()
    mock_runner.status = "successful"
    mock_runner._extracted_stats = {"ok": 1}
    mock_run_playbook.return_value = mock_runner

    result = await firecracker_client.cleanup_vm(
        vm_id="srv-test123",
        limit="hypervisor1.example.com",
    )

    assert result["status"] == "successful"

    # Verify playbook was called correctly
    call_args = mock_run_playbook.call_args
    assert call_args[0][0] == "cleanup-vm.yml"
    extravars = call_args[0][1]
    assert extravars["fc_vm_id"] == "srv-test123"
    assert call_args[0][2] == "hypervisor1.example.com"


@patch("mikrom.clients.firecracker.ansible_runner.run")
def test_error_handling_with_stats_extraction(mock_ansible_run, firecracker_client):
    """Test error handling extracts stats before failure."""
    # Mock failed runner with stats
    mock_runner = Mock()
    mock_runner.status = "failed"
    mock_runner.rc = 2
    mock_runner.stats = {"ok": 0, "failed": 1, "unreachable": 0}
    mock_ansible_run.return_value = mock_runner

    with pytest.raises(FirecrackerError):
        firecracker_client._run_playbook(
            playbook="start-vm.yml",
            extravars={"vm_id": "srv-test"},
        )

    # Stats should be accessible even on failure
    assert mock_runner.stats["failed"] == 1


@patch("mikrom.clients.firecracker.ansible_runner.run")
def test_artifact_dir_cleanup(mock_ansible_run, firecracker_client):
    """Test that artifact directory is cleaned up."""
    mock_runner = Mock()
    mock_runner.status = "successful"
    mock_runner.rc = 0
    mock_runner.stats = {"ok": 1}
    mock_ansible_run.return_value = mock_runner

    firecracker_client._run_playbook(
        playbook="start-vm.yml",
        extravars={"vm_id": "srv-test"},
    )

    # Verify artifact_dir was created in /tmp
    call_kwargs = mock_ansible_run.call_args.kwargs
    artifact_dir = call_kwargs["artifact_dir"]
    assert "/tmp/ansible-" in artifact_dir
