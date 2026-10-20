"""
ReconnectPolicy — the reconnection extension point for :mod:`steely.stt`.

This is the async analog of ``steely.email``'s ``with_retry`` decorator, adapted
to a long-lived duplex connection. :class:`~steely.stt.session.QueueSession`
consults a policy inside its background receive pump: when the backend drops with
a retryable error, the pump backs off and re-opens the stream transparently, so
the consumer's ``async for`` only ever sees a brief pause — never the drop.

Subclass or instantiate with different parameters to change behavior; the
async-iterator contract is unchanged, so reconnection stays invisible.
"""
from __future__ import annotations

import asyncio
import random

from steely.stt.errors import STTConnectionError


class ReconnectPolicy:
    """Exponential-backoff-with-jitter reconnection strategy.

    Parameters
    ----------
    max_retries:
        Maximum consecutive reconnect attempts before giving up. ``0`` disables
        reconnection entirely.
    base_delay:
        Seconds to wait before the first reconnect.
    backoff:
        Multiplier applied to the delay after each attempt.
    max_delay:
        Upper bound on the backoff delay.
    jitter:
        Maximum extra random seconds added to each delay (avoids thundering
        herds when many sessions drop together).
    retryable_excs:
        Exception types the pump treats as reconnectable. Defaults to
        :class:`~steely.stt.errors.STTConnectionError`.
    sleep:
        Async sleep function (injectable for tests). Defaults to
        :func:`asyncio.sleep`.
    """

    def __init__(
        self,
        max_retries: int = 5,
        base_delay: float = 0.5,
        backoff: float = 2.0,
        max_delay: float = 10.0,
        jitter: float = 0.3,
        retryable_excs: tuple[type[BaseException], ...] = (STTConnectionError,),
        sleep=None,
    ) -> None:
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.backoff = backoff
        self.max_delay = max_delay
        self.jitter = jitter
        self.retryable_excs = retryable_excs
        self._sleep = sleep if sleep is not None else asyncio.sleep
        self._attempt = 0

    def should_retry(self, exc: BaseException) -> bool:
        """Return whether to reconnect after ``exc``.

        Override to inspect the error, cap by wall-clock, etc. A
        :class:`STTConnectionError` flagged ``retryable=False`` is never retried.
        """
        if isinstance(exc, STTConnectionError) and not exc.retryable:
            return False
        return self._attempt < self.max_retries

    async def backoff_sleep(self) -> None:
        """Async-sleep before the next reconnect (exponential + jitter)."""
        delay = min(self.base_delay * (self.backoff ** self._attempt), self.max_delay)
        delay += random.uniform(0, self.jitter)
        self._attempt += 1
        await self._sleep(delay)

    def reset(self) -> None:
        """Reset the attempt counter after a successful reconnect + first event."""
        self._attempt = 0
