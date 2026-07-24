"""Unit tests for FlowExecutionEventHandler."""

from unittest.mock import MagicMock, patch

import pytest

from docpipe.core.constants.constants import DocpipeConstants, ExecutionStatus
from docpipe.core.orchestration.flow_execution_event_handler import FlowExecutionEventHandler


@pytest.fixture
def mock_job_stats_service():
    service = MagicMock()
    service.cancel_job_run_if_cancelling.return_value = False
    return service


@pytest.fixture
def mock_job_run_manager():
    return MagicMock()


@pytest.fixture
def mock_execution_reporter():
    return MagicMock()


@pytest.fixture
def handler(mock_job_stats_service, mock_job_run_manager, mock_execution_reporter):
    h = FlowExecutionEventHandler(
        job_stats_service=mock_job_stats_service,
        job_run_manager=mock_job_run_manager,
        execution_reporter=mock_execution_reporter,
    )
    h.job_id = "job-123"
    h.job_run_id = "run-456"
    h.flow_id = "flow-789"
    h.job_log_path = "/tmp/logs/job_stats.json"
    h.common_log_arguments = {"job_id": "job-123", "job_run_id": "run-456"}
    return h


@pytest.fixture
def handler_no_services():
    return FlowExecutionEventHandler()


class TestInitialization:
    """Test FlowExecutionEventHandler initialization."""

    def test_default_init(self):
        handler = FlowExecutionEventHandler()
        assert handler.job_stats_service is None
        assert handler.job_run_manager is None
        assert handler.execution_reporter is None

    def test_init_with_services(self, mock_job_stats_service, mock_job_run_manager, mock_execution_reporter):
        handler = FlowExecutionEventHandler(
            job_stats_service=mock_job_stats_service,
            job_run_manager=mock_job_run_manager,
            execution_reporter=mock_execution_reporter,
        )
        assert handler.job_stats_service is mock_job_stats_service
        assert handler.job_run_manager is mock_job_run_manager
        assert handler.execution_reporter is mock_execution_reporter


class TestBeforeFlowExecutionStart:
    """Test before_flow_execution_start event handler."""

    def test_with_execution_reporter_and_flow_def(self, handler, mock_execution_reporter):
        flow_def = {DocpipeConstants.NAME: "Test Flow", DocpipeConstants.DAG: [{"id": "1"}, {"id": "2"}]}
        handler.before_flow_execution_start(orchestrator=MagicMock(), flow_def=flow_def)
        mock_execution_reporter.print_flow_header.assert_called_once_with(flow_name="Test Flow", operator_count=2)

    def test_without_execution_reporter(self, handler, mock_job_stats_service):
        handler.execution_reporter = None
        flow_def = {DocpipeConstants.NAME: "Test Flow", DocpipeConstants.DAG: []}
        handler.before_flow_execution_start(orchestrator=MagicMock(), flow_def=flow_def)
        mock_job_stats_service.start_tracking_job.assert_called_once()

    def test_cancels_job_if_cancelling(self, handler, mock_job_stats_service):
        mock_job_stats_service.cancel_job_run_if_cancelling.return_value = True
        handler.before_flow_execution_start(orchestrator=MagicMock(), flow_def=None)
        mock_job_stats_service.start_tracking_job.assert_not_called()

    def test_no_job_stats_service(self, handler_no_services):
        # Should not raise
        handler_no_services.job_id = "job-1"
        handler_no_services.job_run_id = "run-1"
        handler_no_services.common_log_arguments = {}
        handler_no_services.before_flow_execution_start(orchestrator=MagicMock(), flow_def=None)


