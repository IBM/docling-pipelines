"""
Integration tests for batch context propagation through executor layer.

Verifies that batch_id and batch_num flow correctly from global_config
through the executor to start_node_execution and complete_node_execution calls.
"""

from unittest.mock import Mock, patch

import pyarrow as pa
import pytest

from docpipe.core.constants.constants import DocpipeConstants, ExecutionStatus
from docpipe.core.constants.operator_constants import OperatorConstants


class TestBatchContextExecutorIntegration:
    """Test batch context propagation through executor layer."""

    @pytest.fixture
    def mock_job_stats_service(self):
        """Create a mock job stats service."""
        service = Mock()
        service.start_node_execution = Mock()
        service.complete_node_execution = Mock()
        return service

    @pytest.fixture
    def sample_table(self):
        """Create a sample PyArrow table for testing."""
        return pa.table({"id": ["doc1", "doc2", "doc3"], "content": ["text1", "text2", "text3"]})

    @pytest.fixture
    def executor_params_with_batch(self):
        """Create executor params with batch context."""
        return {
            OperatorConstants.Columns.NAME: "test_node",
            OperatorConstants.Columns.ID: "node-123",
            DocpipeConstants.JOB_ID: "job-456",
            DocpipeConstants.JOB_RUN_ID: "run-789",
            DocpipeConstants.BATCH_ID: "batch-uuid-abc",
            DocpipeConstants.BATCH_NUM: 7,
        }

    @pytest.fixture
    def executor_params_without_batch(self):
        """Create executor params without batch context."""
        return {
            OperatorConstants.Columns.NAME: "test_node",
            OperatorConstants.Columns.ID: "node-123",
            DocpipeConstants.JOB_ID: "job-456",
            DocpipeConstants.JOB_RUN_ID: "run-789",
        }

    def test_set_default_node_stats_with_batch_context(
        self, mock_job_stats_service, executor_params_with_batch, sample_table
    ):
        """Test that set_default_node_stats passes batch context to start_node_execution."""
        from docpipe.core.orchestration.python.python_operator_executor import (
            PythonOperatorExecutor,
        )

        # Create executor with batch context in params
        executor = PythonOperatorExecutor(
            name="test_node",
            operator="noop",
            params=executor_params_with_batch,
            job_stats_service=mock_job_stats_service,
        )

        # Call set_default_node_stats
        executor.set_default_node_stats(tables=sample_table)

        # Verify start_node_execution was called with batch context
        mock_job_stats_service.start_node_execution.assert_called_once()
        call_kwargs = mock_job_stats_service.start_node_execution.call_args.kwargs

        assert call_kwargs["job_run_id"] == "run-789"
        assert call_kwargs["node_id"] == "node-123"
        assert call_kwargs["node_name"] == "test_node"
        assert call_kwargs["batch_id"] == "batch-uuid-abc"
        assert call_kwargs["batch_num"] == 7
        assert "total_docs" in call_kwargs

    def test_set_default_node_stats_without_batch_context(
        self, mock_job_stats_service, executor_params_without_batch, sample_table
    ):
        """Test that set_default_node_stats works without batch context."""
        from docpipe.core.orchestration.python.python_operator_executor import (
            PythonOperatorExecutor,
        )

        # Create executor without batch context
        executor = PythonOperatorExecutor(
            name="test_node",
            operator="noop",
            params=executor_params_without_batch,
            job_stats_service=mock_job_stats_service,
        )

        # Call set_default_node_stats
        executor.set_default_node_stats(tables=sample_table)

        # Verify start_node_execution was called without batch context
        mock_job_stats_service.start_node_execution.assert_called_once()
        call_kwargs = mock_job_stats_service.start_node_execution.call_args.kwargs

        assert call_kwargs["job_run_id"] == "run-789"
        assert call_kwargs["node_id"] == "node-123"
        assert call_kwargs["node_name"] == "test_node"
        assert call_kwargs["batch_id"] is None
        assert call_kwargs["batch_num"] is None

    def test_update_final_node_stats_with_batch_context(
        self, mock_job_stats_service, executor_params_with_batch, sample_table
    ):
        """Test that update_final_node_stats passes batch context to complete_node_execution."""
        from docpipe.core.orchestration.python.python_operator_executor import (
            PythonOperatorExecutor,
        )

        # Create executor with batch context
        executor = PythonOperatorExecutor(
            name="test_node",
            operator="noop",
            params=executor_params_with_batch,
            job_stats_service=mock_job_stats_service,
        )

        # Call update_final_node_stats
        metadata = {"node_status": ExecutionStatus.COMPLETED.value, "processed_docs": 3}
        executor.update_final_node_stats(tables=[sample_table], metadata=metadata)

        # Verify complete_node_execution was called with batch context
        mock_job_stats_service.complete_node_execution.assert_called_once()
        call_kwargs = mock_job_stats_service.complete_node_execution.call_args.kwargs

        assert call_kwargs["job_run_id"] == "run-789"
        assert call_kwargs["node_id"] == "node-123"
        assert call_kwargs["node_name"] == "test_node"
        assert call_kwargs["batch_id"] == "batch-uuid-abc"
        assert call_kwargs["batch_num"] == 7
        assert call_kwargs["node_status"] == ExecutionStatus.COMPLETED.value

    def test_update_final_node_stats_without_batch_context(
        self, mock_job_stats_service, executor_params_without_batch, sample_table
    ):
        """Test that update_final_node_stats works without batch context."""
        from docpipe.core.orchestration.python.python_operator_executor import (
            PythonOperatorExecutor,
        )

        # Create executor without batch context
        executor = PythonOperatorExecutor(
            name="test_node",
            operator="noop",
            params=executor_params_without_batch,
            job_stats_service=mock_job_stats_service,
        )

        # Call update_final_node_stats
        metadata = {"node_status": ExecutionStatus.COMPLETED.value, "processed_docs": 3}
        executor.update_final_node_stats(tables=[sample_table], metadata=metadata)

        # Verify complete_node_execution was called without batch context
        mock_job_stats_service.complete_node_execution.assert_called_once()
        call_kwargs = mock_job_stats_service.complete_node_execution.call_args.kwargs

        assert call_kwargs["job_run_id"] == "run-789"
        assert call_kwargs["node_id"] == "node-123"
        assert call_kwargs["node_name"] == "test_node"
        assert call_kwargs["batch_id"] is None
        assert call_kwargs["batch_num"] is None

    def test_batch_context_with_failed_docs(self, mock_job_stats_service, executor_params_with_batch, sample_table):
        """Test batch context propagation when node has failed documents."""
        from docpipe.core.orchestration.python.python_operator_executor import (
            PythonOperatorExecutor,
        )

        executor = PythonOperatorExecutor(
            name="test_node",
            operator="noop",
            params=executor_params_with_batch,
            job_stats_service=mock_job_stats_service,
        )

        # Metadata with failed docs
        metadata = {
            "node_status": ExecutionStatus.COMPLETED.value,
            "failed_docs": [{"id": "doc2"}],
            "processed_docs": 2,
        }
        executor.update_final_node_stats(tables=[sample_table], metadata=metadata)

        # Verify batch context is preserved even with failures
        call_kwargs = mock_job_stats_service.complete_node_execution.call_args.kwargs
        assert call_kwargs["batch_id"] == "batch-uuid-abc"
        assert call_kwargs["batch_num"] == 7
        assert len(call_kwargs["failed_docs"]) == 1
        assert call_kwargs["failed_docs"][0] == "doc2"

    def test_failed_docs_excluded_from_docs_completed(
        self, mock_job_stats_service, executor_params_with_batch, sample_table
    ):
        """Failed and skipped doc IDs must not appear in docs_completed (fixes 2/4 display bug)."""
        from docpipe.core.orchestration.python.python_operator_executor import PythonOperatorExecutor

        executor = PythonOperatorExecutor(
            name="test_node",
            operator="noop",
            params=executor_params_with_batch,
            job_stats_service=mock_job_stats_service,
        )

        # doc1=success, doc2=failed, doc3=skipped — all present in the output table
        metadata = {
            "node_status": ExecutionStatus.COMPLETED.value,
            "failed_docs": [{"id": "doc2"}],
            "skipped_docs": [{"id": "doc3"}],
            "processed_docs": 1,
        }
        executor.update_final_node_stats(tables=[sample_table], metadata=metadata)

        call_kwargs = mock_job_stats_service.complete_node_execution.call_args.kwargs
        assert call_kwargs["docs_completed"] == ["doc1"], "failed/skipped IDs must be excluded from docs_completed"
        assert call_kwargs["failed_docs"] == ["doc2"]
        assert call_kwargs["skipped_docs"] == ["doc3"]

    def test_batch_context_with_dict_tables(self, mock_job_stats_service, executor_params_with_batch, sample_table):
        """Test batch context with dict of tables (branching scenario)."""
        from docpipe.core.orchestration.python.python_operator_executor import (
            PythonOperatorExecutor,
        )

        executor = PythonOperatorExecutor(
            name="test_node",
            operator="noop",
            params=executor_params_with_batch,
            job_stats_service=mock_job_stats_service,
        )

        # Dict of tables for branching
        tables_dict = {"branch_a": sample_table, "branch_b": sample_table}

        # Call set_default_node_stats with dict
        executor.set_default_node_stats(tables=tables_dict)

        # Verify batch context is passed
        call_kwargs = mock_job_stats_service.start_node_execution.call_args.kwargs
        assert call_kwargs["batch_id"] == "batch-uuid-abc"
        assert call_kwargs["batch_num"] == 7


