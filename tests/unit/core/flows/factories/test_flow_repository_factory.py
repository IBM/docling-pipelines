"""Tests for FlowRepositoryFactory."""

import pytest

from datasift.core.assets.flows.adapters.repositories.storage_flow_repository import (
    StorageFlowRepository,
)
from datasift.core.assets.flows.factories.flow_repository_factory import FlowRepositoryFactory


def test_create_duckdb_repository(tmp_path):
    """Test creating a DuckDB flow repository."""
    db_path = str(tmp_path / "test.db")

    repository = FlowRepositoryFactory.create(storage_type="duckdb", database_path=db_path)

    assert isinstance(repository, StorageFlowRepository)


def test_create_filesystem_repository(tmp_path):
    """Test creating a filesystem flow repository."""
    base_dir = str(tmp_path / "flows")

    repository = FlowRepositoryFactory.create(storage_type="filesystem", base_dir=base_dir)

    assert isinstance(repository, StorageFlowRepository)


def test_list_available():
    """Test listing available storage types."""
    available = FlowRepositoryFactory.list_available()

    assert "duckdb" in available
    assert "filesystem" in available
    assert len(available) >= 2


def test_create_invalid_storage_type():
    """Test creating repository with invalid storage type raises error."""
    with pytest.raises(ValueError, match="Unsupported storage type"):
        FlowRepositoryFactory.create(storage_type="invalid", some_param="value")


def test_factory_creates_working_repository(tmp_path):
    """Test that factory-created repository actually works."""
    from datasift.core.assets.flows.domain.models.flow import Flow

    # Create repository via factory
    repository = FlowRepositoryFactory.create(storage_type="duckdb", database_path=str(tmp_path / "test.db"))

    # Create and save a flow
    flow = Flow(flow_id="factory-test", name="Factory Test Flow", definition={"doc_type": "pipeline", "pipelines": []})

    saved = repository.save(flow=flow)
    assert saved.flow_id == "factory-test"

    # Retrieve the flow
    retrieved = repository.find_by_id(flow_id="factory-test")
    assert retrieved is not None
    assert retrieved.name == "Factory Test Flow"
