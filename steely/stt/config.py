"""
STTConfig — provider-agnostic session configuration set at creation time.

The worker always speaks canonical values here; each adapter maps them to its
backend (language tag -> provider code, ``sample_rate``/``encoding`` -> the rate
and format the backend requires). The ``sample_rate``/``encoding``/``channels``
fields describe the **input** the worker will push; resampling to the backend's
format happens inside the adapter (Rule 1).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class STTConfig:
    """Configuration for a streaming session.

    Parameters
    ----------
    model:
        Logical/canonical model name; each adapter maps it to a concrete
        provider model (e.g. Deepgram ``"nova-2"``).
    language:
        Canonical BCP-47 tag as the worker speaks it (e.g. ``"pt-BR"``). The
        adapter maps it to the provider's own code.
    sample_rate:
        Sample rate (Hz) of the raw frames the worker will push.
    encoding:
        Encoding of the pushed frames. Canonical default is 16-bit little-endian
        PCM (``"pcm_s16le"``).
    channels:
        Number of channels in the pushed frames. The adapter downmixes to what
        the backend needs (usually mono).
    interim_results:
        Request partial (interim) results where the provider supports them.
    """

    model: str = "default"
    language: str = "pt-BR"
    sample_rate: int = 16000
    encoding: str = "pcm_s16le"
    channels: int = 1
    interim_results: bool = True

    def __post_init__(self) -> None:
        if self.sample_rate <= 0:
            raise ValueError("STTConfig.sample_rate must be positive")
        if self.channels < 1:
            raise ValueError("STTConfig.channels must be >= 1")
