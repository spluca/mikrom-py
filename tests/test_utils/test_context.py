"""Unit tests for mikrom.utils.context module."""

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from mikrom.utils.context import (
    set_context,
    get_context,
    clear_context,
)


class TestContextVariables:
    """Tests for context variable management."""

    def setup_method(self):
        """Set up test fixtures."""
        clear_context()

    def teardown_method(self):
        """Clean up after tests."""
        clear_context()

    def test_set_and_get_vm_id(self):
        """Test setting and getting vm_id context."""
        set_context(vm_id="vm-123")
        context = get_context()
        assert context["vm_id"] == "vm-123"

    def test_set_and_get_user_id(self):
        """Test setting and getting user_id context."""
        set_context(user_id=456)
        context = get_context()
        assert context["user_id"] == 456

    def test_set_and_get_user_name(self):
        """Test setting and getting user_name context."""
        set_context(user_name="testuser")
        context = get_context()
        assert context["user_name"] == "testuser"

    def test_set_and_get_request_id(self):
        """Test setting and getting request_id context."""
        set_context(request_id="req-789")
        context = get_context()
        assert context["request_id"] == "req-789"

    def test_set_and_get_action(self):
        """Test setting and getting action context."""
        set_context(action="test.action")
        context = get_context()
        assert context["action"] == "test.action"

    def test_set_multiple_context_values(self):
        """Test setting multiple context values at once."""
        set_context(
            vm_id="vm-multi",
            user_id=999,
            user_name="multiuser",
            request_id="req-multi",
            action="multi.action",
        )

        context = get_context()
        assert context["vm_id"] == "vm-multi"
        assert context["user_id"] == 999
        assert context["user_name"] == "multiuser"
        assert context["request_id"] == "req-multi"
        assert context["action"] == "multi.action"

    def test_get_context_returns_none_when_not_set(self):
        """Test that get_context returns empty dict when no values set."""
        context = get_context()
        # get_context() returns empty dict when no values are set
        assert context == {}
        assert context.get("vm_id") is None
        assert context.get("user_id") is None
        assert context.get("user_name") is None
        assert context.get("request_id") is None
        assert context.get("action") is None

    def test_clear_context_removes_all_values(self):
        """Test that clear_context removes all context values."""
        # Set all context values
        set_context(
            vm_id="vm-clear",
            user_id=111,
            user_name="clearuser",
            request_id="req-clear",
            action="clear.action",
        )

        # Verify they are set
        context = get_context()
        assert context["vm_id"] == "vm-clear"
        assert context["user_id"] == 111

        # Clear context
        clear_context()

        # Verify they are cleared
        context = get_context()
        assert context == {}
        assert context.get("vm_id") is None
        assert context.get("user_id") is None
        assert context.get("user_name") is None
        assert context.get("request_id") is None
        assert context.get("action") is None

    def test_update_context_values(self):
        """Test updating context values."""
        # Set initial values
        set_context(vm_id="vm-old", user_id=100)

        # Update with new values
        set_context(vm_id="vm-new", user_id=200)

        context = get_context()
        assert context["vm_id"] == "vm-new"
        assert context["user_id"] == 200

    def test_partial_context_update(self):
        """Test updating only some context values."""
        # Set initial values
        set_context(vm_id="vm-partial", user_id=300, action="initial.action")

        # Update only user_id
        set_context(user_id=400)

        context = get_context()
        assert context["vm_id"] == "vm-partial"  # Should remain unchanged
        assert context["user_id"] == 400  # Should be updated
        assert context["action"] == "initial.action"  # Should remain unchanged

    def test_set_context_with_none_values(self):
        """Test setting context with None values explicitly."""
        # Set initial values
        set_context(vm_id="vm-none", user_id=500)

        # Set some values to None (should not change them)
        # The implementation only sets values if they are not None
        set_context(vm_id=None)

        context = get_context()
        # vm_id should remain unchanged since set_context(vm_id=None) doesn't clear it
        assert context["vm_id"] == "vm-none"
        assert context["user_id"] == 500  # Should remain unchanged


