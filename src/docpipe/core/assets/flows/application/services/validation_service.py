"""Validation service for flow definitions.

Provides validation operations for flow definitions including DAG structure,
operator configuration, and feature propagation validation.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ValidationService:
    """Service for validating flow definitions.

    Handles validation logic independently from flow CRUD operations.
    Does not require repository access as validation is stateless and
    thread-safe, making it suitable for concurrent validation requests.

    This service acts as a facade over the core validation infrastructure,
    providing a simplified interface for API endpoints while handling:
    - Format detection and conversion (Elyra vs Authoring)
    - Orchestrator initialization for validation
    - Error normalization and response formatting
    - Exception handling and graceful degradation

    Architecture:
        ValidationService (API Layer)
            ↓
        FlowValidator (Core Validation)
            ↓
        FeaturePropagator (Feature Tracking)

    Thread Safety:
        This service is stateless and thread-safe. Each validation request
        creates its own orchestrator instance, ensuring no shared state
        between concurrent requests.

    Example:
        ```python
        service = ValidationService()
        result = service.validate_flow(
            flow_definition={
                "flow_name": "My Pipeline",
                "flow": [
                    {
                        "type": "ingest_local",
                        "name": "Ingest",
                        "config": {"folder_path": "/data"},
                        "depends_on": []
                    }
                ]
            },
            is_elyra=False
        )
        if result["status"] == "SUCCEEDED":
            print("Flow is valid")
        else:
            print(f"Errors: {result['errors']}")
        ```

    See Also:
        - FlowValidator: Core DAG validation logic
        - FeaturePropagator: Feature propagation engine
        - validation_router: REST API endpoint using this service
    """

    def __init__(self):
        """Initialize validation service.

        Creates a stateless validation service instance. No configuration
        or dependencies are required as all validation state is created
        per-request.
        """
        pass

    def _normalize_validation_alert(self, *, alert: Any, default_code: str) -> dict[str, Any]:
        """Normalize ValidationAlert or ValidationMessage to standardized dict format.

        Converts various alert types (ValidationAlert dict subclass, ValidationMessage
        Pydantic model, or plain objects) into a consistent dictionary format suitable
        for API responses. This ensures clients receive predictable error/warning structures.

        The normalization process:
        1. ValidationAlert (dict subclass) → Convert to plain dict
        2. ValidationMessage (Pydantic model) → model_dump() with code injection
        3. Other types → Fallback to string representation

        Args:
            alert: Alert object to normalize. Can be:
                - ValidationAlert: Dict subclass with code, message, node_id, etc.
                - ValidationMessage: Pydantic model with message and optional message_code
                - Any other type: Converted to string
            default_code: Default error/warning code to use if alert doesn't provide one.
                Typically "VALIDATION_ERROR" or "VALIDATION_WARNING".

        Returns:
            Standardized dict containing at minimum:
                - code: str - Error/warning code for programmatic handling
                - message: str - Human-readable error/warning message
            May also include optional fields:
                - message_code: str - Structured message code
                - node_id: str - ID of the node that failed validation
                - node_name: str - Name of the node
                - operator: str - Operator type

        Example:
            ```python
            alert = ValidationAlert(
                code="OPERATOR_NOT_FOUND",
                message="Operator not found",
                node_id="node-123"
            )
            normalized = self._normalize_validation_alert(
                alert=alert,
                default_code="VALIDATION_ERROR"
            )
            # Returns: {
            #     "code": "OPERATOR_NOT_FOUND",
            #     "message": "Operator not found",
            #     "node_id": "node-123"
            # }
            ```

        Note:
            This method is defensive and never raises exceptions. Unknown types
            are converted to string representations with the default code.
        """
        from docpipe.exceptions.docpipe_exceptions import ValidationAlert
        from docpipe.exceptions.error_messages import ValidationMessage

        # ValidationAlert is a dict subclass - convert to plain dict
        if isinstance(alert, ValidationAlert):
            return dict(alert)

        # ValidationMessage is a Pydantic model - convert to dict
        if isinstance(alert, ValidationMessage):
            alert_dict = alert.model_dump(exclude_none=True)
            # Ensure 'code' field exists
            if "code" not in alert_dict:
                alert_dict["code"] = default_code
            return alert_dict

        # Fallback for unexpected types
        return {"code": default_code, "message": str(alert)}

    def validate_flow(
        self, *, flow_definition: dict[str, Any] | None, is_elyra: bool = False
    ) -> dict[str, Any]:  # NOSONAR python:S3776
        """Validate a flow definition and return comprehensive validation results.

        This is the main entry point for flow validation. It orchestrates the entire
        validation process from format detection through feature propagation, returning
        a structured result that never raises exceptions.

        Validation Pipeline:
            1. Input Validation: Check for missing/empty flow definition
            2. Format Detection: Determine Elyra vs Authoring format
            3. Format Conversion: Convert to internal runtime DAG format
            4. Wrapper Extraction: Unwrap nested flow structures if present
            5. Orchestrator Setup: Initialize validation orchestrator
            6. DAG Validation: Validate structure, operators, and features
            7. Result Normalization: Convert alerts to standardized format
            8. Status Determination: Compute final validation status

        Validation Checks Performed:
            - DAG structure validation (no cycles, connected graph)
            - Operator placement rules (Ingest first, VectorDB last)
            - Operator availability and registration
            - Operator configuration and parameters
            - Feature propagation through pipeline
            - Required feature availability at each node
            - Mandatory feature preservation (id, content, etc.)

        Args:
            flow_definition: Flow definition dictionary or None. Format depends on is_elyra:
                - Authoring format: {"nodes": [...], "edges": [...]}
                - Elyra format: {"doc_type": "pipeline", "pipelines": [...]}
                - None: Returns FAILED status with MISSING_DEFINITION error
            is_elyra: Whether definition is in Elyra format requiring conversion.
                Default is False (authoring format).

        Returns:
            Dictionary with validation results, always containing these keys:
                - status: str - One of:
                    * "SUCCEEDED": No errors or warnings
                    * "FAILED": One or more validation errors
                    * "SUCCEEDED_WITH_WARNINGS": No errors but has warnings
                - message: str | None - Human-readable summary or None
                - errors: list[dict] - Validation errors, each containing:
                    * code: str - Error code for programmatic handling
                    * message: str - Human-readable error message
                    * node_id: str (optional) - ID of problematic node
                    * node_name: str (optional) - Name of problematic node
                    * operator: str (optional) - Operator type
                - warnings: list[dict] - Validation warnings (same structure as errors)

        Error Handling:
            This method implements defensive error handling and never raises exceptions:
            - Missing/empty flow_definition → FAILED with MISSING_DEFINITION
            - Format conversion errors → FAILED with conversion error details
            - Validation errors → FAILED with detailed error list
            - Unexpected exceptions → FAILED with VALIDATION_EXCEPTION

        Example Usage:
            ```python
            service = ValidationService()

            # Validate authoring format
            result = service.validate_flow(
                flow_definition={
                    "nodes": [
                        {
                            "id": "ingest-1",
                            "operator_type": "IngestLocalOperator",
                            "operator_params": {"folder_path": "/data"}
                        }
                    ],
                    "edges": []
                },
                is_elyra=False
            )

            if result["status"] == "SUCCEEDED":
                print("Flow is valid!")
            elif result["status"] == "FAILED":
                for error in result["errors"]:
                    print(f"Error: {error['message']}")
            ```

        Example Response (Success):
            ```python
            {
                "status": "SUCCEEDED",
                "message": None,
                "errors": [],
                "warnings": []
            }
            ```

        Example Response (Failure):
            ```python
            {
                "status": "FAILED",
                "message": "Flow validation failed.",
                "errors": [
                    {
                        "code": "OPERATOR_NOT_FOUND",
                        "message": "Operator not found: InvalidOperator",
                        "node_id": "node-123",
                        "node_name": "My Node"
                    }
                ],
                "warnings": []
            }
            ```

        Example Response (Warnings):
            ```python
            {
                "status": "SUCCEEDED_WITH_WARNINGS",
                "message": "Flow validation succeeded with warnings.",
                "errors": [],
                "warnings": [
                    {
                        "code": "GENERATE_OUTPUT_MISSING",
                        "message": "Last operator should be VectorDB",
                        "node_id": "node-456"
                    }
                ]
            }
            ```

        Performance Considerations:
            - Each validation creates a new orchestrator instance (stateless)
            - Feature propagation traverses the entire DAG
            - Operator metadata is loaded once per validator instance
            - Typical validation time: 100-500ms for small flows

        Thread Safety:
            This method is thread-safe as it creates isolated state per invocation.
            Multiple concurrent validations do not interfere with each other.

        See Also:
            - FlowValidator.validate_dag_with_features: Core validation logic
            - FeaturePropagator.propagate_features: Feature tracking
            - AuthoringCompiler.compile: Authoring format compilation
            - ElyraConverter.transform_elyra_to_internal: Elyra conversion

        Note:
            The error handler middleware will catch any unexpected exceptions that
            escape this method and convert them to 500 errors, but this should never
            happen as all exceptions are caught internally.
        """
        from docpipe.core.assets.flows.application.services.authoring_compiler import AuthoringCompiler
        from docpipe.core.assets.flows.domain.models.authoring_flow import AuthoringFlow
        from docpipe.core.constants.constants import DocpipeConstants, OrchestratorType
        from docpipe.core.orchestration.flow_validator import FlowValidator
        from docpipe.core.orchestration.orchestrator_factory import OrchestratorFactory
        from docpipe.exceptions.docpipe_exceptions import ErrorCode, FlowValidationException, ValidationAlert
        from docpipe.exceptions.error_messages import ValidationCodeMessages
        from docpipe.utils.orchestration.elyra_converter import ElyraConverter

        logger.debug("Validating flow definition (is_elyra=%s)", is_elyra)

        # Handle missing flow definition
        if not flow_definition:
            logger.warning("Flow definition is missing or empty")
            return {
                "status": "FAILED",
                "message": "Flow definition is required for validation",
                "errors": [{"code": "MISSING_DEFINITION", "message": "Flow definition is required for validation"}],
                "warnings": [],
            }

        try:
            # Normalize input to internal runtime DAG format
            if is_elyra:
                logger.debug("Converting Elyra format to internal DAG")
                converter = ElyraConverter()
                flow_definition = converter.transform_elyra_to_internal(
                    elyra_json=flow_definition, flow_id="validation-flow"
                )
                logger.debug("Elyra conversion completed")
            else:
                logger.debug("Compiling authoring format to internal runtime DAG")
                authoring_flow = AuthoringFlow.from_dict(data=flow_definition)
                compiler = AuthoringCompiler()
                flow_definition = compiler.compile(authoring_flow=authoring_flow)
                logger.debug("Authoring compilation completed")

            # Extract flow structure from wrapper if present
            # Wrapped payload: {"flow": {"dag": [...], "global_config": {...}}}
            # Validator expects: {"dag": [...], "global_config": {...}}
            if isinstance(flow_definition, dict) and DocpipeConstants.FLOW in flow_definition:
                logger.debug("Extracting flow structure from 'flow' wrapper")
                inner_flow = flow_definition.get(DocpipeConstants.FLOW)
                if inner_flow is None or not isinstance(inner_flow, dict):
                    raise FlowValidationException(
                        errors=[
                            ValidationAlert(
                                code=ErrorCode.FLOW_VALIDATION_FAILED.value,
                                message=ValidationCodeMessages.INVALID_FLOW_WRAPPER.value,
                                message_code=ValidationCodeMessages.INVALID_FLOW_WRAPPER.name,
                            )
                        ]
                    )
                flow_definition = inner_flow

            # Create and initialize orchestrator for validation
            orchestrator = OrchestratorFactory.create_orchestrator(orchestrator_name=OrchestratorType.PYTHON)
            # Initialize orchestrator to set up flow_engine (required for validation)
            orchestrator.initialize(job_id="validation-job", job_run_id="validation-run")
            validator = FlowValidator(orchestrator=orchestrator)

            # Run validation with feature propagation
            try:
                propagation_result = validator.validate_dag_with_features(flow_def=flow_definition, global_config={})

                # If validation succeeds, return success response
                result: dict[str, Any] = {"status": "SUCCEEDED", "message": None, "errors": [], "warnings": []}

                logger.debug("Flow validation successful with %d nodes", len(propagation_result.available_features))
                return result

            except FlowValidationException as e:
                # Validation failed - extract errors and warnings
                logger.warning("Flow validation failed: %s", str(e))

                # Convert ValidationAlert/ValidationMessage objects to standardized dict format
                errors = []
                if hasattr(e, "errors") and e.errors:
                    for err in e.errors:
                        errors.append(self._normalize_validation_alert(alert=err, default_code="VALIDATION_ERROR"))

                warnings = []
                if hasattr(e, "warnings") and e.warnings:
                    for warn in e.warnings:
                        warnings.append(self._normalize_validation_alert(alert=warn, default_code="VALIDATION_WARNING"))

                # Determine status based on errors and warnings
                # If exception was raised, default to FAILED even if no explicit errors
                if len(errors) > 0:
                    status = "FAILED"
                    message = "Flow validation failed."
                elif len(warnings) > 0:
                    status = "SUCCEEDED_WITH_WARNINGS"
                    message = "Flow validation succeeded with warnings."
                else:
                    # Exception raised but no errors/warnings - still a failure
                    status = "FAILED"
                    message = "Flow validation failed."

                result = {"status": status, "message": message, "errors": errors, "warnings": warnings}

                return result

        except Exception as e:
            # Catch any unexpected exceptions and return as validation error
            logger.error("Unexpected error during flow validation: %s", str(e), exc_info=True)

            result = {
                "status": "FAILED",
                "message": "Validation failed with unexpected error.",
                "errors": [
                    {"code": "VALIDATION_EXCEPTION", "message": f"Validation failed with unexpected error: {e!s}"}
                ],
                "warnings": [],
            }

            return result
