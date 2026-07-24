"""Unit tests for cmd_line_operator_executor module."""

from unittest.mock import Mock, patch

import pytest

from docpipe.core.orchestration.cmdline.cmd_line_operator_executor import (
    CommandLineOperatorExecutor,
)


class TestCommandLineOperatorExecutor:
    """Test CommandLineOperatorExecutor class."""

    @patch("docpipe.core.orchestration.cmdline.cmd_line_operator_executor.PythonOperatorExecutor.__init__")
    def test_init_calls_parent(self, mock_parent_init):
        """Test that initialization calls parent class."""
        mock_parent_init.return_value = None

        _ = CommandLineOperatorExecutor(name="test_executor", operator="test_operator", params={"param1": "value1"})

        mock_parent_init.assert_called_once_with(
            name="test_executor",
            operator="test_operator",
            params={"param1": "value1"},
            job_stats_service=None,
        )

    @patch("docpipe.core.orchestration.cmdline.cmd_line_operator_executor.PythonOperatorExecutor.__init__")
    def test_init_with_empty_params(self, mock_parent_init):
        """Test initialization with empty params."""
        mock_parent_init.return_value = None

        _ = CommandLineOperatorExecutor(name="executor", operator="operator", params={})

        mock_parent_init.assert_called_once_with(
            name="executor",
            operator="operator",
            params={},
            job_stats_service=None,
        )

    @patch("docpipe.core.orchestration.cmdline.cmd_line_operator_executor.PythonOperatorExecutor.__init__")
    def test_init_with_complex_params(self, mock_parent_init):
        """Test initialization with complex parameters."""
        mock_parent_init.return_value = None

        complex_params = {
            "string_param": "value",
            "int_param": 42,
            "list_param": [1, 2, 3],
            "dict_param": {"nested": "value"},
        }

        _ = CommandLineOperatorExecutor(name="complex_executor", operator="complex_operator", params=complex_params)

        mock_parent_init.assert_called_once_with(
            name="complex_executor",
            operator="complex_operator",
            params=complex_params,
            job_stats_service=None,
        )

    def test_inherits_from_python_operator_executor(self):
        """Test that CommandLineOperatorExecutor inherits from PythonOperatorExecutor."""
        from docpipe.core.orchestration.python.python_operator_executor import (
            PythonOperatorExecutor,
        )

        # Verify inheritance
        assert issubclass(CommandLineOperatorExecutor, PythonOperatorExecutor)

    @patch("docpipe.core.orchestration.cmdline.cmd_line_operator_executor.PythonOperatorExecutor.__init__")
    @patch("docpipe.core.orchestration.cmdline.cmd_line_operator_executor.PythonOperatorExecutor.get_operator")
    def test_can_call_parent_methods(self, mock_get_operator, mock_init):
        """Test that parent class methods are accessible."""
        mock_init.return_value = None
        mock_operator = Mock()
        mock_get_operator.return_value = mock_operator

        executor = CommandLineOperatorExecutor(name="test", operator="test_op", params={})

        # Should be able to call parent methods
        # This verifies the inheritance chain works correctly
        assert hasattr(executor, "get_operator")

    @patch("docpipe.core.orchestration.cmdline.cmd_line_operator_executor.PythonOperatorExecutor.__init__")
    def test_multiple_instances(self, mock_parent_init):
        """Test creating multiple instances."""
        mock_parent_init.return_value = None

        _ = CommandLineOperatorExecutor(name="exec1", operator="op1", params={"p1": "v1"})
        _ = CommandLineOperatorExecutor(name="exec2", operator="op2", params={"p2": "v2"})

        assert mock_parent_init.call_count == 2

        # Verify each instance was initialized with correct params (keyword args)
        calls = mock_parent_init.call_args_list
        assert calls[0].kwargs == {
            "name": "exec1",
            "operator": "op1",
            "params": {"p1": "v1"},
            "job_stats_service": None,
        }
        assert calls[1].kwargs == {
            "name": "exec2",
            "operator": "op2",
            "params": {"p2": "v2"},
            "job_stats_service": None,
        }


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
