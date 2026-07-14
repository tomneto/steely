# steely.email — Email Providers Guide

> Canonical integration guide for **humans and AI coding agents** consuming
> `steely` for email. If you are an agent working in a project that sends email,
> **read this file before writing any email code.** It tells you exactly what to
> import, how to send, and the rules you must not break.

`steely.email` sends email over **SMTP** or an **HTTP API** (Resend today, plus a
generic provider that covers Mailchimp Transactional, SendGrid, Mailgun, Postmark,
etc.) behind one small, provider-agnostic interface. Switching providers is a
one-line change; the message you build and the result you get back are identical.

---

## Install

```bash
pip install steely            # SMTP only (standard library, no extra deps)
pip install "steely[http]"    # + Resend / generic HTTP API providers (installs httpx)
```

SMTP needs **no** extra. The HTTP API providers (`ResendProvider`,
`HTTPAPIProvider`) require the `http` extra; constructing one without `httpx`
installed raises `ProviderNotAvailableError` immediately (loud, at construction
time — never a silent failure at send time).

---

## The 30-second version

```python
from steely.email import EmailClient, EmailMessage

# 1) Pick a provider by name (+ its config). Or pass a provider instance.
client = EmailClient("resend", api_key="re_xxx", from_email="noreply@acme.com")

# 2) Build a provider-agnostic message.
msg = EmailMessage(
    to=["dest@example.com"],
    subject="Welcome",
    body_html="<h1>Hi</h1>",
    body_text="Hi",            # optional plain-text fallback (recommended)
)

# 3) Send. You always get an EmailResult back — send() never raises on a
#    rejected send, it returns success=False.
result = client.send(msg)
if result.success:
    print("sent:", result.message_id)
else:
    print("failed:", result.message)
```

To use SMTP instead, change **only** step 1:

```python
client = EmailClient(
    "smtp",
    server="smtp.hostinger.com", port=587,
    username="noreply@acme.com", password="…",
)
```

---

## Core concepts

| Object | What it is |
|--------|------------|
| `EmailMessage` | Provider-agnostic description of the email (recipients, subject, bodies, cc/bcc, reply-to, sender, headers). Build one, reuse it across providers. |
| `EmailClient` | Front door. Construct with a provider name (`"smtp"`/`"resend"`/`"api"`) + kwargs, or with a provider instance. Exposes `.send(msg)` and `.validate()`. |
| `EmailResult` | Uniform return value. `success`, `message`, `provider`, `message_id`, `status_code`, `raw`. Has `.as_tuple()` and is truthy when `success`. |
| `EmailProvider` | The abstract base every backend implements (`name`, `send`, `validate`). Subclass it to add a provider. |
| `SMTPProvider` / `ResendProvider` / `HTTPAPIProvider` | The concrete backends. |

All of these are importable from the top of the package:

```python
from steely.email import (
    EmailClient, EmailMessage, EmailResult, EmailProvider,
    SMTPProvider, ResendProvider, HTTPAPIProvider,
    EmailError, ProviderNotAvailableError, EmailSendError,
)
```

`EmailClient`, `EmailMessage`, `EmailResult` are also re-exported from the top-level
package: `from steely import EmailClient, EmailMessage, EmailResult`.

---

## EmailMessage

```python
EmailMessage(
    to,                 # str | list[str] — a bare str is normalised to [str]
    subject,            # str
    body_html=None,     # str | None   (at least one of body_html/body_text required)
    body_text=None,     # str | None   (recommended alongside HTML as a fallback)
    cc=None,            # str | list[str] | None
    bcc=None,           # str | list[str] | None
    reply_to=None,      # str | None
    from_email=None,    # str | None   — overrides the provider's default sender
    from_name=None,     # str | None   — produces "Name <email>"
    headers=None,       # dict[str, str] | None
)
```

- Raises `ValueError` if `to` is empty or if **neither** body is set.
- `.recipients()` returns `to + cc + bcc` (the SMTP envelope recipients).

---

## Providers

### SMTPProvider — standard library, zero extra deps

```python
from steely.email import SMTPProvider, EmailClient

client = EmailClient(
    "smtp",
    server="smtp.hostinger.com",
    port=587,
    username="noreply@acme.com",
    password="…",
    use_tls=True,        # STARTTLS (default True)
    timeout=30,
    from_email=None,     # defaults to username
)
```

