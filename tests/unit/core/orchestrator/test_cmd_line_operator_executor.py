"""Unit tests for cmd_line_operator_executor module."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from core.orchestrator.cmdline.cmd_line_operator_executor import CommandLineOperatorExecutor


class TestCommandLineOperatorExecutor:
    """Test CommandLineOperatorExecutor class."""

    @patch("core.orchestrator.cmdline.cmd_line_operator_executor.PythonOperatorExecutor.__init__")
    def test_init_calls_parent(self, mock_parent_init):
        """Test that initialization calls parent class."""
        mock_parent_init.return_value = None
        
        executor = CommandLineOperatorExecutor(
            name="test_executor",
            operator="test_operator",
            params={"param1": "value1"}
        )
        
        mock_parent_init.assert_called_once_with(
            "test_executor",
            "test_operator",
            {"param1": "value1"}
        )

    @patch("core.orchestrator.cmdline.cmd_line_operator_executor.PythonOperatorExecutor.__init__")
    def test_init_with_empty_params(self, mock_parent_init):
        """Test initialization with empty params."""
        mock_parent_init.return_value = None
        
        executor = CommandLineOperatorExecutor(
            name="executor",
            operator="operator",
            params={}
        )
        
        mock_parent_init.assert_called_once_with("executor", "operator", {})

    @patch("core.orchestrator.cmdline.cmd_line_operator_executor.PythonOperatorExecutor.__init__")
    def test_init_with_complex_params(self, mock_parent_init):
        """Test initialization with complex parameters."""
        mock_parent_init.return_value = None
        
        complex_params = {
            "string_param": "value",
            "int_param": 42,
            "list_param": [1, 2, 3],
            "dict_param": {"nested": "value"}
        }
        
        executor = CommandLineOperatorExecutor(
            name="complex_executor",
            operator="complex_operator",
            params=complex_params
        )
        
        mock_parent_init.assert_called_once_with(
            "complex_executor",
            "complex_operator",
            complex_params
        )

    def test_inherits_from_python_operator_executor(self):
        """Test that CommandLineOperatorExecutor inherits from PythonOperatorExecutor."""
        from core.orchestrator.python.python_operator_executor import PythonOperatorExecutor
        
        # Verify inheritance
        assert issubclass(CommandLineOperatorExecutor, PythonOperatorExecutor)

    @patch("core.orchestrator.cmdline.cmd_line_operator_executor.PythonOperatorExecutor.__init__")
    @patch("core.orchestrator.cmdline.cmd_line_operator_executor.PythonOperatorExecutor.get_operator")
    def test_can_call_parent_methods(self, mock_get_operator, mock_init):
        """Test that parent class methods are accessible."""
        mock_init.return_value = None
        mock_operator = Mock()
        mock_get_operator.return_value = mock_operator
        
        executor = CommandLineOperatorExecutor(
            name="test",
            operator="test_op",
            params={}
        )
        
        # Should be able to call parent methods
        # This verifies the inheritance chain works correctly
        assert hasattr(executor, 'get_operator')

    @patch("core.orchestrator.cmdline.cmd_line_operator_executor.PythonOperatorExecutor.__init__")
    def test_multiple_instances(self, mock_parent_init):
        """Test creating multiple instances."""
        mock_parent_init.return_value = None
        
        executor1 = CommandLineOperatorExecutor("exec1", "op1", {"p1": "v1"})
        executor2 = CommandLineOperatorExecutor("exec2", "op2", {"p2": "v2"})
        
        assert mock_parent_init.call_count == 2
        
        # Verify each instance was initialized with correct params
        calls = mock_parent_init.call_args_list
        assert calls[0][0] == ("exec1", "op1", {"p1": "v1"})
        assert calls[1][0] == ("exec2", "op2", {"p2": "v2"})


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

# Made with Bob
