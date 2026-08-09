"""
Language-code normalization for :mod:`steely.tts`.

The caller always speaks a canonical BCP-47 tag (e.g. ``"pt-BR"``); each adapter
calls :func:`to_provider_language` to get the code *its* backend expects. Kept in
one file so every adapter maps identically. Many TTS backends infer language from
the chosen voice/model and ignore an explicit code, so the default is a
pass-through.
"""
from __future__ import annotations

from typing import Dict

# Per-provider maps: canonical BCP-47 -> that provider's expected code.
# ElevenLabs and OpenAI infer language from the voice/model, so they are absent
# here and fall through unchanged.
_GOOGLE: Dict[str, str] = {"pt-BR": "pt-BR", "pt": "pt-BR", "en-US": "en-US", "es-ES": "es-ES"}
_AZURE: Dict[str, str] = {"pt-BR": "pt-BR", "pt": "pt-BR", "en-US": "en-US", "es-ES": "es-ES"}
_AWS: Dict[str, str] = {"pt-BR": "pt-BR", "pt": "pt-BR", "en-US": "en-US", "es-ES": "es-ES"}

_MAPS: Dict[str, Dict[str, str]] = {
    "google": _GOOGLE,
    "azure": _AZURE,
    "aws": _AWS,
}


def to_provider_language(provider: str, canonical: str) -> str:
    """Map a canonical BCP-47 tag to ``provider``'s language code.

    Falls back to the canonical tag unchanged when unmapped (most providers
    accept BCP-47 directly, or infer language from the voice). Adapters that
    require a strict set should validate the result themselves and raise
    :class:`~steely.tts.errors.TTSConfigError` before pushing text.
    """
    return _MAPS.get(provider, {}).get(canonical, canonical)
