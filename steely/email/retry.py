"""
Tiny retry helper used by the HTTP API providers (Resend / generic).

``with_retry`` retries a callable when it raises one of ``retry_on`` (by
default :class:`RetryableError`), backing off exponentially. Providers raise
:class:`RetryableError` for transient conditions (HTTP 429 / 5xx / network
errors) and let permanent failures (4xx) fall through untouched.

The ``sleep`` argument is injectable so tests can run without real delays.
"""
from __future__ import annotations

import time
from functools import wraps
from typing import Callable, Optional, Tuple, Type


class RetryableError(Exception):
    """Raised inside a retried function to force another attempt."""


def with_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    backoff: float = 2.0,
    retry_on: Tuple[Type[BaseException], ...] = (RetryableError,),
    sleep: Optional[Callable[[float], None]] = None,
):
    """Decorator that retries ``fn`` up to ``max_attempts`` times.

    Parameters
    ----------
    max_attempts:
        Total attempts (not *additional* retries). ``1`` disables retrying.
    base_delay:
        Seconds to wait before the second attempt.
    backoff:
        Multiplier applied to the delay after each failed attempt.
    retry_on:
        Exception types that trigger a retry. Anything else propagates
        immediately.
    sleep:
        Sleep function (injectable for tests). Resolved at call time; defaults
        to :func:`time.sleep` so patching ``steely.email.retry.time.sleep``
        takes effect without rebinding the default.
    """

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            _sleep = sleep if sleep is not None else time.sleep
            delay = base_delay
            for attempt in range(1, max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except retry_on:
                    if attempt >= max_attempts:
                        raise
                    _sleep(delay)
                    delay *= backoff

        return wrapper

    return decorator
