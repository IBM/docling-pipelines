"""
Unit tests for WorkPoolAdapter.

Tests cover:
- Initialization and configuration validation
- Batch execution and transfer methods
- Error handling and edge cases
- S3, local, and inline storage modes
"""

from unittest.mock import MagicMock, Mock, patch

import pyarrow as pa
import pytest

from docpipe.core.orchestration.batch_manager import BatchInfo
from docpipe.core.orchestration.prefect.adapters.work_pool_adapter import WorkPoolAdapter
from docpipe.core.orchestration.prefect.domain.models import (
    BatchStorageType,
    BatchStrategyConstants,
)
from docpipe.exceptions.docpipe_exceptions import FlowExecutionFailedException


@pytest.fixture
def mock_prefect_engine():
    """Create mock Prefect engine."""
    engine = Mock()
    engine.logger = Mock()
    return engine


@pytest.fixture
def mock_batch_manager():
    """Create mock batch manager."""
    return Mock()


@pytest.fixture
def sample_batch_table():
    """Create sample PyArrow table for testing."""
    return pa.table({"col1": [1, 2, 3], "col2": ["a", "b", "c"]})


@pytest.fixture
def sample_batch_info(sample_batch_table):
    """Create sample BatchInfo."""
    return BatchInfo(batch_id="batch-123", batch_num=0, table=sample_batch_table)


@pytest.fixture
def base_config():
    """Base configuration for work pool."""
    return {
        "type": "process",
        "work_pool_name": "test-pool",
        "deployment_name": "test-deployment",
        "batch_storage": {"type": "inline"},
    }


class TestWorkPoolAdapterInitialization:
    """Test WorkPoolAdapter initialization and validation."""

    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._validate_prefect_connection")
    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._ensure_deployment_exists")
    def test_init_with_valid_config(
        self, mock_ensure_deployment, mock_validate, base_config, mock_prefect_engine, mock_batch_manager
    ):
        """Test initialization with valid configuration."""
        adapter = WorkPoolAdapter(
            work_pool_config=base_config, prefect_engine=mock_prefect_engine, batch_manager=mock_batch_manager
        )

        assert adapter.work_pool_name == "test-pool"
        assert adapter.deployment_name == "test-deployment"
        assert adapter.work_pool_type == "process"
        assert adapter.batch_storage_type == BatchStorageType.INLINE
        mock_validate.assert_called_once()
        mock_ensure_deployment.assert_called_once()

    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._validate_prefect_connection")
    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._ensure_deployment_exists")
    def test_init_missing_work_pool_name(
        self, mock_ensure_deployment, mock_validate, mock_prefect_engine, mock_batch_manager
    ):
        """Test initialization fails without work_pool_name."""
        config = {"type": "process", "batch_storage": {"type": "inline"}}

        with pytest.raises(ValueError, match="work_pool_name is required"):
            WorkPoolAdapter(
                work_pool_config=config, prefect_engine=mock_prefect_engine, batch_manager=mock_batch_manager
            )

    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._validate_prefect_connection")
    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._ensure_deployment_exists")
    def test_init_local_storage_missing_path(
        self, mock_ensure_deployment, mock_validate, mock_prefect_engine, mock_batch_manager
    ):
        """Test initialization fails for local storage without path."""
        config = {"work_pool_name": "test-pool", "batch_storage": {"type": "local"}}

        with pytest.raises(ValueError, match=r"batch_storage\.path is required"):
            WorkPoolAdapter(
                work_pool_config=config, prefect_engine=mock_prefect_engine, batch_manager=mock_batch_manager
            )

    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._validate_prefect_connection")
    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._ensure_deployment_exists")
    def test_init_s3_storage_missing_bucket(
        self, mock_ensure_deployment, mock_validate, mock_prefect_engine, mock_batch_manager
    ):
        """Test initialization fails for S3 storage without bucket."""
        config = {
            "work_pool_name": "test-pool",
            "batch_storage": {"type": "s3", "access_key": "key", "secret_key": "secret"},  # pragma: allowlist secret
        }

        with pytest.raises(ValueError, match=r"batch_storage\.bucket is required"):
            WorkPoolAdapter(
                work_pool_config=config, prefect_engine=mock_prefect_engine, batch_manager=mock_batch_manager
            )

    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._validate_prefect_connection")
    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._ensure_deployment_exists")
    def test_init_s3_storage_missing_credentials(
        self, mock_ensure_deployment, mock_validate, mock_prefect_engine, mock_batch_manager
    ):
        """Test initialization fails for S3 storage without credentials."""
        config = {"work_pool_name": "test-pool", "batch_storage": {"type": "s3", "bucket": "test-bucket"}}

        with pytest.raises(ValueError, match="S3 credentials are required"):
            WorkPoolAdapter(
                work_pool_config=config, prefect_engine=mock_prefect_engine, batch_manager=mock_batch_manager
            )

    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._validate_prefect_connection")
    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._ensure_deployment_exists")
    def test_init_with_default_deployment_name(
        self, mock_ensure_deployment, mock_validate, mock_prefect_engine, mock_batch_manager
    ):
        """Test initialization uses default deployment name."""
        config = {"work_pool_name": "test-pool", "batch_storage": {"type": "inline"}}

        adapter = WorkPoolAdapter(
            work_pool_config=config, prefect_engine=mock_prefect_engine, batch_manager=mock_batch_manager
        )

        assert adapter.deployment_name == BatchStrategyConstants.DEFAULT_DEPLOYMENT_NAME

    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._validate_prefect_connection")
    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._ensure_deployment_exists")
    def test_init_with_s3_credentials_aliases(
        self, mock_ensure_deployment, mock_validate, mock_prefect_engine, mock_batch_manager
    ):
        """Test S3 credentials support both standard and alias names."""
        config = {
            "work_pool_name": "test-pool",
            "batch_storage": {
                "type": "s3",
                "bucket": "test-bucket",
                "access_key_id": "key-id",
                "secret_access_key": "secret",  # pragma: allowlist secret
            },
        }

        adapter = WorkPoolAdapter(
            work_pool_config=config, prefect_engine=mock_prefect_engine, batch_manager=mock_batch_manager
        )

        assert adapter.s3_access_key == "key-id"
        assert adapter.s3_secret_key == "secret"  # pragma: allowlist secret


