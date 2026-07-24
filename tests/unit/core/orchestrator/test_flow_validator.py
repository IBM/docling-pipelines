"""Unit tests for flow_validator module.

Shared helpers make_validator() and make_node() are defined in conftest.py
and imported here so all test classes can call them without re-definition.
"""

from unittest.mock import Mock, patch

import pytest

from docpipe.core.constants.constants import DocpipeConstants
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.abstract_operator import OperatorCategory
from docpipe.core.orchestration.flow_validator import FlowValidator, ValidateStepResults
from docpipe.exceptions.docpipe_exceptions import (
    FlowValidationException,
)
from docpipe.exceptions.error_messages import ValidationCodeMessages
from tests.unit.core.orchestrator.conftest import make_node, make_validator


class TestValidateStepResults:
    """Test ValidateStepResults class."""

    def test_init(self):
        """Test ValidateStepResults initialization."""
        available_features = {"node1": ["feature1", "feature2"]}
        errors = ["error1"]
        warnings = ["warning1"]

        result = ValidateStepResults(available_features=available_features, errors=errors, warnings=warnings)

        assert result.available_features == available_features
        assert result.errors == errors
        assert result.warnings == warnings


class TestFlowValidator:
    """Test FlowValidator class."""

    def test_init(self):
        """Test FlowValidator initialization."""
        mock_orchestrator = Mock()
        mock_orchestrator.common_log_arguments = {}

        validator = FlowValidator(orchestrator=mock_orchestrator)

        assert validator.orchestrator == mock_orchestrator
        assert validator.common_log_arguments == {}

    def test_validate_disabled(self):
        """Test validation when disabled in config."""
        mock_orchestrator = Mock()
        mock_orchestrator.common_log_arguments = {}

        validator = FlowValidator(orchestrator=mock_orchestrator)

        flow_def = {
            OperatorConstants.Config.GLOBAL_CONFIG: {OperatorConstants.Config.DISABLE_VALIDATION: True},
            DocpipeConstants.DAG: [],
        }

        # Should return without raising exception
        validator.validate(flow_def=flow_def, params={})

    def test_validate_missing_dag(self):
        """Test validation with missing DAG."""
        mock_orchestrator = Mock()
        mock_orchestrator.common_log_arguments = {}

        validator = FlowValidator(orchestrator=mock_orchestrator)

        flow_def = {}

        with pytest.raises(FlowValidationException) as exc_info:
            validator.validate(flow_def=flow_def, params={})

        assert len(exc_info.value.errors) > 0

    @patch("docpipe.core.orchestration.flow_validator.clean_up_prefect_home")
    def test_validate_dag_empty_dag(self, mock_cleanup):
        """Test validation with empty DAG."""
        mock_orchestrator = Mock()
        mock_orchestrator.common_log_arguments = {}

        validator = FlowValidator(orchestrator=mock_orchestrator)

        flow_def = {DocpipeConstants.DAG: []}

        with pytest.raises(FlowValidationException) as exc_info:
            validator.validate_dag(flow_def=flow_def, global_config={})

        assert len(exc_info.value.errors) > 0

    @patch("docpipe.core.orchestration.flow_validator.clean_up_prefect_home")
    def test_validate_dag_unnamed_operators(self, mock_cleanup):
        """Test validation with unnamed operators."""
        mock_orchestrator = Mock()
        mock_orchestrator.common_log_arguments = {}
        mock_orchestrator.enable_custom_operators = True
        mock_orchestrator.custom_operator_packages = None
        mock_orchestrator.prefect_executor = Mock()
        mock_orchestrator.prefect_executor.build_non_execute_flow = Mock(return_value=Mock())

        validator = FlowValidator(orchestrator=mock_orchestrator)

        flow_def = {
            DocpipeConstants.DAG: [
                {
                    "id": "node1",
                    OperatorConstants.Misc.OPERATOR: "test_operator",
                    # Missing NAME
                }
            ]
        }

        with pytest.raises(FlowValidationException) as exc_info:
            validator.validate_dag(flow_def=flow_def, global_config={})

        # Should have warnings about unnamed operators
        assert len(exc_info.value.warnings) > 0 or len(exc_info.value.errors) > 0

    @patch("docpipe.core.orchestration.flow_validator.clean_up_prefect_home")
    def test_validate_dag_duplicate_names(self, mock_cleanup):
        """Test validation with duplicate operator names."""
        mock_orchestrator = Mock()
        mock_orchestrator.common_log_arguments = {}
        mock_orchestrator.enable_custom_operators = True
        mock_orchestrator.custom_operator_packages = None
        mock_orchestrator.prefect_executor = Mock()
        mock_orchestrator.prefect_executor.build_non_execute_flow = Mock(return_value=Mock())

        validator = FlowValidator(orchestrator=mock_orchestrator)

        flow_def = {
            DocpipeConstants.DAG: [
                {
                    "id": "node1",
                    OperatorConstants.Columns.NAME: "duplicate_name",
                    OperatorConstants.Misc.OPERATOR: "op1",
                },
                {
                    "id": "node2",
                    OperatorConstants.Columns.NAME: "duplicate_name",
                    OperatorConstants.Misc.OPERATOR: "op2",
                },
            ]
        }

        with pytest.raises(FlowValidationException) as exc_info:
            validator.validate_dag(flow_def=flow_def, global_config={})

        assert len(exc_info.value.errors) > 0

    def test_get_duplicate_node_names(self):
        """Test getting duplicate node names."""
        mock_orchestrator = Mock()
        mock_orchestrator.common_log_arguments = {}

        validator = FlowValidator(orchestrator=mock_orchestrator)

        nodes = ["node1", "node2", "node1", "node3", "node2"]
        result = validator.get_duplicate_node_names(nodes=nodes)

        assert set(result) == {"node1", "node2"}

    def test_get_duplicate_node_names_no_duplicates(self):
        """Test with no duplicate names."""
        mock_orchestrator = Mock()
        mock_orchestrator.common_log_arguments = {}

        validator = FlowValidator(orchestrator=mock_orchestrator)

        nodes = ["node1", "node2", "node3"]
        result = validator.get_duplicate_node_names(nodes=nodes)

        assert result == []

    def test_validate_first_operator_valid(self):
        """Test validating first operator when it's an Ingest operator."""
        mock_orchestrator = Mock()
        mock_orchestrator.common_log_arguments = {}

        validator = FlowValidator(orchestrator=mock_orchestrator)

        dag = [{"id": "node1", "operator": "ingest_op"}]
        validate_results = ValidateStepResults(available_features={}, errors=[], warnings=[])

        with patch.object(validator, "validate_operator_category") as mock_validate:
            validator.validate_first_operator(dag=dag, global_config={}, validate_results=validate_results)

            mock_validate.assert_called_once()

    def test_build_graph(self):
        """Test building graph from DAG."""
        mock_orchestrator = Mock()
        mock_orchestrator.common_log_arguments = {}

        validator = FlowValidator(orchestrator=mock_orchestrator)

        dag = [
            {"id": "node1", DocpipeConstants.OUTPUT_EDGES: [{"node_id_ref": "node2"}]},
            {"id": "node2", DocpipeConstants.OUTPUT_EDGES: [{"node_id_ref": "node3"}]},
            {"id": "node3", DocpipeConstants.OUTPUT_EDGES: []},
        ]

        result = validator._build_graph(dag)

        assert result["node1"] == ["node2"]
        assert result["node2"] == ["node3"]
        assert result["node3"] == []

    def test_make_undirected_graph(self):
        """Test converting directed graph to undirected."""
        mock_orchestrator = Mock()
        mock_orchestrator.common_log_arguments = {}

        validator = FlowValidator(orchestrator=mock_orchestrator)

        graph = {"node1": ["node2"], "node2": ["node3"], "node3": []}

        result = validator._make_undirected_graph(graph)

        assert "node2" in result["node1"]
        assert "node1" in result["node2"]
        assert "node3" in result["node2"]
        assert "node2" in result["node3"]

    def test_find_connected_components_single_component(self):
        """Test finding connected components with single component."""
        mock_orchestrator = Mock()
        mock_orchestrator.common_log_arguments = {}

        validator = FlowValidator(orchestrator=mock_orchestrator)

        undirected = {
            "node1": {"node2"},
            "node2": {"node1", "node3"},
            "node3": {"node2"},
        }

        result = validator._find_connected_components(undirected)

        assert len(result) == 1
        assert result[0] == {"node1", "node2", "node3"}

    def test_find_connected_components_multiple_components(self):
        """Test finding connected components with multiple components."""
        mock_orchestrator = Mock()
        mock_orchestrator.common_log_arguments = {}

        validator = FlowValidator(orchestrator=mock_orchestrator)

        undirected = {
            "node1": {"node2"},
            "node2": {"node1"},
            "node3": {"node4"},
            "node4": {"node3"},
        }

        result = validator._find_connected_components(undirected)

        assert len(result) == 2

    def test_validate_disjoint_operators_connected(self):
        """Test validation with connected operators."""
        mock_orchestrator = Mock()
        mock_orchestrator.common_log_arguments = {}

        validator = FlowValidator(orchestrator=mock_orchestrator)

        dag = [
            {"id": "node1", DocpipeConstants.OUTPUT_EDGES: [{"node_id_ref": "node2"}]},
            {"id": "node2", DocpipeConstants.OUTPUT_EDGES: []},
        ]

        validate_results = ValidateStepResults(available_features={}, errors=[], warnings=[])

        # Should not add errors for connected graph
        validator.validate_disjoint_operators(dag=dag, global_config={}, validate_results=validate_results)

        assert len(validate_results.errors) == 0

    def test_validate_disjoint_operators_disconnected(self):
        """Test validation with disconnected operators."""
        mock_orchestrator = Mock()
        mock_orchestrator.common_log_arguments = {}

        validator = FlowValidator(orchestrator=mock_orchestrator)

        dag = [
            {"id": "node1", DocpipeConstants.OUTPUT_EDGES: []},
            {"id": "node2", DocpipeConstants.OUTPUT_EDGES: []},
        ]

        validate_results = ValidateStepResults(available_features={}, errors=[], warnings=[])

        validator.validate_disjoint_operators(dag=dag, global_config={}, validate_results=validate_results)

        # Should add error for disconnected graph
        assert len(validate_results.errors) > 0

    def test_check_duplicate_extract_operators(self):
        """Test checking for duplicate extract operators."""
        mock_orchestrator = Mock()
        mock_orchestrator.common_log_arguments = {}

        validator = FlowValidator(orchestrator=mock_orchestrator)

        sequence = [
            {"id": "node1", "operator": "extract_op1"},
            {"id": "node2", "operator": "extract_op2"},
        ]

        errors = []

        with patch.object(validator, "get_operator_category") as mock_get_category:
            mock_get_category.return_value = OperatorCategory.Extract

            result = validator.check_duplicate_extract_operators(sequence=sequence, global_config={}, errors=errors)

            assert result == 2
            assert len(errors) > 0  # Should have error for multiple extracts

    def test_validate_operator_category_matches(self):
        """Test validating operator category when it matches."""
        mock_orchestrator = Mock()
        mock_orchestrator.common_log_arguments = {}

        validator = FlowValidator(orchestrator=mock_orchestrator)

        op_def = {"id": "node1", "operator": "test_op"}
        alerts = []

        with patch.object(validator, "get_operator_category") as mock_get_category:
            mock_get_category.return_value = OperatorCategory.Ingest

            validator.validate_operator_category(
                op_def=op_def,
                global_config={},
                expected_category=OperatorCategory.Ingest,
                error_message=Mock(),
                alerts=alerts,
            )

            assert len(alerts) == 0

    def test_validate_operator_category_mismatch(self):
        """Test validating operator category when it doesn't match."""
        mock_orchestrator = Mock()
        mock_orchestrator.common_log_arguments = {}

        validator = FlowValidator(orchestrator=mock_orchestrator)

        op_def = {"id": "node1", "operator": "test_op"}
        alerts = []

        with patch.object(validator, "get_operator_category") as mock_get_category:
            mock_get_category.return_value = OperatorCategory.Extract

            from docpipe.exceptions.error_messages import ValidationMessage

            validator.validate_operator_category(
                op_def=op_def,
                global_config={},
                expected_category=OperatorCategory.Ingest,
                error_message=ValidationMessage(message="Category mismatch error"),
                alerts=alerts,
            )

            assert len(alerts) > 0

    def test_get_operator_category_missing_id(self):
        """Test getting operator category with missing ID."""
        mock_orchestrator = Mock()
        mock_orchestrator.common_log_arguments = {}
        mock_orchestrator.create_executor = Mock()

        validator = FlowValidator(orchestrator=mock_orchestrator)

        op_def = {"operator": "test_op"}  # Missing ID
        alerts = []

        # The method adds alerts but doesn't raise exception for missing ID
        validator.get_operator_category(op_def=op_def, global_config={}, alerts=alerts)

        # Verify that an alert was added for missing ID
        assert len(alerts) > 0
        assert any("MISSING_NODE_ID" in str(alert) or "missing" in str(alert).lower() for alert in alerts)

    def test_get_operator_category_missing_name(self):
        """Test getting operator category with missing name."""
        mock_orchestrator = Mock()
        mock_orchestrator.common_log_arguments = {}
        mock_orchestrator.create_executor = Mock()

        validator = FlowValidator(orchestrator=mock_orchestrator)

        op_def = {"id": "node1", "operator": "test_op"}  # Missing NAME
        alerts = []

        # The method adds alerts but doesn't raise exception for missing name
        validator.get_operator_category(op_def=op_def, global_config={}, alerts=alerts)

        # Verify that an alert was added for missing name
        assert len(alerts) > 0
        assert any("MISSING_NODE_NAME" in str(alert) or "name" in str(alert).lower() for alert in alerts)

    def test_get_operator_category_success(self):
        """Test successfully getting operator category."""
        mock_orchestrator = Mock()
        mock_orchestrator.common_log_arguments = {}

        validator = FlowValidator(orchestrator=mock_orchestrator)

        # Mock the operator metadata to return Ingest category for test_op
        validator.operator_metadata.operator_metadata = {
            "test_op": {OperatorConstants.Misc.CATEGORY: OperatorCategory.Ingest}
        }

        op_def = {
            "id": "node1",
            OperatorConstants.Columns.NAME: "Test Op",
            "operator": "test_op",
        }
        alerts = []

        result = validator.get_operator_category(op_def=op_def, global_config={}, alerts=alerts)

        assert result == OperatorCategory.Ingest

    def test_create_validation_alerts(self):
        """Test creating validation alerts."""
        mock_orchestrator = Mock()
        mock_orchestrator.common_log_arguments = {}

        validator = FlowValidator(orchestrator=mock_orchestrator)

        op_def = {"id": "node1", "name": "Test"}
        messages = [Mock(), Mock()]
        alerts = []

        with patch("docpipe.core.orchestration.flow_validator.add_validation_alert") as mock_add:
            validator.create_validation_alerts(op_def=op_def, messages=messages, alerts=alerts)

            assert mock_add.call_count == 2

    def test_evaluate_node_validation_skip_custom_op(self):
        """Test skipping validation for custom operator."""
        mock_orchestrator = Mock()
        mock_orchestrator.common_log_arguments = {}

        validator = FlowValidator(orchestrator=mock_orchestrator)

        mock_factory = Mock()
        mock_factory.operators = {"known_op": Mock()}

        global_config = {DocpipeConstants.SKIP_CUSTOM_OP_VALIDATION: True}

        result = validator._evaluate_node_validation_skip(
            operator="unknown_op",
            operator_factory=mock_factory,
            global_config=global_config,
        )

        assert result is True

    def test_evaluate_node_validation_skip_known_op(self):
        """Test not skipping validation for known operator."""
        mock_orchestrator = Mock()
        mock_orchestrator.common_log_arguments = {}

        validator = FlowValidator(orchestrator=mock_orchestrator)

        mock_factory = Mock()
        mock_factory.operators = {"known_op": Mock()}

        global_config = {DocpipeConstants.SKIP_CUSTOM_OP_VALIDATION: True}

        result = validator._evaluate_node_validation_skip(
            operator="known_op",
            operator_factory=mock_factory,
            global_config=global_config,
        )

        assert result is False


