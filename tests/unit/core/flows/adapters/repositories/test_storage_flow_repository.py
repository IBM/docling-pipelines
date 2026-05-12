"""Tests for StorageFlowRepository."""

from unittest.mock import Mock

import pytest

from datasift.core.assets.flows.adapters.repositories.storage_flow_repository import (
    StorageFlowRepository,
)
from datasift.core.assets.flows.domain.models.flow import Flow
from datasift.exceptions.datasift_exceptions import (
    FlowInvalidDataException,
    FlowNotFoundException,
)
from datasift.storage import DuckDBKeyValueStorage, FileSystemStorage

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sample_flow():
    """Create a sample flow for testing."""
    return Flow(
        flow_id="test-flow-123",
        name="Test Flow",
        description="A test flow",
        definition={"doc_type": "pipeline", "version": "3.0", "pipelines": [{"id": "pipeline-1", "nodes": []}]},
    )


@pytest.fixture
def duckdb_repository(tmp_path):
    """Create StorageFlowRepository with DuckDB storage."""
    storage = DuckDBKeyValueStorage(database_path=str(tmp_path / "test_flows.db"))
    return StorageFlowRepository(storage=storage)


@pytest.fixture
def filesystem_repository(tmp_path):
    """Create StorageFlowRepository with filesystem storage."""
    storage = FileSystemStorage(base_dir=str(tmp_path / "flows"))
    return StorageFlowRepository(storage=storage)


# ============================================================================
# DuckDB Storage Tests
# ============================================================================


def test_duckdb_save_and_find_by_id(duckdb_repository, sample_flow):
    """Test saving and retrieving a flow with DuckDB storage."""
    saved = duckdb_repository.save(flow=sample_flow)
    assert saved.flow_id == sample_flow.flow_id

    retrieved = duckdb_repository.find_by_id(flow_id=sample_flow.flow_id)
    assert retrieved is not None
    assert retrieved.flow_id == sample_flow.flow_id
    assert retrieved.name == sample_flow.name
    assert retrieved.description == sample_flow.description


def test_duckdb_find_by_id_nonexistent(duckdb_repository):
    """Test retrieving a non-existent flow returns None."""
    result = duckdb_repository.find_by_id(flow_id="nonexistent-flow")
    assert result is None


def test_duckdb_find_all(duckdb_repository):
    """Test listing all flows with DuckDB storage."""
    flow1 = Flow(
        flow_id="flow-1", name="Flow 1", description="First flow", definition={"doc_type": "pipeline", "pipelines": []}
    )
    flow2 = Flow(
        flow_id="flow-2", name="Flow 2", description="Second flow", definition={"doc_type": "pipeline", "pipelines": []}
    )

    duckdb_repository.save(flow=flow1)
    duckdb_repository.save(flow=flow2)

    flows = duckdb_repository.find_all()
    assert len(flows) == 2
    flow_ids = [f.flow_id for f in flows]
    assert "flow-1" in flow_ids
    assert "flow-2" in flow_ids


def test_duckdb_delete(duckdb_repository, sample_flow):
    """Test deleting a flow with DuckDB storage."""
    duckdb_repository.save(flow=sample_flow)
    assert duckdb_repository.exists(flow_id=sample_flow.flow_id)

    deleted = duckdb_repository.delete(flow_id=sample_flow.flow_id)
    assert deleted is True
    assert not duckdb_repository.exists(flow_id=sample_flow.flow_id)


def test_duckdb_delete_nonexistent(duckdb_repository):
    """Test deleting a non-existent flow returns False."""
    deleted = duckdb_repository.delete(flow_id="nonexistent-flow")
    assert deleted is False


def test_duckdb_update(duckdb_repository, sample_flow):
    """Test updating a flow with DuckDB storage."""
    duckdb_repository.save(flow=sample_flow)

    sample_flow.name = "Updated Flow Name"
    sample_flow.description = "Updated description"
    updated = duckdb_repository.update(flow=sample_flow)

    assert updated.name == "Updated Flow Name"

    retrieved = duckdb_repository.find_by_id(flow_id=sample_flow.flow_id)
    assert retrieved.name == "Updated Flow Name"
    assert retrieved.description == "Updated description"


def test_duckdb_exists(duckdb_repository, sample_flow):
    """Test checking if a flow exists."""
    assert not duckdb_repository.exists(flow_id=sample_flow.flow_id)

    duckdb_repository.save(flow=sample_flow)
    assert duckdb_repository.exists(flow_id=sample_flow.flow_id)


