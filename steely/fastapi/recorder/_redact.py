"""
Redaction helpers for the FastAPI recorders
===========================================

The curl and Postman recorders write captured requests to files on disk. Those
files are frequently committed, pasted into tickets or shared with teammates, so
by default steely strips anything that looks like a credential.

Two independent layers:

- :func:`redact_headers` — drops/masks whole headers by name
  (``Authorization``, ``Cookie``, ``X-API-Key``, …).
- :func:`redact_body` — walks a JSON-ish body and masks values whose *key* looks
  sensitive (``password``, ``token``, ``secret``, …).

Both are opt-out, never opt-in: a caller has to explicitly ask for the raw
values (``keep_sensitive_headers=True`` / ``redact_body=False``).

Examples
--------
>>> redact_headers({"Authorization": "Bearer abc", "Accept": "application/json"})
{'Authorization': '***', 'Accept': 'application/json'}
>>> redact_body({"user": "ana", "password": "hunter2"})
{'user': 'ana', 'password': '***'}
"""

from collections.abc import Iterable
from typing import Any, Optional

__all__ = [
    "REDACTED",
    "SENSITIVE_HEADERS",
    "SENSITIVE_BODY_KEYS",
    "normalize_sensitive_headers",
    "redact_headers",
    "redact_body",
]

#: Placeholder written in place of a sensitive value.
REDACTED = "***"

#: Header names (lowercase) masked by default.
SENSITIVE_HEADERS: set[str] = {
    "authorization",
    "cookie",
    "set-cookie",
    "proxy-authorization",
    "x-api-key",
    "api-key",
    "x-auth-token",
}

#: Substrings that mark a body key as sensitive (matched case-insensitively).
SENSITIVE_BODY_KEYS: set[str] = {
    "password",
    "passwd",
    "token",
    "secret",
    "api_key",
    "apikey",
    "access_key",
    "private_key",
    "credit_card",
    "card_number",
    "cvv",
    "authorization",
    "session",
}

# Depth guard so a pathological/recursive payload cannot hang the recorder.
_MAX_DEPTH = 12


def normalize_sensitive_headers(headers: Optional[Iterable[str]]) -> set[str]:
    """
    Normalize a user-supplied set of header names.

    Parameters
    ----------
    headers : iterable of str, optional
        Header names to treat as sensitive. ``None`` means "use the defaults".

    Returns
    -------
    set of str
        Lowercase header names.
    """
    if headers is None:
        return set(SENSITIVE_HEADERS)
    return {str(h).lower() for h in headers}


def redact_headers(
    headers: dict[str, str],
    sensitive: Optional[Iterable[str]] = None,
    enabled: bool = True,
) -> dict[str, str]:
    """
    Return a copy of ``headers`` with sensitive values masked.

    Parameters
    ----------
    headers : dict
        Request headers.
    sensitive : iterable of str, optional
        Header names to mask. Defaults to :data:`SENSITIVE_HEADERS`.
    enabled : bool, optional
        When ``False`` the headers are returned untouched (caller explicitly
        asked to keep credentials). Default ``True``.

    Returns
    -------
    dict
        Header mapping, order preserved.
    """
    if not enabled:
        return dict(headers)

    names = normalize_sensitive_headers(sensitive)
    return {
        key: (REDACTED if key.lower() in names else value)
        for key, value in headers.items()
    }


def _is_sensitive_key(key: Any) -> bool:
    lowered = str(key).lower()
    return any(marker in lowered for marker in SENSITIVE_BODY_KEYS)


def redact_body(body: Any, enabled: bool = True, _depth: int = 0) -> Any:
    """
    Recursively mask sensitive values in a request body.

    Dict keys are matched against :data:`SENSITIVE_BODY_KEYS`; matching values
    become ``"***"`` regardless of their type. Lists and tuples are walked
    element-wise. Anything else (including plain-text bodies, which carry no key
    to match on) is returned unchanged.

    Parameters
    ----------
    body : any
        Parsed request body.
    enabled : bool, optional
        When ``False`` the body is returned untouched. Default ``True``.

    Returns
    -------
    any
        A redacted copy of the body (the input is never mutated).
    """
    if not enabled or body is None:
        return body

    if _depth >= _MAX_DEPTH:
        return body

    if isinstance(body, dict):
        return {
            key: (
                REDACTED
                if _is_sensitive_key(key)
                else redact_body(value, enabled=True, _depth=_depth + 1)
            )
            for key, value in body.items()
        }

    if isinstance(body, (list, tuple)):
        return [redact_body(item, enabled=True, _depth=_depth + 1) for item in body]

    return body
