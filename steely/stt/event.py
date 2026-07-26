"""
STTEvent — the single canonical transcript event, identical across backends.

Every adapter translates its provider's native messages into this one type, so
consumers (the worker) see uniform ``interim``/``final`` semantics and uniform
timestamps regardless of which backend is behind the session.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class EventType(str, Enum):
    """The only two transcript event kinds every backend is normalized to."""

    INTERIM = "interim"   # partial / non-final hypothesis; may still be revised
    FINAL = "final"       # stabilized segment; will not change


@dataclass
class STTEvent:
    """One transcript event, identical across every backend.

    Attributes
    ----------
    type:
        :attr:`EventType.INTERIM` or :attr:`EventType.FINAL`. Adapters map their
        provider's partial/final semantics onto these two values so consumers
        behave the same everywhere (Rule 2).
    text:
        The transcript text for this event.
    start, end:
        Timestamps in **milliseconds** from the start of the stream (``int`` ms
        was chosen over float seconds for exactness and to match LiveKit frame
        timing). Adapters convert their native units once, on the way out.
    speaker:
        Optional speaker label. steely.stt does **not** do diarization — this is
        populated by the worker from the LiveKit track, not by the backend.
    confidence:
        Optional provider confidence in ``[0, 1]`` when available.
    language:
        The canonical BCP-47 tag echoed back (e.g. ``"pt-BR"``), never the
        provider's own code.
    raw:
        The parsed native message, for debugging only (``repr``-hidden so logs
        stay clean).
    """

    type: EventType
    text: str
    start: int
    end: int
    speaker: Optional[str] = None
    confidence: Optional[float] = None
    language: Optional[str] = None
    raw: Optional[Dict[str, Any]] = field(default=None, repr=False)

    @property
    def is_final(self) -> bool:
        """``True`` when this is a stabilized (final) segment."""
        return self.type is EventType.FINAL
