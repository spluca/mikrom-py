"""Context management for structured logging and tracing.

This module provides thread-safe context variables for propagating
request context throughout the application, including across async
operations and background tasks.
"""

import contextvars
from contextlib import contextmanager
from typing import Optional, Any, Dict
from opentelemetry import trace

# Context variables for request/operation tracking
request_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "request_id", default=None
)
user_id_var: contextvars.ContextVar[Optional[int]] = contextvars.ContextVar(
    "user_id", default=None
)
user_name_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "user_name", default=None
)
vm_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "vm_id", default=None
)
action_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "action", default=None
)


def set_context(
    request_id: Optional[str] = None,
    user_id: Optional[int] = None,
    user_name: Optional[str] = None,
    vm_id: Optional[str] = None,
    action: Optional[str] = None,
) -> None:
    """Set context variables.

    Args:
        request_id: Unique request identifier
        user_id: User database ID
        user_name: Username
        vm_id: VM identifier (srv-xxxxxxxx)
        action: Operation being performed (e.g., 'vm.create', 'vm.delete')
    """
    if request_id is not None:
        request_id_var.set(request_id)
    if user_id is not None:
        user_id_var.set(user_id)
    if user_name is not None:
        user_name_var.set(user_name)
    if vm_id is not None:
        vm_id_var.set(vm_id)
    if action is not None:
        action_var.set(action)


def get_context() -> Dict[str, Any]:
    """Get all current context values as a dictionary.

    Returns:
        Dictionary with all non-None context values
    """
    context = {}

    request_id = request_id_var.get()
    if request_id:
        context["request_id"] = request_id

    user_id = user_id_var.get()
    if user_id:
        context["user_id"] = user_id

    user_name = user_name_var.get()
    if user_name:
        context["user_name"] = user_name

    vm_id = vm_id_var.get()
    if vm_id:
        context["vm_id"] = vm_id

    action = action_var.get()
    if action:
        context["action"] = action

    return context


def get_request_id() -> Optional[str]:
    """Get current request ID."""
    return request_id_var.get()


def get_user_id() -> Optional[int]:
    """Get current user ID."""
    return user_id_var.get()


def get_user_name() -> Optional[str]:
    """Get current username."""
    return user_name_var.get()


def get_vm_id() -> Optional[str]:
    """Get current VM ID."""
    return vm_id_var.get()


def get_action() -> Optional[str]:
    """Get current action."""
    return action_var.get()


def clear_context() -> None:
    """Clear all context variables."""
    request_id_var.set(None)
    user_id_var.set(None)
    user_name_var.set(None)
    vm_id_var.set(None)
    action_var.set(None)


@contextmanager
def operation_context(
    action: str,
    request_id: Optional[str] = None,
    user_id: Optional[int] = None,
    user_name: Optional[str] = None,
    vm_id: Optional[str] = None,
):
    """Context manager for setting operation context with automatic cleanup.

    This also sets the action as a span attribute if there's an active span.

    Args:
        action: Operation being performed (e.g., 'vm.create')
        request_id: Optional request ID
        user_id: Optional user ID
        user_name: Optional username
        vm_id: Optional VM ID

    Example:
        with operation_context("vm.create", vm_id="srv-abc123"):
            logger.info("Creating VM")
            # ... operation code ...
    """
    # Save current context
    old_context = get_context()

    try:
        # Set new context
        set_context(
            request_id=request_id,
            user_id=user_id,
            user_name=user_name,
            vm_id=vm_id,
            action=action,
        )

        # Also set on current span if available
        span = trace.get_current_span()
        if span.is_recording():
            span.set_attribute("action", action)
            if vm_id:
                span.set_attribute("vm.id", vm_id)
            if user_id:
                span.set_attribute("user.id", user_id)
            if user_name:
                span.set_attribute("user.name", user_name)

        yield

    finally:
        # Restore old context
        clear_context()
        for key, value in old_context.items():
            if key == "request_id":
                request_id_var.set(value)
            elif key == "user_id":
                user_id_var.set(value)
            elif key == "user_name":
                user_name_var.set(value)
            elif key == "vm_id":
                vm_id_var.set(value)
            elif key == "action":
                action_var.set(value)


def get_trace_context() -> Dict[str, str]:
    """Get current OpenTelemetry trace context.

    Returns:
        Dictionary with trace_id and span_id (if available)
    """
    context = {}

    span = trace.get_current_span()
    if span.is_recording():
        span_context = span.get_span_context()
        if span_context.is_valid:
            context["trace_id"] = format(span_context.trace_id, "032x")
            context["span_id"] = format(span_context.span_id, "016x")

    return context
