"""Unit tests for flow_validator module."""

from unittest.mock import Mock, patch

import pytest

from datasift.core.constants.constants import DatasiftConstants
from datasift.core.constants.operator_constants import OperatorConstants
from datasift.core.operators.abstract_operator import OperatorCategory
from datasift.core.orchestration.flow_validator import FlowValidator, ValidateStepResults
from datasift.exceptions.datasift_exceptions import (
    FlowValidationException,
)
from datasift.exceptions.error_messages import ValidationCodeMessages


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
            DatasiftConstants.DAG: [],
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

    @patch("datasift.core.orchestration.flow_validator.clean_up_prefect_home")
    def test_validate_dag_empty_dag(self, mock_cleanup):
        """Test validation with empty DAG."""
        mock_orchestrator = Mock()
        mock_orchestrator.common_log_arguments = {}

        validator = FlowValidator(orchestrator=mock_orchestrator)

        flow_def = {DatasiftConstants.DAG: []}

        with pytest.raises(FlowValidationException) as exc_info:
            validator.validate_dag(flow_def=flow_def, global_config={})

        assert len(exc_info.value.errors) > 0

    @patch("datasift.core.orchestration.flow_validator.clean_up_prefect_home")
    def test_validate_dag_unnamed_operators(self, mock_cleanup):
        """Test validation with unnamed operators."""
        mock_orchestrator = Mock()
        mock_orchestrator.common_log_arguments = {}
        mock_orchestrator.prefect_executor = Mock()
        mock_orchestrator.prefect_executor.build_non_execute_flow = Mock(return_value=Mock())

        validator = FlowValidator(orchestrator=mock_orchestrator)

        flow_def = {
            DatasiftConstants.DAG: [
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

    @patch("datasift.core.orchestration.flow_validator.clean_up_prefect_home")
    def test_validate_dag_duplicate_names(self, mock_cleanup):
        """Test validation with duplicate operator names."""
        mock_orchestrator = Mock()
        mock_orchestrator.common_log_arguments = {}
        mock_orchestrator.prefect_executor = Mock()
        mock_orchestrator.prefect_executor.build_non_execute_flow = Mock(return_value=Mock())

        validator = FlowValidator(orchestrator=mock_orchestrator)

        flow_def = {
            DatasiftConstants.DAG: [
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
            {"id": "node1", DatasiftConstants.OUTPUT_EDGES: [{"node_id_ref": "node2"}]},
            {"id": "node2", DatasiftConstants.OUTPUT_EDGES: [{"node_id_ref": "node3"}]},
            {"id": "node3", DatasiftConstants.OUTPUT_EDGES: []},
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
            {"id": "node1", DatasiftConstants.OUTPUT_EDGES: [{"node_id_ref": "node2"}]},
            {"id": "node2", DatasiftConstants.OUTPUT_EDGES: []},
        ]

        validate_results = ValidateStepResults(available_features={}, errors=[], warnings=[])

        # Should not add errors for connected graph
        validator.validate_disjoint_operators(dag=dag, validate_results=validate_results)

        assert len(validate_results.errors) == 0

    def test_validate_disjoint_operators_disconnected(self):
        """Test validation with disconnected operators."""
        mock_orchestrator = Mock()
        mock_orchestrator.common_log_arguments = {}

        validator = FlowValidator(orchestrator=mock_orchestrator)

        dag = [
            {"id": "node1", DatasiftConstants.OUTPUT_EDGES: []},
            {"id": "node2", DatasiftConstants.OUTPUT_EDGES: []},
        ]

        validate_results = ValidateStepResults(available_features={}, errors=[], warnings=[])

        validator.validate_disjoint_operators(dag=dag, validate_results=validate_results)

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

            from datasift.exceptions.error_messages import ValidationMessage

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

        with patch("datasift.core.orchestration.flow_validator.add_validation_alert") as mock_add:
            validator.create_validation_alerts(op_def=op_def, messages=messages, alerts=alerts)

            assert mock_add.call_count == 2

    def test_evaluate_node_validation_skip_custom_op(self):
        """Test skipping validation for custom operator."""
        mock_orchestrator = Mock()
        mock_orchestrator.common_log_arguments = {}

        validator = FlowValidator(orchestrator=mock_orchestrator)

        mock_factory = Mock()
        mock_factory.operators = {"known_op": Mock()}

        global_config = {DatasiftConstants.SKIP_CUSTOM_OP_VALIDATION: True}

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

        global_config = {DatasiftConstants.SKIP_CUSTOM_OP_VALIDATION: True}

        result = validator._evaluate_node_validation_skip(
            operator="known_op",
            operator_factory=mock_factory,
            global_config=global_config,
        )

        assert result is False


class TestFlowValidatorIntegration:
    """Integration tests for flow validation with real orchestrator."""

    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator instance for testing."""
        from datasift.core.orchestration.orchestrator_factory import OrchestratorFactory

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
                        "host": "localhost",
                        "port": 9200,
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
                        "host": "localhost",
                        "port": 9200,
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
