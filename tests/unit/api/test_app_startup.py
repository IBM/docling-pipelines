"""Unit tests for FastAPI application startup and core endpoints.

This module tests the FastAPI application initialization and basic endpoint functionality
including health checks, API documentation, and middleware.
"""

import pytest
from fastapi.testclient import TestClient

from docpipe.api.auth.dependencies import get_current_user
from docpipe.api.auth.models import User
from docpipe.api.main import app, run
from docpipe.api.middleware.security_headers import API_CSP, DOCS_CSP


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Create a test client for the FastAPI application.

    Bypasses authentication so endpoint behaviour can be tested in isolation.
    """
    app.dependency_overrides[get_current_user] = lambda: User(
        username="testuser", email="test@example.com", full_name="Test User"
    )
    return TestClient(app)


class TestEntryPoint:
    """Test the docling-pipelines-api console entry point."""

    def test_run_is_callable(self):
        """Entry point must be a zero-argument callable, not an object instance."""
        assert callable(run)

    def test_run_is_not_the_app_object(self):
        """Entry point must not point directly at the FastAPI app instance."""
        assert run is not app


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
