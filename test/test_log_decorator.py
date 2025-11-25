import asyncio
import pytest
from unittest.mock import patch, MagicMock
import inspect

from steely import Dan
from steely.logger import log, Logger


class TestLogDecorator:
    """Tests for the log decorator."""

    def test_sync_function_returns_correct_value(self):
        """Test that decorated sync function returns the correct value."""
        @Dan.log
        def add_numbers(a, b):
            return a + b

        result = add_numbers(2, 3)
        assert result == 5

    def test_sync_function_preserves_signature(self):
        """Test that decorated sync function preserves original signature."""
        def original_func(a: int, b: str, c: float = 1.0) -> str:
            return f"{a}{b}{c}"

        decorated = log(original_func)

        original_sig = inspect.signature(original_func)
        decorated_sig = inspect.signature(decorated)

        assert str(original_sig) == str(decorated_sig)

    def test_sync_function_preserves_name(self):
        """Test that decorated sync function preserves __name__."""
        @Dan.log
        def my_function():
            pass

        assert my_function.__name__ == "my_function"

    def test_sync_function_with_args_and_kwargs(self):
        """Test sync function with positional and keyword arguments."""
        @Dan.log
        def func_with_args(a, b, c=10, d=20):
            return a + b + c + d

        result = func_with_args(1, 2, c=3, d=4)
        assert result == 10

    def test_sync_function_logs_start_message(self, capsys):
        """Test that sync function logs start message."""
        @Dan.log
        def start_test():
            return "done"

        result = start_test()
        assert result == "done"

        # Give thread time to complete
        import time
        time.sleep(0.1)

        captured = capsys.readouterr()
        assert "START" in captured.out
        assert "Function Execution Started" in captured.out

    def test_sync_function_logs_success_message(self, capsys):
        """Test that sync function logs success message on completion."""
        @Dan.log
        def success_test():
            return "done"

        result = success_test()
        assert result == "done"

        # Give thread time to complete
        import time
        time.sleep(0.1)

        captured = capsys.readouterr()
        assert "SUCCESS" in captured.out
        assert "Function Finished" in captured.out

    def test_sync_function_logs_error_on_exception(self, capsys):
        """Test that sync function logs error when exception is raised."""
        @Dan.log
        def failing_func():
            raise ValueError("Test error")

        # The exception should not propagate because the decorator catches it
        result = failing_func()
        assert result is None

        # Give thread time to complete
        import time
        time.sleep(0.1)

        captured = capsys.readouterr()
        assert "ERROR" in captured.out
        assert "Function Failed" in captured.out

    def test_sync_function_with_no_return(self):
        """Test sync function that returns None."""
        @Dan.log
        def no_return_func():
            x = 1 + 1

        result = no_return_func()
        assert result is None

    @pytest.mark.asyncio
    async def test_async_function_returns_correct_value(self):
        """Test that decorated async function returns the correct value."""
        @Dan.log
        async def async_add(a, b):
            await asyncio.sleep(0.01)
            return a + b

        result = await async_add(5, 7)
        assert result == 12

    @pytest.mark.asyncio
    async def test_async_function_preserves_signature(self):
        """Test that decorated async function preserves original signature."""
        async def original_async(x: int, y: str = "default") -> str:
            return f"{x}-{y}"

        decorated = log(original_async)

        original_sig = inspect.signature(original_async)
        decorated_sig = inspect.signature(decorated)

        assert str(original_sig) == str(decorated_sig)

    @pytest.mark.asyncio
    async def test_async_function_preserves_name(self):
        """Test that decorated async function preserves __name__."""
        @Dan.log
        async def my_async_function():
            pass

        assert my_async_function.__name__ == "my_async_function"

    @pytest.mark.asyncio
    async def test_async_function_logs_start_and_success(self, capsys):
        """Test that async function logs start and success messages."""
        @Dan.log
        async def async_func():
            await asyncio.sleep(0.01)
            return "async done"

        result = await async_func()
        assert result == "async done"

        # Give thread time to complete
        import time
        time.sleep(0.1)

        captured = capsys.readouterr()
        assert "START" in captured.out
        assert "SUCCESS" in captured.out

    @pytest.mark.asyncio
    async def test_async_function_logs_error_on_exception(self, capsys):
        """Test that async function logs error when exception is raised."""
        @Dan.log
        async def async_failing():
            await asyncio.sleep(0.01)
            raise RuntimeError("Async error")

        # The exception should not propagate because the decorator catches it
        result = await async_failing()
        assert result is None

        # Give thread time to complete
        import time
        time.sleep(0.1)

        captured = capsys.readouterr()
        assert "ERROR" in captured.out
        assert "Function Failed" in captured.out

    def test_decorator_detects_sync_function(self):
        """Test that decorator correctly identifies sync functions."""
        @Dan.log
        def sync_func():
            return "sync"

        assert not asyncio.iscoroutinefunction(sync_func)

    def test_decorator_detects_async_function(self):
        """Test that decorator correctly identifies async functions."""
        @Dan.log
        async def async_func():
            return "async"

        assert asyncio.iscoroutinefunction(async_func)

    def test_log_uses_module_name(self, capsys):
        """Test that log decorator uses module name in output."""
        @Dan.log
        def module_test():
            return 1

        module_test()

        import time
        time.sleep(0.1)

        captured = capsys.readouterr()
        # Should contain either module name or __main__
        assert "TEST_LOG_DECORATOR" in captured.out.upper() or "__MAIN__" in captured.out.upper()

    def test_log_uses_function_name_as_owner(self, capsys):
        """Test that log decorator uses function name as owner."""
        @Dan.log
        def owner_test():
            return 1

        owner_test()

        import time
        time.sleep(0.1)

        captured = capsys.readouterr()
        assert "OWNER_TEST" in captured.out.upper()


