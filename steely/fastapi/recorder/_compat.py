"""
Internal FastAPI compatibility shim
===================================

The recorders in :mod:`steely.fastapi.recorder` are the only part of steely that
needs FastAPI, and FastAPI is an *optional* extra (``pip install "steely[fastapi]"``).

This module resolves ``fastapi.Request`` lazily so that importing
:mod:`steely.fastapi.recorder` never explodes with a bare ``ModuleNotFoundError``
when the extra is missing — the decorators raise a clear, actionable error
instead, and only when they are actually used.
"""

from typing import Any

__all__ = ["FastAPINotAvailableError", "require_request"]

_INSTALL_HINT = (
    "FastAPI is required for steely.fastapi.recorder but is not installed. "
    'Install the optional extra with: pip install "steely[fastapi]"'
)

_request_cls: Any = None


class FastAPINotAvailableError(ImportError):
    """Raised when a FastAPI recorder is used without FastAPI installed."""


def require_request() -> Any:
    """
    Return ``fastapi.Request``, importing FastAPI on first use.

    Returns
    -------
    type
        The ``fastapi.Request`` class.

    Raises
    ------
    FastAPINotAvailableError
        If FastAPI is not installed.
    """
    global _request_cls
    if _request_cls is None:
        try:
            from fastapi import Request
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise FastAPINotAvailableError(_INSTALL_HINT) from exc
        _request_cls = Request
    return _request_cls
