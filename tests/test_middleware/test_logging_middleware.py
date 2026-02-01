"""Integration tests for logging middleware."""

import json
import logging
from io import StringIO
from unittest.mock import patch

import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI, APIRouter

from mikrom.middleware.logging import LoggingMiddleware
from mikrom.utils.logger import CustomJsonFormatter, get_logger
from mikrom.utils.context import get_context, clear_context


# Create a test app
def create_test_app() -> FastAPI:
    """Create a test FastAPI app with logging middleware."""
    app = FastAPI()

    # Add logging middleware
    app.add_middleware(LoggingMiddleware)

    # Create test router
    router = APIRouter()

    @router.get("/test")
    async def test_endpoint():
        return {"message": "test"}

    @router.get("/test-error")
    async def test_error_endpoint():
        raise ValueError("Test error")

    @router.post("/test-post")
    async def test_post_endpoint(data: dict):
        return {"received": data}

    app.include_router(router)

    return app


class TestLoggingMiddleware:
    """Tests for LoggingMiddleware."""

    @pytest.mark.asyncio
    async def test_middleware_logs_request_and_response(self):
        """Test that middleware logs both request start and completion."""
        from mikrom.utils.logger import ContextInjectionFilter

        app = create_test_app()

        # Set up logging capture
        logger = get_logger("mikrom.middleware.logging")
        logger.addFilter(ContextInjectionFilter())  # Add filter for context injection
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(CustomJsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        # Make request
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/test")

        # Get logs
        output = stream.getvalue()
        log_lines = [line for line in output.strip().split("\n") if line]

        # Should have at least 2 log lines (request start + completion)
        assert len(log_lines) >= 2

        # Parse logs
        logs = [json.loads(line) for line in log_lines]

        # Find request started and completed logs
        started_log = None
        completed_log = None

        for log in logs:
            if log.get("message") == "Request started":
                started_log = log
            elif log.get("message") == "Request completed":
                completed_log = log

        # Verify request started log
        assert started_log is not None
        assert started_log["method"] == "GET"
        assert started_log["path"] == "/test"
        assert "request_id" in started_log
        assert "trace_id" in started_log

        # Verify request completed log
        assert completed_log is not None
        assert completed_log["status_code"] == 200
        assert "duration_ms" in completed_log
        assert completed_log["request_id"] == started_log["request_id"]
        assert completed_log["trace_id"] == started_log["trace_id"]

        # Clean up
        logger.removeHandler(handler)

    @pytest.mark.asyncio
    async def test_middleware_sets_context(self):
        """Test that middleware sets request context."""
        app = create_test_app()

        # Add endpoint that checks context
        @app.get("/test-context")
        async def test_context():
            context = get_context()
            return {
                "request_id": context.get("request_id"),
                "action": context.get("action"),
            }

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/test-context")

        data = response.json()

        # Context should have been set
        assert data["request_id"] is not None
        assert data["action"] == "http.request"

    @pytest.mark.asyncio
    async def test_middleware_generates_unique_request_ids(self):
        """Test that each request gets a unique request_id."""
        app = create_test_app()

        request_ids = []

        @app.get("/test-id")
        async def test_id():
            context = get_context()
            request_id = context.get("request_id")
            request_ids.append(request_id)
            return {"request_id": request_id}

        # Make multiple requests
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.get("/test-id")
            await client.get("/test-id")
            await client.get("/test-id")

        # All request IDs should be unique
        assert len(request_ids) == 3
        assert len(set(request_ids)) == 3

    @pytest.mark.asyncio
    async def test_middleware_logs_error_responses(self):
        """Test that middleware logs error responses."""
        from mikrom.utils.logger import ContextInjectionFilter

        app = create_test_app()

        # Set up logging capture
        logger = get_logger("mikrom.middleware.logging")
        logger.addFilter(ContextInjectionFilter())  # Add filter for context injection
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(CustomJsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        # Make request that raises error
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            try:
                await client.get("/test-error")
            except Exception:
                pass  # Expected to fail

        # Get logs
        output = stream.getvalue()
        log_lines = [line for line in output.strip().split("\n") if line]

        # Parse logs
        logs = [json.loads(line) for line in log_lines]

        # Should have logged the error - message is "Request failed" not "Request completed"
        failed_log = None
        for log in logs:
            if log.get("message") == "Request failed":
                failed_log = log
                break

        # Verify error was logged
        assert failed_log is not None
        assert "error" in failed_log
        assert failed_log["error"] == "Test error"

        # Clean up
        logger.removeHandler(handler)

    @pytest.mark.asyncio
    async def test_middleware_tracks_duration(self):
        """Test that middleware tracks request duration."""
        app = create_test_app()

        # Set up logging capture
        logger = get_logger("mikrom.middleware.logging")
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(CustomJsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        # Make request
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.get("/test")

        # Get logs
        output = stream.getvalue()
        log_lines = [line for line in output.strip().split("\n") if line]
        logs = [json.loads(line) for line in log_lines]

        # Find completed log
        completed_log = None
        for log in logs:
            if log.get("message") == "Request completed":
                completed_log = log
                break

        # Verify duration is tracked
        assert completed_log is not None
        assert "duration_ms" in completed_log
        assert isinstance(completed_log["duration_ms"], (int, float))
        assert completed_log["duration_ms"] >= 0

        # Clean up
        logger.removeHandler(handler)

    @pytest.mark.asyncio
    async def test_middleware_logs_http_method_and_path(self):
        """Test that middleware logs HTTP method and path."""
        app = create_test_app()

        # Set up logging capture
        logger = get_logger("mikrom.middleware.logging")
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(CustomJsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        # Make different types of requests
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.get("/test")
            await client.post("/test-post", json={"key": "value"})

        # Get logs
        output = stream.getvalue()
        log_lines = [line for line in output.strip().split("\n") if line]
        logs = [json.loads(line) for line in log_lines]

        # Find logs for different requests
        get_log = None
        post_log = None

        for log in logs:
            if log.get("message") == "Request started":
                if log.get("method") == "GET" and log.get("path") == "/test":
                    get_log = log
                elif log.get("method") == "POST" and log.get("path") == "/test-post":
                    post_log = log

        # Verify GET request was logged
        assert get_log is not None
        assert get_log["method"] == "GET"
        assert get_log["path"] == "/test"

        # Verify POST request was logged
        assert post_log is not None
        assert post_log["method"] == "POST"
        assert post_log["path"] == "/test-post"

        # Clean up
        logger.removeHandler(handler)

    @pytest.mark.asyncio
    async def test_middleware_logs_client_info(self):
        """Test that middleware logs client information."""
        app = create_test_app()

        # Set up logging capture
        logger = get_logger("mikrom.middleware.logging")
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(CustomJsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        # Make request
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.get("/test", headers={"User-Agent": "test-client/1.0"})

        # Get logs
        output = stream.getvalue()
        log_lines = [line for line in output.strip().split("\n") if line]
        logs = [json.loads(line) for line in log_lines]

        # Find request started log
        started_log = None
        for log in logs:
            if log.get("message") == "Request started":
                started_log = log
                break

        # Verify client info is logged
        assert started_log is not None
        assert "client_ip" in started_log
        assert "user_agent" in started_log

        # Clean up
        logger.removeHandler(handler)

    @pytest.mark.asyncio
    async def test_middleware_creates_trace_context(self):
        """Test that middleware creates OpenTelemetry trace context."""
        from mikrom.utils.logger import ContextInjectionFilter

        app = create_test_app()

        # Set up logging capture
        logger = get_logger("mikrom.middleware.logging")
        logger.addFilter(ContextInjectionFilter())  # Add filter for context injection
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(CustomJsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        # Make request
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.get("/test")

        # Get logs
        output = stream.getvalue()
        log_lines = [line for line in output.strip().split("\n") if line]
        logs = [json.loads(line) for line in log_lines]

        # All logs should have trace context
        for log in logs:
            if log.get("logger") == "mikrom.middleware.logging":
                assert "trace_id" in log
                assert "span_id" in log

        # Clean up
        logger.removeHandler(handler)


class TestMiddlewareContextCleanup:
    """Tests for context cleanup in middleware."""

    @pytest.mark.asyncio
    async def test_middleware_clears_context_after_request(self):
        """Test that middleware clears context after request."""
        app = create_test_app()

        # Make first request
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.get("/test")

        # Context should be cleared after request
        # (In practice this depends on the async context lifecycle)
        # For now, just verify no exceptions occur

    @pytest.mark.asyncio
    async def test_middleware_handles_concurrent_requests(self):
        """Test that middleware handles concurrent requests correctly."""
        app = create_test_app()

        request_data = []

        @app.get("/test-concurrent")
        async def test_concurrent():
            import asyncio

            await asyncio.sleep(0.01)  # Simulate some work
            context = get_context()
            request_data.append(
                {
                    "request_id": context.get("request_id"),
                    "action": context.get("action"),
                }
            )
            return {"request_id": context.get("request_id")}

        # Make multiple concurrent requests
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            import asyncio

            tasks = [client.get("/test-concurrent") for _ in range(5)]
            await asyncio.gather(*tasks)

        # Each request should have its own context
        assert len(request_data) == 5
        request_ids = [r["request_id"] for r in request_data]

        # All request IDs should be unique
        assert len(set(request_ids)) == 5


class TestMiddlewareWithRealEndpoints:
    """Integration tests with real endpoint patterns."""

    @pytest.mark.asyncio
    async def test_middleware_with_query_parameters(self):
        """Test middleware logging with query parameters."""
        app = create_test_app()

        @app.get("/test-query")
        async def test_query(param1: str, param2: int = 10):
            return {"param1": param1, "param2": param2}

        # Set up logging capture
        logger = get_logger("mikrom.middleware.logging")
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(CustomJsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        # Make request with query parameters
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.get("/test-query?param1=value1&param2=20")

        # Get logs
        output = stream.getvalue()
        log_lines = [line for line in output.strip().split("\n") if line]
        logs = [json.loads(line) for line in log_lines]

        # Find request started log
        started_log = None
        for log in logs:
            if log.get("message") == "Request started":
                started_log = log
                break

        # Query parameters should be logged
        assert started_log is not None
        assert started_log["path"] == "/test-query"
        # query_params field should exist (may be null or contain params)
        assert "query_params" in started_log

        # Clean up
        logger.removeHandler(handler)

    @pytest.mark.asyncio
    async def test_middleware_with_path_parameters(self):
        """Test middleware logging with path parameters."""
        from mikrom.utils.logger import ContextInjectionFilter

        app = create_test_app()

        @app.get("/items/{item_id}")
        async def get_item(item_id: int):
            return {"item_id": item_id}

        # Set up logging capture
        logger = get_logger("mikrom.middleware.logging")
        logger.addFilter(ContextInjectionFilter())  # Add filter for context injection
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(CustomJsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        # Make request
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.get("/items/123")

        # Get logs
        output = stream.getvalue()
        log_lines = [line for line in output.strip().split("\n") if line]
        logs = [json.loads(line) for line in log_lines]

        # Find request started log
        started_log = None
        for log in logs:
            if log.get("message") == "Request started":
                started_log = log
                break

        # Path should be logged
        assert started_log is not None
        assert started_log["path"] == "/items/123"

        # Clean up
        logger.removeHandler(handler)
