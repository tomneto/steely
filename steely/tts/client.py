"""
TTSClient — the front door of :mod:`steely.tts`.

Construct it with a provider *name* + kwargs (it builds the provider for you) or
with a ready-made :class:`~steely.tts.base.TTSProvider` instance. Then open a
streaming session and iterate its audio chunks, or call :meth:`synthesize` for a
one-shot clip. Switching providers is a one-line change; the session API and the
:class:`AudioChunk` you receive stay identical.

>>> from steely.tts import TTSClient, TTSConfig       # doctest: +SKIP
>>> client = TTSClient("elevenlabs", api_key="el_xxx")  # doctest: +SKIP
>>> audio = await client.synthesize("Olá, tudo bem?", TTSConfig(language="pt-BR"))  # doctest: +SKIP

The provider name -> class mapping mirrors ``STTClient``'s ``_FACTORY`` dispatch:
entries are ``(module, class)`` strings so importing the client never pulls in a
provider's optional SDK until that provider is actually requested.
"""
from __future__ import annotations

import importlib
from typing import Any, Optional, Union

from steely.tts.base import TTSProvider, TTSSession
from steely.tts.config import TTSConfig
from steely.tts.reconnect import ReconnectPolicy

# name -> (module, class). Strings so optional SDKs import lazily.
_FACTORY = {
    "elevenlabs": ("steely.tts.providers.elevenlabs", "ElevenLabsProvider"),
    "eleven": ("steely.tts.providers.elevenlabs", "ElevenLabsProvider"),
    "openai": ("steely.tts.providers.openai", "OpenAIProvider"),
    "fake": ("steely.tts.providers.fake", "FakeProvider"),
}


class TTSClient:
    """Provider-agnostic streaming TTS front door.

    Parameters
    ----------
    provider:
        Either a provider name (``"elevenlabs"``/``"eleven"``, ``"openai"``,
        ``"fake"``) or a :class:`TTSProvider` instance. When a name is given,
        remaining keyword arguments are forwarded to that provider's constructor
        (credentials, base_url, ...).
    """

    def __init__(self, provider: Union[str, TTSProvider], **kwargs: Any) -> None:
        if isinstance(provider, TTSProvider):
            self._provider = provider
        elif isinstance(provider, str):
            key = provider.lower().strip()
            if key not in _FACTORY:
                valid = sorted(set(_FACTORY))
                raise ValueError(f"Unknown TTS provider '{provider}'. Valid options: {valid}")
            module_name, cls_name = _FACTORY[key]
            module = importlib.import_module(module_name)
            self._provider = getattr(module, cls_name)(**kwargs)
        else:
            raise TypeError(
                "provider must be a provider name (str) or a TTSProvider instance"
            )

    @property
    def provider(self) -> TTSProvider:
        return self._provider

    @property
    def provider_name(self) -> str:
        return self._provider.name

    async def open_session(
        self,
        config: Optional[TTSConfig] = None,
        *,
        reconnect: Optional[ReconnectPolicy] = None,
        **kwargs: Any,
    ) -> TTSSession:
        """Open a streaming synthesis session via the underlying provider.

        ``config`` defaults to :class:`TTSConfig` (pt-BR, 24 kHz PCM). Per-session
        provider tuning goes in ``**kwargs``.
        """
        return await self._provider.open_session(
            config or TTSConfig(), reconnect=reconnect, **kwargs
        )

    async def synthesize(
        self,
        text: str,
        config: Optional[TTSConfig] = None,
        **kwargs: Any,
    ) -> bytes:
        """One-shot: synthesize ``text`` and return the full audio bytes."""
        return await self._provider.synthesize(text, config or TTSConfig(), **kwargs)

    def validate(self) -> bool:
        """Return whether the underlying provider's config looks usable."""
        return self._provider.validate()
