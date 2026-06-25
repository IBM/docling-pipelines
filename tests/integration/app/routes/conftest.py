"""Pytest fixtures for flow API integration tests."""

import shutil
import tempfile
from pathlib import Path
from typing import Generator

import pytest
from fastapi.testclient import TestClient

from docpipe.api.main import app
from docpipe.api.routes.flows import get_flow_repository
from docpipe.core.assets.flows.adapters.repositories.local.local_flow_repository import (
    LocalFlowRepository,
)


@pytest.fixture(scope="function")
def temp_flows_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for flow storage during tests.

    This fixture creates a clean temporary directory for each test function,
    ensuring test isolation. The directory is automatically cleaned up after
    the test completes.

    Yields:
        Path: Path to the temporary flows directory
    """
    temp_dir = tempfile.mkdtemp(prefix="test_flows_")
    temp_path = Path(temp_dir)

    yield temp_path

    # Cleanup after test
    if temp_path.exists():
        shutil.rmtree(temp_path)


@pytest.fixture(scope="function")
def test_repository(temp_flows_dir: Path, monkeypatch) -> LocalFlowRepository:
    """Create a LocalFlowRepository instance using temporary directory.
    Args:
        temp_flows_dir: Temporary directory fixture
        monkeypatch: Pytest monkeypatch fixture
    Returns:
        LocalFlowRepository: Repository instance configured for testing
    """
    monkeypatch.setenv("LOCAL_FLOWS_DIR", str(temp_flows_dir))
    return LocalFlowRepository()


@pytest.fixture(scope="function")
def test_client(
    test_repository: LocalFlowRepository,
) -> Generator[TestClient, None, None]:
    """Create FastAPI test client with dependency overrides.

    This fixture creates a test client that uses a temporary file system
    for flow storage, ensuring tests don't interfere with production data
    or each other.

    Args:
        test_repository: Test repository fixture

    Yields:
        TestClient: Configured test client for making API requests
    """
    # Override the repository dependency to use test repository
    app.dependency_overrides[get_flow_repository] = lambda: test_repository

    client = TestClient(app)

    yield client

    # Clear dependency overrides after test
    app.dependency_overrides.clear()


@pytest.fixture
def sample_flow_data() -> dict:
    """Sample flow data for creating test flows.

    Returns:
        dict: Valid flow creation request data
    """
    return {
        "name": "Test Integration Flow",
        "description": "A flow for integration testing",
        "definition": {
            "doc_type": "pipeline",
            "version": "3.0",
            "pipelines": [
                {
                    "id": "test-pipeline-id",
                    "nodes": [
                        {
                            "id": "node1",
                            "type": "execution_node",
                            "op": "test-operator",
                        }
                    ],
                    "app_data": {"ds_flow": {}, "ui_data": {}},
                }
            ],
            "schemas": [],
        },
        "tags": ["integration", "test"],
        "container_kind": "project",
        "container_id": "550e8400-e29b-41d4-a716-446655440000",
        "is_hidden": False,
        "flow_version": "2.0",
        "created_by": "test_user",
    }


@pytest.fixture
def minimal_flow_data() -> dict:
    """Minimal flow data with only required fields.

    Returns:
        dict: Minimal valid flow creation request data
    """
    return {
        "name": "Minimal Test Flow",
    }


@pytest.fixture
def create_test_flow(test_client: TestClient, sample_flow_data: dict):
    """Factory fixture for creating test flows.

    This fixture returns a function that can be called to create flows
    during tests. It's useful for tests that need multiple flows.

    Args:
        test_client: Test client fixture
        sample_flow_data: Sample flow data fixture

    Returns:
        Callable: Function that creates a flow and returns the response
    """

    def _create_flow(flow_data: dict | None = None, is_elyra: bool = True) -> dict:
        """Create a flow using the test client.

        Args:
            flow_data: Optional custom flow data, defaults to sample_flow_data
            is_elyra: Whether the flow definition is in Elyra format (default: True)

        Returns:
            dict: Created flow response data
        """
        data = flow_data if flow_data is not None else sample_flow_data
        response = test_client.post(f"/api/v1/flows?is_elyra={str(is_elyra).lower()}", json=data)
        assert response.status_code == 201, f"Failed to create flow: {response.json()}"
        return response.json()

    return _create_flow
