"""Flow validation module for docpipe orchestrator.

This module contains the FlowValidator class which handles all flow validation logic
that was previously embedded in AbstractOrchestrator.
"""

from typing import Any

from docpipe.core.constants.constants import DocpipeConstants, OrchestratorType
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.models.session_info import get_session_info, set_session_info
from docpipe.core.operators.abstract_operator import OperatorCategory
from docpipe.core.operators.operator_metadata import OperatorMetadata
from docpipe.core.orchestration.abstract_orchestrator import AbstractOrchestrator
from docpipe.core.orchestration.feature_propagation import (
    FeaturePropagationResult,
    FeaturePropagator,
)
from docpipe.core.orchestration.operator_factory import OperatorFactory, OperatorFactoryProvider
from docpipe.exceptions.docpipe_exceptions import (
    ErrorCode,
    FlowValidationException,
    ValidationAlert,
)
from docpipe.exceptions.error_messages import ValidationCodeMessages, ValidationMessage
from docpipe.utils.infrastructure.logging import get_logger
from docpipe.utils.orchestration.flow_utils import add_validation_alert
from docpipe.utils.orchestration.prefect_config import clean_up_prefect_home

logger = get_logger()


class ValidateStepResults:
    """Container for validation results including features, errors, and warnings.

    Separates validation concerns (errors/warnings) from feature propagation state,
    allowing validators to accumulate results during DAG traversal without mixing
    feature tracking with error reporting.

    This class acts as a mutable accumulator that is passed through the validation
    pipeline, collecting errors and warnings from various validation checks while
    also tracking which features are available at each node.

    Attributes:
        available_features: Dict mapping node IDs to lists of available feature names
            at that node. Used for debugging and feature availability checks.
        errors: List of validation errors (ValidationAlert objects or dicts).
            Non-empty list indicates validation failure.
        warnings: List of validation warnings (ValidationAlert objects or dicts).
            Warnings don't fail validation but indicate potential issues.

    Example:
        ```python
        results = ValidateStepResults(
            available_features={},
            errors=[],
            warnings=[]
        )

        # Validators add errors/warnings during traversal
        results.errors.append(ValidationAlert(
            code="OPERATOR_NOT_FOUND",
            message="Operator not found"
        ))

        # Feature tracking
        results.available_features["node-1"] = ["id", "content", "metadata"]
        ```

    Note:
        This is a simple data container without methods. Validators directly
        mutate the lists and dict to accumulate results.
    """

    def __init__(self, *, available_features: dict, errors: list, warnings: list):
        """Initialize validation results container.

        Args:
            available_features: Empty dict to be populated with node_id -> feature list mappings
            errors: Empty list to be populated with validation errors
            warnings: Empty list to be populated with validation warnings
        """
        self.available_features = available_features
        self.errors = errors
        self.warnings = warnings


