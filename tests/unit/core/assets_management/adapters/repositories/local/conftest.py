"""Shared fixtures for LocalFlowRepository tests."""

import tempfile
from pathlib import Path
from uuid import uuid4

import pytest

from docpipe.core.assets.flows.adapters.repositories.local.local_flow_repository import (
    LocalFlowRepository,
)
from docpipe.core.assets.flows.domain.models.flow import Flow


@pytest.fixture
def temp_flows_dir():
    """Create a temporary directory for flow file storage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def repository(temp_flows_dir, monkeypatch):
    """Create a LocalFlowRepository instance backed by a temporary directory."""
    monkeypatch.setenv("LOCAL_FLOWS_DIR", str(temp_flows_dir))
    return LocalFlowRepository()


@pytest.fixture
def sample_flow():
    """Return a Flow instance with a pre-assigned ID for use across test classes."""
    return Flow(
        name="Test Flow",
        definition={"doc_type": "pipeline", "pipelines": []},
        asset_id=str(uuid4()),
        description="A test flow",
    )
