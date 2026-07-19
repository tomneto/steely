"""Tests for the QueueSession core: pump, error propagation, reconnection.

These drive a QueueSession subclass whose backend hooks are in-memory, so the
receive pump / async-iterator / reconnect logic is exercised without any network
or SDK.
"""

import pytest

from steely.stt.config import STTConfig
from steely.stt.errors import STTConnectionError, STTError
from steely.stt.event import EventType, STTEvent
from steely.stt.reconnect import ReconnectPolicy
from steely.stt.session import QueueSession


class ScriptedSession(QueueSession):
    """QueueSession whose _receive replays scripted rounds.

    ``rounds`` is a list of lists; each inner list is what one _receive call
    yields, except a value that is an Exception instance is raised instead. The
    pump advances to the next round on each (re)connect.
    """

    BACKEND_RATE = 16000

    @property
    def name(self) -> str:
        return "scripted"

    def __init__(self, config, *, reconnect=None, rounds=None):
        super().__init__(config, reconnect=reconnect)
        self._rounds = list(rounds or [])
        self._round = 0
        self.connects = 0
        self.sent = []
        self.ended = False
        self.conn_closed = False

    async def _connect(self, config):
        self.connects += 1
        return object()

    async def _receive(self, conn):
        if self._round >= len(self._rounds):
            return
        items = self._rounds[self._round]
        self._round += 1
        for item in items:
            if isinstance(item, BaseException):
                raise item
            yield item

    async def _send_bytes(self, conn, pcm):
        self.sent.append(pcm)

    async def _signal_end(self, conn):
        self.ended = True

    async def _close_conn(self, conn):
        self.conn_closed = True


def _ev(text, t):
    return STTEvent(EventType.FINAL, text, t, t + 100, language="pt-BR")


@pytest.mark.asyncio
async def test_clean_stream_ends_with_stop_async_iteration():
    session = ScriptedSession(STTConfig(), rounds=[[_ev("a", 0), _ev("b", 100)]])
    await session._start()
    async with session:
        out = [ev async for ev in session]
    assert [e.text for e in out] == ["a", "b"]
    assert session.connects == 1


@pytest.mark.asyncio
async def test_fatal_error_propagates_to_consumer():
    # non-retryable error -> surfaces out of the async for as STTConnectionError
    boom = STTConnectionError("stream exploded", retryable=False)
    session = ScriptedSession(STTConfig(), rounds=[[_ev("a", 0), boom]])
    await session._start()
    collected = []
    with pytest.raises(STTError):
        async with session:
            async for ev in session:
                collected.append(ev)
    assert [e.text for e in collected] == ["a"]


@pytest.mark.asyncio
async def test_transparent_reconnect_is_invisible_to_consumer():
    # round 1 drops with a retryable error after one event; round 2 completes.
    policy = ReconnectPolicy(max_retries=3, base_delay=0, jitter=0, sleep=_no_sleep)
    session = ScriptedSession(
        STTConfig(),
        reconnect=policy,
        rounds=[
            [_ev("first", 0), STTConnectionError("drop", retryable=True)],
            [_ev("second", 100), _ev("third", 200)],
        ],
    )
    await session._start()
    async with session:
        out = [ev async for ev in session]
    # consumer sees an uninterrupted sequence across the reconnect
    assert [e.text for e in out] == ["first", "second", "third"]
    assert session.connects == 2  # initial + one reconnect


@pytest.mark.asyncio
async def test_retries_exhausted_surface_error():
    policy = ReconnectPolicy(max_retries=1, base_delay=0, jitter=0, sleep=_no_sleep)
    session = ScriptedSession(
        STTConfig(),
        reconnect=policy,
        rounds=[
            [STTConnectionError("drop1", retryable=True)],
            [STTConnectionError("drop2", retryable=True)],
        ],
    )
    await session._start()
    with pytest.raises(STTConnectionError):
        async with session:
            async for _ in session:
                pass


@pytest.mark.asyncio
async def test_push_frame_resamples_and_forwards():
    session = ScriptedSession(STTConfig(sample_rate=48000, channels=1), rounds=[[]])
    await session._start()
    async with session:
        await session.push_frame(b"\x00\x01" * 480)  # 480 samples @48k
        _ = [ev async for ev in session]
    assert len(session.sent) == 1
    # resampled 48k -> 16k roughly thirds the byte count
    assert 0 < len(session.sent[0]) < 480 * 2


@pytest.mark.asyncio
async def test_push_after_close_raises():
    session = ScriptedSession(STTConfig(), rounds=[[]])
    await session._start()
    await session.aclose()
    with pytest.raises(STTError):
        await session.push_frame(b"\x00\x01")


async def _no_sleep(_delay):
    return None