def test_duckdb_bulk_delete(duckdb_repository):
    """Test bulk deleting flows."""
    flow1 = Flow(flow_id="flow-1", name="Flow 1", definition={"doc_type": "pipeline", "pipelines": []})
    flow2 = Flow(flow_id="flow-2", name="Flow 2", definition={"doc_type": "pipeline", "pipelines": []})
    flow3 = Flow(flow_id="flow-3", name="Flow 3", definition={"doc_type": "pipeline", "pipelines": []})

    duckdb_repository.save(flow=flow1)
    duckdb_repository.save(flow=flow2)
    duckdb_repository.save(flow=flow3)

    result = duckdb_repository.bulk_delete(flow_ids=["flow-1", "flow-2", "nonexistent"])

    assert result["total_requested"] == 3
    assert result["total_deleted"] >= 2  # At least 2 should be deleted
    assert "flow-1" in result["deleted"]
    assert "flow-2" in result["deleted"]

    # Verify the flows are actually deleted
    assert not duckdb_repository.exists(flow_id="flow-1")
    assert not duckdb_repository.exists(flow_id="flow-2")
    assert duckdb_repository.exists(flow_id="flow-3")  # flow-3 should still exist


# ============================================================================
# Filesystem Storage Tests
# ============================================================================


def test_filesystem_save_and_find_by_id(filesystem_repository, sample_flow):
    """Test saving and retrieving a flow with filesystem storage."""
    saved = filesystem_repository.save(flow=sample_flow)
    assert saved.flow_id == sample_flow.flow_id

    retrieved = filesystem_repository.find_by_id(flow_id=sample_flow.flow_id)
    assert retrieved is not None
    assert retrieved.flow_id == sample_flow.flow_id
    assert retrieved.name == sample_flow.name


def test_filesystem_find_all(filesystem_repository):
    """Test listing all flows with filesystem storage."""
    flow1 = Flow(flow_id="flow-1", name="Flow 1", definition={"doc_type": "pipeline", "pipelines": []})
    flow2 = Flow(flow_id="flow-2", name="Flow 2", definition={"doc_type": "pipeline", "pipelines": []})

    filesystem_repository.save(flow=flow1)
    filesystem_repository.save(flow=flow2)

    flows = filesystem_repository.find_all()
    assert len(flows) == 2


def test_filesystem_delete(filesystem_repository, sample_flow):
    """Test deleting a flow with filesystem storage."""
    filesystem_repository.save(flow=sample_flow)
    assert filesystem_repository.exists(flow_id=sample_flow.flow_id)

    deleted = filesystem_repository.delete(flow_id=sample_flow.flow_id)
    assert deleted is True
    assert not filesystem_repository.exists(flow_id=sample_flow.flow_id)


def test_filesystem_update(filesystem_repository, sample_flow):
    """Test updating a flow with filesystem storage."""
    filesystem_repository.save(flow=sample_flow)

    sample_flow.name = "Updated Flow Name"
    filesystem_repository.update(flow=sample_flow)

    retrieved = filesystem_repository.find_by_id(flow_id=sample_flow.flow_id)
    assert retrieved.name == "Updated Flow Name"


# ============================================================================
# Exception Handling Tests
# ============================================================================


def test_save_without_flow_id(duckdb_repository):
    """Test saving a flow without flow_id raises FlowInvalidDataException."""
    flow = Flow(name="Test", definition={"doc_type": "pipeline", "pipelines": []})
    flow.flow_id = None  # Force None

    with pytest.raises(FlowInvalidDataException, match="Flow ID is required"):
        duckdb_repository.save(flow=flow)


def test_update_without_flow_id(duckdb_repository):
    """Test updating a flow without flow_id raises FlowInvalidDataException."""
    flow = Flow(name="Test", definition={"doc_type": "pipeline", "pipelines": []})
    flow.flow_id = None  # Force None

    with pytest.raises(FlowInvalidDataException, match="Flow ID is required"):
        duckdb_repository.update(flow=flow)


def test_update_nonexistent_flow(duckdb_repository, sample_flow):
    """Test updating a non-existent flow raises FlowNotFoundException."""
    with pytest.raises(FlowNotFoundException, match="Flow not found"):
        duckdb_repository.update(flow=sample_flow)


def test_bulk_delete_empty_list(duckdb_repository):
    """Test bulk delete with empty list raises FlowInvalidDataException."""
    with pytest.raises(FlowInvalidDataException, match="flow_ids list cannot be empty"):
        duckdb_repository.bulk_delete(flow_ids=[])


# ============================================================================
# Mock Storage Tests
# ============================================================================


def test_repository_with_mock_storage():
    """Test repository with mock storage."""
    mock_storage = Mock()
    mock_storage.save_record = Mock()
    mock_storage.get_record = Mock(return_value=None)
    mock_storage.record_exists = Mock(return_value=False)

    repository = StorageFlowRepository(storage=mock_storage)

    flow = Flow(
        flow_id="test-flow", name="Test", description="Test flow", definition={"doc_type": "pipeline", "pipelines": []}
    )

    repository.save(flow=flow)

    mock_storage.save_record.assert_called_once()
    call_args = mock_storage.save_record.call_args
    assert call_args.kwargs["collection"] == "flows"
    assert call_args.kwargs["key"] == "test-flow"


