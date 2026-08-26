"""
Integration test template for a docpipe operator or API route.

Copy this file to:
  - tests/integration/operators/<operator_name>/test_<operator_name>_integration.py
  - tests/integration/api/test_<route>_integration.py

See docs/guides/TESTING_STANDARDS.md for full guidance.
"""

import pytest
from fastapi.testclient import TestClient

# Replace with real imports:
# from docpipe.api.main import app
# from docpipe.api.auth.jwt_handler import get_current_user


# ---------------------------------------------------------------------------
# Skip guard — integration tests require external services
# ---------------------------------------------------------------------------


def pytest_configure(config):
    """Register integration marker."""


# ---------------------------------------------------------------------------
# Operator integration example
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestMyOperatorIntegration:
    """Integration tests — require real services (Ollama, OpenSearch, etc.).

    These tests are excluded from CI via `-m "unit and not slow"`.
    Run locally with: pytest tests/integration/ -v
    """

    def test_operator_processes_real_document(self, tmp_path) -> None:
        """End-to-end: operator processes a real document file on disk."""
        # Create a real test file
        doc = tmp_path / "test.txt"
        doc.write_text("This is a real document for integration testing.")

        # op = MyOperator(config={"doc_column": "content", "paths": str(tmp_path)})
        # ... run ingest + operator, assert output columns exist


# ---------------------------------------------------------------------------
# API route integration example
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestMyRouteIntegration:
    """FastAPI route integration tests using TestClient with dependency overrides."""

    @pytest.fixture
    def client(self):
        """TestClient with authentication bypassed."""
        from unittest.mock import MagicMock

        # app.dependency_overrides[get_current_user] = lambda: MagicMock(username="test-user")
        # yield TestClient(app)
        # app.dependency_overrides.clear()
        return MagicMock()  # replace with real client fixture

    def test_endpoint_returns_200_for_valid_payload(self, client: TestClient) -> None:
        # response = client.post("/api/v1/flows", json={"flow_name": "test-flow", "flow": []})
        # assert response.status_code == 201
        ...  # replace with real assertions

    def test_endpoint_returns_401_without_authentication(self) -> None:
        # unauthenticated_client = TestClient(app)
        # response = unauthenticated_client.get("/api/v1/flows")
        # assert response.status_code == 401
        ...  # replace with real assertions
