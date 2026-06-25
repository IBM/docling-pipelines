"""
Tests for runtime terminal path propagation with batch context.

Verifies that failure/cancel/skip paths correctly wire to the new
terminal service APIs with real batch_id and batch_num.
"""

from unittest.mock import Mock, patch

import pytest

from docpipe.core.constants.constants import DocpipeConstants


class TestTerminalPathBatchPropagation:
    """Test terminal path propagation with batch context."""

    @pytest.fixture
    def mock_job_stats_service(self):
        """Create a mock job stats service."""
        service = Mock()
        service.fail_node_execution = Mock()
        service.skip_node_execution = Mock()
        service.cancel_node_execution = Mock()
        service.get_job = Mock(return_value=None)
        service.write_job_logs = Mock()
        return service

    @patch("docpipe.core.orchestration.flow_execution_event_handler.logger")
    def test_after_node_failure_with_batch_context(self, mock_logger, mock_job_stats_service):
        """Test that after_node_failure calls fail_node_execution with batch context."""
        # Import here to avoid circular import at module level
        from docpipe.core.orchestration.flow_execution_event_handler import (
            FlowExecutionEventHandler,
        )

        # Arrange
        handler = FlowExecutionEventHandler(job_stats_service=mock_job_stats_service)
        handler.job_run_id = "test-job-run-123"
        handler.job_log_path = "/tmp/test.log"
        handler.common_log_arguments = {
            "job_id": "test-job",
            "job_run_id": "test-job-run-123",
        }
        handler.node_logger = Mock()

        node_id = "node-1"
        node_name = "TestNode"
        exception = ValueError("Test error")
        global_config = {
            DocpipeConstants.ENABLE_MICRO_BATCHING: True,
            DocpipeConstants.BATCH_ID: "batch-uuid-123",
            DocpipeConstants.BATCH_NUM: 5,
        }

        # Act
        handler.after_node_failure(
            node_id=node_id,
            node_name=node_name,
            global_config=global_config,
            e=exception,
        )

        # Assert
        mock_job_stats_service.fail_node_execution.assert_called_once_with(
            job_run_id="test-job-run-123",
            node_id=node_id,
            node_name=node_name,
            exception=exception,
            batch_id="batch-uuid-123",
            batch_num=5,
        )

    @patch("docpipe.core.orchestration.flow_execution_event_handler.logger")
    def test_after_node_failure_without_batch_context(self, mock_logger, mock_job_stats_service):
        """Test that after_node_failure works without batch context (non-batch mode)."""
        from docpipe.core.orchestration.flow_execution_event_handler import (
            FlowExecutionEventHandler,
        )

        # Arrange
        handler = FlowExecutionEventHandler(job_stats_service=mock_job_stats_service)
        handler.job_run_id = "test-job-run-123"
        handler.job_log_path = "/tmp/test.log"
        handler.common_log_arguments = {
            "job_id": "test-job",
            "job_run_id": "test-job-run-123",
        }
        handler.node_logger = Mock()

        node_id = "node-1"
        node_name = "TestNode"
        exception = ValueError("Test error")
        global_config = {
            DocpipeConstants.ENABLE_MICRO_BATCHING: False,
        }

        # Act
        handler.after_node_failure(
            node_id=node_id,
            node_name=node_name,
            global_config=global_config,
            e=exception,
        )

        # Assert - should be called with None for batch_id and batch_num
        mock_job_stats_service.fail_node_execution.assert_called_once_with(
            job_run_id="test-job-run-123",
            node_id=node_id,
            node_name=node_name,
            exception=exception,
            batch_id=None,
            batch_num=None,
        )

    def test_after_node_skipped_with_batch_context(self, mock_job_stats_service):
        """Test that after_node_skipped calls skip_node_execution with batch context."""
        from docpipe.core.orchestration.flow_execution_event_handler import (
            FlowExecutionEventHandler,
        )

        # Arrange
        handler = FlowExecutionEventHandler(job_stats_service=mock_job_stats_service)
        handler.job_run_id = "test-job-run-123"
        handler.common_log_arguments = {
            "job_id": "test-job",
            "job_run_id": "test-job-run-123",
        }
        handler.node_logger = Mock()

        node_id = "node-2"
        node_name = "SkippedNode"
        operator_type = "TestOperator"
        column_names = ["col1", "col2"]
        global_config = {
            DocpipeConstants.ENABLE_MICRO_BATCHING: True,
            DocpipeConstants.BATCH_ID: "batch-uuid-456",
            DocpipeConstants.BATCH_NUM: 3,
        }

        # Act
        handler.after_node_skipped(
            node_id=node_id,
            node_name=node_name,
            operator_type=operator_type,
            global_config=global_config,
            start_time=1000.0,
            end_time=1005.0,
            column_names=column_names,
        )

        # Assert
        mock_job_stats_service.skip_node_execution.assert_called_once_with(
            job_run_id="test-job-run-123",
            node_id=node_id,
            node_name=node_name,
            reason="Skipped - no input data to process",
            col_names=column_names,
            batch_id="batch-uuid-456",
            batch_num=3,
        )

    def test_after_node_skipped_without_batch_context(self, mock_job_stats_service):
        """Test that after_node_skipped works without batch context (non-batch mode)."""
        from docpipe.core.orchestration.flow_execution_event_handler import (
            FlowExecutionEventHandler,
        )

        # Arrange
        handler = FlowExecutionEventHandler(job_stats_service=mock_job_stats_service)
        handler.job_run_id = "test-job-run-123"
        handler.common_log_arguments = {
            "job_id": "test-job",
            "job_run_id": "test-job-run-123",
        }
        handler.node_logger = Mock()

        node_id = "node-2"
        node_name = "SkippedNode"
        operator_type = "TestOperator"
        column_names = ["col1", "col2"]
        global_config = {}  # No batching enabled

        # Act
        handler.after_node_skipped(
            node_id=node_id,
            node_name=node_name,
            operator_type=operator_type,
            global_config=global_config,
            start_time=1000.0,
            end_time=1005.0,
            column_names=column_names,
        )

        # Assert - should be called with None for batch_id and batch_num
        mock_job_stats_service.skip_node_execution.assert_called_once_with(
            job_run_id="test-job-run-123",
            node_id=node_id,
            node_name=node_name,
            reason="Skipped - no input data to process",
            col_names=column_names,
            batch_id=None,
            batch_num=None,
        )

    def test_after_node_skipped_with_custom_reason(self, mock_job_stats_service):
        """Test that after_node_skipped accepts custom reason for upstream failure scenarios."""
        from docpipe.core.orchestration.flow_execution_event_handler import (
            FlowExecutionEventHandler,
        )

        # Arrange
        handler = FlowExecutionEventHandler(job_stats_service=mock_job_stats_service)
        handler.job_run_id = "test-job-run-123"
        handler.common_log_arguments = {
            "job_id": "test-job",
            "job_run_id": "test-job-run-123",
        }
        handler.node_logger = Mock()

        node_id = "node-3"
        node_name = "DownstreamNode"
        operator_type = "ExtractOperator"
        column_names = []
        custom_reason = "Skipped - no data received from previous step"
        global_config = {
            DocpipeConstants.ENABLE_MICRO_BATCHING: True,
            DocpipeConstants.BATCH_ID: "batch-uuid-789",
            DocpipeConstants.BATCH_NUM: 1,
        }

        # Act
        handler.after_node_skipped(
            node_id=node_id,
            node_name=node_name,
            operator_type=operator_type,
            global_config=global_config,
            start_time=2000.0,
            end_time=2000.0,
            column_names=column_names,
            reason=custom_reason,
        )

        # Assert - should use custom reason
        mock_job_stats_service.skip_node_execution.assert_called_once_with(
            job_run_id="test-job-run-123",
            node_id=node_id,
            node_name=node_name,
            reason=custom_reason,
            col_names=column_names,
            batch_id="batch-uuid-789",
            batch_num=1,
        )
