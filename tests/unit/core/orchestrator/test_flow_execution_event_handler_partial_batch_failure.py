"""
Unit tests for partial batch failure detection delegation in FlowExecutionEventHandler.

The detection logic now lives in JobStatsService and the event handler delegates to it
from after_flow_execution_complete().
"""

from unittest.mock import MagicMock

import pytest

from docpipe.core.constants.constants import DocpipeConstants, ExecutionStatus
from docpipe.core.orchestration.flow_execution_event_handler import FlowExecutionEventHandler


class TestPartialBatchFailureDelegation:
    """Test suite for partial batch failure handling in after_flow_execution_complete."""

    @pytest.fixture
    def event_handler(self):
        """Create FlowExecutionEventHandler instance with mocked dependencies."""
        job_stats_service = MagicMock()
        job_run_manager = MagicMock()
        handler = FlowExecutionEventHandler(
            job_stats_service=job_stats_service,
            job_run_manager=job_run_manager,
            execution_reporter=None,
        )
        handler.job_run_id = "run-1"
        handler.job_log_path = None
        handler.common_log_arguments = {}
        return handler

    @pytest.fixture
    def op_flow(self):
        """Create minimal operator flow."""
        return [{"id": "node_1", "name": "Node 1"}]

    @pytest.fixture
    def job_stats(self):
        """Create mock job stats with node stats."""
        stats = MagicMock()
        stats.node_stats = {"node_1": MagicMock(node_status=ExecutionStatus.COMPLETED.value)}
        return stats

    def test_sets_completed_with_errors_when_service_detects_partial_failure(
        self, event_handler, op_flow, job_stats, monkeypatch
    ):
        """Verify partial failure detection from service overrides final status."""
        event_handler.job_stats_service.get_job.return_value = job_stats
        event_handler.job_stats_service.detect_partial_batch_failure.return_value = True

        determine_final_job_status = MagicMock(return_value=ExecutionStatus.COMPLETED)
        monkeypatch.setattr(
            "docpipe.core.orchestration.flow_execution_event_handler.OperatorUtils.determine_final_job_status",
            determine_final_job_status,
        )

        # Mock background report generation to prevent additional end_job calls
        mock_start_background = MagicMock()
        monkeypatch.setattr(
            "docpipe.core.orchestration.flow_execution_event_handler.FlowExecutionEventHandler._start_background_report_generation",
            mock_start_background,
        )

        event_handler.after_flow_execution_complete(
            op_flow=op_flow,
            present_job_status=ExecutionStatus.RUNNING,
            message="done",
            global_config={
                DocpipeConstants.ENABLE_MICRO_BATCHING: True,
                DocpipeConstants.CONTINUE_ON_BATCH_FAILURE: True,
            },
        )

        event_handler.job_stats_service.detect_partial_batch_failure.assert_called_once_with(
            job_stats=job_stats,
            global_config={
                DocpipeConstants.ENABLE_MICRO_BATCHING: True,
                DocpipeConstants.CONTINUE_ON_BATCH_FAILURE: True,
            },
        )
        determine_final_job_status.assert_not_called()
        event_handler.job_stats_service.end_job.assert_called_once_with(
            job_run_id="run-1",
            status=ExecutionStatus.COMPLETED_WITH_ERRORS.value,
            job_run_stats={"message": "done"},
        )

    def test_uses_operator_utils_when_service_reports_no_partial_failure(
        self, event_handler, op_flow, job_stats, monkeypatch
    ):
        """Verify normal final status determination when no partial failure is detected."""
        event_handler.job_stats_service.get_job.return_value = job_stats
        event_handler.job_stats_service.detect_partial_batch_failure.return_value = False

        determine_final_job_status = MagicMock(return_value=ExecutionStatus.COMPLETED)
        monkeypatch.setattr(
            "docpipe.core.orchestration.flow_execution_event_handler.OperatorUtils.determine_final_job_status",
            determine_final_job_status,
        )

        # Mock background report generation to prevent additional end_job calls
        mock_start_background = MagicMock()
        monkeypatch.setattr(
            "docpipe.core.orchestration.flow_execution_event_handler.FlowExecutionEventHandler._start_background_report_generation",
            mock_start_background,
        )

        event_handler.after_flow_execution_complete(
            op_flow=op_flow,
            present_job_status=ExecutionStatus.RUNNING,
            message="done",
            global_config={
                DocpipeConstants.ENABLE_MICRO_BATCHING: True,
                DocpipeConstants.CONTINUE_ON_BATCH_FAILURE: True,
            },
        )

        event_handler.job_stats_service.detect_partial_batch_failure.assert_called_once_with(
            job_stats=job_stats,
            global_config={
                DocpipeConstants.ENABLE_MICRO_BATCHING: True,
                DocpipeConstants.CONTINUE_ON_BATCH_FAILURE: True,
            },
        )
        determine_final_job_status.assert_called_once_with(node_stats_list=job_stats.node_stats)
        event_handler.job_stats_service.end_job.assert_called_once_with(
            job_run_id="run-1",
            status=ExecutionStatus.COMPLETED.value,
            job_run_stats={"message": "done"},
        )

    def test_passes_empty_dict_when_global_config_is_none(self, event_handler, op_flow, job_stats, monkeypatch):
        """Verify empty dict is passed to service when global_config is None."""
        event_handler.job_stats_service.get_job.return_value = job_stats
        event_handler.job_stats_service.detect_partial_batch_failure.return_value = False

        determine_final_job_status = MagicMock(return_value=ExecutionStatus.COMPLETED)
        monkeypatch.setattr(
            "docpipe.core.orchestration.flow_execution_event_handler.OperatorUtils.determine_final_job_status",
            determine_final_job_status,
        )

        # Mock background report generation to prevent additional end_job calls
        mock_start_background = MagicMock()
        monkeypatch.setattr(
            "docpipe.core.orchestration.flow_execution_event_handler.FlowExecutionEventHandler._start_background_report_generation",
            mock_start_background,
        )

        event_handler.after_flow_execution_complete(
            op_flow=op_flow,
            present_job_status=ExecutionStatus.RUNNING,
            message=None,
            global_config=None,
        )

        event_handler.job_stats_service.detect_partial_batch_failure.assert_called_once_with(
            job_stats=job_stats,
            global_config={},
        )
        determine_final_job_status.assert_called_once_with(node_stats_list=job_stats.node_stats)
        event_handler.job_stats_service.end_job.assert_called_once_with(
            job_run_id="run-1",
            status=ExecutionStatus.COMPLETED.value,
            job_run_stats=None,
        )
