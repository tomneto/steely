"""
FakeProvider / FakeSession — an in-memory backend for tests.

Implements the same :class:`TTSProvider` / :class:`TTSSession` contract as the
real adapters but touches no network: it records pushed text and emits a scripted
list of :class:`AudioChunk` objects. Use it to exercise the interface, the
factory, and any consumer code without any SDK installed.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from steely.tts.audio_chunk import AudioChunk
from steely.tts.base import TTSProvider, TTSSession
from steely.tts.config import TTSConfig
from steely.tts.reconnect import ReconnectPolicy


def _default_script() -> list[AudioChunk]:
    return [
        AudioChunk(b"\x01\x02" * 80, index=0, is_final=False, duration_ms=100),
        AudioChunk(b"\x03\x04" * 80, index=1, is_final=False, duration_ms=100),
        AudioChunk(b"\x05\x06" * 80, index=2, is_final=True, duration_ms=100),
    ]


class FakeSession(TTSSession):
    """In-memory session: records pushed text, emits scripted audio chunks."""

    def __init__(self, config: TTSConfig, script: list[AudioChunk] | None = None) -> None:
        self.config = config
        self.pushed: list[str] = []
        self.ended = False
        self.closed = False
        self._script = list(script) if script is not None else _default_script()
        self._i = 0

    async def push_text(self, text: str) -> None:
        if self.closed:
            raise RuntimeError("push_text after close")
        self.pushed.append(text)

    async def end_input(self) -> None:
        self.ended = True

    async def aclose(self) -> None:
        self.closed = True

    def __aiter__(self) -> AsyncIterator[AudioChunk]:
        return self

    async def __anext__(self) -> AudioChunk:
        if self._i >= len(self._script):
            raise StopAsyncIteration
        chunk = self._script[self._i]
        self._i += 1
        return chunk


class FakeProvider(TTSProvider):
    """A backend that returns :class:`FakeSession` instances.

    Parameters
    ----------
    script:
        Optional list of chunks every opened session will emit. Defaults to a
        short three-chunk sequence ending with ``is_final=True``.
    """

    def __init__(self, script: list[AudioChunk] | None = None, **_: Any) -> None:
        self._script = script

    @property
    def name(self) -> str:
        return "fake"

    async def open_session(
        self,
        config: TTSConfig,
        *,
        reconnect: ReconnectPolicy | None = None,
        **kwargs: Any,
    ) -> TTSSession:
        return FakeSession(config, self._script)

    def validate(self) -> bool:
        return True
