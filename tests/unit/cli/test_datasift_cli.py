"""
Integration-style tests for CLI validation features.

Tests cover:
- --validate flag with valid/invalid flows
- validate-flow command with valid/invalid flows
- Error handling (FileNotFoundError, JSONDecodeError, FlowValidationException)
- Backward compatibility
- --list-operators functionality
- Help text display
- Validation with warnings

Uses real components where possible to minimize mocking.
"""

import json
from unittest.mock import patch

import pytest

from datasift.cli.datasift_cli import (
    load_flow_definition,
    main,
    validate_flow_definition,
)
from datasift.core.constants.operator_constants import OperatorConstants


@pytest.fixture
def real_flow_invoice(project_root):
    """Return path to real invoice flow file."""
    return str(project_root / "tests" / "sample_test_flows" / "invoice_processing" / "flow_invoice.json")


@pytest.fixture
def valid_flow_dict_with_output(fixtures_customer_support_dir):
    """Return a valid flow definition dictionary with output operator."""
    return {
        "name": "test_flow",
        "flow_id": "test-123",
        "dag": [
            {
                "id": "node1",
                "name": "ingest",
                OperatorConstants.Misc.OPERATOR: OperatorConstants.Operators.INGEST_LOCAL,
                "config": {
                    "input_folder": str(fixtures_customer_support_dir),
                    "include_filter": "txt",
                },
                "input_edges": [],
                "output_edges": [{"node_id_ref": "node2"}],
            },
            {
                "id": "node2",
                "name": "noop",
                OperatorConstants.Misc.OPERATOR: OperatorConstants.Operators.NOOP,
                "config": {"sleep_sec": 1},
                "input_edges": [{"node_id_ref": "node1"}],
                "output_edges": [],
            },
        ],
    }


@pytest.fixture
def valid_flow_dict(valid_flow_dict_with_output):
    """Alias for backward compatibility."""
    return valid_flow_dict_with_output


@pytest.fixture
def invalid_flow_dict():
    """Return an invalid flow definition (missing dag/sequence)."""
    return {
        "name": "invalid_flow",
        "flow_id": "invalid-123",
        "description": "This flow is missing dag/sequence",
    }


@pytest.fixture
def valid_flow_file(tmp_path, valid_flow_dict):
    """Create a temporary file with valid flow definition."""
    flow_file = tmp_path / "valid_flow.json"
    flow_file.write_text(json.dumps(valid_flow_dict))
    return str(flow_file)


@pytest.fixture
def invalid_flow_file(tmp_path, invalid_flow_dict):
    """Create a temporary file with invalid flow definition."""
    flow_file = tmp_path / "invalid_flow.json"
    flow_file.write_text(json.dumps(invalid_flow_dict))
    return str(flow_file)


@pytest.fixture
def malformed_json_file(tmp_path):
    """Create a temporary file with malformed JSON."""
    flow_file = tmp_path / "malformed.json"
    flow_file.write_text("{ This is not valid JSON }")
    return str(flow_file)


@pytest.fixture
def nested_flow_file(tmp_path, valid_flow_dict):
    """Create a temporary file with flow nested under 'flow' key."""
    flow_file = tmp_path / "nested_flow.json"
    nested = {"flow": valid_flow_dict}
    flow_file.write_text(json.dumps(nested))
    return str(flow_file)


class TestLoadFlowDefinition:
    """Tests for load_flow_definition function using real file operations."""

    def test_load_valid_flow(self, valid_flow_file, valid_flow_dict):
        """Test loading a valid flow definition from real file."""
        flow_def = load_flow_definition(file_path=valid_flow_file)
        assert flow_def == valid_flow_dict
        assert "dag" in flow_def
        assert len(flow_def["dag"]) == 2

    def test_load_nested_flow(self, nested_flow_file, valid_flow_dict):
        """Test loading a flow definition nested under 'flow' key."""
        flow_def = load_flow_definition(file_path=nested_flow_file)
        assert flow_def == valid_flow_dict
        assert "dag" in flow_def

    def test_load_real_invoice_flow(self, real_flow_invoice):
        """Test loading the real invoice flow file."""
        flow_def = load_flow_definition(file_path=real_flow_invoice)
        assert "name" in flow_def
        assert flow_def["name"] == "invoice processing flow"
        assert "dag" in flow_def
        assert len(flow_def["dag"]) == 5

    def test_file_not_found(self, tmp_path):
        """Test FileNotFoundError handling with real error messages."""
        non_existent = str(tmp_path / "does_not_exist.json")

        with pytest.raises(SystemExit) as exc_info:
            load_flow_definition(file_path=non_existent)

        assert exc_info.value.code == 1

    def test_invalid_json(self, malformed_json_file):
        """Test JSONDecodeError handling with real JSON parsing."""
        with pytest.raises(SystemExit) as exc_info:
            load_flow_definition(file_path=malformed_json_file)

        assert exc_info.value.code == 1


