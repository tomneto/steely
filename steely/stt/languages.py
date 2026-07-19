"""
Language-code normalization for :mod:`steely.stt`.

The worker always speaks a canonical BCP-47 tag (e.g. ``"pt-BR"``); each adapter
calls :func:`to_provider_language` to get the code *its* backend expects. Kept
in one file so every adapter maps identically. The :class:`STTEvent.language`
echoed back to the worker is always the canonical tag, never the provider code.
"""
from __future__ import annotations

from typing import Dict

# Per-provider maps: canonical BCP-47 -> that provider's expected code.
_DEEPGRAM: Dict[str, str] = {"pt-BR": "pt-BR", "pt": "pt", "en-US": "en-US", "es-ES": "es"}
_ASSEMBLYAI: Dict[str, str] = {"pt-BR": "pt", "pt": "pt", "en-US": "en", "es-ES": "es"}
_GOOGLE: Dict[str, str] = {"pt-BR": "pt-BR", "pt": "pt-BR", "en-US": "en-US", "es-ES": "es-ES"}
_AZURE: Dict[str, str] = {"pt-BR": "pt-BR", "pt": "pt-BR", "en-US": "en-US", "es-ES": "es-ES"}
_AWS: Dict[str, str] = {"pt-BR": "pt-BR", "pt": "pt-BR", "en-US": "en-US", "es-ES": "es-ES"}
# WhisperLive / faster-whisper uses Whisper's ISO-639-1 language codes.
_WHISPERLIVE: Dict[str, str] = {"pt-BR": "pt", "pt": "pt", "en-US": "en", "es-ES": "es"}

_MAPS: Dict[str, Dict[str, str]] = {
    "deepgram": _DEEPGRAM,
    "assemblyai": _ASSEMBLYAI,
    "google": _GOOGLE,
    "azure": _AZURE,
    "aws": _AWS,
    "whisperlive": _WHISPERLIVE,
}


def to_provider_language(provider: str, canonical: str) -> str:
    """Map a canonical BCP-47 tag to ``provider``'s language code.

    Falls back to the canonical tag unchanged when unmapped (most providers
    accept BCP-47 directly). Adapters that require a strict set should validate
    the result themselves and raise
    :class:`~steely.stt.errors.STTConfigError` before pushing audio.
    """
    return _MAPS.get(provider, {}).get(canonical, canonical)
