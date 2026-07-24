"""Pytest fixtures for routes tests."""

from datetime import UTC, datetime
from typing import Any

import pytest

from docpipe.core.assets.flows.domain.models.flow import Flow


@pytest.fixture
def sample_flow_data_elyra() -> dict[str, Any]:
    """Sample flow data dictionary for testing (Elyra format)."""
    return {
        "doc_type": "pipeline",
        "version": "3.0",
        "json_schema": "https://api.dataplatform.ibm.com/schemas/common-pipeline/pipeline-flow/pipeline-flow-v3-schema.json",
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "primary_pipeline": "660e8400-e29b-41d4-a716-446655440000",
        "pipelines": [
            {
                "id": "660e8400-e29b-41d4-a716-446655440000",
                "nodes": [],
                "app_data": {
                    "ds_flow": {
                        "name": "Test Flow",
                        "description": "A test flow for unit testing",
                    },
                    "ui_data": {"comments": []},
                },
            }
        ],
        "schemas": [],
    }


@pytest.fixture
def sample_flow_data_authoring() -> dict[str, Any]:
    """Sample flow data dictionary for testing (authoring format)."""
    return {
        "flow_name": "Test Flow",
        "description": "A test flow for unit testing",
        "flow": [
            {
                "type": "ingest_local",
                "name": "ingest_node",
                "config": {"paths": "./data"},
                "depends_on": [],
            },
            {
                "type": "extract_operator",
                "name": "extract_node",
                "config": {},
                "depends_on": ["ingest_node"],
            },
        ],
        "global_config": {},
    }


# Backward compatibility: keep sample_flow_data pointing to authoring format
@pytest.fixture
def sample_flow_data(sample_flow_data_authoring) -> dict[str, Any]:
    """Sample flow data dictionary for testing (defaults to authoring format for backward compatibility)."""
    return sample_flow_data_authoring


@pytest.fixture
def sample_flow_with_id_elyra(sample_flow_data_elyra) -> Flow:
    """Sample Flow domain object with Elyra format definition for testing."""
    flow = Flow(
        flow_id="12345678-1234-1234-1234-123456789abc",
        name="Test Flow",
        description="A test flow for unit testing",
        definition=sample_flow_data_elyra,  # Elyra format definition
        tags=["test", "unit-test"],
        container_kind="project",
        container_id="550e8400-e29b-41d4-a716-446655440000",
        is_hidden=False,
        flow_version="2.0",
        job_id="660e8400-e29b-41d4-a716-446655440000",
        created_by="test_user",
        created_on=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
        modified_on=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
    )
    return flow


@pytest.fixture
def sample_flow_with_id(sample_flow_with_id_elyra) -> Flow:
    """Sample Flow domain object with a specific flow_id for testing (defaults to Elyra format for backward compatibility)."""
    return sample_flow_with_id_elyra


@pytest.fixture
def sample_authoring_flow_with_id() -> Flow:
    """Sample Flow domain object with authoring format definition for testing."""
    authoring_definition = {
        "flow_name": "Test Flow",
        "description": "A test flow for unit testing",
        "flow": [
            {
                "type": "ingest_local",
                "name": "ingest_node",
                "config": {"paths": "./data"},
                "depends_on": [],
            },
            {
                "type": "extract_operator",
                "name": "extract_node",
                "config": {},
                "depends_on": ["ingest_node"],
            },
        ],
        "global_config": {},
        "tags": ["test", "unit-test"],
    }
    flow = Flow(
        flow_id="12345678-1234-1234-1234-123456789abc",
        name="Test Flow",
        description="A test flow for unit testing",
        definition=authoring_definition,
        tags=["test", "unit-test"],
        container_kind=None,
        container_id=None,
        is_hidden=False,
        flow_version="2.0",
        job_id=None,
        created_by="test_user",
        created_on=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
        modified_on=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
    )
    return flow


@pytest.fixture
def multiple_sample_flows() -> list[Flow]:
    """Multiple sample flows for testing list operations."""
    flows = []
    # Use valid UUIDs for flow IDs
    flow_ids = [
        "12345678-1234-1234-1234-12345678900",
        "12345678-1234-1234-1234-123456789001",
        "12345678-1234-1234-1234-123456789002",
        "12345678-1234-1234-1234-123456789003",
        "12345678-1234-1234-1234-123456789004",
    ]
    for i in range(5):
        flow = Flow(
            flow_id=flow_ids[i],
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
