"""Unit tests for the in-process login rate limiter."""

import time

import pytest

from docpipe.api.middleware.rate_limit import (
    RATE_LIMIT_MAX_ATTEMPTS,
    RATE_LIMIT_WINDOW_SECONDS,
    _login_attempts,
    check_login_rate_limit,
)


@pytest.fixture(autouse=True)
def clear_state():
    """Reset the shared state before each test."""
    _login_attempts.clear()
    yield
    _login_attempts.clear()


class TestCheckLoginRateLimit:
    def test_first_attempt_is_allowed(self):
        assert check_login_rate_limit(client_ip="1.2.3.4") is True

    def test_attempts_up_to_max_are_allowed(self):
        for _ in range(RATE_LIMIT_MAX_ATTEMPTS):
            assert check_login_rate_limit(client_ip="1.2.3.4") is True

    def test_attempt_beyond_max_is_rejected(self):
        for _ in range(RATE_LIMIT_MAX_ATTEMPTS):
            check_login_rate_limit(client_ip="1.2.3.4")
        assert check_login_rate_limit(client_ip="1.2.3.4") is False

    def test_different_ips_are_tracked_independently(self):
        for _ in range(RATE_LIMIT_MAX_ATTEMPTS):
            check_login_rate_limit(client_ip="10.0.0.1")
        # Exhausted for 10.0.0.1 — 10.0.0.2 is unaffected
        assert check_login_rate_limit(client_ip="10.0.0.2") is True

    def test_expired_timestamps_are_evicted(self, monkeypatch):
        """Timestamps older than the window are dropped so the slot reopens."""
        ip = "5.5.5.5"
        # Fill the window with timestamps that are already expired
        past = time.monotonic() - RATE_LIMIT_WINDOW_SECONDS - 1
        _login_attempts[ip] = [past] * RATE_LIMIT_MAX_ATTEMPTS

        # All old entries should be purged — next attempt must be allowed
        assert check_login_rate_limit(client_ip=ip) is True

    def test_partially_expired_window(self):
        """Only fresh timestamps within the window count toward the limit."""
        ip = "6.6.6.6"
        past = time.monotonic() - RATE_LIMIT_WINDOW_SECONDS - 1
        # Two stale + (MAX-1) fresh = total fresh < MAX → should be allowed
        fresh_count = RATE_LIMIT_MAX_ATTEMPTS - 1
        _login_attempts[ip] = [past, past] + [time.monotonic()] * fresh_count

        # After eviction: fresh_count entries remain, one more is allowed
        assert check_login_rate_limit(client_ip=ip) is True

    def test_constants_are_sensible(self):
        assert RATE_LIMIT_MAX_ATTEMPTS > 0
        assert RATE_LIMIT_WINDOW_SECONDS > 0
