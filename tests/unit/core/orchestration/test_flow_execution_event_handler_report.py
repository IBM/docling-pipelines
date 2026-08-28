"""
Unit tests for FlowExecutionEventHandler report status methods.

Covers:
- _mark_report_not_available(): writes NOT_AVAILABLE to job_run_stats
- _mark_report_not_available(): no-ops when job_stats_service is None
- _mark_report_not_available(): no-ops when job_run_id is None
- _mark_report_not_available(): no-ops when get_job returns None
- _generate_report_async(): sets NOT_AVAILABLE before early return when parquet absent
- _generate_report_async(): does NOT set NOT_AVAILABLE when parquet is present
"""

from unittest.mock import MagicMock, patch

from docpipe.core.constants.constants import ExecutionStatus
from docpipe.core.job_management.domain.models.job_stats import JobStats
from docpipe.core.orchestration.flow_execution_event_handler import FlowExecutionEventHandler

JOB_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
JOB_RUN_ID = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


def _make_handler(job_stats_service=None):
    handler = FlowExecutionEventHandler(job_stats_service=job_stats_service)
    handler.job_run_id = JOB_RUN_ID
    handler.job_id = JOB_ID
    handler.common_log_arguments = {}
    return handler


def _make_job_stats():
    return JobStats(job_id=JOB_ID, job_run_id=JOB_RUN_ID, status=ExecutionStatus.COMPLETED)


class TestMarkReportNotAvailable:
    def test_writes_not_available_status(self):
        """Calls end_job with report_status=NOT_AVAILABLE."""
        mock_service = MagicMock()
        mock_service.get_job.return_value = _make_job_stats()
        handler = _make_handler(job_stats_service=mock_service)

        handler._mark_report_not_available()

        mock_service.end_job.assert_called_once()
        call_kwargs = mock_service.end_job.call_args.kwargs
        assert call_kwargs["job_run_stats"]["report_status"] == "NOT_AVAILABLE"

    def test_job_run_id_passed_to_end_job(self):
        """end_job is called with the correct job_run_id."""
        mock_service = MagicMock()
        mock_service.get_job.return_value = _make_job_stats()
        handler = _make_handler(job_stats_service=mock_service)

        handler._mark_report_not_available()

        call_kwargs = mock_service.end_job.call_args.kwargs
        assert call_kwargs["job_run_id"] == JOB_RUN_ID

    def test_noop_when_no_service(self):
        """Does nothing when job_stats_service is None."""
        handler = _make_handler(job_stats_service=None)
        # Must not raise
        handler._mark_report_not_available()

    def test_noop_when_job_run_id_is_none(self):
        """Does nothing when job_run_id is not set."""
        mock_service = MagicMock()
        handler = _make_handler(job_stats_service=mock_service)
        handler.job_run_id = None

        handler._mark_report_not_available()

        mock_service.end_job.assert_not_called()

    def test_noop_when_job_not_found(self):
        """Does nothing when get_job returns None."""
        mock_service = MagicMock()
        mock_service.get_job.return_value = None
        handler = _make_handler(job_stats_service=mock_service)

        handler._mark_report_not_available()

        mock_service.end_job.assert_not_called()


class TestGenerateReportAsyncParquetAbsent:
    def test_not_available_set_when_parquet_missing(self):
        """_generate_report_async sets NOT_AVAILABLE before early return."""
        from docpipe.core.models.session_info import SessionInfo

        mock_service = MagicMock()
        mock_service.get_job.return_value = _make_job_stats()
        handler = _make_handler(job_stats_service=mock_service)
        session_info = SessionInfo(job_id=JOB_ID, job_run_id=JOB_RUN_ID)

        with patch(
            "docpipe.core.job_management.application.services.report_utils.check_parquet_availability",
            return_value=(False, "Data directory not found"),
        ):
            handler._generate_report_async(
                session_info,
                dag_nodes_ref=[],
                batch_node_stats_ref={},
                node_metadata_list_ref=[],
            )

        mock_service.end_job.assert_called_once()
        call_kwargs = mock_service.end_job.call_args.kwargs
        assert call_kwargs["job_run_stats"]["report_status"] == "NOT_AVAILABLE"

    def test_not_available_not_set_when_parquet_present(self):
        """When parquet is available, NOT_AVAILABLE is never written to job_run_stats."""
        from docpipe.core.models.session_info import SessionInfo

        mock_service = MagicMock()
        mock_service.get_job.return_value = _make_job_stats()
        handler = _make_handler(job_stats_service=mock_service)
        session_info = SessionInfo(job_id=JOB_ID, job_run_id=JOB_RUN_ID)

        with (
            patch(
                "docpipe.core.job_management.application.services.report_utils.check_parquet_availability",
                return_value=(True, ""),
            ),
            patch.object(handler, "_set_report_generating_status"),
            patch.object(handler, "_mark_report_failed"),
            patch(
                "docpipe.core.job_management.application.services.report_generator.JobReportGenerator",
                side_effect=Exception("short-circuit"),
            ),
        ):
            handler._generate_report_async(
                session_info,
                dag_nodes_ref=[],
                batch_node_stats_ref={},
                node_metadata_list_ref=[],
            )

        # end_job must not have been called with NOT_AVAILABLE
        for call in mock_service.end_job.call_args_list:
            stats = (call.kwargs or {}).get("job_run_stats", {})
            assert stats.get("report_status") != "NOT_AVAILABLE"