class TestAfterFlowExecutionComplete:
    """Test after_flow_execution_complete event handler."""

    def test_no_job_stats_service_logs_warning(self, handler_no_services):
        handler_no_services.job_run_id = "run-1"
        handler_no_services.common_log_arguments = {}
        # Should not raise
        handler_no_services.after_flow_execution_complete(
            op_flow=[], present_job_status=ExecutionStatus.COMPLETED, message=None
        )

    def test_canceling_status_sets_canceled(self, handler, mock_job_stats_service):
        job_stats_mock = MagicMock()
        job_stats_mock.node_stats = {}
        mock_job_stats_service.get_job.return_value = job_stats_mock
        handler.after_flow_execution_complete(
            op_flow=[], present_job_status=ExecutionStatus.CANCELING, message="Canceled"
        )
        mock_job_stats_service.end_job.assert_called_once()
        call_kwargs = mock_job_stats_service.end_job.call_args[1]
        assert call_kwargs["status"] == ExecutionStatus.CANCELED.value

    def test_failing_status_sets_failed(self, handler, mock_job_stats_service):
        job_stats_mock = MagicMock()
        job_stats_mock.node_stats = {}
        mock_job_stats_service.get_job.return_value = job_stats_mock
        handler.after_flow_execution_complete(op_flow=[], present_job_status=ExecutionStatus.FAILING, message="Error")
        mock_job_stats_service.end_job.assert_called_once()
        call_kwargs = mock_job_stats_service.end_job.call_args[1]
        assert call_kwargs["status"] == ExecutionStatus.FAILED.value

    def test_completed_status_determines_from_node_stats(self, handler, mock_job_stats_service):
        node_stats_mock = MagicMock()
        node_stats_mock.node_status = "Completed"
        job_stats_mock = MagicMock()
        job_stats_mock.node_stats = {"node1": node_stats_mock}
        mock_job_stats_service.get_job.return_value = job_stats_mock

        with patch(
            "docpipe.core.operators.operator_utils.OperatorUtils.determine_final_job_status",
            return_value=ExecutionStatus.COMPLETED,
        ):
            handler.after_flow_execution_complete(
                op_flow=[], present_job_status=ExecutionStatus.COMPLETED, message=None
            )
        mock_job_stats_service.end_job.assert_called()

    def test_prints_flow_summary_when_reporter_present(self, handler, mock_job_stats_service, mock_execution_reporter):
        job_stats_mock = MagicMock()
        job_stats_mock.node_stats = {}
        mock_job_stats_service.get_job.return_value = job_stats_mock

        with patch(
            "docpipe.core.operators.operator_utils.OperatorUtils.determine_final_job_status",
            return_value=ExecutionStatus.COMPLETED,
        ):
            handler.after_flow_execution_complete(
                op_flow=[], present_job_status=ExecutionStatus.COMPLETED, message=None
            )
        mock_execution_reporter.print_flow_summary.assert_called_once()


class TestBeforeStepExecutionStart:
    """Test before_step_execution_start event handler."""

    def test_prints_operator_start_when_not_skipped(self, handler, mock_execution_reporter):
        handler.before_step_execution_start(
            node_id="n1",
            node_name="extract",
            global_config={"operator_type": "ExtractOperator"},
            job_status=ExecutionStatus.RUNNING,
            prev_results=MagicMock(),
        )
        mock_execution_reporter.print_operator_start.assert_called_once_with(
            step_name="extract", operator_type="ExtractOperator"
        )

    def test_does_not_print_when_prev_results_is_none(self, handler, mock_execution_reporter):
        handler.before_step_execution_start(
            node_id="n1",
            node_name="extract",
            global_config=None,
            job_status=ExecutionStatus.RUNNING,
            prev_results=None,
        )
        mock_execution_reporter.print_operator_start.assert_not_called()

    def test_does_not_print_when_canceling(self, handler, mock_execution_reporter):
        handler.before_step_execution_start(
            node_id="n1",
            node_name="extract",
            global_config=None,
            job_status=ExecutionStatus.CANCELING,
            prev_results=MagicMock(),
        )
        mock_execution_reporter.print_operator_start.assert_not_called()

    def test_does_not_print_when_failing(self, handler, mock_execution_reporter):
        handler.before_step_execution_start(
            node_id="n1",
            node_name="extract",
            global_config=None,
            job_status=ExecutionStatus.FAILING,
            prev_results=MagicMock(),
        )
        mock_execution_reporter.print_operator_start.assert_not_called()


class TestAfterStepExecutionComplete:
    """Test after_step_execution_complete event handler."""

    def test_updates_doc_counts_and_framework_status(self, handler, mock_job_stats_service, mock_job_run_manager):
        from docpipe.core.operators.abstract_operator import OperatorCategory

        handler.after_step_execution_complete(
            node_id="n1",
            node_name="ingest",
            operator_category=OperatorCategory.Ingest,
            operator=MagicMock(),
            global_config={},
            is_last_step=False,
            metadata={"total_docs_count": 5},
            start_time=0,
            tables=None,
        )
        mock_job_stats_service.update_doc_counts.assert_called_once()


class TestAfterNodeSkipped:
    """Test after_node_skipped event handler."""

    def test_calls_skip_node_execution(self, handler, mock_job_stats_service):
        handler.after_node_skipped(
            node_id="n1",
            node_name="extract",
            operator_type="ExtractOperator",
            global_config={},
            start_time=0,
            end_time=1,
            column_names=["id", "content"],
        )
        mock_job_stats_service.skip_node_execution.assert_called_once()

    def test_skips_with_micro_batching_context(self, handler, mock_job_stats_service):
        global_config = {
            DocpipeConstants.ENABLE_MICRO_BATCHING: True,
            DocpipeConstants.BATCH_ID: "batch-1",
            DocpipeConstants.BATCH_NUM: 0,
        }
        handler.after_node_skipped(
            node_id="n1",
            node_name="extract",
            operator_type="ExtractOperator",
            global_config=global_config,
            start_time=0,
            end_time=1,
            column_names=[],
        )
        call_kwargs = mock_job_stats_service.skip_node_execution.call_args[1]
        assert call_kwargs["batch_id"] == "batch-1"


