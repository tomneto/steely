import asyncio
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from steely import Dan
from steely.cronos import cronos


class TestCronosDecorator:
    """Tests for the cronos timing decorator."""

    def test_sync_function_returns_correct_value(self):
        """Test that decorated sync function returns the correct value."""
        @Dan.cronos
        def add_numbers(a, b):
            return a + b

        result = add_numbers(2, 3)
        assert result == 5

    def test_sync_function_preserves_signature(self):
        """Test that decorated sync function preserves original signature."""
        import inspect

        def original_func(a: int, b: str, c: float = 1.0) -> str:
            return f"{a}{b}{c}"

        decorated = cronos(original_func)

        original_sig = inspect.signature(original_func)
        decorated_sig = inspect.signature(decorated)

        assert str(original_sig) == str(decorated_sig)

    def test_sync_function_preserves_name(self):
        """Test that decorated sync function preserves __name__."""
        @Dan.cronos
        def my_function():
            pass

        assert my_function.__name__ == "my_function"

    def test_sync_function_with_args_and_kwargs(self):
        """Test sync function with positional and keyword arguments."""
        @Dan.cronos
        def func_with_args(a, b, c=10, d=20):
            return a + b + c + d

        result = func_with_args(1, 2, c=3, d=4)
        assert result == 10

    def test_sync_function_logs_time_elapsed(self, capsys):
        """Test that sync function logs time elapsed."""
        @Dan.cronos
        def slow_func():
            return "done"

        with patch('steely.cronos.Logger') as mock_logger:
            mock_log = MagicMock()
            mock_logger.return_value.log = mock_log

            # Re-decorate to use the mock
            @Dan.cronos
            def slow_func_mocked():
                return "done"

            result = slow_func_mocked()

            assert result == "done"
            mock_log.assert_called_once()
            call_args = mock_log.call_args[0]
            assert call_args[0] == 'TEST-RESULT'
            assert 'Total Time Elapsed' in call_args[1]

    def test_sync_function_exception_still_logs(self):
        """Test that time is logged even when exception is raised."""
        with patch('steely.cronos.Logger') as mock_logger:
            mock_log = MagicMock()
            mock_logger.return_value.log = mock_log

            @Dan.cronos
            def failing_func():
                raise ValueError("Test error")

            with pytest.raises(ValueError, match="Test error"):
                failing_func()

            mock_log.assert_called_once()
            call_args = mock_log.call_args[0]
            assert call_args[0] == 'TEST-RESULT'

    @pytest.mark.asyncio
    async def test_async_function_returns_correct_value(self):
        """Test that decorated async function returns the correct value."""
        @Dan.cronos
        async def async_add(a, b):
            await asyncio.sleep(0.01)
            return a + b

        result = await async_add(5, 7)
        assert result == 12

    @pytest.mark.asyncio
    async def test_async_function_preserves_signature(self):
        """Test that decorated async function preserves original signature."""
        import inspect

        async def original_async(x: int, y: str = "default") -> str:
            return f"{x}-{y}"

        decorated = cronos(original_async)

        original_sig = inspect.signature(original_async)
        decorated_sig = inspect.signature(decorated)

        assert str(original_sig) == str(decorated_sig)

    @pytest.mark.asyncio
    async def test_async_function_preserves_name(self):
        """Test that decorated async function preserves __name__."""
        @Dan.cronos
        async def my_async_function():
            pass

        assert my_async_function.__name__ == "my_async_function"

    @pytest.mark.asyncio
    async def test_async_function_logs_time_elapsed(self):
        """Test that async function logs time elapsed."""
        with patch('steely.cronos.Logger') as mock_logger:
            mock_log = MagicMock()
            mock_logger.return_value.log = mock_log

            @Dan.cronos
            async def async_func():
                await asyncio.sleep(0.01)
                return "async done"

            result = await async_func()

            assert result == "async done"
            mock_log.assert_called_once()
            call_args = mock_log.call_args[0]
            assert call_args[0] == 'TEST-RESULT'
            assert 'Total Time Elapsed' in call_args[1]

    @pytest.mark.asyncio
    async def test_async_function_exception_still_logs(self):
        """Test that time is logged even when async exception is raised."""
        with patch('steely.cronos.Logger') as mock_logger:
            mock_log = MagicMock()
            mock_logger.return_value.log = mock_log

            @Dan.cronos
            async def async_failing_func():
                await asyncio.sleep(0.01)
                raise RuntimeError("Async error")

            with pytest.raises(RuntimeError, match="Async error"):
                await async_failing_func()

            mock_log.assert_called_once()
            call_args = mock_log.call_args[0]
            assert call_args[0] == 'TEST-RESULT'

    def test_decorator_detects_sync_function(self):
        """Test that decorator correctly identifies sync functions."""
        @Dan.cronos
        def sync_func():
            return "sync"

        assert not asyncio.iscoroutinefunction(sync_func)

    def test_decorator_detects_async_function(self):
        """Test that decorator correctly identifies async functions."""
        @Dan.cronos
        async def async_func():
            return "async"

        assert asyncio.iscoroutinefunction(async_func)

    def test_sync_function_with_no_return(self):
        """Test sync function that returns None."""
        @Dan.cronos
        def no_return_func():
            x = 1 + 1

        result = no_return_func()
        assert result is None

    @pytest.mark.asyncio
    async def test_async_function_with_no_return(self):
        """Test async function that returns None."""
        @Dan.cronos
        async def no_return_async():
            await asyncio.sleep(0.001)

        result = await no_return_async()
        assert result is None