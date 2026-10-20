"""
Abstract contracts for :mod:`steely.tts`.

Every concrete adapter implements :class:`TTSProvider` (which opens sessions) and
returns a :class:`TTSSession` (an async iterator of :class:`AudioChunk`).
Consumers depend only on these two abstractions — never on a concrete backend.

Adding a provider is: subclass both (usually via
:class:`~steely.tts.session.QueueSession` for streaming backends, or
:class:`TTSSession` directly for one-shot HTTP ones), implement the backend
hooks, and register it in ``steely.tts.client._FACTORY``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

from steely.tts.audio_chunk import AudioChunk
from steely.tts.config import TTSConfig
from steely.tts.reconnect import ReconnectPolicy


def redact(secret: Any) -> str:
    """Return a log-safe representation of a secret (``***`` + last 4 chars)."""
    if not secret:
        return "***"
    s = str(secret)
    return "***" + s[-4:] if len(s) > 4 else "***"


class TTSProvider(ABC):
    """Contract implemented by every TTS backend adapter.

    Construction validates credentials/optional deps (raising
    :class:`~steely.tts.errors.ProviderNotAvailableError` early, like the email
    providers). No network connection is opened until :meth:`open_session`.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Short provider id, e.g. ``"elevenlabs"``, ``"openai"``."""

    @abstractmethod
    async def open_session(
        self,
        config: TTSConfig,
        *,
        reconnect: ReconnectPolicy | None = None,
        **kwargs: Any,
    ) -> TTSSession:
        """Open a live synthesis session.

        Returns a *connected* :class:`TTSSession` ready to receive text via
        :meth:`TTSSession.push_text`. ``**kwargs`` are per-session provider
        tuning options.
        """

    async def synthesize(
        self,
        text: str,
        config: TTSConfig,
        **kwargs: Any,
    ) -> bytes:
        """One-shot convenience: synthesize ``text`` and return the full audio.

        Opens a session, pushes the whole text, drains every
        :class:`AudioChunk`, and returns the concatenated audio bytes. Adapters
        with a cheaper non-streaming path may override this.
        """
        session = await self.open_session(config, **kwargs)
        async with session:
            await session.push_text(text)
            await session.end_input()
            return b"".join([chunk.audio async for chunk in session])

    def validate(self) -> bool:
        """Return ``True`` if credentials/config look usable. Must not raise."""
        return True


class TTSSession(ABC):
    """A single live synthesis session; an async iterator of :class:`AudioChunk`.

    Usage::

        session = await provider.open_session(config)
        async with session:
            await session.push_text("Olá, tudo bem?")
            await session.end_input()
            async for chunk in session:
                play(chunk.audio)                # ... is_final on the last one
    """

    @abstractmethod
    async def push_text(self, text: str) -> None:
        """Push a fragment of text to synthesize.

        Streaming backends begin emitting audio as text arrives; one-shot
        backends buffer until :meth:`end_input`.
        """

    @abstractmethod
    async def end_input(self) -> None:
        """Signal that no more text will be pushed.

        The backend flushes its remaining audio, then the stream ends (the
        ``async for`` stops after the last chunk is drained).
        """

    @abstractmethod
    async def aclose(self) -> None:
        """Close the session and release the connection. Idempotent."""

    @abstractmethod
    def __aiter__(self) -> AsyncIterator[AudioChunk]:
        ...

    @abstractmethod
    async def __anext__(self) -> AudioChunk:
        ...

    async def __aenter__(self) -> TTSSession:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.aclose()