class TestBatchTransferMethods:
    """Test batch data transfer methods."""

    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._validate_prefect_connection")
    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._ensure_deployment_exists")
    def test_transfer_batch_inline(
        self,
        mock_ensure_deployment,
        mock_validate,
        base_config,
        mock_prefect_engine,
        mock_batch_manager,
        sample_batch_table,
    ):
        """Test inline batch transfer."""
        adapter = WorkPoolAdapter(
            work_pool_config=base_config, prefect_engine=mock_prefect_engine, batch_manager=mock_batch_manager
        )

        result = adapter._transfer_batch(batch_table=sample_batch_table, batch_num=0, job_run_id="job-123")

        assert result["type"] == "inline"
        assert "data" in result
        assert isinstance(result["data"], dict)

    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._validate_prefect_connection")
    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._ensure_deployment_exists")
    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._transfer_batch_local")
    def test_transfer_batch_local(
        self,
        mock_transfer_local,
        mock_ensure_deployment,
        mock_validate,
        mock_prefect_engine,
        mock_batch_manager,
        sample_batch_table,
    ):
        """Test local filesystem batch transfer."""
        config = {"work_pool_name": "test-pool", "batch_storage": {"type": "local", "path": "/tmp/batches"}}

        mock_transfer_local.return_value = {"type": "local", "ref": "/tmp/batches/job-123/batch-0.parquet"}

        adapter = WorkPoolAdapter(
            work_pool_config=config, prefect_engine=mock_prefect_engine, batch_manager=mock_batch_manager
        )

        result = adapter._transfer_batch(batch_table=sample_batch_table, batch_num=0, job_run_id="job-123")

        assert result["type"] == "local"
        assert "ref" in result
        mock_transfer_local.assert_called_once()

    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._validate_prefect_connection")
    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._ensure_deployment_exists")
    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._transfer_batch_s3")
    def test_transfer_batch_s3(
        self,
        mock_transfer_s3,
        mock_ensure_deployment,
        mock_validate,
        mock_prefect_engine,
        mock_batch_manager,
        sample_batch_table,
    ):
        """Test S3 batch transfer."""
        config = {
            "work_pool_name": "test-pool",
            "batch_storage": {
                "type": "s3",
                "bucket": "test-bucket",
                "access_key": "key",
                "secret_key": "secret",  # pragma: allowlist secret
            },
        }

        mock_transfer_s3.return_value = {"type": "s3", "ref": "s3://test-bucket/tmp/batches/job-123/batch-0.parquet"}

        adapter = WorkPoolAdapter(
            work_pool_config=config, prefect_engine=mock_prefect_engine, batch_manager=mock_batch_manager
        )

        result = adapter._transfer_batch(batch_table=sample_batch_table, batch_num=0, job_run_id="job-123")

        assert result["type"] == "s3"
        assert "ref" in result
        mock_transfer_s3.assert_called_once()

    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._validate_prefect_connection")
    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._ensure_deployment_exists")
    def test_transfer_batch_inline_size_warning(
        self, mock_ensure_deployment, mock_validate, base_config, mock_prefect_engine, mock_batch_manager
    ):
        """Test inline transfer logs warning for large batches."""
        # Create table that exceeds warning threshold (80% of 512KB = ~410KB) but not the limit
        # Need to account for JSON overhead, so use smaller data
        # Each row is ~35KB, so 10 rows = ~350KB which should trigger warning without exceeding limit
        large_table = pa.table({"col": [b"x" * 35000 for _ in range(10)]})

        adapter = WorkPoolAdapter(
            work_pool_config=base_config, prefect_engine=mock_prefect_engine, batch_manager=mock_batch_manager
        )

        result = adapter._transfer_batch_inline(batch_table=large_table, batch_num=0, job_run_id="job-123")

        assert result["type"] == "inline"
        # Should log warning for size approaching limit
        mock_prefect_engine.logger.warning.assert_called()

    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._validate_prefect_connection")
    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._ensure_deployment_exists")
    @patch("pyarrow.parquet.write_table", side_effect=OSError("Permission denied"))
    def test_transfer_batch_local_error(
        self,
        mock_write_table,
        mock_ensure_deployment,
        mock_validate,
        mock_prefect_engine,
        mock_batch_manager,
        sample_batch_table,
    ):
        """Test local transfer handles file system errors."""
        config = {"work_pool_name": "test-pool", "batch_storage": {"type": "local", "path": "/tmp/batches"}}

        adapter = WorkPoolAdapter(
            work_pool_config=config, prefect_engine=mock_prefect_engine, batch_manager=mock_batch_manager
        )

        with pytest.raises(FlowExecutionFailedException, match="Failed to write batch"):
            adapter._transfer_batch_local(batch_table=sample_batch_table, batch_num=0, job_run_id="job-123")


