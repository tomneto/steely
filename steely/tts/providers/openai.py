"""
OpenAIProvider — text-to-speech via OpenAI's ``/v1/audio/speech`` endpoint.

A one-shot HTTP backend: it buffers pushed text and, on :meth:`end_input`, makes
a single request and returns the whole clip as one final :class:`AudioChunk`.
Because it does not stream, it implements :class:`TTSSession` directly rather
than going through :class:`~steely.tts.session.QueueSession`.

Install: ``pip install "steely[tts-openai]"`` (needs ``httpx``). The API key
comes from the ``api_key`` kwarg or the ``OPENAI_API_KEY`` environment variable.
"""
from __future__ import annotations

import os
from typing import Any, AsyncIterator, List, Optional

from steely.tts.audio_chunk import AudioChunk
from steely.tts.base import TTSProvider, TTSSession, redact
from steely.tts.config import TTSConfig
from steely.tts.errors import (
    ProviderNotAvailableError,
    TTSConfigError,
    TTSConnectionError,
    TTSError,
)
from steely.tts.reconnect import ReconnectPolicy

# OpenAI's canonical -> response_format container names.
_FORMATS = {"pcm": "pcm", "mp3": "mp3", "wav": "wav", "opus": "opus", "flac": "flac", "aac": "aac"}


class OpenAISession(TTSSession):
    """One-shot session: buffers text, synthesizes on ``end_input``."""

    def __init__(self, provider: "OpenAIProvider", config: TTSConfig) -> None:
        self._provider = provider
        self._config = config
        self._buf: List[str] = []
        self._chunks: List[AudioChunk] = []
        self._i = 0
        self._done = False
        self.closed = False

    async def push_text(self, text: str) -> None:
        if self.closed:
            raise TTSError("push_text after close")
        self._buf.append(text)

    async def end_input(self) -> None:
        if self._done:
            return
        self._done = True
        audio = await self._provider._synthesize_http("".join(self._buf), self._config)
        self._chunks = [AudioChunk(audio, index=0, is_final=True)]

    async def aclose(self) -> None:
        self.closed = True

    def __aiter__(self) -> AsyncIterator[AudioChunk]:
        return self

    async def __anext__(self) -> AudioChunk:
        if not self._done:
            # Convenience: iterating before end_input() flushes the buffer.
            await self.end_input()
        if self._i >= len(self._chunks):
            raise StopAsyncIteration
        chunk = self._chunks[self._i]
        self._i += 1
        return chunk


class OpenAIProvider(TTSProvider):
    """OpenAI text-to-speech backend.

    Parameters
    ----------
    api_key:
        OpenAI API key. Falls back to ``OPENAI_API_KEY``.
    base_url:
        Override the API base (default ``https://api.openai.com/v1``).
    timeout:
        Per-request timeout in seconds.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        base_url: str = "https://api.openai.com/v1",
        timeout: float = 30.0,
        **_: Any,
    ) -> None:
        try:
            import httpx  # noqa: F401
        except ImportError as exc:  # pragma: no cover - exercised via monkeypatch
            raise ProviderNotAvailableError(
                "OpenAI TTS needs httpx. Install with: pip install \"steely[tts-openai]\""
            ) from exc
        self._httpx = httpx
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self._api_key:
            raise TTSConfigError("OpenAI TTS needs an api_key (or OPENAI_API_KEY env var)")
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self.__logger__ = None  # set lazily to avoid Logger import cost when unused

    @property
    def name(self) -> str:
        return "openai"

    def validate(self) -> bool:
        return bool(self._api_key)

    async def open_session(
        self,
        config: TTSConfig,
        *,
        reconnect: Optional[ReconnectPolicy] = None,
        **kwargs: Any,
    ) -> TTSSession:
        return OpenAISession(self, config)

    def __repr__(self) -> str:  # keep secrets out of logs/reprs
        return f"OpenAIProvider(api_key={redact(self._api_key)})"

    async def _synthesize_http(self, text: str, config: TTSConfig) -> bytes:
        """POST to /audio/speech and return the raw audio bytes."""
        voice = "alloy" if config.voice == "default" else config.voice
        model = "tts-1" if config.model == "default" else config.model
        response_format = _FORMATS.get(config.audio_format, config.audio_format)
        payload = {
            "model": model,
            "voice": voice,
            "input": text,
            "response_format": response_format,
            "speed": config.speed,
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}
        try:
            async with self._httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self._base_url}/audio/speech", json=payload, headers=headers
                )
        except self._httpx.TransportError as exc:
            raise TTSConnectionError(f"OpenAI TTS request failed: {exc}") from exc
        if resp.status_code >= 400:
            retryable = resp.status_code == 429 or resp.status_code >= 500
            raise TTSConnectionError(
                f"OpenAI TTS returned {resp.status_code}: {resp.text[:200]}",
                retryable=retryable,
            )
        return resp.content
