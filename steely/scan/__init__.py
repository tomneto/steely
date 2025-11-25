"""
Scan Module - Real-Time Variable Tracking with Beautiful Output
================================================================

This module provides the `scan` decorator, a powerful debugging tool that
tracks variable assignments in real-time during function execution. It
displays beautifully formatted output showing variable names, types, values,
and line numbers.

Features
--------
- Real-time variable tracking using Python's sys.settrace
- Type-specific color coding for easy visual identification
- Line number references for each variable assignment
- Function parameter display
- Return value tracking
- Exception visualization
- Execution time measurement
- Support for both sync and async functions

Color Scheme
------------
Variables are color-coded by type:

- **int**: Bright blue
- **float**: Deep blue
- **str**: Orange
- **bool**: Magenta
- **None**: Gray
- **list**: Sea green
- **dict**: Gold
- **tuple**: Light purple
- **set**: Pink

Examples
--------
Basic usage:

>>> from steely import Dan
>>> @Dan.scan
... def calculate(x, y):
...     total = x + y
...     squared = total ** 2
...     return squared
>>> calculate(3, 4)
# Beautiful output showing each variable assignment

Output example::

    ┌──────────────────────────────────────────────────────────┐
    │ ⚡ SCAN │ calculate @ __main__
    ├──────────────────────────────────────────────────────────┤
    │ Parameters:
    │    ◈ x : int = 3
    │    ◈ y : int = 4
    ├──────────────────────────────────────────────────────────┤
    │ L3 ◈ total : int = 7
    │ L4 ◈ squared : int = 49
    ├──────────────────────────────────────────────────────────┤
    │ ⟼ return : int = 49
    ├──────────────────────────────────────────────────────────┤
    │ ✓ Completed in 0.123ms
    └──────────────────────────────────────────────────────────┘

Notes
-----
- The scan decorator uses sys.settrace which may affect performance.
  Use primarily for debugging, not in production.
- The original function signature is preserved for framework compatibility.
- Internal variables (starting with _) are automatically filtered out.
"""

import asyncio
import inspect
import sys
from functools import wraps
from datetime import datetime
from typing import Any, Dict, Optional, Set

from steely.design import UnicodeColors, TypeColors, Symbols

__all__ = ["scan", "ScanPrinter", "VariableTracker"]


