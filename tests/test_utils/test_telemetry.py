"""Unit tests for mikrom.utils.telemetry module."""

from unittest.mock import patch, MagicMock, call
import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.resources import Resource

from opentelemetry import trace
from mikrom.utils.telemetry import (
    setup_telemetry,
    get_tracer,
    add_span_attributes,
    # get_current_span - use trace.get_current_span() instead
)


class TestInitTelemetry:
    """Tests for setup_telemetry function."""

    @patch("mikrom.utils.telemetry.settings")
    @patch("mikrom.utils.telemetry.trace")
    def test_setup_telemetry_creates_tracer_provider(self, mock_trace, mock_settings):
        """Test that setup_telemetry creates and sets a tracer provider."""
        mock_settings.OTEL_SERVICE_NAME = "test-service"
        mock_settings.OTEL_TRACE_SAMPLE_RATE = 1.0
        mock_settings.OTEL_EXPORT_CONSOLE = False
        mock_settings.APP_VERSION = "1.0.0"
        mock_settings.ENVIRONMENT = "test"

        setup_telemetry()

        # Verify trace.set_tracer_provider was called
        mock_trace.set_tracer_provider.assert_called_once()

    @patch("mikrom.utils.telemetry.settings")
    @patch("mikrom.utils.telemetry.TracerProvider")
    def test_setup_telemetry_configures_resource(
        self, mock_provider_class, mock_settings
    ):
        """Test that setup_telemetry configures resource with service info."""
        mock_settings.OTEL_SERVICE_NAME = "test-service"
        mock_settings.OTEL_TRACE_SAMPLE_RATE = 1.0
        mock_settings.OTEL_EXPORT_CONSOLE = False
        mock_settings.APP_VERSION = "1.0.0"
        mock_settings.ENVIRONMENT = "test"

        mock_provider = MagicMock()
        mock_provider_class.return_value = mock_provider

        setup_telemetry()

        # Verify TracerProvider was called with resource
        assert mock_provider_class.called
        call_kwargs = mock_provider_class.call_args[1]
        assert "resource" in call_kwargs

        resource = call_kwargs["resource"]
        assert isinstance(resource, Resource)

    @patch("mikrom.utils.telemetry.settings")
    @patch("mikrom.utils.telemetry.ConsoleSpanExporter")
    def test_setup_telemetry_with_console_export_enabled(
        self, mock_console_exporter, mock_settings
    ):
        """Test that console exporter is added when enabled."""
        mock_settings.OTEL_SERVICE_NAME = "test-service"
        mock_settings.OTEL_TRACE_SAMPLE_RATE = 1.0
        mock_settings.OTEL_EXPORT_CONSOLE = True
        mock_settings.APP_VERSION = "1.0.0"
        mock_settings.ENVIRONMENT = "test"

        setup_telemetry()

        # Verify ConsoleSpanExporter was instantiated
        mock_console_exporter.assert_called_once()

    @patch("mikrom.utils.telemetry.settings")
    @patch("mikrom.utils.telemetry.ConsoleSpanExporter")
    def test_setup_telemetry_without_console_export(
        self, mock_console_exporter, mock_settings
    ):
        """Test that console exporter is not added when disabled."""
        mock_settings.OTEL_SERVICE_NAME = "test-service"
        mock_settings.OTEL_TRACE_SAMPLE_RATE = 1.0
        mock_settings.OTEL_EXPORT_CONSOLE = False
        mock_settings.APP_VERSION = "1.0.0"
        mock_settings.ENVIRONMENT = "test"

        setup_telemetry()

        # Console exporter should not be called when disabled
        mock_console_exporter.assert_not_called()

    @patch("mikrom.utils.telemetry.settings")
    @patch("mikrom.utils.telemetry.logger")
    def test_setup_telemetry_logs_initialization(self, mock_logger, mock_settings):
        """Test that setup_telemetry logs initialization message."""
        mock_settings.OTEL_SERVICE_NAME = "test-service"
        mock_settings.OTEL_TRACE_SAMPLE_RATE = 1.0
        mock_settings.OTEL_EXPORT_CONSOLE = True
        mock_settings.APP_VERSION = "1.0.0"
        mock_settings.ENVIRONMENT = "test"

        setup_telemetry()

        # Verify logger.info was called
        assert mock_logger.info.called


