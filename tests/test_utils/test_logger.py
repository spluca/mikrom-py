"""Unit tests for mikrom.utils.logger module."""

import json
import logging
from io import StringIO
from unittest.mock import patch

from opentelemetry import trace

from mikrom.utils.logger import (
    CustomJsonFormatter,
    get_logger,
    setup_logging,
)
from mikrom.utils.context import set_context, clear_context


class TestCustomJsonFormatter:
    """Tests for CustomJsonFormatter class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.formatter = CustomJsonFormatter()
        clear_context()

    def teardown_method(self):
        """Clean up after tests."""
        clear_context()

    def test_format_basic_log_record(self):
        """Test formatting a basic log record to JSON."""
        # Create a log record
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        # Format the record
        result = self.formatter.format(record)

        # Parse JSON
        log_data = json.loads(result)

        # Verify basic fields
        assert log_data["level"] == "INFO"
        assert log_data["logger"] == "test.logger"
        assert log_data["message"] == "Test message"
        assert "timestamp" in log_data

        # Verify timestamp format (Unix timestamp)
        # timestamp is a Unix timestamp
        assert isinstance(log_data["timestamp"], (int, float))
        assert log_data["timestamp"] > 0

    def test_format_with_extra_fields(self):
        """Test formatting log with extra fields."""
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        # Add extra fields
        record.vm_id = "vm-123"
        record.user_id = 456
        record.custom_field = "custom_value"

        result = self.formatter.format(record)
        log_data = json.loads(result)

        # Verify extra fields are included
        assert log_data["vm_id"] == "vm-123"
        assert log_data["user_id"] == 456
        assert log_data["custom_field"] == "custom_value"

    def test_format_with_trace_context(self):
        """Test formatting log with OpenTelemetry trace context."""
        from mikrom.utils.logger import ContextInjectionFilter

        # Create a span to establish trace context
        tracer = trace.get_tracer(__name__)

        with tracer.start_as_current_span("test-span") as span:
            span_context = span.get_span_context()

            record = logging.LogRecord(
                name="test.logger",
                level=logging.INFO,
                pathname="test.py",
                lineno=42,
                msg="Test message",
                args=(),
                exc_info=None,
            )

            # Apply filter to inject trace context
            filter = ContextInjectionFilter()
            filter.filter(record)

            result = self.formatter.format(record)
            log_data = json.loads(result)

            # Verify trace context is included
            assert "trace_id" in log_data
            assert "span_id" in log_data
            assert log_data["trace_id"] == format(span_context.trace_id, "032x")
            assert log_data["span_id"] == format(span_context.span_id, "016x")

    def test_format_with_context_variables(self):
        """Test formatting log with context variables."""
        from mikrom.utils.logger import ContextInjectionFilter

        # Set context
        set_context(
            vm_id="vm-789",
            user_id=999,
            user_name="testuser",
            request_id="req-123",
            action="test.action",
        )

        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        # Apply filter to inject context
        filter = ContextInjectionFilter()
        filter.filter(record)

        result = self.formatter.format(record)
        log_data = json.loads(result)

        # Verify context variables are included
        assert log_data["vm_id"] == "vm-789"
        assert log_data["user_id"] == 999
        assert log_data["user_name"] == "testuser"
        assert log_data["request_id"] == "req-123"
        assert log_data["action"] == "test.action"

    def test_format_with_exception(self):
        """Test formatting log with exception information."""
        import sys

        try:
            raise ValueError("Test error")
        except ValueError:
            record = logging.LogRecord(
                name="test.logger",
                level=logging.ERROR,
                pathname="test.py",
                lineno=42,
                msg="Error occurred",
                args=(),
                exc_info=sys.exc_info(),
            )

            result = self.formatter.format(record)
            log_data = json.loads(result)

            # Verify exception info is included
            assert log_data["level"] == "ERROR"
            assert log_data["message"] == "Error occurred"
            assert "exc_info" in log_data
            assert "ValueError: Test error" in log_data["exc_info"]

    def test_format_excludes_internal_fields(self):
        """Test that internal logging fields are excluded from output."""
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        result = self.formatter.format(record)
        log_data = json.loads(result)

        # Verify internal fields are not included
        excluded_fields = [
            "name",
            "levelname",
            "levelno",
            "pathname",
            "filename",
            "module",
            "lineno",
            "funcName",
            "created",
            "msecs",
            "relativeCreated",
            "thread",
            "threadName",
            "processName",
            "process",
            "msg",
            "args",
            "exc_info",
            "exc_text",
            "stack_info",
        ]

        for field in excluded_fields:
            assert field not in log_data

    def test_format_different_log_levels(self):
        """Test formatting logs at different levels."""
        levels = [
            (logging.DEBUG, "DEBUG"),
            (logging.INFO, "INFO"),
            (logging.WARNING, "WARNING"),
            (logging.ERROR, "ERROR"),
            (logging.CRITICAL, "CRITICAL"),
        ]

        for level_num, level_name in levels:
            record = logging.LogRecord(
                name="test.logger",
                level=level_num,
                pathname="test.py",
                lineno=42,
                msg=f"Message at {level_name}",
                args=(),
                exc_info=None,
            )

            result = self.formatter.format(record)
            log_data = json.loads(result)

            assert log_data["level"] == level_name
            assert log_data["message"] == f"Message at {level_name}"

    def test_format_with_message_formatting(self):
        """Test formatting log with message arguments."""
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="User %s logged in from %s",
            args=("john", "192.168.1.1"),
            exc_info=None,
        )

        result = self.formatter.format(record)
        log_data = json.loads(result)

        assert log_data["message"] == "User john logged in from 192.168.1.1"


class TestGetLogger:
    """Tests for get_logger function."""

    def test_get_logger_returns_logger(self):
        """Test that get_logger returns a logging.Logger instance."""
        logger = get_logger("test.module")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test.module"

    def test_get_logger_caches_loggers(self):
        """Test that get_logger returns the same logger for the same name."""
        logger1 = get_logger("test.module")
        logger2 = get_logger("test.module")
        assert logger1 is logger2

    def test_logger_can_log_at_different_levels(self):
        """Test that logger can log at different levels."""
        logger = get_logger("test.module")

        # Create a string buffer to capture logs
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(CustomJsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        # Log at different levels
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")
        logger.critical("Critical message")

        # Get the output
        output = stream.getvalue()
        lines = output.strip().split("\n")

        # Verify we got 5 log lines
        assert len(lines) == 5

        # Parse and verify each log
        log_levels = []
        for line in lines:
            log_data = json.loads(line)
            log_levels.append(log_data["level"])

        assert log_levels == ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

        # Clean up
        logger.removeHandler(handler)

    def test_logger_with_extra_context(self):
        """Test that logger includes extra context in logs."""
        logger = get_logger("test.module")

        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(CustomJsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        # Log with extra context
        logger.info(
            "Test message",
            extra={
                "user_id": 123,
                "action": "test_action",
                "custom_field": "value",
            },
        )

        output = stream.getvalue()
        log_data = json.loads(output.strip())

        # Verify extra fields are included
        assert log_data["user_id"] == 123
        assert log_data["action"] == "test_action"
        assert log_data["custom_field"] == "value"

        # Clean up
        logger.removeHandler(handler)


class TestSetupLogging:
    """Tests for setup_logging function."""

    @patch("mikrom.utils.logger.settings")
    def test_setup_logging_json_format(self, mock_settings):
        """Test setup_logging configures JSON format."""
        mock_settings.LOG_FORMAT = "json"
        mock_settings.LOG_LEVEL = "INFO"

        setup_logging()

        # Get root logger
        root_logger = logging.getLogger()

        # Verify handler is configured
        assert len(root_logger.handlers) > 0

        # Find the StreamHandler
        stream_handler = None
        for handler in root_logger.handlers:
            if isinstance(handler, logging.StreamHandler):
                stream_handler = handler
                break

        assert stream_handler is not None
        assert isinstance(stream_handler.formatter, CustomJsonFormatter)

    @patch("mikrom.utils.logger.settings")
    def test_setup_logging_text_format(self, mock_settings):
        """Test setup_logging configures text format."""
        mock_settings.LOG_FORMAT = "text"
        mock_settings.LOG_LEVEL = "INFO"

        setup_logging()

        root_logger = logging.getLogger()

        # Find the StreamHandler
        stream_handler = None
        for handler in root_logger.handlers:
            if isinstance(handler, logging.StreamHandler):
                stream_handler = handler
                break

        assert stream_handler is not None
        assert not isinstance(stream_handler.formatter, CustomJsonFormatter)

    @patch("mikrom.utils.logger.settings")
    def test_setup_logging_sets_log_level(self, mock_settings):
        """Test setup_logging sets the correct log level."""
        mock_settings.LOG_FORMAT = "json"
        mock_settings.LOG_LEVEL = "DEBUG"

        setup_logging()

        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG

        # Test with different level
        mock_settings.LOG_LEVEL = "WARNING"
        setup_logging()
        assert root_logger.level == logging.WARNING


class TestLoggingIntegration:
    """Integration tests for the logging system."""

    def setup_method(self):
        """Set up test fixtures."""
        clear_context()

    def teardown_method(self):
        """Clean up after tests."""
        clear_context()

    def test_end_to_end_logging_flow(self):
        """Test complete logging flow from logger to output."""
        from mikrom.utils.logger import ContextInjectionFilter

        # Set up logger with JSON formatter
        logger = get_logger("test.integration")
        logger.addFilter(ContextInjectionFilter())  # Add filter for context injection
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(CustomJsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        # Set context
        set_context(vm_id="vm-integration", user_id=888)

        # Create span for trace context
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("integration-test"):
            # Log a message with extra fields
            logger.info(
                "Integration test message",
                extra={"test_field": "test_value"},
            )

        # Get output
        output = stream.getvalue().strip()
        log_data = json.loads(output)

        # Verify all context is present
        assert log_data["message"] == "Integration test message"
        assert log_data["vm_id"] == "vm-integration"
        assert log_data["user_id"] == 888
        assert log_data["test_field"] == "test_value"
        assert "trace_id" in log_data
        assert "span_id" in log_data
        assert "timestamp" in log_data

        # Clean up
        logger.removeHandler(handler)

    def test_logging_without_context(self):
        """Test that logging works even without context set."""
        logger = get_logger("test.no_context")
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(CustomJsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        # Log without setting any context
        logger.info("Message without context")

        output = stream.getvalue().strip()
        log_data = json.loads(output)

        # Should still have basic fields
        assert log_data["message"] == "Message without context"
        assert log_data["level"] == "INFO"
        assert log_data["logger"] == "test.no_context"

        # Context fields should be null or absent
        assert log_data.get("vm_id") is None
        assert log_data.get("user_id") is None

        # Clean up
        logger.removeHandler(handler)
