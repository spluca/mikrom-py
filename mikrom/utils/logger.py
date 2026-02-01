"""Enhanced logging with structured JSON output and context injection.

This module provides JSON-formatted logging with automatic injection of
request context (request_id, user_id, vm_id) and OpenTelemetry trace context
(trace_id, span_id).
"""

import logging
import sys
import time
from contextlib import contextmanager
from functools import wraps
from typing import Optional, Callable, Any

from pythonjsonlogger import jsonlogger

from mikrom.config import settings
from mikrom.utils.context import get_context, get_trace_context


class ContextInjectionFilter(logging.Filter):
    """Logging filter that injects context variables into log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Add context to log record.

        Args:
            record: Log record to enhance

        Returns:
            True (always include record)
        """
        # Add request context
        context = get_context()
        for key, value in context.items():
            setattr(record, key, value)

        # Add trace context
        trace_context = get_trace_context()
        for key, value in trace_context.items():
            setattr(record, key, value)

        return True


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with additional fields."""

    def add_fields(
        self, log_record: dict, record: logging.LogRecord, message_dict: dict
    ) -> None:
        """Add custom fields to log record.

        Args:
            log_record: Dictionary to be logged as JSON
            record: Original log record
            message_dict: Message dictionary from logger call
        """
        super().add_fields(log_record, record, message_dict)

        # Ensure timestamp is ISO format
        if "timestamp" not in log_record:
            log_record["timestamp"] = record.created

        # Add standard fields
        log_record["level"] = record.levelname
        log_record["logger"] = record.name

        # Add context fields if present
        for field in [
            "request_id",
            "user_id",
            "user_name",
            "vm_id",
            "action",
            "trace_id",
            "span_id",
        ]:
            if hasattr(record, field):
                value = getattr(record, field)
                if value is not None:
                    log_record[field] = value


class ColoredConsoleFormatter(logging.Formatter):
    """Colored console formatter for non-JSON output."""

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors."""
        if record.levelname in self.COLORS:
            record.levelname = (
                f"{self.COLORS[record.levelname]}{record.levelname}{self.RESET}"
            )
        return super().format(record)


def setup_logging() -> None:
    """Configure application logging with JSON formatting."""
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)

    # Add context injection filter
    console_handler.addFilter(ContextInjectionFilter())

    # Choose formatter based on configuration
    if settings.LOG_FORMAT == "json":
        formatter = CustomJsonFormatter(
            "%(timestamp)s %(level)s %(logger)s %(message)s",
            timestamp=True,
        )
    else:
        # Console format with colors (for development)
        formatter = ColoredConsoleFormatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    console_handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))
    root_logger.handlers.clear()  # Remove any existing handlers
    root_logger.addHandler(console_handler)

    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("opentelemetry").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the specified name.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


@contextmanager
def log_timer(operation_name: str, logger: Optional[logging.Logger] = None):
    """Context manager to log operation duration.

    Args:
        operation_name: Name of the operation being timed
        logger: Optional logger to use (creates one if not provided)

    Example:
        with log_timer("vm_creation"):
            create_vm()
        # Logs: {"message": "Operation completed", "operation": "vm_creation", "duration_ms": 1234}
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    start_time = time.time()

    try:
        yield
    finally:
        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            f"Operation completed: {operation_name}",
            extra={"operation": operation_name, "duration_ms": round(duration_ms, 2)},
        )


def log_duration(operation_name: Optional[str] = None):
    """Decorator to log function execution duration.

    Args:
        operation_name: Optional custom operation name. Uses function name if not provided.

    Example:
        @log_duration("create_vm_operation")
        async def create_vm(vm_id: str):
            # ... operation code ...
    """

    def decorator(func: Callable) -> Callable:
        name = operation_name or func.__name__
        func_logger = logging.getLogger(func.__module__)

        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                func_logger.info(
                    f"Function completed: {name}",
                    extra={"function": name, "duration_ms": round(duration_ms, 2)},
                )
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                func_logger.error(
                    f"Function failed: {name}",
                    extra={
                        "function": name,
                        "duration_ms": round(duration_ms, 2),
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                )
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                func_logger.info(
                    f"Function completed: {name}",
                    extra={"function": name, "duration_ms": round(duration_ms, 2)},
                )
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                func_logger.error(
                    f"Function failed: {name}",
                    extra={
                        "function": name,
                        "duration_ms": round(duration_ms, 2),
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                )
                raise

        # Return appropriate wrapper based on function type
        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator
