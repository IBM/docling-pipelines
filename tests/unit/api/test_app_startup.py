"""Unit tests for FastAPI application startup and core endpoints.

This module tests the FastAPI application initialization and basic endpoint functionality
including health checks, API documentation, and middleware.
"""

import pytest
from fastapi.testclient import TestClient

from docpipe.api.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Create a test client for the FastAPI application.

    Uses module scope for efficiency since the app doesn't change between tests.
    """
    return TestClient(app)


class TestApplicationStartup:
    """Test FastAPI application initialization."""

    def test_app_starts_without_errors(self, *, client: TestClient):
        """Test that the FastAPI application starts without errors."""
        assert client is not None
        assert app.title == "Docpipe Opensource API"
        assert app.version == "1.0.0"


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

    def test_security_headers_present_in_responses(self, *, client: TestClient):
        """Test that security headers are present in responses."""
        response = client.get("/health")

        assert response.status_code == 200
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["referrer-policy"] == "no-referrer"
        assert "content-security-policy" in response.headers

    def test_transaction_id_header_present_in_responses(self, *, client: TestClient):
        """Test that transaction ID header is present in responses."""
        response = client.get("/health")

        assert response.status_code == 200
        assert "x-transaction-id" in response.headers
        assert len(response.headers["x-transaction-id"]) > 0
