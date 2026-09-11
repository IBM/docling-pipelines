"""Tests for security headers middleware."""

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.responses import Response

from docpipe.api.middleware.security_headers import (
    API_CSP,
    DOCS_CSP,
    SecurityHeadersMiddleware,
)


@pytest.fixture
def app_with_security_headers():
    """Create test FastAPI app with security headers middleware."""
    test_app = FastAPI()
    test_app.add_middleware(SecurityHeadersMiddleware)

    @test_app.get("/api/v1/test")
    async def api_endpoint():
        return {"message": "api"}

    @test_app.get("/api/v1/docs")
    async def docs_endpoint():
        return {"message": "docs"}

    @test_app.get("/api/v1/redoc")
    async def redoc_endpoint():
        return {"message": "redoc"}

    @test_app.get("/api/v1/docs/swagger.json")
    async def docs_json_endpoint():
        return {"message": "swagger json"}

    return test_app


@pytest.fixture
def client(app_with_security_headers):
    """Create test client."""
    return TestClient(app_with_security_headers)


def test_adds_x_content_type_options_header(client):
    """Test that X-Content-Type-Options header is added to all responses."""
    response = client.get("/api/v1/test")

    assert "X-Content-Type-Options" in response.headers
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_adds_x_frame_options_header(client):
    """Test that X-Frame-Options header is added to all responses."""
    response = client.get("/api/v1/test")

    assert "X-Frame-Options" in response.headers
    assert response.headers["X-Frame-Options"] == "DENY"


def test_adds_referrer_policy_header(client):
    """Test that Referrer-Policy header is added to all responses."""
    response = client.get("/api/v1/test")

    assert "Referrer-Policy" in response.headers
    assert response.headers["Referrer-Policy"] == "no-referrer"


def test_adds_content_security_policy_header(client):
    """Test that Content-Security-Policy header is added to all responses."""
    response = client.get("/api/v1/test")

    assert "Content-Security-Policy" in response.headers


def test_applies_strict_csp_to_api_endpoints(client):
    """Test that strict CSP is applied to API endpoints."""
    response = client.get("/api/v1/test")

    csp = response.headers["Content-Security-Policy"]
    assert csp == API_CSP
    assert "unsafe-inline" not in csp
    assert "unsafe-eval" not in csp


def test_applies_relaxed_csp_to_docs_endpoint(client):
    """Test that relaxed CSP is applied to /api/v1/docs endpoint."""
    response = client.get("/api/v1/docs")

    csp = response.headers["Content-Security-Policy"]
    assert csp == DOCS_CSP
    assert "unsafe-inline" in csp
    assert "unsafe-eval" in csp


def test_applies_relaxed_csp_to_redoc_endpoint(client):
    """Test that relaxed CSP is applied to /api/v1/redoc endpoint."""
    response = client.get("/api/v1/redoc")

    csp = response.headers["Content-Security-Policy"]
    assert csp == DOCS_CSP
    assert "unsafe-inline" in csp
    assert "unsafe-eval" in csp


def test_applies_relaxed_csp_to_docs_subpaths(client):
    """Test that relaxed CSP is applied to docs subpaths."""
    response = client.get("/api/v1/docs/swagger.json")

    csp = response.headers["Content-Security-Policy"]
    assert csp == DOCS_CSP


def test_all_security_headers_present_on_api_endpoint(client):
    """Test that all security headers are present on API endpoints."""
    response = client.get("/api/v1/test")

    assert "X-Content-Type-Options" in response.headers
    assert "X-Frame-Options" in response.headers
    assert "Referrer-Policy" in response.headers
    assert "Content-Security-Policy" in response.headers


def test_all_security_headers_present_on_docs_endpoint(client):
    """Test that all security headers are present on docs endpoints."""
    response = client.get("/api/v1/docs")

    assert "X-Content-Type-Options" in response.headers
    assert "X-Frame-Options" in response.headers
    assert "Referrer-Policy" in response.headers
    assert "Content-Security-Policy" in response.headers


def test_api_csp_constant_format():
    """Test that API_CSP constant has expected directives."""
    assert "default-src 'self'" in API_CSP
    assert "script-src 'self' https://cdn.jsdelivr.net" in API_CSP
    assert "style-src 'self' https://cdn.jsdelivr.net" in API_CSP
    assert "img-src 'self' data: https:" in API_CSP
    assert "font-src 'self' data:" in API_CSP
    assert "connect-src 'self'" in API_CSP
    assert "frame-ancestors 'none'" in API_CSP
    assert "unsafe-inline" not in API_CSP
    assert "unsafe-eval" not in API_CSP


def test_docs_csp_constant_format():
    """Test that DOCS_CSP constant has expected directives."""
    assert "default-src 'self'" in DOCS_CSP
    assert "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net" in DOCS_CSP
    assert "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net" in DOCS_CSP
    assert "img-src 'self' data: https:" in DOCS_CSP
    assert "font-src 'self' data:" in DOCS_CSP
    assert "connect-src 'self'" in DOCS_CSP
    assert "frame-ancestors 'none'" in DOCS_CSP
    assert "unsafe-inline" in DOCS_CSP
    assert "unsafe-eval" in DOCS_CSP


