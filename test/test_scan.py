import asyncio
import pytest
from unittest.mock import patch, MagicMock
from io import StringIO
import sys

from steely import Dan
from steely.scan import scan, ScanPrinter, VariableTracker
from steely.design import TypeColors, Symbols, UnicodeColors


class TestScanDecorator:
    """Tests for the scan decorator."""

    def test_sync_function_returns_correct_value(self):
        """Test that decorated sync function returns the correct value."""
        @Dan.scan
        def add_numbers(a, b):
            c = a + b
            return c

        result = add_numbers(2, 3)
        assert result == 5

    def test_sync_function_preserves_signature(self):
        """Test that decorated sync function preserves original signature."""
        import inspect

        def original_func(a: int, b: str, c: float = 1.0) -> str:
            result = f"{a}{b}{c}"
            return result

        decorated = scan(original_func)

        original_sig = inspect.signature(original_func)
        decorated_sig = inspect.signature(decorated)

        assert str(original_sig) == str(decorated_sig)

    def test_sync_function_preserves_name(self):
        """Test that decorated sync function preserves __name__."""
        @Dan.scan
        def my_function():
            pass

        assert my_function.__name__ == "my_function"

    def test_sync_function_with_args_and_kwargs(self):
        """Test sync function with positional and keyword arguments."""
        @Dan.scan
        def func_with_args(a, b, c=10, d=20):
            result = a + b + c + d
            return result

        result = func_with_args(1, 2, c=3, d=4)
        assert result == 10

    def test_sync_function_tracks_variables(self, capsys):
        """Test that sync function tracks variable assignments."""
        @Dan.scan
        def variable_func():
            a = 1
            b = 2
            c = a + b
            return c

        result = variable_func()
        assert result == 3

        captured = capsys.readouterr()
        # Check that variables are tracked in output
        assert "a" in captured.out
        assert "b" in captured.out
        assert "c" in captured.out

    def test_sync_function_shows_return_value(self, capsys):
        """Test that return value is displayed."""
        @Dan.scan
        def return_func():
            return 42

        result = return_func()
        assert result == 42

        captured = capsys.readouterr()
        assert "return" in captured.out
        assert "42" in captured.out

    def test_sync_function_handles_exception(self, capsys):
        """Test that exceptions are displayed and re-raised."""
        @Dan.scan
        def failing_func():
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            failing_func()

        captured = capsys.readouterr()
        assert "Exception" in captured.out
        assert "ValueError" in captured.out

    def test_sync_function_with_no_return(self, capsys):
        """Test sync function that returns None."""
        @Dan.scan
        def no_return_func():
            x = 1 + 1

        result = no_return_func()
        assert result is None

        captured = capsys.readouterr()
        assert "None" in captured.out

    @pytest.mark.asyncio
    async def test_async_function_returns_correct_value(self):
        """Test that decorated async function returns the correct value."""
        @Dan.scan
        async def async_add(a, b):
            await asyncio.sleep(0.01)
            c = a + b
            return c

        result = await async_add(5, 7)
        assert result == 12

    @pytest.mark.asyncio
    async def test_async_function_preserves_signature(self):
        """Test that decorated async function preserves original signature."""
        import inspect

        async def original_async(x: int, y: str = "default") -> str:
            result = f"{x}-{y}"
            return result

        decorated = scan(original_async)

        original_sig = inspect.signature(original_async)
        decorated_sig = inspect.signature(decorated)

        assert str(original_sig) == str(decorated_sig)

    @pytest.mark.asyncio
    async def test_async_function_preserves_name(self):
        """Test that decorated async function preserves __name__."""
        @Dan.scan
        async def my_async_function():
            pass

        assert my_async_function.__name__ == "my_async_function"

    @pytest.mark.asyncio
    async def test_async_function_handles_exception(self, capsys):
        """Test that async exceptions are displayed and re-raised."""
        @Dan.scan
        async def async_failing():
            await asyncio.sleep(0.01)
            raise RuntimeError("Async error")

        with pytest.raises(RuntimeError, match="Async error"):
            await async_failing()

        captured = capsys.readouterr()
        assert "Exception" in captured.out
        assert "RuntimeError" in captured.out

    def test_decorator_detects_sync_function(self):
        """Test that decorator correctly identifies sync functions."""
        @Dan.scan
        def sync_func():
            return "sync"

        assert not asyncio.iscoroutinefunction(sync_func)

    def test_decorator_detects_async_function(self):
        """Test that decorator correctly identifies async functions."""
        @Dan.scan
        async def async_func():
            return "async"

        assert asyncio.iscoroutinefunction(async_func)


