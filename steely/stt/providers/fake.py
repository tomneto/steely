"""
FakeProvider / FakeSession — an in-memory backend for tests.

Implements the same :class:`STTProvider` / :class:`STTSession` contract as the
real adapters but touches no network: it records pushed frames and emits a
scripted list of :class:`STTEvent` objects. Use it to exercise the interface,
the factory, and any consumer code without any SDK installed.
"""
from __future__ import annotations

from typing import Any, AsyncIterator, List, Optional

from steely.stt.base import STTProvider, STTSession
from steely.stt.config import STTConfig
from steely.stt.event import EventType, STTEvent
from steely.stt.reconnect import ReconnectPolicy


def _default_script() -> List[STTEvent]:
    return [
        STTEvent(EventType.INTERIM, "ola", 0, 300, language="pt-BR"),
        STTEvent(EventType.INTERIM, "ola mun", 0, 600, language="pt-BR"),
        STTEvent(EventType.FINAL, "olá mundo", 0, 900, language="pt-BR"),
    ]


class FakeSession(STTSession):
    """In-memory session: records pushed frames, emits scripted events."""

    def __init__(self, config: STTConfig, script: Optional[List[STTEvent]] = None) -> None:
        self.config = config
        self.pushed: List[bytes] = []
        self.ended = False
        self.closed = False
        self._script = list(script) if script is not None else _default_script()
        self._i = 0

    async def push_frame(self, frame: bytes) -> None:
        if self.closed:
            raise RuntimeError("push_frame after close")
        self.pushed.append(frame)

    async def end_input(self) -> None:
        self.ended = True

    async def aclose(self) -> None:
        self.closed = True

    def __aiter__(self) -> AsyncIterator[STTEvent]:
        return self

    async def __anext__(self) -> STTEvent:
        if self._i >= len(self._script):
            raise StopAsyncIteration
        ev = self._script[self._i]
        self._i += 1
        return ev


class FakeProvider(STTProvider):
    """A backend that returns :class:`FakeSession` instances.

    Parameters
    ----------
    script:
        Optional list of events every opened session will emit. Defaults to a
        short pt-BR interim->final sequence.
    """

    def __init__(self, script: Optional[List[STTEvent]] = None, **_: Any) -> None:
        self._script = script

    @property
    def name(self) -> str:
        return "fake"

    async def open_session(
        self,
        config: STTConfig,
        *,
        reconnect: Optional[ReconnectPolicy] = None,
        **kwargs: Any,
    ) -> STTSession:
        return FakeSession(config, self._script)

    def validate(self) -> bool:
        return True
