"""Tests for Prefect batch subflow module."""

import base64
from unittest.mock import Mock, patch

import pyarrow as pa
import pytest

from docpipe.core.constants.constants import DocpipeConstants
from docpipe.core.orchestration.prefect.batch_subflow import (
    _deserialize_batch_data,
    _load_batch,
    batch_subflow,
)
from docpipe.exceptions.docpipe_exceptions import FlowExecutionFailedException


@pytest.fixture
def sample_batch_table():
    """Create a sample PyArrow table for testing."""
    return pa.table(
        {
            "id": [1, 2, 3],
            "text": ["First", "Second", "Third"],
            "value": [10.5, 20.3, 30.1],
        }
    )


@pytest.fixture
def sample_op_flow():
    """Create a sample operator flow."""
    return [
        {"operator": "IngestOperator", "config": {}},
        {"operator": "ExtractOperator", "config": {}},
    ]


@pytest.fixture
def sample_global_config():
    """Create a sample global config."""
    return {
        DocpipeConstants.JOB_ID: "test-job-123",
        DocpipeConstants.FLOW_ID: "test-flow-456",
        DocpipeConstants.TRACK_PERF: False,
    }


class TestDeserializeBatchData:
    """Test _deserialize_batch_data function."""

    def test_deserialize_basic_data(self):
        """Test deserializing basic batch data."""
        batch_data = {
            "columns": ["id", "name"],
            "data": [
                {"id": 1, "name": "Alice"},
                {"id": 2, "name": "Bob"},
            ],
        }

        table = _deserialize_batch_data(batch_data=batch_data)

        assert isinstance(table, pa.Table)
        assert table.num_columns == 2
        assert table.num_rows == 2
        assert table.column_names == ["id", "name"]

    def test_deserialize_with_binary_columns(self):
        """Test deserializing data with binary columns."""
        binary_value = b"test binary data"
        encoded_value = base64.b64encode(binary_value).decode("utf-8")

        batch_data = {
            "columns": ["id", "data"],
            "data": [
                {"id": 1, "data": encoded_value},
                {"id": 2, "data": encoded_value},
            ],
            "binary_columns": ["data"],
        }

        table = _deserialize_batch_data(batch_data=batch_data)

        assert isinstance(table, pa.Table)
        assert table.num_columns == 2
        # Binary data should be decoded
        assert table.column("data")[0].as_py() == binary_value

    def test_deserialize_with_none_values(self):
        """Test deserializing data with None values."""
        batch_data = {
            "columns": ["id", "optional"],
            "data": [
                {"id": 1, "optional": "value"},
                {"id": 2, "optional": None},
            ],
        }

        table = _deserialize_batch_data(batch_data=batch_data)

        assert isinstance(table, pa.Table)
        assert table.num_rows == 2
        assert table.column("optional")[1].as_py() is None

    def test_deserialize_empty_data(self):
        """Test deserializing empty data."""
        batch_data = {
            "columns": ["id", "name"],
            "data": [],
        }

        table = _deserialize_batch_data(batch_data=batch_data)

        assert isinstance(table, pa.Table)
        assert table.num_rows == 0
        assert table.num_columns == 2

    def test_deserialize_invalid_data_raises_exception(self):
        """Test that invalid data raises FlowExecutionFailedException."""
        batch_data = {
            "columns": ["id"],
            # Missing "data" key
        }

        with pytest.raises(FlowExecutionFailedException) as exc_info:
            _deserialize_batch_data(batch_data=batch_data)

        assert "deserialization failed" in str(exc_info.value).lower()

    def test_deserialize_with_multiple_binary_columns(self):
        """Test deserializing with multiple binary columns."""
        binary1 = b"data1"
        binary2 = b"data2"
        encoded1 = base64.b64encode(binary1).decode("utf-8")
        encoded2 = base64.b64encode(binary2).decode("utf-8")

        batch_data = {
            "columns": ["id", "bin1", "bin2"],
            "data": [
                {"id": 1, "bin1": encoded1, "bin2": encoded2},
            ],
            "binary_columns": ["bin1", "bin2"],
        }

        table = _deserialize_batch_data(batch_data=batch_data)

        assert table.column("bin1")[0].as_py() == binary1
        assert table.column("bin2")[0].as_py() == binary2