class TestContextIsolation:
    """Tests for context isolation between threads and async tasks."""

    def setup_method(self):
        """Set up test fixtures."""
        clear_context()

    def teardown_method(self):
        """Clean up after tests."""
        clear_context()

    def test_context_isolated_between_threads(self):
        """Test that context is isolated between threads."""
        results = {}

        def thread_function(thread_id):
            """Function to run in separate thread."""
            clear_context()
            # Use thread_id + 1 to avoid 0 which is falsy and won't be included in get_context()
            set_context(vm_id=f"vm-thread-{thread_id}", user_id=thread_id + 1)
            # Simulate some work
            import time

            time.sleep(0.01)
            # Get context
            context = get_context()
            results[thread_id] = context

        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=thread_function, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify each thread had its own context
        for thread_id in range(5):
            assert results[thread_id]["vm_id"] == f"vm-thread-{thread_id}"
            assert results[thread_id]["user_id"] == thread_id + 1

    @pytest.mark.asyncio
    async def test_context_isolated_between_async_tasks(self):
        """Test that context is isolated between async tasks."""
        results = {}

        async def async_task(task_id):
            """Async function to run as task."""
            clear_context()
            # Use task_id + 1 to avoid 0 which is falsy and won't be included in get_context()
            set_context(vm_id=f"vm-task-{task_id}", user_id=task_id + 1)
            # Simulate some async work
            await asyncio.sleep(0.01)
            # Get context
            context = get_context()
            results[task_id] = context

        # Create multiple async tasks
        tasks = [async_task(i) for i in range(5)]
        await asyncio.gather(*tasks)

        # Verify each task had its own context
        for task_id in range(5):
            assert results[task_id]["vm_id"] == f"vm-task-{task_id}"
            assert results[task_id]["user_id"] == task_id + 1

    def test_context_with_thread_pool_executor(self):
        """Test context isolation with ThreadPoolExecutor."""

        def worker(worker_id):
            """Worker function for thread pool."""
            clear_context()
            # Use worker_id + 1 to avoid 0 which is falsy and won't be included in get_context()
            set_context(vm_id=f"vm-worker-{worker_id}", user_id=worker_id + 1)
            import time

            time.sleep(0.01)
            context = get_context()
            return context

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(worker, i) for i in range(5)]
            results = [future.result() for future in futures]

        # Verify each worker had its own context
        for i, context in enumerate(results):
            assert context["vm_id"] == f"vm-worker-{i}"
            assert context["user_id"] == i + 1

    @pytest.mark.asyncio
    async def test_context_propagates_within_async_task(self):
        """Test that context propagates within nested async calls."""

        async def inner_function():
            """Inner async function."""
            context = get_context()
            return context

        async def outer_function():
            """Outer async function."""
            set_context(vm_id="vm-nested", user_id=777)
            # Call inner function
            result = await inner_function()
            return result

        result = await outer_function()
        assert result["vm_id"] == "vm-nested"
        assert result["user_id"] == 777