class TestScanPrinter:
    """Tests for the ScanPrinter class."""

    def test_header_prints_function_name(self, capsys):
        """Test that header prints function name."""
        ScanPrinter.header("test_func", "test_module")

        captured = capsys.readouterr()
        assert "test_func" in captured.out
        assert "test_module" in captured.out
        assert "SCAN" in captured.out

    def test_return_value_prints_value(self, capsys):
        """Test that return_value prints the value."""
        ScanPrinter.return_value(42)

        captured = capsys.readouterr()
        assert "return" in captured.out
        assert "42" in captured.out
        assert "int" in captured.out

    def test_exception_prints_error_info(self, capsys):
        """Test that exception prints error information."""
        exc = ValueError("Test error message")
        ScanPrinter.exception(exc)

        captured = capsys.readouterr()
        assert "Exception" in captured.out
        assert "ValueError" in captured.out
        assert "Test error message" in captured.out

    def test_footer_prints_elapsed_time(self, capsys):
        """Test that footer prints elapsed time."""
        ScanPrinter.footer(123.456)

        captured = capsys.readouterr()
        assert "123.456ms" in captured.out
        assert "Completed" in captured.out

    def test_format_value_truncates_long_strings(self):
        """Test that long values are truncated."""
        long_string = "a" * 100
        result = ScanPrinter._format_value(long_string, max_len=20)

        assert len(result) <= 20
        assert result.endswith(Symbols.ELLIPSIS)

    def test_format_value_preserves_short_strings(self):
        """Test that short values are not truncated."""
        short_string = "hello"
        result = ScanPrinter._format_value(short_string)

        assert result == "'hello'"

    def test_get_type_name_for_list(self):
        """Test type name for list includes length."""
        result = ScanPrinter._get_type_name([1, 2, 3])
        assert result == "list[3]"

    def test_get_type_name_for_dict(self):
        """Test type name for dict includes length."""
        result = ScanPrinter._get_type_name({"a": 1, "b": 2})
        assert result == "dict{2}"

    def test_get_type_name_for_string(self):
        """Test type name for string includes length."""
        result = ScanPrinter._get_type_name("hello")
        assert result == "str[5]"

    def test_get_type_name_for_int(self):
        """Test type name for int."""
        result = ScanPrinter._get_type_name(42)
        assert result == "int"

    def test_get_type_name_for_tuple(self):
        """Test type name for tuple includes length."""
        result = ScanPrinter._get_type_name((1, 2, 3, 4))
        assert result == "tuple[4]"

    def test_get_type_name_for_set(self):
        """Test type name for set includes length."""
        result = ScanPrinter._get_type_name({1, 2})
        assert result == "set[2]"


class TestTypeColors:
    """Tests for TypeColors class."""

    def test_get_color_for_int(self):
        """Test color for integers."""
        assert TypeColors.get_color(42) == TypeColors.INT

    def test_get_color_for_float(self):
        """Test color for floats."""
        assert TypeColors.get_color(3.14) == TypeColors.FLOAT

    def test_get_color_for_string(self):
        """Test color for strings."""
        assert TypeColors.get_color("hello") == TypeColors.STR

    def test_get_color_for_bool(self):
        """Test color for booleans."""
        assert TypeColors.get_color(True) == TypeColors.BOOL
        assert TypeColors.get_color(False) == TypeColors.BOOL

    def test_get_color_for_none(self):
        """Test color for None."""
        assert TypeColors.get_color(None) == TypeColors.NONE

    def test_get_color_for_list(self):
        """Test color for lists."""
        assert TypeColors.get_color([1, 2, 3]) == TypeColors.LIST

    def test_get_color_for_dict(self):
        """Test color for dicts."""
        assert TypeColors.get_color({"key": "value"}) == TypeColors.DICT

    def test_get_color_for_tuple(self):
        """Test color for tuples."""
        assert TypeColors.get_color((1, 2)) == TypeColors.TUPLE

    def test_get_color_for_set(self):
        """Test color for sets."""
        assert TypeColors.get_color({1, 2}) == TypeColors.SET

    def test_get_color_for_callable(self):
        """Test color for callables."""
        def func():
            pass
        assert TypeColors.get_color(func) == TypeColors.CALLABLE

    def test_get_color_for_class_instance(self):
        """Test color for class instances."""
        class MyClass:
            pass
        assert TypeColors.get_color(MyClass()) == TypeColors.CLASS

    def test_bool_checked_before_int(self):
        """Test that bool is checked before int (since bool is subclass of int)."""
        # True is technically an int (True == 1), but should get BOOL color
        assert TypeColors.get_color(True) == TypeColors.BOOL
        assert TypeColors.get_color(True) != TypeColors.INT