class TestLoadBatch:
    """Test _load_batch function."""

    def test_load_batch_inline(self, sample_batch_table):
        """Test loading batch from inline data."""
        batch_data = {
            "columns": ["id", "text"],
            "data": [
                {"id": 1, "text": "First"},
                {"id": 2, "text": "Second"},
            ],
        }

        batch_transfer = {
            "type": "inline",
            "data": batch_data,
        }

        table = _load_batch(batch_transfer=batch_transfer, batch_num=0)

        assert isinstance(table, pa.Table)
        assert table.num_rows == 2

    @patch("docpipe.core.orchestration.prefect.batch_subflow.pq.read_table")
    def test_load_batch_local(self, mock_read_table, sample_batch_table):
        """Test loading batch from local filesystem."""
        mock_read_table.return_value = sample_batch_table

        batch_transfer = {
            "type": "local",
            "ref": "/tmp/batch-0.parquet",
        }

        table = _load_batch(batch_transfer=batch_transfer, batch_num=0)

        assert isinstance(table, pa.Table)
        mock_read_table.assert_called_once_with("/tmp/batch-0.parquet")

    @patch("pyarrow.fs.S3FileSystem")
    @patch("docpipe.core.orchestration.prefect.batch_subflow.pq.read_table")
    def test_load_batch_s3(self, mock_read_table, mock_s3fs_class, sample_batch_table):
        """Test loading batch from S3."""
        mock_s3fs = Mock()
        mock_s3fs_class.return_value = mock_s3fs
        mock_read_table.return_value = sample_batch_table

        batch_transfer = {
            "type": "s3",
            "bucket": "test-bucket",
            "key": "batches/batch-0.parquet",
            "access_key": "test-access-key",  # pragma: allowlist secret
            "secret_key": "test-secret-key",  # pragma: allowlist secret
            "region": "us-east-1",
            "endpoint_url": "https://s3.amazonaws.com",
        }

        table = _load_batch(batch_transfer=batch_transfer, batch_num=0)

        assert isinstance(table, pa.Table)
        mock_s3fs_class.assert_called_once()
        mock_read_table.assert_called_once()

    @patch("pyarrow.fs.S3FileSystem")
    @patch("docpipe.core.orchestration.prefect.batch_subflow.pq.read_table")
    def test_load_batch_s3_without_optional_params(self, mock_read_table, mock_s3fs_class, sample_batch_table):
        """Test loading batch from S3 without optional parameters."""
        mock_s3fs = Mock()
        mock_s3fs_class.return_value = mock_s3fs
        mock_read_table.return_value = sample_batch_table

        batch_transfer = {
            "type": "s3",
            "bucket": "test-bucket",
            "key": "batches/batch-0.parquet",
            "access_key": "test-access-key",  # pragma: allowlist secret
            "secret_key": "test-secret-key",  # pragma: allowlist secret
        }

        table = _load_batch(batch_transfer=batch_transfer, batch_num=0)

        assert isinstance(table, pa.Table)
        # Verify S3FileSystem was called with only required params
        call_kwargs = mock_s3fs_class.call_args[1]
        assert "access_key" in call_kwargs
        assert "secret_key" in call_kwargs
        assert "region" not in call_kwargs

    def test_load_batch_unknown_type(self):
        """Test loading batch with unknown storage type."""
        batch_transfer = {
            "type": "unknown",
        }

        with pytest.raises(FlowExecutionFailedException) as exc_info:
            _load_batch(batch_transfer=batch_transfer, batch_num=0)

        assert "Unknown batch storage type" in str(exc_info.value)

    @patch("docpipe.core.orchestration.prefect.batch_subflow.pq.read_table")
    def test_load_batch_local_file_not_found(self, mock_read_table):
        """Test loading batch when local file doesn't exist."""
        mock_read_table.side_effect = FileNotFoundError("File not found")

        batch_transfer = {
            "type": "local",
            "ref": "/nonexistent/batch.parquet",
        }

        with pytest.raises(FlowExecutionFailedException) as exc_info:
            _load_batch(batch_transfer=batch_transfer, batch_num=0)

        assert "Failed to load batch" in str(exc_info.value)

    def test_load_batch_inline_invalid_data(self):
        """Test loading batch with invalid inline data."""
        batch_transfer = {
            "type": "inline",
            "data": {"invalid": "structure"},
        }

        with pytest.raises(FlowExecutionFailedException):
            _load_batch(batch_transfer=batch_transfer, batch_num=0)