Opens a fresh connection per send (thread-safe). Builds a
`multipart/alternative` message so the plain-text fallback and HTML body travel
together.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `server` | — | SMTP host |
| `port` | — | SMTP port (587 STARTTLS, 465 usually implicit TLS — use 587 here) |
| `username` | `None` | Login user (also the default sender) |
| `password` | `None` | Login password |
| `use_tls` | `True` | Issue `STARTTLS` after connect |
| `timeout` | `30` | Socket timeout (s) |
| `from_email` | `username` | Default sender when the message omits `from_email` |

### ResendProvider — the Resend HTTP API (needs `steely[http]`)

```python
client = EmailClient(
    "resend",
    api_key="re_xxx",                 # never logged in full
    from_email="noreply@acme.com",    # must be a verified Resend domain address
    timeout=30,
    max_attempts=3,                   # transient errors (429/5xx/network) retried
)
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `api_key` | — | Resend API key (`re_…`) |
| `from_email` | `None` | Default verified sender |
| `timeout` | `30` | Per-request timeout (s) |
| `max_attempts` | `3` | Total send attempts (exponential backoff between) |

### HTTPAPIProvider — generic REST provider (needs `steely[http]`)

Use for any "POST JSON with a token" email API (Mailchimp Transactional,
SendGrid, Mailgun, Postmark, …) without a vendor-specific class.

```python
# Simple case — vendor accepts a Resend-like {from,to,subject,html,text} body:
client = EmailClient(
    "api",   # or "http"
    endpoint_url="https://api.vendor.com/v1/send",
    api_key="…",
    from_email="noreply@acme.com",
)

# Custom payload — supply a builder to match the vendor's shape:
def mandrill_body(message, sender):
    return {
        "message": {
            "from_email": sender,
            "subject": message.subject,
            "html": message.body_html,
            "to": [{"email": r, "type": "to"} for r in message.to],
        },
    }

from steely.email import HTTPAPIProvider, EmailClient
provider = HTTPAPIProvider(
    endpoint_url="https://mandrillapp.com/api/1.0/messages/send",
    api_key=MANDRILL_KEY,
    from_email="noreply@acme.com",
    request_body=mandrill_body,   # dict (static) or callable(message, sender)->dict
    auth_header="Authorization",  # set to None to omit the auth header
    auth_scheme="Bearer",         # set to None to send the raw key as the header value
    message_id_key="id",          # where to read the id from in the JSON response
)
client = EmailClient(provider)
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `endpoint_url` | — | Full URL to send to |
| `api_key` | — | Credential (injected into `auth_header`) |
| `from_email` | `None` | Default sender |
| `request_body` | `None` | `None` → default body; `dict` → sent verbatim; `callable(message, sender)->dict` |
| `auth_header` | `"Authorization"` | Header name for the credential; `None` to omit |
| `auth_scheme` | `"Bearer"` | Scheme prefix; `None` sends the raw key |
| `method` | `"POST"` | HTTP method |
| `extra_headers` | `{}` | Extra static headers |
| `timeout` | `30` | Per-request timeout (s) |
| `max_attempts` | `3` | Total attempts (429/5xx/network retried) |
| `success_codes` | `range(200,300)` | Status codes treated as success |
| `message_id_key` | `"id"` | Response JSON key for the message id |

---

## EmailResult — the return value

```python
result = client.send(msg)

result.success       # bool — did the provider accept it?
result.message       # str  — human-readable status/error (never contains secrets)
result.provider      # "smtp" | "resend" | "api"
result.message_id    # provider id when available (Resend's id, etc.)
result.status_code   # HTTP status for API providers; None for SMTP
result.raw           # parsed provider response body (for debugging)

bool(result)                 # == result.success
result.as_tuple()            # (success, message, message_id)
```

`send()` **never raises** for a rejected/failed send — it returns
`success=False`. It only raises for programmer errors (e.g. a malformed
`EmailMessage`, which fails at construction). This keeps calling code branch-free
and identical across providers.

---

## Consuming from an application (the recommended pattern)

Applications typically want a thin service around `EmailClient` and a rule for
**which** credentials to use. steely stays *credential-agnostic*: you decide.