class TestBeforeFlowExecutionStart:
    def test_noop_when_no_service(self):
        handler = _make_handler()
        handler.before_flow_execution_start(orchestrator=MagicMock(), flow_def=None)

    def test_starts_tracking_job_when_service_present(self):
        mock_service = MagicMock()
        mock_service.cancel_job_run_if_cancelling.return_value = False
        handler = _make_handler(job_stats_service=mock_service)
        handler.flow_id = "flow-1"
        handler.job_log_path = "/tmp/log"
        handler.before_flow_execution_start(orchestrator=MagicMock(), flow_def={"name": "flow", "dag": []})
        mock_service.start_tracking_job.assert_called_once()

    def test_returns_early_when_already_canceling(self):
        mock_service = MagicMock()
        mock_service.cancel_job_run_if_cancelling.return_value = True
        handler = _make_handler(job_stats_service=mock_service)
        handler.flow_id = "flow-1"
        handler.job_log_path = "/tmp/log"
        handler.before_flow_execution_start(orchestrator=MagicMock(), flow_def={"name": "flow", "dag": []})
        mock_service.start_tracking_job.assert_not_called()

    def test_calls_execution_reporter_when_set(self):
        reporter = MagicMock()
        handler = _make_handler()
        handler.execution_reporter = reporter
        handler.flow_id = "flow-1"
        handler.before_flow_execution_start(orchestrator=MagicMock(), flow_def={"name": "my-flow", "dag": [{}, {}]})
        reporter.print_flow_header.assert_called_once_with(flow_name="my-flow", operator_count=2)


class TestDetermineJobStatusFromStats:
    def test_returns_failed_when_no_service(self):
        handler = _make_handler()
        result = handler._determine_job_status_from_stats([])
        assert result == ExecutionStatus.FAILED

    def test_returns_failed_when_no_job_stats(self):
        mock_service = MagicMock()
        mock_service.get_job.return_value = None
        handler = _make_handler(job_stats_service=mock_service)
        result = handler._determine_job_status_from_stats([])
        assert result == ExecutionStatus.FAILED

    def test_returns_completed_with_errors_on_partial_batch_failure(self):
        from docpipe.core.job_management.domain.models.node_stats import NodeStats

        mock_service = MagicMock()
        job = _make_job_stats()
        # node_stats must be non-empty for the branch to be reached
        job.node_stats = {"n1": NodeStats(id="n1", name="Node1")}
        mock_service.get_job.return_value = job
        mock_service.detect_partial_batch_failure.return_value = True
        handler = _make_handler(job_stats_service=mock_service)
        result = handler._determine_job_status_from_stats([])
        assert result == ExecutionStatus.COMPLETED_WITH_ERRORS


class TestAfterNodeFailure:
    def test_noop_when_no_service(self):
        handler = _make_handler()
        with patch("docpipe.core.orchestration.flow_execution_event_handler.get_session_info") as mock_si:
            mock_si.return_value = MagicMock(transaction_id="tx-1")
            handler.after_node_failure(node_id="n1", node_name="Extract", global_config={}, e=RuntimeError("fail"))

    def test_calls_fail_node_execution(self):
        mock_service = MagicMock()
        mock_service.get_job.return_value = None
        handler = _make_handler(job_stats_service=mock_service)
        handler.job_log_path = None
        with patch("docpipe.core.orchestration.flow_execution_event_handler.get_session_info") as mock_si:
            mock_si.return_value = MagicMock(transaction_id="tx-1")
            handler.after_node_failure(node_id="n1", node_name="Extract", global_config={}, e=RuntimeError("fail"))
        mock_service.fail_node_execution.assert_called_once()

    def test_extracts_batch_context_from_global_config(self):
        mock_service = MagicMock()
        mock_service.get_job.return_value = None
        handler = _make_handler(job_stats_service=mock_service)
        handler.job_log_path = None
        with patch("docpipe.core.orchestration.flow_execution_event_handler.get_session_info") as mock_si:
            mock_si.return_value = MagicMock(transaction_id="tx-1")
            handler.after_node_failure(
                node_id="n1",
                node_name="Extract",
                global_config={"enable_micro_batching": True, "batch_id": "b1", "batch_num": 2},
                e=RuntimeError("fail"),
            )
        call_kwargs = mock_service.fail_node_execution.call_args.kwargs
        assert call_kwargs["batch_id"] == "b1"
        assert call_kwargs["batch_num"] == 2


