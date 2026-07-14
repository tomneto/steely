"""Tests for EmailResult — tuple adapter and truthiness."""

from steely.email import EmailResult


def test_as_tuple():
    r = EmailResult(success=True, message="ok", provider="resend", message_id="abc")
    assert r.as_tuple() == (True, "ok", "abc")


def test_as_tuple_without_id():
    r = EmailResult(success=False, message="boom", provider="smtp")
    assert r.as_tuple() == (False, "boom", None)


def test_bool_reflects_success():
    assert bool(EmailResult(success=True, message="", provider="smtp")) is True
    assert bool(EmailResult(success=False, message="", provider="smtp")) is False