@pytest.mark.anyio
async def test_middleware_dispatch_returns_response():
    """Test that middleware properly returns response from next handler."""
    middleware = SecurityHeadersMiddleware(app=MagicMock())

    mock_request = MagicMock(spec=Request)
    mock_request.url.path = "/api/v1/test"

    expected_response = Response(content="test", status_code=200)

    async def mock_call_next(request):
        return expected_response

    result = await middleware.dispatch(mock_request, mock_call_next)

    assert result == expected_response
    assert "X-Content-Type-Options" in result.headers
    assert "X-Frame-Options" in result.headers
    assert "Referrer-Policy" in result.headers
    assert "Content-Security-Policy" in result.headers


@pytest.mark.anyio
async def test_middleware_adds_headers_to_error_responses():
    """Test that middleware adds security headers even to error responses."""
    middleware = SecurityHeadersMiddleware(app=MagicMock())

    mock_request = MagicMock(spec=Request)
    mock_request.url.path = "/api/v1/test"

    error_response = Response(content="error", status_code=500)

    async def mock_call_next(request):
        return error_response

    result = await middleware.dispatch(mock_request, mock_call_next)

    assert result.status_code == 500
    assert "X-Content-Type-Options" in result.headers
    assert "X-Frame-Options" in result.headers
    assert "Referrer-Policy" in result.headers
    assert "Content-Security-Policy" in result.headers


@pytest.mark.anyio
async def test_middleware_applies_correct_csp_based_on_path():
    """Test that middleware applies correct CSP based on request path."""
    middleware = SecurityHeadersMiddleware(app=MagicMock())

    # Test API endpoint gets strict CSP
    api_request = MagicMock(spec=Request)
    api_request.url.path = "/api/v1/flows"

    api_response = Response(content="api", status_code=200)

    async def mock_call_next_api(request):
        return api_response

    api_result = await middleware.dispatch(api_request, mock_call_next_api)
    assert api_result.headers["Content-Security-Policy"] == API_CSP

    # Test docs endpoint gets relaxed CSP
    docs_request = MagicMock(spec=Request)
    docs_request.url.path = "/api/v1/docs"

    docs_response = Response(content="docs", status_code=200)

    async def mock_call_next_docs(request):
        return docs_response

    docs_result = await middleware.dispatch(docs_request, mock_call_next_docs)
    assert docs_result.headers["Content-Security-Policy"] == DOCS_CSP


def test_csp_includes_cdn_jsdelivr_for_swagger_ui(client):
    """Test that CSP allows cdn.jsdelivr.net for Swagger UI resources."""
    response = client.get("/api/v1/docs")

    csp = response.headers["Content-Security-Policy"]
    assert "https://cdn.jsdelivr.net" in csp


def test_csp_allows_data_uris_for_images(client):
    """Test that CSP allows data: URIs for images."""
    response = client.get("/api/v1/test")

    csp = response.headers["Content-Security-Policy"]
    assert "img-src 'self' data: https:" in csp


def test_csp_allows_data_uris_for_fonts(client):
    """Test that CSP allows data: URIs for fonts."""
    response = client.get("/api/v1/test")

    csp = response.headers["Content-Security-Policy"]
    assert "font-src 'self' data:" in csp


def test_frame_ancestors_none_prevents_clickjacking(client):
    """Test that frame-ancestors 'none' is set to prevent clickjacking."""
    response = client.get("/api/v1/test")

    csp = response.headers["Content-Security-Policy"]
    assert "frame-ancestors 'none'" in csp


def test_x_frame_options_deny_prevents_framing(client):
    """Test that X-Frame-Options DENY prevents framing."""
    response = client.get("/api/v1/test")

    assert response.headers["X-Frame-Options"] == "DENY"


def test_referrer_policy_no_referrer_prevents_leakage(client):
    """Test that Referrer-Policy no-referrer prevents information leakage."""
    response = client.get("/api/v1/test")

    assert response.headers["Referrer-Policy"] == "no-referrer"


def test_x_content_type_options_nosniff_prevents_mime_sniffing(client):
    """Test that X-Content-Type-Options nosniff prevents MIME sniffing."""
    response = client.get("/api/v1/test")

    assert response.headers["X-Content-Type-Options"] == "nosniff"


@pytest.mark.anyio
async def test_middleware_handles_exceptions_from_next_handler():
    """Test that middleware allows exceptions from next handler to propagate."""
    middleware = SecurityHeadersMiddleware(app=MagicMock())

    mock_request = MagicMock(spec=Request)
    mock_request.url.path = "/api/v1/test"

    async def mock_call_next(request):
        raise ValueError("Test error")

    with pytest.raises(ValueError, match="Test error"):
        await middleware.dispatch(mock_request, mock_call_next)
