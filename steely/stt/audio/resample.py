"""
to_backend_pcm — resample/transcode a raw audio frame to a backend's format.

Every adapter calls this from :meth:`push_frame`, so resampling and format
conversion live inside the library (Rule 1) and are identical across backends.
Uses the standard-library :mod:`audioop` (removed in Python 3.13, where the
``audioop-lts`` back-port supplies it via the ``steely[audio]`` extra). No numpy
— this is mono 16-bit rate conversion and stays dependency-light.
"""
from __future__ import annotations

import array
import sys
from typing import Any

try:  # audioop is stdlib on <= 3.12
    import audioop  # type: ignore
except ImportError:  # pragma: no cover - exercised only on Python 3.13+
    try:
        import audioop_lts as audioop  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "audioop is unavailable on this Python. Install the back-port with: "
            "pip install 'steely[audio]'"
        ) from exc


# Bytes per sample for the encodings we accept as input.
_WIDTHS = {"pcm_s16le": 2, "pcm_s24le": 3, "pcm_s32le": 4}


def to_backend_pcm(
    frame: bytes,
    *,
    in_rate: int,
    in_channels: int,
    in_encoding: str,
    out_rate: int,
    out_channels: int = 1,
    out_encoding: str = "pcm_s16le",
    state: dict[str, Any] | None = None,
) -> bytes:
    """Convert one raw PCM ``frame`` to the backend's required format.

    Handles sample-width normalization to 16-bit, stereo->mono downmix, and
    sample-rate conversion, in that order.

    Parameters
    ----------
    frame:
        Raw PCM bytes as the worker pushed them.
    in_rate, in_channels, in_encoding:
        Format of ``frame`` (from :class:`~steely.stt.config.STTConfig`).
    out_rate, out_channels, out_encoding:
        Format the backend requires (adapter class attributes).
    state:
        Per-session dict carrying :func:`audioop.ratecv` state across frames.
        Pass the same dict every call so rate conversion stays continuous and
        does not click at frame boundaries.

    Returns
    -------
    bytes
        PCM in the requested output format.
    """
    if out_encoding != "pcm_s16le":
        raise ValueError(f"unsupported out_encoding {out_encoding!r} (only pcm_s16le)")
    if in_encoding not in _WIDTHS:
        raise ValueError(f"unsupported in_encoding {in_encoding!r}")

    pcm = frame
    width = _WIDTHS[in_encoding]

    # 1) normalize sample width to 16-bit signed.
    if width != 2:
        pcm = audioop.lin2lin(pcm, width, 2)
        width = 2

    # 2) downmix to mono if the backend wants mono.
    if in_channels > 1 and out_channels == 1:
        pcm = audioop.tomono(pcm, width, 0.5, 0.5)
        channels = 1
    else:
        channels = in_channels

    # 3) resample if needed, threading ratecv state across frames.
    if in_rate != out_rate:
        prev: Any = state.get("ratecv") if state is not None else None
        pcm, new_state = audioop.ratecv(pcm, width, channels, in_rate, out_rate, prev)
        if state is not None:
            state["ratecv"] = new_state

    return pcm


def pcm16le_to_float32le(pcm16: bytes) -> bytes:
    """Convert 16-bit little-endian PCM to 32-bit little-endian float in [-1, 1).

    Some backends (e.g. WhisperLive / faster-whisper) expect normalized float32
    samples rather than int16. Uses the stdlib :mod:`array` module (no numpy).
    """
    ints = array.array("h")  # signed 16-bit, native byte order
    ints.frombytes(pcm16)
    if sys.byteorder == "big":  # incoming bytes are little-endian
        ints.byteswap()
    floats = array.array("f", (s / 32768.0 for s in ints))
    if sys.byteorder == "big":  # emit little-endian float32
        floats.byteswap()
    return floats.tobytes()