class TestBatchSubflow:
    """Test batch_subflow function."""

    @patch("docpipe.core.orchestration.prefect.batch_subflow.set_session_info")
    @patch("docpipe.core.orchestration.prefect.batch_subflow.get_default_factory")
    @patch("docpipe.core.orchestration.prefect.batch_subflow.BatchManager.create_batch_data_access")
    @patch("docpipe.core.orchestration.prefect.batch_subflow._load_batch")
    def test_batch_subflow_success(
        self,
        mock_load_batch,
        mock_create_data_access,
        mock_get_factory,
        mock_set_session,
        sample_batch_table,
        sample_op_flow,
        sample_global_config,
    ):
        """Test successful batch subflow execution."""
        # Setup mocks
        mock_load_batch.return_value = sample_batch_table
        mock_data_access = Mock()
        mock_create_data_access.return_value = mock_data_access

        # Mock job management factory
        mock_factory = Mock()
        mock_stats_service = Mock()
        mock_run_manager = Mock()
        mock_factory.create_job_stats_service.return_value = mock_stats_service
        mock_factory.create_job_run_manager.return_value = mock_run_manager
        mock_get_factory.return_value = mock_factory

        # Mock orchestrator and engine
        with patch("docpipe.core.orchestration.prefect.batch_subflow.PythonOrchestrator") as mock_orch_class:
            mock_orchestrator = Mock()
            mock_engine = Mock()
            mock_orchestrator.flow_engine = mock_engine
            mock_orch_class.return_value = mock_orchestrator

            batch_transfer = {
                "type": "inline",
                "data": {"columns": ["id"], "data": [{"id": 1}]},
            }

            # Execute
            batch_subflow(
                job_run_id="run-123",
                batch_id="batch-456",
                batch_num=0,
                batch_transfer=batch_transfer,
                op_flow=sample_op_flow,
                global_config=sample_global_config,
            )

            # Verify
            mock_load_batch.assert_called_once()
            mock_create_data_access.assert_called_once()
            mock_orchestrator.initialize.assert_called_once()
            mock_engine.execute_operator_flow.assert_called_once()

    @patch("docpipe.core.orchestration.prefect.batch_subflow._load_batch")
    def test_batch_subflow_load_failure(
        self,
        mock_load_batch,
        sample_op_flow,
        sample_global_config,
    ):
        """Test batch subflow when batch loading fails."""
        mock_load_batch.side_effect = FlowExecutionFailedException("Load failed")

        batch_transfer = {"type": "inline", "data": {}}

        with pytest.raises(FlowExecutionFailedException) as exc_info:
            batch_subflow(
                job_run_id="run-123",
                batch_id="batch-456",
                batch_num=0,
                batch_transfer=batch_transfer,
                op_flow=sample_op_flow,
                global_config=sample_global_config,
            )

        assert "Load failed" in str(exc_info.value)

    @patch("docpipe.core.orchestration.prefect.batch_subflow.set_session_info")
    @patch("docpipe.core.orchestration.prefect.batch_subflow.get_default_factory")
    @patch("docpipe.core.orchestration.prefect.batch_subflow.BatchManager.create_batch_data_access")
    @patch("docpipe.core.orchestration.prefect.batch_subflow._load_batch")
    def test_batch_subflow_no_flow_engine(
        self,
        mock_load_batch,
        mock_create_data_access,
        mock_get_factory,
        mock_set_session,
        sample_batch_table,
        sample_op_flow,
        sample_global_config,
    ):
        """Test batch subflow when flow engine is not initialized."""
        mock_load_batch.return_value = sample_batch_table
        mock_data_access = Mock()
        mock_create_data_access.return_value = mock_data_access

        mock_factory = Mock()
        mock_stats_service = Mock()
        mock_run_manager = Mock()
        mock_factory.create_job_stats_service.return_value = mock_stats_service
        mock_factory.create_job_run_manager.return_value = mock_run_manager
        mock_get_factory.return_value = mock_factory

        with patch("docpipe.core.orchestration.prefect.batch_subflow.PythonOrchestrator") as mock_orch_class:
            mock_orchestrator = Mock()
            mock_orchestrator.flow_engine = None  # No engine
            mock_orch_class.return_value = mock_orchestrator

            batch_transfer = {"type": "inline", "data": {"columns": ["id"], "data": [{"id": 1}]}}

            with pytest.raises(FlowExecutionFailedException) as exc_info:
                batch_subflow(
                    job_run_id="run-123",
                    batch_id="batch-456",
                    batch_num=0,
                    batch_transfer=batch_transfer,
                    op_flow=sample_op_flow,
                    global_config=sample_global_config,
                )

            assert "Failed to initialize PrefectEngine" in str(exc_info.value)

    @patch("docpipe.core.orchestration.prefect.batch_subflow.set_session_info")
    @patch("docpipe.core.orchestration.prefect.batch_subflow.get_default_factory")
    @patch("docpipe.core.orchestration.prefect.batch_subflow.BatchManager.create_batch_data_access")
    @patch("docpipe.core.orchestration.prefect.batch_subflow._load_batch")
    def test_batch_subflow_execution_failure(
        self,
        mock_load_batch,
        mock_create_data_access,
        mock_get_factory,
        mock_set_session,
        sample_batch_table,
        sample_op_flow,
        sample_global_config,
    ):
        """Test batch subflow when operator execution fails."""
        mock_load_batch.return_value = sample_batch_table
        mock_data_access = Mock()
        mock_create_data_access.return_value = mock_data_access

        mock_factory = Mock()
        mock_stats_service = Mock()
        mock_run_manager = Mock()
        mock_factory.create_job_stats_service.return_value = mock_stats_service
        mock_factory.create_job_run_manager.return_value = mock_run_manager
        mock_get_factory.return_value = mock_factory

        with patch("docpipe.core.orchestration.prefect.batch_subflow.PythonOrchestrator") as mock_orch_class:
            mock_orchestrator = Mock()
            mock_engine = Mock()
            mock_engine.execute_operator_flow.side_effect = Exception("Execution failed")
            mock_orchestrator.flow_engine = mock_engine
            mock_orch_class.return_value = mock_orchestrator

            batch_transfer = {"type": "inline", "data": {"columns": ["id"], "data": [{"id": 1}]}}

            with pytest.raises(FlowExecutionFailedException) as exc_info:
                batch_subflow(
                    job_run_id="run-123",
                    batch_id="batch-456",
                    batch_num=0,
                    batch_transfer=batch_transfer,
                    op_flow=sample_op_flow,
                    global_config=sample_global_config,
                )

            assert "Batch 0 failed" in str(exc_info.value)

    @patch("docpipe.core.orchestration.prefect.batch_subflow.set_session_info")
    @patch("docpipe.core.orchestration.prefect.batch_subflow.get_default_factory")
    @patch("docpipe.core.orchestration.prefect.batch_subflow.BatchManager.create_batch_data_access")
    @patch("docpipe.core.orchestration.prefect.batch_subflow._load_batch")
    def test_batch_subflow_sets_context_id(
        self,
        mock_load_batch,
        mock_create_data_access,
        mock_get_factory,
        mock_set_session,
        sample_batch_table,
        sample_op_flow,
        sample_global_config,
    ):
        """Test that batch subflow sets context_id correctly."""
        mock_load_batch.return_value = sample_batch_table
        mock_data_access = Mock()
        mock_create_data_access.return_value = mock_data_access

        mock_factory = Mock()
        mock_stats_service = Mock()
        mock_run_manager = Mock()
        mock_factory.create_job_stats_service.return_value = mock_stats_service
        mock_factory.create_job_run_manager.return_value = mock_run_manager
        mock_get_factory.return_value = mock_factory

        with patch("docpipe.core.orchestration.prefect.batch_subflow.PythonOrchestrator") as mock_orch_class:
            mock_orchestrator = Mock()
            mock_engine = Mock()
            mock_orchestrator.flow_engine = mock_engine
            mock_orch_class.return_value = mock_orchestrator

            batch_transfer = {"type": "inline", "data": {"columns": ["id"], "data": [{"id": 1}]}}

            batch_subflow(
                job_run_id="run-123",
                batch_id="batch-456",
                batch_num=0,
                batch_transfer=batch_transfer,
                op_flow=sample_op_flow,
                global_config=sample_global_config,
            )

            # Verify context_id was set to job_id
            assert mock_orchestrator.context_id == sample_global_config[DocpipeConstants.JOB_ID]

    @patch("docpipe.core.orchestration.prefect.batch_subflow.set_session_info")
    @patch("docpipe.core.orchestration.prefect.batch_subflow.get_default_factory")
    @patch("docpipe.core.orchestration.prefect.batch_subflow.BatchManager.create_batch_data_access")
    @patch("docpipe.core.orchestration.prefect.batch_subflow._load_batch")
    def test_batch_subflow_updates_global_config(
        self,
        mock_load_batch,
        mock_create_data_access,
        mock_get_factory,
        mock_set_session,
        sample_batch_table,
        sample_op_flow,
        sample_global_config,
    ):
        """Test that batch subflow updates global config with batch info."""
        mock_load_batch.return_value = sample_batch_table
        mock_data_access = Mock()
        mock_create_data_access.return_value = mock_data_access

        mock_factory = Mock()
        mock_stats_service = Mock()
        mock_run_manager = Mock()
        mock_factory.create_job_stats_service.return_value = mock_stats_service
        mock_factory.create_job_run_manager.return_value = mock_run_manager
        mock_get_factory.return_value = mock_factory

        with patch("docpipe.core.orchestration.prefect.batch_subflow.PythonOrchestrator") as mock_orch_class:
            mock_orchestrator = Mock()
            mock_engine = Mock()
            mock_orchestrator.flow_engine = mock_engine
            mock_orch_class.return_value = mock_orchestrator

            batch_transfer = {"type": "inline", "data": {"columns": ["id"], "data": [{"id": 1}]}}

            batch_subflow(
                job_run_id="run-123",
                batch_id="batch-456",
                batch_num=5,
                batch_transfer=batch_transfer,
                op_flow=sample_op_flow,
                global_config=sample_global_config,
            )

            # Verify execute_operator_flow was called with updated config
            call_args = mock_engine.execute_operator_flow.call_args
            config = call_args[1]["global_config"]
            assert config[DocpipeConstants.BATCH_ID] == "batch-456"
            assert config[DocpipeConstants.BATCH_NUM] == 5
            assert config[DocpipeConstants.JOB_RUN_ID] == "run-123"
