"""Flow validation module for datasift orchestrator.

This module contains the FlowValidator class which handles all flow validation logic
that was previously embedded in AbstractOrchestrator.
"""

from typing import Any

from datasift.core.constants.constants import DatasiftConstants, OrchestratorType
from datasift.core.constants.operator_constants import OperatorConstants
from datasift.core.models.session_info import get_session_info, set_session_info
from datasift.core.operators.abstract_operator import OperatorCategory
from datasift.core.orchestration.abstract_orchestrator import AbstractOrchestrator
from datasift.core.orchestration.operator_factory import OperatorFactory, OperatorFactoryProvider
from datasift.exceptions.datasift_exceptions import (
    DatasiftException,
    ErrorCode,
    FlowValidationException,
    ValidationAlert,
)
from datasift.exceptions.error_messages import ValidationCodeMessages, ValidationMessage
from datasift.utils.infrastructure.logging import get_logger
from datasift.utils.orchestration.flow_utils import add_validation_alert
from datasift.utils.orchestration.prefect_config import clean_up_prefect_home

logger = get_logger()


class ValidateStepResults:
    """Container for validation results including features, errors, and warnings."""

    def __init__(self, available_features, errors, warnings):
        self.available_features = available_features
        self.errors = errors
        self.warnings = warnings