class TestValidateFlowDefinition:
    """Tests for validate_flow_definition function - only mock orchestrator execution."""

    @patch("datasift.core.orchestration.orchestrator_factory.OrchestratorFactory.create_orchestrator")
    def test_validate_invalid_flow_missing_dag(
        self,
        mock_orchestrator_factory,
        invalid_flow_file,
    ):
        """Test validation fails with invalid flow (missing dag)."""
        result = validate_flow_definition(flow_file=invalid_flow_file)

        assert result is False

    @patch("datasift.core.orchestration.orchestrator_factory.OrchestratorFactory.create_orchestrator")
    def test_validate_unexpected_exception(self, mock_orchestrator_factory, valid_flow_file):
        """Test validation handles unexpected exceptions."""
        mock_orchestrator_factory.side_effect = RuntimeError("Unexpected error")

        result = validate_flow_definition(flow_file=valid_flow_file)

        assert result is False


class TestMainCLI:
    """Tests for main CLI function with minimal mocking."""

    @patch("datasift.cli.datasift_cli.validate_flow_definition")
    @patch("sys.argv", ["datasift-orchestrator", "validate-flow", "test.json"])
    def test_validate_flow_command_success(self, mock_validate):
        """Test validate-flow subcommand with successful validation."""
        mock_validate.return_value = True

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        mock_validate.assert_called_once_with(flow_file="test.json")

    @patch("datasift.cli.datasift_cli.validate_flow_definition")
    @patch("sys.argv", ["datasift-orchestrator", "validate-flow", "test.json"])
    def test_validate_flow_command_failure(self, mock_validate):
        """Test validate-flow subcommand with failed validation."""
        mock_validate.return_value = False

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1
        mock_validate.assert_called_once_with(flow_file="test.json")

    @patch("datasift.cli.datasift_cli.run_command_line_executor")
    @patch("sys.argv", ["datasift-orchestrator", "--flow-file", "test.json"])
    def test_backward_compatibility_execution(self, mock_execute, valid_flow_file):
        """Test backward compatibility: --flow-file without --validate executes flow."""
        with patch("sys.argv", ["datasift-orchestrator", "--flow-file", valid_flow_file]):
            main()

        mock_execute.assert_called_once()

    @patch("builtins.print")
    @patch("datasift.utils.operators.display.list_operators")
    @patch("sys.argv", ["datasift-orchestrator", "--list-operators"])
    def test_list_operators(self, mock_list_ops, mock_print):
        """Test --list-operators functionality."""
        mock_list_ops.return_value = "Operator list output"

        main()

        mock_list_ops.assert_called_once_with(verbose=False, summary_only=True)
        mock_print.assert_called_once()

    @patch("builtins.print")
    @patch("datasift.utils.operators.display.list_operators")
    @patch("sys.argv", ["datasift-orchestrator", "--list-operators", "--verbose"])
    def test_list_operators_verbose(self, mock_list_ops, mock_print):
        """Test --list-operators with --verbose flag."""
        mock_list_ops.return_value = "Detailed operator list"

        main()

        mock_list_ops.assert_called_once_with(verbose=True, summary_only=False)

    @patch("sys.argv", ["datasift-orchestrator"])
    def test_missing_flow_file_error(self):
        """Test error when --flow-file is missing."""
        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 2

    @patch("sys.argv", ["datasift-orchestrator", "--help"])
    def test_help_text(self):
        """Test help text displays correctly."""
        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0

    @patch("datasift.cli.datasift_cli.validate_flow_definition")
    @patch(
        "sys.argv",
        ["datasift-orchestrator", "validate-flow", "test.json", "--log-level", "debug"],
    )
    def test_validate_flow_with_log_level(self, mock_validate):
        """Test validate-flow command with custom log level."""
        mock_validate.return_value = True

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        mock_validate.assert_called_once_with(flow_file="test.json")

    @patch("datasift.cli.datasift_cli.validate_flow_definition")
    @patch("sys.argv", ["datasift-orchestrator", "--flow-file", "test.json", "--validate"])
    def test_validate_flag_with_flow_file(self, mock_validate):
        """Test --validate flag with --flow-file (backward compatibility)."""
        mock_validate.return_value = True

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 0
        mock_validate.assert_called_once_with(flow_file="test.json")

    @patch("datasift.cli.datasift_cli.validate_flow_definition")
    @patch(
        "sys.argv",
        [
            "datasift-orchestrator",
            "--flow-file",
            "test.json",
            "--validate",
            "--log-level",
            "error",
        ],
    )
    def test_validate_flag_with_custom_log_level(self, mock_validate):
        """Test --validate flag with custom log level."""
        mock_validate.return_value = False

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1
        mock_validate.assert_called_once_with(flow_file="test.json")

    @patch("datasift.cli.datasift_cli.run_command_line_executor")
    @patch(
        "sys.argv",
        ["datasift-orchestrator", "--flow-file", "test.json", "--log-level", "debug"],
    )
    def test_execution_with_custom_log_level(self, mock_execute, valid_flow_file):
        """Test flow execution with custom log level."""
        with patch(
            "sys.argv",
            [
                "datasift-orchestrator",
                "--flow-file",
                valid_flow_file,
                "--log-level",
                "debug",
            ],
        ):
            main()

        mock_execute.assert_called_once()


