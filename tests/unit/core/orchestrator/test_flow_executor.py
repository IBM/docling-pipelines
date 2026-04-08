"""Unit tests for flow_executor module."""

import json
import tempfile
from unittest.mock import Mock, patch

import pytest

from common.constants.constants import DatasiftConstants
from common.exceptions.datasift_exceptions import FlowValidationException
from core.orchestrator.flow_executor import FlowExecutor


class TestFlowExecutor:
    """Test FlowExecutor class."""

    @patch("core.orchestrator.flow_executor.get_session_info")
    def test_init_with_flow_def_file(self, mock_session):
        """Test initialization with flow definition file."""
        mock_session.return_value = Mock(get_common_log_arguments=Mock(return_value={}))
        
        flow_data = {
            "flow": {
                "name": "Test Flow",
                "description": "Test Description",
                "dag": []
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(flow_data, f)
            temp_path = f.name
        
        try:
            executor = FlowExecutor(flow_def_file=temp_path)
            
            assert executor.flow_def["name"] == "Test Flow"
            assert executor.flow_def["description"] == "Test Description"
        finally:
            import os
            os.unlink(temp_path)

    @patch("core.orchestrator.flow_executor.get_session_info")
    def test_init_with_flow_def_dict(self, mock_session):
        """Test initialization with flow definition dict."""
        mock_session.return_value = Mock(get_common_log_arguments=Mock(return_value={}))
        
        flow_def = {
            "name": "Direct Flow",
            "description": "Direct Description",
            "dag": []
        }
        
        executor = FlowExecutor(flow_def=flow_def)
        
        assert executor.flow_def["name"] == "Direct Flow"
        assert executor.flow_def["description"] == "Direct Description"

    @patch("core.orchestrator.flow_executor.get_session_info")
    def test_init_with_orchestrator(self, mock_session):
        """Test initialization with orchestrator."""
        mock_session.return_value = Mock(get_common_log_arguments=Mock(return_value={}))
        mock_orchestrator = Mock()
        
        flow_def = {"name": "Test", "dag": []}
        executor = FlowExecutor(flow_def=flow_def, orchestrator=mock_orchestrator)
        
        assert executor._FlowExecutor__orchestrator == mock_orchestrator

    @patch("core.orchestrator.flow_executor.get_session_info")
    def test_str_representation(self, mock_session):
        """Test string representation of FlowExecutor."""
        mock_session.return_value = Mock(get_common_log_arguments=Mock(return_value={}))
        
        flow_def = {
            "name": "My Flow",
            "description": "My Description",
            "dag": []
        }
        
        executor = FlowExecutor(flow_def=flow_def)
        result = str(executor)
        
        assert "My Flow" in result
        assert "My Description" in result

    @patch("core.orchestrator.flow_executor.get_session_info")
    @patch("core.orchestrator.flow_executor.FlowValidator")
    def test_execute_basic(self, mock_validator, mock_session):
        """Test basic flow execution."""
        mock_session.return_value = Mock(
            get_common_log_arguments=Mock(return_value={}),
            job_run_id="run_123"
        )
        
        mock_validator_instance = Mock()
        mock_validator.return_value = mock_validator_instance
        
        mock_orchestrator = Mock()
        mock_tracker_instance = Mock()
        mock_tracker_instance.cancel_job_run_if_cancelling.return_value = False
        mock_orchestrator.job_tracker = mock_tracker_instance
        mock_data_access = Mock()
        mock_orchestrator.execute.return_value = mock_data_access
        
        flow_def = {"name": "Test", "dag": [{"id": "node1"}]}
        executor = FlowExecutor(flow_def=flow_def)
        
        params = {DatasiftConstants.JOB_RUN_ID: "run_123"}
        result = executor.execute(orchestrator=mock_orchestrator, params=params)
        
        mock_validator_instance.validate.assert_called_once()
        mock_orchestrator.execute.assert_called_once()
        assert result == mock_data_access

    @patch("core.orchestrator.flow_executor.get_session_info")
    def test_execute_cancelled(self, mock_session):
        """Test execution when job is cancelled."""
        mock_session.return_value = Mock(
            get_common_log_arguments=Mock(return_value={}),
            job_run_id="run_123"
        )
        
        mock_orchestrator = Mock()
        mock_tracker_instance = Mock()
        mock_tracker_instance.cancel_job_run_if_cancelling.return_value = True
        mock_orchestrator.job_tracker = mock_tracker_instance
        flow_def = {"name": "Test", "dag": []}
        executor = FlowExecutor(flow_def=flow_def)
        
        params = {DatasiftConstants.JOB_RUN_ID: "run_123"}
        result = executor.execute(orchestrator=mock_orchestrator, params=params)
        
        assert result is None
        mock_orchestrator.execute.assert_not_called()

    @patch("core.orchestrator.flow_executor.get_session_info")
    @patch("core.orchestrator.flow_executor.FlowValidator")
    def test_execute_validation_warnings_only(self, mock_validator, mock_session):
        """Test execution with validation warnings but no errors."""
        mock_session.return_value = Mock(
            get_common_log_arguments=Mock(return_value={}),
            job_run_id="run_123"
        )
        
        mock_validator_instance = Mock()
        # Raise exception with warnings but no errors
        from common.exceptions.error_messages import ValidationMessage
        validation_exc = FlowValidationException(
            errors=[],
            warnings=[ValidationMessage(message="Warning 1")]
        )
        mock_validator_instance.validate.side_effect = validation_exc
        mock_validator.return_value = mock_validator_instance
        
        mock_orchestrator = Mock()
        mock_tracker_instance = Mock()
        mock_tracker_instance.cancel_job_run_if_cancelling.return_value = False
        mock_orchestrator.job_tracker = mock_tracker_instance
        mock_orchestrator.execute.return_value = Mock()
        
        flow_def = {"name": "Test", "dag": []}
        executor = FlowExecutor(flow_def=flow_def)
        
        params = {DatasiftConstants.JOB_RUN_ID: "run_123"}
        # Should not raise exception, just log warning
        result = executor.execute(orchestrator=mock_orchestrator, params=params)
        
        mock_orchestrator.execute.assert_called_once()

    @patch("core.orchestrator.flow_executor.get_session_info")
    @patch("core.orchestrator.flow_executor.FlowValidator")
    def test_execute_validation_errors(self, mock_validator, mock_session):
        """Test execution with validation errors."""
        mock_session.return_value = Mock(
            get_common_log_arguments=Mock(return_value={}),
            job_run_id="run_123"
        )
        
        mock_validator_instance = Mock()
        from common.exceptions.error_messages import ValidationMessage
        validation_exc = FlowValidationException(
            errors=[ValidationMessage(message="Error 1")],
            warnings=[]
        )
        mock_validator_instance.validate.side_effect = validation_exc
        mock_validator.return_value = mock_validator_instance
        
        mock_orchestrator = Mock()
        mock_tracker_instance = Mock()
        mock_tracker_instance.cancel_job_run_if_cancelling.return_value = False
        mock_orchestrator.job_tracker = mock_tracker_instance
        flow_def = {"name": "Test", "dag": []}
        executor = FlowExecutor(flow_def=flow_def)
        
        params = {DatasiftConstants.JOB_RUN_ID: "run_123"}
        
        with pytest.raises(FlowValidationException):
            executor.execute(orchestrator=mock_orchestrator, params=params)

    @patch("core.orchestrator.flow_executor.get_session_info")
    @patch("core.orchestrator.flow_executor.FlowValidator")
    def test_execute_orchestrator_exception(self, mock_validator, mock_session):
        """Test execution when orchestrator raises exception."""
        mock_session.return_value = Mock(
            get_common_log_arguments=Mock(return_value={}),
            job_run_id="run_123"
        )
        
        mock_validator_instance = Mock()
        mock_validator.return_value = mock_validator_instance
        
        mock_orchestrator = Mock()
        mock_tracker_instance = Mock()
        mock_tracker_instance.cancel_job_run_if_cancelling.return_value = False
        mock_orchestrator.job_tracker = mock_tracker_instance
        mock_orchestrator.execute.side_effect = Exception("Execution failed")
        
        flow_def = {"name": "Test", "dag": []}
        executor = FlowExecutor(flow_def=flow_def)
        
        params = {DatasiftConstants.JOB_RUN_ID: "run_123"}
        
        with pytest.raises(Exception, match="Execution failed"):
            executor.execute(orchestrator=mock_orchestrator, params=params)

    @patch("core.orchestrator.flow_executor.get_session_info")
    def test_cancel(self, mock_session):
        """Test cancel method."""
        mock_session.return_value = Mock(get_common_log_arguments=Mock(return_value={}))
        
        mock_orchestrator = Mock()
        flow_def = {"name": "Test", "dag": []}
        executor = FlowExecutor(flow_def=flow_def, orchestrator=mock_orchestrator)
        
        executor.cancel()
        
        mock_orchestrator.cancel.assert_called_once()

    @patch("core.orchestrator.flow_executor.get_session_info")
    def test_cancel_no_orchestrator(self, mock_session):
        """Test cancel when no orchestrator is set."""
        mock_session.return_value = Mock(get_common_log_arguments=Mock(return_value={}))
        
        flow_def = {"name": "Test", "dag": []}
        executor = FlowExecutor(flow_def=flow_def)
        
        # Should not raise exception
        executor.cancel()

    @patch("core.orchestrator.flow_executor.get_session_info")
    def test_pause(self, mock_session):
        """Test pause method."""
        mock_session.return_value = Mock(get_common_log_arguments=Mock(return_value={}))
        
        mock_orchestrator = Mock()
        flow_def = {"name": "Test", "dag": []}
        executor = FlowExecutor(flow_def=flow_def, orchestrator=mock_orchestrator)
        
        executor.pause()
        
        mock_orchestrator.pause.assert_called_once()

    @patch("core.orchestrator.flow_executor.get_session_info")
    def test_resume(self, mock_session):
        """Test resume method."""
        mock_session.return_value = Mock(get_common_log_arguments=Mock(return_value={}))
        
        mock_orchestrator = Mock()
        flow_def = {"name": "Test", "dag": []}
        executor = FlowExecutor(flow_def=flow_def, orchestrator=mock_orchestrator)
        
        executor.resume()
        
        mock_orchestrator.resume.assert_called_once()

    @patch("core.orchestrator.flow_executor.get_session_info")
    @patch("core.orchestrator.flow_executor.FlowValidator")
    def test_validate(self, mock_validator, mock_session):
        """Test validation through execute method."""
        mock_session.return_value = Mock(
            get_common_log_arguments=Mock(return_value={}),
            job_run_id="run_123"
        )
        
        mock_validator_instance = Mock()
        mock_validator.return_value = mock_validator_instance
        
        mock_orchestrator = Mock()
        mock_tracker_instance = Mock()
        mock_tracker_instance.cancel_job_run_if_cancelling.return_value = False
        mock_orchestrator.job_tracker = mock_tracker_instance
        mock_orchestrator.execute.return_value = Mock()
        
        flow_def = {"name": "Test", "dag": []}
        executor = FlowExecutor(flow_def=flow_def)
        
        params = {"key": "value"}
        executor.execute(orchestrator=mock_orchestrator, params=params)
        
        # Verify that FlowValidator.validate was called
        mock_validator_instance.validate.assert_called_once_with(flow_def=flow_def, params=params)

    @patch("core.orchestrator.flow_executor.get_session_info")
    def test_start_diagnostic_collection_enabled(self, mock_session):
        """Test starting diagnostic collection when enabled."""
        mock_session.return_value = Mock(get_common_log_arguments=Mock(return_value={}))
        
        flow_def = {"name": "Test", "dag": []}
        
        with patch.dict('os.environ', {DatasiftConstants.TRACE_MEMORY_ALLOCATIONS: 'true'}):
            with patch('tracemalloc.start') as mock_tracemalloc:
                executor = FlowExecutor(flow_def=flow_def)
                executor.start_diagnostic_collection()
                
                mock_tracemalloc.assert_called_once()

    @patch("core.orchestrator.flow_executor.get_session_info")
    def test_start_diagnostic_collection_disabled(self, mock_session):
        """Test starting diagnostic collection when disabled."""
        mock_session.return_value = Mock(get_common_log_arguments=Mock(return_value={}))
        
        flow_def = {"name": "Test", "dag": []}
        
        with patch.dict('os.environ', {}, clear=True):
            with patch('tracemalloc.start') as mock_tracemalloc:
                executor = FlowExecutor(flow_def=flow_def)
                executor.start_diagnostic_collection()
                
                mock_tracemalloc.assert_not_called()

    @patch("core.orchestrator.flow_executor.get_session_info")
    def test_stop_diagnostic_collection(self, mock_session):
        """Test stopping diagnostic collection."""
        mock_session.return_value = Mock(get_common_log_arguments=Mock(return_value={}))
        
        flow_def = {"name": "Test", "dag": []}
        
        with patch.dict('os.environ', {DatasiftConstants.TRACE_MEMORY_ALLOCATIONS: 'true'}):
            with patch('tracemalloc.stop') as mock_tracemalloc:
                executor = FlowExecutor(flow_def=flow_def)
                executor.stop_diagnostic_collection()
                
                mock_tracemalloc.assert_called_once()

    @patch("core.orchestrator.flow_executor.get_session_info")
    @patch("core.orchestrator.flow_executor.gc")
    def test_print_diagnostic_info(self, mock_gc, mock_session):
        """Test printing diagnostic info."""
        mock_session.return_value = Mock(get_common_log_arguments=Mock(return_value={}))
        mock_gc.get_stats.return_value = [{"collections": 10}]
        
        flow_def = {"name": "Test", "dag": []}
        executor = FlowExecutor(flow_def=flow_def)
        
        # Should not raise exception
        executor.print_diagnostic_info()
        
        mock_gc.get_stats.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

# Made with Bob