class TestBatchExecution:
    """Test batch execution methods."""

    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._validate_prefect_connection")
    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._ensure_deployment_exists")
    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.asyncio.run")
    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._cleanup_batch_storage")
    def test_execute_batches_success(
        self,
        mock_cleanup,
        mock_asyncio_run,
        mock_ensure_deployment,
        mock_validate,
        base_config,
        mock_prefect_engine,
        mock_batch_manager,
        sample_batch_info,
    ):
        """Test successful batch execution."""
        adapter = WorkPoolAdapter(
            work_pool_config=base_config, prefect_engine=mock_prefect_engine, batch_manager=mock_batch_manager
        )

        batches = [sample_batch_info]
        op_flow = [{"operator": "test"}]
        global_config = {"flow_definition": {"name": "test-flow"}}

        adapter.execute_batches(batches=batches, op_flow=op_flow, global_config=global_config, job_run_id="job-123")

        mock_asyncio_run.assert_called_once()
        mock_cleanup.assert_called_once_with(job_run_id="job-123")
        mock_prefect_engine.logger.info.assert_called()

    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._validate_prefect_connection")
    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._ensure_deployment_exists")
    def test_get_strategy_name(
        self, mock_ensure_deployment, mock_validate, base_config, mock_prefect_engine, mock_batch_manager
    ):
        """Test strategy name retrieval."""
        adapter = WorkPoolAdapter(
            work_pool_config=base_config, prefect_engine=mock_prefect_engine, batch_manager=mock_batch_manager
        )

        # Strategy name is "work-pool-{type}" where type defaults to "process"
        assert adapter.get_strategy_name() == "work-pool-process"


