"""
GoogleProvider — streaming STT via Google Cloud Speech-to-Text (incl. Chirp).

Requires the optional ``google-cloud-speech`` dependency::

    pip install "steely[stt-google]"

Auth uses Application Default Credentials: point ``GOOGLE_APPLICATION_CREDENTIALS``
at a service-account JSON, or pass ``credentials_path=...``. The canonical
``"pt-BR"`` maps straight through. Registered under both ``"google"`` and
``"chirp"`` in the factory (pass ``model="chirp"`` / ``"chirp_2"`` to use Chirp).

Google's async streaming API is *pull-based*: it consumes an async iterator of
requests and yields an async iterator of responses. This adapter feeds audio
through an internal queue that backs the request iterator, and translates the
response iterator inside :meth:`_receive`.
"""
from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from typing import Any

from steely.stt.base import STTProvider, STTSession, redact
from steely.stt.config import STTConfig
from steely.stt.errors import ProviderNotAvailableError, STTConfigError, STTConnectionError
from steely.stt.event import EventType, STTEvent
from steely.stt.languages import to_provider_language
from steely.stt.reconnect import ReconnectPolicy
from steely.stt.session import QueueSession

_AUDIO_END: Any = object()


class GoogleSession(QueueSession):
    """Live Google Cloud Speech session. Backend wants 16 kHz LINEAR16 mono."""

    BACKEND_RATE = 16000
    BACKEND_ENCODING = "pcm_s16le"

    def __init__(self, provider: GoogleProvider, config: STTConfig, **opts: Any) -> None:
        super().__init__(config, reconnect=opts.pop("reconnect", None))
        self._provider = provider
        self._opts = opts
        self._audio: asyncio.Queue[Any] = asyncio.Queue()

    async def _requests(self, streaming_config: Any) -> AsyncIterator[Any]:
        speech = self._provider._speech
        yield speech.StreamingRecognizeRequest(streaming_config=streaming_config)
        while True:
            chunk = await self._audio.get()
            if chunk is _AUDIO_END:
                return
            yield speech.StreamingRecognizeRequest(audio_content=chunk)

    async def _connect(self, config: STTConfig) -> Any:
        speech = self._provider._speech
        client = self._provider._client
        recognition_config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=self.BACKEND_RATE,
            language_code=to_provider_language("google", config.language),
            model=None if config.model == "default" else config.model,
        )
        streaming_config = speech.StreamingRecognitionConfig(
            config=recognition_config,
            interim_results=config.interim_results,
        )
        try:
            responses = await client.streaming_recognize(
                requests=self._requests(streaming_config)
            )
        except Exception as exc:  # noqa: BLE001
            raise STTConnectionError(f"Google streaming_recognize failed: {exc}") from exc
        return responses

    async def _receive(self, conn: Any) -> AsyncIterator[STTEvent]:
        try:
            async for response in conn:
                for result in response.results:
                    if not result.alternatives:
                        continue
                    alt = result.alternatives[0]
                    text = alt.transcript
                    if not text:
                        continue
                    end_ms = _duration_ms(getattr(result, "result_end_time", None))
                    start_ms = _word_start_ms(alt, default=end_ms)
                    yield STTEvent(
                        type=EventType.FINAL if result.is_final else EventType.INTERIM,
                        text=text,
                        start=start_ms,
                        end=end_ms,
                        confidence=getattr(alt, "confidence", None) or None,
                        language=self._config.language,
                    )
        except Exception as exc:  # noqa: BLE001 - normalize to the common error
            raise STTConnectionError(f"Google stream error: {exc}", retryable=True) from exc

    async def _send_bytes(self, conn: Any, pcm: bytes) -> None:
        await self._audio.put(pcm)

    async def _signal_end(self, conn: Any) -> None:
        await self._audio.put(_AUDIO_END)

    async def _close_conn(self, conn: Any) -> None:
        await self._audio.put(_AUDIO_END)


def _duration_ms(duration: Any) -> int:
    """Convert a protobuf Duration (or timedelta) to integer milliseconds."""
    if duration is None:
        return 0
    try:
        return int(duration.total_seconds() * 1000)
    except AttributeError:
        seconds = getattr(duration, "seconds", 0) or 0
        nanos = getattr(duration, "nanos", 0) or 0
        return int(seconds * 1000 + nanos / 1_000_000)


def _word_start_ms(alt: Any, default: int) -> int:
    words = getattr(alt, "words", None)
    if words:
        return _duration_ms(getattr(words[0], "start_time", None))
    return default


class GoogleProvider(STTProvider):
    """Google Cloud Speech-to-Text streaming backend.

    Parameters
    ----------
    credentials_path:
        Optional path to a service-account JSON. If given, it is exported as
        ``GOOGLE_APPLICATION_CREDENTIALS`` so ADC picks it up.
    """

    def __init__(self, credentials_path: str | None = None, **_: Any) -> None:
        if credentials_path:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
        try:
            from google.cloud import speech_v1 as speech
        except ImportError as exc:  # pragma: no cover - exercised via monkeypatch
            raise ProviderNotAvailableError(
                "GoogleProvider requires 'google-cloud-speech'. Install with: "
                "pip install 'steely[stt-google]'"
            ) from exc
        try:
            self._client = speech.SpeechAsyncClient()
        except Exception as exc:  # noqa: BLE001 - missing/invalid credentials
            raise STTConfigError(f"Google credentials not usable: {exc}") from exc
        self._speech = speech
        self._redacted = redact(
            credentials_path or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        )

    @property
    def name(self) -> str:
        return "google"

    async def open_session(
        self,
        config: STTConfig,
        *,
        reconnect: ReconnectPolicy | None = None,
        **kwargs: Any,
    ) -> STTSession:
        session = GoogleSession(self, config, reconnect=reconnect, **kwargs)
        await session._start()
        return session