class TestLogDecoratorWithLogger:
    """Tests for log decorator integration with Logger class."""

    def test_log_creates_logger_with_correct_module(self):
        """Test that log decorator creates Logger with correct module name."""
        with patch('steely.logger.Logger') as mock_logger:
            mock_instance = MagicMock()
            mock_logger.return_value = mock_instance

            @log
            def test_func():
                return 1

            # The decorator should have created a Logger instance
            mock_logger.assert_called_once()

    def test_log_calls_start_and_success(self):
        """Test that log decorator calls start and success methods."""
        with patch('steely.logger.Logger') as mock_logger:
            mock_instance = MagicMock()
            mock_logger.return_value = mock_instance

            @log
            def test_func():
                return 42

            result = test_func()

            # Verify start was called
            mock_instance.start.assert_called_once()
            # Verify success was called
            mock_instance.success.assert_called_once()

    def test_log_calls_error_on_exception(self):
        """Test that log decorator calls error method on exception."""
        with patch('steely.logger.Logger') as mock_logger:
            mock_instance = MagicMock()
            mock_logger.return_value = mock_instance

            @log
            def failing_func():
                raise ValueError("Test error")

            result = failing_func()

            # Verify error was called
            mock_instance.error.assert_called_once()
            call_args = mock_instance.error.call_args[0][0]
            assert "Test error" in call_args


class TestLogDecoratorOutput:
    """Tests for log decorator output formatting."""

    def test_output_contains_timestamp(self, capsys):
        """Test that output contains timestamp."""
        @Dan.log
        def timestamp_test():
            return 1

        timestamp_test()

        import time
        time.sleep(0.1)

        captured = capsys.readouterr()
        # Check for timestamp format (DD-MM-YYYY)
        import re
        assert re.search(r'\d{2}-\d{2}-\d{4}', captured.out)

    def test_output_contains_level_tags(self, capsys):
        """Test that output contains level tags in brackets."""
        @Dan.log
        def level_test():
            return 1

        level_test()

        import time
        time.sleep(0.1)

        captured = capsys.readouterr()
        assert "[START]" in captured.out
        assert "[SUCCESS]" in captured.out

    def test_output_uses_colors(self, capsys):
        """Test that output uses ANSI color codes."""
        @Dan.log
        def color_test():
            return 1

        color_test()

        import time
        time.sleep(0.1)

        captured = capsys.readouterr()
        # Check for ANSI escape codes
        assert "\033[" in captured.out


class TestLogDecoratorEdgeCases:
    """Tests for edge cases of the log decorator."""

    def test_multiple_decorated_functions(self):
        """Test that multiple functions can be decorated independently."""
        @Dan.log
        def func_a():
            return "a"

        @Dan.log
        def func_b():
            return "b"

        assert func_a() == "a"
        assert func_b() == "b"

    def test_nested_decorated_functions(self):
        """Test nested decorated function calls."""
        @Dan.log
        def outer():
            return inner()

        @Dan.log
        def inner():
            return "inner result"

        result = outer()
        assert result == "inner result"

    def test_decorated_function_with_default_args(self):
        """Test decorated function with default arguments."""
        @Dan.log
        def default_args(a, b=10, c="default"):
            return f"{a}-{b}-{c}"

        result = default_args(1)
        assert result == "1-10-default"

        result = default_args(2, b=20)
        assert result == "2-20-default"

    def test_decorated_function_with_args_kwargs(self):
        """Test decorated function with *args and **kwargs."""
        @Dan.log
        def args_kwargs(*args, **kwargs):
            return sum(args) + sum(kwargs.values())

        result = args_kwargs(1, 2, 3, x=4, y=5)
        assert result == 15

    def test_decorated_class_method(self):
        """Test that log decorator works with class methods."""
        class MyClass:
            @Dan.log
            def method(self, x):
                return x * 2

        obj = MyClass()
        result = obj.method(5)
        assert result == 10

    def test_decorated_static_method(self):
        """Test that log decorator works with static methods."""
        class MyClass:
            @staticmethod
            @Dan.log
            def static_method(x):
                return x * 3

        result = MyClass.static_method(5)
        assert result == 15

    def test_decorated_lambda_equivalent(self):
        """Test decorated function that mimics lambda behavior."""
        @Dan.log
        def lambda_like(x):
            return x ** 2

        result = lambda_like(4)
        assert result == 16

    def test_function_returning_complex_type(self):
        """Test decorated function returning complex types."""
        @Dan.log
        def complex_return():
            return {"list": [1, 2, 3], "nested": {"a": 1}}

        result = complex_return()
        assert result == {"list": [1, 2, 3], "nested": {"a": 1}}

    @pytest.mark.asyncio
    async def test_async_with_await_multiple_times(self):
        """Test async function with multiple await calls."""
        @Dan.log
        async def multi_await():
            await asyncio.sleep(0.01)
            x = 1
            await asyncio.sleep(0.01)
            y = 2
            await asyncio.sleep(0.01)
            return x + y

        result = await multi_await()
        assert result == 3
