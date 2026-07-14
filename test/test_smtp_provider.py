"""Tests for SMTPProvider using a fake smtplib.SMTP (no real network)."""

import smtplib

import pytest

from steely.email import EmailMessage, EmailResult, SMTPProvider


class FakeSMTP:
    """Minimal stand-in for smtplib.SMTP that records what it was asked to do."""

    instances = []

    def __init__(self, host, port, timeout=None):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.tls = False
        self.logged_in = None
        self.sent = []
        self.quit_called = False
        self.fail_on_send = False
        FakeSMTP.instances.append(self)

    def starttls(self):
        self.tls = True

    def login(self, user, password):
        self.logged_in = (user, password)

    def sendmail(self, sender, recipients, message):
        if self.fail_on_send:
            raise smtplib.SMTPException("nope")
        self.sent.append((sender, recipients, message))

    def quit(self):
        self.quit_called = True


@pytest.fixture(autouse=True)
def _patch_smtp(monkeypatch):
    FakeSMTP.instances = []
    monkeypatch.setattr("steely.email.providers.smtp.smtplib.SMTP", FakeSMTP)
    yield


def _provider():
    return SMTPProvider(
        server="smtp.example.com", port=587,
        username="user@example.com", password="secret",
    )


def test_send_success_returns_result():
    result = _provider().send(
        EmailMessage(to=["dest@example.com"], subject="Hi", body_html="<p>Hi</p>")
    )
    assert isinstance(result, EmailResult)
    assert result.success is True
    assert result.provider == "smtp"


def test_send_uses_starttls_and_login():
    _provider().send(EmailMessage(to=["dest@example.com"], subject="Hi", body_text="Hi"))
    conn = FakeSMTP.instances[-1]
    assert conn.tls is True
    assert conn.logged_in == ("user@example.com", "secret")
    assert conn.quit_called is True


def test_send_envelope_and_recipients():
    _provider().send(
        EmailMessage(
            to=["a@x.com"], subject="Hi", body_html="<p>Hi</p>",
            cc=["c@x.com"], bcc=["b@x.com"],
        )
    )
    sender, recipients, raw = FakeSMTP.instances[-1].sent[-1]
    assert sender == "user@example.com"
    assert recipients == ["a@x.com", "c@x.com", "b@x.com"]
    assert "multipart/alternative" in raw
    assert "To: a@x.com" in raw
    assert "Cc: c@x.com" in raw


def test_send_builds_text_and_html_parts():
    _provider().send(
        EmailMessage(to=["a@x.com"], subject="Hi", body_html="<p>H</p>", body_text="H")
    )
    raw = FakeSMTP.instances[-1].sent[-1][2]
    assert "text/plain" in raw
    assert "text/html" in raw


def test_send_failure_returns_unsuccessful_result():
    provider = _provider()

    def failing(host, port, timeout=None):
        inst = FakeSMTP(host, port, timeout)
        inst.fail_on_send = True
        return inst

    # Replace with a factory that yields a connection which fails on send.
    import steely.email.providers.smtp as smtp_mod
    smtp_mod.smtplib.SMTP = failing
    try:
        result = provider.send(EmailMessage(to=["a@x.com"], subject="s", body_text="b"))
    finally:
        smtp_mod.smtplib.SMTP = FakeSMTP
    assert result.success is False
    assert result.message.startswith("Error sending email")


def test_validate_true():
    assert _provider().validate() is True
