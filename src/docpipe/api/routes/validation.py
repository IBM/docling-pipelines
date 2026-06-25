"""Validation API routes.

Provides REST API endpoints for flow validation operations.
"""

import logging
from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from docpipe.api.dto.authoring_flow_dto import AuthoringFlowCreateRequest
from docpipe.api.dto.error_dto import ErrorResponse
from docpipe.api.dto.flow_dto import ElyraFlowCreateRequest, FlowValidationResponse
from docpipe.core.assets.flows.application.services.validation_service import ValidationService

# Configure logging
logger = logging.getLogger(__name__)

# Create router with /validation prefix
validation_router = APIRouter(
    prefix="/validation",
    tags=["validation"],
    responses={500: {"description": "Internal server error", "model": ErrorResponse}},
)


@lru_cache
def get_validation_service() -> ValidationService:
    """Dependency injection for ValidationService.

    Creates and caches a singleton ValidationService instance for use across
    validation requests. The service is stateless and thread-safe.

    Returns:
        ValidationService: Cached validation service instance

    Note:
        Uses lru_cache to ensure only one instance is created per process.
    """
    return ValidationService()


@validation_router.post(
    "/validate_flow",
    response_model=FlowValidationResponse,
    status_code=200,
    summary="Validate a flow definition",
    description="Validates a flow definition and returns feature propagation results",
    responses={
        200: {
            "description": "Flow validation completed (may contain errors/warnings)",
            "model": FlowValidationResponse,
        },
        400: {
            "description": "Invalid request data",
            "model": ErrorResponse,
        },
        500: {
            "description": "Internal server error during validation",
            "model": ErrorResponse,
        },
    },
)
def validate_flow(
    body: dict,
    service: Annotated[ValidationService, Depends(get_validation_service)],
    is_elyra: bool = Query(
        default=False,
        description="Whether the flow definition is in Elyra format (requires conversion to internal DAG)",
    ),
) -> FlowValidationResponse:
    """Validate a flow definition without creating it.

    Accepts authoring format by default and Elyra format when `is_elyra` is true.
    This endpoint performs comprehensive validation without persisting the flow,
    making it ideal for pre-submission validation in UI/CLI tools.

    Validation Process:
        1. Format Detection: Determines if input is Elyra or authoring format
        2. Format Conversion: Converts to internal runtime DAG format
        3. Structure Validation: Validates DAG structure, edges, and node definitions
        4. Operator Validation: Checks operator availability and configuration
        5. Feature Propagation: Tracks features through the pipeline
        6. Dependency Validation: Ensures required features are available at each node

    Validation Checks:
        - DAG structure and connectivity (no cycles, no disjoint nodes)
        - Operator placement (Ingest first, VectorDB last recommended)
        - Operator configuration and parameter validation
        - Feature propagation through the pipeline
        - Required feature availability at each operator
        - Mandatory feature preservation (cannot drop id, content, etc.)

    Args:
        body: Raw request body containing flow definition. Format depends on is_elyra flag.
            For authoring format: {"flow_name": "My Flow", "flow": [...]}
            For Elyra format: {"doc_type": "pipeline", "pipelines": [...]}
        service: Injected validation service instance (dependency injection)
        is_elyra: Whether definition is in Elyra format requiring conversion.
            Default is False (authoring format).

    Returns:
        FlowValidationResponse: Validation results containing:
            - status: "SUCCEEDED", "FAILED", or "SUCCEEDED_WITH_WARNINGS"
            - message: Optional human-readable summary
            - errors: List of validation errors (empty if successful)
            - warnings: List of validation warnings (empty if none)

    Response Status Codes:
        - 200: Validation completed (check status field for actual result)
        - 400: Invalid request format or malformed flow definition
        - 500: Internal server error during validation

    Example Request (Authoring Format):
        ```json
        {
            "flow_name": "Simple Ingest Flow",
            "flow": [
                {
                    "type": "ingest_local",
                    "name": "Ingest Documents",
                    "config": {
                        "folder_path": "/data/documents"
                    },
                    "depends_on": []
                }
            ]
        }
        ```

    Example Response (Success):
        ```json
        {
            "status": "SUCCEEDED",
            "message": null,
            "errors": [],
            "warnings": []
        }
        ```

    Example Response (Failure):
        ```json
        {
            "status": "FAILED",
            "message": "Flow validation failed.",
            "errors": [
                {
                    "code": "OPERATOR_NOT_FOUND",
                    "message": "Operator not found: InvalidOperator",
                    "node_id": "node-123"
                }
            ],
            "warnings": []
        }
        ```

    Note:
        - This endpoint never raises exceptions; all errors are returned in response
        - Validation is stateless and does not modify any persisted data
        - Feature propagation results are computed but not included in response
          (use debug endpoints for detailed feature information)
        - The service handles format conversion internally based on is_elyra flag

    See Also:
        - ValidationService.validate_flow: Core validation logic
        - FlowValidator.validate_dag_with_features: DAG validation with feature tracking
        - FeaturePropagator: Feature propagation engine
    """
    logger.debug(f"Validating flow definition (is_elyra={is_elyra})")

    if is_elyra:
        flow_dto = ElyraFlowCreateRequest(**body)
        flow_definition = flow_dto.definition
    else:
        from docpipe.core.assets.flows.domain.models.authoring_flow import AuthoringFlow

        authoring_dto = AuthoringFlowCreateRequest(**body)
        authoring_flow = AuthoringFlow.from_dict(data=authoring_dto.model_dump())
        authoring_flow.validate()
        flow_definition = authoring_dto.model_dump()

    result = service.validate_flow(flow_definition=flow_definition, is_elyra=is_elyra)

    logger.info(
        f"Flow validation completed: status={result['status']}, "
        f"errors={len(result.get('errors', []))}, "
        f"warnings={len(result.get('warnings', []))}"
    )

    return FlowValidationResponse(**result)
