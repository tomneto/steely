"""
FastAPI Request Recorders
=========================

Decorators that capture live FastAPI traffic into reproducible artifacts:

- :func:`curl` — executable ``.sh`` scripts of curl commands.
- :func:`postman` — Postman Collection v2.1 JSON files.

Both redact credential headers and sensitive body keys by default; see
:mod:`steely.fastapi.recorder._redact`.

FastAPI itself is an optional extra (``pip install "steely[fastapi]"``). It is
imported lazily, so importing this module without FastAPI installed is safe —
the decorators raise :class:`FastAPINotAvailableError` when used.
"""

from steely.fastapi.recorder._compat import FastAPINotAvailableError
from steely.fastapi.recorder._redact import SENSITIVE_BODY_KEYS, SENSITIVE_HEADERS
from steely.fastapi.recorder.curl import CurlRecorder, curl
from steely.fastapi.recorder.postman import PostmanRecorder, postman

__all__ = [
    "curl",
    "CurlRecorder",
    "postman",
    "PostmanRecorder",
    "FastAPINotAvailableError",
    "SENSITIVE_HEADERS",
    "SENSITIVE_BODY_KEYS",
]
