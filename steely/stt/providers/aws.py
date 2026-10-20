"""
AmazonTranscribeProvider — streaming STT via Amazon Transcribe.

Requires the optional ``amazon-transcribe`` dependency (the async streaming SDK,
**not** boto3)::

    pip install "steely[stt-aws]"

Auth uses the standard AWS credential chain (env vars, shared config, IAM role);
``region`` comes from the ``region`` kwarg or ``AWS_REGION``. Canonical
``"pt-BR"`` maps straight through. Registered under both ``"aws"`` and
``"transcribe"`` in the factory.

Amazon Transcribe's ``output_stream`` is an async iterator of events, so this
adapter is a straightforward pull-based :class:`QueueSession`.
"""
from __future__ import annotations

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


class AmazonTranscribeSession(QueueSession):
    """Live Amazon Transcribe session. Backend wants 16 kHz PCM s16le mono."""

    BACKEND_RATE = 16000
    BACKEND_ENCODING = "pcm_s16le"

    def __init__(self, provider: AmazonTranscribeProvider, config: STTConfig, **opts: Any) -> None:
        super().__init__(config, reconnect=opts.pop("reconnect", None))
        self._provider = provider
        self._opts = opts

    async def _connect(self, config: STTConfig) -> Any:
        client = self._provider._client_cls(region=self._provider._region)
        try:
            stream = await client.start_stream_transcription(
                language_code=to_provider_language("aws", config.language),
                media_sample_rate_hz=self.BACKEND_RATE,
                media_encoding="pcm",
                **self._opts,
            )
        except Exception as exc:  # noqa: BLE001
            raise STTConnectionError(f"Amazon Transcribe start failed: {exc}") from exc
        return stream

    async def _receive(self, conn: Any) -> AsyncIterator[STTEvent]:
        try:
            async for event in conn.output_stream:
                transcript = getattr(event, "transcript", None)
                if transcript is None:
                    continue
                for result in transcript.results:
                    if not result.alternatives:
                        continue
                    text = result.alternatives[0].transcript
                    if not text:
                        continue
                    yield STTEvent(
                        type=EventType.INTERIM if result.is_partial else EventType.FINAL,
                        text=text,
                        start=int(float(result.start_time) * 1000),
                        end=int(float(result.end_time) * 1000),
                        language=self._config.language,
                    )
        except Exception as exc:  # noqa: BLE001 - normalize to the common error
            raise STTConnectionError(
                f"Amazon Transcribe stream error: {exc}", retryable=True
            ) from exc

    async def _send_bytes(self, conn: Any, pcm: bytes) -> None:
        await conn.input_stream.send_audio_event(audio_chunk=pcm)

    async def _signal_end(self, conn: Any) -> None:
        await conn.input_stream.end_stream()

    async def _close_conn(self, conn: Any) -> None:
        try:
            await conn.input_stream.end_stream()
        except Exception:  # noqa: BLE001 - best-effort
            pass


class AmazonTranscribeProvider(STTProvider):
    """Amazon Transcribe streaming STT backend.

    Parameters
    ----------
    region:
        AWS region (e.g. ``"us-east-1"``). Falls back to ``AWS_REGION``.
    """

    def __init__(self, region: str | None = None, **_: Any) -> None:
        reg = region or os.environ.get("AWS_REGION")
        if not reg:
            raise STTConfigError("AmazonTranscribeProvider requires a region or AWS_REGION")
        try:
            from amazon_transcribe.client import TranscribeStreamingClient
        except ImportError as exc:  # pragma: no cover - exercised via monkeypatch
            raise ProviderNotAvailableError(
                "AmazonTranscribeProvider requires 'amazon-transcribe'. Install with: "
                "pip install 'steely[stt-aws]'"
            ) from exc
        self._client_cls = TranscribeStreamingClient
        self._region = reg
        self._redacted = redact(reg)

    @property
    def name(self) -> str:
        return "aws"

    async def open_session(
        self,
        config: STTConfig,
        *,
        reconnect: ReconnectPolicy | None = None,
        **kwargs: Any,
    ) -> STTSession:
        session = AmazonTranscribeSession(self, config, reconnect=reconnect, **kwargs)
        await session._start()
        return session
