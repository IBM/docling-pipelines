"""Unit tests for OAuth2 route helpers and security fixes."""

import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from docpipe.api.auth.oauth2_routes import (
    _MAX_STATE_ENTRIES,
    _STATE_TTL_SECONDS,
    _consume_state,
    _is_same_origin,
    _state_store,
    _store_state,
)


@pytest.fixture(autouse=True)
def clear_state_store():
    """Ensure state store is empty before each test."""
    _state_store.clear()
    yield
    _state_store.clear()


# ---------------------------------------------------------------------------
# _is_same_origin
# ---------------------------------------------------------------------------


class TestIsSameOrigin:
    @pytest.mark.parametrize(
        "url",
        [
            "",
            "/",
            "/dashboard",
            "/callback?next=/home",
            "/deep/path?foo=bar#anchor",
        ],
    )
    def test_relative_urls_are_safe(self, url):
        assert _is_same_origin(url) is True

    @pytest.mark.parametrize(
        "url",
        [
            "https://evil.example.com",
            "http://evil.example.com/path",
            "javascript:alert(1)",
            "//evil.example.com/path",  # protocol-relative
            "//evil.example.com",
        ],
    )
    def test_external_and_protocol_relative_urls_are_rejected(self, url):
        assert _is_same_origin(url) is False

    def test_empty_string_is_safe(self):
        assert _is_same_origin("") is True


# ---------------------------------------------------------------------------
# _store_state / _consume_state
# ---------------------------------------------------------------------------


class TestStateStore:
    def test_stored_state_is_consumed_once(self):
        _store_state(state="abc123", redirect_url="/home")
        result = _consume_state(state="abc123")
        assert result == "/home"

    def test_consumed_state_cannot_be_reused(self):
        _store_state(state="abc123", redirect_url="/home")
        _consume_state(state="abc123")
        assert _consume_state(state="abc123") is None

    def test_unknown_state_returns_none(self):
        assert _consume_state(state="no-such-state") is None

    def test_empty_redirect_url_is_stored_and_returned(self):
        _store_state(state="s1", redirect_url="")
        assert _consume_state(state="s1") == ""

    def test_expired_state_is_rejected(self):
        state = "expired-state"
        expired_time = time.monotonic() - _STATE_TTL_SECONDS - 1
        _state_store[state] = ("/home", expired_time)
        assert _consume_state(state=state) is None

    def test_expired_states_are_purged_on_store(self):
        # Plant an expired entry
        _state_store["old"] = ("/old", time.monotonic() - _STATE_TTL_SECONDS - 1)
        # Storing a new state triggers purge
        _store_state(state="new", redirect_url="/new")
        assert "old" not in _state_store
        assert "new" in _state_store

    def test_multiple_states_tracked_independently(self):
        _store_state(state="s1", redirect_url="/a")
        _store_state(state="s2", redirect_url="/b")
        assert _consume_state(state="s1") == "/a"
        assert _consume_state(state="s2") == "/b"

    def test_store_full_raises_runtime_error(self):
        """_store_state raises RuntimeError when the cap is reached after purging."""
        # Fill the store to capacity with fresh (non-expired) entries
        future = time.monotonic() + _STATE_TTL_SECONDS + 100
        for i in range(_MAX_STATE_ENTRIES):
            _state_store[f"fill-{i}"] = ("/x", future)
        with pytest.raises(RuntimeError, match="full"):
            _store_state(state="overflow", redirect_url="/y")


# ---------------------------------------------------------------------------
# /authorize endpoint — redirect_after validation
# ---------------------------------------------------------------------------


class TestAuthorizeEndpointRedirectValidation:
    """The /authorize endpoint must reject absolute redirect_after URLs."""

    @pytest.fixture
    def app_with_routes(self):
        from docpipe.api.auth.oauth2_routes import router

        app = FastAPI()
        app.include_router(router)
        return app

    def test_absolute_redirect_after_returns_400(self, app_with_routes):
        client = TestClient(app_with_routes, raise_server_exceptions=False)
        response = client.get(
            "/auth/oauth2/authorize",
            params={"redirect_after": "https://evil.example.com"},
        )
        assert response.status_code == 400
        assert "relative" in response.json().get("detail", "").lower()

    def test_protocol_relative_redirect_after_returns_400(self, app_with_routes):
        client = TestClient(app_with_routes, raise_server_exceptions=False)
        response = client.get(
            "/auth/oauth2/authorize",
            params={"redirect_after": "//evil.example.com/path"},
        )
        assert response.status_code == 400

    def test_relative_redirect_after_is_not_blocked(self, app_with_routes, monkeypatch):
        """A relative redirect_after passes the validation guard (OAuth2 not configured
        in tests so we expect 503, not 400)."""
        client = TestClient(app_with_routes, raise_server_exceptions=False)
        response = client.get(
            "/auth/oauth2/authorize",
            params={"redirect_after": "/dashboard"},
        )
        # 400 means the redirect validation fired — that must NOT happen for /dashboard.
        assert response.status_code != 400

    def test_no_redirect_after_is_not_blocked(self, app_with_routes):
        client = TestClient(app_with_routes, raise_server_exceptions=False)
        response = client.get("/auth/oauth2/authorize")
        assert response.status_code != 400
