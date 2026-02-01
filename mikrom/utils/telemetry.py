"""OpenTelemetry tracing setup and utilities.

This module initializes OpenTelemetry for distributed tracing and provides
utilities for creating spans and instrumenting operations.
"""

import logging
from contextlib import contextmanager
from functools import wraps
from typing import Optional, Any, Callable

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, BatchSpanProcessor
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor

from mikrom.config import settings
from mikrom import __version__

logger = logging.getLogger(__name__)

# Global tracer instance
_tracer: Optional[trace.Tracer] = None


def setup_telemetry() -> None:
    """Initialize OpenTelemetry tracing.

    This should be called once at application startup, before
    any other operations that might create spans.
    """
    global _tracer

    # Create resource with service information
    resource = Resource(
        attributes={
            SERVICE_NAME: settings.OTEL_SERVICE_NAME,
            SERVICE_VERSION: __version__,
            "environment": settings.ENVIRONMENT,
        }
    )

    # Configure sampling rate
    sampler = TraceIdRatioBased(settings.OTEL_TRACE_SAMPLE_RATE)

    # Create tracer provider
    provider = TracerProvider(resource=resource, sampler=sampler)

    # Add console exporter if enabled
    if settings.OTEL_EXPORT_CONSOLE:
        console_exporter = ConsoleSpanExporter()
        provider.add_span_processor(BatchSpanProcessor(console_exporter))

    # Set as global tracer provider
    trace.set_tracer_provider(provider)

    # Get tracer for this service
    _tracer = trace.get_tracer(__name__, __version__)

    logger.info(
        "OpenTelemetry initialized",
        extra={
            "service_name": settings.OTEL_SERVICE_NAME,
            "sample_rate": settings.OTEL_TRACE_SAMPLE_RATE,
            "export_console": settings.OTEL_EXPORT_CONSOLE,
        },
    )


def instrument_app(app: Any) -> None:
    """Instrument FastAPI application with OpenTelemetry.

    Args:
        app: FastAPI application instance
    """
    try:
        FastAPIInstrumentor.instrument_app(app)
        logger.info("FastAPI instrumented with OpenTelemetry")
    except Exception as e:
        logger.warning(f"Failed to instrument FastAPI: {e}")


def instrument_sqlalchemy(engine: Any) -> None:
    """Instrument SQLAlchemy engine with OpenTelemetry.

    Args:
        engine: SQLAlchemy engine instance
    """
    try:
        SQLAlchemyInstrumentor().instrument(engine=engine)
        logger.info("SQLAlchemy instrumented with OpenTelemetry")
    except Exception as e:
        logger.warning(f"Failed to instrument SQLAlchemy: {e}")


def instrument_redis() -> None:
    """Instrument Redis client with OpenTelemetry."""
    try:
        RedisInstrumentor().instrument()
        logger.info("Redis instrumented with OpenTelemetry")
    except Exception as e:
        logger.warning(f"Failed to instrument Redis: {e}")


def get_tracer() -> trace.Tracer:
    """Get the global tracer instance.

    Returns:
        OpenTelemetry Tracer instance
    """
    global _tracer

    if _tracer is None:
        # If not initialized, create a no-op tracer
        logger.warning("Tracer not initialized, creating default tracer")
        _tracer = trace.get_tracer(__name__, __version__)

    return _tracer


@contextmanager
def trace_operation(
    name: str,
    attributes: Optional[dict] = None,
):
    """Context manager for creating a traced operation span.

    Args:
        name: Name of the operation (e.g., 'vm.create', 'db.query')
        attributes: Optional dictionary of span attributes

    Example:
        with trace_operation("vm.create", {"vm.id": "srv-abc123"}):
            # ... operation code ...
    """
    tracer = get_tracer()

    with tracer.start_as_current_span(name) as span:
        if attributes:
            for key, value in attributes.items():
                if value is not None:
                    span.set_attribute(key, value)

        try:
            yield span
        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            raise


def trace_function(name: Optional[str] = None):
    """Decorator for tracing function calls.

    Args:
        name: Optional custom span name. If not provided, uses function name.

    Example:
        @trace_function("custom.operation")
        async def my_operation(vm_id: str):
            # ... operation code ...
    """

    def decorator(func: Callable) -> Callable:
        span_name = name or f"{func.__module__}.{func.__name__}"

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            with trace_operation(span_name):
                return await func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            with trace_operation(span_name):
                return func(*args, **kwargs)

        # Return appropriate wrapper based on function type
        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def add_span_attributes(**attributes) -> None:
    """Add attributes to the current span.

    Args:
        **attributes: Key-value pairs to add as span attributes

    Example:
        add_span_attributes(vm_id="srv-abc123", user_id=1)
    """
    span = trace.get_current_span()
    if span.is_recording():
        for key, value in attributes.items():
            if value is not None:
                span.set_attribute(key, value)


def add_span_event(name: str, attributes: Optional[dict] = None) -> None:
    """Add an event to the current span.

    Args:
        name: Event name
        attributes: Optional event attributes

    Example:
        add_span_event("vm.ip_allocated", {"ip": "172.16.0.15"})
    """
    span = trace.get_current_span()
    if span.is_recording():
        span.add_event(name, attributes or {})