class TestContextEdgeCases:
    """Tests for edge cases and error conditions."""

    def setup_method(self):
        """Set up test fixtures."""
        clear_context()

    def teardown_method(self):
        """Clean up after tests."""
        clear_context()

    def test_set_context_with_no_arguments(self):
        """Test that set_context with no arguments does nothing."""
        # Set initial context
        set_context(vm_id="vm-initial", user_id=100)

        # Call set_context with no arguments
        set_context()

        # Verify context is unchanged
        context = get_context()
        assert context["vm_id"] == "vm-initial"
        assert context["user_id"] == 100

    def test_set_context_with_invalid_types(self):
        """Test set_context with various data types."""
        # These should all work - context variables accept any type
        set_context(
            vm_id=12345,  # Integer instead of string
            user_id="string_id",  # String instead of integer
            user_name=None,  # None
            request_id=["list", "of", "items"],  # List
            action={"dict": "value"},  # Dict
        )

        context = get_context()
        assert context["vm_id"] == 12345
        assert context["user_id"] == "string_id"
        assert context.get("user_name") is None
        assert context["request_id"] == ["list", "of", "items"]
        assert context["action"] == {"dict": "value"}

    def test_multiple_clear_context_calls(self):
        """Test that multiple clear_context calls are safe."""
        set_context(vm_id="vm-test")
        clear_context()
        clear_context()  # Should not raise error
        clear_context()  # Should not raise error

        context = get_context()
        assert context.get("vm_id") is None

    def test_context_variables_are_independent(self):
        """Test that context variables are independent."""
        # Set only vm_id
        set_context(vm_id="vm-independent")

        context = get_context()
        assert context["vm_id"] == "vm-independent"
        assert context.get("user_id") is None
        assert context.get("user_name") is None

        # Set only user_id
        clear_context()
        set_context(user_id=999)

        context = get_context()
        assert context.get("vm_id") is None
        assert context["user_id"] == 999
        assert context.get("user_name") is None

    def test_large_context_values(self):
        """Test context with large values."""
        large_string = "x" * 10000
        large_id = 999999999999

        set_context(vm_id=large_string, user_id=large_id)

        context = get_context()
        assert context["vm_id"] == large_string
        assert context["user_id"] == large_id
        assert len(context["vm_id"]) == 10000

    def test_special_characters_in_context(self):
        """Test context with special characters."""
        special_chars = "vm-テスト-🚀-\n\t-quotes'\"both"

        set_context(vm_id=special_chars, action="test\naction")

        context = get_context()
        assert context["vm_id"] == special_chars
        assert context["action"] == "test\naction"


class TestContextUsagePatterns:
    """Tests for common context usage patterns."""

    def setup_method(self):
        """Set up test fixtures."""
        clear_context()

    def teardown_method(self):
        """Clean up after tests."""
        clear_context()

    def test_request_scoped_context(self):
        """Test context pattern for request-scoped operations."""
        # Simulate request start
        set_context(request_id="req-123", action="http.request")

        # Simulate processing
        context = get_context()
        assert context["request_id"] == "req-123"
        assert context["action"] == "http.request"

        # Add more context during processing
        set_context(user_id=456, vm_id="vm-789")

        context = get_context()
        assert context["request_id"] == "req-123"  # Still present
        assert context["user_id"] == 456

        # Simulate request end (cleanup)
        clear_context()

        context = get_context()
        assert context.get("request_id") is None
        assert context.get("user_id") is None

    def test_nested_operation_context(self):
        """Test context pattern for nested operations."""
        # Outer operation
        set_context(request_id="req-outer", action="outer.operation")

        outer_context = get_context()
        assert outer_context["action"] == "outer.operation"

        # Inner operation (overrides action but keeps request_id)
        set_context(action="inner.operation", vm_id="vm-inner")

        inner_context = get_context()
        assert inner_context["request_id"] == "req-outer"  # Inherited
        assert inner_context["action"] == "inner.operation"  # Overridden
        assert inner_context["vm_id"] == "vm-inner"  # Added

    @pytest.mark.asyncio
    async def test_context_in_background_task(self):
        """Test context usage in background task scenario."""
        # Set initial context (e.g., from HTTP request)
        set_context(request_id="req-bg", user_id=123)

        async def background_task():
            """Simulate background task."""
            # Context should be available
            context = get_context()
            assert context["request_id"] == "req-bg"
            assert context["user_id"] == 123

            # Background task can add more context
            set_context(vm_id="vm-bg", action="background.processing")

            context = get_context()
            assert context["vm_id"] == "vm-bg"
            assert context["request_id"] == "req-bg"  # Still available

        await background_task()

    def test_context_persistence_across_function_calls(self):
        """Test that context persists across function calls."""

        def function_a():
            """First function."""
            set_context(vm_id="vm-persist", user_id=111)

        def function_b():
            """Second function."""
            context = get_context()
            return context

        function_a()
        result = function_b()

        assert result["vm_id"] == "vm-persist"
        assert result["user_id"] == 111
