"""
EmailClient — the front door of :mod:`steely.email`.

Construct it either with a provider *name* + kwargs (it builds the provider
for you) or with a ready-made :class:`~steely.email.providers.base.EmailProvider`
instance. Then call :meth:`send` with an :class:`~steely.email.message.EmailMessage`.

>>> from steely.email import EmailClient, EmailMessage
>>> client = EmailClient("resend", api_key="re_xxx", from_email="noreply@acme.com")
>>> result = client.send(EmailMessage(to=["a@b.com"], subject="Hi", body_html="<p>Hi</p>"))
>>> result.success
True

The provider name → class mapping mirrors ``GrafanaSink``'s ``protocol=``
dispatch style used elsewhere in steely.
"""
from __future__ import annotations

import importlib
from typing import Any

from steely.email.message import EmailMessage
from steely.email.providers.base import EmailProvider
from steely.email.result import EmailResult

# name -> (module, class). Kept as strings so importing the client never pulls
# in optional dependencies until a given provider is actually requested.
_FACTORY = {
    "smtp": ("steely.email.providers.smtp", "SMTPProvider"),
    "resend": ("steely.email.providers.resend", "ResendProvider"),
    "api": ("steely.email.providers.http_api", "HTTPAPIProvider"),
    "http": ("steely.email.providers.http_api", "HTTPAPIProvider"),
}


class EmailClient:
    """Provider-agnostic email sender.

    Parameters
    ----------
    provider:
        Either a provider name (``"smtp"``, ``"resend"``, ``"api"``/``"http"``)
        or an :class:`EmailProvider` instance. When a name is given, remaining
        keyword arguments are forwarded to that provider's constructor.
    """

    def __init__(self, provider: str | EmailProvider, **kwargs: Any) -> None:
        if isinstance(provider, EmailProvider):
            self._provider = provider
        elif isinstance(provider, str):
            key = provider.lower().strip()
            if key not in _FACTORY:
                valid = sorted(set(_FACTORY))
                raise ValueError(f"Unknown email provider '{provider}'. Valid options: {valid}")
            module_name, cls_name = _FACTORY[key]
            module = importlib.import_module(module_name)
            self._provider = getattr(module, cls_name)(**kwargs)
        else:
            raise TypeError(
                "provider must be a provider name (str) or an EmailProvider instance"
            )

    @property
    def provider(self) -> EmailProvider:
        return self._provider

    @property
    def provider_name(self) -> str:
        return self._provider.name

    def send(self, message: EmailMessage, **kwargs: Any) -> EmailResult:
        """Send ``message`` via the underlying provider."""
        return self._provider.send(message, **kwargs)

    def validate(self) -> bool:
        """Return whether the underlying provider's config looks usable."""
        return self._provider.validate()