class ScanPrinter:
    """
    Beautiful console printer for scan output with Unicode box drawing.

    This class provides static methods for printing beautifully formatted
    output during function scanning. It uses ANSI colors and Unicode box
    drawing characters for visual appeal.

    Attributes
    ----------
    C : UnicodeColors
        Reference to UnicodeColors for ANSI color codes.
    T : TypeColors
        Reference to TypeColors for type-specific colors.
    S : Symbols
        Reference to Symbols for Unicode characters.

    Examples
    --------
    >>> ScanPrinter.header("my_function", "__main__")
    >>> ScanPrinter.return_value(42)
    >>> ScanPrinter.footer(0.123)
    """

    C = UnicodeColors
    T = TypeColors
    S = Symbols

    @classmethod
    def header(cls, func_name: str, module: str):
        """
        Print the scan header with function name and module.

        Parameters
        ----------
        func_name : str
            The name of the function being scanned.
        module : str
            The module name where the function is defined.
        """
        width = 60
        print()
        print(f"{cls.C.bright_cyan}{cls.S.BOX_TL}{cls.S.BOX_H * (width - 2)}{cls.S.BOX_TR}{cls.C.reset}")
        print(f"{cls.C.bright_cyan}{cls.S.BOX_V}{cls.C.reset} {cls.S.SCAN} {cls.C.bold}{cls.C.bright_yellow}SCAN{cls.C.reset} {cls.C.dim}│{cls.C.reset} {cls.C.bright_white}{func_name}{cls.C.reset} {cls.C.dim}@ {module}{cls.C.reset}")
        print(f"{cls.C.bright_cyan}{cls.S.BOX_L}{cls.S.BOX_H * (width - 2)}{cls.S.BOX_R}{cls.C.reset}")

    @classmethod
    def signature(cls, sig: inspect.Signature, args: tuple, kwargs: dict, param_names: list):
        """
        Print function parameters with their values.

        Parameters
        ----------
        sig : inspect.Signature
            The function's signature object.
        args : tuple
            Positional arguments passed to the function.
        kwargs : dict
            Keyword arguments passed to the function.
        param_names : list
            List of parameter names from the signature.
        """
        print(f"{cls.C.bright_cyan}{cls.S.BOX_V}{cls.C.reset} {cls.C.dim}Parameters:{cls.C.reset}")

        # Map args to parameter names
        bound_args = {}
        for i, arg in enumerate(args):
            if i < len(param_names):
                bound_args[param_names[i]] = arg
        bound_args.update(kwargs)

        if not bound_args:
            print(f"{cls.C.bright_cyan}{cls.S.BOX_V}{cls.C.reset}   {cls.C.dim}(no parameters){cls.C.reset}")
        else:
            for name, value in bound_args.items():
                cls._print_variable(name, value, prefix="   ")

        print(f"{cls.C.bright_cyan}{cls.S.BOX_L}{cls.S.BOX_H * 58}{cls.S.BOX_R}{cls.C.reset}")

    @classmethod
    def _format_value(cls, value: Any, max_len: int = 40) -> str:
        """
        Format a value for display, truncating if necessary.

        Parameters
        ----------
        value : Any
            The value to format.
        max_len : int, optional
            Maximum length before truncation. Default is 40.

        Returns
        -------
        str
            The formatted (and possibly truncated) value representation.
        """
        repr_val = repr(value)
        if len(repr_val) > max_len:
            repr_val = repr_val[:max_len - 1] + cls.S.ELLIPSIS
        return repr_val

    @classmethod
    def _get_type_name(cls, value: Any) -> str:
        """
        Get a friendly type name with size information for collections.

        Parameters
        ----------
        value : Any
            The value to get the type name for.

        Returns
        -------
        str
            Type name like 'int', 'list[3]', 'dict{2}', 'str[10]'.
        """
        t = type(value).__name__
        if isinstance(value, (list, tuple, set, frozenset)):
            return f"{t}[{len(value)}]"
        elif isinstance(value, dict):
            return f"{t}{{{len(value)}}}"
        elif isinstance(value, str):
            return f"{t}[{len(value)}]"
        return t

    @classmethod
    def _print_variable(cls, name: str, value: Any, prefix: str = "", is_new: bool = True, line_no: Optional[int] = None):
        """
        Print a single variable with beautiful colored formatting.

        Parameters
        ----------
        name : str
            The variable name.
        value : Any
            The variable value.
        prefix : str, optional
            Prefix string for indentation. Default is "".
        is_new : bool, optional
            Whether this is a new variable (uses ◈) or existing (uses →).
        line_no : int, optional
            The line number where the assignment occurred.
        """
        color = TypeColors.get_color(value)
        type_name = cls._get_type_name(value)
        formatted_val = cls._format_value(value)

        line_info = f"{cls.C.dim}L{line_no}{cls.C.reset} " if line_no else ""
        symbol = cls.S.VAR if is_new else cls.S.ARROW_RIGHT

        print(f"{cls.C.bright_cyan}{cls.S.BOX_V}{cls.C.reset}{prefix}{line_info}"
              f"{cls.C.bright_purple}{symbol}{cls.C.reset} "
              f"{cls.C.bright_white}{name}{cls.C.reset} "
              f"{cls.C.dim}:{cls.C.reset} "
              f"{cls.C.yellow}{type_name}{cls.C.reset} "
              f"{cls.C.dim}={cls.C.reset} "
              f"{color}{formatted_val}{cls.C.reset}")

    @classmethod
    def variable_change(cls, name: str, old_value: Any, new_value: Any, line_no: int):
        """
        Print a variable value change with old and new values.

        Parameters
        ----------
        name : str
            The variable name.
        old_value : Any
            The previous value.
        new_value : Any
            The new value.
        line_no : int
            The line number where the change occurred.
        """
        color = TypeColors.get_color(new_value)
        type_name = cls._get_type_name(new_value)
        formatted_new = cls._format_value(new_value)
        formatted_old = cls._format_value(old_value, max_len=20)

        print(f"{cls.C.bright_cyan}{cls.S.BOX_V}{cls.C.reset} {cls.C.dim}L{line_no}{cls.C.reset} "
              f"{cls.C.orange}{cls.S.ARROW_RIGHT}{cls.C.reset} "
              f"{cls.C.bright_white}{name}{cls.C.reset} "
              f"{cls.C.dim}:{cls.C.reset} "
              f"{cls.C.yellow}{type_name}{cls.C.reset} "
              f"{cls.C.dim}{formatted_old} {cls.S.ARROW_RIGHT}{cls.C.reset} "
              f"{color}{formatted_new}{cls.C.reset}")

    @classmethod
    def new_variable(cls, name: str, value: Any, line_no: int):
        """
        Print a new variable assignment.

        Parameters
        ----------
        name : str
            The variable name.
        value : Any
            The assigned value.
        line_no : int
            The line number of the assignment.
        """
        cls._print_variable(name, value, prefix=" ", is_new=True, line_no=line_no)

    @classmethod
    def locals_snapshot(cls, local_vars: Dict[str, Any], title: str = "Local Variables"):
        """
        Print a snapshot of all local variables.

        Parameters
        ----------
        local_vars : Dict[str, Any]
            Dictionary of local variable names and values.
        title : str, optional
            Section title. Default is "Local Variables".
        """
        print(f"{cls.C.bright_cyan}{cls.S.BOX_V}{cls.C.reset} {cls.C.dim}{title}:{cls.C.reset}")

        # Filter out internal variables
        filtered = {k: v for k, v in local_vars.items()
                   if not k.startswith('_') and k not in ('self', 'cls')}

        if not filtered:
            print(f"{cls.C.bright_cyan}{cls.S.BOX_V}{cls.C.reset}   {cls.C.dim}(none){cls.C.reset}")
        else:
            for name, value in filtered.items():
                cls._print_variable(name, value, prefix="   ", is_new=False)

    @classmethod
    def return_value(cls, value: Any):
        """
        Print the function's return value.

        Parameters
        ----------
        value : Any
            The value being returned by the function.
        """
        print(f"{cls.C.bright_cyan}{cls.S.BOX_L}{cls.S.BOX_H * 58}{cls.S.BOX_R}{cls.C.reset}")
        color = TypeColors.get_color(value)
        type_name = cls._get_type_name(value)
        formatted_val = cls._format_value(value)

        print(f"{cls.C.bright_cyan}{cls.S.BOX_V}{cls.C.reset} {cls.S.RETURN} {cls.C.bright_green}return{cls.C.reset} "
              f"{cls.C.dim}:{cls.C.reset} "
              f"{cls.C.yellow}{type_name}{cls.C.reset} "
              f"{cls.C.dim}={cls.C.reset} "
              f"{color}{formatted_val}{cls.C.reset}")

    @classmethod
    def exception(cls, exc: Exception):
        """
        Print exception information when an error occurs.

        Parameters
        ----------
        exc : Exception
            The exception that was raised.
        """
        print(f"{cls.C.bright_cyan}{cls.S.BOX_L}{cls.S.BOX_H * 58}{cls.S.BOX_R}{cls.C.reset}")
        print(f"{cls.C.bright_cyan}{cls.S.BOX_V}{cls.C.reset} {cls.S.CROSS} {cls.C.bright_red}Exception{cls.C.reset} "
              f"{cls.C.dim}:{cls.C.reset} "
              f"{cls.C.yellow}{type(exc).__name__}{cls.C.reset} "
              f"{cls.C.dim}-{cls.C.reset} "
              f"{cls.C.red}{str(exc)}{cls.C.reset}")

    @classmethod
    def footer(cls, elapsed_ms: float):
        """
        Print the scan footer with execution time.

        Parameters
        ----------
        elapsed_ms : float
            The elapsed time in milliseconds.
        """
        print(f"{cls.C.bright_cyan}{cls.S.BOX_L}{cls.S.BOX_H * 58}{cls.S.BOX_R}{cls.C.reset}")
        print(f"{cls.C.bright_cyan}{cls.S.BOX_V}{cls.C.reset} {cls.S.CHECK} {cls.C.dim}Completed in{cls.C.reset} "
              f"{cls.C.bright_green}{elapsed_ms:.3f}ms{cls.C.reset}")
        print(f"{cls.C.bright_cyan}{cls.S.BOX_BL}{cls.S.BOX_H * 58}{cls.S.BOX_BR}{cls.C.reset}")
        print()


