"""
AzureProvider — streaming STT via Azure AI Speech.

Requires the optional ``azure-cognitiveservices-speech`` dependency::

    pip install "steely[stt-azure]"

Credentials come from ``subscription_key`` + ``region`` kwargs or the
``AZURE_SPEECH_KEY`` + ``AZURE_SPEECH_REGION`` environment variables. Canonical
``"pt-BR"`` maps straight through.

The Azure SDK is callback-based and fires ``recognizing``/``recognized`` on its
own threads, so this adapter bridges them onto the asyncio queue via
:class:`~steely.stt.session.CallbackQueueSession`. Audio is fed through a
``PushAudioInputStream`` of 16 kHz/16-bit/mono PCM.
"""
from __future__ import annotations

import asyncio
import os
from typing import Any

from steely.stt.base import STTProvider, STTSession, redact
from steely.stt.config import STTConfig
from steely.stt.errors import ProviderNotAvailableError, STTConfigError, STTConnectionError
from steely.stt.event import EventType, STTEvent
from steely.stt.languages import to_provider_language
from steely.stt.reconnect import ReconnectPolicy
from steely.stt.session import CallbackQueueSession

# Azure reports offsets/durations in 100-nanosecond "ticks".
_TICKS_PER_MS = 10_000


class AzureSession(CallbackQueueSession):
    """Live Azure session. Backend wants 16 kHz 16-bit PCM mono."""

    BACKEND_RATE = 16000
    BACKEND_ENCODING = "pcm_s16le"

    def __init__(self, provider: AzureProvider, config: STTConfig, **opts: Any) -> None:
        super().__init__(config, reconnect=opts.pop("reconnect", None))
        self._provider = provider
        self._opts = opts
        self._push_stream: Any = None
        self._recognizer: Any = None

    async def _connect(self, config: STTConfig) -> Any:
        speechsdk = self._provider._sdk
        speech_config = speechsdk.SpeechConfig(
            subscription=self._provider._key, region=self._provider._region
        )
        speech_config.speech_recognition_language = to_provider_language("azure", config.language)

        stream_format = speechsdk.audio.AudioStreamFormat(
            samples_per_second=self.BACKEND_RATE, bits_per_sample=16, channels=1
        )
        push_stream = speechsdk.audio.PushAudioInputStream(stream_format)
        audio_config = speechsdk.audio.AudioConfig(stream=push_stream)
        recognizer = speechsdk.SpeechRecognizer(
            speech_config=speech_config, audio_config=audio_config
        )

        if config.interim_results:
            recognizer.recognizing.connect(lambda evt: self._on_result(evt, EventType.INTERIM))
        recognizer.recognized.connect(lambda evt: self._on_result(evt, EventType.FINAL))
        recognizer.canceled.connect(self._on_canceled)
        recognizer.session_stopped.connect(lambda evt: self.emit_end())

        try:
            await asyncio.to_thread(recognizer.start_continuous_recognition_async().get)
        except Exception as exc:  # noqa: BLE001
            raise STTConnectionError(f"Azure start failed: {exc}") from exc

        self._push_stream = push_stream
        self._recognizer = recognizer
        return recognizer

    def _on_result(self, evt: Any, kind: EventType) -> None:
        try:
            text = evt.result.text
            if not text:
                return
            start_ms = int(getattr(evt.result, "offset", 0) / _TICKS_PER_MS)
            end_ms = start_ms + int(getattr(evt.result, "duration", 0) / _TICKS_PER_MS)
            self.emit(
                STTEvent(
                    type=kind,
                    text=text,
                    start=start_ms,
                    end=end_ms,
                    language=self._config.language,
                )
            )
        except Exception as exc:  # noqa: BLE001
            self.emit_error(STTConnectionError(f"Azure parse error: {exc}"))

    def _on_canceled(self, evt: Any) -> None:
        reason = getattr(evt, "error_details", None) or getattr(evt, "reason", "canceled")
        self.emit_error(STTConnectionError(f"Azure canceled: {reason}", retryable=True))

    async def _send_bytes(self, conn: Any, pcm: bytes) -> None:
        self._push_stream.write(pcm)

    async def _signal_end(self, conn: Any) -> None:
        self._push_stream.close()

    async def _close_conn(self, conn: Any) -> None:
        try:
            self._push_stream.close()
        finally:
            await asyncio.to_thread(conn.stop_continuous_recognition_async().get)


class AzureProvider(STTProvider):
    """Azure AI Speech streaming backend.

    Parameters
    ----------
    subscription_key:
        Azure Speech key. Falls back to ``AZURE_SPEECH_KEY``.
    region:
        Azure region (e.g. ``"brazilsouth"``). Falls back to ``AZURE_SPEECH_REGION``.
    """

    def __init__(
        self,
        subscription_key: str | None = None,
        region: str | None = None,
        **_: Any,
    ) -> None:
        key = subscription_key or os.environ.get("AZURE_SPEECH_KEY")
        reg = region or os.environ.get("AZURE_SPEECH_REGION")
        if not key or not reg:
            raise STTConfigError(
                "AzureProvider requires subscription_key + region "
                "(or AZURE_SPEECH_KEY + AZURE_SPEECH_REGION)"
            )
        try:
            import azure.cognitiveservices.speech as speechsdk
        except ImportError as exc:  # pragma: no cover - exercised via monkeypatch
            raise ProviderNotAvailableError(
                "AzureProvider requires 'azure-cognitiveservices-speech'. Install with: "
                "pip install 'steely[stt-azure]'"
            ) from exc
        self._sdk = speechsdk
        self._key = key
        self._region = reg
        self._redacted = redact(key)

    @property
    def name(self) -> str:
        return "azure"

    async def open_session(
        self,
        config: STTConfig,
        *,
        reconnect: ReconnectPolicy | None = None,
        **kwargs: Any,
    ) -> STTSession:
        session = AzureSession(self, config, reconnect=reconnect, **kwargs)
        await session._start()
        return session
