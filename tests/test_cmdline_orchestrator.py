from typing import Any
import os
import unittest
import tempfile
from unittest.mock import patch, MagicMock

from core.orchestrator.cmdline.cmd_line_orchestrator import run_command_line_executor, load_flow_definition
from common.util.constants import DatasiftConstants, OperatorConstants
from common.exceptions.datasift_exceptions import FlowValidationException


class TestCommandLineOrchestrator(unittest.TestCase):

    def setUp(self):
        os.environ["test_mode"] = "True"
        os.environ[DatasiftConstants.DATA_FOLDER] = "/tmp/data"

    def test_basic_flow(self):
        """
        Test orchestrating a basic pipeline with two operators
        """
        flow_def = {
            "dag": [
                {
                    "id": "e9c41958-2d27-4c02-ab03-789e031b9500",
                    "name": "ingest",
                    OperatorConstants.OPERATOR: OperatorConstants.INGEST_LOCAL,
                    "config": {
                        "input_folder": "tests/fixtures/customer_support_docs",
                        "include_filter": "txt"},
                    "input_edges": [],
                    "output_edges": [{"node_id_ref": "e9c41958-2d27-4c02-ab03-789e031b9501"}]

                },
                {
                    "id": "e9c41958-2d27-4c02-ab03-789e031b9501",
                    "name": "Sleep",
                    OperatorConstants.OPERATOR: OperatorConstants.NOOP,
                    "config": {"sleep_sec": 2},
                    "input_edges": [{"node_id_ref": "e9c41958-2d27-4c02-ab03-789e031b9500"}],
                    "output_edges": []
                }
            ]
        }

        run_command_line_executor(flow_def=flow_def)
        
    def test_load_flow_definition(self):
        """
        Test loading a flow definition from a file
        """
        from core.orchestrator.cmdline.cmd_line_orchestrator import load_flow_definition
        filepath = "tests/flow_local.json"

        flow_def = load_flow_definition(file_path=filepath)
        assert flow_def is not None
        
    def test_invalid_flow_definition(self):
        """
        Test handling of invalid flow definition (missing 'sequence' or 'dag')
        """
        # Create an invalid flow definition without sequence or dag
        invalid_flow_def = {
            "name": "invalid flow",
            "flow_id": "12345",
            "description": "This flow is invalid"
        }
        
        # Test that the orchestrator raises an exception for invalid flow
        with self.assertRaises(FlowValidationException):
            run_command_line_executor(flow_def=invalid_flow_def)
            
    @patch('builtins.open')
    def test_file_not_found_exception(self, mock_open):
        """
        Test handling of FileNotFoundError in load_flow_definition
        """
        # Mock open to raise FileNotFoundError
        mock_open.side_effect = FileNotFoundError("File not found")
        
        # Use a non-existent file path
        file_path = "non_existent_file.json"
        
        # Test with sys.exit patched to avoid test termination
        with patch('sys.exit') as mock_exit:
            load_flow_definition(file_path=file_path)
            # Verify that sys.exit was called with exit code 1
            mock_exit.assert_called_once_with(1)
            
    def test_invalid_json_exception(self):
        """
        Test handling of invalid JSON in load_flow_definition
        """
        # Create a temporary file with invalid JSON content
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            temp_file.write("{ This is not valid JSON }")
            temp_file_path = temp_file.name
        
        try:
            # Test with sys.exit patched to avoid test termination
            with patch('sys.exit') as mock_exit:
                load_flow_definition(file_path=temp_file_path)
                # Verify that sys.exit was called with exit code 1
                mock_exit.assert_called_once_with(1)
        finally:
            # Clean up the temporary file
            os.unlink(temp_file_path)
            
    @patch('core.orchestrator.orchestrator_factory.OrchestratorFactory.create_orchestrator')
    def test_flow_execution_failure(self, mock_create_orchestrator):
        """
        Test handling of flow execution failure
        """
        # Create a mock orchestrator that raises an exception during execution
        mock_orchestrator = MagicMock()
        mock_orchestrator.execute.side_effect = Exception("Flow execution failed")
        mock_create_orchestrator.return_value = mock_orchestrator
        
        # Create a simple flow definition
        flow_def = {
            "dag": [
                {
                    "id": "test-id",
                    "name": "test-operator",
                    OperatorConstants.OPERATOR: "test-operator",
                    "config": {}
                }
            ]
        }
        
        # Test that the exception is propagated
        with self.assertRaises(Exception):
            run_command_line_executor(flow_def=flow_def)

