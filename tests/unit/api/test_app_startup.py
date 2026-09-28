"""Unit tests for FastAPI application startup and core endpoints.

This module tests the FastAPI application initialization and basic endpoint functionality
including health checks, API documentation, middleware, and the BFF sidecar integration.
"""

import os
from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from docpipe.api.auth.dependencies import get_current_user
from docpipe.api.auth.models import User
from docpipe.api.main import _start_bff, _wait_for_bff, app, mount_ui_routes
from docpipe.api.middleware.security_headers import API_CSP, DOCS_CSP


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    """Create a test client for the FastAPI application.

    Bypasses authentication so endpoint behaviour can be tested in isolation.
    dependency_overrides are cleared on teardown to prevent leaking into other
    test modules in the same pytest session.
    """
    app.dependency_overrides[get_current_user] = lambda: User(
        username="testuser", email="test@example.com", full_name="Test User"
    )
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestApplicationStartup:
    """Test FastAPI application initialization."""

    def test_app_starts_without_errors(self, *, client: TestClient):
        """Test that the FastAPI application starts without errors."""
        assert client is not None
        assert app.title == "Docpipe Opensource API"
        assert app.version == "0.1.0"


class TestCoreEndpoints:
    """Test core API endpoints."""

    def test_root_endpoint_returns_200(self, *, client: TestClient):
        """Test that root endpoint / returns 200 OK."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Welcome to Docpipe Opensource API"

    def test_health_endpoint_returns_200(self, *, client: TestClient):
        """Test that /health endpoint returns 200 OK."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_api_docs_endpoint_returns_200(self, *, client: TestClient):
        """Test that /api/v1/docs endpoint returns 200 OK."""
        response = client.get("/api/v1/docs")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_openapi_json_endpoint_returns_200(self, *, client: TestClient):
        """Test that /api/v1/openapi.json endpoint returns 200 OK."""
        response = client.get("/api/v1/openapi.json")

        assert response.status_code == 200
        data = response.json()
        assert data["openapi"]
        assert data["info"]["title"] == "Docpipe Opensource API"

    def test_operators_metadata_endpoint_returns_200(self, *, client: TestClient):
        """Test that /api/v1/operators/metadata endpoint returns 200 OK."""
        response = client.get("/api/v1/operators/metadata")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)

        # Verify response contains operator metadata
        if data:
            first_operator = data[next(iter(data))]
            assert "label" in first_operator
            assert "category" in first_operator


class TestMiddleware:
    """Test middleware functionality."""

    def test_security_headers_present_in_api_responses(self, *, client: TestClient):
        """Test that security headers are present in API responses."""
        response = client.get("/health")

        assert response.status_code == 200
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["referrer-policy"] == "no-referrer"
        assert response.headers["content-security-policy"] == API_CSP

    def test_strict_csp_applied_to_api_paths(self, *, client: TestClient):
        """Non-docs paths must receive the strict CSP (no unsafe-inline/unsafe-eval)."""
        response = client.get("/health")

        csp = response.headers["content-security-policy"]
        assert "unsafe-inline" not in csp
        assert "unsafe-eval" not in csp

    def test_relaxed_csp_applied_to_swagger_docs(self, *, client: TestClient):
        """Swagger UI path must receive the relaxed CSP so the UI can load."""
        response = client.get("/api/v1/docs")

        assert response.status_code == 200
        assert response.headers["content-security-policy"] == DOCS_CSP

    def test_relaxed_csp_applied_to_redoc(self, *, client: TestClient):
        """ReDoc path must also receive the relaxed CSP."""
        response = client.get("/api/v1/redoc")

        assert response.status_code == 200
        assert response.headers["content-security-policy"] == DOCS_CSP

    def test_transaction_id_header_present_in_responses(self, *, client: TestClient):
        """Test that transaction ID header is present in responses."""
        response = client.get("/health")

        assert response.status_code == 200
        assert "x-transaction-id" in response.headers
        assert len(response.headers["x-transaction-id"]) > 0


class FakeBffResponse:
    """Minimal stand-in for an httpx.Response returned by the BFF."""

    def __init__(self, *, status_code: int = 200):
        self.content = b'{"ok": true}'
        self.status_code = status_code
        self.headers = {"content-type": "application/json"}