class FlowValidator:
    """Handles all flow validation logic for the datasift orchestrator.

    This class encapsulates validation methods that check:
    - DAG structure and connectivity
    - Operator placement and categories
    - Node naming and uniqueness
    - Operator-specific validation rules
    """

    def __init__(self, orchestrator: AbstractOrchestrator):
        """Initialize the FlowValidator.

        Args:
            orchestrator: Reference to the AbstractOrchestrator instance
        """
        self.orchestrator = orchestrator
        self.logger = get_logger()
        self.common_log_arguments = orchestrator.common_log_arguments

    def validate(self, *, flow_def: dict, params: dict):
        """Main validation entry point for a flow definition.

        Args:
            flow_def: The flow definition dictionary
            params: Additional parameters to merge with global config

        Raises:
            FlowValidationException: If validation fails
        """
        global_config = flow_def.get(OperatorConstants.Config.GLOBAL_CONFIG, {}) | params

        # Skip validation if explicitly disabled
        if global_config.get(OperatorConstants.Config.DISABLE_VALIDATION, False):
            return

        if DatasiftConstants.DAG not in flow_def:
            raise FlowValidationException(
                errors=[
                    ValidationAlert(
                        ErrorCode.FLOW_VALIDATION_FAILED.value,
                        message=ValidationCodeMessages.PIPELINE_NOT_FOUND_ERROR.value,
                        message_code=ValidationCodeMessages.PIPELINE_NOT_FOUND_ERROR.name,
                    )
                ]
            )
        self.validate_dag(flow_def=flow_def, global_config=global_config)

    def validate_dag(self, *, flow_def: dict, global_config: dict):
        """Validate the DAG structure and all nodes.

        Args:
            flow_def: The flow definition dictionary
            global_config: Global configuration dictionary

        Raises:
            FlowValidationException: If validation fails
        """
        logger.info("Validating DAG", extra=self.common_log_arguments)
        errors: list[Any] = []
        warnings: list[Any] = []

        dag = flow_def.get(DatasiftConstants.DAG, [])
        if not dag:
            errors.append(
                ValidationAlert(
                    ErrorCode.FLOW_VALIDATION_FAILED.value,
                    message=ValidationCodeMessages.DAG_PIPELINE_MISSING.value,
                    message_code=ValidationCodeMessages.DAG_PIPELINE_MISSING.name,
                )
            )
            raise FlowValidationException(errors=errors)

        unnamed_operators = [
            node[OperatorConstants.Misc.OPERATOR] for node in dag if OperatorConstants.Misc.NAME not in node
        ]
        if unnamed_operators:
            warnings.append(
                ValidationAlert(
                    ErrorCode.FLOW_VALIDATION_FAILED.value,
                    f"The following operators are missing names: {', '.join(unnamed_operators)}",
                )
            )

        # Operator name uniqueness check
        operator_names = [
            op_def[OperatorConstants.Columns.NAME] for op_def in dag if OperatorConstants.Columns.NAME in op_def
        ]
        duplicates = self.get_duplicate_node_names(nodes=operator_names)
        if duplicates:
            errors.append(
                ValidationAlert(
                    ErrorCode.FLOW_VALIDATION_FAILED.value,
                    message=ValidationCodeMessages.OPERATOR_NAME_REPEATED.value.format(operators=", ".join(duplicates)),
                    message_code=ValidationCodeMessages.OPERATOR_NAME_REPEATED.name,
                    operators=duplicates,
                )
            )
            self.logger.error(f"Duplicate operator names have been found with: {','.join(duplicates)}")

        validate_results = ValidateStepResults(available_features={}, errors=errors, warnings=warnings)
        session_info = get_session_info()

        self.validate_first_operator(dag=dag, global_config=global_config, validate_results=validate_results)
        self.validate_disjoint_operators(dag=dag, validate_results=validate_results)

        def node_validation_task(task_name, op_def, result=None, link_name=None):
            return self._validate_node(
                op_def=op_def, global_config=global_config, validate_results=validate_results, session_info=session_info
            )

        if self.orchestrator.flow_engine is None:
            raise FlowValidationException(
                errors=[
                    ValidationAlert(
                        ErrorCode.FLOW_VALIDATION_FAILED.value,
                        message="Flow engine not initialized",
                        message_code="FLOW_ENGINE_NOT_INITIALIZED",
                    )
                ]
            )

        self.orchestrator.flow_engine.execute_non_execute_flow(
            flow_name="dag_validation_flow", task=node_validation_task, dag=dag
        )
        clean_up_prefect_home()

        self.validate_last_operator(dag=dag, global_config=global_config, validate_results=validate_results)

        if validate_results.errors or validate_results.warnings:
            self.logger.error(f"Validation errors: {validate_results.errors}")
            raise FlowValidationException(errors=validate_results.errors, warnings=validate_results.warnings)

    def validate_first_operator(self, *, dag: list, global_config: dict, validate_results: ValidateStepResults):
        """Validate that the first operator in the DAG is an Ingest operator.

        Args:
            dag: List of operator definitions
            global_config: Global configuration dictionary
            validate_results: Container for validation results
        """
        # If the first operator is not an ingest, then add an error.
        self.validate_operator_category(
            op_def=dag[0],
            global_config=global_config,
            expected_category=OperatorCategory.Ingest,
            error_message=ValidationMessage(
                message=ValidationCodeMessages.INGEST_OPERATOR_MISPLACED.value,
                message_code=ValidationCodeMessages.INGEST_OPERATOR_MISPLACED.name,
            ),
            alerts=validate_results.errors,
        )

    def validate_disjoint_operators(self, *, dag: list, validate_results: ValidateStepResults):
        """Validate that the DAG does not contain disconnected (disjoint) operators.

        Args:
            dag: List of operator definitions
            validate_results: Container for validation results
        """
        graph = self._build_graph(dag)
        undirected = self._make_undirected_graph(graph)
        components = self._find_connected_components(undirected)

        if len(components) > 1:
            # Identify the last operator node in the first connected component and report it in the error.
            id_to_index = {n["id"]: i for i, n in enumerate(dag)}
            index = id_to_index.get(list(components[0])[-1])
            if index is not None:
                add_validation_alert(
                    message=ValidationMessage(
                        message=ValidationCodeMessages.DISJOINT_OPERATORS_DETECTED.value,
                        message_code=ValidationCodeMessages.DISJOINT_OPERATORS_DETECTED.name,
                    ),
                    op_def=dag[index],
                    alerts=validate_results.errors,
                )

    def _build_graph(self, dag: list) -> dict:
        """Build a directed graph representation from the DAG.

        Args:
            dag: List of operator definitions

        Returns:
            Dictionary mapping node IDs to lists of connected node IDs
        """
        graph: dict[str, list[str]] = {n["id"]: [] for n in dag}
        for node in dag:
            for edge in node.get(DatasiftConstants.OUTPUT_EDGES, []):
                graph[node["id"]].append(edge["node_id_ref"])
        return graph

    def _make_undirected_graph(self, graph: dict) -> dict:
        """Convert a directed graph into an undirected graph for disjoint detection.

        Args:
            graph: Directed graph dictionary

        Returns:
            Undirected graph dictionary
        """
        undirected: dict[str, set[str]] = {n: set() for n in graph}
        for src, outs in graph.items():
            for dst in outs:
                undirected[src].add(dst)
                undirected[dst].add(src)
        return undirected

    def _find_connected_components(self, undirected: dict) -> list:
        """Find connected components in an undirected graph.

        Args:
            undirected: Undirected graph dictionary

        Returns:
            List of sets, each containing node IDs in a connected component
        """
        visited = set()
        components = []

        for node in undirected:
            if node not in visited:
                stack = [node]
                comp = set()
                while stack:
                    x = stack.pop()
                    if x not in visited:
                        visited.add(x)
                        comp.add(x)
                        stack.extend(undirected[x])
                components.append(comp)
        return components

    def check_duplicate_extract_operators(self, *, sequence, global_config, errors):
        """Check for duplicate extract operators in the sequence.

        Args:
            sequence: List of operator definitions
            global_config: Global configuration dictionary
            errors: List to collect error alerts

        Returns:
            Count of extract operators found
        """
        # Get the count of extract operators in the flow.
        extract_operator_count = 0

        for _, op_def in enumerate(sequence):
            category = self.get_operator_category(op_def=op_def, global_config=global_config, alerts=errors)
            if category == OperatorCategory.Extract:
                extract_operator_count += 1

                if extract_operator_count > 1:
                    add_validation_alert(
                        ValidationMessage(
                            message="Multiple extract operators detected. Ensure they are used correctly",
                            message_code=ValidationCodeMessages.MULTIPLE_EXTRACTED_DETECTED.name,
                        ),
                        op_def=op_def,
                        alerts=errors,
                    )

        return extract_operator_count

    def validate_last_operator(self, *, dag: list, global_config: dict, validate_results: ValidateStepResults):
        """Validate that the last operator in the DAG is a VectorDB operator."""
        if not dag:
            return

        last_op = dag[-1]
        category = self.get_operator_category(
            op_def=last_op, global_config=global_config, alerts=validate_results.errors
        )

        if category != OperatorCategory.VectorDB:
            add_validation_alert(
                message=ValidationMessage(
                    message=ValidationCodeMessages.GENERATE_OUTPUT_MISSING.value,
                    message_code=ValidationCodeMessages.GENERATE_OUTPUT_MISSING.name,
                ),
                op_def=last_op,
                alerts=validate_results.warnings,
            )

    def validate_operator_category(
        self,
        *,
        op_def: dict,
        global_config: dict,
        expected_category: str,
        error_message: ValidationMessage,
        alerts: list,
    ):
        """Validate that an operator belongs to the expected category.

        Args:
            op_def: Operator definition dictionary
            global_config: Global configuration dictionary
            expected_category: Expected operator category
            error_message: Error message to add if validation fails
            alerts: List to collect alerts
        """
        category = self.get_operator_category(op_def=op_def, global_config=global_config, alerts=alerts)
        if category != expected_category:
            add_validation_alert(message=error_message, op_def=op_def, alerts=alerts)

    def get_operator_category(self, *, op_def: dict, global_config: dict, alerts: list):
        """Get the category of an operator.

        Args:
            op_def: Operator definition dictionary
            global_config: Global configuration dictionary
            alerts: List to collect alerts

        Returns:
            Operator category

        Raises:
            FlowValidationException: If operator cannot be created
        """
        if OperatorConstants.Columns.ID not in op_def:
            add_validation_alert(
                ValidationMessage(
                    message=ValidationCodeMessages.MISSING_NODE_ID.value,
                    message_code=ValidationCodeMessages.MISSING_NODE_ID.name,
                ),
                op_def=op_def,
                alerts=alerts,
            )
        if OperatorConstants.Columns.NAME not in op_def:
            add_validation_alert(
                message=ValidationMessage(
                    message=ValidationCodeMessages.MISSING_NODE_NAME.value,
                    message_code=ValidationCodeMessages.MISSING_NODE_NAME.name,
                ),
                op_def=op_def,
                alerts=alerts,
            )
        operator = None
        try:
            operator = self.orchestrator.create_executor(op_def=op_def, global_config=global_config).get_operator()
        except DatasiftException:
            errors: list[Any] = []
            add_validation_alert(
                ValidationMessage(
                    message=ValidationCodeMessages.GET_OPERATOR_FAILED.value,
                    message_code=ValidationCodeMessages.GET_OPERATOR_FAILED.name,
                ),
                op_def=op_def,
                alerts=errors,
            )
        if operator is None:
            errors = []
            add_validation_alert(
                ValidationMessage(
                    message=ValidationCodeMessages.GET_OPERATOR_FAILED.value,
                    message_code=ValidationCodeMessages.GET_OPERATOR_FAILED.name,
                ),
                op_def=op_def,
                alerts=errors,
            )
            raise FlowValidationException(errors=errors)
        return operator.category

    def create_validation_alerts(self, op_def: dict, messages: list, alerts: list, **kwargs):
        """Create validation alerts from a list of messages.

        Args:
            op_def: Operator definition dictionary
            messages: List of validation messages
            alerts: List to collect alerts
            **kwargs: Additional keyword arguments for alert creation
        """
        for message in messages:
            add_validation_alert(message=message, op_def=op_def, alerts=alerts, **kwargs)

    def _validate_node(
        self,
        *,
        op_def,
        global_config,
        validate_results: ValidateStepResults,
        session_info,
    ):
        """Validate a single node in the DAG.

        Args:
            op_def: Operator definition dictionary
            global_config: Global configuration dictionary
            validate_results: Container for validation results
            session_info: Session information

        Returns:
            Updated validate_results
        """
        node_id = op_def["id"]
        node_name = op_def.get("name", "")
        operator = op_def.get("operator", "")

        operator_factory: OperatorFactory = OperatorFactoryProvider.get_operator_factory(
            orchestrator=OrchestratorType.PYTHON
        )
        if self._evaluate_node_validation_skip(
            operator=operator,
            operator_factory=operator_factory,
            global_config=global_config,
        ):
            self.logger.info(
                f"Skipping validating node: {node_name} ({operator})",
                extra=self.common_log_arguments,
            )
            return validate_results

        set_session_info(session_info)
        self.logger.info(f"Validating node: {node_name} ({operator})", extra=self.common_log_arguments)

        input_refs = op_def.get(DatasiftConstants.INPUT_EDGES, [])  # list of dicts with node_id_ref
        prev_node_ids = [ref.get("node_id_ref") for ref in input_refs if "node_id_ref" in ref]
        output_refs = op_def.get(DatasiftConstants.OUTPUT_EDGES, [])

        available_features = set()
        for parent_id in prev_node_ids:
            available_features.update(validate_results.available_features.get(parent_id, []))

        executor = self.orchestrator.create_executor(op_def=op_def, global_config=global_config)
        new_features = set(
            op_def.get(OperatorConstants.Config.CONFIG, {}).get(OperatorConstants.Config.INPUT_FEATURES, {}).keys()
        )

        all_features = list(available_features.union(new_features))
        validate_results.available_features[node_id] = all_features

        error_messages: list[ValidationMessage] = []
        warning_messages: list[ValidationMessage] = []

        if not output_refs:
            # If the operator does not have any output refs and it is not VectorDB operator, then add a warning
            category = self.get_operator_category(
                op_def=op_def,
                global_config=global_config,
                alerts=validate_results.errors,
            )
            if category != OperatorCategory.VectorDB:
                warning_msg = ValidationMessage(
                    message=ValidationCodeMessages.GENERATE_OUTPUT_MISSING.value,
                    message_code=ValidationCodeMessages.GENERATE_OUTPUT_MISSING.name,
                )
                warning_messages.append(warning_msg)

        executor.validate(
            errors=error_messages,
            warnings=warning_messages,
            available_features=all_features,
        )

        self.create_validation_alerts(op_def=op_def, messages=error_messages, alerts=validate_results.errors)
        self.create_validation_alerts(op_def=op_def, messages=warning_messages, alerts=validate_results.warnings)

        self.logger.info(f"Completed validation: {node_name}", extra=self.common_log_arguments)
        logger.info(f"Validating node: {node_name} ({operator})", extra=self.common_log_arguments)
        return validate_results

    def get_duplicate_node_names(self, *, nodes):
        """Get duplicate names of nodes from pipeline.

        Args:
            nodes: List of node names

        Returns:
            List of duplicate node names
        """
        duplicates = [item for item in set(nodes) if nodes.count(item) > 1]
        return duplicates

    def _evaluate_node_validation_skip(
        self, operator: str, operator_factory: OperatorFactory, global_config: dict
    ) -> bool:
        """Evaluate whether to skip validation for a custom operator.

        Args:
            operator: Operator name
            operator_factory: Operator factory instance
            global_config: Global configuration dictionary

        Returns:
            True if validation should be skipped, False otherwise
        """
        if (
            DatasiftConstants.SKIP_CUSTOM_OP_VALIDATION in global_config
            and global_config[DatasiftConstants.SKIP_CUSTOM_OP_VALIDATION]
            and operator not in operator_factory.operators
        ):
            return True
        return False