class TestSymbols:
    """Tests for Symbols class."""

    def test_symbols_are_unicode(self):
        """Test that symbols are unicode characters."""
        assert Symbols.ARROW_RIGHT == '→'
        assert Symbols.CHECK == '✓'
        assert Symbols.CROSS == '✗'
        assert Symbols.SCAN == '⚡'
        assert Symbols.VAR == '◈'
        assert Symbols.RETURN == '⟼'

    def test_box_drawing_characters(self):
        """Test box drawing characters."""
        assert Symbols.BOX_TL == '┌'
        assert Symbols.BOX_TR == '┐'
        assert Symbols.BOX_BL == '└'
        assert Symbols.BOX_BR == '┘'
        assert Symbols.BOX_H == '─'
        assert Symbols.BOX_V == '│'


class TestVariableTracker:
    """Tests for VariableTracker class."""

    def test_tracker_initialization(self):
        """Test VariableTracker initialization."""
        def dummy():
            pass

        tracker = VariableTracker(dummy.__code__)

        assert tracker.target_code == dummy.__code__
        assert tracker.previous_locals == {}
        assert tracker.tracked_names == set()
        assert tracker.changes == []
        assert tracker.active is False

    def test_tracker_not_active_returns_none(self):
        """Test that inactive tracker returns None."""
        def dummy():
            pass

        tracker = VariableTracker(dummy.__code__)
        tracker.active = False

        result = tracker.trace_calls(None, 'call', None)
        assert result is None


class TestScanWithDifferentTypes:
    """Tests for scan decorator with various data types."""

    def test_scan_with_integer_variables(self, capsys):
        """Test scan tracks integer variables."""
        @Dan.scan
        def int_func():
            x = 42
            return x

        result = int_func()
        assert result == 42

        captured = capsys.readouterr()
        assert "int" in captured.out

    def test_scan_with_float_variables(self, capsys):
        """Test scan tracks float variables."""
        @Dan.scan
        def float_func():
            pi = 3.14159
            return pi

        result = float_func()
        assert result == 3.14159

        captured = capsys.readouterr()
        assert "float" in captured.out

    def test_scan_with_string_variables(self, capsys):
        """Test scan tracks string variables."""
        @Dan.scan
        def str_func():
            message = "hello world"
            return message

        result = str_func()
        assert result == "hello world"

        captured = capsys.readouterr()
        assert "str" in captured.out

    def test_scan_with_list_variables(self, capsys):
        """Test scan tracks list variables."""
        @Dan.scan
        def list_func():
            items = [1, 2, 3]
            return items

        result = list_func()
        assert result == [1, 2, 3]

        captured = capsys.readouterr()
        assert "list" in captured.out

    def test_scan_with_dict_variables(self, capsys):
        """Test scan tracks dict variables."""
        @Dan.scan
        def dict_func():
            data = {"key": "value"}
            return data

        result = dict_func()
        assert result == {"key": "value"}

        captured = capsys.readouterr()
        assert "dict" in captured.out

    def test_scan_with_none_variable(self, capsys):
        """Test scan tracks None variables."""
        @Dan.scan
        def none_func():
            nothing = None
            return nothing

        result = none_func()
        assert result is None

        captured = capsys.readouterr()
        assert "None" in captured.out

    def test_scan_with_boolean_variables(self, capsys):
        """Test scan tracks boolean variables."""
        @Dan.scan
        def bool_func():
            flag = True
            return flag

        result = bool_func()
        assert result is True

        captured = capsys.readouterr()
        assert "bool" in captured.out

    def test_scan_with_tuple_variables(self, capsys):
        """Test scan tracks tuple variables."""
        @Dan.scan
        def tuple_func():
            coords = (1, 2, 3)
            return coords

        result = tuple_func()
        assert result == (1, 2, 3)

        captured = capsys.readouterr()
        assert "tuple" in captured.out


class TestScanOutputFormat:
    """Tests for scan output formatting."""

    def test_output_contains_header(self, capsys):
        """Test that output contains header with function name."""
        @Dan.scan
        def header_test():
            return 1

        header_test()
        captured = capsys.readouterr()

        assert "SCAN" in captured.out
        assert "header_test" in captured.out

    def test_output_contains_box_characters(self, capsys):
        """Test that output contains box drawing characters."""
        @Dan.scan
        def box_test():
            return 1

        box_test()
        captured = capsys.readouterr()

        assert "┌" in captured.out
        assert "└" in captured.out
        assert "│" in captured.out

    def test_output_contains_completion_time(self, capsys):
        """Test that output shows completion time."""
        @Dan.scan
        def time_test():
            return 1

        time_test()
        captured = capsys.readouterr()

        assert "Completed" in captured.out
        assert "ms" in captured.out

    def test_output_shows_parameters(self, capsys):
        """Test that output shows function parameters."""
        @Dan.scan
        def param_test(x, y):
            return x + y

        param_test(10, 20)
        captured = capsys.readouterr()

        assert "Parameters" in captured.out
        assert "10" in captured.out
        assert "20" in captured.out
