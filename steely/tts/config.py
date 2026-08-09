"""
TTSConfig — provider-agnostic synthesis configuration set at creation time.

The caller always speaks canonical values here; each adapter maps them to its
backend (language tag -> provider code, ``voice`` -> the backend's voice id,
``audio_format``/``sample_rate`` -> the container/rate the backend emits). The
``sample_rate``/``encoding`` fields describe the **output** audio the caller
wants back; the adapter asks its backend for that format (or the closest it
supports) and documents any deviation.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TTSConfig:
    """Configuration for a synthesis session.

    Parameters
    ----------
    voice:
        Logical/canonical voice id; each adapter maps it to a concrete provider
        voice (e.g. an ElevenLabs voice id or an OpenAI voice name like
        ``"alloy"``). ``"default"`` lets the adapter pick its house voice.
    language:
        Canonical BCP-47 tag (e.g. ``"pt-BR"``). The adapter maps it to the
        provider's own code where the provider needs one.
    model:
        Logical model name; each adapter maps it to a concrete provider model
        (e.g. ElevenLabs ``"eleven_multilingual_v2"``, OpenAI ``"tts-1"``).
    sample_rate:
        Desired output sample rate (Hz) of the returned audio.
    encoding:
        Desired output encoding. Canonical default is 16-bit little-endian PCM
        (``"pcm_s16le"``); adapters may also honor container formats via
        ``audio_format``.
    audio_format:
        Container/codec for the returned audio (``"pcm"``, ``"mp3"``,
        ``"wav"``, ...). ``"pcm"`` yields raw ``encoding`` samples.
    speed:
        Speaking-rate multiplier where the provider supports it (``1.0`` =
        normal). Adapters clamp to their supported range.
    """

    voice: str = "default"
    language: str = "pt-BR"
    model: str = "default"
    sample_rate: int = 24000
    encoding: str = "pcm_s16le"
    audio_format: str = "pcm"
    speed: float = 1.0

    def __post_init__(self) -> None:
        if self.sample_rate <= 0:
            raise ValueError("TTSConfig.sample_rate must be positive")
        if self.speed <= 0:
            raise ValueError("TTSConfig.speed must be positive")