class TestBatchStateTransitions:
    """Test state transitions (pending/running/completed/failed) with batch context."""

    @pytest.fixture
    def mock_job_stats_service(self):
        """Create a mock job stats service."""
        service = Mock()
        service.start_node_execution = Mock()
        service.complete_node_execution = Mock()
        service.fail_node_execution = Mock()
        return service

    @pytest.fixture
    def sample_table(self):
        """Create a sample PyArrow table for testing."""
        return pa.table({"id": ["doc1", "doc2"], "content": ["text1", "text2"]})

    def test_pending_to_running_transition_with_batch_context(self, mock_job_stats_service, sample_table):
        """Test transition from PENDING to RUNNING state with batch context."""
        from docpipe.core.orchestration.python.python_operator_executor import (
            PythonOperatorExecutor,
        )

        executor_params = {
            OperatorConstants.Columns.NAME: "test_node",
            OperatorConstants.Columns.ID: "node-123",
            DocpipeConstants.JOB_ID: "job-456",
            DocpipeConstants.JOB_RUN_ID: "run-789",
            DocpipeConstants.BATCH_ID: "batch-uuid-pending",
            DocpipeConstants.BATCH_NUM: 1,
        }

        executor = PythonOperatorExecutor(
            name="test_node",
            operator="noop",
            params=executor_params,
            job_stats_service=mock_job_stats_service,
        )

        # Call set_default_node_stats (PENDING -> RUNNING transition)
        executor.set_default_node_stats(tables=sample_table)

        # Verify start_node_execution was called with batch context
        mock_job_stats_service.start_node_execution.assert_called_once()
        call_kwargs = mock_job_stats_service.start_node_execution.call_args.kwargs

        assert call_kwargs["batch_id"] == "batch-uuid-pending"
        assert call_kwargs["batch_num"] == 1
        assert call_kwargs["node_id"] == "node-123"

    def test_running_to_completed_transition_with_batch_context(self, mock_job_stats_service, sample_table):
        """Test transition from RUNNING to COMPLETED state with batch context."""
        from docpipe.core.orchestration.python.python_operator_executor import (
            PythonOperatorExecutor,
        )

        executor_params = {
            OperatorConstants.Columns.NAME: "test_node",
            OperatorConstants.Columns.ID: "node-123",
            DocpipeConstants.JOB_ID: "job-456",
            DocpipeConstants.JOB_RUN_ID: "run-789",
            DocpipeConstants.BATCH_ID: "batch-uuid-running",
            DocpipeConstants.BATCH_NUM: 2,
        }

        executor = PythonOperatorExecutor(
            name="test_node",
            operator="noop",
            params=executor_params,
            job_stats_service=mock_job_stats_service,
        )

        # Call update_final_node_stats (RUNNING -> COMPLETED transition)
        metadata = {"node_status": ExecutionStatus.COMPLETED.value, "processed_docs": 2}
        executor.update_final_node_stats(tables=[sample_table], metadata=metadata)

        # Verify complete_node_execution was called with batch context
        mock_job_stats_service.complete_node_execution.assert_called_once()
        call_kwargs = mock_job_stats_service.complete_node_execution.call_args.kwargs

        assert call_kwargs["batch_id"] == "batch-uuid-running"
        assert call_kwargs["batch_num"] == 2
        assert call_kwargs["node_status"] == ExecutionStatus.COMPLETED.value

    def test_running_to_failed_transition_with_batch_context(self, mock_job_stats_service):
        """Test transition from RUNNING to FAILED state with batch context."""
        from docpipe.core.orchestration.flow_execution_event_handler import (
            FlowExecutionEventHandler,
        )

        handler = FlowExecutionEventHandler(job_stats_service=mock_job_stats_service)
        handler.job_run_id = "run-789"
        handler.job_log_path = "/tmp/test.log"
        handler.common_log_arguments = {"job_id": "job-456", "job_run_id": "run-789"}
        handler.node_logger = Mock()

        node_id = "node-failed"
        node_name = "FailedNode"
        exception = RuntimeError("Processing failed")
        global_config = {
            DocpipeConstants.ENABLE_MICRO_BATCHING: True,
            DocpipeConstants.BATCH_ID: "batch-uuid-failed",
            DocpipeConstants.BATCH_NUM: 3,
        }

        # Mock get_job to return a dict or object with model_dump
        mock_job_stats_service.get_job.return_value = None  # Simplest: skip stats injection

        # Call after_node_failure (RUNNING -> FAILED transition)
        with patch("docpipe.core.orchestration.flow_execution_event_handler.logger"):
            handler.after_node_failure(
                node_id=node_id,
                node_name=node_name,
                global_config=global_config,
                e=exception,
            )

        # Verify fail_node_execution was called with batch context
        mock_job_stats_service.fail_node_execution.assert_called_once()
        call_kwargs = mock_job_stats_service.fail_node_execution.call_args.kwargs

        assert call_kwargs["batch_id"] == "batch-uuid-failed"
        assert call_kwargs["batch_num"] == 3
        assert call_kwargs["node_id"] == node_id
        assert call_kwargs["exception"] == exception

    def test_multiple_batches_independent_state_transitions(self, mock_job_stats_service, sample_table):
        """Test that multiple batches can have independent state transitions."""
        from docpipe.core.orchestration.python.python_operator_executor import (
            PythonOperatorExecutor,
        )

        # Batch 0: PENDING -> RUNNING
        executor_batch_0 = PythonOperatorExecutor(
            name="test_node",
            operator="noop",
            params={
                OperatorConstants.Columns.NAME: "test_node",
                OperatorConstants.Columns.ID: "node-123",
                DocpipeConstants.JOB_RUN_ID: "run-789",
                DocpipeConstants.BATCH_ID: "batch-uuid-0",
                DocpipeConstants.BATCH_NUM: 0,
            },
            job_stats_service=mock_job_stats_service,
        )
        executor_batch_0.set_default_node_stats(tables=sample_table)

        # Batch 1: PENDING -> RUNNING
        executor_batch_1 = PythonOperatorExecutor(
            name="test_node",
            operator="noop",
            params={
                OperatorConstants.Columns.NAME: "test_node",
                OperatorConstants.Columns.ID: "node-123",
                DocpipeConstants.JOB_RUN_ID: "run-789",
                DocpipeConstants.BATCH_ID: "batch-uuid-1",
                DocpipeConstants.BATCH_NUM: 1,
            },
            job_stats_service=mock_job_stats_service,
        )
        executor_batch_1.set_default_node_stats(tables=sample_table)

        # Verify both batches called start_node_execution with different batch contexts
        assert mock_job_stats_service.start_node_execution.call_count == 2

        calls = mock_job_stats_service.start_node_execution.call_args_list
        batch_0_call = calls[0].kwargs
        batch_1_call = calls[1].kwargs

        assert batch_0_call["batch_id"] == "batch-uuid-0"
        assert batch_0_call["batch_num"] == 0
        assert batch_1_call["batch_id"] == "batch-uuid-1"
        assert batch_1_call["batch_num"] == 1

    def test_aborted_state_not_yet_implemented(self):
        """
        Document that ABORTED state transition is not yet implemented.

        NOTE: The abort/cancel functionality in prefect_engine.py (lines 272-356)
        currently cancels batch futures but does NOT call a dedicated
        'abort_node_execution' or similar method on the job_stats_service.

        Current behavior:
        - Batch cancellation is logged
        - Cancelled batches are waited on before semaphore reset
        - No explicit ABORTED state is set in node_stats

        This test documents the gap for Phase 4 implementation.
        """
        # This is a documentation test - no assertions needed
        # When abort is implemented, add tests like:
        # - test_running_to_aborted_transition_with_batch_context
        # - test_cancelled_batch_calls_abort_node_execution
        ...  # noqa: PIE790
