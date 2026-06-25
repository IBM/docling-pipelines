"""Operator metadata API routes.

This module provides REST API endpoints for retrieving operator metadata including
operator configurations, features, and capabilities. It follows the standard
router → service → domain architecture pattern.

Architecture:
    Router Layer (this file)
        ↓
    Service Layer (OperatorMetadataService)
        ↓
    Domain Layer (OperatorMetadata)

Error Handling Strategy:
    All endpoints delegate to service layer which raises DocpipeException:
    - DocpipeException (500): Operator metadata retrieval failure
    - Error handler middleware converts DocpipeException to ErrorResponse DTO format
    - All errors logged with transaction ID for request tracing
    - No try/catch in router - exceptions bubble naturally to middleware

Endpoints:
    GET /api/v1/operators/metadata - Retrieve metadata for all operators

Dependencies:
    - OperatorMetadataService: Injected via get_operator_metadata_service()
    - Uses @lru_cache for singleton pattern in API context
"""

import logging
from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends

from docpipe.api.dto.error_dto import ErrorResponse
from docpipe.api.dto.operator_dto import OperatorMetadataItem
from docpipe.core.operators.application.services.operator_metadata_service import OperatorMetadataService

logger = logging.getLogger(__name__)

operators_router = APIRouter(prefix="/operators", tags=["Operators"])


@lru_cache
def get_operator_metadata_service() -> OperatorMetadataService:
    """Dependency provider for operator metadata service.

    Uses @lru_cache to create a singleton instance for the API context,
    improving performance by reusing the same service instance across requests.

    Note:
        While the service is cached here for API performance, the service class
        itself is not designed as a singleton and can be instantiated directly
        in other contexts (e.g., CLI, background jobs).

    Returns:
        OperatorMetadataService: Cached service instance for API use

    Example:
        >>> # In FastAPI endpoint
        >>> @router.get("/metadata")
        >>> def get_metadata(
        ...     service: Annotated[OperatorMetadataService, Depends(get_operator_metadata_service)]
        ... ):
        ...     return service.get_all_operator_metadata(internal_features=False)
    """
    logger.debug("Creating OperatorMetadataService instance")
    return OperatorMetadataService()


OperatorMetadataServiceDep = Annotated[OperatorMetadataService, Depends(get_operator_metadata_service)]


@operators_router.get(
    "/metadata",
    response_model=dict[str, OperatorMetadataItem],
    summary="Get all operator metadata",
    description="Retrieve metadata for all available operators in the system including their configurations, features, and capabilities",
    responses={
        200: {
            "description": "Operator metadata retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "extract_operator": {
                            "label": "Extract Operator",
                            "category": "Extract",
                            "description": "Extracts structured content from documents using Docling",
                            "features": {
                                "content": {
                                    "name": "Document Content",
                                    "description": "The markdown content extracted from the document",
                                    "type": "string",
                                    "required": True,
                                },
                                "doc_id_hash": {
                                    "name": "Hash ID",
                                    "description": "Hash ID of the document row",
                                    "type": "string",
                                    "required": True,
                                },
                            },
                            "required_features": [],
                            "attributes": {
                                "text_extraction_mode": {
                                    "type": "string",
                                    "description": "Text extraction strategy (docling_library or docling_serve)",
                                    "required": True,
                                    "default": "docling_library",
                                },
                                "entity_extraction_mode": {
                                    "type": "string",
                                    "description": "Entity extraction strategy (litellm, watsonx, docling, or none)",
                                    "required": False,
                                    "default": "none",
                                },
                            },
                        },
                        "chunker": {
                            "label": "Chunker",
                            "category": "Functional",
                            "description": "Splits documents into smaller chunks for processing",
                            "features": {
                                "chunk_id": {
                                    "name": "Chunk ID",
                                    "description": "Unique identifier for each chunk",
                                    "type": "string",
                                    "required": True,
                                },
                                "chunk_text": {
                                    "name": "Chunk Text",
                                    "description": "Text content of the chunk",
                                    "type": "string",
                                    "required": True,
                                },
                            },
                            "required_features": ["content"],
                            "attributes": {},
                        },
                    }
                }
            },
        },
        500: {"description": "Internal server error", "model": ErrorResponse},
    },
)
def get_operator_metadata(service: OperatorMetadataServiceDep) -> dict[str, OperatorMetadataItem]:
    """Get metadata for all available operators in the system.

    This endpoint retrieves comprehensive metadata for all registered operators,
    including their categories, features, and requirements. The metadata is used
    by the UI to:
    - Display available operators in flow builder
    - Show operator capabilities and configurations
    - Validate operator connections in pipelines
    - Provide autocomplete for operator parameters

    Internal features (like doc_id_hash) are filtered out by default to keep
    the API response focused on user-facing features.

    Args:
        service: Injected operator metadata service (via dependency injection)

    Returns:
        Dictionary mapping operator short names to their metadata. Each operator
        includes:
        - label: Human-readable name
        - category: Operator category (Extract, Ingest, Functional, Quality, VectorDB)
        - description: What the operator does
        - features: Dict of output features with types and descriptions
        - required_features: List of required input features
        - attributes: Dict of configuration attributes/parameters with types and descriptions

    Raises:
        DocpipeException: If metadata retrieval fails. The error_handler middleware
                          converts this to a proper HTTP 500 response with error details.

    Example Response:
        {
            "extract_operator": {
                "label": "Extract Operator",
                "category": "Extract",
                "description": "Extracts structured content from documents",
                "features": {
                    "content": {
                        "type": "string",
                        "description": "Markdown content",
                        "required": true
                    }
                },
                "required_features": [],
                "attributes": {
                    "text_extraction_mode": {
                        "type": "string",
                        "description": "Text extraction strategy",
                        "required": true,
                        "default": "docling_library"
                    }
                }
            },
            "chunker": {
                "label": "Chunker",
                "category": "Functional",
                "description": "Splits documents into chunks",
                "features": {
                    "chunk_text": {
                        "type": "string",
                        "description": "Chunk content"
                    }
                },
                "required_features": ["content"],
                "attributes": {}
            }
        }
    """
    metadata = service.get_all_operator_metadata(internal_features=False)

    logger.info("Successfully retrieved metadata for %d operators", len(metadata))

    # Convert raw metadata dict to proper response model
    operators_dict = {}
    for short_name, meta in metadata.items():
        operators_dict[short_name] = OperatorMetadataItem(
            label=meta.get("label", short_name),
            category=meta.get("category", "Custom"),  # Default to "Custom" (valid OperatorCategory enum value)
            description=meta.get("description"),
            features=meta.get("features", {}),
            required_features=meta.get("required_features", []),
            attributes=meta.get("attributes", {}),
        )

    return operators_dict
