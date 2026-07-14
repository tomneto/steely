"""Tests for EmailMessage — normalisation, validation, recipient collection."""

import pytest

from steely.email import EmailMessage


def test_string_recipient_is_normalised_to_list():
    msg = EmailMessage(to="a@b.com", subject="s", body_text="hi")
    assert msg.to == ["a@b.com"]


def test_cc_bcc_string_normalised():
    msg = EmailMessage(to=["a@b.com"], subject="s", body_text="hi", cc="c@b.com", bcc="d@b.com")
    assert msg.cc == ["c@b.com"]
    assert msg.bcc == ["d@b.com"]


def test_recipients_collects_to_cc_bcc():
    msg = EmailMessage(
        to=["a@b.com"], subject="s", body_text="hi",
        cc=["c@b.com"], bcc=["d@b.com", "e@b.com"],
    )
    assert msg.recipients() == ["a@b.com", "c@b.com", "d@b.com", "e@b.com"]


def test_empty_recipients_raises():
    with pytest.raises(ValueError):
        EmailMessage(to=[], subject="s", body_text="hi")


def test_missing_body_raises():
    with pytest.raises(ValueError):
        EmailMessage(to=["a@b.com"], subject="s")


def test_html_only_is_valid():
    msg = EmailMessage(to=["a@b.com"], subject="s", body_html="<p>hi</p>")
    assert msg.body_html == "<p>hi</p>"
    assert msg.body_text is None
