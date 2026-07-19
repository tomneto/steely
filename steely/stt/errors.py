"""Exception hierarchy for :mod:`steely.stt`.

Only two things ever raise out of a session at *construction* time
(:class:`ProviderNotAvailableError`, :class:`STTConfigError`); everything that
can go wrong at *stream* time surfaces as the single :class:`STTConnectionError`
so the worker never sees a backend-native exception (Rule 4 of the design).
"""
from __future__ import annotations


class STTError(Exception):
    """Base class for all steely.stt errors."""


class ProviderNotAvailableError(STTError):
    """A provider's optional SDK is missing (e.g. ``deepgram-sdk``).

    Raised at provider construction time so failures are loud and early
    rather than at stream time.
    """


class STTConfigError(STTError):
    """Bad/missing credentials or an unusable configuration.

    Raised at construction or ``open_session`` time — before any audio is
    pushed — so the worker fails fast instead of degrading silently.
    """


class STTConnectionError(STTError):
    """The single common error for every network/backend failure.

    Adapters catch their provider-native transport/protocol exceptions and
    re-raise them as this one type, so no backend exception ever reaches the
    worker. ``retryable`` tells :class:`~steely.stt.reconnect.ReconnectPolicy`
    whether a transparent reconnect should be attempted.
    """

    def __init__(self, message: str, *, retryable: bool = True) -> None:
        super().__init__(message)
        self.retryable = retryable
