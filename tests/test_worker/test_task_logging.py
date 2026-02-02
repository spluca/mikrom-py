"""Unit tests for worker task logging functionality."""

import json
import logging
from io import StringIO
from unittest.mock import AsyncMock, Mock, patch

import pytest

from mikrom.models import VM
from mikrom.utils.context import clear_context
from mikrom.utils.logger import ContextInjectionFilter, CustomJsonFormatter, get_logger
from mikrom.worker.tasks import create_vm_task, delete_vm_task


class TestCreateVMTaskLogging:
    """Tests for create_vm_task logging functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        clear_context()

    def teardown_method(self):
        """Clean up after tests."""
        clear_context()

    @patch("mikrom.worker.tasks.Session")
    @patch("mikrom.worker.tasks.IPPoolClient")
    @patch("mikrom.worker.tasks.FirecrackerClient")
    def test_create_vm_logs_all_steps(
        self, mock_fc_client, mock_ippool_client, mock_session_class
    ):
        """Test that create_vm_task logs all major steps."""
        # Set up logging capture
        logger = get_logger("mikrom.worker.tasks")
        logger.addFilter(ContextInjectionFilter())
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(CustomJsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        # Mock database session
        mock_session = Mock()
        mock_session_class.return_value.__enter__.return_value = mock_session
        mock_session_class.return_value.__exit__.return_value = None

        mock_vm = Mock(spec=VM)
        mock_vm.vm_id = "srv-test123"
        mock_vm.name = "test-vm"
        mock_session.get.return_value = mock_vm
        mock_session.add = Mock()
        mock_session.commit = Mock()

        # Mock IP pool client
        mock_ippool_instance = AsyncMock()
        mock_ippool_instance.allocate_ip.return_value = {"ip": "192.168.1.100"}
        mock_ippool_instance.close = AsyncMock()
        mock_ippool_client.return_value = mock_ippool_instance

        # Mock Firecracker client
        mock_fc_instance = AsyncMock()
        mock_fc_instance.start_vm.return_value = {"status": "success"}
        mock_fc_client.return_value = mock_fc_instance

        # Execute task
        result = create_vm_task(vm_db_id=1, vcpu_count=2, memory_mb=2048)

        # Parse logs
        output = stream.getvalue()
        log_lines = [line for line in output.strip().split("\n") if line]
        logs = [json.loads(line) for line in log_lines]
        messages = [log.get("message", "") for log in logs]

        # Verify all key steps are logged
        assert any("Starting VM creation" in msg for msg in messages)
        assert any("Allocating IP address" in msg for msg in messages)
        assert any("IP allocated successfully" in msg for msg in messages)
        assert any("VM status updated to provisioning" in msg for msg in messages)
        assert any("Starting Firecracker VM" in msg for msg in messages)
        assert any("VM created successfully" in msg for msg in messages)

        # Verify context is set
        assert any(log.get("vm_id") == "srv-test123" for log in logs)
        assert any(log.get("action") == "vm.create.background" for log in logs)

        # Verify result
        assert result["success"] is True
        assert result["vm_id"] == "srv-test123"

        logger.removeHandler(handler)

    @patch("mikrom.worker.tasks.Session")
    @patch("mikrom.worker.tasks.IPPoolClient")
    @patch("mikrom.worker.tasks.FirecrackerClient")
    def test_create_vm_logs_error_and_cleanup(
        self, mock_fc_client, mock_ippool_client, mock_session_class
    ):
        """Test that create_vm_task logs errors and cleanup attempts."""
        # Set up logging capture
        logger = get_logger("mikrom.worker.tasks")
        logger.addFilter(ContextInjectionFilter())
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(CustomJsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        # Mock database session
        mock_session = Mock()
        mock_session_class.return_value.__enter__.return_value = mock_session
        mock_session_class.return_value.__exit__.return_value = None

        mock_vm = Mock(spec=VM)
        mock_vm.vm_id = "srv-error123"
        mock_vm.name = "error-vm"
        mock_session.get.return_value = mock_vm
        mock_session.add = Mock()
        mock_session.commit = Mock()

        # Mock IP pool to raise error
        mock_ippool_instance = AsyncMock()
        mock_ippool_instance.allocate_ip.side_effect = Exception("IP allocation failed")
        mock_ippool_instance.release_ip = AsyncMock()
        mock_ippool_instance.close = AsyncMock()
        mock_ippool_client.return_value = mock_ippool_instance

        # Mock Firecracker client (required even though not used in error path)
        mock_fc_instance = AsyncMock()
        mock_fc_client.return_value = mock_fc_instance

        # Execute task (should raise exception)
        with pytest.raises(Exception, match="IP allocation failed"):
            create_vm_task(vm_db_id=2, vcpu_count=2, memory_mb=2048)

        # Parse logs
        output = stream.getvalue()
        log_lines = [line for line in output.strip().split("\n") if line]
        logs = [json.loads(line) for line in log_lines]
        messages = [log.get("message", "") for log in logs]

        # Verify error and cleanup are logged
        assert any("VM creation failed" in msg for msg in messages)
        assert any("Attempting to cleanup IP allocation" in msg for msg in messages)
        assert any(
            log.get("error") == "IP allocation failed" and log.get("level") == "ERROR"
            for log in logs
        )

        # Verify IP cleanup was called
        mock_ippool_instance.release_ip.assert_called_once_with("srv-error123")

        logger.removeHandler(handler)


class TestDeleteVMTaskLogging:
    """Tests for delete_vm_task logging functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        clear_context()

    def teardown_method(self):
        """Clean up after tests."""
        clear_context()

    @patch("mikrom.worker.tasks.Session")
    @patch("mikrom.worker.tasks.IPPoolClient")
    @patch("mikrom.worker.tasks.FirecrackerClient")
    def test_delete_vm_logs_all_steps(
        self, mock_fc_client, mock_ippool_client, mock_session_class
    ):
        """Test that delete_vm_task logs all major steps."""
        # Set up logging capture
        logger = get_logger("mikrom.worker.tasks")
        logger.addFilter(ContextInjectionFilter())
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(CustomJsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        # Mock database session
        mock_session = Mock()
        mock_session_class.return_value.__enter__.return_value = mock_session
        mock_session_class.return_value.__exit__.return_value = None

        mock_vm = Mock(spec=VM)
        mock_vm.vm_id = "srv-delete123"
        mock_session.get.return_value = mock_vm
        mock_session.add = Mock()
        mock_session.commit = Mock()
        mock_session.delete = Mock()

        # Mock IP pool and Firecracker
        mock_ippool_instance = AsyncMock()
        mock_ippool_instance.release_ip = AsyncMock()
        mock_ippool_instance.close = AsyncMock()
        mock_ippool_client.return_value = mock_ippool_instance

        mock_fc_instance = AsyncMock()
        mock_fc_instance.cleanup_vm = AsyncMock()
        mock_fc_client.return_value = mock_fc_instance

        # Execute task
        result = delete_vm_task(vm_db_id=10, vm_id="srv-delete123")

        # Parse logs
        output = stream.getvalue()
        log_lines = [line for line in output.strip().split("\n") if line]
        logs = [json.loads(line) for line in log_lines]
        messages = [log.get("message", "") for log in logs]

        # Verify all key steps are logged
        assert any("Starting VM deletion" in msg for msg in messages)
        assert any("VM status updated to deleting" in msg for msg in messages)
        assert any("Cleaning up Firecracker VM" in msg for msg in messages)
        assert any("Releasing IP address" in msg for msg in messages)
        assert any("VM deleted from database" in msg for msg in messages)
        assert any("VM deleted successfully" in msg for msg in messages)

        # Verify context is set
        assert any(log.get("vm_id") == "srv-delete123" for log in logs)
        assert any(log.get("action") == "vm.delete.background" for log in logs)

        # Verify result
        assert result["success"] is True
        assert result["status"] == "deleted"

        logger.removeHandler(handler)

    @patch("mikrom.worker.tasks.Session")
    @patch("mikrom.worker.tasks.IPPoolClient")
    @patch("mikrom.worker.tasks.FirecrackerClient")
    def test_delete_vm_continues_on_partial_failure(
        self, mock_fc_client, mock_ippool_client, mock_session_class
    ):
        """Test that delete_vm_task continues even if cleanup steps fail."""
        # Set up logging capture
        logger = get_logger("mikrom.worker.tasks")
        logger.addFilter(ContextInjectionFilter())
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(CustomJsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.WARNING)

        # Mock database session
        mock_session = Mock()
        mock_session_class.return_value.__enter__.return_value = mock_session
        mock_session_class.return_value.__exit__.return_value = None

        mock_vm = Mock(spec=VM)
        mock_vm.vm_id = "srv-partial123"
        mock_session.get.return_value = mock_vm
        mock_session.add = Mock()
        mock_session.commit = Mock()
        mock_session.delete = Mock()

        # Mock IP pool to succeed
        mock_ippool_instance = AsyncMock()
        mock_ippool_instance.release_ip = AsyncMock()
        mock_ippool_instance.close = AsyncMock()
        mock_ippool_client.return_value = mock_ippool_instance

        # Mock Firecracker to fail
        mock_fc_instance = AsyncMock()
        mock_fc_instance.cleanup_vm.side_effect = Exception(
            "Firecracker cleanup failed"
        )
        mock_fc_client.return_value = mock_fc_instance

        # Execute task (should still succeed)
        result = delete_vm_task(vm_db_id=11, vm_id="srv-partial123")

        # Parse logs
        output = stream.getvalue()
        log_lines = [line for line in output.strip().split("\n") if line]
        logs = [json.loads(line) for line in log_lines]

        # Verify warning logged but task succeeded
        warning_logs = [log for log in logs if log.get("level") == "WARNING"]
        assert len(warning_logs) > 0, "Should log cleanup failure as warning"
        assert any(
            "Firecracker cleanup failed" in log.get("message", "")
            for log in warning_logs
        )

        # Verify task still succeeded
        assert result["success"] is True
        assert result["status"] == "deleted"

        logger.removeHandler(handler)