class TestFindConnectedComponents:
    """Test _find_connected_components method."""

    def test_single_component(self):
        """Test fully connected graph."""
        mock_orchestrator = Mock()
        mock_orchestrator.common_log_arguments = {}

        validator = FlowValidator(orchestrator=mock_orchestrator)

        undirected = {
            "node1": ["node2", "node3"],
            "node2": ["node1", "node3"],
            "node3": ["node1", "node2"],
        }

        result = validator._find_connected_components(undirected)

        assert len(result) == 1
        assert result[0] == {"node1", "node2", "node3"}

    def test_multiple_components(self):
        """Test 2+ disconnected components."""
        mock_orchestrator = Mock()
        mock_orchestrator.common_log_arguments = {}

        validator = FlowValidator(orchestrator=mock_orchestrator)

        undirected = {
            "node1": ["node2"],
            "node2": ["node1"],
            "node3": ["node4"],
            "node4": ["node3"],
            "node5": [],
        }

        result = validator._find_connected_components(undirected)

        assert len(result) == 3
        component_sets = [set(comp) for comp in result]
        assert {"node1", "node2"} in component_sets
        assert {"node3", "node4"} in component_sets
        assert {"node5"} in component_sets

    def test_isolated_nodes(self):
        """Test nodes with no connections."""
        mock_orchestrator = Mock()
        mock_orchestrator.common_log_arguments = {}

        validator = FlowValidator(orchestrator=mock_orchestrator)

        undirected = {
            "node1": [],
            "node2": [],
            "node3": [],
        }

        result = validator._find_connected_components(undirected)

        assert len(result) == 3
        for comp in result:
            assert len(comp) == 1

    def test_empty_graph(self):
        """Test empty node list."""
        mock_orchestrator = Mock()
        mock_orchestrator.common_log_arguments = {}

        validator = FlowValidator(orchestrator=mock_orchestrator)

        undirected = {}

        result = validator._find_connected_components(undirected)

        assert len(result) == 0


