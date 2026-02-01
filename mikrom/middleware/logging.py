"""Enhanced logging middleware with context and tracing."""

import time
import logging
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from mikrom.utils.context import set_context, clear_context
from mikrom.utils.telemetry import get_tracer, add_span_attributes

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log HTTP requests/responses with context and tracing."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process the request with logging and context injection."""
        # Generate or get request ID
        request_id = request.headers.get("X-Request-ID", f"{time.time()}")

        # Initialize request context
        set_context(request_id=request_id, action="http.request")

        # Try to extract user from token (if authenticated)
        user_id = None
        user_name = None
        if hasattr(request.state, "user"):
            user = request.state.user
            user_id = user.id if hasattr(user, "id") else None
            user_name = user.username if hasattr(user, "username") else None
            if user_id:
                set_context(user_id=user_id, user_name=user_name)

        # Get tracer and create span
        tracer = get_tracer()

        with tracer.start_as_current_span(
            f"{request.method} {request.url.path}"
        ) as span:
            # Add span attributes
            add_span_attributes(
                **{
                    "http.method": request.method,
                    "http.url": str(request.url),
                    "http.path": request.url.path,
                    "http.client_ip": request.client.host if request.client else None,
                    "http.user_agent": request.headers.get("user-agent"),
                }
            )

            if user_id:
                add_span_attributes(**{"user.id": user_id, "user.name": user_name})

            # Log request start
            logger.info(
                "Request started",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "query_params": str(request.query_params)
                    if request.query_params
                    else None,
                    "client_ip": request.client.host if request.client else None,
                    "user_agent": request.headers.get("user-agent"),
                },
            )

            # Process request
            start_time = time.time()

            try:
                response = await call_next(request)
                duration_ms = (time.time() - start_time) * 1000

                # Add response attributes to span
                add_span_attributes(
                    **{
                        "http.status_code": response.status_code,
                        "http.duration_ms": round(duration_ms, 2),
                    }
                )

                # Add custom headers
                response.headers["X-Request-ID"] = request_id
                response.headers["X-Process-Time"] = f"{duration_ms:.2f}ms"

                # Log response
                logger.info(
                    "Request completed",
                    extra={
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": response.status_code,
                        "duration_ms": round(duration_ms, 2),
                    },
                )

                return response

            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000

                # Record exception in span
                span.record_exception(e)

                # Log error
                logger.error(
                    "Request failed",
                    extra={
                        "method": request.method,
                        "path": request.url.path,
                        "duration_ms": round(duration_ms, 2),
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                )

                raise

            finally:
                # Clear context after request
                clear_context()
