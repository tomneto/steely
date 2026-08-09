"""Exception hierarchy for :mod:`steely.tts`.

Mirrors :mod:`steely.stt`: only :class:`ProviderNotAvailableError` and
:class:`TTSConfigError` ever raise out of a provider at *construction* time;
everything that can go wrong at *synthesis* time surfaces as the single
:class:`TTSConnectionError`, so the caller never sees a backend-native exception.
"""
from __future__ import annotations


class TTSError(Exception):
    """Base class for all steely.tts errors."""


class ProviderNotAvailableError(TTSError):
    """A provider's optional SDK/client is missing (e.g. ``elevenlabs``).

    Raised at provider construction time so failures are loud and early rather
    than at synthesis time.
    """


class TTSConfigError(TTSError):
    """Bad/missing credentials or an unusable configuration.

    Raised at construction or ``open_session`` time — before any text is
    pushed — so the caller fails fast instead of degrading silently.
    """


class TTSConnectionError(TTSError):
    """The single common error for every network/backend failure.

    Adapters catch their provider-native transport/protocol exceptions and
    re-raise them as this one type, so no backend exception ever reaches the
    caller. ``retryable`` tells :class:`~steely.tts.reconnect.ReconnectPolicy`
    whether a transparent reconnect should be attempted.
    """

    def __init__(self, message: str, *, retryable: bool = True) -> None:
        super().__init__(message)
        self.retryable = retryable
