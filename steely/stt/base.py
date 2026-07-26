"""
Abstract contracts for :mod:`steely.stt`.

Every concrete adapter implements :class:`STTProvider` (which opens sessions) and
returns an :class:`STTSession` (an async iterator of :class:`STTEvent`). Consumers
depend only on these two abstractions — never on a concrete backend.

Adding a provider is: subclass both (usually via
:class:`~steely.stt.session.QueueSession` for the session), implement the
backend hooks, and register it in ``steely.stt.client._FACTORY``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Optional

from steely.stt.config import STTConfig
from steely.stt.event import STTEvent
from steely.stt.reconnect import ReconnectPolicy


def redact(secret: Any) -> str:
    """Return a log-safe representation of a secret (``***`` + last 4 chars)."""
    if not secret:
        return "***"
    s = str(secret)
    return "***" + s[-4:] if len(s) > 4 else "***"


class STTProvider(ABC):
    """Contract implemented by every STT backend adapter.

    Construction validates credentials/optional deps (raising
    :class:`~steely.stt.errors.ProviderNotAvailableError` early, like the email
    providers). No network connection is opened until :meth:`open_session`.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Short provider id, e.g. ``"deepgram"``, ``"assemblyai"``."""

    @abstractmethod
    async def open_session(
        self,
        config: STTConfig,
        *,
        reconnect: Optional[ReconnectPolicy] = None,
        **kwargs: Any,
    ) -> "STTSession":
        """Open a live streaming session.

        Returns a *connected* :class:`STTSession` whose background receive loop
        is already running. ``**kwargs`` are per-session provider tuning options
        (e.g. Deepgram ``endpointing=300``).
        """

    def validate(self) -> bool:
        """Return ``True`` if credentials/config look usable. Must not raise."""
        return True


class STTSession(ABC):
    """A single live streaming session; an async iterator of :class:`STTEvent`.

    Usage::

        session = await provider.open_session(config)
        async with session:
            await session.push_frame(frame_bytes)   # raw PCM from LiveKit
            await session.end_input()
            async for event in session:
                handle(event)                       # interim... final
    """

    @abstractmethod
    async def push_frame(self, frame: bytes) -> None:
        """Push one raw audio frame (the worker's native PCM bytes).

        The adapter resamples/transcodes to the backend format internally; the
        frame's format is the one declared in :class:`STTConfig`.
        """

    @abstractmethod
    async def end_input(self) -> None:
        """Signal that no more audio will be pushed.

        The backend flushes its remaining finals, then the event stream ends
        (the ``async for`` stops after the last final is drained).
        """

    @abstractmethod
    async def aclose(self) -> None:
        """Close the session and release the connection. Idempotent."""

    @abstractmethod
    def __aiter__(self) -> AsyncIterator[STTEvent]:
        ...

    @abstractmethod
    async def __anext__(self) -> STTEvent:
        ...

    async def __aenter__(self) -> "STTSession":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.aclose()