class TestAfterNodeFailure:
    """Test after_node_failure event handler."""

    def test_calls_fail_node_execution(self, handler, mock_job_stats_service, mock_job_run_manager):
        job_stats_mock = MagicMock()
        mock_job_stats_service.get_job.return_value = job_stats_mock

        handler.after_node_failure(node_id="n1", node_name="extract", global_config={}, e=RuntimeError("Test error"))
        mock_job_stats_service.fail_node_execution.assert_called_once()
        mock_job_run_manager.update_job_run_status.assert_called()

    def test_no_job_stats_service(self, handler):
        handler.job_stats_service = None
        # Should not raise even without services
        with patch.object(handler, "_update_framework_status"):
            handler.after_node_failure(node_id="n1", node_name="extract", global_config={}, e=RuntimeError("Error"))


class TestAfterBatchesPrepared:
    """Test after_batches_prepared event handler."""

    def test_skips_when_micro_batching_disabled(self, handler, mock_job_stats_service):
        handler.after_batches_prepared(
            batches=[],
            op_flow=[{"id": "n1", "name": "ingest"}, {"id": "n2", "name": "extract"}],
            global_config={DocpipeConstants.ENABLE_MICRO_BATCHING: False},
        )
        mock_job_stats_service.create_pending_batch_node_stats.assert_not_called()

    def test_creates_pending_stats_when_micro_batching_enabled(self, handler, mock_job_stats_service):
        from docpipe.core.orchestration.batch_manager import BatchInfo

        batches = [
            BatchInfo(batch_id="batch-1", batch_num=0, table=MagicMock()),
            BatchInfo(batch_id="batch-2", batch_num=1, table=MagicMock()),
        ]
        op_flow = [
            {"id": "n0", "name": "ingest"},
            {"id": "n1", "name": "extract"},
            {"id": "n2", "name": "chunk"},
        ]
        handler.after_batches_prepared(
            batches=batches,
            op_flow=op_flow,
            global_config={DocpipeConstants.ENABLE_MICRO_BATCHING: True},
        )
        mock_job_stats_service.create_pending_batch_node_stats.assert_called_once()

    def test_no_job_stats_service_skips(self, handler):
        handler.job_stats_service = None
        # Should not raise
        handler.after_batches_prepared(
            batches=[MagicMock()],
            op_flow=[{"id": "n1"}],
            global_config={DocpipeConstants.ENABLE_MICRO_BATCHING: True},
        )


class TestShouldPrintOperatorSummary:
    """Test _should_print_operator_summary static method."""

    def test_non_batch_mode_always_returns_true(self):
        node_stats = MagicMock()
        job_stats = MagicMock()
        result = FlowExecutionEventHandler._should_print_operator_summary(
            node_id="n1",
            node_stats=node_stats,
            global_config=None,
            job_stats=job_stats,
        )
        assert result is True

    def test_non_batch_mode_with_no_batch_id(self):
        result = FlowExecutionEventHandler._should_print_operator_summary(
            node_id="n1",
            node_stats=MagicMock(),
            global_config={},
            job_stats=MagicMock(),
        )
        assert result is True

    def test_batch_mode_no_batch_records_returns_false(self):
        job_stats = MagicMock()
        job_stats.batch_node_stats = {}
        result = FlowExecutionEventHandler._should_print_operator_summary(
            node_id="n1",
            node_stats=MagicMock(),
            global_config={DocpipeConstants.BATCH_ID: "batch-1"},
            job_stats=job_stats,
        )
        assert result is False


class TestGetCompleteJobStats:
    """Test _get_complete_job_stats helper."""

    def test_no_job_stats_service_returns_message(self, handler):
        handler.job_stats_service = None
        result = handler._get_complete_job_stats(message="Error occurred")
        assert result == {"message": "Error occurred"}

    def test_no_job_stats_service_returns_none_when_no_message(self, handler):
        handler.job_stats_service = None
        result = handler._get_complete_job_stats()
        assert result is None

    def test_returns_job_stats_with_message(self, handler, mock_job_stats_service):
        job_stats_mock = MagicMock()
        job_stats_mock.model_dump.return_value = {"job_id": "123", "status": "running"}
        mock_job_stats_service.get_job.return_value = job_stats_mock

        result = handler._get_complete_job_stats(message="Done")
        assert result["message"] == "Done"
        assert result["job_id"] == "123"


class TestUpdateFrameworkStatus:
    """Test _update_framework_status helper."""

    def test_calls_job_run_manager(self, handler, mock_job_run_manager):
        handler._update_framework_status(status="Running", job_run_stats={"count": 1})
        mock_job_run_manager.update_job_run_status.assert_called_once()

    def test_no_job_run_manager_does_nothing(self, handler):
        handler.job_run_manager = None
        # Should not raise
        handler._update_framework_status(status="Running")

    def test_framework_exception_is_swallowed(self, handler, mock_job_run_manager):
        mock_job_run_manager.update_job_run_status.side_effect = RuntimeError("Framework error")
        # Should not raise
        handler._update_framework_status(status="Running")