class TestValidateOperatorAvailability:
    """Test validate_operator_availability method."""

    def test_all_operators_available(self):
        """Test with all registered operators."""
        mock_orchestrator = Mock()
        mock_orchestrator.common_log_arguments = {}
        mock_orchestrator.enable_custom_operators = False
        mock_orchestrator.custom_operator_packages = None

        validator = FlowValidator(orchestrator=mock_orchestrator)

        dag = [
            {"id": "node1", OperatorConstants.Misc.OPERATOR: "ingest_local"},
            {"id": "node2", OperatorConstants.Misc.OPERATOR: "extract_operator"},
        ]

        validate_results = ValidateStepResults(available_features={}, errors=[], warnings=[])

        with patch(
            "docpipe.core.orchestration.flow_validator.OperatorFactoryProvider.get_operator_factory"
        ) as mock_factory_provider:
            mock_factory = Mock()
            mock_factory.operators = {"ingest_local": Mock(), "extract_operator": Mock()}
            mock_factory_provider.return_value = mock_factory

            validator.validate_operator_availability(dag=dag, global_config={}, validate_results=validate_results)

            assert len(validate_results.errors) == 0

    def test_missing_operator(self):
        """Test with unregistered operator."""
        mock_orchestrator = Mock()
        mock_orchestrator.common_log_arguments = {}
        mock_orchestrator.enable_custom_operators = False
        mock_orchestrator.custom_operator_packages = None

        validator = FlowValidator(orchestrator=mock_orchestrator)

        dag = [
            {"id": "node1", OperatorConstants.Misc.OPERATOR: "unknown_operator"},
        ]

        validate_results = ValidateStepResults(available_features={}, errors=[], warnings=[])

        with patch(
            "docpipe.core.orchestration.flow_validator.OperatorFactoryProvider.get_operator_factory"
        ) as mock_factory_provider:
            mock_factory = Mock()
            mock_factory.operators = {"ingest_local": Mock()}
            mock_factory_provider.return_value = mock_factory

            validator.validate_operator_availability(dag=dag, global_config={}, validate_results=validate_results)

            assert len(validate_results.errors) > 0
            assert any("unknown_operator" in str(error) for error in validate_results.errors)

    def test_custom_operator_skip(self):
        """Test custom operator skip logic."""
        mock_orchestrator = Mock()
        mock_orchestrator.common_log_arguments = {}
        mock_orchestrator.enable_custom_operators = True
        mock_orchestrator.custom_operator_packages = None

        validator = FlowValidator(orchestrator=mock_orchestrator)

        dag = [
            {"id": "node1", OperatorConstants.Misc.OPERATOR: "custom_operator"},
        ]

        validate_results = ValidateStepResults(available_features={}, errors=[], warnings=[])
        global_config = {DocpipeConstants.SKIP_CUSTOM_OP_VALIDATION: True}

        with patch(
            "docpipe.core.orchestration.flow_validator.OperatorFactoryProvider.get_operator_factory"
        ) as mock_factory_provider:
            mock_factory = Mock()
            mock_factory.operators = {"ingest_local": Mock()}
            mock_factory_provider.return_value = mock_factory

            validator.validate_operator_availability(
                dag=dag, global_config=global_config, validate_results=validate_results
            )

            # Should not add error for custom operator when skip is enabled
            assert len(validate_results.errors) == 0

    def test_empty_operator_list(self):
        """Test with no operators."""
        mock_orchestrator = Mock()
        mock_orchestrator.common_log_arguments = {}
        mock_orchestrator.enable_custom_operators = False
        mock_orchestrator.custom_operator_packages = None

        validator = FlowValidator(orchestrator=mock_orchestrator)

        dag = []

        validate_results = ValidateStepResults(available_features={}, errors=[], warnings=[])

        with patch(
            "docpipe.core.orchestration.flow_validator.OperatorFactoryProvider.get_operator_factory"
        ) as mock_factory_provider:
            mock_factory = Mock()
            mock_factory.operators = {}
            mock_factory_provider.return_value = mock_factory

            validator.validate_operator_availability(dag=dag, global_config={}, validate_results=validate_results)

            assert len(validate_results.errors) == 0


class TestValidateOperatorCategory:
    """Test validate_operator_category method."""

    def test_valid_category(self):
        """Test matching category."""
        mock_orchestrator = Mock()
        mock_orchestrator.common_log_arguments = {}

        validator = FlowValidator(orchestrator=mock_orchestrator)

        op_def = {"id": "node1", OperatorConstants.Columns.NAME: "test", "operator": "test_op"}
        alerts = []

        with patch.object(validator, "get_operator_category") as mock_get_category:
            mock_get_category.return_value = OperatorCategory.Ingest

            from docpipe.exceptions.error_messages import ValidationMessage

            validator.validate_operator_category(
                op_def=op_def,
                global_config={},
                expected_category=OperatorCategory.Ingest,
                error_message=ValidationMessage(message="Category mismatch"),
                alerts=alerts,
            )

            assert len(alerts) == 0

    def test_category_mismatch(self):
        """Test category mismatch error."""
        mock_orchestrator = Mock()
        mock_orchestrator.common_log_arguments = {}

        validator = FlowValidator(orchestrator=mock_orchestrator)

        op_def = {"id": "node1", OperatorConstants.Columns.NAME: "test", "operator": "test_op"}
        alerts = []

        with patch.object(validator, "get_operator_category") as mock_get_category:
            mock_get_category.return_value = OperatorCategory.Extract

            from docpipe.exceptions.error_messages import ValidationMessage

            validator.validate_operator_category(
                op_def=op_def,
                global_config={},
                expected_category=OperatorCategory.Ingest,
                error_message=ValidationMessage(message="Category mismatch"),
                alerts=alerts,
            )

            assert len(alerts) > 0

    def test_missing_category(self):
        """Test missing category handling."""
        mock_orchestrator = Mock()
        mock_orchestrator.common_log_arguments = {}

        validator = FlowValidator(orchestrator=mock_orchestrator)

        op_def = {"id": "node1", OperatorConstants.Columns.NAME: "test", "operator": "test_op"}
        alerts = []

        with patch.object(validator, "get_operator_category") as mock_get_category:
            mock_get_category.return_value = None

            from docpipe.exceptions.error_messages import ValidationMessage

            validator.validate_operator_category(
                op_def=op_def,
                global_config={},
                expected_category=OperatorCategory.Ingest,
                error_message=ValidationMessage(message="Category mismatch"),
                alerts=alerts,
            )

            # Should add error when category is None
            assert len(alerts) > 0


class TestGetOperatorCategory:
    """Test get_operator_category method."""

    def test_get_from_metadata(self):
        """Test category from operator metadata."""
        mock_orchestrator = Mock()
        mock_orchestrator.common_log_arguments = {}

        validator = FlowValidator(orchestrator=mock_orchestrator)

        validator.operator_metadata.operator_metadata = {
            "test_op": {OperatorConstants.Misc.CATEGORY: OperatorCategory.Functional}
        }

        op_def = {
            "id": "node1",
            OperatorConstants.Columns.NAME: "test",
            OperatorConstants.Misc.OPERATOR: "test_op",
        }
        alerts = []

        result = validator.get_operator_category(op_def=op_def, global_config={}, alerts=alerts)

        assert result == OperatorCategory.Functional
        assert len(alerts) == 0

    def test_get_from_registry(self):
        """Test category from operator registry."""
        mock_orchestrator = Mock()
        mock_orchestrator.common_log_arguments = {}

        validator = FlowValidator(orchestrator=mock_orchestrator)

        validator.operator_metadata.operator_metadata = {
            "registered_op": {OperatorConstants.Misc.CATEGORY: OperatorCategory.Quality}
        }

        op_def = {
            "id": "node1",
            OperatorConstants.Columns.NAME: "test",
            OperatorConstants.Misc.OPERATOR: "registered_op",
        }
        alerts = []

        result = validator.get_operator_category(op_def=op_def, global_config={}, alerts=alerts)

        assert result == OperatorCategory.Quality

    def test_missing_metadata(self):
        """Test fallback when metadata missing."""
        mock_orchestrator = Mock()
        mock_orchestrator.common_log_arguments = {}

        validator = FlowValidator(orchestrator=mock_orchestrator)

        validator.operator_metadata.operator_metadata = {}

        op_def = {
            "id": "node1",
            OperatorConstants.Columns.NAME: "test",
            OperatorConstants.Misc.OPERATOR: "unknown_op",
        }
        alerts = []

        result = validator.get_operator_category(op_def=op_def, global_config={}, alerts=alerts)

        assert result is None
        assert len(alerts) > 0
        assert any("OPERATOR_CATEGORY_UNKNOWN" in str(alert) or "category" in str(alert).lower() for alert in alerts)

    def test_invalid_operator(self):
        """Test with invalid operator name."""
        mock_orchestrator = Mock()
        mock_orchestrator.common_log_arguments = {}

        validator = FlowValidator(orchestrator=mock_orchestrator)

        validator.operator_metadata.operator_metadata = {}

        op_def = {
            "id": "node1",
            OperatorConstants.Columns.NAME: "test",
            # Missing operator key
        }
        alerts = []

        result = validator.get_operator_category(op_def=op_def, global_config={}, alerts=alerts)

        assert result is None
        assert len(alerts) > 0


class TestValidateNoCycles:
    """Tests for validate_no_cycles function."""

    def test_no_cycle_linear_dag(self):
        """Test simple linear flow."""
        mock_orchestrator = Mock()
        mock_orchestrator.common_log_arguments = {}

        validator = FlowValidator(orchestrator=mock_orchestrator)

        dag = [
            {"id": "node1", DocpipeConstants.OUTPUT_EDGES: [{"node_id_ref": "node2"}]},
            {"id": "node2", DocpipeConstants.OUTPUT_EDGES: [{"node_id_ref": "node3"}]},
            {"id": "node3", DocpipeConstants.OUTPUT_EDGES: []},
        ]

        validate_results = ValidateStepResults(available_features={}, errors=[], warnings=[])
        validator.validate_no_cycles(dag=dag, validate_results=validate_results)

        # Should have no errors
        assert len(validate_results.errors) == 0

    def test_detects_simple_cycle(self):
        """Test A→B→A cycle."""
        mock_orchestrator = Mock()
        mock_orchestrator.common_log_arguments = {}

        validator = FlowValidator(orchestrator=mock_orchestrator)

        dag = [
            {"id": "node1", DocpipeConstants.OUTPUT_EDGES: [{"node_id_ref": "node2"}]},
            {"id": "node2", DocpipeConstants.OUTPUT_EDGES: [{"node_id_ref": "node1"}]},
        ]

        validate_results = ValidateStepResults(available_features={}, errors=[], warnings=[])
        validator.validate_no_cycles(dag=dag, validate_results=validate_results)

        # Should detect cycle
        assert len(validate_results.errors) > 0
        assert any("Cyclic dependency" in str(err) for err in validate_results.errors)

    def test_detects_complex_cycle(self):
        """Test A→B→C→A cycle."""
        mock_orchestrator = Mock()
        mock_orchestrator.common_log_arguments = {}

        validator = FlowValidator(orchestrator=mock_orchestrator)

        dag = [
            {"id": "node1", DocpipeConstants.OUTPUT_EDGES: [{"node_id_ref": "node2"}]},
            {"id": "node2", DocpipeConstants.OUTPUT_EDGES: [{"node_id_ref": "node3"}]},
            {"id": "node3", DocpipeConstants.OUTPUT_EDGES: [{"node_id_ref": "node1"}]},
        ]

        validate_results = ValidateStepResults(available_features={}, errors=[], warnings=[])
        validator.validate_no_cycles(dag=dag, validate_results=validate_results)

        # Should detect cycle
        assert len(validate_results.errors) > 0

    def test_self_loop_cycle(self):
        """Test A→A self-loop."""
        mock_orchestrator = Mock()
        mock_orchestrator.common_log_arguments = {}

        validator = FlowValidator(orchestrator=mock_orchestrator)

        dag = [
            {"id": "node1", DocpipeConstants.OUTPUT_EDGES: [{"node_id_ref": "node1"}]},
        ]

        validate_results = ValidateStepResults(available_features={}, errors=[], warnings=[])
        validator.validate_no_cycles(dag=dag, validate_results=validate_results)

        # Should detect self-loop
        assert len(validate_results.errors) > 0

    def test_multiple_paths_no_cycle(self):
        """Test diamond pattern (no cycle)."""
        mock_orchestrator = Mock()
        mock_orchestrator.common_log_arguments = {}

        validator = FlowValidator(orchestrator=mock_orchestrator)

        # Diamond: node1 → node2 → node4
        #                 → node3 → node4
        dag = [
            {
                "id": "node1",
                DocpipeConstants.OUTPUT_EDGES: [{"node_id_ref": "node2"}, {"node_id_ref": "node3"}],
            },
            {"id": "node2", DocpipeConstants.OUTPUT_EDGES: [{"node_id_ref": "node4"}]},
            {"id": "node3", DocpipeConstants.OUTPUT_EDGES: [{"node_id_ref": "node4"}]},
            {"id": "node4", DocpipeConstants.OUTPUT_EDGES: []},
        ]

        validate_results = ValidateStepResults(available_features={}, errors=[], warnings=[])
        validator.validate_no_cycles(dag=dag, validate_results=validate_results)

        # Should have no errors (diamond is acyclic)
        assert len(validate_results.errors) == 0