class FlowValidator:
    """Handles all flow validation logic for the docpipe orchestrator.

    This class encapsulates comprehensive validation logic for DAG-based data
    processing flows, ensuring structural integrity, operator correctness, and
    feature availability throughout the pipeline.

    Validation Responsibilities:
        - DAG Structure: Validates graph connectivity, detects cycles, checks for disjoint nodes
        - Operator Placement: Ensures Ingest operators are first, VectorDB operators are last
        - Operator Availability: Verifies all operators are registered and available
        - Operator Configuration: Validates operator-specific parameters and requirements
        - Feature Propagation: Tracks features through the pipeline and validates availability
        - Node Naming: Checks for unique node names and proper identification

    Architecture:
        FlowValidator works in conjunction with:
        - FeaturePropagator: Handles feature tracking through the DAG
        - OperatorMetadata: Provides operator capability information
        - FlowEngine: Executes validation traversal (Prefect-based)

    Validation Modes:
        1. validate(): Basic structural validation without feature tracking
        2. validate_dag(): Full validation with error accumulation
        3. validate_dag_with_features(): Validation + feature propagation results
        4. debug_feature_propagation(): Detailed per-node feature snapshots

    Thread Safety:
        FlowValidator instances are NOT thread-safe. Each validation request
        should use its own validator instance (created with its own orchestrator).

    Example:
        ```python
        from docpipe.core.orchestration.orchestrator_factory import OrchestratorFactory
        from docpipe.core.orchestration.flow_validator import FlowValidator

        # Create orchestrator and validator
        orchestrator = OrchestratorFactory.create_orchestrator("python")
        orchestrator.initialize(job_id="val-job", job_run_id="val-run")
        validator = FlowValidator(orchestrator=orchestrator)

        # Validate flow (internal runtime DAG format)
        # Note: Authoring format is converted to this format before validation
        flow_def = {
            "dag": [
                {
                    "id": "ingest-1",
                    "name": "Ingest",
                    "operator": "ingest_local",
                    "config": {"folder_path": "/data"},
                    "output_edges": [{"node_id_ref": "extract-1"}]
                },
                {
                    "id": "extract-1",
                    "name": "Extract",
                    "operator": "extract_operator",
                    "config": {},
                    "input_edges": [{"node_id_ref": "ingest-1"}],
                    "output_edges": []
                }
            ]
        }

        try:
            validator.validate_dag(flow_def=flow_def, global_config={})
            print("Validation passed!")
        except FlowValidationException as e:
            print(f"Validation failed: {e.errors}")
        ```

    See Also:
        - FeaturePropagator: Feature tracking engine
        - ValidationService: API-level validation facade
        - AbstractOrchestrator: Orchestrator interface
    """

    def __init__(self, *, orchestrator: AbstractOrchestrator):
        """Initialize the FlowValidator.

        Creates a validator instance tied to a specific orchestrator. The validator
        loads operator metadata once during initialization for efficient validation.

        Args:
            orchestrator: Reference to the AbstractOrchestrator instance that will
                execute the validation traversal. Must have flow_engine initialized.

        Note:
            Operator metadata loading may fail for operators requiring external services
            (e.g., Ollama, OpenSearch). This is acceptable as validation only needs
            structural information, not runtime capabilities.
        """
        self.orchestrator = orchestrator
        self.logger = get_logger()
        self.common_log_arguments = orchestrator.common_log_arguments
        self.operator_metadata = OperatorMetadata(orchestrator=orchestrator)
        # Load operator metadata once during initialization
        # Operators that require external services may fail to load metadata
        # This is acceptable for validation as we only need structural information
        try:
            self.operator_metadata.get_operator_metadata(internal_features=True)
        except Exception as e:
            self.logger.warning(
                f"Some operators failed to load metadata (this is normal if external services are unavailable): {e!s}"
            )
            # Continue with whatever metadata was successfully loaded
        # Initialize feature propagator
        self.feature_propagator = FeaturePropagator()

    def validate(self, *, flow_def: dict, params: dict):
        """Main validation entry point for a flow definition.

        Performs basic structural validation without feature propagation.
        This is the simplest validation mode, suitable for quick checks.

        Args:
            flow_def: The flow definition dictionary containing:
                - dag: List of operator node definitions
                - global_config: Optional global configuration
            params: Additional parameters to merge with global config.
                Typically used to override or extend global_config.

        Raises:
            FlowValidationException: If validation fails with errors.
                Contains errors and warnings lists.

        Note:
            Validation can be disabled by setting disable_validation=True
            in global_config or params.
        """
        global_config = flow_def.get(OperatorConstants.Config.GLOBAL_CONFIG, {}) | params

        # Skip validation if explicitly disabled
        if global_config.get(OperatorConstants.Config.DISABLE_VALIDATION, False):
            return

        if DocpipeConstants.DAG not in flow_def:
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

        Performs comprehensive validation including structure checks, operator
        validation, and feature propagation. This is the standard validation
        method used by most validation workflows.

        Validation Steps:
            1. Check DAG exists and is non-empty
            2. Check for unnamed operators (warning)
            3. Check for duplicate operator names (error)
            4. Validate first operator is Ingest category
            5. Validate no disjoint (disconnected) operators
            6. Validate no cycles in the DAG
            7. Validate all operators are available/registered
            8. Traverse DAG and validate each node
            9. Validate last operator is VectorDB (warning if not)

        Args:
            flow_def: The flow definition dictionary containing:
                - dag: List of operator node definitions (required)
                - global_config: Optional global configuration
            global_config: Global configuration dictionary merged with flow_def config.
                Used for operator configuration and validation settings.

        Raises:
            FlowValidationException: If validation fails with errors or warnings.
                The exception contains:
                - errors: List of validation errors (non-empty means failure)
                - warnings: List of validation warnings (don't fail validation)

        Note:
            This method uses the flow_engine to traverse the DAG in topological
            order, validating each node and propagating features. The traversal
            is non-executing (no actual data processing).
        """
        logger.info("Validating DAG", extra=self.common_log_arguments)
        errors: list[Any] = []
        warnings: list[Any] = []

        dag = flow_def.get(DocpipeConstants.DAG, [])
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
        self.validate_acl_operator_placement(dag=dag, validate_results=validate_results)
        self.validate_disjoint_operators(dag=dag, global_config=global_config, validate_results=validate_results)
        self.validate_no_cycles(dag=dag, validate_results=validate_results)
        self.validate_operator_availability(dag=dag, global_config=global_config, validate_results=validate_results)

        def node_validation_task(task_name, op_def, result=None, link_name=None):
            return self._validate_node(
                op_def=op_def,
                prev_result=result,
                global_config=global_config,
                validate_results=validate_results,
                session_info=session_info,
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

        if validate_results.warnings:
            self.logger.warning(f"Validation warnings: {validate_results.warnings}")
        if validate_results.errors:
            self.logger.error(f"Validation errors: {validate_results.errors}")

        # Raise exception if there are errors OR warnings (warnings need to be returned to API)
        if validate_results.errors or validate_results.warnings:
            raise FlowValidationException(errors=validate_results.errors, warnings=validate_results.warnings)

    def validate_dag_with_features(self, *, flow_def: dict, global_config: dict) -> FeaturePropagationResult:
        """Validate DAG and propagate features through all nodes.

        This method enhances the standard validate_dag() by adding feature propagation
        and returning detailed feature information for each node. It's the most
        comprehensive validation mode, used by the validation API.

        Process:
            1. Run standard validate_dag() - raises if validation fails
            2. Perform separate feature propagation traversal
            3. Collect feature metadata for all nodes
            4. Return FeaturePropagationResult with complete feature information

        The feature propagation traversal tracks:
            - Input features available to each node
            - Output features produced by each node
            - Feature metadata (description, tags, availability flags)
            - Global parameters (e.g., embeddings_model_id)
            - Features dropped by operators (e.g., SQLFilter)

        Args:
            flow_def: The flow definition dictionary containing:
                - dag: List of operator node definitions (required)
                - global_config: Optional global configuration
            global_config: Global configuration dictionary for operators

        Returns:
            FeaturePropagationResult containing:
                - available_features: Dict[node_id, List[feature_names]]
                - opensearch_features: Dict[node_id, List[vector_db_features]]
                - feature_metadata: Dict[feature_name, FeatureMetadata]
                - global_params: Dict[param_name, param_value]
                - output_features_to_drop: Dict[node_id, OutputFeaturesToDrop]

        Raises:
            FlowValidationException: If validation fails (from validate_dag call).
                Feature propagation only runs if validation succeeds.

        Example:
            ```python
            result = validator.validate_dag_with_features(
                flow_def=flow_def,
                global_config={}
            )

            # Check features available at specific node
            node_features = result.available_features.get("node-123", [])
            print(f"Features at node: {node_features}")

            # Check feature metadata
            for feature_name, metadata in result.feature_metadata.items():
                print(f"{feature_name}: {metadata.description}")
            ```

        Note:
            This method performs two DAG traversals: one for validation and one
            for feature propagation. For large DAGs, this may take longer than
            validate_dag() alone.

        See Also:
            - validate_dag: Standard validation without feature propagation
            - debug_feature_propagation: Detailed per-node feature snapshots
            - FeaturePropagator.propagate_features: Core feature tracking logic
        """
        # First, run standard validation (this will raise if validation fails)
        self.validate_dag(flow_def=flow_def, global_config=global_config)

        # If validation passed, perform feature propagation
        logger.info("Performing feature propagation", extra=self.common_log_arguments)

        dag = flow_def.get(DocpipeConstants.DAG, [])
        propagation_result = FeaturePropagationResult()

        def feature_propagation_task(task_name, op_def, prev_result=None, link_name=None):
            """Task function for feature propagation traversal."""
            node_result = self._build_node_feature_result(
                op_def=op_def,
                prev_result=prev_result,
                global_config=global_config,
            )
            self._merge_node_result_into_propagation_result(
                op_def=op_def,
                node_result=node_result,
                propagation_result=propagation_result,
            )
            return node_result

        # Execute feature propagation traversal
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
            flow_name="feature_propagation_flow", task=feature_propagation_task, dag=dag
        )
        clean_up_prefect_home()

        logger.info(
            f"Feature propagation complete: {len(propagation_result.available_features)} nodes processed",
            extra=self.common_log_arguments,
        )

        return propagation_result

    def _validate_node(  # NOSONAR python:S3516
        self,
        *,
        op_def: dict[str, Any],
        prev_result: Any,
        global_config: dict[str, Any],
        validate_results: ValidateStepResults,
        session_info: Any,
    ) -> FeaturePropagationResult:
        """Validate a single DAG node and return its propagation result."""
        if session_info is not None:
            set_session_info(session_info=session_info)

        node_result = self._build_node_feature_result(
            op_def=op_def,
            prev_result=prev_result,
            global_config=global_config,
        )
        node_id, operator_name, _ = self._get_required_node_fields(op_def=op_def)

        input_features = list(node_result.get_input_features(node_id=node_id).keys())
        output_features = list(node_result.feature_metadata.keys())
        validate_results.available_features[node_id] = output_features

        operator_factory: OperatorFactory = OperatorFactoryProvider.get_operator_factory(
            orchestrator=OrchestratorType.PYTHON,
            package_names=self.orchestrator.custom_operator_packages,
            enable_custom_operators=self.orchestrator.enable_custom_operators,
        )

        if self._evaluate_node_validation_skip(
            operator=operator_name,
            operator_factory=operator_factory,
            global_config=global_config,
        ):
            return node_result

        try:
            operator_class = operator_factory.operators.get(operator_name)

            if operator_class is None:
                add_validation_alert(
                    message=ValidationMessage(
                        message=f"Operator '{operator_name}' is not available. Please check operator name and registration.",
                        message_code="OPERATOR_NOT_AVAILABLE",
                    ),
                    op_def=op_def,
                    alerts=validate_results.errors,
                )
                return node_result

            config = global_config | op_def.get(OperatorConstants.Config.CONFIG, {})
            operator = operator_class(config=config)
            operator.name = op_def.get(OperatorConstants.Columns.NAME)
            operator.id = op_def.get(OperatorConstants.Columns.ID)

            errors: list[Any] = []
            warnings: list[Any] = []
            operator.validate(errors=errors, warnings=warnings, available_features=input_features)

            self.create_validation_alerts(op_def=op_def, messages=errors, alerts=validate_results.errors)
            self.create_validation_alerts(op_def=op_def, messages=warnings, alerts=validate_results.warnings)
        except FlowValidationException as exc:
            if exc.errors:
                validate_results.errors.extend(exc.errors)
            if exc.warnings:
                validate_results.warnings.extend(exc.warnings)
        except Exception as exc:
            add_validation_alert(
                message=ValidationMessage(
                    message=f"Validation failed for operator '{operator_name}': {exc!s}",
                    message_code="OPERATOR_VALIDATION_FAILED",
                ),
                op_def=op_def,
                alerts=validate_results.errors,
            )

        return node_result

    def _get_parent_results(self, *, prev_result: Any) -> list[FeaturePropagationResult]:
        """Normalize Prefect traversal input into a list of parent propagation results."""
        if isinstance(prev_result, FeaturePropagationResult):
            return [prev_result]
        if isinstance(prev_result, list):
            return [parent for parent in prev_result if isinstance(parent, FeaturePropagationResult)]
        if isinstance(prev_result, dict):
            return [parent for parent in prev_result.values() if isinstance(parent, FeaturePropagationResult)]
        return []

    def _feature_metadata_to_dict(self, *, result: FeaturePropagationResult) -> dict[str, dict[str, Any]]:
        """Convert node feature metadata into plain dictionaries for downstream propagation/debugging."""
        return {
            name: {
                "description": meta.description,
                "tags": meta.tags,
                "available_for_filter": meta.available_for_filter,
                "available_for_vector_db": meta.available_for_vector_db,
                "type": meta.type,
                **({"source_node_id": meta.node_id} if meta.node_id else {}),
            }
            for name, meta in result.feature_metadata.items()
        }

    def _get_required_node_fields(self, *, op_def: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
        """Extract required propagation fields from a DAG node definition."""
        node_id = op_def.get(OperatorConstants.Misc.ID)
        operator = op_def.get(OperatorConstants.Misc.OPERATOR)
        operator_config = op_def.get(OperatorConstants.Config.CONFIG, {})

        if not isinstance(node_id, str) or not node_id:
            raise FlowValidationException(
                errors=[
                    ValidationAlert(
                        ErrorCode.FLOW_VALIDATION_FAILED.value,
                        message="Flow node is missing a valid id",
                        message_code="INVALID_FLOW_NODE_ID",
                    )
                ]
            )

        if not isinstance(operator, str) or not operator:
            raise FlowValidationException(
                errors=[
                    ValidationAlert(
                        ErrorCode.FLOW_VALIDATION_FAILED.value,
                        message=f"Flow node '{node_id}' is missing a valid operator",
                        message_code="INVALID_FLOW_NODE_OPERATOR",
                    )
                ]
            )

        if not isinstance(operator_config, dict):
            operator_config = {}

        return node_id, operator, operator_config

    def _build_node_feature_result(
        self,
        *,
        op_def: dict[str, Any],
        prev_result: Any,
        global_config: dict[str, Any],
    ) -> FeaturePropagationResult:
        """Build propagation state for a single node from its parents."""
        node_id, operator, operator_config = self._get_required_node_fields(op_def=op_def)

        parent_results = self._get_parent_results(prev_result=prev_result)
        input_features: dict[str, dict[str, Any]] = {}

        for parent_result in parent_results:
            input_features.update(self._feature_metadata_to_dict(result=parent_result))

        return self.feature_propagator.propagate_features(
            node_id=node_id,
            operator_short_name=operator,
            operator_config=operator_config,
            input_features=input_features,
            global_config=global_config,
            parent_results=parent_results,
        )

    def _merge_node_result_into_propagation_result(
        self,
        *,
        op_def: dict[str, Any],
        node_result: FeaturePropagationResult,
        propagation_result: FeaturePropagationResult,
    ) -> None:
        """Store per-node propagation output in the aggregate flow result."""
        node_id, _, _ = self._get_required_node_fields(op_def=op_def)
        feature_names = list(node_result.feature_metadata.keys())
        propagation_result.set_available_features(node_id=node_id, features=feature_names)

        opensearch_features = [
            name for name, meta in node_result.feature_metadata.items() if meta.available_for_vector_db
        ]
        if opensearch_features:
            propagation_result.set_opensearch_features(node_id=node_id, features=opensearch_features)

        for feature_name, feature_meta in node_result.feature_metadata.items():
            scoped_feature_name = f"{node_id}.{feature_name}"
            propagation_result.feature_metadata[scoped_feature_name] = feature_meta
            if feature_name not in propagation_result.feature_metadata:
                propagation_result.feature_metadata[feature_name] = feature_meta

        propagation_result.global_params.update(node_result.global_params)

        if node_id in node_result.output_features_to_drop:
            propagation_result.output_features_to_drop[node_id] = node_result.output_features_to_drop[node_id]

    def debug_feature_propagation(self, *, flow_def: dict, global_config: dict) -> dict[str, dict[str, Any]]:
        """Return per-node feature propagation snapshots without changing validation behavior."""
        normalized_flow_def = flow_def
        if "definition" in normalized_flow_def:
            normalized_flow_def = normalized_flow_def["definition"]
        if "flow" in normalized_flow_def:
            normalized_flow_def = normalized_flow_def["flow"]

        dag = normalized_flow_def.get(DocpipeConstants.DAG, [])
        debug_snapshots: dict[str, dict[str, Any]] = {}
        parent_node_map: dict[str, list[str]] = {}

        for node in dag:
            node_id = node.get(OperatorConstants.Misc.ID)
            parent_ids = [edge.get("node_id_ref") for edge in node.get("input_edges", []) if edge.get("node_id_ref")]
            parent_node_map[node_id] = parent_ids

        def feature_debug_task(task_name, op_def, prev_result=None, link_name=None):
            node_id = op_def.get(OperatorConstants.Misc.ID)
            operator = op_def.get(OperatorConstants.Misc.OPERATOR)

            node_result = self._build_node_feature_result(
                op_def=op_def,
                prev_result=prev_result,
                global_config=global_config,
            )

            debug_snapshots[node_id] = {
                "node_id": node_id,
                "node_name": op_def.get(OperatorConstants.Misc.NAME),
                "operator": operator,
                "parent_node_ids": parent_node_map.get(node_id, []),
                "input_features": node_result.get_input_features(node_id=node_id),
                "output_features": node_result.get_output_features(node_id=node_id),
                "available_features": self._feature_metadata_to_dict(result=node_result),
                "dropped_features": sorted(
                    node_result.get_output_features_to_drop(node_id=node_id).get_features_to_drop()
                ),
                "global_params": dict(node_result.global_params),
            }

            return node_result

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
            flow_name="feature_propagation_debug_flow", task=feature_debug_task, dag=dag
        )
        clean_up_prefect_home()
        return debug_snapshots

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

    def validate_disjoint_operators(self, *, dag: list, global_config: dict, validate_results: ValidateStepResults):
        """Validate that the DAG does not contain disconnected (disjoint) operators.

        Args:
            dag: List of operator definitions
            validate_results: Container for validation results
        """
        graph = self._build_graph(dag)
        undirected = self._make_undirected_graph(graph)
        components = self._find_connected_components(undirected)

        id_to_index = {n["id"]: i for i, n in enumerate(dag)}
        reported_nodes: set[str] = set()
        reverse_graph: dict[str, list[str]] = self._build_reverse_graph(dag)

        if len(components) > 1:
            self._validate_disconnected_components(
                components=components,
                graph=graph,
                dag=dag,
                id_to_index=id_to_index,
                global_config=global_config,
                validate_results=validate_results,
                reported_nodes=reported_nodes,
            )
        # check if any nodes are isolated
        self._validate_isolated_nodes(
            dag=dag,
            graph=graph,
            reverse_graph=reverse_graph,
            reported_nodes=reported_nodes,
            validate_results=validate_results,
        )

    def _build_reverse_graph(self, dag: list) -> dict:
        """Build reverse graph to find nodes without inputs."""
        reverse_graph: dict[str, list[str]] = {n["id"]: [] for n in dag}
        for node in dag:
            for edge in node.get("output_edges", []):
                target_node_id = edge.get("node_id_ref")
                if target_node_id and target_node_id in reverse_graph:
                    reverse_graph[target_node_id].append(node["id"])
        return reverse_graph

    def _validate_disconnected_components(
        self,
        *,
        components: list,
        graph: dict,
        dag: list,
        id_to_index: dict,
        global_config: dict,
        validate_results: ValidateStepResults,
        reported_nodes: set,
    ):
        """Validate disconnected components and report terminal nodes that are not VectorDB operators."""
        for component in components:
            terminal_node_id = self._find_terminal_node(component, graph)
            if terminal_node_id is None:
                continue

            self._report_non_vectordb_terminal(
                terminal_node_id=terminal_node_id,
                id_to_index=id_to_index,
                dag=dag,
                global_config=global_config,
                validate_results=validate_results,
                reported_nodes=reported_nodes,
            )

    def _find_terminal_node(self, component: set, graph: dict) -> str | None:
        """Find the terminal node (node with no outgoing edges) in a component."""
        for node_id in component:
            if not graph.get(node_id, []):
                return node_id
        return None

    def _report_non_vectordb_terminal(
        self,
        *,
        terminal_node_id: str,
        id_to_index: dict,
        dag: list,
        global_config: dict,
        validate_results: ValidateStepResults,
        reported_nodes: set,
    ):
        """Report terminal node if it's not a VectorDB operator."""
        index = id_to_index.get(terminal_node_id)
        if index is None:
            return

        terminal_node = dag[index]
        category = self.get_operator_category(
            op_def=terminal_node, global_config=global_config, alerts=validate_results.errors
        )

        if category != OperatorCategory.VectorDB:
            add_validation_alert(
                message=ValidationMessage(
                    message=ValidationCodeMessages.DISJOINT_OPERATORS_DETECTED.value,
                    message_code=ValidationCodeMessages.DISJOINT_OPERATORS_DETECTED.name,
                ),
                op_def=terminal_node,
                alerts=validate_results.errors,
            )
            reported_nodes.add(terminal_node_id)

    def _validate_isolated_nodes(
        self, *, dag: list, graph: dict, reverse_graph: dict, reported_nodes: set, validate_results: ValidateStepResults
    ):
        """Check for isolated nodes (nodes with no input AND no output)."""
        for node in dag:
            node_id = node.get("id")
            if not node_id or node_id in reported_nodes:
                continue

            has_output = bool(graph.get(node_id, []))
            has_input = bool(reverse_graph.get(node_id, []))

            if not has_output and not has_input:
                add_validation_alert(
                    message=ValidationMessage(
                        message=ValidationCodeMessages.DISJOINT_OPERATORS_DETECTED.value,
                        message_code=ValidationCodeMessages.DISJOINT_OPERATORS_DETECTED.name,
                    ),
                    op_def=node,
                    alerts=validate_results.errors,
                )

    def validate_acl_operator_placement(
        self, *, dag: list, validate_results: ValidateStepResults
    ):  # NOSONAR python:S3776
        """Validate ACL operator placement in the DAG.

        ACL operator must be placed immediately after an ingest operator (ingest_source or ingest_local).
        Only one ACL operator is allowed per flow.

        Args:
            dag: List of operator definitions
            global_config: Global configuration dictionary
        """
        # Early exit if no ACL operator present
        acl_nodes = [
            node
            for node in dag
            if node.get(OperatorConstants.Misc.OPERATOR) == OperatorConstants.Operators.ACL_OPERATOR
        ]
        if not acl_nodes:
            return

        # Check for multiple ACL operators
        if len(acl_nodes) > 1:
            for acl_node in acl_nodes:
                add_validation_alert(
                    message=ValidationMessage(
                        message=ValidationCodeMessages.MULTIPLE_ACL_OPERATORS.value,
                        message_code=ValidationCodeMessages.MULTIPLE_ACL_OPERATORS.name,
                    ),
                    op_def=acl_node,
                    alerts=validate_results.errors,
                )
            return

        acl_node = acl_nodes[0]
        acl_node_id = acl_node.get(OperatorConstants.Misc.ID)

        # Build reverse graph to find parent nodes
        parent_map: dict[str, list[str]] = {n[OperatorConstants.Misc.ID]: [] for n in dag}
        for node in dag:
            output_edges = node.get(DocpipeConstants.OUTPUT_EDGES, [])
            for edge in output_edges:
                target_id = edge.get("node_id_ref")
                if target_id and target_id in parent_map:
                    parent_map[target_id].append(node[OperatorConstants.Misc.ID])

        # Get parent nodes of ACL operator
        parent_ids = parent_map.get(acl_node_id, [])
        if not parent_ids:
            add_validation_alert(
                message=ValidationMessage(
                    message=ValidationCodeMessages.ACL_OPERATOR_NO_INPUT.value,
                    message_code=ValidationCodeMessages.ACL_OPERATOR_NO_INPUT.name,
                ),
                op_def=acl_node,
                alerts=validate_results.errors,
            )
            return

        # Find parent operator details
        parent_operators = [node for node in dag if node.get(OperatorConstants.Misc.ID) in parent_ids]

        # ACL operator should have only one parent
        if len(parent_operators) > 1:
            add_validation_alert(
                message=ValidationMessage(
                    message=ValidationCodeMessages.ACL_MULTIPLE_PARENTS.value.format(
                        parent_count=len(parent_operators)
                    ),
                    message_code=ValidationCodeMessages.ACL_MULTIPLE_PARENTS.name,
                ),
                op_def=acl_node,
                alerts=validate_results.errors,
            )
            return

        # Check if any parent is an ingest_source operator
        has_valid_parent = False
        predecessor_operator = None
        ingest_source_parent = None

        for parent in parent_operators:
            parent_op_name = parent.get(OperatorConstants.Misc.OPERATOR)
            if parent_op_name == OperatorConstants.Operators.INGEST_SOURCE:
                has_valid_parent = True
                ingest_source_parent = parent
                break
            predecessor_operator = parent_op_name

        if not has_valid_parent:
            add_validation_alert(
                message=ValidationMessage(
                    message=ValidationCodeMessages.ACL_OPERATOR_MISPLACED.value.format(
                        predecessor_operator=predecessor_operator or "unknown"
                    ),
                    message_code=ValidationCodeMessages.ACL_OPERATOR_MISPLACED.name,
                ),
                op_def=acl_node,
                alerts=validate_results.errors,
            )
        elif ingest_source_parent is not None:
            # Validate that ingest_source uses SharePoint provider
            provider = ingest_source_parent.get(OperatorConstants.Config.CONFIG, {}).get("provider", "").lower()
            if provider != "sharepoint":
                add_validation_alert(
                    message=ValidationMessage(
                        message=ValidationCodeMessages.ACL_INVALID_PROVIDER.value.format(provider=provider),
                        message_code=ValidationCodeMessages.ACL_INVALID_PROVIDER.name,
                    ),
                    op_def=acl_node,
                    alerts=validate_results.errors,
                )
        # Early exit if no ACL operator present

    def _build_graph(self, dag: list) -> dict:
        """Build a directed graph representation from the DAG.

        Args:
            dag: List of operator definitions

        Returns:
            Dictionary mapping node IDs to lists of connected node IDs
        """
        graph: dict[str, list[str]] = {n["id"]: [] for n in dag}
        for node in dag:
            output_edges = node.get(DocpipeConstants.OUTPUT_EDGES, [])
            for edge in output_edges:
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

    def validate_no_cycles(self, *, dag: list, validate_results: ValidateStepResults):  # NOSONAR python:S3776
        """Validate that the DAG does not contain cycles.

        Uses depth-first search with recursion stack to detect cycles.

        Args:
            dag: List of operator definitions
            validate_results: Container for validation results
        """
        graph = self._build_graph(dag)
        visited = set()
        rec_stack = set()

        def has_cycle(node_id: str) -> bool:
            """DFS helper to detect cycles."""
            visited.add(node_id)
            rec_stack.add(node_id)

            for neighbor in graph.get(node_id, []):
                if neighbor not in visited:
                    if has_cycle(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True

            rec_stack.remove(node_id)
            return False

        # Check each node for cycles
        for node in dag:
            node_id = node.get("id")
            if node_id and node_id not in visited:
                if has_cycle(node_id):
                    add_validation_alert(
                        message=ValidationMessage(
                            message="Cyclic dependency detected in DAG. Flows must be acyclic.",
                            message_code="CYCLIC_DEPENDENCY_DETECTED",
                        ),
                        op_def=node,
                        alerts=validate_results.errors,
                    )
                    break

    def validate_operator_availability(self, *, dag: list, global_config: dict, validate_results: ValidateStepResults):
        """Validate that all operators in the DAG are available in the operator factory.

        Performs early check before DAG traversal to fail fast with clear error.

        Args:
            dag: List of operator definitions
            global_config: Global configuration dictionary
            validate_results: Container for validation results
        """
        operator_factory: OperatorFactory = OperatorFactoryProvider.get_operator_factory(
            orchestrator=OrchestratorType.PYTHON,
            package_names=self.orchestrator.custom_operator_packages,
            enable_custom_operators=self.orchestrator.enable_custom_operators,
        )

        for node in dag:
            operator_name = node.get(OperatorConstants.Misc.OPERATOR)

            # Skip validation for custom operators if configured
            if self._evaluate_node_validation_skip(
                operator=operator_name, operator_factory=operator_factory, global_config=global_config
            ):
                continue

            # Check if operator exists in factory
            if operator_name and operator_name not in operator_factory.operators:
                add_validation_alert(
                    message=ValidationMessage(
                        message=f"Operator '{operator_name}' is not available. Please check operator name and registration.",
                        message_code="OPERATOR_NOT_AVAILABLE",
                    ),
                    op_def=node,
                    alerts=validate_results.errors,
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
        # Get operator name from definition
        operator_name = op_def.get(OperatorConstants.Misc.OPERATOR)
        if not operator_name:
            add_validation_alert(
                ValidationMessage(
                    message="Operator name is missing from node definition",
                    message_code="MISSING_OPERATOR_NAME",
                ),
                op_def=op_def,
                alerts=alerts,
            )
            return None

        # Look up category from cached metadata (avoids operator instantiation)
        metadata = self.operator_metadata.operator_metadata.get(operator_name, {})
        category = metadata.get(OperatorConstants.Misc.CATEGORY)

        if category is None:
            add_validation_alert(
                ValidationMessage(
                    message=f"Could not determine category for operator '{operator_name}'. Operator may not be registered or metadata is unavailable.",
                    message_code="OPERATOR_CATEGORY_UNKNOWN",
                ),
                op_def=op_def,
                alerts=alerts,
            )
            return None

        return category

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
            DocpipeConstants.SKIP_CUSTOM_OP_VALIDATION in global_config
            and global_config[DocpipeConstants.SKIP_CUSTOM_OP_VALIDATION]
            and operator not in operator_factory.operators
        ):
            return True
        return False
