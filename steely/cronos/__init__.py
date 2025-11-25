"""
Cronos Module - Execution Time Measurement
==========================================

Named after the Greek god of time (Kronos/Chronos), this module provides
a decorator for measuring and reporting function execution times.

The cronos decorator is useful for:
- Performance profiling and benchmarking
- Identifying slow functions in your codebase
- Monitoring execution times in development and testing

Features
--------
- Automatic timing of function execution
- Support for both sync and async functions
- Beautiful colored output using the Logger system
- Preserves function signatures for framework compatibility

Examples
--------
Basic timing:

>>> from steely import Dan
>>> @Dan.cronos
... def slow_function():
...     time.sleep(1)
...     return "done"
>>> slow_function()
# Output: [TEST-RESULT]: Total Time Elapsed: 0:00:01.001234
'done'

Timing async functions:

>>> @Dan.cronos
... async def fetch_data():
...     await asyncio.sleep(0.5)
...     return {"data": "value"}

Combining with other decorators:

>>> @Dan.log
... @Dan.cronos
... def important_operation():
...     # This logs start/success AND execution time
...     pass
"""

import asyncio
import inspect
from datetime import datetime
from functools import wraps

from steely.logger import Logger

__all__ = ["cronos"]


def cronos(func):
    """
    Decorator that measures and reports function execution time.

    This decorator wraps a function to measure its execution duration from
    start to finish, then logs the elapsed time using the Logger system.
    The timing is always reported, even if the function raises an exception.

    Parameters
    ----------
    func : callable
        The function to time. Can be synchronous or asynchronous.

    Returns
    -------
    callable
        The wrapped function that reports its execution time.

    Output Format
    -------------
    The decorator logs timing information in the format::

        [*-CRONOS-*] [FUNCTION_NAME] [TEST-RESULT]: Total Time Elapsed: H:MM:SS.ffffff

    Where:
    - H:MM:SS.ffffff is the elapsed time (hours:minutes:seconds.microseconds)
    - FUNCTION_NAME is the decorated function's name in uppercase

    Examples
    --------
    Basic usage:

    >>> from steely import Dan
    >>> import time
    >>> @Dan.cronos
    ... def compute():
    ...     time.sleep(0.1)
    ...     return 42
    >>> result = compute()
    # Logs: Total Time Elapsed: 0:00:00.100xxx
    >>> result
    42

    With async function:

    >>> @Dan.cronos
    ... async def async_task():
    ...     await asyncio.sleep(0.5)
    ...     return "completed"
    >>> await async_task()
    # Logs: Total Time Elapsed: 0:00:00.500xxx
    'completed'

    Timing even with exceptions:

    >>> @Dan.cronos
    ... def failing_function():
    ...     time.sleep(0.1)
    ...     raise ValueError("Error!")
    >>> failing_function()
    # Logs: Total Time Elapsed: 0:00:00.100xxx (logged before exception)
    # ValueError: Error!

    Notes
    -----
    - The elapsed time includes all time spent in the function, including
      any I/O waits, sleep calls, or blocking operations.
    - The original function signature is preserved for compatibility with
      frameworks like FastAPI that rely on signature introspection.
    - The timing is always logged via a background thread for non-blocking
      behavior.
    - For async functions, the time includes await durations.

    See Also
    --------
    Dan.log : Decorator for logging function execution lifecycle.
    Dan.scan : Decorator for tracking variable assignments.
    """
    log = Logger('*-cronos-*', func.__name__).log

    if asyncio.iscoroutinefunction(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = datetime.now()
            try:
                res = await func(*args, **kwargs)
            finally:
                time_elapsed = datetime.now() - start
                log('TEST-RESULT', f'Total Time Elapsed: {time_elapsed}')
            return res

        # Preserve the original signature for FastAPI
        async_wrapper.__signature__ = inspect.signature(func)
        return async_wrapper
    else:
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = datetime.now()
            try:
                res = func(*args, **kwargs)
            finally:
                time_elapsed = datetime.now() - start
                log('TEST-RESULT', f'Total Time Elapsed: {time_elapsed}')
            return res

        # Preserve the original signature for FastAPI
        sync_wrapper.__signature__ = inspect.signature(func)
        return sync_wrapper