class TestAfterBatchesPrepared:
    def test_noop_when_micro_batching_disabled(self):
        mock_service = MagicMock()
        handler = _make_handler(job_stats_service=mock_service)
        handler.after_batches_prepared(batches=[], op_flow=[], global_config={})
        mock_service.create_pending_batch_node_stats.assert_not_called()

    def test_noop_when_no_service(self):
        handler = _make_handler()
        handler.after_batches_prepared(batches=[MagicMock()], op_flow=[], global_config={"enable_micro_batching": True})

    def test_calls_create_pending_batch_stats(self):
        mock_service = MagicMock()
        handler = _make_handler(job_stats_service=mock_service)
        batch = MagicMock()
        batch.batch_id = "b1"
        batch.batch_num = 0
        op_flow = [
            {"id": "n0", "name": "Ingest", "operator": "ingest_source"},
            {"id": "n1", "name": "Extract", "operator": "extract_operator"},
        ]
        handler.after_batches_prepared(batches=[batch], op_flow=op_flow, global_config={"enable_micro_batching": True})
        mock_service.create_pending_batch_node_stats.assert_called_once()


class TestGetCompleteJobStats:
    def test_returns_message_dict_when_no_service(self):
        handler = _make_handler()
        result = handler._get_complete_job_stats(message="done")
        assert result == {"message": "done"}

    def test_returns_none_when_no_service_no_message(self):
        handler = _make_handler()
        result = handler._get_complete_job_stats()
        assert result is None


class TestUpdateFrameworkStatus:
    def test_noop_when_no_manager(self):
        handler = _make_handler()
        handler.job_run_manager = None
        handler._update_framework_status(status="running")

    def test_calls_manager_update(self):
        mgr = MagicMock()
        handler = _make_handler()
        handler.job_run_manager = mgr
        handler._update_framework_status(status="running")
        mgr.update_job_run_status.assert_called_once()

    def test_swallows_framework_exception(self):
        mgr = MagicMock()
        mgr.update_job_run_status.side_effect = Exception("network error")
        handler = _make_handler()
        handler.job_run_manager = mgr
        handler._update_framework_status(status="running")  # must not raise


class TestSetReportGeneratingStatus:
    def test_noop_when_no_service(self):
        handler = _make_handler()
        handler._set_report_generating_status(started_at=123)

    def test_noop_when_job_not_found(self):
        mock_service = MagicMock()
        mock_service.get_job.return_value = None
        handler = _make_handler(job_stats_service=mock_service)
        handler._set_report_generating_status(started_at=123)
        mock_service.end_job.assert_not_called()

    def test_calls_end_job_with_generating_status(self):
        mock_service = MagicMock()
        mock_service.get_job.return_value = _make_job_stats()
        handler = _make_handler(job_stats_service=mock_service)
        handler._set_report_generating_status(started_at=123)
        call_kwargs = mock_service.end_job.call_args.kwargs
        assert call_kwargs["job_run_stats"]["report_status"] == "GENERATING"


class TestMarkReportFailed:
    def test_noop_when_no_service(self):
        handler = _make_handler()
        handler._mark_report_failed(1.5, Exception("fail"))

    def test_calls_end_job_with_failed_status(self):
        mock_service = MagicMock()
        mock_service.get_job.return_value = _make_job_stats()
        handler = _make_handler(job_stats_service=mock_service)
        with patch("docpipe.utils.core.datetime.get_current_timestamp", return_value=999):
            handler._mark_report_failed(1.5, Exception("report failed"))
        call_kwargs = mock_service.end_job.call_args.kwargs
        assert call_kwargs["job_run_stats"]["report_status"] == "FAILED"


class TestExtractNodeMetadataListFromJobStats:
    def test_extracts_metadata_from_node_stats(self):
        node_stat = MagicMock()
        node_stat.node_metadata = {"key": "val"}
        job_stats = MagicMock()
        job_stats.node_stats = {"n1": node_stat}
        result = FlowExecutionEventHandler._extract_node_metadata_list_from_job_stats(job_stats)
        assert result == [{"key": "val"}]

    def test_skips_node_with_no_metadata(self):
        node_stat = MagicMock()
        node_stat.node_metadata = None
        job_stats = MagicMock()
        job_stats.node_stats = {"n1": node_stat}
        result = FlowExecutionEventHandler._extract_node_metadata_list_from_job_stats(job_stats)
        assert result == []
