"""Unit tests for prefect_engine module (BatchFuture, AbstractFlowEngine, PrefectEngine helpers)."""

import os
from unittest.mock import MagicMock, Mock, patch

import pytest

from docpipe.core.orchestration.prefect.domain.models import (
    BatchStorageType,
    BatchStrategyConstants,
    ExecutionMode,
    ExecutionStrategyType,
    WorkPoolType,
)
from docpipe.core.orchestration.prefect.prefect_engine import (
    BatchFuture,
    ExecuteStepResults,
)


@pytest.mark.unit
class TestBatchFuture:
    def test_describe_state_with_full_state(self):
        mock_future = Mock()
        mock_future.state.is_completed.return_value = True
        mock_future.state.is_failed.return_value = False
        mock_future.state.is_crashed.return_value = False
        mock_future.state.is_cancelled.return_value = False
        mock_future.state.type.value = "COMPLETED"
        mock_future.state.name = "Completed"

        bf = BatchFuture(batch_id="b-1", batch_num=1, future=mock_future)
        desc = bf.describe_state()

        assert "is_completed=True" in desc
        assert "is_failed=False" in desc
        assert "COMPLETED" in desc
        assert "Completed" in desc

    def test_describe_state_state_exception_handled(self):
        mock_future = Mock()
        mock_future.state.is_completed.side_effect = RuntimeError("state error")

        bf = BatchFuture(batch_id="b-1", batch_num=1, future=mock_future)
        desc = bf.describe_state()

        assert "state_unavailable" in desc

    def test_describe_state_with_wrapped_future(self):
        mock_inner = Mock()
        mock_inner.done.return_value = True
        mock_inner.cancelled.return_value = False
        mock_inner.running.return_value = False

        mock_future = Mock()
        mock_future.state.is_completed.return_value = True
        mock_future.state.is_failed.return_value = False
        mock_future.state.is_crashed.return_value = False
        mock_future.state.is_cancelled.return_value = False
        mock_future.state.type.value = "COMPLETED"
        mock_future.state.name = "Completed"
        mock_future._wrapped_future = mock_inner

        bf = BatchFuture(batch_id="b-2", batch_num=2, future=mock_future)
        desc = bf.describe_state()

        assert "wrapped_done=True" in desc
        assert "wrapped_cancelled=False" in desc
        assert "wrapped_running=False" in desc

    def test_describe_state_wrapped_future_exception_handled(self):
        mock_inner = Mock()
        mock_inner.done.side_effect = RuntimeError("wrapped error")

        mock_future = Mock()
        mock_future.state.is_completed.return_value = False
        mock_future.state.is_failed.return_value = True
        mock_future.state.is_crashed.return_value = False
        mock_future.state.is_cancelled.return_value = False
        mock_future.state.type.value = "FAILED"
        mock_future.state.name = "Failed"
        mock_future._wrapped_future = mock_inner

        bf = BatchFuture(batch_id="b-3", batch_num=3, future=mock_future)
        desc = bf.describe_state()

        assert "wrapped_state_unavailable" in desc

    def test_describe_state_no_wrapped_future(self):
        mock_future_with_state = MagicMock()
        mock_future_with_state.state.is_completed.return_value = False
        mock_future_with_state.state.is_failed.return_value = False
        mock_future_with_state.state.is_crashed.return_value = False
        mock_future_with_state.state.is_cancelled.return_value = True
        mock_future_with_state.state.type.value = "CANCELLED"
        mock_future_with_state.state.name = "Cancelled"
        # No _wrapped_future attribute
        del mock_future_with_state._wrapped_future

        bf = BatchFuture(batch_id="b-4", batch_num=4, future=mock_future_with_state)
        desc = bf.describe_state()

        # Should not include wrapped_done
        assert "wrapped_done" not in desc

    def test_attributes_set_correctly(self):
        mock_future = Mock()
        bf = BatchFuture(batch_id="batch-xyz", batch_num=5, future=mock_future)
        assert bf.batch_id == "batch-xyz"
        assert bf.batch_num == 5
        assert bf.future is mock_future


@pytest.mark.unit
class TestExecuteStepResults:
    def test_init_stores_values(self):
        da = [Mock()]
        tables = [Mock()]
        meta = {"key": "val"}
        result = ExecuteStepResults(da, tables, meta)
        assert result.data_accesses is da
        assert result.tables is tables
        assert result.internal_metadata is meta


