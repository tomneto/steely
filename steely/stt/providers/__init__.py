"""
Streaming STT providers.

- :class:`DeepgramProvider`          — Deepgram live WebSocket (``steely[stt-deepgram]``).
- :class:`AssemblyAIProvider`        — AssemblyAI realtime (``steely[stt-assemblyai]``).
- :class:`GoogleProvider`            — Google Cloud Speech / Chirp (``steely[stt-google]``).
- :class:`AzureProvider`             — Azure AI Speech (``steely[stt-azure]``).
- :class:`AmazonTranscribeProvider`  — Amazon Transcribe (``steely[stt-aws]``).
- :class:`WhisperLiveProvider`       — faster-whisper self-hosted (``steely[stt-whisperlive]``).
- :class:`FakeProvider`              — in-memory backend for tests (no deps).

Importing this package is always safe: each provider imports its SDK lazily
inside its own constructor, so ``import`` never fails when an SDK is absent —
only *constructing* that provider does (raising ``ProviderNotAvailableError``).
"""
from steely.stt.providers.assemblyai import AssemblyAIProvider
from steely.stt.providers.aws import AmazonTranscribeProvider
from steely.stt.providers.azure import AzureProvider
from steely.stt.providers.deepgram import DeepgramProvider
from steely.stt.providers.fake import FakeProvider, FakeSession
from steely.stt.providers.google import GoogleProvider
from steely.stt.providers.whisperlive import WhisperLiveProvider

__all__ = [
    "DeepgramProvider",
    "AssemblyAIProvider",
    "GoogleProvider",
    "AzureProvider",
    "AmazonTranscribeProvider",
    "WhisperLiveProvider",
    "FakeProvider",
    "FakeSession",
]