class VariableTracker:
    """
    Tracks variable changes during function execution using sys.settrace.

    This class uses Python's tracing mechanism to monitor variable assignments
    as they happen during function execution. It detects new variables and
    changes to existing variables.

    Parameters
    ----------
    target_func_code : code
        The code object of the function to track (func.__code__).

    Attributes
    ----------
    target_code : code
        The code object being tracked.
    previous_locals : Dict[str, Any]
        Snapshot of local variables from the previous trace event.
    tracked_names : Set[str]
        Set of variable names that have been seen.
    changes : list
        List of recorded changes (tuples of change info).
    active : bool
        Whether tracking is currently active.

    Notes
    -----
    This class is used internally by the scan decorator and should not
    typically be instantiated directly.
    """

    def __init__(self, target_func_code):
        self.target_code = target_func_code
        self.previous_locals: Dict[str, Any] = {}
        self.tracked_names: Set[str] = set()
        self.changes: list = []
        self.active = False

    def trace_calls(self, frame, event, arg):
        """
        Main trace function registered with sys.settrace.

        Parameters
        ----------
        frame : frame
            The current stack frame.
        event : str
            The event type ('call', 'line', 'return', 'exception').
        arg : Any
            Event-specific argument.

        Returns
        -------
        callable or None
            Returns trace_lines for 'call' events on target function,
            None otherwise.
        """
        if not self.active:
            return None

        # Only trace our target function
        if frame.f_code is not self.target_code:
            return None

        if event == 'call':
            self.previous_locals = {}
            self.tracked_names = set()
            return self.trace_lines

        return None

    def trace_lines(self, frame, event, arg):
        """
        Trace line-by-line execution to detect variable changes.

        This method is called for each line of code executed within
        the target function. It compares current local variables with
        the previous snapshot to detect new assignments and changes.

        Parameters
        ----------
        frame : frame
            The current stack frame.
        event : str
            The event type ('line' or 'return').
        arg : Any
            Event-specific argument.

        Returns
        -------
        callable
            Returns itself to continue tracing.
        """
        if not self.active:
            return None

        if frame.f_code is not self.target_code:
            return None

        if event == 'line' or event == 'return':
            current_locals = frame.f_locals.copy()
            line_no = frame.f_lineno

            # Detect new and changed variables
            for name, value in current_locals.items():
                if name.startswith('_'):
                    continue

                if name not in self.previous_locals:
                    # New variable
                    self.changes.append(('new', name, value, line_no))
                    ScanPrinter.new_variable(name, value, line_no)
                elif name in self.previous_locals:
                    old_val = self.previous_locals[name]
                    try:
                        # Check if value changed (handle unhashable types)
                        if old_val is not value and old_val != value:
                            self.changes.append(('change', name, old_val, value, line_no))
                            ScanPrinter.variable_change(name, old_val, value, line_no)
                    except (TypeError, ValueError):
                        # For unhashable types, use identity check
                        if old_val is not value:
                            self.changes.append(('change', name, old_val, value, line_no))
                            ScanPrinter.variable_change(name, old_val, value, line_no)

            self.previous_locals = current_locals.copy()

        return self.trace_lines


