"""Unit tests for Flow CRUD operations.

This module tests flow create, retrieve, and list operations through the FastAPI endpoints.
Uses isolated temporary storage for each test to ensure test independence.
"""

import shutil
import tempfile
from pathlib import Path
from typing import Generator

import pytest
from fastapi.testclient import TestClient

from docpipe.api.auth.dependencies import get_current_user
from docpipe.api.auth.models import User
from docpipe.api.dependencies import get_flow_repository
from docpipe.api.main import app
from docpipe.core.assets.common.adapters.repositories.local_asset_repository import LocalAssetRepository
from docpipe.core.assets.flows.domain.models.flow import Flow


@pytest.fixture
def temp_flows_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for flow storage during tests."""
    temp_dir = tempfile.mkdtemp(prefix="test_flows_")
    temp_path = Path(temp_dir)

    yield temp_path

    if temp_path.exists():
        shutil.rmtree(temp_path)


@pytest.fixture
def test_flow_repository(*, temp_flows_dir: Path) -> LocalAssetRepository:
    """Create a LocalAssetRepository[Flow] instance using temporary directory."""
    return LocalAssetRepository(asset_type=Flow, storage_path=str(temp_flows_dir))


@pytest.fixture
def flow_client(*, test_flow_repository: LocalAssetRepository) -> Generator[TestClient, None, None]:
    """Create FastAPI test client with dependency overrides for flow operations."""
    app.dependency_overrides[get_flow_repository] = lambda: test_flow_repository
    app.dependency_overrides[get_current_user] = lambda: User(
        username="testuser", email="test@example.com", full_name="Test User"
    )

    client = TestClient(app)

    yield client

    app.dependency_overrides.clear()


class TestFlowCreation:
    """Test flow creation operations."""

    def test_create_flow_returns_201(self, *, flow_client: TestClient):
        """Test creating a flow returns 201 with flow data."""
        flow_data = {
            "name": "Test Flow",
            "description": "A test flow for unit testing",
            "tags": ["test", "unit"],
        }

        response = flow_client.post("/api/v1/flows?is_elyra=true", json=flow_data)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == flow_data["name"]
        assert data["description"] == flow_data["description"]
        assert set(data["tags"]) == set(flow_data["tags"])
        assert "flow_id" in data
        assert "created_on" in data
        assert "modified_on" in data


class TestFlowRetrieval:
    """Test flow retrieval operations."""

    def test_retrieve_flow_returns_200(self, *, flow_client: TestClient):
        """Test retrieving a created flow returns 200 with correct data."""
        # Create a flow
        flow_data = {
            "name": "Retrieve Test Flow",
            "description": "Flow for retrieval testing",
        }
        create_response = flow_client.post("/api/v1/flows?is_elyra=true", json=flow_data)
        assert create_response.status_code == 201
        flow_id = create_response.json()["flow_id"]

        # Retrieve the flow
        response = flow_client.get(f"/api/v1/flows/{flow_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["flow_id"] == flow_id
        assert data["name"] == flow_data["name"]
        assert data["description"] == flow_data["description"]

    def test_retrieve_nonexistent_flow_returns_404(self, *, flow_client: TestClient):
        """Test retrieving a non-existent flow returns 404."""
        nonexistent_id = "550e8400-e29b-41d4-a716-446655440000"

        response = flow_client.get(f"/api/v1/flows/{nonexistent_id}")

        assert response.status_code == 404


class TestFlowListing:
    """Test flow listing operations."""

    def test_list_flows_endpoint_returns_200(self, *, flow_client: TestClient):
        """Test listing flows endpoint returns 200 with proper structure."""
        response = flow_client.get("/api/v1/flows")

        assert response.status_code == 200
        data = response.json()
        assert "flows" in data
        assert "total_count" in data
        assert "offset" in data
        assert "limit" in data
        assert isinstance(data["flows"], list)
        assert isinstance(data["total_count"], int)


class TestFlowWorkflows:
    """Test complete flow workflows."""

    def test_create_and_retrieve_workflow(self, *, flow_client: TestClient):
        """Test complete workflow: create and retrieve flow."""
        # Create
        create_data = {
            "name": "Workflow Test Flow",
            "description": "Testing complete workflow",
            "tags": ["workflow", "test"],
        }
        create_response = flow_client.post("/api/v1/flows?is_elyra=true", json=create_data)
        assert create_response.status_code == 201
        flow_id = create_response.json()["flow_id"]

        # Retrieve
        get_response = flow_client.get(f"/api/v1/flows/{flow_id}")
        assert get_response.status_code == 200
        retrieved_data = get_response.json()
        assert retrieved_data["name"] == create_data["name"]
        assert retrieved_data["description"] == create_data["description"]
        assert set(retrieved_data["tags"]) == set(create_data["tags"])
