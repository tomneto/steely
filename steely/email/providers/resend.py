"""
ResendProvider — delivery through the Resend HTTP API (https://resend.com).

Requires the optional ``httpx`` dependency::

    pip install "steely[http]"

If ``httpx`` is not installed, constructing the provider raises
:class:`~steely.email.errors.ProviderNotAvailableError` immediately.

The provider is **credential-agnostic**: it sends with whatever ``api_key`` it
is given. Deciding *which* key to use (a system key vs. a per-workspace key)
and keeping keys isolated is the responsibility of the calling application,
not this library.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from steely.email.errors import ProviderNotAvailableError
from steely.email.message import EmailMessage
from steely.email.providers.base import EmailProvider, redact
from steely.email.result import EmailResult
from steely.email.retry import RetryableError, with_retry
from steely.logger import Logger


class ResendProvider(EmailProvider):
    """Send email via ``POST https://api.resend.com/emails``.

    Parameters
    ----------
    api_key:
        Resend API key (``re_...``). Never logged in full.
    from_email:
        Default sender (must be a verified Resend domain address) used when a
        message doesn't set ``from_email``.
    timeout:
        Per-request timeout in seconds.
    max_attempts:
        Total send attempts; transient errors (429/5xx/network) are retried
        with exponential backoff.
    """

    BASE_URL = "https://api.resend.com"

    def __init__(
        self,
        api_key: str,
        from_email: Optional[str] = None,
        timeout: int = 30,
        max_attempts: int = 3,
    ) -> None:
        try:
            import httpx  # noqa: F401
        except ImportError as exc:  # pragma: no cover - exercised via monkeypatch
            raise ProviderNotAvailableError(
                "ResendProvider requires 'httpx'. Install with: pip install 'steely[http]'"
            ) from exc
        self._httpx = httpx
        self.api_key = api_key
        self.from_email = from_email
        self.timeout = timeout
        self.max_attempts = max_attempts
        self.__logger__ = Logger(
            app_name=self.__class__.__name__, owner=redact(api_key)
        ).log

    @property
    def name(self) -> str:
        return "resend"

    def _payload(self, message: EmailMessage, from_email: Optional[str]) -> Dict[str, Any]:
        sender = message.from_email or from_email or self.from_email
        if message.from_name and sender:
            sender = f"{message.from_name} <{sender}>"
        payload: Dict[str, Any] = {
            "from": sender,
            "to": message.to,
            "subject": message.subject,
        }
        if message.body_html:
            payload["html"] = message.body_html
        if message.body_text:
            payload["text"] = message.body_text
        if message.cc:
            payload["cc"] = message.cc
        if message.bcc:
            payload["bcc"] = message.bcc
        if message.reply_to:
            payload["reply_to"] = message.reply_to
        if message.headers:
            payload["headers"] = message.headers
        return payload

    def send(
        self, message: EmailMessage, from_email: Optional[str] = None, **kwargs: Any
    ) -> EmailResult:
        payload = self._payload(message, from_email)
        if not payload.get("from"):
            return EmailResult(
                success=False,
                message="Resend requires a 'from' address (set from_email on the provider or message)",
                provider=self.name,
            )
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        @with_retry(
            max_attempts=self.max_attempts,
            retry_on=(RetryableError, self._httpx.TransportError),
        )
        def _do():
            resp = self._httpx.post(
                f"{self.BASE_URL}/emails",
                json=payload,
                headers=headers,
                timeout=self.timeout,
            )
            if resp.status_code == 429 or resp.status_code >= 500:
                raise RetryableError(f"Resend transient error {resp.status_code}: {resp.text}")
            return resp

        try:
            resp = _do()
        except Exception as exc:  # noqa: BLE001 - surfaced as a result
            self.__logger__("error", f"Resend send failed: {exc}")
            return EmailResult(success=False, message=str(exc), provider=self.name)

        if 200 <= resp.status_code < 300:
            data: Dict[str, Any] = {}
            try:
                data = resp.json()
            except Exception:  # noqa: BLE001
                pass
            self.__logger__("success", "Email sent via Resend")
            return EmailResult(
                success=True,
                message="Email sent via Resend",
                provider=self.name,
                message_id=data.get("id") if isinstance(data, dict) else None,
                status_code=resp.status_code,
                raw=data if isinstance(data, dict) else None,
            )

        self.__logger__("error", f"Resend error {resp.status_code}")
        return EmailResult(
            success=False,
            message=f"Resend error {resp.status_code}: {resp.text}",
            provider=self.name,
            status_code=resp.status_code,
        )

    def validate(self) -> bool:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            resp = self._httpx.get(
                f"{self.BASE_URL}/api-keys", headers=headers, timeout=self.timeout
            )
            return resp.status_code < 400
        except Exception as exc:  # noqa: BLE001
            self.__logger__("error", f"Resend validate failed: {exc}")
            return False
