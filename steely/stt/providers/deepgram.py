"""
DeepgramProvider — streaming STT via Deepgram's live WebSocket API.

Requires the optional ``deepgram-sdk`` dependency::

    pip install "steely[stt-deepgram]"

Credentials come from the ``api_key`` kwarg or the ``DEEPGRAM_API_KEY``
environment variable (never hardcoded). Deepgram's multilingual ``nova-2`` model
handles pt-BR; the canonical ``"pt-BR"`` tag maps straight through.
"""
from __future__ import annotations

import os
from typing import Any, Optional

from steely.stt.base import STTProvider, STTSession, redact
from steely.stt.config import STTConfig
from steely.stt.errors import ProviderNotAvailableError, STTConfigError, STTConnectionError
from steely.stt.event import EventType, STTEvent
from steely.stt.languages import to_provider_language
from steely.stt.reconnect import ReconnectPolicy
from steely.stt.session import CallbackQueueSession


class DeepgramSession(CallbackQueueSession):
    """Live Deepgram session. Backend wants 16 kHz linear16 (PCM s16le) mono."""

    BACKEND_RATE = 16000
    BACKEND_ENCODING = "pcm_s16le"

    def __init__(self, provider: "DeepgramProvider", config: STTConfig, **opts: Any) -> None:
        super().__init__(config, reconnect=opts.pop("reconnect", None))
        self._provider = provider
        self._opts = opts

    async def _connect(self, config: STTConfig) -> Any:
        dg = self._provider._sdk
        events = self._provider._events
        conn = self._provider._client.listen.asyncwebsocket.v("1")

        conn.on(events.Transcript, self._on_transcript)
        conn.on(events.Error, self._on_error)
        conn.on(events.Close, self._on_close)

        options = dg.LiveOptions(
            model=config.model if config.model != "default" else "nova-2",
            language=to_provider_language("deepgram", config.language),
            encoding="linear16",
            sample_rate=self.BACKEND_RATE,
            channels=1,
            interim_results=config.interim_results,
            **self._opts,
        )
        started = await conn.start(options)
        if not started:
            raise STTConnectionError("Deepgram failed to start live session")
        return conn

    async def _on_transcript(self, _self: Any, result: Any, **_: Any) -> None:
        try:
            alt = result.channel.alternatives[0]
            text = alt.transcript
            if not text:
                return
            start_ms = int(float(result.start) * 1000)
            end_ms = int((float(result.start) + float(result.duration)) * 1000)
            self.emit(
                STTEvent(
                    type=EventType.FINAL if result.is_final else EventType.INTERIM,
                    text=text,
                    start=start_ms,
                    end=end_ms,
                    confidence=getattr(alt, "confidence", None),
                    language=self._config.language,
                    raw=None,
                )
            )
        except Exception as exc:  # noqa: BLE001 - never let a bad message kill the loop
            self.emit_error(STTConnectionError(f"Deepgram parse error: {exc}"))

    async def _on_error(self, _self: Any, error: Any, **_: Any) -> None:
        self.emit_error(STTConnectionError(f"Deepgram error: {error}", retryable=True))

    async def _on_close(self, _self: Any, *_a: Any, **_k: Any) -> None:
        self.emit_end()

    async def _send_bytes(self, conn: Any, pcm: bytes) -> None:
        await conn.send(pcm)

    async def _signal_end(self, conn: Any) -> None:
        await conn.finish()

    async def _close_conn(self, conn: Any) -> None:
        await conn.finish()


class DeepgramProvider(STTProvider):
    """Deepgram streaming STT backend.

    Parameters
    ----------
    api_key:
        Deepgram API key. Falls back to ``DEEPGRAM_API_KEY``.
    """

    def __init__(self, api_key: Optional[str] = None, **_: Any) -> None:
        key = api_key or os.environ.get("DEEPGRAM_API_KEY")
        if not key:
            raise STTConfigError("DeepgramProvider requires an api_key or DEEPGRAM_API_KEY")
        try:
            import deepgram as _dg
            from deepgram import DeepgramClient, LiveTranscriptionEvents
        except ImportError as exc:  # pragma: no cover - exercised via monkeypatch
            raise ProviderNotAvailableError(
                "DeepgramProvider requires 'deepgram-sdk'. Install with: "
                "pip install 'steely[stt-deepgram]'"
            ) from exc
        self._sdk = _dg
        self._events = LiveTranscriptionEvents
        self._client = DeepgramClient(key)
        self._api_key = key
        self._redacted = redact(key)

    @property
    def name(self) -> str:
        return "deepgram"

    async def open_session(
        self,
        config: STTConfig,
        *,
        reconnect: Optional[ReconnectPolicy] = None,
        **kwargs: Any,
    ) -> STTSession:
        session = DeepgramSession(self, config, reconnect=reconnect, **kwargs)
        await session._start()
        return session
