"""
WhisperLiveProvider — faster-whisper self-hosted via WhisperLive.

Requires the optional ``websockets`` dependency::

    pip install "steely[stt-whisperlive]"

WhisperLive (https://github.com/collabora/WhisperLive) is a streaming wrapper
around faster-whisper. It is **batch under the hood**, so *endpointing is the
adapter's responsibility* (Rule: the interface never assumes endpointing comes
from the backend). This adapter owns endpointing by:

- enabling WhisperLive's server-side VAD (``use_vad=True``), and
- mapping each segment's ``completed`` flag to :attr:`EventType.FINAL` (an
  in-progress segment is :attr:`EventType.INTERIM`),

so a consumer sees the exact same uniform ``interim``/``final`` stream as every
other backend. No interface change was needed to add it.

Endpoint & auth: self-hosted, so there are no credentials — only an
``endpoint_url`` (kwarg) or the ``WHISPERLIVE_URL`` env var
(default ``ws://localhost:9090``).

Protocol
--------
1. Open the WebSocket and send a JSON config
   (``uid``, ``language``, ``task``, ``model``, ``use_vad``).
2. Stream audio as **little-endian float32** PCM at 16 kHz mono.
3. Receive JSON messages; ``{"segments": [...]}`` carry the transcript, each
   segment with string ``start``/``end`` seconds, ``text`` and ``completed``.
4. On ``end_input`` send ``"END_OF_AUDIO"`` so the server flushes its finals.
"""
from __future__ import annotations

import json
import os
import uuid
from typing import Any, AsyncIterator, Optional, Set, Tuple

from steely.stt.audio.resample import pcm16le_to_float32le
from steely.stt.base import STTProvider, STTSession, redact
from steely.stt.config import STTConfig
from steely.stt.errors import ProviderNotAvailableError, STTConnectionError
from steely.stt.event import EventType, STTEvent
from steely.stt.languages import to_provider_language
from steely.stt.reconnect import ReconnectPolicy
from steely.stt.session import QueueSession

_DEFAULT_URL = "ws://localhost:9090"
# WhisperLive control messages that are not transcript payloads.
_CONTROL_MESSAGES = {"SERVER_READY", "WAIT", "DISCONNECT", "ERROR"}


class WhisperLiveSession(QueueSession):
    """Live WhisperLive session. Backend wants 16 kHz mono float32 PCM.

    Frames are resampled to 16 kHz s16le by the base class, then converted to
    float32 here. Endpointing is owned by this adapter (server VAD + the
    ``completed`` flag), not assumed from the backend.
    """

    BACKEND_RATE = 16000
    BACKEND_ENCODING = "pcm_s16le"  # converted to float32 in _send_bytes

    def __init__(self, provider: "WhisperLiveProvider", config: STTConfig, **opts: Any) -> None:
        super().__init__(config, reconnect=opts.pop("reconnect", None))
        self._provider = provider
        self._opts = opts
        self._uid = uuid.uuid4().hex
        # Keys of completed segments already emitted, so re-sent segment lists
        # don't produce duplicate finals.
        self._emitted_finals: Set[Tuple[int, str]] = set()

    async def _connect(self, config: STTConfig) -> Any:
        websockets = self._provider._ws
        try:
            conn = await websockets.connect(self._provider._url, max_size=None)
        except Exception as exc:  # noqa: BLE001
            raise STTConnectionError(f"WhisperLive connect failed: {exc}") from exc

        payload = {
            "uid": self._uid,
            "language": to_provider_language("whisperlive", config.language),
            "task": "transcribe",
            "model": config.model if config.model != "default" else "small",
            "use_vad": True,
        }
        payload.update(self._opts)
        try:
            await conn.send(json.dumps(payload))
        except Exception as exc:  # noqa: BLE001
            raise STTConnectionError(f"WhisperLive handshake failed: {exc}") from exc
        return conn

    async def _receive(self, conn: Any) -> AsyncIterator[STTEvent]:
        try:
            async for message in conn:
                if isinstance(message, (bytes, bytearray)):
                    continue  # WhisperLive replies are JSON text
                try:
                    data = json.loads(message)
                except (ValueError, TypeError):
                    continue
                if data.get("message") in _CONTROL_MESSAGES or "segments" not in data:
                    if data.get("message") == "DISCONNECT":
                        return
                    continue
                for event in self._translate_segments(data["segments"]):
                    yield event
        except Exception as exc:  # noqa: BLE001 - normalize to the common error
            raise STTConnectionError(f"WhisperLive stream error: {exc}", retryable=True) from exc

    def _translate_segments(self, segments: Any):
        """Yield canonical events from a WhisperLive segment list.

        Completed segments become FINAL (deduplicated across the re-sent list);
        the trailing in-progress segment becomes a single INTERIM.
        """
        for i, seg in enumerate(segments):
            text = (seg.get("text") or "").strip()
            if not text:
                continue
            start_ms = int(float(seg.get("start", 0)) * 1000)
            end_ms = int(float(seg.get("end", 0)) * 1000)
            completed = bool(seg.get("completed", i < len(segments) - 1))
            if completed:
                key = (start_ms, text)
                if key in self._emitted_finals:
                    continue
                self._emitted_finals.add(key)
                yield STTEvent(
                    type=EventType.FINAL,
                    text=text,
                    start=start_ms,
                    end=end_ms,
                    language=self._config.language,
                )
            else:
                yield STTEvent(
                    type=EventType.INTERIM,
                    text=text,
                    start=start_ms,
                    end=end_ms,
                    language=self._config.language,
                )

    async def _send_bytes(self, conn: Any, pcm: bytes) -> None:
        await conn.send(pcm16le_to_float32le(pcm))

    async def _signal_end(self, conn: Any) -> None:
        try:
            await conn.send("END_OF_AUDIO")
        except Exception as exc:  # noqa: BLE001
            raise STTConnectionError(f"WhisperLive end_input failed: {exc}") from exc

    async def _close_conn(self, conn: Any) -> None:
        await conn.close()


class WhisperLiveProvider(STTProvider):
    """faster-whisper self-hosted via WhisperLive (WebSocket) backend.

    Parameters
    ----------
    endpoint_url:
        WhisperLive WebSocket URL. Falls back to ``WHISPERLIVE_URL`` then
        ``ws://localhost:9090``.
    """

    def __init__(self, endpoint_url: Optional[str] = None, **_: Any) -> None:
        self._url = endpoint_url or os.environ.get("WHISPERLIVE_URL", _DEFAULT_URL)
        try:
            import websockets
        except ImportError as exc:  # pragma: no cover - exercised via monkeypatch
            raise ProviderNotAvailableError(
                "WhisperLiveProvider requires 'websockets'. Install with: "
                "pip install 'steely[stt-whisperlive]'"
            ) from exc
        self._ws = websockets
        self._redacted = redact(self._url)

    @property
    def name(self) -> str:
        return "whisperlive"

    async def open_session(
        self,
        config: STTConfig,
        *,
        reconnect: Optional[ReconnectPolicy] = None,
        **kwargs: Any,
    ) -> STTSession:
        session = WhisperLiveSession(self, config, reconnect=reconnect, **kwargs)
        await session._start()
        return session