class TestPrefectValidation:
    """Test Prefect connection validation."""

    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._ensure_deployment_exists")
    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.get_client")
    def test_validate_prefect_connection_success(
        self, mock_get_client, mock_ensure_deployment, base_config, mock_prefect_engine, mock_batch_manager
    ):
        """Test successful Prefect connection validation."""
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = None
        mock_client.api_healthcheck.return_value = None  # None means healthy
        mock_get_client.return_value = mock_client

        adapter = WorkPoolAdapter(
            work_pool_config=base_config, prefect_engine=mock_prefect_engine, batch_manager=mock_batch_manager
        )

        # Should not raise
        adapter._validate_prefect_connection()

    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._ensure_deployment_exists")
    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.get_client")
    def test_validate_prefect_connection_failure(
        self, mock_get_client, mock_ensure_deployment, base_config, mock_prefect_engine, mock_batch_manager
    ):
        """Test Prefect connection validation failure."""
        mock_get_client.side_effect = Exception("Connection refused")

        with pytest.raises(ValueError, match="Cannot connect to Prefect Server"):
            WorkPoolAdapter(
                work_pool_config=base_config, prefect_engine=mock_prefect_engine, batch_manager=mock_batch_manager
            )


class TestDeploymentManagement:
    """Test deployment creation and management."""

    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._validate_prefect_connection")
    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._ensure_deployment_exists")
    def test_ensure_deployment_exists_creates_new(
        self, mock_ensure_deployment, mock_validate, base_config, mock_prefect_engine, mock_batch_manager
    ):
        """Test deployment creation when it doesn't exist."""
        # Mock the _ensure_deployment_exists to track it was called
        mock_ensure_deployment.return_value = None

        _ = WorkPoolAdapter(
            work_pool_config=base_config, prefect_engine=mock_prefect_engine, batch_manager=mock_batch_manager
        )

        # Verify _ensure_deployment_exists was called during initialization
        mock_ensure_deployment.assert_called_once()

    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._validate_prefect_connection")
    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._ensure_deployment_exists")
    def test_ensure_deployment_exists_uses_existing(
        self, mock_ensure_deployment, mock_validate, base_config, mock_prefect_engine, mock_batch_manager
    ):
        """Test deployment reuse when it already exists."""
        # Mock the _ensure_deployment_exists to track it was called
        mock_ensure_deployment.return_value = None

        _ = WorkPoolAdapter(
            work_pool_config=base_config, prefect_engine=mock_prefect_engine, batch_manager=mock_batch_manager
        )

        # Verify _ensure_deployment_exists was called during initialization
        mock_ensure_deployment.assert_called_once()


