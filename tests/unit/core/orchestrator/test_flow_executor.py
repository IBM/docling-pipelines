"""Unit tests for flow_executor module."""

import json
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest

from docpipe.core.constants.constants import DocpipeConstants
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.orchestration.flow_executor import FlowExecutor
from docpipe.exceptions.docpipe_exceptions import FlowValidationException


class TestFlowExecutor:
    """Test FlowExecutor class."""

    @patch("docpipe.core.orchestration.flow_executor.get_session_info")
    def test_init_with_flow_def_file(self, mock_session):
        """Test initialization with flow definition file."""
        mock_session.return_value = Mock(get_common_log_arguments=Mock(return_value={}))

        flow_data = {"flow": {"name": "Test Flow", "description": "Test Description", "dag": []}}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(flow_data, f)
            temp_path = f.name

        try:
            executor = FlowExecutor(flow_def_file=temp_path)

            assert executor.flow_def["name"] == "Test Flow"
            assert executor.flow_def["description"] == "Test Description"
        finally:
            Path(temp_path).unlink()

    @patch("docpipe.core.orchestration.flow_executor.get_session_info")
    def test_init_with_flow_def_dict(self, mock_session):
        """Test initialization with flow definition dict."""
        mock_session.return_value = Mock(get_common_log_arguments=Mock(return_value={}))

        flow_def = {
            "name": "Direct Flow",
            "description": "Direct Description",
            "dag": [],
        }

        executor = FlowExecutor(flow_def=flow_def)

        assert executor.flow_def["name"] == "Direct Flow"
        assert executor.flow_def["description"] == "Direct Description"

    @patch("docpipe.core.orchestration.flow_executor.get_session_info")
    def test_init_with_orchestrator(self, mock_session):
        """Test initialization with orchestrator."""
        mock_session.return_value = Mock(get_common_log_arguments=Mock(return_value={}))
        mock_orchestrator = Mock()

        flow_def = {"name": "Test", "dag": []}
        executor = FlowExecutor(flow_def=flow_def, orchestrator=mock_orchestrator)

        assert executor._FlowExecutor__orchestrator == mock_orchestrator

    @patch("docpipe.core.orchestration.flow_executor.get_session_info")
    def test_str_representation(self, mock_session):
        """Test string representation of FlowExecutor."""
        mock_session.return_value = Mock(get_common_log_arguments=Mock(return_value={}))

        flow_def = {"name": "My Flow", "description": "My Description", "dag": []}

        executor = FlowExecutor(flow_def=flow_def)
        result = str(executor)

        assert "My Flow" in result
        assert "My Description" in result

    @patch("docpipe.core.orchestration.flow_executor.get_session_info")
    @patch("docpipe.core.orchestration.flow_executor.FlowValidator")
    def test_execute_basic(self, mock_validator, mock_session):
        """Test basic flow execution."""
        mock_session.return_value = Mock(get_common_log_arguments=Mock(return_value={}), job_run_id="run_123")

        mock_validator_instance = Mock()
        mock_validator.return_value = mock_validator_instance

        mock_orchestrator = Mock()
        mock_orchestrator.job_stats_service = None  # Explicitly set to None
        mock_tracker_instance = Mock()
        mock_tracker_instance.cancel_job_run_if_cancelling.return_value = False
        mock_orchestrator.job_tracker = mock_tracker_instance
        mock_orchestrator.flow_execution_event_handler = Mock(job_log_path="/tmp/test.log")
        mock_data_access = Mock()
        mock_orchestrator.execute.return_value = mock_data_access

        flow_def = {"name": "Test", "dag": [{"id": "node1"}]}
        executor = FlowExecutor(flow_def=flow_def)

        params = {DocpipeConstants.JOB_RUN_ID: "run_123"}
        result = executor.execute(orchestrator=mock_orchestrator, params=params)

        mock_validator_instance.validate.assert_called_once()
        mock_orchestrator.execute.assert_called_once()
        assert result == mock_data_access

    @patch("docpipe.core.orchestration.flow_executor.get_session_info")
    def test_execute_cancelled(self, mock_session):
        """Test execution when job is cancelled."""
        mock_session.return_value = Mock(get_common_log_arguments=Mock(return_value={}), job_run_id="run_123")

        mock_orchestrator = Mock()
        mock_tracker_instance = Mock()
        mock_tracker_instance.cancel_job_run_if_cancelling.return_value = True
        mock_orchestrator.job_tracker = mock_tracker_instance
        flow_def = {"name": "Test", "dag": []}
        executor = FlowExecutor(flow_def=flow_def)

        params = {DocpipeConstants.JOB_RUN_ID: "run_123"}
        result = executor.execute(orchestrator=mock_orchestrator, params=params)

        assert result is None
        mock_orchestrator.execute.assert_not_called()

    @patch("docpipe.core.orchestration.flow_executor.get_session_info")
    @patch("docpipe.core.orchestration.flow_executor.FlowValidator")
    def test_execute_validation_warnings_only(self, mock_validator, mock_session):
        """Test execution with validation warnings but no errors."""
        mock_session.return_value = Mock(get_common_log_arguments=Mock(return_value={}), job_run_id="run_123")

        mock_validator_instance = Mock()
        # Raise exception with warnings but no errors
        from docpipe.exceptions.error_messages import ValidationMessage

        validation_exc = FlowValidationException(errors=[], warnings=[ValidationMessage(message="Warning 1")])
        mock_validator_instance.validate.side_effect = validation_exc
        mock_validator.return_value = mock_validator_instance

        mock_orchestrator = Mock()
        mock_orchestrator.job_stats_service = None  # Explicitly set to None
        mock_tracker_instance = Mock()
        mock_tracker_instance.cancel_job_run_if_cancelling.return_value = False
        mock_orchestrator.job_tracker = mock_tracker_instance
        mock_orchestrator.flow_execution_event_handler = Mock(job_log_path="/tmp/test.log")
        mock_orchestrator.execute.return_value = Mock()

        flow_def = {"name": "Test", "dag": []}
        executor = FlowExecutor(flow_def=flow_def)

        params = {DocpipeConstants.JOB_RUN_ID: "run_123"}
        # Should not raise exception, just log warning
        executor.execute(orchestrator=mock_orchestrator, params=params)

        mock_orchestrator.execute.assert_called_once()

    @patch("docpipe.core.orchestration.flow_executor.get_session_info")
    @patch("docpipe.core.orchestration.flow_executor.FlowValidator")
    def test_execute_validation_errors(self, mock_validator, mock_session):
        """Test execution with validation errors."""
        mock_session.return_value = Mock(get_common_log_arguments=Mock(return_value={}), job_run_id="run_123")

        mock_validator_instance = Mock()
        from docpipe.exceptions.error_messages import ValidationMessage

        validation_exc = FlowValidationException(errors=[ValidationMessage(message="Error 1")], warnings=[])
        mock_validator_instance.validate.side_effect = validation_exc
        mock_validator.return_value = mock_validator_instance

        mock_orchestrator = Mock()
        mock_orchestrator.job_stats_service = None  # Explicitly set to None
        mock_tracker_instance = Mock()
        mock_tracker_instance.cancel_job_run_if_cancelling.return_value = False
        mock_orchestrator.job_tracker = mock_tracker_instance
        mock_orchestrator.flow_execution_event_handler = Mock(job_log_path="/tmp/test.log")
        flow_def = {"name": "Test", "dag": []}
        executor = FlowExecutor(flow_def=flow_def)

        params = {DocpipeConstants.JOB_RUN_ID: "run_123"}

        with pytest.raises(FlowValidationException):
            executor.execute(orchestrator=mock_orchestrator, params=params)

    @patch("docpipe.core.orchestration.flow_executor.get_session_info")
    @patch("docpipe.core.orchestration.flow_executor.FlowValidator")
    def test_execute_orchestrator_exception(self, mock_validator, mock_session):
        """Test execution when orchestrator raises exception."""
        mock_session.return_value = Mock(get_common_log_arguments=Mock(return_value={}), job_run_id="run_123")

        mock_validator_instance = Mock()
        mock_validator.return_value = mock_validator_instance

        mock_orchestrator = Mock()
        mock_orchestrator.job_stats_service = None  # Explicitly set to None
        mock_tracker_instance = Mock()
        mock_tracker_instance.cancel_job_run_if_cancelling.return_value = False
        mock_orchestrator.job_tracker = mock_tracker_instance
        mock_orchestrator.flow_execution_event_handler = Mock(job_log_path="/tmp/test.log")
        mock_orchestrator.execute.side_effect = Exception("Execution failed")

        flow_def = {"name": "Test", "dag": []}
        executor = FlowExecutor(flow_def=flow_def)

        params = {DocpipeConstants.JOB_RUN_ID: "run_123"}

        with pytest.raises(Exception, match="Execution failed"):
            executor.execute(orchestrator=mock_orchestrator, params=params)

    @patch("docpipe.core.orchestration.flow_executor.get_session_info")
    @patch("docpipe.core.orchestration.flow_executor.FlowValidator")
    def test_execute_injects_available_features_into_node_config(self, mock_validator, mock_session):
        """Propagated available_features are written directly into each node's config dict."""
        mock_session.return_value = Mock(
            get_common_log_arguments=Mock(return_value={}),
            job_run_id="run_123",
            job_id="job_123",
        )

        propagated_features = {
            "embeddings": {
                "available_for_vector_db": True,
                "type": "vector",
            }
        }
        mock_validator_instance = Mock()
        mock_validator_instance.propagate_features_per_node.return_value = {
            "node-2": {OperatorConstants.Config.AVAILABLE_FEATURES: propagated_features}
        }
        mock_validator.return_value = mock_validator_instance

        mock_orchestrator = Mock()
        mock_orchestrator.job_stats_service = None
        mock_tracker_instance = Mock()
        mock_tracker_instance.cancel_job_run_if_cancelling.return_value = False
        mock_orchestrator.job_tracker = mock_tracker_instance
        mock_orchestrator.flow_execution_event_handler = Mock(job_log_path="/tmp/test.log")
        mock_orchestrator.execute.return_value = Mock()

        node: dict[str, Any] = {"id": "node-2"}
        flow_def = {"name": "Test", "global_config": {}, "dag": [node]}
        executor = FlowExecutor(flow_def=flow_def)

        params = {DocpipeConstants.JOB_RUN_ID: "run_123", DocpipeConstants.JOB_ID: "job_123"}
        executor.execute(orchestrator=mock_orchestrator, params=params)

        # available_features must be injected directly into the node's config dict,
        # not tunnelled through params or global_config.
        node_config: dict[str, Any] = node.get("config", {})
        assert node_config.get(OperatorConstants.Config.AVAILABLE_FEATURES) == propagated_features
        assert "_propagated_node_features" not in params
        mock_validator_instance.propagate_features_per_node.assert_called_once_with(
            flow_def=flow_def,
            global_config={},
        )

    @patch("docpipe.core.orchestration.flow_executor.get_session_info")
    def test_cancel(self, mock_session):
        """Test cancel method."""
        mock_session.return_value = Mock(get_common_log_arguments=Mock(return_value={}))

        mock_orchestrator = Mock()
        flow_def = {"name": "Test", "dag": []}
        executor = FlowExecutor(flow_def=flow_def, orchestrator=mock_orchestrator)

        executor.cancel()

        mock_orchestrator.cancel.assert_called_once()

    @patch("docpipe.core.orchestration.flow_executor.get_session_info")
    def test_cancel_no_orchestrator(self, mock_session):
        """Test cancel when no orchestrator is set."""
        mock_session.return_value = Mock(get_common_log_arguments=Mock(return_value={}))

        flow_def = {"name": "Test", "dag": []}
        executor = FlowExecutor(flow_def=flow_def)

        # Should not raise exception
        executor.cancel()

    @patch("docpipe.core.orchestration.flow_executor.get_session_info")
    def test_pause(self, mock_session):
        """Test pause method."""
        mock_session.return_value = Mock(get_common_log_arguments=Mock(return_value={}))

        mock_orchestrator = Mock()
        flow_def = {"name": "Test", "dag": []}
        executor = FlowExecutor(flow_def=flow_def, orchestrator=mock_orchestrator)

        executor.pause()

        mock_orchestrator.pause.assert_called_once()

    @patch("docpipe.core.orchestration.flow_executor.get_session_info")
    def test_resume(self, mock_session):
        """Test resume method."""
        mock_session.return_value = Mock(get_common_log_arguments=Mock(return_value={}))

        mock_orchestrator = Mock()
        flow_def = {"name": "Test", "dag": []}
        executor = FlowExecutor(flow_def=flow_def, orchestrator=mock_orchestrator)

        executor.resume()

        mock_orchestrator.resume.assert_called_once()

    @patch("docpipe.core.orchestration.flow_executor.get_session_info")
    @patch("docpipe.core.orchestration.flow_executor.FlowValidator")
    def test_validate(self, mock_validator, mock_session):
        """Test validation through execute method."""
        mock_session.return_value = Mock(get_common_log_arguments=Mock(return_value={}), job_run_id="run_123")

        mock_validator_instance = Mock()
        mock_validator.return_value = mock_validator_instance

        mock_orchestrator = Mock()
        mock_orchestrator.job_stats_service = None  # Explicitly set to None
        mock_tracker_instance = Mock()
        mock_tracker_instance.cancel_job_run_if_cancelling.return_value = False
        mock_orchestrator.job_tracker = mock_tracker_instance
        mock_orchestrator.flow_execution_event_handler = Mock(job_log_path="/tmp/test.log")
        mock_orchestrator.execute.return_value = Mock()

        flow_def = {"name": "Test", "dag": []}
        executor = FlowExecutor(flow_def=flow_def)

        params = {"key": "value"}
        executor.execute(orchestrator=mock_orchestrator, params=params)

        # Verify that FlowValidator.validate was called
        mock_validator_instance.validate.assert_called_once_with(flow_def=flow_def, params=params)

    @patch("docpipe.core.orchestration.flow_executor.get_session_info")
    def test_start_diagnostic_collection_enabled(self, mock_session):
        """Test starting diagnostic collection when enabled."""
        mock_session.return_value = Mock(get_common_log_arguments=Mock(return_value={}))

        flow_def = {"name": "Test", "dag": []}

        with patch.dict("os.environ", {DocpipeConstants.TRACE_MEMORY_ALLOCATIONS: "true"}):
            with patch("tracemalloc.start") as mock_tracemalloc:
                executor = FlowExecutor(flow_def=flow_def)
                executor.start_diagnostic_collection()

                mock_tracemalloc.assert_called_once()

    @patch("docpipe.core.orchestration.flow_executor.get_session_info")
    def test_start_diagnostic_collection_disabled(self, mock_session):
        """Test starting diagnostic collection when disabled."""
        mock_session.return_value = Mock(get_common_log_arguments=Mock(return_value={}))

        flow_def = {"name": "Test", "dag": []}

        with patch.dict("os.environ", {}, clear=True):
            with patch("tracemalloc.start") as mock_tracemalloc:
                executor = FlowExecutor(flow_def=flow_def)
                executor.start_diagnostic_collection()

                mock_tracemalloc.assert_not_called()

    @patch("docpipe.core.orchestration.flow_executor.get_session_info")
    def test_stop_diagnostic_collection(self, mock_session):
        """Test stopping diagnostic collection."""
        mock_session.return_value = Mock(get_common_log_arguments=Mock(return_value={}))

        flow_def = {"name": "Test", "dag": []}

        with patch.dict("os.environ", {DocpipeConstants.TRACE_MEMORY_ALLOCATIONS: "true"}):
            with patch("tracemalloc.stop") as mock_tracemalloc:
                executor = FlowExecutor(flow_def=flow_def)
                executor.stop_diagnostic_collection()

                mock_tracemalloc.assert_called_once()

    @patch("docpipe.core.orchestration.flow_executor.get_session_info")
    @patch("docpipe.core.orchestration.flow_executor.gc")
    def test_print_diagnostic_info(self, mock_gc, mock_session):
        """Test printing diagnostic info."""
        mock_session.return_value = Mock(get_common_log_arguments=Mock(return_value={}))
        mock_gc.get_stats.return_value = [{"collections": 10}]

        flow_def = {"name": "Test", "dag": []}
        executor = FlowExecutor(flow_def=flow_def)

        # Should not raise exception
        executor.print_diagnostic_info()

        mock_gc.get_stats.assert_called_once()

    @patch("docpipe.core.orchestration.flow_executor.get_session_info")
    @patch("docpipe.core.orchestration.flow_executor.FlowValidator")
    def test_execute_saves_flow_definition(self, mock_validator, mock_session):
        """Test that execute() calls job_stats_service.save_flow_definition when job_id and job_run_id are provided."""
        mock_session.return_value = Mock(get_common_log_arguments=Mock(return_value={}), job_run_id=None, job_id=None)

        mock_validator_instance = Mock()
        mock_validator.return_value = mock_validator_instance

        mock_job_stats_service = Mock()
        # Mock cancel_job_run_if_cancelling to return False so execution continues
        mock_job_stats_service.cancel_job_run_if_cancelling.return_value = False

        mock_orchestrator = Mock()
        mock_orchestrator.job_stats_service = mock_job_stats_service
        mock_orchestrator.flow_execution_event_handler = Mock(job_log_path="/tmp/test.log")
        mock_orchestrator.execute.return_value = Mock()
        mock_orchestrator.initialize = Mock()

        flow_def = {"name": "Test Flow", "dag": [{"id": "node1"}]}
        original_flow = {"flow_name": "Test Flow", "flow": [{"name": "node1", "type": "test"}]}
        executor = FlowExecutor(flow_def=flow_def, original_flow_def=original_flow)

        job_id = "test_job_789"
        job_run_id = "test_run_012"
        params = {DocpipeConstants.JOB_ID: job_id, DocpipeConstants.JOB_RUN_ID: job_run_id}

        executor.execute(orchestrator=mock_orchestrator, params=params)

        # Verify job_stats_service.save_flow_definition was called with original flow
        mock_job_stats_service.save_flow_definition.assert_called_once_with(
            job_id=job_id, job_run_id=job_run_id, flow_definition=original_flow, params=params
        )

    @patch("docpipe.core.orchestration.flow_executor.get_session_info")
    @patch("docpipe.core.orchestration.flow_executor.FlowValidator")
    def test_execute_skips_save_when_no_job_ids(self, mock_validator, mock_session):
        """Test that execute() skips saving when job_id or job_run_id is missing."""
        mock_session.return_value = Mock(get_common_log_arguments=Mock(return_value={}), job_run_id=None, job_id=None)

        mock_validator_instance = Mock()
        mock_validator.return_value = mock_validator_instance

        mock_job_stats_service = Mock()
        mock_orchestrator = Mock()
        mock_orchestrator.job_stats_service = mock_job_stats_service
        mock_orchestrator.flow_execution_event_handler = Mock(job_log_path="/tmp/test.log")
        mock_orchestrator.execute.return_value = Mock()

        flow_def = {"name": "Test", "dag": []}
        executor = FlowExecutor(flow_def=flow_def)

        # Execute without job_id and job_run_id
        executor.execute(orchestrator=mock_orchestrator, params={})

        # Verify save_flow_definition was not called
        mock_job_stats_service.save_flow_definition.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