def scan(func):
    """
    Decorator that provides real-time variable tracking with beautiful output.

    The scan decorator instruments a function to track all variable assignments
    as they happen, displaying them in a beautifully formatted, color-coded
    terminal output. It's an invaluable tool for debugging and understanding
    code flow.

    Parameters
    ----------
    func : callable
        The function to scan. Can be synchronous or asynchronous.

    Returns
    -------
    callable
        The wrapped function with variable tracking enabled.

    Output Sections
    ---------------
    The scan output includes the following sections:

    1. **Header**: Function name and module
    2. **Parameters**: Input arguments with types and values
    3. **Variables**: Each new variable assignment (with line number)
    4. **Return**: The return value with type
    5. **Footer**: Execution time in milliseconds

    Color Coding
    ------------
    Variables are color-coded by type for easy identification:

    - **int**: Bright blue
    - **float**: Deep blue
    - **str**: Orange (with length shown)
    - **bool**: Magenta
    - **None**: Gray
    - **list**: Sea green (with length shown)
    - **dict**: Gold (with size shown)
    - **tuple**: Light purple (with length shown)
    - **set**: Pink (with size shown)
    - **callable**: Cyan
    - **objects**: Lavender

    Examples
    --------
    Basic usage:

    >>> from steely import Dan
    >>> @Dan.scan
    ... def calculate(x, y):
    ...     total = x + y
    ...     multiplied = total * 2
    ...     return multiplied
    >>> calculate(5, 3)
    # Output:
    # ┌──────────────────────────────────────────────────────────┐
    # │ ⚡ SCAN │ calculate @ __main__
    # ├──────────────────────────────────────────────────────────┤
    # │ Parameters:
    # │    ◈ x : int = 5
    # │    ◈ y : int = 3
    # ├──────────────────────────────────────────────────────────┤
    # │ L3 ◈ total : int = 8
    # │ L4 ◈ multiplied : int = 16
    # ├──────────────────────────────────────────────────────────┤
    # │ ⟼ return : int = 16
    # ├──────────────────────────────────────────────────────────┤
    # │ ✓ Completed in 0.123ms
    # └──────────────────────────────────────────────────────────┘
    16

    With different types:

    >>> @Dan.scan
    ... def process_data():
    ...     name = "Alice"
    ...     scores = [95, 87, 92]
    ...     info = {"student": name, "grades": scores}
    ...     return info

    Async function:

    >>> @Dan.scan
    ... async def fetch_user(user_id):
    ...     user = await database.get_user(user_id)
    ...     return user

    Notes
    -----
    - Uses sys.settrace for tracking, which may impact performance.
      Best used for debugging, not in production.
    - Variables starting with underscore (_) are filtered out.
    - The original function signature is preserved for framework compatibility.
    - Exceptions are displayed and then re-raised.

    See Also
    --------
    Dan.log : Decorator for logging function lifecycle.
    Dan.cronos : Decorator for timing function execution.
    """

    # Get function info
    module_name = getattr(inspect.getmodule(func), '__name__', '__main__')
    sig = inspect.signature(func)
    param_names = list(sig.parameters.keys())

    if asyncio.iscoroutinefunction(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = datetime.now()

            # Print header
            ScanPrinter.header(func.__name__, module_name)
            ScanPrinter.signature(sig, args, kwargs, param_names)

            # Set up tracing
            tracker = VariableTracker(func.__code__)
            tracker.active = True
            old_trace = sys.gettrace()
            sys.settrace(tracker.trace_calls)

            try:
                result = await func(*args, **kwargs)
                ScanPrinter.return_value(result)
                return result
            except Exception as e:
                ScanPrinter.exception(e)
                raise
            finally:
                sys.settrace(old_trace)
                tracker.active = False
                elapsed = (datetime.now() - start).total_seconds() * 1000
                ScanPrinter.footer(elapsed)

        async_wrapper.__signature__ = sig
        return async_wrapper
    else:
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = datetime.now()

            # Print header
            ScanPrinter.header(func.__name__, module_name)
            ScanPrinter.signature(sig, args, kwargs, param_names)

            # Set up tracing
            tracker = VariableTracker(func.__code__)
            tracker.active = True
            old_trace = sys.gettrace()
            sys.settrace(tracker.trace_calls)

            try:
                result = func(*args, **kwargs)
                ScanPrinter.return_value(result)
                return result
            except Exception as e:
                ScanPrinter.exception(e)
                raise
            finally:
                sys.settrace(old_trace)
                tracker.active = False
                elapsed = (datetime.now() - start).total_seconds() * 1000
                ScanPrinter.footer(elapsed)

        sync_wrapper.__signature__ = sig
        return sync_wrapper
