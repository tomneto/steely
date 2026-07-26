"""
AssemblyAIProvider — streaming STT via AssemblyAI's realtime API.

Requires the optional ``assemblyai`` dependency::

    pip install "steely[stt-assemblyai]"

Credentials come from the ``api_key`` kwarg or ``ASSEMBLYAI_API_KEY``.

Language note (flagged deviation): AssemblyAI's realtime streaming supports a
narrower language set than its batch API. The canonical ``"pt-BR"`` maps to
``"pt"``; if the installed SDK/plan rejects it, :meth:`open_session` raises
:class:`~steely.stt.errors.STTConfigError` up front — before any audio is
pushed — rather than silently degrading to English.
"""
from __future__ import annotations

import asyncio
import os
from typing import Any, Optional

from steely.stt.base import STTProvider, STTSession, redact
from steely.stt.config import STTConfig
from steely.stt.errors import ProviderNotAvailableError, STTConfigError, STTConnectionError
from steely.stt.event import EventType, STTEvent
from steely.stt.languages import to_provider_language
from steely.stt.reconnect import ReconnectPolicy
from steely.stt.session import CallbackQueueSession


class AssemblyAISession(CallbackQueueSession):
    """Live AssemblyAI session. Backend wants 16 kHz PCM s16le mono.

    AssemblyAI reports ``audio_start``/``audio_end`` already in milliseconds, so
    no unit conversion is needed for timestamps.
    """

    BACKEND_RATE = 16000
    BACKEND_ENCODING = "pcm_s16le"

    def __init__(self, provider: "AssemblyAIProvider", config: STTConfig, **opts: Any) -> None:
        super().__init__(config, reconnect=opts.pop("reconnect", None))
        self._provider = provider
        self._opts = opts
        self._transcriber: Any = None

    async def _connect(self, config: STTConfig) -> Any:
        aai = self._provider._sdk
        language = to_provider_language("assemblyai", config.language)

        kwargs = dict(
            sample_rate=self.BACKEND_RATE,
            on_data=self._on_data,
            on_error=self._on_error,
            on_close=self._on_close,
            **self._opts,
        )
        # Newer SDKs accept a language code for realtime; older ones are
        # English-only and raise TypeError -> fail fast for non-English.
        if language and language != "en":
            kwargs["language_code"] = language
        try:
            transcriber = aai.RealtimeTranscriber(**kwargs)
        except TypeError as exc:
            raise STTConfigError(
                f"AssemblyAI realtime does not support language '{language}' "
                f"with the installed SDK: {exc}"
            ) from exc

        try:
            await asyncio.to_thread(transcriber.connect)
        except Exception as exc:  # noqa: BLE001
            raise STTConnectionError(f"AssemblyAI connect failed: {exc}") from exc
        self._transcriber = transcriber
        return transcriber

    def _on_data(self, transcript: Any) -> None:
        try:
            text = getattr(transcript, "text", "") or ""
            if not text:
                return
            # RealtimeFinalTranscript vs RealtimePartialTranscript by class name.
            is_final = type(transcript).__name__.endswith("FinalTranscript")
            self.emit(
                STTEvent(
                    type=EventType.FINAL if is_final else EventType.INTERIM,
                    text=text,
                    start=int(getattr(transcript, "audio_start", 0) or 0),
                    end=int(getattr(transcript, "audio_end", 0) or 0),
                    confidence=getattr(transcript, "confidence", None),
                    language=self._config.language,
                )
            )
        except Exception as exc:  # noqa: BLE001
            self.emit_error(STTConnectionError(f"AssemblyAI parse error: {exc}"))

    def _on_error(self, error: Any) -> None:
        self.emit_error(STTConnectionError(f"AssemblyAI error: {error}", retryable=True))

    def _on_close(self, *_: Any) -> None:
        self.emit_end()

    async def _send_bytes(self, conn: Any, pcm: bytes) -> None:
        await asyncio.to_thread(conn.stream, pcm)

    async def _signal_end(self, conn: Any) -> None:
        await asyncio.to_thread(conn.close)

    async def _close_conn(self, conn: Any) -> None:
        await asyncio.to_thread(conn.close)


class AssemblyAIProvider(STTProvider):
    """AssemblyAI streaming STT backend.

    Parameters
    ----------
    api_key:
        AssemblyAI API key. Falls back to ``ASSEMBLYAI_API_KEY``.
    """

    def __init__(self, api_key: Optional[str] = None, **_: Any) -> None:
        key = api_key or os.environ.get("ASSEMBLYAI_API_KEY")
        if not key:
            raise STTConfigError("AssemblyAIProvider requires an api_key or ASSEMBLYAI_API_KEY")
        try:
            import assemblyai as aai
        except ImportError as exc:  # pragma: no cover - exercised via monkeypatch
            raise ProviderNotAvailableError(
                "AssemblyAIProvider requires 'assemblyai'. Install with: "
                "pip install 'steely[stt-assemblyai]'"
            ) from exc
        aai.settings.api_key = key
        self._sdk = aai
        self._redacted = redact(key)

    @property
    def name(self) -> str:
        return "assemblyai"

    async def open_session(
        self,
        config: STTConfig,
        *,
        reconnect: Optional[ReconnectPolicy] = None,
        **kwargs: Any,
    ) -> STTSession:
        session = AssemblyAISession(self, config, reconnect=reconnect, **kwargs)
        await session._start()
        return session
