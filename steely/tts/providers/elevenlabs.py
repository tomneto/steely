"""
ElevenLabsProvider — streaming text-to-speech over ElevenLabs' WebSocket API.

A true streaming backend: text fragments are pushed as they arrive and audio
chunks come back before the full text is known, so it subclasses
:class:`~steely.tts.session.QueueSession` and implements the WS hooks. The API
key is sent inside the first ("beginning of stream") message, avoiding
websockets-version header differences.

Install: ``pip install "steely[tts-elevenlabs]"`` (needs ``websockets``). The API
key comes from the ``api_key`` kwarg or the ``ELEVENLABS_API_KEY`` env var.
"""
from __future__ import annotations

import base64
import json
import os
from typing import Any, AsyncIterator, Optional

from steely.tts.audio_chunk import AudioChunk
from steely.tts.base import TTSProvider, redact
from steely.tts.config import TTSConfig
from steely.tts.errors import (
    ProviderNotAvailableError,
    TTSConfigError,
    TTSConnectionError,
)
from steely.tts.reconnect import ReconnectPolicy
from steely.tts.session import QueueSession

# ElevenLabs' default "Rachel" voice, used when config.voice == "default".
_DEFAULT_VOICE = "21m00Tcm4TlvDq8ikWAM"
_DEFAULT_MODEL = "eleven_multilingual_v2"


def _output_format(config: TTSConfig) -> str:
    """Map TTSConfig to an ElevenLabs ``output_format`` token."""
    if config.audio_format in ("pcm", "pcm_s16le"):
        return f"pcm_{config.sample_rate}"
    if config.audio_format == "mp3":
        return "mp3_44100_128"
    return config.audio_format


class ElevenLabsSession(QueueSession):
    """Streaming WS session for ElevenLabs. Emits base64-decoded PCM/MP3 chunks."""

    def __init__(self, provider: "ElevenLabsProvider", config: TTSConfig, **kw: Any) -> None:
        super().__init__(config, **kw)
        self._provider = provider
        self._index = 0

    @property
    def name(self) -> str:
        return "elevenlabs"

    async def _connect(self, config: TTSConfig) -> Any:
        ws = self._provider._websockets
        voice = _DEFAULT_VOICE if config.voice == "default" else config.voice
        model = _DEFAULT_MODEL if config.model == "default" else config.model
        url = (
            f"wss://api.elevenlabs.io/v1/text-to-speech/{voice}/stream-input"
            f"?model_id={model}&output_format={_output_format(config)}"
        )
        try:
            conn = await ws.connect(url)
            # Beginning-of-stream: settings + credentials, no text yet.
            await conn.send(json.dumps({
                "text": " ",
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.8},
                "xi_api_key": self._provider._api_key,
            }))
        except Exception as exc:  # noqa: BLE001 - normalize to the canonical error
            raise TTSConnectionError(f"ElevenLabs connect failed: {exc}") from exc
        return conn

    async def _send_text(self, conn: Any, text: str) -> None:
        # ElevenLabs triggers generation on whitespace; a trailing space helps.
        await conn.send(json.dumps({"text": text + " ", "try_trigger_generation": True}))

    async def _signal_end(self, conn: Any) -> None:
        # An empty-string text closes the input stream and flushes final audio.
        await conn.send(json.dumps({"text": ""}))

    async def _receive(self, conn: Any) -> AsyncIterator[AudioChunk]:
        closed_excs = self._provider._closed_excs
        try:
            async for raw in conn:
                msg = json.loads(raw)
                audio_b64 = msg.get("audio")
                is_final = bool(msg.get("isFinal"))
                if audio_b64:
                    yield AudioChunk(
                        base64.b64decode(audio_b64),
                        index=self._index,
                        is_final=is_final,
                        raw=msg,
                    )
                    self._index += 1
                if is_final:
                    return
        except closed_excs as exc:
            # Clean server close ends the stream; anything else is retryable.
            if getattr(exc, "code", 1000) in (1000, 1001):
                return
            raise TTSConnectionError(f"ElevenLabs stream dropped: {exc}") from exc

    async def _close_conn(self, conn: Any) -> None:
        await conn.close()


class ElevenLabsProvider(TTSProvider):
    """ElevenLabs streaming text-to-speech backend.

    Parameters
    ----------
    api_key:
        ElevenLabs API key. Falls back to ``ELEVENLABS_API_KEY``.
    """

    def __init__(self, api_key: Optional[str] = None, **_: Any) -> None:
        try:
            import websockets
            from websockets import exceptions as ws_exc
        except ImportError as exc:  # pragma: no cover - exercised via monkeypatch
            raise ProviderNotAvailableError(
                "ElevenLabs TTS needs websockets. Install with: "
                "pip install \"steely[tts-elevenlabs]\""
            ) from exc
        self._websockets = websockets
        self._closed_excs = (ws_exc.ConnectionClosed,)
        self._api_key = api_key or os.environ.get("ELEVENLABS_API_KEY")
        if not self._api_key:
            raise TTSConfigError(
                "ElevenLabs TTS needs an api_key (or ELEVENLABS_API_KEY env var)"
            )

    @property
    def name(self) -> str:
        return "elevenlabs"

    def validate(self) -> bool:
        return bool(self._api_key)

    async def open_session(
        self,
        config: TTSConfig,
        *,
        reconnect: Optional[ReconnectPolicy] = None,
        **kwargs: Any,
    ) -> ElevenLabsSession:
        session = ElevenLabsSession(self, config, reconnect=reconnect)
        await session._start()
        return session

    def __repr__(self) -> str:
        return f"ElevenLabsProvider(api_key={redact(self._api_key)})"
