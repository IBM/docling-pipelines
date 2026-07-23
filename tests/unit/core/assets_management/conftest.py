"""Pytest fixtures for assets management tests."""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import Mock

import pytest

from docpipe.core.assets.common.domain.ports.asset_repository import AssetRepository
from docpipe.core.assets.flows.application.services.flow_service import FlowService
from docpipe.core.assets.flows.domain.models.flow import Flow


@pytest.fixture
def sample_flow_data() -> dict[str, Any]:
    """Sample flow data dictionary for testing."""
    return {
        "name": "Test Flow",
        "description": "A test flow for unit testing",
        "definition": {
            "doc_type": "pipeline",
            "version": "3.0",
            "id": "test-pipeline-id",
            "primary_pipeline": "test-pipeline-id",
            "pipelines": [
                {
                    "id": "test-pipeline-id",
                    "nodes": [
                        {
                            "id": "node1",
                            "type": "execution_node",
                            "op": "execute-notebook-node",
                        }
                    ],
                    "app_data": {"ds_flow": {}, "ui_data": {}},
                }
            ],
            "schemas": [],
        },
        "tags": ["test", "unit-test"],
        "container_kind": "project",
        "container_id": "550e8400-e29b-41d4-a716-446655440000",
        "is_hidden": False,
        "flow_version": "2.0",
        "job_id": "660e8400-e29b-41d4-a716-446655440000",
        "created_by": "test_user",
    }


@pytest.fixture
def sample_flow_domain(sample_flow_data) -> Flow:
    """Sample Flow domain object for testing."""
    return Flow(
        name=sample_flow_data["name"],
        description=sample_flow_data["description"],
        definition=sample_flow_data["definition"],
        tags=sample_flow_data["tags"],
        container_kind=sample_flow_data["container_kind"],
        container_id=sample_flow_data["container_id"],
        is_hidden=sample_flow_data["is_hidden"],
        flow_version=sample_flow_data["flow_version"],
        job_id=sample_flow_data["job_id"],
        created_by=sample_flow_data["created_by"],
    )


@pytest.fixture
def sample_flow_with_id(sample_flow_data) -> Flow:
    """Sample Flow domain object with a specific flow_id for testing."""
    return Flow(
        asset_id="test-flow-id-123",
        name=sample_flow_data["name"],
        description=sample_flow_data["description"],
        definition=sample_flow_data["definition"],
        tags=sample_flow_data["tags"],
        container_kind=sample_flow_data["container_kind"],
        container_id=sample_flow_data["container_id"],
        is_hidden=sample_flow_data["is_hidden"],
        flow_version=sample_flow_data["flow_version"],
        job_id=sample_flow_data["job_id"],
        created_by=sample_flow_data["created_by"],
        created_on=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
        modified_on=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
    )


@pytest.fixture
def mock_flow_repository() -> Mock:
    """Mock AssetRepository[Flow] for testing."""
    mock_repo = Mock(spec=AssetRepository[Flow])

    # Configure default return values
    mock_repo.save.return_value = None  # Will be set by individual tests
    mock_repo.find_by_id.return_value = None
    mock_repo.find_all.return_value = []
    mock_repo.delete.return_value = True
    mock_repo.exists.return_value = False
    mock_repo.exists_by_name.return_value = False  # Default: no duplicate names

    return mock_repo


@pytest.fixture
def mock_flow_service(mock_flow_repository) -> FlowService:
    """Mock FlowService with mocked repository for testing."""
    return FlowService(repository=mock_flow_repository)


@pytest.fixture
def multiple_sample_flows() -> list[Flow]:
    """Multiple sample flows for testing list operations."""
    flows = []
    for i in range(5):
        flow = Flow(
            asset_id=f"flow-id-{i}",
            name=f"Test Flow {i}",
            description=f"Description for flow {i}",
            definition={"doc_type": "pipeline", "pipelines": []},
            tags=["test", f"tag-{i}"],
            is_hidden=(i % 2 == 0),
            created_on=datetime(2024, 1, i + 1, 12, 0, 0, tzinfo=UTC),
            modified_on=datetime(2024, 1, i + 1, 12, 0, 0, tzinfo=UTC),
        )
        flows.append(flow)
    return flows


@pytest.fixture
def invalid_flow_data() -> dict[str, Any]:
    """Invalid flow data for testing validation errors."""
    return {
        "name": "",  # Empty name - invalid
        "description": "x" * 2001,  # Too long - invalid
        "definition": {},  # Empty definition - invalid
        "container_kind": "invalid",  # Invalid container kind
    }