class TestCleanup:
    """Test cleanup operations."""

    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._validate_prefect_connection")
    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._ensure_deployment_exists")
    @patch("shutil.rmtree")
    def test_cleanup_batch_storage_local(
        self, mock_rmtree, mock_ensure_deployment, mock_validate, mock_prefect_engine, mock_batch_manager
    ):
        """Test cleanup of local batch storage."""
        config = {"work_pool_name": "test-pool", "batch_storage": {"type": "local", "path": "/tmp/batches"}}

        adapter = WorkPoolAdapter(
            work_pool_config=config, prefect_engine=mock_prefect_engine, batch_manager=mock_batch_manager
        )

        adapter._cleanup_batch_storage(job_run_id="job-123")

        mock_rmtree.assert_called_once()

    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._validate_prefect_connection")
    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._ensure_deployment_exists")
    def test_cleanup_batch_storage_inline_noop(
        self, mock_ensure_deployment, mock_validate, base_config, mock_prefect_engine, mock_batch_manager
    ):
        """Test cleanup is no-op for inline storage."""
        adapter = WorkPoolAdapter(
            work_pool_config=base_config, prefect_engine=mock_prefect_engine, batch_manager=mock_batch_manager
        )

        # Should not raise
        adapter._cleanup_batch_storage(job_run_id="job-123")

    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._validate_prefect_connection")
    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._ensure_deployment_exists")
    @patch("shutil.rmtree", side_effect=OSError("Permission denied"))
    def test_cleanup_batch_storage_error_handling(
        self, mock_rmtree, mock_ensure_deployment, mock_validate, mock_prefect_engine, mock_batch_manager
    ):
        """Test cleanup handles errors gracefully."""
        config = {"work_pool_name": "test-pool", "batch_storage": {"type": "local", "path": "/tmp/batches"}}

        adapter = WorkPoolAdapter(
            work_pool_config=config, prefect_engine=mock_prefect_engine, batch_manager=mock_batch_manager
        )

        # Should not raise, just log warning
        adapter._cleanup_batch_storage(job_run_id="job-123")
        mock_prefect_engine.logger.warning.assert_called()


class TestErrorHandling:
    """Test error handling and failure scenarios."""

    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._validate_prefect_connection")
    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._ensure_deployment_exists")
    def test_raise_failure_with_details(
        self, mock_ensure_deployment, mock_validate, base_config, mock_prefect_engine, mock_batch_manager
    ):
        """Test failure raising with detailed error information."""
        adapter = WorkPoolAdapter(
            work_pool_config=base_config, prefect_engine=mock_prefect_engine, batch_manager=mock_batch_manager
        )

        failed_info = [
            {"batch_num": 0, "run_id": "run-1", "message": "Error 1"},
            {"batch_num": 1, "run_id": "run-2", "message": "Error 2"},
        ]

        with pytest.raises(FlowExecutionFailedException, match=r"Failed: 2.*Completed: 3.*Total: 5"):
            adapter._raise_failure(failed_info=failed_info, completed_count=3, total_count=5)


class TestJobManagementConfig:
    """Test job management configuration resolution."""

    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._validate_prefect_connection")
    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._ensure_deployment_exists")
    def test_resolve_job_management_config_from_env(
        self, mock_ensure_deployment, mock_validate, base_config, mock_prefect_engine, mock_batch_manager
    ):
        """Test job management config resolution from environment."""
        import os
        from unittest.mock import patch

        with patch.dict(os.environ, {"DOCPIPE_CONFIG_PATH": "/custom/path/config.json"}):
            adapter = WorkPoolAdapter(
                work_pool_config=base_config, prefect_engine=mock_prefect_engine, batch_manager=mock_batch_manager
            )

            config_path = adapter._resolve_job_management_config_path()
            assert str(config_path) == "/custom/path/config.json"

    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._validate_prefect_connection")
    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._ensure_deployment_exists")
    @patch.dict("os.environ", {}, clear=True)
    def test_resolve_job_management_config_default(
        self, mock_ensure_deployment, mock_validate, base_config, mock_prefect_engine, mock_batch_manager
    ):
        """Test job management config uses default when env not set."""
        adapter = WorkPoolAdapter(
            work_pool_config=base_config, prefect_engine=mock_prefect_engine, batch_manager=mock_batch_manager
        )

        config_path = adapter._resolve_job_management_config_path()
        # Returns a Path object pointing to default location
        assert config_path is not None
        assert "docling-pipelines-config.yaml" in str(config_path)

    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._validate_prefect_connection")
    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._ensure_deployment_exists")
    @patch(
        "docpipe.core.job_management.adapters.config.job_management_factory.JobManagementFactory.from_default_sources"
    )
    def test_get_effective_job_management_env(
        self, mock_factory, mock_ensure_deployment, mock_validate, base_config, mock_prefect_engine, mock_batch_manager
    ):
        """Test effective job management environment retrieval."""
        mock_instance = Mock()
        mock_instance.resolve_worker_env.return_value = {"KEY": "value"}
        mock_factory.return_value = mock_instance

        adapter = WorkPoolAdapter(
            work_pool_config=base_config, prefect_engine=mock_prefect_engine, batch_manager=mock_batch_manager
        )

        env = adapter._get_effective_job_management_env()
        assert "KEY" in env
        assert env["KEY"] == "value"