# ---------------------------------------------------------------------------
# Additional FlowExecutor tests (merged from test_flow_executor_coverage.py)
# ---------------------------------------------------------------------------


def _make_executor_simple(flow_def=None):
    """Build a FlowExecutor without needing a patched session."""
    with patch("docpipe.core.orchestration.flow_executor.get_session_info") as mock_session:
        mock_session.return_value = Mock(
            get_common_log_arguments=Mock(return_value={}),
            job_run_id=None,
            job_id=None,
        )
        return FlowExecutor(flow_def=flow_def or {"name": "test", "dag": []})


class TestFlowExecutorNoOrchestrator:
    def test_execute_raises_when_no_orchestrator(self):
        executor = _make_executor_simple()
        with pytest.raises(ValueError, match="No orchestrator"):
            executor.execute(orchestrator=None, params={})


class TestFlowExecutorCancelPauseResume:
    def test_cancel_with_orchestrator(self):
        executor = _make_executor_simple()
        mock_orch = MagicMock()
        executor._FlowExecutor__orchestrator = mock_orch
        executor.cancel()
        mock_orch.cancel.assert_called_once()

    def test_cancel_without_orchestrator(self):
        executor = _make_executor_simple()
        executor._FlowExecutor__orchestrator = None
        executor.cancel()  # should not raise

    def test_pause_with_orchestrator(self):
        executor = _make_executor_simple()
        mock_orch = MagicMock()
        executor._FlowExecutor__orchestrator = mock_orch
        executor.pause()
        mock_orch.pause.assert_called_once()

    def test_resume_with_orchestrator(self):
        executor = _make_executor_simple()
        mock_orch = MagicMock()
        executor._FlowExecutor__orchestrator = mock_orch
        executor.resume()
        mock_orch.resume.assert_called_once()


