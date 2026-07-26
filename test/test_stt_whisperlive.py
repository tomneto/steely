"""Tests for the WhisperLive adapter: float32 conversion, segment translation,
adapter-owned endpointing (completed -> FINAL) with dedup — all without a server.
"""

import json
import struct

import pytest

from steely.stt import STTClient, STTConfig
from steely.stt.audio.resample import pcm16le_to_float32le
from steely.stt.errors import ProviderNotAvailableError
from steely.stt.event import EventType
from steely.stt.providers.whisperlive import WhisperLiveSession


def test_whisperlive_registered_in_factory():
    from steely.stt.client import _FACTORY

    assert "whisperlive" in _FACTORY
    assert "whisper" in _FACTORY


def test_provider_not_available_without_websockets():
    # websockets isn't installed in this environment -> loud, at construction.
    with pytest.raises(ProviderNotAvailableError):
        STTClient("whisperlive")


def test_pcm16le_to_float32le_roundtrip():
    pcm = struct.pack("<4h", 0, 32767, -32768, 16384)
    out = pcm16le_to_float32le(pcm)
    floats = struct.unpack("<4f", out)
    assert floats[0] == 0.0
    assert abs(floats[1] - (32767 / 32768.0)) < 1e-6
    assert floats[2] == -1.0
    assert abs(floats[3] - 0.5) < 1e-6


# --- fakes to drive the session without a network -------------------------- #
class _FakeConn:
    def __init__(self, messages):
        self._messages = list(messages)
        self.sent = []
        self.closed = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._messages:
            raise StopAsyncIteration
        return self._messages.pop(0)

    async def send(self, data):
        self.sent.append(data)

    async def close(self):
        self.closed = True


class _FakeWS:
    def __init__(self, conn):
        self._conn = conn

    async def connect(self, url, **kwargs):
        return self._conn


class _DummyProvider:
    def __init__(self, conn, url="ws://localhost:9090"):
        self._ws = _FakeWS(conn)
        self._url = url

    @property
    def name(self):
        return "whisperlive"


def _seg(text, start, end, completed):
    return {"text": text, "start": str(start), "end": str(end), "completed": completed}


@pytest.mark.asyncio
async def test_segment_translation_and_final_dedup():
    # WhisperLive re-sends the growing segment list; completed segments must be
    # emitted as FINAL exactly once, the trailing in-progress one as INTERIM.
    messages = [
        json.dumps({"uid": "x", "message": "SERVER_READY"}),
        json.dumps({"segments": [_seg("olá", 0.0, 0.5, False)]}),
        json.dumps({"segments": [_seg("olá mundo", 0.0, 0.9, True)]}),
        json.dumps({"segments": [
            _seg("olá mundo", 0.0, 0.9, True),          # re-sent -> no dup
            _seg("tudo", 0.9, 1.2, False),
        ]}),
        json.dumps({"segments": [
            _seg("olá mundo", 0.0, 0.9, True),
            _seg("tudo bem", 0.9, 1.5, True),
        ]}),
        json.dumps({"uid": "x", "message": "DISCONNECT"}),
    ]
    conn = _FakeConn(messages)
    session = WhisperLiveSession(_DummyProvider(conn), STTConfig(language="pt-BR"))
    await session._start()
    async with session:
        events = [e async for e in session]

    finals = [e for e in events if e.type is EventType.FINAL]
    interims = [e for e in events if e.type is EventType.INTERIM]
    assert [e.text for e in finals] == ["olá mundo", "tudo bem"]  # each final once
    assert "olá" in [e.text for e in interims]
    # timestamps are integer ms from seconds
    assert finals[0].start == 0 and finals[0].end == 900
    assert finals[1].start == 900 and finals[1].end == 1500
    assert all(e.language == "pt-BR" for e in events)


@pytest.mark.asyncio
async def test_handshake_and_end_of_audio_signal():
    conn = _FakeConn([json.dumps({"uid": "x", "message": "DISCONNECT"})])
    session = WhisperLiveSession(_DummyProvider(conn), STTConfig(language="pt-BR"))
    await session._start()
    async with session:
        await session.push_frame(b"\x00\x01" * 320)   # 16k s16le -> float32 sent
        await session.end_input()
        _ = [e async for e in session]

    # first sent frame is the JSON handshake with mapped language "pt"
    handshake = json.loads(conn.sent[0])
    assert handshake["language"] == "pt"
    assert handshake["use_vad"] is True
    # audio frame was converted to float32 (4 bytes/sample vs 2 in)
    assert isinstance(conn.sent[1], (bytes, bytearray))
    assert len(conn.sent[1]) == 320 * 4
    # end_input sent the END_OF_AUDIO marker
    assert "END_OF_AUDIO" in conn.sent