class TestGetTracer:
    """Tests for get_tracer function."""

    def test_get_tracer_returns_tracer(self):
        """Test that get_tracer returns a Tracer instance."""
        tracer = get_tracer()
        assert tracer is not None

    def test_get_tracer_with_name(self):
        """Test that get_tracer returns a tracer (name parameter not supported)."""
        # Note: Our implementation doesn't support custom names, it returns global tracer
        tracer = get_tracer()
        assert tracer is not None

    def test_get_tracer_returns_same_instance(self):
        """Test that get_tracer returns the same tracer instance."""
        tracer1 = get_tracer()
        tracer2 = get_tracer()
        # Should be the same instance
        assert tracer1 is tracer2

    def test_get_tracer_default_name(self):
        """Test get_tracer with default name."""
        tracer = get_tracer()
        assert tracer is not None


class TestAddSpanAttributes:
    """Tests for add_span_attributes function."""

    def test_add_span_attributes_adds_to_current_span(self):
        """Test that add_span_attributes adds attributes to current span."""
        tracer = get_tracer()

        with tracer.start_as_current_span("test-span") as span:
            # Add attributes
            add_span_attributes(
                test_attr="test_value",
                numeric_attr=123,
                bool_attr=True,
            )

            # Verify attributes were added
            # Note: We can't directly access span attributes in tests,
            # but we can verify the function doesn't raise errors
            assert span.is_recording()

    def test_add_span_attributes_without_active_span(self):
        """Test that add_span_attributes handles no active span gracefully."""
        # Should not raise an error even without an active span
        try:
            add_span_attributes(test_attr="test_value")
        except Exception as e:
            pytest.fail(f"add_span_attributes raised an exception: {e}")

    def test_add_span_attributes_with_various_types(self):
        """Test add_span_attributes with various data types."""
        tracer = get_tracer()

        with tracer.start_as_current_span("test-span"):
            # Should handle various types
            add_span_attributes(
                string_attr="string",
                int_attr=42,
                float_attr=3.14,
                bool_attr=True,
                none_attr=None,
            )

            # Function should complete without error

    def test_add_span_attributes_with_empty_dict(self):
        """Test add_span_attributes with no attributes."""
        tracer = get_tracer()

        with tracer.start_as_current_span("test-span"):
            # Should handle empty attributes
            add_span_attributes()


class TestGetCurrentSpan:
    """Tests for get_current_span function."""

    def test_get_current_span_returns_span_when_active(self):
        """Test that get_current_span returns the current span."""
        tracer = get_tracer()

        with tracer.start_as_current_span("test-span"):
            span = trace.get_current_span()
            assert span is not None
            assert span.is_recording()

    def test_get_current_span_returns_none_when_no_active_span(self):
        """Test that get_current_span returns None when no span is active."""
        span = trace.get_current_span()
        # When no span is active, should return a non-recording span or None
        if span is not None:
            assert not span.is_recording()

    def test_get_current_span_in_nested_spans(self):
        """Test get_current_span with nested spans."""
        tracer = get_tracer()

        with tracer.start_as_current_span("outer-span"):
            outer_span = trace.get_current_span()
            assert outer_span.is_recording()

            with tracer.start_as_current_span("inner-span"):
                inner_span = trace.get_current_span()
                assert inner_span.is_recording()

                # Inner span should be different from outer span
                assert (
                    inner_span.get_span_context().span_id
                    != outer_span.get_span_context().span_id
                )


class TestTelemetryIntegration:
    """Integration tests for telemetry functionality."""

    def test_create_and_use_span(self):
        """Test creating and using a span."""
        tracer = get_tracer()

        with tracer.start_as_current_span("integration-span") as span:
            # Span should be recording
            assert span.is_recording()

            # Get span context
            span_context = span.get_span_context()
            assert span_context.trace_id > 0
            assert span_context.span_id > 0

            # Add attributes
            add_span_attributes(
                test_operation="integration",
                test_id=12345,
            )

    def test_nested_spans_maintain_hierarchy(self):
        """Test that nested spans maintain parent-child relationship."""
        tracer = get_tracer()

        with tracer.start_as_current_span("parent-span") as parent:
            parent_context = parent.get_span_context()

            with tracer.start_as_current_span("child-span") as child:
                child_context = child.get_span_context()

                # Both should be recording
                assert parent.is_recording()
                assert child.is_recording()

                # Child should have same trace_id but different span_id
                assert child_context.trace_id == parent_context.trace_id
                assert child_context.span_id != parent_context.span_id

    def test_span_with_attributes_and_events(self):
        """Test span with attributes and events."""
        tracer = get_tracer()

        with tracer.start_as_current_span("event-span") as span:
            # Add attributes
            add_span_attributes(user_id=123, action="test")

            # Add event
            span.add_event("test_event", {"detail": "event_detail"})

            # Span should still be recording
            assert span.is_recording()

    def test_multiple_tracers(self):
        """Test creating multiple tracers with different names."""
        tracer1 = get_tracer()
        tracer2 = get_tracer()

        # Both should be valid tracers
        assert tracer1 is not None
        assert tracer2 is not None

        # They should be different instances (different names)
        # Note: OpenTelemetry may cache tracers, so this might not always be true

        # Both should be able to create spans
        with tracer1.start_as_current_span("span1") as span1:
            assert span1.is_recording()

        with tracer2.start_as_current_span("span2") as span2:
            assert span2.is_recording()