class FakeAsyncClient:
    """Minimal stand-in for httpx.AsyncClient stored on app.state.

    Not a context manager — the real client is created once in lifespan and
    reused across requests. Tests that exercise proxy_to_bff patch app.state
    directly rather than patching AsyncClient construction.
    """

    async def request(self, **kwargs):
        """Return a 200 FakeBffResponse for any request."""
        del kwargs
        return FakeBffResponse()

    async def aclose(self):
        """No-op close — no real connection pool to release."""


class TestWaitForBff:
    """Tests for _wait_for_bff()."""

    def test_returns_true_when_bff_responds_with_2xx(self):
        """Returns True when /health responds with a 2xx status code."""
        mock_response = MagicMock(status_code=200)
        with (
            patch("docpipe.api.main.httpx.get", return_value=mock_response),
            patch("docpipe.api.main.time.sleep"),
        ):
            result = _wait_for_bff(bff_url="http://localhost:3001")
        assert result is True

    def test_returns_false_when_bff_responds_with_5xx(self):
        """Returns False when every /health response is a 5xx — BFF not ready."""
        mock_response = MagicMock(status_code=503)
        with (
            patch("docpipe.api.main.httpx.get", return_value=mock_response),
            patch("docpipe.api.main.time.sleep"),
        ):
            result = _wait_for_bff(bff_url="http://localhost:3001", retries=3, delay=0.0)
        assert result is False

    def test_returns_false_when_bff_responds_with_4xx(self):
        """Returns False when every /health response is 4xx — only 2xx is healthy."""
        mock_response = MagicMock(status_code=404)
        with (
            patch("docpipe.api.main.httpx.get", return_value=mock_response),
            patch("docpipe.api.main.time.sleep"),
        ):
            result = _wait_for_bff(bff_url="http://localhost:3001", retries=3, delay=0.0)
        assert result is False

    def test_returns_false_after_exhausting_retries(self):
        """Returns False when every attempt raises TransportError."""
        import httpx as _httpx

        with (
            patch("docpipe.api.main.httpx.get", side_effect=_httpx.TransportError("refused")),
            patch("docpipe.api.main.time.sleep"),
        ):
            result = _wait_for_bff(bff_url="http://localhost:3001", retries=3, delay=0.0)
        assert result is False

    def test_returns_true_on_second_attempt(self):
        """Returns True when the second poll succeeds after one TransportError."""
        import httpx as _httpx

        mock_ok = MagicMock(status_code=200)
        attempts: list = [_httpx.TransportError("not ready yet"), mock_ok]

        def _side_effect(*_args, **_kwargs):
            """Pop the next attempt; raise if it is an exception, return otherwise."""
            val = attempts.pop(0)
            if isinstance(val, Exception):
                raise val
            return val

        with (
            patch("docpipe.api.main.httpx.get", side_effect=_side_effect),
            patch("docpipe.api.main.time.sleep"),
        ):
            result = _wait_for_bff(bff_url="http://localhost:3001", retries=5, delay=0.0)
        assert result is True


class TestStartBff:
    """Tests for _start_bff()."""

    def test_start_bff_returns_none_when_bff_url_already_set(self, monkeypatch):
        """No-op when BFF_URL is already in the environment (external BFF assumed).

        Returns (None, "") — the empty URL signals to lifespan() that it should
        fall back to the pre-configured BFF_URL environment variable.
        """
        monkeypatch.setenv("BFF_URL", "http://bff:3001")
        process, url = _start_bff()
        assert process is None
        assert url == ""

    def test_start_bff_returns_none_when_bundle_missing(self, monkeypatch):
        """No-op when the bundled server.cjs is not present in the wheel."""
        monkeypatch.delenv("BFF_URL", raising=False)
        with patch.object(Path, "exists", return_value=False):
            process, url = _start_bff()

        assert process is None
        assert url == ""

    def test_start_bff_returns_none_when_node_missing(self, monkeypatch):
        """No-op when `node` is not available in PATH."""
        monkeypatch.delenv("BFF_URL", raising=False)
        with (
            patch.object(Path, "exists", return_value=True),
            patch("docpipe.api.main.shutil.which", return_value=None),
        ):
            process, url = _start_bff()

        assert process is None
        assert url == ""

    def test_start_bff_starts_process_and_returns_bff_url(self, monkeypatch):
        """Successful spawn returns (process, url) without mutating os.environ."""
        monkeypatch.delenv("BFF_URL", raising=False)
        monkeypatch.setenv("BFF_PORT", "3001")
        monkeypatch.setenv("FASTAPI_PORT", "8080")

        mock_process = MagicMock(pid=1234)
        with (
            patch.object(Path, "exists", return_value=True),
            patch("docpipe.api.main.shutil.which", return_value="/usr/bin/node"),
            patch("docpipe.api.main.subprocess.Popen", return_value=mock_process) as mock_popen,
            patch("docpipe.api.main._wait_for_bff", return_value=True),
        ):
            process, url = _start_bff()

        assert process is mock_process
        mock_popen.assert_called_once()
        assert url == "http://localhost:3001"
        # Must NOT mutate the process environment.
        assert "BFF_URL" not in os.environ

    def test_start_bff_returns_url_even_when_health_poll_fails(self, monkeypatch):
        """Process and URL are returned even when the health poll times out."""
        monkeypatch.delenv("BFF_URL", raising=False)
        monkeypatch.setenv("BFF_PORT", "3001")
        monkeypatch.setenv("FASTAPI_PORT", "8080")

        mock_process = MagicMock(pid=5678)
        with (
            patch.object(Path, "exists", return_value=True),
            patch("docpipe.api.main.shutil.which", return_value="/usr/bin/node"),
            patch("docpipe.api.main.subprocess.Popen", return_value=mock_process),
            patch("docpipe.api.main._wait_for_bff", return_value=False),
        ):
            process, url = _start_bff()

        assert process is mock_process
        assert url == "http://localhost:3001"
        assert "BFF_URL" not in os.environ


