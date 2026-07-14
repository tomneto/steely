"""Tests for EmailClient factory dispatch and delegation."""

import pytest

from steely.email import EmailClient, EmailMessage, EmailResult
from steely.email.providers.base import EmailProvider


class FakeProvider(EmailProvider):
    def __init__(self):
        self.sent = []

    @property
    def name(self):
        return "fake"

    def send(self, message, **kwargs):
        self.sent.append((message, kwargs))
        return EmailResult(success=True, message="ok", provider=self.name, message_id="1")

    def validate(self):
        return True


def test_dispatch_smtp():
    client = EmailClient("smtp", server="localhost", port=25)
    assert client.provider_name == "smtp"


def test_dispatch_resend():
    pytest.importorskip("httpx")
    client = EmailClient("resend", api_key="re_x", from_email="a@b.com")
    assert client.provider_name == "resend"


def test_dispatch_api_and_http_aliases():
    pytest.importorskip("httpx")
    assert EmailClient("api", endpoint_url="http://x/y", api_key="k").provider_name == "api"
    assert EmailClient("http", endpoint_url="http://x/y", api_key="k").provider_name == "api"


def test_dispatch_is_case_insensitive():
    assert EmailClient("SMTP", server="localhost", port=25).provider_name == "smtp"


def test_unknown_provider_raises():
    with pytest.raises(ValueError):
        EmailClient("carrier-pigeon")


def test_instance_passthrough():
    provider = FakeProvider()
    client = EmailClient(provider)
    assert client.provider is provider


def test_send_delegates_to_provider():
    provider = FakeProvider()
    client = EmailClient(provider)
    msg = EmailMessage(to=["a@b.com"], subject="s", body_text="b")
    result = client.send(msg, from_email="x@y.com")
    assert result.success is True
    assert provider.sent[-1][0] is msg
    assert provider.sent[-1][1] == {"from_email": "x@y.com"}


def test_validate_delegates():
    assert EmailClient(FakeProvider()).validate() is True


def test_bad_provider_type_raises():
    with pytest.raises(TypeError):
        EmailClient(123)