class TestCheckDuplicateExtractOperators:
    """Tests for check_duplicate_extract_operators function."""

    def test_no_extract_operators(self):
        """Test flow with zero extract operators."""
        mock_orchestrator = Mock()
        mock_orchestrator.common_log_arguments = {}

        validator = FlowValidator(orchestrator=mock_orchestrator)

        sequence = [
            {"id": "node1", OperatorConstants.Misc.OPERATOR: "ingest_op"},
            {"id": "node2", OperatorConstants.Misc.OPERATOR: "chunk_op"},
        ]

        errors = []
        with patch.object(validator, "get_operator_category") as mock_get_category:
            mock_get_category.side_effect = [OperatorCategory.Ingest, OperatorCategory.Functional]

            count = validator.check_duplicate_extract_operators(sequence=sequence, global_config={}, errors=errors)

        assert count == 0
        assert len(errors) == 0

    def test_single_extract_operator(self):
        """Test flow with one extract operator."""
        mock_orchestrator = Mock()
        mock_orchestrator.common_log_arguments = {}

        validator = FlowValidator(orchestrator=mock_orchestrator)

        sequence = [
            {"id": "node1", OperatorConstants.Misc.OPERATOR: "ingest_op"},
            {"id": "node2", OperatorConstants.Misc.OPERATOR: "extract_op"},
        ]

        errors = []
        with patch.object(validator, "get_operator_category") as mock_get_category:
            mock_get_category.side_effect = [OperatorCategory.Ingest, OperatorCategory.Extract]

            count = validator.check_duplicate_extract_operators(sequence=sequence, global_config={}, errors=errors)

        assert count == 1
        assert len(errors) == 0

    def test_multiple_extract_operators_error(self):
        """Test error with 2+ extract operators."""
        mock_orchestrator = Mock()
        mock_orchestrator.common_log_arguments = {}

        validator = FlowValidator(orchestrator=mock_orchestrator)

        sequence = [
            {"id": "node1", OperatorConstants.Misc.OPERATOR: "extract_op1"},
            {"id": "node2", OperatorConstants.Misc.OPERATOR: "extract_op2"},
        ]

        errors = []
        with patch.object(validator, "get_operator_category") as mock_get_category:
            mock_get_category.side_effect = [OperatorCategory.Extract, OperatorCategory.Extract]

            count = validator.check_duplicate_extract_operators(sequence=sequence, global_config={}, errors=errors)

        assert count == 2
        assert len(errors) > 0

    def test_extract_operator_identification(self):
        """Test correct operator type detection."""
        mock_orchestrator = Mock()
        mock_orchestrator.common_log_arguments = {}

        validator = FlowValidator(orchestrator=mock_orchestrator)

        sequence = [
            {"id": "node1", OperatorConstants.Misc.OPERATOR: "ingest_op"},
            {"id": "node2", OperatorConstants.Misc.OPERATOR: "extract_op"},
            {"id": "node3", OperatorConstants.Misc.OPERATOR: "chunk_op"},
        ]

        errors = []
        with patch.object(validator, "get_operator_category") as mock_get_category:
            mock_get_category.side_effect = [
                OperatorCategory.Ingest,
                OperatorCategory.Extract,
                OperatorCategory.Functional,
            ]

            count = validator.check_duplicate_extract_operators(sequence=sequence, global_config={}, errors=errors)

        # Should identify exactly one extract operator
        assert count == 1
        assert len(errors) == 0


class TestValidateLastOperator:
    """Tests for validate_last_operator function."""

    def test_vectordb_terminal_valid(self):
        """Test VectorDB as last operator."""
        mock_orchestrator = Mock()
        mock_orchestrator.common_log_arguments = {}

        validator = FlowValidator(orchestrator=mock_orchestrator)

        dag = [
            {"id": "node1", OperatorConstants.Misc.OPERATOR: "ingest_op"},
            {"id": "node2", OperatorConstants.Misc.OPERATOR: "vectordb_op"},
        ]

        validate_results = ValidateStepResults(available_features={}, errors=[], warnings=[])

        with patch.object(validator, "get_operator_category") as mock_get_category:
            mock_get_category.return_value = OperatorCategory.VectorDB

            validator.validate_last_operator(dag=dag, global_config={}, validate_results=validate_results)

        # Should have no warnings
        assert len(validate_results.warnings) == 0

    def test_non_vectordb_terminal_invalid(self):
        """Test non-VectorDB terminal raises warning."""
        mock_orchestrator = Mock()
        mock_orchestrator.common_log_arguments = {}

        validator = FlowValidator(orchestrator=mock_orchestrator)

        dag = [
            {"id": "node1", OperatorConstants.Misc.OPERATOR: "ingest_op"},
            {"id": "node2", OperatorConstants.Misc.OPERATOR: "chunk_op"},
        ]

        validate_results = ValidateStepResults(available_features={}, errors=[], warnings=[])

        with patch.object(validator, "get_operator_category") as mock_get_category:
            mock_get_category.return_value = OperatorCategory.Functional

            validator.validate_last_operator(dag=dag, global_config={}, validate_results=validate_results)

        # Should have warning about missing output generation
        assert len(validate_results.warnings) > 0

    def test_empty_dag(self):
        """Test with empty DAG."""
        mock_orchestrator = Mock()
        mock_orchestrator.common_log_arguments = {}

        validator = FlowValidator(orchestrator=mock_orchestrator)

        dag = []
        validate_results = ValidateStepResults(available_features={}, errors=[], warnings=[])

        validator.validate_last_operator(dag=dag, global_config={}, validate_results=validate_results)

        # Should handle empty DAG gracefully
        assert len(validate_results.warnings) == 0
        assert len(validate_results.errors) == 0


