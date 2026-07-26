"""
steely.stt — provider-agnostic streaming speech-to-text.

Push raw audio frames into a session and consume a uniform stream of transcript
events, behind one small async interface. The five initial backends (Deepgram,
AssemblyAI, Google Cloud / Chirp, Azure AI Speech, Amazon Transcribe) each
translate their native protocol into the single canonical :class:`STTEvent`, so
switching providers is a one-line config change.

Quick start
-----------
>>> from steely.stt import STTClient, STTConfig            # doctest: +SKIP
>>> client = STTClient("deepgram", api_key="dg_xxx")       # doctest: +SKIP
>>> session = await client.open_session(STTConfig(language="pt-BR"))  # doctest: +SKIP
>>> async with session:                                    # doctest: +SKIP
...     await session.push_frame(livekit_frame.data.tobytes())
...     await session.end_input()
...     async for event in session:
...         print(event.type, event.text)                  # interim... final

Each backend's SDK is an optional install; ``import steely.stt`` is always safe:

    pip install "steely[stt-deepgram]"     # only Deepgram
    pip install "steely[stt-all]"          # every backend

See ``STT_PROVIDERS.md`` for the full per-provider integration guide (auth,
pt-BR language code, expected sample rate/encoding).
"""
from steely.stt.base import STTProvider, STTSession
from steely.stt.client import STTClient
from steely.stt.config import STTConfig
from steely.stt.errors import (
    ProviderNotAvailableError,
    STTConfigError,
    STTConnectionError,
    STTError,
)
from steely.stt.event import EventType, STTEvent
from steely.stt.reconnect import ReconnectPolicy

__all__ = [
    "STTClient",
    "STTConfig",
    "STTEvent",
    "EventType",
    "STTProvider",
    "STTSession",
    "ReconnectPolicy",
    "STTError",
    "ProviderNotAvailableError",
    "STTConfigError",
    "STTConnectionError",
]