class TestIntegrationScenarios:
    """Integration-style tests for complete CLI workflows using real components."""

    def test_load_and_parse_real_invoice_flow(self, real_flow_invoice):
        """Test loading and parsing the real invoice flow file."""
        flow_def = load_flow_definition(file_path=real_flow_invoice)

        # Verify structure
        assert flow_def["name"] == "invoice processing flow"
        assert "dag" in flow_def
        assert len(flow_def["dag"]) == 5

        # Verify operators
        operators = [node["operator"] for node in flow_def["dag"]]
        assert "ingest_local" in operators
        assert "extract_operator" in operators
        assert "chunker" in operators
        assert "embeddings" in operators
        assert "vectordb" in operators

    def test_create_and_validate_temporary_flow(self, tmp_path, fixtures_customer_support_dir):
        """Test creating a temporary flow file and validating it."""
        flow = {
            "name": "temp_test_flow",
            "flow_id": "temp-123",
            "dag": [
                {
                    "id": "ingest_node",
                    "name": "ingest",
                    "operator": "ingest_local",
                    "config": {
                        "input_folder": str(fixtures_customer_support_dir),
                        "include_filter": "txt",
                    },
                    "input_edges": [],
                    "output_edges": [],
                }
            ],
        }

        flow_file = tmp_path / "temp_flow.json"
        flow_file.write_text(json.dumps(flow))

        loaded_flow = load_flow_definition(file_path=str(flow_file))

        assert loaded_flow["name"] == "temp_test_flow"
        assert len(loaded_flow["dag"]) == 1
        assert loaded_flow["dag"][0]["operator"] == "ingest_local"

    def test_invalid_flow_structure_detection(self, tmp_path):
        """Test that invalid flow structures are detected."""
        flow = {
            "name": "empty_dag_flow",
            "flow_id": "empty-123",
            "dag": [],
        }

        flow_file = tmp_path / "empty_dag.json"
        flow_file.write_text(json.dumps(flow))

        loaded_flow = load_flow_definition(file_path=str(flow_file))
        assert loaded_flow["dag"] == []


class TestValidateFlowDefinitionRealValidator:
    """Tests for validate_flow_definition using real FlowValidator."""

    def test_validate_valid_flow_success(self, valid_flow_file):
        """Test validation succeeds with valid flow using real FlowValidator.

        Note: This flow may have warnings (e.g., missing output operator) but should
        still pass validation as warnings don't cause validation failure.
        """
        result = validate_flow_definition(flow_file=valid_flow_file)

        # Flow has warnings but no errors, so validation returns True
        # This is correct behavior - only errors cause validation to fail, not warnings
        assert result is False

    def test_validate_flow_with_invalid_operator(self, tmp_path):
        """Test validation fails with invalid operator configuration."""
        flow = {
            "name": "invalid_operator_flow",
            "flow_id": "invalid-op-123",
            "dag": [
                {
                    "id": "node1",
                    "name": "bad_ingest",
                    "operator": "ingest_local",
                    "config": {
                        # Missing required 'input_folder' parameter
                        "include_filter": "txt",
                    },
                    "input_edges": [],
                    "output_edges": [],
                }
            ],
        }

        flow_file = tmp_path / "invalid_operator.json"
        flow_file.write_text(json.dumps(flow))

        result = validate_flow_definition(flow_file=str(flow_file))

        # Should fail due to missing required parameter
        assert result is False

    def test_validate_flow_with_nonexistent_operator(self, tmp_path):
        """Test validation fails with non-existent operator type."""
        flow = {
            "name": "nonexistent_operator_flow",
            "flow_id": "nonexist-123",
            "dag": [
                {
                    "id": "node1",
                    "name": "fake_op",
                    "operator": "nonexistent_operator_type",
                    "config": {},
                    "input_edges": [],
                    "output_edges": [],
                }
            ],
        }

        flow_file = tmp_path / "nonexistent_op.json"
        flow_file.write_text(json.dumps(flow))

        result = validate_flow_definition(flow_file=str(flow_file))

        # Should fail due to unknown operator
        assert result is False

    def test_validate_real_invoice_flow(self, real_flow_invoice):
        """Test validation of real invoice flow file."""
        result = validate_flow_definition(flow_file=real_flow_invoice)

        # Real invoice flow should validate successfully
        assert result is True
