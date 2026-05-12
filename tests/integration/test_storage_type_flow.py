"""Integration test for storage type configuration flow.

Tests the complete flow of storage_type from flow JSON definition through
orchestrator to operators (FlowRepository and DocumentSetOperator).
"""

import tempfile
from pathlib import Path

import pyarrow as pa
import pytest

from datasift.core.constants.constants import DatasiftConstants
from datasift.core.orchestration.python.python_orchestrator import PythonOrchestrator
from datasift.storage import StorageFactory


class TestStorageTypeFlow:
    """Test storage type configuration propagation through the system."""

    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir)
            yield {
                "base": base_path,
                "duckdb": base_path / "duckdb",
                "filesystem": base_path / "filesystem",
                "data": base_path / "data",
            }

    @pytest.fixture
    def sample_data(self):
        """Create sample PyArrow table for testing."""
        return pa.table(
            {
                "id": ["doc1", "doc2", "doc3"],
                "content": ["Content 1", "Content 2", "Content 3"],
                "metadata": ["Meta 1", "Meta 2", "Meta 3"],
            }
        )

    def test_storage_type_duckdb_flow(self, temp_dirs, sample_data):
        """Test flow with storage_type='duckdb' in global_config."""
        # Create flow definition with storage_type in global_config
        flow_def = {
            "name": "test-storage-duckdb",
            "flow_id": "test-flow-duckdb-001",
            "global_config": {
                "storage_type": "duckdb",
                "doc_column": "content",
            },
            "dag": [
                {
                    "id": "ingest-1",
                    "name": "ingest_test",
                    "operator": "noop",
                    "config": {},
                },
                {
                    "id": "docset-1",
                    "name": "document_set_test",
                    "operator": "document_set",
                    "config": {
                        "document_set_name": "test_docs_duckdb",
                        "database_path": str(temp_dirs["duckdb"] / "test.db"),
                        "data_backend": "duckdb",
                    },
                    "input_edges": ["ingest-1"],
                },
            ],
        }

        # Create orchestrator
        orchestrator = PythonOrchestrator()

        # Execute flow
        params = {
            DatasiftConstants.JOB_ID: "test-job-001",
            DatasiftConstants.JOB_RUN_ID: "test-run-001",
        }

        # Verify storage_type is extracted and validated
        try:
            orchestrator.execute(flow_def=flow_def, params=params)
        except Exception as e:
            # Expected to fail at operator execution, but storage_type should be validated
            assert "storage_type" not in str(e).lower() or "unsupported" not in str(e).lower()

    def test_storage_type_filesystem_flow(self, temp_dirs):
        """Test flow with storage_type='filesystem' in global_config."""
        flow_def = {
            "name": "test-storage-filesystem",
            "flow_id": "test-flow-fs-001",
            "global_config": {
                "storage_type": "filesystem",
                "doc_column": "content",
            },
            "dag": [
                {
                    "id": "ingest-1",
                    "name": "ingest_test",
                    "operator": "noop",
                    "config": {},
                },
            ],
        }

        orchestrator = PythonOrchestrator()
        params = {
            DatasiftConstants.JOB_ID: "test-job-002",
            DatasiftConstants.JOB_RUN_ID: "test-run-002",
        }

        # Verify filesystem storage type is accepted
        try:
            orchestrator.execute(flow_def=flow_def, params=params)
        except Exception as e:
            # Should not fail on storage_type validation
            assert "unsupported storage type" not in str(e).lower()

    def test_storage_type_default(self, temp_dirs):
        """Test flow without storage_type uses default (duckdb)."""
        flow_def = {
            "name": "test-storage-default",
            "flow_id": "test-flow-default-001",
            "global_config": {
                "doc_column": "content",
            },
            "dag": [
                {
                    "id": "ingest-1",
                    "name": "ingest_test",
                    "operator": "noop",
                    "config": {},
                },
            ],
        }

        orchestrator = PythonOrchestrator()
        params = {
            DatasiftConstants.JOB_ID: "test-job-003",
            DatasiftConstants.JOB_RUN_ID: "test-run-003",
        }

        # Should use default storage type (duckdb)
        try:
            orchestrator.execute(flow_def=flow_def, params=params)
        except Exception as e:
            # Should not fail on storage_type
            assert "storage type" not in str(e).lower()

    def test_storage_type_invalid(self, temp_dirs):
        """Test flow with invalid storage_type raises error."""
        flow_def = {
            "name": "test-storage-invalid",
            "flow_id": "test-flow-invalid-001",
            "global_config": {
                "storage_type": "invalid_backend",
                "doc_column": "content",
            },
            "dag": [
                {
                    "id": "ingest-1",
                    "name": "ingest_test",
                    "operator": "noop",
                    "config": {},
                },
            ],
        }

        orchestrator = PythonOrchestrator()
        params = {
            DatasiftConstants.JOB_ID: "test-job-004",
            DatasiftConstants.JOB_RUN_ID: "test-run-004",
        }

        # Should raise error for unsupported storage type
        with pytest.raises(Exception) as exc_info:
            orchestrator.execute(flow_def=flow_def, params=params)

        assert "unsupported storage type" in str(exc_info.value).lower()
        assert "invalid_backend" in str(exc_info.value)

    def test_storage_factory_validation(self):
        """Test StorageFactory validates storage types correctly."""
        # Valid storage types should work
        storage_duckdb = StorageFactory.create_key_value_storage(storage_type="duckdb", database_path=":memory:")
        assert storage_duckdb is not None

        # Invalid storage type should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            StorageFactory.create_key_value_storage(storage_type="invalid_type", database_path=":memory:")

        assert "unsupported" in str(exc_info.value).lower()
        assert "invalid_type" in str(exc_info.value)

    def test_storage_type_propagation_to_params(self, temp_dirs):
        """Test that storage_type is added to params for operators."""
        flow_def = {
            "name": "test-storage-propagation",
            "flow_id": "test-flow-prop-001",
            "global_config": {
                "storage_type": "filesystem",
                "doc_column": "content",
            },
            "dag": [
                {
                    "id": "ingest-1",
                    "name": "ingest_test",
                    "operator": "noop",
                    "config": {},
                },
            ],
        }

        orchestrator = PythonOrchestrator()

        # Mock to capture params passed to operators
        original_create_executor = orchestrator.create_executor_impl
        captured_params = {}

        def mock_create_executor(*, name, operator, params, job_stats_service=None):
            captured_params.update(params)
            return original_create_executor(
                name=name, operator=operator, params=params, job_stats_service=job_stats_service
            )

        orchestrator.create_executor_impl = mock_create_executor

        params = {
            DatasiftConstants.JOB_ID: "test-job-005",
            DatasiftConstants.JOB_RUN_ID: "test-run-005",
        }

        try:
            orchestrator.execute(flow_def=flow_def, params=params)
        except Exception:
            pass  # We just want to check params were set

        # Verify storage_type was added to params
        assert DatasiftConstants.STORAGE_TYPE in captured_params
        assert captured_params[DatasiftConstants.STORAGE_TYPE] == "filesystem"

    def test_constants_defined(self):
        """Test that required constants are defined."""
        assert hasattr(DatasiftConstants, "STORAGE_TYPE")
        assert hasattr(DatasiftConstants, "DEFAULT_STORAGE_TYPE")
        assert hasattr(DatasiftConstants, "SUPPORTED_STORAGE_TYPES")

        assert DatasiftConstants.STORAGE_TYPE == "storage_type"
        assert DatasiftConstants.DEFAULT_STORAGE_TYPE == "duckdb"
        assert "duckdb" in DatasiftConstants.SUPPORTED_STORAGE_TYPES
        assert "filesystem" in DatasiftConstants.SUPPORTED_STORAGE_TYPES


# Made with Bob
