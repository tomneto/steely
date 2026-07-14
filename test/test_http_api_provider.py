"""Tests for the generic HTTPAPIProvider against a mock HTTP server."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

httpx = pytest.importorskip("httpx")

from steely.email import EmailMessage, HTTPAPIProvider


class _State:
    def __init__(self):
        self.requests = []
        self.responses = [(200, {"id": "msg_default"})]
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
                    {"path": self.path, "headers": dict(self.headers),
                     "json": json.loads(raw) if raw else None}
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
    srv.url = f"http://127.0.0.1:{port}/send"
    yield srv
    srv.shutdown()


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr("steely.email.retry.time.sleep", lambda s: None)


def _msg():
    return EmailMessage(to=["dest@example.com"], subject="Hi", body_html="<p>Hi</p>")


def test_default_body_and_bearer_auth(server):
    provider = HTTPAPIProvider(endpoint_url=server.url, api_key="key_123", from_email="a@acme.com")
    result = provider.send(_msg())
    assert result.success is True
    assert result.message_id == "msg_default"
    req = server.state.requests[-1]
    assert req["headers"]["Authorization"] == "Bearer key_123"
    assert req["json"]["from"] == "a@acme.com"
    assert req["json"]["to"] == ["dest@example.com"]


def test_custom_request_body_builder(server):
    def builder(message, sender):
        return {"custom": True, "subject": message.subject, "sender": sender}

    provider = HTTPAPIProvider(
        endpoint_url=server.url, api_key="k", from_email="a@acme.com", request_body=builder,
    )
    provider.send(_msg())
    assert server.state.requests[-1]["json"] == {
        "custom": True, "subject": "Hi", "sender": "a@acme.com",
    }


def test_custom_auth_header_and_scheme(server):
    provider = HTTPAPIProvider(
        endpoint_url=server.url, api_key="abc",
        auth_header="X-Api-Key", auth_scheme=None,
    )
    provider.send(_msg())
    assert server.state.requests[-1]["headers"]["X-Api-Key"] == "abc"


def test_no_auth_header(server):
    provider = HTTPAPIProvider(endpoint_url=server.url, api_key="abc", auth_header=None)
    provider.send(_msg())
    assert "Authorization" not in server.state.requests[-1]["headers"]


def test_custom_message_id_key(server):
    server.state.responses = [(200, {"_id": "xyz"})]
    provider = HTTPAPIProvider(endpoint_url=server.url, api_key="k", message_id_key="_id")
    result = provider.send(_msg())
    assert result.message_id == "xyz"


def test_error_status_returns_failure(server):
    server.state.responses = [(400, {"error": "bad"})]
    provider = HTTPAPIProvider(endpoint_url=server.url, api_key="k")
    result = provider.send(_msg())
    assert result.success is False
    assert result.status_code == 400


def test_validate_defaults_true():
    provider = HTTPAPIProvider(endpoint_url="http://x/y", api_key="k")
    assert provider.validate() is True
