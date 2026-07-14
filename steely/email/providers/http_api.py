"""
HTTPAPIProvider — generic HTTP email-API delivery.

A single configurable provider that can talk to most "POST JSON with a bearer
token" email APIs (Mailchimp Transactional, SendGrid, Mailgun, Postmark, ...)
without a dedicated class per vendor. Point it at an endpoint, give it an API
key, and optionally supply a ``request_body`` template or builder to match the
vendor's payload shape.

Requires the optional ``httpx`` dependency (``pip install "steely[http]"``);
constructing it without ``httpx`` raises
:class:`~steely.email.errors.ProviderNotAvailableError`.

Examples
--------
Mailchimp Transactional (Mandrill), whose payload is *not* the default shape,
so pass a ``request_body`` builder::

    def mandrill_body(message, sender):
        return {
            "key": "IGNORED_USE_HEADER",   # or put the key here instead of a header
            "message": {
                "from_email": sender,
                "subject": message.subject,
                "html": message.body_html,
                "to": [{"email": r, "type": "to"} for r in message.to],
            },
        }

    provider = HTTPAPIProvider(
        endpoint_url="https://mandrillapp.com/api/1.0/messages/send",
        api_key=MANDRILL_KEY,
        from_email="noreply@acme.com",
        request_body=mandrill_body,
        auth_header=None,               # Mandrill takes the key in the body
    )
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, Optional, Union

from steely.email.errors import ProviderNotAvailableError
from steely.email.message import EmailMessage
from steely.email.providers.base import EmailProvider, redact
from steely.email.result import EmailResult
from steely.email.retry import RetryableError, with_retry
from steely.logger import Logger

BodyBuilder = Callable[[EmailMessage, Optional[str]], Dict[str, Any]]


class HTTPAPIProvider(EmailProvider):
    """Generic REST email provider.

    Parameters
    ----------
    endpoint_url:
        Full URL to POST (or ``method``) the request to.
    api_key:
        Credential injected into the auth header (unless ``auth_header`` is
        ``None`` and the key is placed in the body by ``request_body``).
    from_email:
        Default sender when a message doesn't set ``from_email``.
    request_body:
        How to build the request body. One of:
        - ``None`` (default): a Resend-like ``{from,to,subject,html,text,...}``
          object is produced automatically.
        - a ``dict``: sent verbatim (static payload).
        - a callable ``(message, sender) -> dict``: full control per send.
    auth_header, auth_scheme:
        Header name and scheme for the credential, e.g.
        ``Authorization`` + ``Bearer`` → ``Authorization: Bearer <key>``.
        Set ``auth_header=None`` to omit the auth header entirely.
    method:
        HTTP method (default ``"POST"``).
    extra_headers:
        Additional static headers to send.
    timeout, max_attempts:
        Per-request timeout and total send attempts (429/5xx/network retried).
    success_codes:
        Status codes treated as success (default ``range(200, 300)``).
    message_id_key:
        Key to read the provider message id from in the JSON response.
    """

    def __init__(
        self,
        endpoint_url: str,
        api_key: str,
        from_email: Optional[str] = None,
        request_body: Union[Dict[str, Any], BodyBuilder, None] = None,
        auth_header: Optional[str] = "Authorization",
        auth_scheme: Optional[str] = "Bearer",
        method: str = "POST",
        extra_headers: Optional[Dict[str, str]] = None,
        timeout: int = 30,
        max_attempts: int = 3,
        success_codes: Iterable[int] = range(200, 300),
        message_id_key: str = "id",
    ) -> None:
        try:
            import httpx  # noqa: F401
        except ImportError as exc:  # pragma: no cover - exercised via monkeypatch
            raise ProviderNotAvailableError(
                "HTTPAPIProvider requires 'httpx'. Install with: pip install 'steely[http]'"
            ) from exc
        self._httpx = httpx
        self.endpoint_url = endpoint_url
        self.api_key = api_key
        self.from_email = from_email
        self.request_body = request_body
        self.auth_header = auth_header
        self.auth_scheme = auth_scheme
        self.method = method.upper()
        self.extra_headers = extra_headers or {}
        self.timeout = timeout
        self.max_attempts = max_attempts
        self.success_codes = set(success_codes)
        self.message_id_key = message_id_key
        self.__logger__ = Logger(
            app_name=self.__class__.__name__, owner=redact(api_key)
        ).log

    @property
    def name(self) -> str:
        return "api"

    def _default_body(self, message: EmailMessage, sender: Optional[str]) -> Dict[str, Any]:
        body: Dict[str, Any] = {"from": sender, "to": message.to, "subject": message.subject}
        if message.body_html:
            body["html"] = message.body_html
        if message.body_text:
            body["text"] = message.body_text
        if message.cc:
            body["cc"] = message.cc
        if message.bcc:
            body["bcc"] = message.bcc
        if message.reply_to:
            body["reply_to"] = message.reply_to
        if message.headers:
            body["headers"] = message.headers
        return body

    def _build_body(self, message: EmailMessage, from_email: Optional[str]) -> Dict[str, Any]:
        sender = message.from_email or from_email or self.from_email
        if callable(self.request_body):
            return self.request_body(message, sender)
        if isinstance(self.request_body, dict):
            return self.request_body
        return self._default_body(message, sender)

    def send(
        self, message: EmailMessage, from_email: Optional[str] = None, **kwargs: Any
    ) -> EmailResult:
        body = self._build_body(message, from_email)
        headers = {"Content-Type": "application/json"}
        if self.auth_header:
            if self.auth_scheme:
                headers[self.auth_header] = f"{self.auth_scheme} {self.api_key}"
            else:
                headers[self.auth_header] = str(self.api_key)
        headers.update(self.extra_headers)

        @with_retry(
            max_attempts=self.max_attempts,
            retry_on=(RetryableError, self._httpx.TransportError),
        )
        def _do():
            resp = self._httpx.request(
                self.method,
                self.endpoint_url,
                json=body,
                headers=headers,
                timeout=self.timeout,
            )
            if resp.status_code == 429 or resp.status_code >= 500:
                raise RetryableError(f"HTTP API transient error {resp.status_code}: {resp.text}")
            return resp

        try:
            resp = _do()
        except Exception as exc:  # noqa: BLE001 - surfaced as a result
            self.__logger__("error", f"HTTP API send failed: {exc}")
            return EmailResult(success=False, message=str(exc), provider=self.name)

        if resp.status_code in self.success_codes:
            data: Any = {}
            try:
                data = resp.json()
            except Exception:  # noqa: BLE001
                pass
            mid = data.get(self.message_id_key) if isinstance(data, dict) else None
            return EmailResult(
                success=True,
                message="Email sent via HTTP API",
                provider=self.name,
                message_id=mid,
                status_code=resp.status_code,
                raw=data if isinstance(data, dict) else None,
            )

        self.__logger__("error", f"HTTP API error {resp.status_code}")
        return EmailResult(
            success=False,
            message=f"HTTP API error {resp.status_code}: {resp.text}",
            provider=self.name,
            status_code=resp.status_code,
        )

    def validate(self) -> bool:
        # There is no universal validation endpoint for an arbitrary API, so a
        # successfully-constructed provider is considered valid. Vendors with a
        # ping endpoint can be validated by the caller before use.
        return True