class TestLifespanBffWiring:
    """Tests for BFF start/stop wiring inside the FastAPI lifespan."""

    def test_lifespan_terminates_bff_process_on_shutdown(self):
        """When _start_bff() returns a process, terminate() is called on shutdown.

        wait() is intentionally not called — it is a blocking syscall that would
        stall the uvicorn event loop. Only terminate() is asserted here.
        """
        mock_process = MagicMock()
        with (
            patch("docpipe.api.main._start_bff", return_value=(mock_process, "http://localhost:3001")),
            TestClient(app),
        ):
            pass

        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_not_called()

    def test_lifespan_skips_shutdown_when_bff_not_started(self):
        """When _start_bff() returns (None, ""), shutdown must not attempt to terminate anything."""
        with patch("docpipe.api.main._start_bff", return_value=(None, "")), TestClient(app):
            pass  # no exception expected


class TestProxyToBff:
    """Tests for the /api/{path} catch-all proxy route."""

    def test_proxy_to_bff_returns_404_when_bff_url_unset(self, monkeypatch):
        """Requests to unmatched /api/* paths 404 when the BFF is not running."""
        monkeypatch.delenv("BFF_URL", raising=False)
        client = TestClient(app)

        response = client.get("/api/some-unmatched-path")

        assert response.status_code == 404

    def test_proxy_to_bff_forwards_request_when_client_on_state(self):
        """Requests are forwarded when a BFF client is present on app.state."""
        app.state.bff_client = FakeAsyncClient()
        try:
            client = TestClient(app)
            response = client.get("/api/some-unmatched-path")
            assert response.status_code == 200
            assert response.json() == {"ok": True}
        finally:
            app.state.bff_client = None

    def test_proxy_strips_hop_by_hop_headers_from_response(self):
        """transfer-encoding and other hop-by-hop headers must not reach the client."""
        from docpipe.api.main import _HOP_BY_HOP_HEADERS

        class ChunkedFakeAsyncClient:
            """Fake client that returns hop-by-hop headers in its response."""

            async def request(self, **kwargs):
                """Return a response containing hop-by-hop headers."""
                del kwargs
                r = FakeBffResponse()
                r.headers = {
                    "content-type": "application/json",
                    "transfer-encoding": "chunked",
                    "connection": "keep-alive",
                }
                return r

            async def aclose(self):
                """No-op close."""

        app.state.bff_client = ChunkedFakeAsyncClient()
        try:
            client = TestClient(app)
            response = client.get("/api/some-unmatched-path")
            assert response.status_code == 200
            # content-length is stripped from the forwarded request (to prevent
            # duplicate headers when httpx recomputes it), but FastAPI always
            # adds it back on the final response to the client — that is correct.
            # Assert only on the other hop-by-hop headers that must not reach the client.
            transport_hop_headers = _HOP_BY_HOP_HEADERS - {"content-length"}
            for hop_header in transport_hop_headers:
                assert hop_header not in response.headers
        finally:
            app.state.bff_client = None