class TestFlowValidatorIntegration:
    """Integration tests for flow validation with real orchestrator."""

    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator instance for testing."""
        from docpipe.core.orchestration.orchestrator_factory import OrchestratorFactory

        orch = OrchestratorFactory.create_orchestrator(orchestrator_name="python")
        orch.initialize(job_id="test-job-id", job_run_id="test-job-run-id")
        return orch

    @pytest.fixture
    def validator(self, orchestrator):
        """Create flow validator instance."""
        return FlowValidator(orchestrator=orchestrator)

    def test_valid_simple_flow_passes_validation(self, validator, fixtures_invoices_dir):
        """Test that a valid simple flow passes validation without errors."""
        flow_def = {
            "dag": [
                {
                    "id": "ingest-1",
                    "name": "ingest_documents",
                    "operator": "ingest_local",
                    "config": {"paths": str(fixtures_invoices_dir)},
                    "input_edges": [],
                    "output_edges": [{"node_id_ref": "extract-1"}],
                },
                {
                    "id": "extract-1",
                    "name": "extract_documents",
                    "operator": "extract_operator",
                    "config": {"text_extraction": {"provider": "docling_library", "doc_column": "content"}},
                    "input_edges": [{"node_id_ref": "ingest-1"}],
                    "output_edges": [{"node_id_ref": "vectordb-1"}],
                },
                {
                    "id": "vectordb-1",
                    "name": "store_in_opensearch",
                    "operator": "vectordb",
                    "config": {
                        "provider": "opensearch",
                        "provider_config": {
                            "host": "localhost",
                            "port": 9200,
                            "use_ssl": False,
                        },
                        "index_name": "test_index",
                        "vector_dimension": 384,
                        "doc_id_column": "id",
                        "embeddings_column": "embeddings",
                    },
                    "input_edges": [{"node_id_ref": "extract-1"}],
                    "output_edges": [],
                },
            ]
        }
        validator.validate_dag(flow_def=flow_def, global_config={})

    def test_missing_required_features_fails(self, validator, fixtures_invoices_dir):
        """Test that flow with missing required features fails validation."""
        flow_def = {
            "dag": [
                {
                    "id": "ingest-1",
                    "name": "ingest_documents",
                    "operator": "ingest_local",
                    "config": {"paths": str(fixtures_invoices_dir)},
                    "input_edges": [],
                    "output_edges": [{"node_id_ref": "chunker-1"}],
                },
                {
                    "id": "chunker-1",
                    "name": "chunk_documents",
                    "operator": "chunker",
                    "config": {"doc_column": "content", "chunk_size": 1000},
                    "input_edges": [{"node_id_ref": "ingest-1"}],
                    "output_edges": [],
                },
            ]
        }

        with pytest.raises(FlowValidationException) as exc_info:
            validator.validate_dag(flow_def=flow_def, global_config={})

        errors = exc_info.value.errors or []
        assert any(ValidationCodeMessages.MISSING_FEATURES.name in str(error.message_code) for error in errors), (
            "Expected MISSING_FEATURES error not found"
        )

    def test_last_operator_not_vectordb_warns(self, validator, fixtures_invoices_dir):
        """Test that flow where last operator is not VectorDB generates warning."""
        flow_def = {
            "dag": [
                {
                    "id": "ingest-1",
                    "name": "ingest_documents",
                    "operator": "ingest_local",
                    "config": {"paths": str(fixtures_invoices_dir)},
                    "input_edges": [],
                    "output_edges": [{"node_id_ref": "extract-1"}],
                },
                {
                    "id": "extract-1",
                    "name": "extract_documents",
                    "operator": "extract_operator",
                    "config": {"doc_column": "content"},
                    "input_edges": [{"node_id_ref": "ingest-1"}],
                    "output_edges": [{"node_id_ref": "chunker-1"}],
                },
                {
                    "id": "chunker-1",
                    "name": "chunk_documents",
                    "operator": "chunker",
                    "config": {"doc_column": "content", "chunk_size": 200},
                    "input_edges": [{"node_id_ref": "extract-1"}],
                    "output_edges": [],
                },
            ]
        }

        with pytest.raises(FlowValidationException) as exc_info:
            validator.validate_dag(flow_def=flow_def, global_config={})

        warnings = exc_info.value.warnings or []
        assert any(
            ValidationCodeMessages.GENERATE_OUTPUT_MISSING.name in str(warning.message_code) for warning in warnings
        ), "Expected GENERATE_OUTPUT_MISSING warning not found"

    def test_first_operator_not_ingest_fails(self, validator, fixtures_invoices_dir):
        """Test that flow where first operator is not Ingest fails."""
        flow_def = {
            "dag": [
                {
                    "id": "extract-1",
                    "name": "extract_documents",
                    "operator": "extract_operator",
                    "config": {"doc_column": "content"},
                    "input_edges": [],
                    "output_edges": [{"node_id_ref": "chunker-1"}],
                },
                {
                    "id": "chunker-1",
                    "name": "chunk_documents",
                    "operator": "chunker",
                    "config": {"doc_column": "content", "chunk_size": 200},
                    "input_edges": [{"node_id_ref": "extract-1"}],
                    "output_edges": [{"node_id_ref": "vectordb-1"}],
                },
                {
                    "id": "vectordb-1",
                    "name": "store_in_opensearch",
                    "operator": "vectordb",
                    "config": {
                        "provider": "opensearch",
                        "provider_config": {
                            "host": "localhost",
                            "port": 9200,
                            "use_ssl": False,
                        },
                        "index_name": "test_index",
                        "vector_dimension": 384,
                        "doc_id_column": "id",
                        "embeddings_column": "embeddings",
                    },
                    "input_edges": [{"node_id_ref": "chunker-1"}],
                    "output_edges": [],
                },
            ]
        }

        with pytest.raises(FlowValidationException) as exc_info:
            validator.validate_dag(flow_def=flow_def, global_config={})

        errors = exc_info.value.errors or []
        assert any(
            ValidationCodeMessages.INGEST_OPERATOR_MISPLACED.name in str(error.message_code) for error in errors
        ), "Expected INGEST_OPERATOR_MISPLACED error not found"

    def test_integration_empty_dag_fails(self, validator):
        """Test that empty DAG fails validation."""
        flow_def = {"dag": []}

        with pytest.raises(FlowValidationException) as exc_info:
            validator.validate_dag(flow_def=flow_def, global_config={})

        errors = exc_info.value.errors or []
        assert any(ValidationCodeMessages.DAG_PIPELINE_MISSING.name in str(error.message_code) for error in errors), (
            "Expected DAG_PIPELINE_MISSING error not found"
        )

    def test_integration_duplicate_operator_names_fails(self, validator, fixtures_invoices_dir):
        """Test that duplicate operator names fail validation."""
        flow_def = {
            "dag": [
                {
                    "id": "ingest-1",
                    "name": "duplicate_name",
                    "operator": "ingest_local",
                    "config": {"paths": str(fixtures_invoices_dir)},
                    "input_edges": [],
                    "output_edges": [{"node_id_ref": "extract-1"}],
                },
                {
                    "id": "extract-1",
                    "name": "duplicate_name",
                    "operator": "extract_operator",
                    "config": {"doc_column": "content"},
                    "input_edges": [{"node_id_ref": "ingest-1"}],
                    "output_edges": [],
                },
            ]
        }

        with pytest.raises(FlowValidationException) as exc_info:
            validator.validate_dag(flow_def=flow_def, global_config={})

        errors = exc_info.value.errors or []
        assert any(ValidationCodeMessages.OPERATOR_NAME_REPEATED.name in str(error.message_code) for error in errors), (
            "Expected OPERATOR_NAME_REPEATED error not found"
        )

    def test_integration_disjoint_operators_fails(self, validator, fixtures_invoices_dir):
        """Test that disjoint operators fail validation."""
        flow_def = {
            "dag": [
                {
                    "id": "ingest-1",
                    "name": "ingest_documents",
                    "operator": "ingest_local",
                    "config": {"paths": str(fixtures_invoices_dir)},
                    "input_edges": [],
                    "output_edges": [],
                },
                {
                    "id": "extract-1",
                    "name": "extract_documents",
                    "operator": "extract_operator",
                    "config": {"doc_column": "content"},
                    "input_edges": [],
                    "output_edges": [],
                },
            ]
        }

        with pytest.raises(FlowValidationException) as exc_info:
            validator.validate_dag(flow_def=flow_def, global_config={})

        errors = exc_info.value.errors or []
        assert any(
            ValidationCodeMessages.DISJOINT_OPERATORS_DETECTED.name in str(error.message_code) for error in errors
        ), "Expected DISJOINT_OPERATORS_DETECTED error not found"

    def test_integration_multiple_extract_operators_warns(self, validator, fixtures_invoices_dir):
        """Test that multiple extract operators generate warnings."""
        flow_def = {
            "dag": [
                {
                    "id": "ingest-1",
                    "name": "ingest_documents",
                    "operator": "ingest_local",
                    "config": {"paths": str(fixtures_invoices_dir)},
                    "input_edges": [],
                    "output_edges": [{"node_id_ref": "extract-1"}],
                },
                {
                    "id": "extract-1",
                    "name": "extract_documents_1",
                    "operator": "extract_operator",
                    "config": {"doc_column": "content"},
                    "input_edges": [{"node_id_ref": "ingest-1"}],
                    "output_edges": [{"node_id_ref": "extract-2"}],
                },
                {
                    "id": "extract-2",
                    "name": "extract_documents_2",
                    "operator": "extract_operator",
                    "config": {"doc_column": "content"},
                    "input_edges": [{"node_id_ref": "extract-1"}],
                    "output_edges": [],
                },
            ]
        }

        errors = []
        extract_count = validator.check_duplicate_extract_operators(
            sequence=flow_def["dag"], global_config={}, errors=errors
        )

        assert extract_count == 2, "Expected 2 extract operators"
        assert len(errors) > 0, "Expected error for multiple extract operators"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


# ---------------------------------------------------------------------------
# validate_dag_with_features
# ---------------------------------------------------------------------------


class TestValidateDagWithFeatures:
    """Tests for validate_dag_with_features method."""

    def test_flow_engine_none_raises(self):
        """flow_engine is None raises FlowValidationException."""
        validator = make_validator()
        validator.orchestrator.flow_engine = None

        flow_def = {
            DocpipeConstants.DAG: [
                make_node("n1", "ingest_local", output_edges=[{"node_id_ref": "n2"}]),
                make_node("n2", "extract_operator", output_edges=[]),
            ]
        }

        # validate_dag itself will raise before feature propagation because
        # flow_engine is None; the exception must be FlowValidationException.
        with pytest.raises(FlowValidationException):
            validator.validate_dag_with_features(flow_def=flow_def, global_config={})

    @patch("docpipe.core.orchestration.flow_validator.clean_up_prefect_home")
    def test_successful_feature_propagation(self, mock_cleanup):
        """Successful path returns a FeaturePropagationResult."""
        from docpipe.core.orchestration.feature_propagation.models import FeaturePropagationResult

        validator = make_validator()

        # Stub validate_dag so it does not raise
        with patch.object(validator, "validate_dag"):
            # Simulate flow_engine.execute_non_execute_flow running the task
            def fake_execute(flow_name, task, dag):
                for node in dag:
                    task("t", node, prev_result=None)

            validator.orchestrator.flow_engine.execute_non_execute_flow.side_effect = fake_execute

            flow_def = {
                DocpipeConstants.DAG: [
                    make_node("n1", "ingest_local", output_edges=[]),
                ]
            }

            result = validator.validate_dag_with_features(flow_def=flow_def, global_config={})

        assert isinstance(result, FeaturePropagationResult)
        mock_cleanup.assert_called()


# ---------------------------------------------------------------------------
# _validate_node
# ---------------------------------------------------------------------------


class TestValidateNode:
    """Tests for _validate_node method."""

    def _make_op_def(self, node_id="n1", operator="some_op"):
        return {
            "id": node_id,
            OperatorConstants.Misc.OPERATOR: operator,
            OperatorConstants.Misc.NAME: "Test Node",
            OperatorConstants.Config.CONFIG: {},
        }

    def test_session_info_is_set_when_not_none(self):
        """session_info is not None triggers set_session_info (line 480)."""
        validator = make_validator()
        mock_session = Mock()

        validate_results = ValidateStepResults(available_features={}, errors=[], warnings=[])

        with (
            patch("docpipe.core.orchestration.flow_validator.set_session_info") as mock_set,
            patch.object(validator, "_build_node_feature_result") as mock_build,
            patch.object(validator, "_get_required_node_fields") as mock_fields,
            patch(
                "docpipe.core.orchestration.flow_validator.OperatorFactoryProvider.get_operator_factory"
            ) as mock_factory_provider,
        ):
            from docpipe.core.orchestration.feature_propagation.models import FeaturePropagationResult

            mock_result = FeaturePropagationResult()
            mock_build.return_value = mock_result
            mock_fields.return_value = ("n1", "some_op", {})
            mock_factory = Mock()
            mock_factory.operators = {}
            mock_factory_provider.return_value = mock_factory

            validator._validate_node(
                op_def=self._make_op_def(),
                prev_result=None,
                global_config={},
                validate_results=validate_results,
                session_info=mock_session,
            )

        mock_set.assert_called_once_with(session_info=mock_session)

    def test_session_info_none_does_not_call_set(self):
        """session_info None skips set_session_info call."""
        validator = make_validator()

        validate_results = ValidateStepResults(available_features={}, errors=[], warnings=[])

        with (
            patch("docpipe.core.orchestration.flow_validator.set_session_info") as mock_set,
            patch.object(validator, "_build_node_feature_result") as mock_build,
            patch.object(validator, "_get_required_node_fields") as mock_fields,
            patch(
                "docpipe.core.orchestration.flow_validator.OperatorFactoryProvider.get_operator_factory"
            ) as mock_factory_provider,
        ):
            from docpipe.core.orchestration.feature_propagation.models import FeaturePropagationResult

            mock_result = FeaturePropagationResult()
            mock_build.return_value = mock_result
            mock_fields.return_value = ("n1", "some_op", {})
            mock_factory = Mock()
            mock_factory.operators = {}
            mock_factory_provider.return_value = mock_factory

            validator._validate_node(
                op_def=self._make_op_def(),
                prev_result=None,
                global_config={},
                validate_results=validate_results,
                session_info=None,
            )

        mock_set.assert_not_called()

    def test_operator_class_none_adds_error(self):
        """operator_class is None adds error and returns early (lines 510-518)."""
        validator = make_validator()
        validate_results = ValidateStepResults(available_features={}, errors=[], warnings=[])

        with (
            patch.object(validator, "_build_node_feature_result") as mock_build,
            patch.object(validator, "_get_required_node_fields") as mock_fields,
            patch.object(validator, "_evaluate_node_validation_skip", return_value=False),
            patch(
                "docpipe.core.orchestration.flow_validator.OperatorFactoryProvider.get_operator_factory"
            ) as mock_factory_provider,
        ):
            from docpipe.core.orchestration.feature_propagation.models import FeaturePropagationResult

            mock_result = FeaturePropagationResult()
            mock_build.return_value = mock_result
            mock_fields.return_value = ("n1", "missing_op", {})
            mock_factory = Mock()
            mock_factory.operators = {}  # operator not registered
            mock_factory_provider.return_value = mock_factory

            result = validator._validate_node(
                op_def=self._make_op_def(operator="missing_op"),
                prev_result=None,
                global_config={},
                validate_results=validate_results,
                session_info=None,
            )

        assert len(validate_results.errors) > 0
        assert any("missing_op" in str(e) for e in validate_results.errors)
        assert result is mock_result

    def test_flow_validation_exception_from_operator_validate(self):
        """FlowValidationException from operator.validate is caught (lines 531-535)."""
        from docpipe.exceptions.docpipe_exceptions import ValidationAlert

        validator = make_validator()
        validate_results = ValidateStepResults(available_features={}, errors=[], warnings=[])

        sentinel_error = ValidationAlert("FLOW_VALIDATION_FAILED", message="operator blew up", message_code="TEST_ERR")

        mock_operator_class = Mock()
        mock_operator_instance = Mock()
        mock_operator_class.return_value = mock_operator_instance
        mock_operator_instance.validate.side_effect = FlowValidationException(errors=[sentinel_error])

        with (
            patch.object(validator, "_build_node_feature_result") as mock_build,
            patch.object(validator, "_get_required_node_fields") as mock_fields,
            patch.object(validator, "_evaluate_node_validation_skip", return_value=False),
            patch(
                "docpipe.core.orchestration.flow_validator.OperatorFactoryProvider.get_operator_factory"
            ) as mock_factory_provider,
        ):
            from docpipe.core.orchestration.feature_propagation.models import FeaturePropagationResult

            mock_result = FeaturePropagationResult()
            mock_build.return_value = mock_result
            mock_fields.return_value = ("n1", "some_op", {})
            mock_factory = Mock()
            mock_factory.operators = {"some_op": mock_operator_class}
            mock_factory_provider.return_value = mock_factory

            validator._validate_node(
                op_def=self._make_op_def(),
                prev_result=None,
                global_config={},
                validate_results=validate_results,
                session_info=None,
            )

        assert sentinel_error in validate_results.errors

    def test_generic_exception_from_operator_validate(self):
        """Generic exception from operator.validate is caught (lines 536-544)."""
        validator = make_validator()
        validate_results = ValidateStepResults(available_features={}, errors=[], warnings=[])

        mock_operator_class = Mock()
        mock_operator_instance = Mock()
        mock_operator_class.return_value = mock_operator_instance
        mock_operator_instance.validate.side_effect = RuntimeError("unexpected error")

        with (
            patch.object(validator, "_build_node_feature_result") as mock_build,
            patch.object(validator, "_get_required_node_fields") as mock_fields,
            patch.object(validator, "_evaluate_node_validation_skip", return_value=False),
            patch(
                "docpipe.core.orchestration.flow_validator.OperatorFactoryProvider.get_operator_factory"
            ) as mock_factory_provider,
        ):
            from docpipe.core.orchestration.feature_propagation.models import FeaturePropagationResult

            mock_result = FeaturePropagationResult()
            mock_build.return_value = mock_result
            mock_fields.return_value = ("n1", "some_op", {})
            mock_factory = Mock()
            mock_factory.operators = {"some_op": mock_operator_class}
            mock_factory_provider.return_value = mock_factory

            validator._validate_node(
                op_def=self._make_op_def(),
                prev_result=None,
                global_config={},
                validate_results=validate_results,
                session_info=None,
            )

        assert len(validate_results.errors) > 0
        assert any("unexpected error" in str(e) for e in validate_results.errors)

    def test_evaluate_node_validation_skip_returns_early(self):
        """_evaluate_node_validation_skip returning True causes early return (lines 499-504)."""
        validator = make_validator()
        validate_results = ValidateStepResults(available_features={}, errors=[], warnings=[])

        with (
            patch.object(validator, "_build_node_feature_result") as mock_build,
            patch.object(validator, "_get_required_node_fields") as mock_fields,
            patch.object(validator, "_evaluate_node_validation_skip", return_value=True),
            patch(
                "docpipe.core.orchestration.flow_validator.OperatorFactoryProvider.get_operator_factory"
            ) as mock_factory_provider,
        ):
            from docpipe.core.orchestration.feature_propagation.models import FeaturePropagationResult

            mock_result = FeaturePropagationResult()
            mock_build.return_value = mock_result
            mock_fields.return_value = ("n1", "some_op", {})
            mock_factory = Mock()
            mock_factory.operators = {}
            mock_factory_provider.return_value = mock_factory

            result = validator._validate_node(
                op_def=self._make_op_def(),
                prev_result=None,
                global_config={},
                validate_results=validate_results,
                session_info=None,
            )

        assert result is mock_result
        assert len(validate_results.errors) == 0


# ---------------------------------------------------------------------------
# _get_parent_results
# ---------------------------------------------------------------------------


class TestGetParentResults:
    """Tests for _get_parent_results method."""

    def test_single_propagation_result_wrapped_in_list(self):
        """A single FeaturePropagationResult is returned in a 1-element list."""
        from docpipe.core.orchestration.feature_propagation.models import FeaturePropagationResult

        validator = make_validator()
        r = FeaturePropagationResult()
        result = validator._get_parent_results(prev_result=r)
        assert result == [r]

    def test_list_filters_non_results(self):
        """List input keeps only FeaturePropagationResult items (lines 552-553)."""
        from docpipe.core.orchestration.feature_propagation.models import FeaturePropagationResult

        validator = make_validator()
        r = FeaturePropagationResult()
        result = validator._get_parent_results(prev_result=[r, "not_a_result", 42])
        assert result == [r]

    def test_dict_filters_non_results(self):
        """Dict input keeps only FeaturePropagationResult values (lines 554-555)."""
        from docpipe.core.orchestration.feature_propagation.models import FeaturePropagationResult

        validator = make_validator()
        r = FeaturePropagationResult()
        result = validator._get_parent_results(prev_result={"node1": r, "node2": "bad"})
        assert result == [r]

    def test_none_returns_empty_list(self):
        """None (other) input returns empty list (line 556)."""
        validator = make_validator()
        result = validator._get_parent_results(prev_result=None)
        assert result == []

    def test_unexpected_type_returns_empty_list(self):
        """Unrecognised type returns empty list."""
        validator = make_validator()
        result = validator._get_parent_results(prev_result=12345)
        assert result == []


# ---------------------------------------------------------------------------
# _feature_metadata_to_dict
# ---------------------------------------------------------------------------


class TestFeatureMetadataToDict:
    """Tests for _feature_metadata_to_dict method."""

    def test_node_id_present_in_metadata(self):
        """node_id on a feature is included as source_node_id (line 567)."""
        from docpipe.core.orchestration.feature_propagation.models import FeaturePropagationResult

        validator = make_validator()
        result = FeaturePropagationResult()
        result.add_feature(
            feature_name="my_feature",
            node_id="node-1",
            description="test",
            available_for_vector_db=True,
        )

        out = validator._feature_metadata_to_dict(result=result)

        assert "my_feature" in out
        assert out["my_feature"]["source_node_id"] == "node-1"
        assert out["my_feature"]["available_for_vector_db"] is True

    def test_feature_without_node_id_omitted(self):
        """Feature whose node_id is empty string omits source_node_id key."""
        from docpipe.core.orchestration.feature_propagation.models import FeatureMetadata, FeaturePropagationResult

        validator = make_validator()
        result = FeaturePropagationResult()
        # Manually insert metadata with empty node_id to exercise the conditional
        result.feature_metadata["feat"] = FeatureMetadata(name="feat", node_id="")

        out = validator._feature_metadata_to_dict(result=result)

        assert "source_node_id" not in out["feat"]


# ---------------------------------------------------------------------------
# _get_required_node_fields
# ---------------------------------------------------------------------------


class TestGetRequiredNodeFields:
    """Tests for _get_required_node_fields method."""

    def test_missing_node_id_raises(self):
        """Missing id raises FlowValidationException (lines 578-587)."""
        validator = make_validator()
        with pytest.raises(FlowValidationException) as exc_info:
            validator._get_required_node_fields(op_def={"operator": "some_op"})
        assert any("id" in str(e).lower() or "INVALID_FLOW_NODE_ID" in str(e) for e in exc_info.value.errors)

    def test_empty_string_node_id_raises(self):
        """Empty string id raises FlowValidationException."""
        validator = make_validator()
        with pytest.raises(FlowValidationException):
            validator._get_required_node_fields(op_def={"id": "", "operator": "some_op"})

    def test_missing_operator_raises(self):
        """Missing operator raises FlowValidationException (lines 589-598)."""
        validator = make_validator()
        with pytest.raises(FlowValidationException) as exc_info:
            validator._get_required_node_fields(op_def={"id": "n1"})
        assert any("INVALID_FLOW_NODE_OPERATOR" in str(e) for e in exc_info.value.errors)

    def test_operator_config_not_dict_defaults_to_empty(self):
        """Non-dict operator_config is coerced to {} (lines 600-601)."""
        validator = make_validator()
        node_id, operator, op_config = validator._get_required_node_fields(
            op_def={"id": "n1", "operator": "my_op", "config": "bad_value"}
        )
        assert node_id == "n1"
        assert operator == "my_op"
        assert op_config == {}

    def test_valid_fields_returned(self):
        """Valid fields are returned as a tuple."""
        validator = make_validator()
        node_id, operator, op_config = validator._get_required_node_fields(
            op_def={"id": "n1", "operator": "my_op", "config": {"key": "val"}}
        )
        assert node_id == "n1"
        assert operator == "my_op"
        assert op_config == {"key": "val"}


# ---------------------------------------------------------------------------
# _build_node_feature_result
# ---------------------------------------------------------------------------


class TestBuildNodeFeatureResult:
    """Tests for _build_node_feature_result method."""

    def test_returns_feature_propagation_result(self):
        """Normal operation returns a FeaturePropagationResult (lines 605-628)."""
        from docpipe.core.orchestration.feature_propagation.models import FeaturePropagationResult

        validator = make_validator()

        with patch.object(validator.feature_propagator, "propagate_features") as mock_propagate:
            mock_propagate.return_value = FeaturePropagationResult()

            op_def = {"id": "n1", "operator": "some_op", "config": {}}
            result = validator._build_node_feature_result(op_def=op_def, prev_result=None, global_config={})

        assert isinstance(result, FeaturePropagationResult)
        mock_propagate.assert_called_once()

    def test_passes_input_features_from_parents(self):
        """Parent results' features are merged and passed to propagate_features."""
        from docpipe.core.orchestration.feature_propagation.models import FeaturePropagationResult

        validator = make_validator()
        parent = FeaturePropagationResult()
        parent.add_feature(feature_name="col1", node_id="p1", available_for_vector_db=False)

        with patch.object(validator.feature_propagator, "propagate_features") as mock_propagate:
            mock_propagate.return_value = FeaturePropagationResult()

            op_def = {"id": "n2", "operator": "some_op", "config": {}}
            validator._build_node_feature_result(op_def=op_def, prev_result=parent, global_config={})

        call_kwargs = mock_propagate.call_args.kwargs
        assert "col1" in call_kwargs["input_features"]


