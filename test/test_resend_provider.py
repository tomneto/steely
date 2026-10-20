"""Tests for ResendProvider against a controllable mock HTTP server.

Requires httpx (the ``steely[http]`` extra). Skipped if httpx is absent.
"""

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

httpx = pytest.importorskip("httpx")

from steely.email import EmailMessage, ProviderNotAvailableError, ResendProvider
from steely.email.providers.base import redact


class _State:
    def __init__(self):
        self.requests = []
        self.responses = [(200, {"id": "email_default"})]
        self.idx = 0
        self.lock = threading.Lock()


def _make_handler(state):
    class Handler(BaseHTTPRequestHandler):
        def _respond(self):
            with state.lock:
                i = min(state.idx, len(state.responses) - 1)
                status, body = state.responses[i]
                state.idx += 1
            payload = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length)
            with state.lock:
                state.requests.append(
                    {
                        "method": "POST",
                        "path": self.path,
                        "headers": dict(self.headers),
                        "json": json.loads(raw) if raw else None,
                    }
                )
            self._respond()

        def do_GET(self):
            with state.lock:
                state.requests.append(
                    {"method": "GET", "path": self.path, "headers": dict(self.headers)}
                )
            self._respond()

        def log_message(self, *args):
            pass

    return Handler


@pytest.fixture
def server():
    state = _State()
    srv = HTTPServer(("127.0.0.1", 0), _make_handler(state))
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    srv.state = state
    srv.base_url = f"http://127.0.0.1:{port}"
    yield srv
    srv.shutdown()


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    # Make retry backoff instant.
    monkeypatch.setattr("steely.email.retry.time.sleep", lambda s: None)


def _provider(server, **kwargs):
    p = ResendProvider(api_key="re_testkey_1234", from_email="noreply@acme.com", **kwargs)
    p.BASE_URL = server.base_url
    return p


def _msg():
    return EmailMessage(
        to=["dest@example.com"], subject="Hi", body_html="<p>Hi</p>", body_text="Hi"
    )


def test_redact_never_exposes_full_secret():
    assert redact("re_supersecret_ABCD") == "***ABCD"
    assert redact("") == "***"
    assert redact("ab") == "***"


def test_send_success_returns_message_id(server):
    server.state.responses = [(200, {"id": "email_abc"})]
    result = _provider(server).send(_msg())
    assert result.success is True
    assert result.message_id == "email_abc"
    assert result.status_code == 200
    assert result.provider == "resend"


def test_send_sends_expected_payload_and_auth(server):
    _provider(server).send(_msg())
    req = server.state.requests[-1]
    assert req["path"] == "/emails"
    assert req["headers"]["Authorization"] == "Bearer re_testkey_1234"
    assert req["json"]["from"] == "noreply@acme.com"
    assert req["json"]["to"] == ["dest@example.com"]
    assert req["json"]["html"] == "<p>Hi</p>"
    assert req["json"]["text"] == "Hi"


def test_4xx_is_not_retried(server):
    server.state.responses = [(422, {"message": "invalid"})]
    result = _provider(server).send(_msg())
    assert result.success is False
    assert result.status_code == 422
    assert len(server.state.requests) == 1  # no retry on 4xx


def test_retries_transient_then_succeeds(server):
    server.state.responses = [(429, {}), (500, {}), (200, {"id": "ok"})]
    result = _provider(server, max_attempts=3).send(_msg())
    assert result.success is True
    assert len(server.state.requests) == 3


def test_quota_exhaustion_429_is_not_retried(server):
    """A 429 for plan quota is permanent — retrying wastes the caller's allowance.

    Resend reuses 429 for rate limiting (transient) and for an exhausted daily or
    monthly quota (not transient). Retrying the latter turned one doomed send into
    three requests against an already-spent quota.
    """
    server.state.responses = [(429, {"name": "daily_quota_exceeded",
                                     "message": "You have reached your daily quota"})]
    result = _provider(server, max_attempts=3).send(_msg())
    assert result.success is False
    assert result.status_code == 429
    assert len(server.state.requests) == 1
    # The body must survive into the message so callers can classify it.
    assert "daily_quota_exceeded" in result.message


def test_monthly_quota_429_is_not_retried(server):
    server.state.responses = [(429, {"name": "monthly_quota_exceeded"})]
    result = _provider(server, max_attempts=3).send(_msg())
    assert result.success is False
    assert len(server.state.requests) == 1


def test_rate_limit_429_is_still_retried(server):
    """The transient flavour of 429 must keep retrying."""
    server.state.responses = [(429, {"name": "rate_limit_exceeded"}), (200, {"id": "ok"})]
    result = _provider(server, max_attempts=3).send(_msg())
    assert result.success is True
    assert len(server.state.requests) == 2


def test_retries_exhausted(server):
    server.state.responses = [(500, {"e": "boom"})]
    result = _provider(server, max_attempts=3).send(_msg())
    assert result.success is False
    assert len(server.state.requests) == 3


def test_missing_from_is_rejected(server):
    provider = ResendProvider(api_key="re_x", from_email=None)
    provider.BASE_URL = server.base_url
    result = provider.send(EmailMessage(to=["a@b.com"], subject="s", body_text="b"))
    assert result.success is False
    assert "from" in result.message.lower()
    assert len(server.state.requests) == 0  # never hit the network


def test_from_name_formats_sender(server):
    msg = EmailMessage(to=["a@b.com"], subject="s", body_html="<p>x</p>", from_name="ACME")
    _provider(server).send(msg)
    assert server.state.requests[-1]["json"]["from"] == "ACME <noreply@acme.com>"


def test_missing_httpx_raises_provider_not_available(monkeypatch):
    monkeypatch.setitem(sys.modules, "httpx", None)
    with pytest.raises(ProviderNotAvailableError):
        ResendProvider(api_key="re_x", from_email="a@b.com")