class TestServeUiRoutes:
    """Tests for the /ui static file serving routes.

    mount_ui_routes() is exercised directly against a temporary directory
    with fake built assets, so these tests do not depend on whether the
    real frontend has been built in the running environment (e.g. CI).
    """

    @pytest.fixture
    def ui_app(self, tmp_path: Path) -> FastAPI:
        """A fresh FastAPI app with UI routes mounted against fake built assets."""
        fake_static_dir = tmp_path / "static"
        fake_assets_dir = fake_static_dir / "assets"
        fake_assets_dir.mkdir(parents=True)
        (fake_static_dir / "index.html").write_text("<html><body>index</body></html>")
        (fake_assets_dir / "app.js").write_text("console.log('app');")

        test_app = FastAPI()
        mount_ui_routes(test_app, fake_static_dir)
        return test_app

    def test_mount_ui_routes_is_noop_when_static_dir_missing(self, tmp_path: Path):
        """No routes are registered when the static directory does not exist."""
        missing_dir = tmp_path / "does-not-exist"
        test_app = FastAPI()

        mount_ui_routes(test_app, missing_dir)

        client = TestClient(test_app)
        response = client.get("/ui")
        assert response.status_code == 404

    def test_serve_ui_root_returns_index_html(self, *, ui_app: FastAPI):
        """GET /ui returns the SPA's index.html."""
        client = TestClient(ui_app)

        response = client.get("/ui")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_serve_ui_existing_asset_file_returns_file(self, *, ui_app: FastAPI):
        """GET /ui/assets/<file> serves the actual built asset when present."""
        client = TestClient(ui_app)

        response = client.get("/ui/assets/app.js")

        assert response.status_code == 200

    def test_serve_ui_missing_file_with_extension_returns_404(self, *, ui_app: FastAPI):
        """A path with a file extension that does not exist must return 404.

        Broken asset references (e.g. a renamed Vite chunk) should surface as an
        error, not silently return index.html which would make them very hard to debug.
        """
        client = TestClient(ui_app, raise_server_exceptions=False)

        response = client.get("/ui/some-page/missing-file.json")

        assert response.status_code == 404

    def test_serve_ui_spa_route_returns_index_html(self, *, ui_app: FastAPI):
        """Client-side routes with no file extension fall back to index.html."""
        client = TestClient(ui_app)

        response = client.get("/ui/dashboard")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_serve_ui_path_traversal_blocked(self, *, ui_app: FastAPI, tmp_path: Path):
        """Path traversal attempts never serve files outside the static root.

        HTTPX normalises URLs before sending (e.g. assets/../../../etc/passwd
        becomes /etc/passwd), so the traversal attempt reaches FastAPI as a
        simple path that resolves *inside* the static root (as static/etc/passwd)
        and correctly returns 404 — the file doesn't exist, but no filesystem
        content outside the root is ever served.

        For paths where the ".." components survive routing and would resolve
        outside the root, the guard returns 400. This test exercises both cases
        to verify the server never leaks content outside _safe_root.
        """
        client = TestClient(ui_app, raise_server_exceptions=False)

        # Case 1: HTTPX normalises these fully — FastAPI sees a path that stays
        # inside the root; 404 is the correct and safe response.
        normalised_paths = [
            "assets/../../../etc/passwd",
            "sub/dir/../../../../../../etc/passwd",
        ]
        for path in normalised_paths:
            response = client.get(f"/ui/{path}")
            # Must not be 200 — no filesystem content outside root may be served.
            assert response.status_code != 200, f"Unexpected 200 for traversal path: {path}"

        # Case 2: Plant a real file outside the static root and verify serve_ui
        # does not serve it even when full_path contains ".." components that
        # would resolve outside. We call the route handler directly via the
        # test app to bypass HTTPX normalisation.
        secret_file = tmp_path / "secret.txt"
        secret_file.write_text("TOP SECRET")

        # Construct a path that stays syntactically inside /ui/ but resolves
        # outside the static root: static/../secret.txt
        # Re-use the existing client — HTTPX normalisation happens per-request,
        # not per-client; encoding bypasses it regardless of which client is used.
        # Encode the ".." as %2e%2e to prevent HTTPX from normalising it.
        encoded_response = client.get("/ui/assets/%2e%2e%2f%2e%2e%2fsecret.txt")
        # FastAPI will URL-decode this and the guard must block or 404 it — never 200.
        assert encoded_response.status_code != 200, "Encoded path traversal must not return 200"