```python
from steely.email import EmailClient, EmailMessage

class EmailService:
    """App-level wrapper. Owns credential selection; steely owns delivery."""

    def __init__(self, system_resend_key: str, system_from: str):
        self._system = EmailClient("resend", api_key=system_resend_key, from_email=system_from)

    def send_transactional(self, msg: EmailMessage):
        """System email (signup, confirmation, invite). Returns (ok, message, id)."""
        return self._system.send(msg).as_tuple()   # <-- as_tuple() bridges to a tuple API

    def client_for_workspace(self, cfg: dict) -> EmailClient:
        """Build a client from a workspace's own stored config."""
        if cfg["provider"] == "resend":
            return EmailClient("resend", api_key=cfg["api_key"], from_email=cfg["from_email"])
        if cfg["provider"] == "smtp":
            return EmailClient("smtp", server=cfg["smtp_server"], port=cfg["smtp_port"],
                               username=cfg["smtp_username"], password=cfg["smtp_password"])
        raise ValueError(f"unknown provider {cfg['provider']}")
```

Note `.as_tuple()` — it exists precisely so a service that models sending as
`(success, message, message_id)` doesn't have to reach into result fields.

---

## Rules for agents & integrators (do not skip)

1. **Never log secrets.** `api_key`/passwords must never be printed or logged in
   full. steely already redacts them (`***{last4}`) in its own logs via
   `steely.email.providers.base.redact`; if you log around a provider, redact too.
2. **steely is credential-agnostic.** It sends with whatever key/credentials it
   is given. Deciding *which* key to use, and keeping keys isolated (e.g. a system
   key must never be handed to an end-user workspace), is the **application's**
   responsibility — never the library's.
3. **`send()` returns, it doesn't raise.** Check `result.success`; don't wrap
   sends in bare `try/except` expecting exceptions for delivery failures.
4. **HTTP providers need `steely[http]`.** If you add Resend/API usage to a
   project, add the `http` extra to that project's dependencies
   (e.g. `steely[http]>=1.0.2.2`). SMTP-only projects don't need it.
5. **Don't break `steely.smtp.SendEmail`.** See below — it's a frozen legacy API
   still imported by existing code.
6. **Always provide a `from_email`.** Either on the provider (default) or on the
   message. Resend/most APIs reject a send with no sender.

---

## Legacy compatibility: `steely.smtp.SendEmail`

`steely.smtp.SendEmail` predates `steely.email` and is still imported directly by
existing consumers:

```python
from steely.smtp import SendEmail

sender = SendEmail(login="noreply@acme.com", password="…",
                   smtp_server="smtp.acme.com", smtp_port=587)
sender.check_config()                      # -> True (raises on failure)
sender.send_email(subject="Hi",            # message is the HTML body
                  message="<p>Hi</p>",
                  destination="dest@x.com") # -> {"message": "Email Successfully Sent"}
```

Its public surface is **frozen** (constructor + `check_config()` + `send_email()`).
Internally it now delegates to `SMTPProvider`, so there is a single SMTP
implementation, but the observable behaviour is unchanged. **New code should use
`EmailClient` / `EmailMessage` instead.**

---

## Adding a new provider

1. Subclass `EmailProvider` (`steely/email/providers/base.py`): implement
   `name` (property), `send(message, **kwargs) -> EmailResult`,
   `validate() -> bool`. `send` must return a result, never raise for a rejected
   send; `validate` must return `False` (not raise) on failure.
2. For HTTP transports, import the optional dep **inside `__init__`** and raise
   `ProviderNotAvailableError` if missing (see `ResendProvider`). Use
   `steely.email.retry.with_retry` + raise `RetryableError` on 429/5xx/network for
   retries.
3. Redact secrets in any logging (`redact()` helper).
4. Register the name → class in `steely/email/client.py`'s `_FACTORY` so
   `EmailClient("yourname", …)` works.
5. Add tests mirroring `test/test_resend_provider.py` (mock `http.server`).

---

## Testing without a real server

- HTTP providers: point the provider at a local `http.server.HTTPServer`
  (see `test/test_resend_provider.py`). For `ResendProvider`, set
  `provider.BASE_URL = "http://127.0.0.1:<port>"`.
- SMTP: monkeypatch `steely.email.providers.smtp.smtplib.SMTP` with a fake
  (see `test/test_smtp_provider.py`).
- Retry backoff: patch `steely.email.retry.time.sleep` to a no-op to keep tests
  instant.