# ---------------------------------------------------------------------------
# _merge_node_result_into_propagation_result
# ---------------------------------------------------------------------------


class TestMergeNodeResultIntoPropagationResult:
    """Tests for _merge_node_result_into_propagation_result method."""

    def test_features_with_opensearch_support_stored(self):
        """Features flagged available_for_vector_db are stored as opensearch features (lines 642-646)."""
        from docpipe.core.orchestration.feature_propagation.models import FeaturePropagationResult

        validator = make_validator()
        op_def = {"id": "n1", "operator": "some_op", "config": {}}
        node_result = FeaturePropagationResult()
        node_result.add_feature(
            feature_name="embeddings",
            node_id="n1",
            available_for_vector_db=True,
        )

        propagation_result = FeaturePropagationResult()
        validator._merge_node_result_into_propagation_result(
            op_def=op_def,
            node_result=node_result,
            propagation_result=propagation_result,
        )

        assert "n1" in propagation_result.opensearch_features
        assert "embeddings" in propagation_result.opensearch_features["n1"]

    def test_features_without_opensearch_not_stored(self):
        """Features without vector_db flag are not added to opensearch_features."""
        from docpipe.core.orchestration.feature_propagation.models import FeaturePropagationResult

        validator = make_validator()
        op_def = {"id": "n1", "operator": "some_op", "config": {}}
        node_result = FeaturePropagationResult()
        node_result.add_feature(
            feature_name="plain_col",
            node_id="n1",
            available_for_vector_db=False,
        )

        propagation_result = FeaturePropagationResult()
        validator._merge_node_result_into_propagation_result(
            op_def=op_def,
            node_result=node_result,
            propagation_result=propagation_result,
        )

        assert "n1" not in propagation_result.opensearch_features

    def test_scoped_feature_metadata_written(self):
        """Merged features are stored under both scoped and plain names."""
        from docpipe.core.orchestration.feature_propagation.models import FeaturePropagationResult

        validator = make_validator()
        op_def = {"id": "n1", "operator": "some_op", "config": {}}
        node_result = FeaturePropagationResult()
        node_result.add_feature(feature_name="content", node_id="n1")

        propagation_result = FeaturePropagationResult()
        validator._merge_node_result_into_propagation_result(
            op_def=op_def,
            node_result=node_result,
            propagation_result=propagation_result,
        )

        assert "n1.content" in propagation_result.feature_metadata
        assert "content" in propagation_result.feature_metadata