class TestContainerEnvironment:
    """Test container environment building."""

    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._validate_prefect_connection")
    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._ensure_deployment_exists")
    def test_build_container_env_basic(
        self, mock_ensure_deployment, mock_validate, base_config, mock_prefect_engine, mock_batch_manager
    ):
        """Test basic container environment building."""
        adapter = WorkPoolAdapter(
            work_pool_config=base_config, prefect_engine=mock_prefect_engine, batch_manager=mock_batch_manager
        )

        base_env = {"EXISTING_VAR": "value"}
        required_env = {
            "PREFECT_API_URL": "https://prefect-server:4200/api",
            "OLLAMA_HOST": "https://ollama-server:11434",
        }
        with patch.dict("os.environ", required_env):
            env = adapter._build_container_env(base_env=base_env, deployment_path="/app")

        assert "EXISTING_VAR" in env
        assert env["EXISTING_VAR"] == "value"
        assert "PYTHONPATH" in env

    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._validate_prefect_connection")
    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._ensure_deployment_exists")
    @patch(
        "docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._get_effective_job_management_env"
    )
    def test_build_container_env_with_job_management(
        self,
        mock_get_env,
        mock_ensure_deployment,
        mock_validate,
        base_config,
        mock_prefect_engine,
        mock_batch_manager,
    ):
        """Test container environment includes job management vars."""
        mock_get_env.return_value = {"JOB_VAR": "job_value"}

        adapter = WorkPoolAdapter(
            work_pool_config=base_config, prefect_engine=mock_prefect_engine, batch_manager=mock_batch_manager
        )

        required_env = {
            "PREFECT_API_URL": "https://prefect-server:4200/api",
            "OLLAMA_HOST": "https://ollama-server:11434",
        }
        with patch.dict("os.environ", required_env):
            env = adapter._build_container_env(base_env={}, deployment_path="/app")

        assert "JOB_VAR" in env
        assert env["JOB_VAR"] == "job_value"


class TestJobVariables:
    """Test job variables building."""

    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._validate_prefect_connection")
    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._ensure_deployment_exists")
    def test_build_job_variables_process(
        self, mock_ensure_deployment, mock_validate, mock_prefect_engine, mock_batch_manager
    ):
        """Test job variables for process work pool."""
        config = {"work_pool_name": "test-pool", "type": "process", "batch_storage": {"type": "inline"}}

        adapter = WorkPoolAdapter(
            work_pool_config=config, prefect_engine=mock_prefect_engine, batch_manager=mock_batch_manager
        )

        required_env = {
            "PREFECT_API_URL": "https://prefect-server:4200/api",
            "OLLAMA_HOST": "https://ollama-server:11434",
        }
        with patch.dict("os.environ", required_env):
            job_vars = adapter._build_job_variables()

        assert job_vars is not None
        assert isinstance(job_vars, dict)

    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._validate_prefect_connection")
    @patch("docpipe.core.orchestration.prefect.adapters.work_pool_adapter.WorkPoolAdapter._ensure_deployment_exists")
    def test_build_job_variables_docker(
        self, mock_ensure_deployment, mock_validate, mock_prefect_engine, mock_batch_manager
    ):
        """Test job variables for docker work pool."""
        config = {
            "work_pool_name": "test-pool",
            "type": "docker",
            "batch_storage": {"type": "inline"},
            "image": "test-image:latest",
        }

        adapter = WorkPoolAdapter(
            work_pool_config=config, prefect_engine=mock_prefect_engine, batch_manager=mock_batch_manager
        )

        required_env = {
            "PREFECT_API_URL": "https://prefect-server:4200/api",
            "OLLAMA_HOST": "https://ollama-server:11434",
        }
        with patch.dict("os.environ", required_env):
            job_vars = adapter._build_job_variables()

        assert job_vars is not None
        assert isinstance(job_vars, dict)
