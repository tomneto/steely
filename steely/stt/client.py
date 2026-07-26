"""
STTClient — the front door of :mod:`steely.stt`.

Construct it with a provider *name* + kwargs (it builds the provider for you) or
with a ready-made :class:`~steely.stt.base.STTProvider` instance. Then open a
streaming session and iterate its events. Switching providers is a one-line
change; the session API and the :class:`STTEvent` you receive stay identical.

>>> from steely.stt import STTClient, STTConfig      # doctest: +SKIP
>>> client = STTClient("deepgram", api_key="dg_xxx")  # doctest: +SKIP
>>> session = await client.open_session(STTConfig(language="pt-BR"))  # doctest: +SKIP

The provider name -> class mapping mirrors ``EmailClient``'s ``_FACTORY``
dispatch: entries are ``(module, class)`` strings so importing the client never
pulls in a provider's optional SDK until that provider is actually requested.
"""
from __future__ import annotations

import importlib
from typing import Any, Optional, Union

from steely.stt.base import STTProvider, STTSession
from steely.stt.config import STTConfig
from steely.stt.reconnect import ReconnectPolicy

# name -> (module, class). Strings so optional SDKs import lazily. Aliases point
# at the same class (chirp -> google, transcribe -> aws).
_FACTORY = {
    "deepgram": ("steely.stt.providers.deepgram", "DeepgramProvider"),
    "assemblyai": ("steely.stt.providers.assemblyai", "AssemblyAIProvider"),
    "google": ("steely.stt.providers.google", "GoogleProvider"),
    "chirp": ("steely.stt.providers.google", "GoogleProvider"),
    "azure": ("steely.stt.providers.azure", "AzureProvider"),
    "aws": ("steely.stt.providers.aws", "AmazonTranscribeProvider"),
    "transcribe": ("steely.stt.providers.aws", "AmazonTranscribeProvider"),
    "whisperlive": ("steely.stt.providers.whisperlive", "WhisperLiveProvider"),
    "whisper": ("steely.stt.providers.whisperlive", "WhisperLiveProvider"),
    "fake": ("steely.stt.providers.fake", "FakeProvider"),
}


class STTClient:
    """Provider-agnostic streaming STT front door.

    Parameters
    ----------
    provider:
        Either a provider name (``"deepgram"``, ``"assemblyai"``, ``"google"``/
        ``"chirp"``, ``"azure"``, ``"aws"``/``"transcribe"``, ``"fake"``) or an
        :class:`STTProvider` instance. When a name is given, remaining keyword
        arguments are forwarded to that provider's constructor (credentials,
        region, endpoint, ...).
    """

    def __init__(self, provider: Union[str, STTProvider], **kwargs: Any) -> None:
        if isinstance(provider, STTProvider):
            self._provider = provider
        elif isinstance(provider, str):
            key = provider.lower().strip()
            if key not in _FACTORY:
                valid = sorted(set(_FACTORY))
                raise ValueError(f"Unknown STT provider '{provider}'. Valid options: {valid}")
            module_name, cls_name = _FACTORY[key]
            module = importlib.import_module(module_name)
            self._provider = getattr(module, cls_name)(**kwargs)
        else:
            raise TypeError(
                "provider must be a provider name (str) or an STTProvider instance"
            )

    @property
    def provider(self) -> STTProvider:
        return self._provider

    @property
    def provider_name(self) -> str:
        return self._provider.name

    async def open_session(
        self,
        config: Optional[STTConfig] = None,
        *,
        reconnect: Optional[ReconnectPolicy] = None,
        **kwargs: Any,
    ) -> STTSession:
        """Open a streaming session via the underlying provider.

        ``config`` defaults to :class:`STTConfig` (pt-BR, 16 kHz). Per-session
        provider tuning goes in ``**kwargs`` (e.g. Deepgram ``endpointing=300``).
        """
        return await self._provider.open_session(
            config or STTConfig(), reconnect=reconnect, **kwargs
        )

    def validate(self) -> bool:
        """Return whether the underlying provider's config looks usable."""
        return self._provider.validate()
