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

        handler._mark_report_not_available("no parquet found")

        mock_service.end_job.assert_called_once()
        call_kwargs = mock_service.end_job.call_args.kwargs
        assert call_kwargs["job_run_stats"]["report_status"] == "NOT_AVAILABLE"

    def test_job_run_id_passed_to_end_job(self):
        """end_job is called with the correct job_run_id."""
        mock_service = MagicMock()
        mock_service.get_job.return_value = _make_job_stats()
        handler = _make_handler(job_stats_service=mock_service)

        handler._mark_report_not_available("reason")

        call_kwargs = mock_service.end_job.call_args.kwargs
        assert call_kwargs["job_run_id"] == JOB_RUN_ID

    def test_noop_when_no_service(self):
        """Does nothing when job_stats_service is None."""
        handler = _make_handler(job_stats_service=None)
        # Must not raise
        handler._mark_report_not_available("reason")

    def test_noop_when_job_run_id_is_none(self):
        """Does nothing when job_run_id is not set."""
        mock_service = MagicMock()
        handler = _make_handler(job_stats_service=mock_service)
        handler.job_run_id = None

        handler._mark_report_not_available("reason")

        mock_service.end_job.assert_not_called()

    def test_noop_when_job_not_found(self):
        """Does nothing when get_job returns None."""
        mock_service = MagicMock()
        mock_service.get_job.return_value = None
        handler = _make_handler(job_stats_service=mock_service)

        handler._mark_report_not_available("reason")

        mock_service.end_job.assert_not_called()


class TestGenerateReportAsyncParquetAbsent:
    def test_not_available_set_when_parquet_missing(self):
        """_generate_report_async sets NOT_AVAILABLE before early return."""
        mock_service = MagicMock()
        mock_service.get_job.return_value = _make_job_stats()
        handler = _make_handler(job_stats_service=mock_service)

        with patch(
            "docpipe.core.job_management.application.services.report_utils.check_parquet_availability",
            return_value=(False, "Data directory not found"),
        ):
            handler._generate_report_async(
                job_run_id=JOB_RUN_ID,
                job_id=JOB_ID,
                dag_nodes_ref=[],
                batch_node_stats_ref={},
                node_metadata_list_ref=[],
            )

        mock_service.end_job.assert_called_once()
        call_kwargs = mock_service.end_job.call_args.kwargs
        assert call_kwargs["job_run_stats"]["report_status"] == "NOT_AVAILABLE"

    def test_not_available_not_set_when_parquet_present(self):
        """When parquet is available, NOT_AVAILABLE is never written to job_run_stats."""
        mock_service = MagicMock()
        mock_service.get_job.return_value = _make_job_stats()
        handler = _make_handler(job_stats_service=mock_service)

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
                job_run_id=JOB_RUN_ID,
                job_id=JOB_ID,
                dag_nodes_ref=[],
                batch_node_stats_ref={},
                node_metadata_list_ref=[],
            )

        # end_job must not have been called with NOT_AVAILABLE
        for call in mock_service.end_job.call_args_list:
            stats = (call.kwargs or {}).get("job_run_stats", {})
            assert stats.get("report_status") != "NOT_AVAILABLE"