# ---------------------------------------------------------------------------
# debug_feature_propagation
# ---------------------------------------------------------------------------


class TestDebugFeaturePropagation:
    """Tests for debug_feature_propagation method."""

    def test_flow_engine_none_raises(self):
        """flow_engine is None raises FlowValidationException (lines 702-711)."""
        validator = make_validator()
        validator.orchestrator.flow_engine = None

        flow_def = {
            DocpipeConstants.DAG: [
                make_node("n1", "ingest_local", output_edges=[]),
            ]
        }

        with pytest.raises(FlowValidationException):
            validator.debug_feature_propagation(flow_def=flow_def, global_config={})

    def test_definition_key_unwrapped(self):
        """flow_def with 'definition' key is unwrapped before processing (line 662)."""
        validator = make_validator()

        inner_flow = {
            DocpipeConstants.DAG: [
                make_node("n1", "ingest_local", output_edges=[]),
            ]
        }

        flow_def = {"definition": inner_flow}

        with patch("docpipe.core.orchestration.flow_validator.clean_up_prefect_home"):
            validator.debug_feature_propagation(flow_def=flow_def, global_config={})

        # The flow_engine is already a Mock; confirm execute_non_execute_flow was called
        validator.orchestrator.flow_engine.execute_non_execute_flow.assert_called_once()

    def test_flow_key_unwrapped(self):
        """flow_def with nested 'flow' key is unwrapped before processing (line 664)."""
        validator = make_validator()

        inner_flow = {
            DocpipeConstants.DAG: [
                make_node("n1", "ingest_local", output_edges=[]),
            ]
        }

        flow_def = {"flow": inner_flow}

        with patch("docpipe.core.orchestration.flow_validator.clean_up_prefect_home"):
            validator.debug_feature_propagation(flow_def=flow_def, global_config={})

        validator.orchestrator.flow_engine.execute_non_execute_flow.assert_called_once()

    @patch("docpipe.core.orchestration.flow_validator.clean_up_prefect_home")
    def test_full_traversal_returns_snapshots(self, mock_cleanup):
        """Full traversal populates per-node snapshots and returns them (lines 713-717)."""
        validator = make_validator()

        def fake_execute(flow_name, task, dag):
            for node in dag:
                task("t", node, prev_result=None)

        validator.orchestrator.flow_engine.execute_non_execute_flow.side_effect = fake_execute

        flow_def = {
            DocpipeConstants.DAG: [
                make_node("n1", "ingest_local", output_edges=[]),
            ]
        }

        result = validator.debug_feature_propagation(flow_def=flow_def, global_config={})

        assert isinstance(result, dict)
        mock_cleanup.assert_called()


# ---------------------------------------------------------------------------
# _build_reverse_graph
# ---------------------------------------------------------------------------


class TestBuildReverseGraph:
    """Tests for _build_reverse_graph method."""

    def test_standard_operation(self):
        """Standard DAG builds correct reverse mapping (lines 773-781)."""
        validator = make_validator()

        dag = [
            {"id": "n1", DocpipeConstants.OUTPUT_EDGES: [{"node_id_ref": "n2"}]},
            {"id": "n2", DocpipeConstants.OUTPUT_EDGES: [{"node_id_ref": "n3"}]},
            {"id": "n3", DocpipeConstants.OUTPUT_EDGES: []},
        ]

        reverse = validator._build_reverse_graph(dag)

        assert reverse["n1"] == []
        assert reverse["n2"] == ["n1"]
        assert reverse["n3"] == ["n2"]

    def test_node_with_no_edges_has_empty_parents(self):
        """Node with no output edges has empty parent list."""
        validator = make_validator()
        dag = [{"id": "solo", DocpipeConstants.OUTPUT_EDGES: []}]
        reverse = validator._build_reverse_graph(dag)
        assert reverse["solo"] == []


