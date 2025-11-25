"""
Steely - A Python Debugging and Analysis Toolkit
=================================================

Steely provides a collection of powerful decorators for debugging, profiling,
and analyzing Python code. It offers beautiful, colorful terminal output to
help developers understand their code's behavior at runtime.

Main Features
-------------
- **Dan.log**: Automatic function logging with start/success/error tracking
- **Dan.cronos**: Execution time measurement and profiling
- **Dan.scan**: Real-time variable tracking with type-colored output

Quick Start
-----------
>>> from steely import Dan
>>>
>>> @Dan.log
... def my_function():
...     return "Hello, World!"
>>>
>>> @Dan.cronos
... def slow_function():
...     time.sleep(1)
...     return "Done"
>>>
>>> @Dan.scan
... def debug_function(x, y):
...     result = x + y
...     return result

For more information, see the individual module documentation.

License
-------
MIT License
"""

from steely.cronos import cronos
from steely.logger import log
from steely.scan import scan

__version__ = "0.1.0"
__author__ = "Steely Contributors"
__all__ = ["Dan", "cronos", "log", "scan"]


class Dan:
    """
    Digital Analyzer (Dan) - A unified interface for code analysis decorators.

    Dan provides a collection of static decorator methods that can be applied
    to functions and methods to add debugging, logging, and profiling capabilities.

    Decorators
    ----------
    log : decorator
        Wraps a function to automatically log execution start, success, and errors.
        Useful for tracking function calls in production and development.

    cronos : decorator
        Measures and reports the execution time of a function.
        Named after the Greek god of time.

    scan : decorator
        Provides real-time variable tracking with beautiful, type-colored output.
        Shows variable assignments, types, values, and return values.

    Examples
    --------
    Using the log decorator:

    >>> @Dan.log
    ... def fetch_data(url):
    ...     return requests.get(url)

    Using the cronos decorator for timing:

    >>> @Dan.cronos
    ... def compute_heavy_task(data):
    ...     return process(data)

    Using the scan decorator for debugging:

    >>> @Dan.scan
    ... def calculate(a, b):
    ...     total = a + b
    ...     squared = total ** 2
    ...     return squared

    Combining decorators:

    >>> @Dan.log
    ... @Dan.cronos
    ... def important_function():
    ...     pass

    Notes
    -----
    All decorators preserve the original function's signature and metadata,
    making them compatible with frameworks like FastAPI that rely on
    function introspection.
    """

    cronos = cronos
    log = log
    scan = scan

@Dan.scan
def main():
    a = 1
    b = 2.5
    c = "hello"
    d = [1, 2, 3]
    e = {"key": "value"}
    f = a + int(b)
    result = f * 2
    return result

if __name__ == "__main__":
    main()