@pytest.mark.unit
class TestCollectFailedDocIds:
    def _make_engine(self, job_stats_service=None):
        """Create a minimal PrefectEngine-like object for testing _collect_failed_doc_ids."""
        from docpipe.core.orchestration.prefect.prefect_engine import PrefectEngine

        # We test via a manually constructed mock that has the method bound
        orchestrator = Mock()
        orchestrator.job_stats_service = job_stats_service

        engine = object.__new__(PrefectEngine)
        engine.orchestrator = orchestrator
        engine.job_run_id = "run-123"
        engine.logger = Mock()
        engine.common_log_arguments = {}
        return engine

    def test_no_job_stats_service_returns_empty(self):
        engine = self._make_engine(job_stats_service=None)
        result = engine._collect_failed_doc_ids()
        assert result == []

    def test_no_job_stats_returns_empty(self):
        mock_service = Mock()
        mock_service.get_job.return_value = None
        engine = self._make_engine(job_stats_service=mock_service)
        result = engine._collect_failed_doc_ids()
        assert result == []

    def test_job_stats_no_node_stats_returns_empty(self):
        mock_service = Mock()
        mock_job = Mock()
        mock_job.node_stats = None
        mock_service.get_job.return_value = mock_job
        engine = self._make_engine(job_stats_service=mock_service)
        result = engine._collect_failed_doc_ids()
        assert result == []

    def test_collects_failed_docs_from_object(self):
        mock_service = Mock()
        mock_job = Mock()
        node_stat = Mock()
        node_stat.failed_docs = ["doc1", "doc2"]
        mock_job.node_stats = {"node-1": node_stat}
        mock_service.get_job.return_value = mock_job
        engine = self._make_engine(job_stats_service=mock_service)
        result = engine._collect_failed_doc_ids()
        assert "doc1" in result
        assert "doc2" in result

    def test_collects_failed_docs_from_dict(self):
        mock_service = Mock()
        mock_job = Mock()
        node_stat = {"failed_docs": ["doc3", "doc4"]}
        mock_job.node_stats = {"node-1": node_stat}
        mock_service.get_job.return_value = mock_job
        engine = self._make_engine(job_stats_service=mock_service)
        result = engine._collect_failed_doc_ids()
        assert "doc3" in result
        assert "doc4" in result

    def test_node_stat_no_failed_docs_skipped(self):
        mock_service = Mock()
        mock_job = Mock()
        node_stat = Mock(spec=["other_attr"])  # no failed_docs
        mock_job.node_stats = {"node-1": node_stat}
        mock_service.get_job.return_value = mock_job
        engine = self._make_engine(job_stats_service=mock_service)
        result = engine._collect_failed_doc_ids()
        assert result == []

    def test_dict_node_stat_no_failed_docs_skipped(self):
        mock_service = Mock()
        mock_job = Mock()
        node_stat = {"other_key": "value"}
        mock_job.node_stats = {"node-1": node_stat}
        mock_service.get_job.return_value = mock_job
        engine = self._make_engine(job_stats_service=mock_service)
        result = engine._collect_failed_doc_ids()
        assert result == []


"""Tests for BatchStrategyConstants.get_inline_size_limit."""


@pytest.mark.unit
class TestBatchStrategyConstants:
    def test_default_limit_returned_when_no_env(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("prefect.settings.get_current_settings") as mock_settings:
                mock_settings.side_effect = Exception("no settings")
                limit = BatchStrategyConstants.get_inline_size_limit()
        assert limit == BatchStrategyConstants.DEFAULT_INLINE_SIZE_LIMIT_BYTES

    def test_env_var_overrides_default(self):
        from docpipe.core.constants import EnvironmentVariables

        env_key = EnvironmentVariables.PREFECT_SERVER_API_MAX_PARAMETER_SIZE
        with patch.dict(os.environ, {env_key: "1048576"}):
            with patch("prefect.settings.get_current_settings") as mock_settings:
                mock_settings.side_effect = Exception("no prefect settings")
                limit = BatchStrategyConstants.get_inline_size_limit()
        assert limit == 1048576

    def test_invalid_env_var_falls_back_to_default(self):
        from docpipe.core.constants import EnvironmentVariables

        env_key = EnvironmentVariables.PREFECT_SERVER_API_MAX_PARAMETER_SIZE
        with patch.dict(os.environ, {env_key: "not_a_number"}):
            with patch("prefect.settings.get_current_settings") as mock_settings:
                mock_settings.side_effect = Exception("no settings")
                limit = BatchStrategyConstants.get_inline_size_limit()
        assert limit == BatchStrategyConstants.DEFAULT_INLINE_SIZE_LIMIT_BYTES

    def test_prefect_settings_used_when_available(self):
        mock_settings = MagicMock()
        mock_settings.server.api.max_parameter_size = 2097152  # 2MB
        with patch("prefect.settings.get_current_settings", return_value=mock_settings):
            limit = BatchStrategyConstants.get_inline_size_limit()
        assert limit == 2097152

    def test_prefect_settings_negative_value_falls_back(self):
        mock_settings = MagicMock()
        mock_settings.server.api.max_parameter_size = -1
        with patch("prefect.settings.get_current_settings", return_value=mock_settings):
            with patch.dict(os.environ, {}, clear=True):
                limit = BatchStrategyConstants.get_inline_size_limit()
        assert limit == BatchStrategyConstants.DEFAULT_INLINE_SIZE_LIMIT_BYTES


@pytest.mark.unit
class TestEnumValues:
    def test_execution_strategy_values(self):
        assert ExecutionStrategyType.THREAD_POOL == "thread-pool"
        assert ExecutionStrategyType.WORK_POOL_PROCESS == "work-pool-process"
        assert ExecutionStrategyType.WORK_POOL_DOCKER == "work-pool-docker"

    def test_execution_mode_values(self):
        assert ExecutionMode.LOCAL == "local"
        assert ExecutionMode.DISTRIBUTED == "distributed"

    def test_work_pool_type_values(self):
        assert WorkPoolType.PROCESS == "process"
        assert WorkPoolType.DOCKER == "docker"

    def test_batch_storage_type_values(self):
        assert BatchStorageType.INLINE == "inline"
        assert BatchStorageType.LOCAL == "local"
        assert BatchStorageType.S3 == "s3"