# ---------------------------------------------------------------------------
# _validate_disconnected_components
# ---------------------------------------------------------------------------


class TestValidateDisconnectedComponents:
    """Tests for _validate_disconnected_components method."""

    def test_terminal_node_id_none_skips_reporting(self):
        """Component with no terminal node (all nodes have outgoing edges) is skipped (line 797-798)."""
        validator = make_validator()

        dag = [
            {"id": "n1", DocpipeConstants.OUTPUT_EDGES: [{"node_id_ref": "n2"}]},
            {"id": "n2", DocpipeConstants.OUTPUT_EDGES: [{"node_id_ref": "n1"}]},  # cycle, no terminal
        ]
        graph = validator._build_graph(dag)
        components = [{"n1", "n2"}]
        id_to_index = {"n1": 0, "n2": 1}
        validate_results = ValidateStepResults(available_features={}, errors=[], warnings=[])
        reported_nodes: set = set()

        validator._validate_disconnected_components(
            components=components,
            graph=graph,
            dag=dag,
            id_to_index=id_to_index,
            global_config={},
            validate_results=validate_results,
            reported_nodes=reported_nodes,
        )

        # No errors because _find_terminal_node returns None for the cyclic component
        assert len(validate_results.errors) == 0


# ---------------------------------------------------------------------------
# _find_terminal_node
# ---------------------------------------------------------------------------


class TestFindTerminalNode:
    """Tests for _find_terminal_node method."""

    def test_node_with_no_outgoing_edges_is_terminal(self):
        """Node with empty adjacency is returned as terminal (returns node_id)."""
        validator = make_validator()
        graph = {"n1": ["n2"], "n2": []}
        component = {"n1", "n2"}
        result = validator._find_terminal_node(component, graph)
        assert result == "n2"

    def test_no_terminal_returns_none(self):
        """All nodes have outgoing edges so None is returned (line 814)."""
        validator = make_validator()
        graph = {"n1": ["n2"], "n2": ["n1"]}
        component = {"n1", "n2"}
        result = validator._find_terminal_node(component, graph)
        assert result is None


# ---------------------------------------------------------------------------
# _report_non_vectordb_terminal
# ---------------------------------------------------------------------------


class TestReportNonVectorDBTerminal:
    """Tests for _report_non_vectordb_terminal method."""

    def test_index_none_returns_without_error(self):
        """terminal_node_id not in id_to_index returns silently (lines 828-829)."""
        validator = make_validator()
        validate_results = ValidateStepResults(available_features={}, errors=[], warnings=[])
        reported_nodes: set = set()

        validator._report_non_vectordb_terminal(
            terminal_node_id="nonexistent",
            id_to_index={},
            dag=[],
            global_config={},
            validate_results=validate_results,
            reported_nodes=reported_nodes,
        )

        assert len(validate_results.errors) == 0

    def test_vectordb_terminal_adds_no_alert(self):
        """VectorDB terminal does not add error (line 836 -> exit branch)."""
        validator = make_validator()
        dag = [make_node("n1", "vectordb")]
        validate_results = ValidateStepResults(available_features={}, errors=[], warnings=[])
        reported_nodes: set = set()

        with patch.object(validator, "get_operator_category", return_value=OperatorCategory.VectorDB):
            validator._report_non_vectordb_terminal(
                terminal_node_id="n1",
                id_to_index={"n1": 0},
                dag=dag,
                global_config={},
                validate_results=validate_results,
                reported_nodes=reported_nodes,
            )

        assert len(validate_results.errors) == 0

    def test_non_vectordb_terminal_adds_error(self):
        """Non-VectorDB terminal adds a DISJOINT_OPERATORS_DETECTED error."""
        validator = make_validator()
        dag = [make_node("n1", "some_other_op")]
        validate_results = ValidateStepResults(available_features={}, errors=[], warnings=[])
        reported_nodes: set = set()

        with patch.object(validator, "get_operator_category", return_value=OperatorCategory.Extract):
            validator._report_non_vectordb_terminal(
                terminal_node_id="n1",
                id_to_index={"n1": 0},
                dag=dag,
                global_config={},
                validate_results=validate_results,
                reported_nodes=reported_nodes,
            )

        assert len(validate_results.errors) > 0
        assert "n1" in reported_nodes


# ---------------------------------------------------------------------------
# validate_acl_operator_placement
# ---------------------------------------------------------------------------


class TestValidateAclOperatorPlacement:
    """Tests for validate_acl_operator_placement method."""

    def _acl_node(self, node_id="acl1", output_edges=None):
        return {
            "id": node_id,
            OperatorConstants.Misc.OPERATOR: OperatorConstants.Operators.ACL_OPERATOR,
            OperatorConstants.Misc.NAME: "ACL Node",
            DocpipeConstants.OUTPUT_EDGES: output_edges or [],
        }

    def _ingest_node(self, node_id="ingest1", provider="sharepoint", output_edges=None):
        return {
            "id": node_id,
            OperatorConstants.Misc.OPERATOR: OperatorConstants.Operators.INGEST_SOURCE,
            OperatorConstants.Misc.NAME: "Ingest Node",
            OperatorConstants.Config.CONFIG: {"provider": provider},
            DocpipeConstants.OUTPUT_EDGES: output_edges or [{"node_id_ref": "acl1"}],
        }

    def test_no_acl_operators_returns_early(self):
        """No ACL operators in DAG returns without errors (early return line 888)."""
        validator = make_validator()
        dag = [make_node("n1", "ingest_local"), make_node("n2", "extract_operator")]
        results = ValidateStepResults(available_features={}, errors=[], warnings=[])

        validator.validate_acl_operator_placement(dag=dag, validate_results=results)

        assert len(results.errors) == 0

    def test_multiple_acl_operators_adds_errors(self):
        """Two ACL operators each get an error (lines 891-901)."""
        validator = make_validator()
        acl1 = self._acl_node("acl1")
        acl2 = self._acl_node("acl2")
        dag = [acl1, acl2]
        results = ValidateStepResults(available_features={}, errors=[], warnings=[])

        validator.validate_acl_operator_placement(dag=dag, validate_results=results)

        assert len(results.errors) == 2
        assert all("MULTIPLE_ACL_OPERATORS" in str(e) for e in results.errors)

    def test_acl_with_no_parents_adds_error(self):
        """ACL operator with no parents adds ACL_OPERATOR_NO_INPUT error (lines 917-926)."""
        validator = make_validator()
        acl = self._acl_node("acl1")
        dag = [make_node("n1", "some_op", output_edges=[]), acl]
        results = ValidateStepResults(available_features={}, errors=[], warnings=[])

        validator.validate_acl_operator_placement(dag=dag, validate_results=results)

        assert len(results.errors) > 0
        assert any("ACL_OPERATOR_NO_INPUT" in str(e) for e in results.errors)

    def test_acl_with_multiple_parents_adds_error(self):
        """ACL operator with multiple parents adds ACL_MULTIPLE_PARENTS error (lines 932-943)."""
        validator = make_validator()
        parent1 = {
            "id": "p1",
            OperatorConstants.Misc.OPERATOR: "op1",
            DocpipeConstants.OUTPUT_EDGES: [{"node_id_ref": "acl1"}],
        }
        parent2 = {
            "id": "p2",
            OperatorConstants.Misc.OPERATOR: "op2",
            DocpipeConstants.OUTPUT_EDGES: [{"node_id_ref": "acl1"}],
        }
        acl = self._acl_node("acl1")
        dag = [parent1, parent2, acl]
        results = ValidateStepResults(available_features={}, errors=[], warnings=[])

        validator.validate_acl_operator_placement(dag=dag, validate_results=results)

        assert len(results.errors) > 0
        assert any("ACL_MULTIPLE_PARENTS" in str(e) for e in results.errors)

    def test_acl_parent_is_not_ingest_source_adds_error(self):
        """ACL parent is not ingest_source adds ACL_OPERATOR_MISPLACED error (lines 958-968)."""
        validator = make_validator()
        non_ingest = {
            "id": "p1",
            OperatorConstants.Misc.OPERATOR: "extract_operator",
            DocpipeConstants.OUTPUT_EDGES: [{"node_id_ref": "acl1"}],
        }
        acl = self._acl_node("acl1")
        dag = [non_ingest, acl]
        results = ValidateStepResults(available_features={}, errors=[], warnings=[])

        validator.validate_acl_operator_placement(dag=dag, validate_results=results)

        assert len(results.errors) > 0
        assert any("ACL_OPERATOR_MISPLACED" in str(e) for e in results.errors)

    def test_acl_parent_ingest_source_non_sharepoint_adds_error(self):
        """ingest_source with non-sharepoint provider adds ACL_INVALID_PROVIDER error (lines 969-975)."""
        validator = make_validator()
        ingest = self._ingest_node("ingest1", provider="local")
        acl = self._acl_node("acl1")
        dag = [ingest, acl]
        results = ValidateStepResults(available_features={}, errors=[], warnings=[])

        validator.validate_acl_operator_placement(dag=dag, validate_results=results)

        assert len(results.errors) > 0
        assert any("ACL_INVALID_PROVIDER" in str(e) for e in results.errors)

    def test_acl_parent_ingest_source_sharepoint_no_error(self):
        """ingest_source with sharepoint provider produces no errors."""
        validator = make_validator()
        ingest = self._ingest_node("ingest1", provider="sharepoint")
        acl = self._acl_node("acl1")
        dag = [ingest, acl]
        results = ValidateStepResults(available_features={}, errors=[], warnings=[])

        validator.validate_acl_operator_placement(dag=dag, validate_results=results)

        assert len(results.errors) == 0