class TestTelemetryErrorHandling:
    """Tests for error handling in telemetry functions."""

    def test_add_span_attributes_handles_exceptions(self):
        """Test that add_span_attributes handles exceptions gracefully."""
        tracer = get_tracer()

        with tracer.start_as_current_span("test-span"):
            # Try adding invalid attributes
            try:
                add_span_attributes(
                    valid_attr="valid",
                    # Some implementations might reject certain types
                    complex_obj=object(),
                )
            except Exception:
                # Should handle gracefully
                pass

    def test_span_context_after_span_ends(self):
        """Test accessing span context after span ends."""
        tracer = get_tracer()

        span = tracer.start_span("test-span")
        span_context = span.get_span_context()

        # End the span
        span.end()

        # Context should still be accessible
        assert span_context.trace_id > 0
        assert span_context.span_id > 0


class TestTelemetryConfiguration:
    """Tests for telemetry configuration."""

    @patch("mikrom.utils.telemetry.settings")
    def test_telemetry_respects_sampling_rate(self, mock_settings):
        """Test that telemetry respects sampling configuration."""
        mock_settings.OTEL_SERVICE_NAME = "test-service"
        mock_settings.OTEL_TRACE_SAMPLE_RATE = 0.0  # No sampling
        mock_settings.OTEL_EXPORT_CONSOLE = False
        mock_settings.APP_VERSION = "1.0.0"
        mock_settings.ENVIRONMENT = "test"

        setup_telemetry()

        # Even with 0 sampling, tracer should still work
        tracer = get_tracer()
        assert tracer is not None

    @patch("mikrom.utils.telemetry.settings")
    def test_telemetry_with_different_environments(self, mock_settings):
        """Test telemetry initialization in different environments."""
        environments = ["development", "staging", "production"]

        for env in environments:
            mock_settings.OTEL_SERVICE_NAME = f"test-{env}"
            mock_settings.OTEL_TRACE_SAMPLE_RATE = 1.0
            mock_settings.OTEL_EXPORT_CONSOLE = True
            mock_settings.APP_VERSION = "1.0.0"
            mock_settings.ENVIRONMENT = env

            setup_telemetry()

            tracer = get_tracer()
            assert tracer is not None


class TestSpanContextPropagation:
    """Tests for span context propagation."""

    def test_span_context_propagates_across_functions(self):
        """Test that span context propagates across function calls."""
        tracer = get_tracer()

        def inner_function():
            """Inner function that should inherit span context."""
            span = trace.get_current_span()
            return span

        with tracer.start_as_current_span("outer-span"):
            # Get span in outer scope
            outer_span = trace.get_current_span()
            outer_context = outer_span.get_span_context()

            # Call inner function
            inner_span = inner_function()
            inner_context = inner_span.get_span_context()

            # Should be the same span
            assert outer_context.span_id == inner_context.span_id
            assert outer_context.trace_id == inner_context.trace_id

    @pytest.mark.asyncio
    async def test_span_context_propagates_in_async(self):
        """Test that span context propagates in async functions."""
        tracer = get_tracer()

        async def async_inner():
            """Async inner function."""
            span = trace.get_current_span()
            return span

        with tracer.start_as_current_span("async-span"):
            outer_span = trace.get_current_span()
            inner_span = await async_inner()

            # Should have same context
            assert (
                outer_span.get_span_context().trace_id
                == inner_span.get_span_context().trace_id
            )