def test_find_all_with_invalid_records(duckdb_repository):
    """Test find_all skips invalid flow records."""
    # Save a valid flow
    valid_flow = Flow(flow_id="valid-flow", name="Valid Flow", definition={"doc_type": "pipeline", "pipelines": []})
    duckdb_repository.save(flow=valid_flow)

    # Manually insert an invalid record
    invalid_data = {"flow_id": "invalid", "name": "Invalid"}  # Missing required 'definition'
    duckdb_repository.storage.save_record(collection="flows", key="invalid-flow", data=invalid_data)

    # find_all should skip the invalid record and return only valid ones
    flows = duckdb_repository.find_all()
    assert len(flows) == 1
    assert flows[0].flow_id == "valid-flow"


# ============================================================================
# Integration Tests
# ============================================================================


def test_full_crud_cycle_duckdb(duckdb_repository):
    """Test complete CRUD cycle with DuckDB storage."""
    # Create
    flow = Flow(
        flow_id="crud-test",
        name="CRUD Test Flow",
        description="Testing CRUD operations",
        definition={"doc_type": "pipeline", "pipelines": []},
    )
    saved = duckdb_repository.save(flow=flow)
    assert saved.flow_id == "crud-test"

    # Read
    retrieved = duckdb_repository.find_by_id(flow_id="crud-test")
    assert retrieved is not None
    assert retrieved.name == "CRUD Test Flow"

    # Update
    retrieved.name = "Updated CRUD Test"
    updated = duckdb_repository.update(flow=retrieved)
    assert updated.name == "Updated CRUD Test"

    # Verify update
    verified = duckdb_repository.find_by_id(flow_id="crud-test")
    assert verified.name == "Updated CRUD Test"

    # Delete
    deleted = duckdb_repository.delete(flow_id="crud-test")
    assert deleted is True

    # Verify deletion
    assert not duckdb_repository.exists(flow_id="crud-test")


def test_full_crud_cycle_filesystem(filesystem_repository):
    """Test complete CRUD cycle with filesystem storage."""
    # Create
    flow = Flow(
        flow_id="crud-test",
        name="CRUD Test Flow",
        description="Testing CRUD operations",
        definition={"doc_type": "pipeline", "pipelines": []},
    )
    saved = filesystem_repository.save(flow=flow)
    assert saved.flow_id == "crud-test"

    # Read
    retrieved = filesystem_repository.find_by_id(flow_id="crud-test")
    assert retrieved is not None

    # Update
    retrieved.name = "Updated CRUD Test"
    updated = filesystem_repository.update(flow=retrieved)
    assert updated.name == "Updated CRUD Test"

    # Delete
    deleted = filesystem_repository.delete(flow_id="crud-test")
    assert deleted is True

    # Verify deletion
    assert not filesystem_repository.exists(flow_id="crud-test")


def test_duckdb_actual_database_file_created(tmp_path):
    """Verify that actual DuckDB database file is created (not mocked)."""
    import duckdb

    db_path = tmp_path / "verify_real_db.db"

    # Create repository with DuckDB storage
    storage = DuckDBKeyValueStorage(database_path=str(db_path))
    repository = StorageFlowRepository(storage=storage)

    # Save a flow
    flow = Flow(flow_id="verify-real", name="Verify Real DB", definition={"doc_type": "pipeline", "pipelines": []})
    repository.save(flow=flow)

    # Verify the database file actually exists
    assert db_path.exists(), "DuckDB database file should exist"

    # Verify we can connect to it directly with DuckDB
    conn = duckdb.connect(str(db_path))

    # Verify the flows table exists
    tables = conn.execute("SHOW TABLES").fetchall()
    table_names = [t[0] for t in tables]
    assert "flows" in table_names, "flows table should exist in database"

    # Verify the data is actually in the database
    result = conn.execute("SELECT COUNT(*) FROM flows").fetchone()
    assert result is not None and result[0] == 1, "Should have 1 flow in database"

    # Verify the actual flow data
    flow_data = conn.execute("SELECT key, data FROM flows WHERE key = 'verify-real'").fetchone()
    assert flow_data is not None, "Flow should exist in database"
    assert flow_data[0] == "verify-real", "Flow key should match"

    conn.close()


def test_filesystem_actual_files_created(tmp_path):
    """Verify that actual filesystem files are created (not mocked)."""
    import json

    base_dir = tmp_path / "verify_real_fs"

    # Create repository with filesystem storage
    storage = FileSystemStorage(base_dir=str(base_dir))
    repository = StorageFlowRepository(storage=storage)

    # Save a flow
    flow = Flow(
        flow_id="verify-real-fs", name="Verify Real Filesystem", definition={"doc_type": "pipeline", "pipelines": []}
    )
    repository.save(flow=flow)

    # Verify the directory structure exists
    flows_dir = base_dir / "flows"
    assert flows_dir.exists(), "flows directory should exist"

    # Verify the JSON file exists
    flow_file = flows_dir / "verify-real-fs.json"
    assert flow_file.exists(), "Flow JSON file should exist"

    # Verify we can read the file directly
    with open(flow_file) as f:
        flow_data = json.load(f)

    assert flow_data["flow_id"] == "verify-real-fs", "Flow ID should match"
    assert flow_data["name"] == "Verify Real Filesystem", "Flow name should match"
    assert "definition" in flow_data, "Flow should have definition"
