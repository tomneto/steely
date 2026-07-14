"""Unit tests for the with_retry helper."""

import pytest

from steely.email.retry import RetryableError, with_retry


def test_succeeds_first_try():
    calls = []

    @with_retry(max_attempts=3, sleep=lambda s: None)
    def fn():
        calls.append(1)
        return "ok"

    assert fn() == "ok"
    assert len(calls) == 1


def test_retries_then_succeeds():
    calls = []

    @with_retry(max_attempts=3, sleep=lambda s: None)
    def fn():
        calls.append(1)
        if len(calls) < 3:
            raise RetryableError("transient")
        return "ok"

    assert fn() == "ok"
    assert len(calls) == 3


def test_gives_up_after_max_attempts():
    calls = []

    @with_retry(max_attempts=3, sleep=lambda s: None)
    def fn():
        calls.append(1)
        raise RetryableError("always")

    with pytest.raises(RetryableError):
        fn()
    assert len(calls) == 3


def test_non_retryable_propagates_immediately():
    calls = []

    @with_retry(max_attempts=3, retry_on=(RetryableError,), sleep=lambda s: None)
    def fn():
        calls.append(1)
        raise ValueError("permanent")

    with pytest.raises(ValueError):
        fn()
    assert len(calls) == 1


def test_backoff_delays_grow():
    delays = []

    @with_retry(max_attempts=3, base_delay=1.0, backoff=2.0, sleep=delays.append)
    def fn():
        raise RetryableError("x")

    with pytest.raises(RetryableError):
        fn()
    assert delays == [1.0, 2.0]
