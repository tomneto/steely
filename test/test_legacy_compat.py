"""
Backward-compatibility tests for ``steely.smtp.SendEmail``.

These pin the *observable* contract that existing consumers depend on
(constructor signature, return value, exception on failure, HTML body,
``From``/envelope = login). Do not relax these without a major version bump.
"""

import smtplib

import pytest

from steely.smtp import SendEmail


class FakeSMTP:
    instances = []

    def __init__(self, host, port, timeout=None):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.tls = False
        self.logged_in = None
        self.sent = []
        self.quit_called = False
        FakeSMTP.instances.append(self)

    def starttls(self):
        self.tls = True

    def login(self, user, password):
        self.logged_in = (user, password)

    def sendmail(self, sender, recipients, message):
        self.sent.append((sender, recipients, message))

    def quit(self):
        self.quit_called = True


@pytest.fixture(autouse=True)
def _patch_smtp(monkeypatch):
    FakeSMTP.instances = []
    monkeypatch.setattr("steely.email.providers.smtp.smtplib.SMTP", FakeSMTP)
    yield


def _sender():
    return SendEmail(
        login="noreply@acme.com", password="secret",
        smtp_server="smtp.acme.com", smtp_port=587,
    )


def test_send_email_returns_legacy_dict():
    result = _sender().send_email(subject="Hi", message="<p>Hi</p>", destination="dest@x.com")
    assert result == {"message": "Email Successfully Sent"}


def test_send_email_accepts_keyword_style_used_by_consumers():
    # selfApi calls: send_email(destination=..., subject=..., message=...)
    result = _sender().send_email(destination="dest@x.com", subject="Confirm", message="<b>x</b>")
    assert result == {"message": "Email Successfully Sent"}


def test_from_and_envelope_are_login():
    _sender().send_email(subject="Hi", message="<p>Hi</p>", destination="dest@x.com")
    sender, recipients, raw = FakeSMTP.instances[-1].sent[-1]
    assert sender == "noreply@acme.com"
    assert recipients == ["dest@x.com"]
    assert "From: noreply@acme.com" in raw


def test_body_is_html():
    _sender().send_email(subject="Hi", message="<p>Hi</p>", destination="dest@x.com")
    raw = FakeSMTP.instances[-1].sent[-1][2]
    assert "text/html" in raw


def test_send_email_raises_on_failure(monkeypatch):
    def failing(host, port, timeout=None):
        raise smtplib.SMTPException("down")

    monkeypatch.setattr("steely.email.providers.smtp.smtplib.SMTP", failing)
    with pytest.raises(Exception) as exc:
        _sender().send_email(subject="Hi", message="x", destination="d@x.com")
    assert "Error sending email" in str(exc.value)


def test_check_config_true_on_success():
    assert _sender().check_config() is True


def test_check_config_raises_on_failure(monkeypatch):
    def failing(host, port, timeout=None):
        raise smtplib.SMTPException("bad login")

    monkeypatch.setattr("steely.email.providers.smtp.smtplib.SMTP", failing)
    with pytest.raises(Exception):
        _sender().check_config()


def test_uses_smtp_provider_internally():
    assert _sender()._provider.name == "smtp"
