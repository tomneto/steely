"""
AudioChunk — the single canonical synthesis output, identical across backends.

Every adapter translates its provider's native audio messages into this one
type, so consumers see a uniform stream of audio bytes regardless of which
backend is behind the session. The final chunk of a stream carries
``is_final=True`` (it may still hold audio); concatenating every chunk's
``audio`` in order reconstructs the full clip.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AudioChunk:
    """One chunk of synthesized audio, identical across every backend.

    Attributes
    ----------
    audio:
        Raw audio bytes in the format requested by
        :class:`~steely.tts.config.TTSConfig` (``encoding``/``audio_format``).
    index:
        0-based position of this chunk within the stream.
    is_final:
        ``True`` on the last chunk of the stream (it may still carry audio).
    duration_ms:
        Optional duration of this chunk's audio in milliseconds, when the
        provider reports or it can be derived.
    raw:
        The parsed native message, for debugging only (``repr``-hidden so logs
        stay clean).
    """

    audio: bytes
    index: int = 0
    is_final: bool = False
    duration_ms: int | None = None
    raw: dict[str, Any] | None = field(default=None, repr=False)