class TestFlowExecutorDiagnostics:
    def test_start_stop_diagnostic_no_trace(self):
        executor = _make_executor_simple()
        executor.trace_memory_allocations = False
        executor.start_diagnostic_collection()
        executor.stop_diagnostic_collection()

    def test_print_diagnostic_no_trace(self):
        executor = _make_executor_simple()
        executor.trace_memory_allocations = False
        executor.print_diagnostic_info()  # should not raise

    def test_print_diagnostic_with_trace(self):
        import tracemalloc

        executor = _make_executor_simple()
        executor.trace_memory_allocations = True
        tracemalloc.start()
        try:
            snapshot = tracemalloc.take_snapshot()
            executor.print_diagnostic_info(snapshot=snapshot, limit=2)
        finally:
            tracemalloc.stop()


class TestFlowExecutorStr:
    def test_str_representation(self):
        executor = _make_executor_simple(flow_def={"name": "MyFlow", "description": "Desc", "dag": []})
        result = str(executor)
        assert "MyFlow" in result


class TestFlowExecutorSaveFlowDefinitionError:
    @patch("docpipe.core.orchestration.flow_executor.get_session_info")
    def test_execute_continues_when_save_flow_def_fails(self, mock_session):
        mock_session.return_value = Mock(
            get_common_log_arguments=Mock(return_value={}),
            job_run_id="run1",
            job_id="job1",
        )
        executor = FlowExecutor(flow_def={"name": "f", "dag": []})

        mock_orch = MagicMock()
        mock_orch.job_stats_service = MagicMock()
        mock_orch.job_stats_service.cancel_job_run_if_cancelling.return_value = False
        mock_orch.job_stats_service.save_flow_definition.side_effect = RuntimeError("disk full")
        mock_orch.execute.return_value = None
        mock_orch.flow_execution_event_handler.job_log_path = "/tmp/log"

        with patch("docpipe.core.orchestration.flow_executor.FlowValidator") as mock_val:
            mock_val.return_value.validate.return_value = None
            executor.execute(
                orchestrator=mock_orch,
                params={DocpipeConstants.JOB_ID: "job1", DocpipeConstants.JOB_RUN_ID: "run1"},
            )
        mock_orch.execute.assert_called_once()
