"""Unit tests for SecurityHeadersMiddleware."""

from unittest.mock import MagicMock

import pytest
from starlette.responses import Response

from docpipe.api.middleware.security_headers import (
    API_CSP,
    DOCS_CSP,
    SecurityHeadersMiddleware,
)


@pytest.fixture
def mock_call_next():
    """Create a mock call_next that returns a 200 response."""

    async def call_next(request):
        return Response(content="ok", status_code=200)

    return call_next


def _make_request(*, path: str) -> MagicMock:
    """Create a mock request with the given URL path."""
    request = MagicMock()
    request.url.path = path
    request.method = "GET"
    return request


class TestSecurityHeadersMiddlewareCommonHeaders:
    """Tests for security headers applied to all responses."""

    @pytest.mark.anyio
    async def test_x_content_type_options_header(self, mock_call_next):
        """X-Content-Type-Options should be set to nosniff."""
        request = _make_request(path="/api/v1/flows")
        middleware = SecurityHeadersMiddleware(app=MagicMock())

        response = await middleware.dispatch(request, mock_call_next)

        assert response.headers["X-Content-Type-Options"] == "nosniff"

    @pytest.mark.anyio
    async def test_x_frame_options_header(self, mock_call_next):
        """X-Frame-Options should be set to DENY."""
        request = _make_request(path="/api/v1/flows")
        middleware = SecurityHeadersMiddleware(app=MagicMock())

        response = await middleware.dispatch(request, mock_call_next)

        assert response.headers["X-Frame-Options"] == "DENY"

    @pytest.mark.anyio
    async def test_referrer_policy_header(self, mock_call_next):
        """Referrer-Policy should be set to no-referrer."""
        request = _make_request(path="/api/v1/flows")
        middleware = SecurityHeadersMiddleware(app=MagicMock())

        response = await middleware.dispatch(request, mock_call_next)

        assert response.headers["Referrer-Policy"] == "no-referrer"

    @pytest.mark.anyio
    async def test_content_security_policy_header_present(self, mock_call_next):
        """Content-Security-Policy header should always be present."""
        request = _make_request(path="/api/v1/operators")
        middleware = SecurityHeadersMiddleware(app=MagicMock())

        response = await middleware.dispatch(request, mock_call_next)

        assert "Content-Security-Policy" in response.headers


class TestSecurityHeadersMiddlewareCSPPolicy:
    """Tests for differentiated CSP policies (strict API vs relaxed docs)."""

    @pytest.mark.anyio
    async def test_strict_csp_for_api_endpoint(self, mock_call_next):
        """API endpoints should receive the strict CSP without unsafe directives."""
        request = _make_request(path="/api/v1/flows")
        middleware = SecurityHeadersMiddleware(app=MagicMock())

        response = await middleware.dispatch(request, mock_call_next)

        csp = response.headers["Content-Security-Policy"]
        assert csp == API_CSP
        assert "unsafe-inline" not in csp
        assert "unsafe-eval" not in csp

    @pytest.mark.anyio
    async def test_relaxed_csp_for_docs_path(self, mock_call_next):
        """The /api/v1/docs path should receive relaxed CSP for Swagger UI."""
        request = _make_request(path="/api/v1/docs")
        middleware = SecurityHeadersMiddleware(app=MagicMock())

        response = await middleware.dispatch(request, mock_call_next)

        csp = response.headers["Content-Security-Policy"]
        assert csp == DOCS_CSP
        assert "unsafe-inline" in csp
        assert "unsafe-eval" in csp

    @pytest.mark.anyio
    async def test_relaxed_csp_for_redoc_path(self, mock_call_next):
        """The /api/v1/redoc path should receive relaxed CSP for ReDoc."""
        request = _make_request(path="/api/v1/redoc")
        middleware = SecurityHeadersMiddleware(app=MagicMock())

        response = await middleware.dispatch(request, mock_call_next)

        csp = response.headers["Content-Security-Policy"]
        assert csp == DOCS_CSP

    @pytest.mark.anyio
    async def test_strict_csp_for_non_docs_path(self, mock_call_next):
        """Non-docs paths should receive the strict API CSP."""
        request = _make_request(path="/api/v1/job-runs")
        middleware = SecurityHeadersMiddleware(app=MagicMock())

        response = await middleware.dispatch(request, mock_call_next)

        csp = response.headers["Content-Security-Policy"]
        assert csp == API_CSP

    @pytest.mark.anyio
    async def test_strict_csp_for_root_path(self, mock_call_next):
        """The root path should receive the strict API CSP."""
        request = _make_request(path="/")
        middleware = SecurityHeadersMiddleware(app=MagicMock())

        response = await middleware.dispatch(request, mock_call_next)

        csp = response.headers["Content-Security-Policy"]
        assert csp == API_CSP

    @pytest.mark.anyio
    async def test_docs_subpath_gets_relaxed_csp(self, mock_call_next):
        """Subpaths under /api/v1/docs should also get relaxed CSP."""
        request = _make_request(path="/api/v1/docs/oauth2-redirect")
        middleware = SecurityHeadersMiddleware(app=MagicMock())

        response = await middleware.dispatch(request, mock_call_next)

        csp = response.headers["Content-Security-Policy"]
        assert csp == DOCS_CSP


class TestSecurityHeadersMiddlewareResponsePreservation:
    """Tests that the middleware does not alter the original response."""

    @pytest.mark.anyio
    async def test_response_status_code_preserved(self, mock_call_next):
        """Middleware must not alter the response status code."""
        request = _make_request(path="/api/v1/flows")
        middleware = SecurityHeadersMiddleware(app=MagicMock())

        response = await middleware.dispatch(request, mock_call_next)

        assert response.status_code == 200

    @pytest.mark.anyio
    async def test_response_body_preserved(self, mock_call_next):
        """Middleware must not alter the response body."""
        request = _make_request(path="/api/v1/flows")
        middleware = SecurityHeadersMiddleware(app=MagicMock())

        response = await middleware.dispatch(request, mock_call_next)

        assert response.body == b"ok"

    @pytest.mark.anyio
    async def test_error_response_gets_security_headers(self):
        """Security headers should be added even to error responses."""

        async def error_call_next(request):
            return Response(content="error", status_code=500)

        request = _make_request(path="/api/v1/flows")
        middleware = SecurityHeadersMiddleware(app=MagicMock())

        response = await middleware.dispatch(request, error_call_next)

        assert response.status_code == 500
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["Referrer-Policy"] == "no-referrer"
        assert "Content-Security-Policy" in response.headers
