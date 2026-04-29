"""Flow management API routes.

This module provides REST API endpoints for flow management operations including
create, read, update, delete, and list flows. It follows hexagonal architecture
with DTOs for API serialization and domain models for business logic.

Error Handling Strategy:
All endpoints delegate to service layer which raises custom DatasiftException subclasses:
- FlowNotFoundException (404): Flow not found
- FlowAlreadyExistsException (409): Duplicate flow name
- FlowInvalidDataException (400): Invalid flow data or validation failure
- FlowStorageException (500): File system errors
- Error handler middleware converts DatasiftException to ErrorResponse DTO format
- All errors logged with transaction ID for request tracing
"""

import logging
from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request

from datasift.api.dto.error_dto import ErrorResponse
from datasift.api.dto.field_definitions import (
    LIMIT_MAX,
    LIMIT_MIN,
    NAME_MAX_LENGTH,
    NAME_MIN_LENGTH,
    OFFSET_MAX,
    OFFSET_MIN,
    UUID_LENGTH,
    UUID_PATTERN,
)
from datasift.api.dto.flow_dto import (
    BulkDeleteResponse,
    FlowCreateRequest,
    FlowResponse,
    FlowUpdateRequest,
    PaginatedFlowResponse,
)
from datasift.api.dto.mappers.flow_mapper import FlowMapper
from datasift.core.flows.adapters.config.repository_factory import RepositoryFactory
from datasift.core.flows.application.services.flow_service import FlowService
from datasift.core.flows.domain.ports.flow_repository import FlowRepository

# Configure logging
logger = logging.getLogger(__name__)

# Create router
flows_router = APIRouter(prefix="/flows", tags=["Flows"])

# Path parameter type definitions
FlowIdPath = Annotated[
    str,
    Path(
        description="Unique identifier for the flow",
        min_length=UUID_LENGTH,
        max_length=UUID_LENGTH,
        pattern=UUID_PATTERN,
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    ),
]

# Query parameter type definitions
LimitQuery = Annotated[
    int,
    Query(
        description="Maximum number of flows to return",
        ge=LIMIT_MIN,
        le=LIMIT_MAX,
        examples=[100],
        json_schema_extra={"format": "int32"},
    ),
]

OffsetQuery = Annotated[
    int,
    Query(
        description="Number of flows to skip",
        ge=OFFSET_MIN,
        le=OFFSET_MAX,
        examples=[0],
        json_schema_extra={"format": "int32"},
    ),
]

NameQuery = Annotated[
    str | None,
    Query(
        description="Filter flows by name (partial match)",
        min_length=NAME_MIN_LENGTH,
        max_length=NAME_MAX_LENGTH,
        examples=["my-flow"],
        json_schema_extra={
            "minLength": NAME_MIN_LENGTH,
            "maxLength": NAME_MAX_LENGTH,
        },
    ),
]

TagsQuery = Annotated[
    list[str] | None,
    Query(
        description="Filter flows by tags",
        examples=[["production", "ml-pipeline"]],
        json_schema_extra={
            "minItems": 0,
            "maxItems": 100,
            "items": {
                "type": "string",
                "minLength": 1,
                "maxLength": 64,
                "pattern": r"^[A-Za-z0-9._:/# -]+$",
            },
        },
    ),
]

IsHiddenQuery = Annotated[
    bool | None,
    Query(
        description="Filter by visibility status",
        examples=[False],
    ),
]

FlowIdsQuery = Annotated[
    str,
    Query(
        description="Comma-separated list of flow IDs to delete",
        pattern=r"^[a-zA-Z0-9_-]+(,[a-zA-Z0-9_-]+)*$",
        examples=["flow-id-1,flow-id-2,flow-id-3"],
    ),
]


# Dependency functions for parameter extraction
def get_flow_id(flow_id: FlowIdPath) -> str:
    """Extract and validate flow ID from path parameter.

    Args:
        flow_id: Flow identifier from path

    Returns:
        Validated flow ID

    Raises:
        400: If flow_id is not a valid UUID format (handled by validation_exception_handler)
    """
    return flow_id


def get_pagination_params(
    limit: LimitQuery = 100,
    offset: OffsetQuery = 0,
) -> tuple[int, int]:
    """Extract and validate pagination parameters.

    Args:
        limit: Maximum number of results
        offset: Number of results to skip

    Returns:
        Tuple of (limit, offset)

    Raises:
        400: If parameters are out of valid range (handled by validation_exception_handler)
    """
    return limit, offset


def get_filter_params(
    name: NameQuery = None,
    tags: TagsQuery = None,
    is_hidden: IsHiddenQuery = None,
) -> dict:
    """Extract and validate filter parameters.

    Args:
        name: Flow name filter
        tags: Flow tags filter
        is_hidden: Visibility filter

    Returns:
        Dictionary of filter parameters
    """
    return {
        "name": name,
        "tags": tags,
        "is_hidden": is_hidden,
    }


# Dependency providers
@lru_cache(maxsize=1)
def get_flow_repository() -> FlowRepository:
    """Dependency provider for flow repository (singleton).

    Creates a single repository instance that is reused across all requests
    using LRU cache. Delegates to RepositoryFactory for repository creation
    and configuration.

    Returns:
        FlowRepository: Configured repository instance (cached singleton)

    Note:
        Configuration is handled by RepositoryFactory via environment variables.
        See RepositoryFactory.create_flow_repository() for configuration details.
    """
    return RepositoryFactory.create_flow_repository()


def get_flow_service(repository: FlowRepository = Depends(get_flow_repository)) -> FlowService:  # noqa: B008
    """Dependency provider for flow service.

    Args:
        repository: Injected repository instance

    Returns:
        FlowService: Service instance with injected repository
    """
    return FlowService(repository=repository)


# Type alias for dependency injection
PaginationDep = Annotated[tuple[int, int], Depends(get_pagination_params)]
FiltersDep = Annotated[dict, Depends(get_filter_params)]
FlowServiceDep = Annotated[FlowService, Depends(get_flow_service)]


@flows_router.post(
    "",
    response_model=FlowResponse,
    status_code=201,
    operation_id="create_flow",
    summary="Create a new flow",
    responses={
        201: {
            "description": "Flow created successfully",
            "content": {
                "application/json": {
                    "example": {
                        "flow_id": "550e8400-e29b-41d4-a716-446655440000",
                        "name": "Invoice Processing Pipeline",
                        "description": "Extracts entities from invoices",
                        "definition": {"nodes": [], "edges": []},
                        "tags": ["invoice", "extraction"],
                        "container_kind": "project",
                        "container_id": "123e4567-e89b-12d3-a456-426614174000",
                        "is_hidden": False,
                        "flow_version": "2.0",
                        "created_on": "2026-04-01T11:00:00Z",
                        "modified_on": "2026-04-01T11:00:00Z",
                        "job_id": None,
                        "created_by": "user@example.com",
                        "modified_by": None,
                        "href": "/api/v1/flows/550e8400-e29b-41d4-a716-446655440000",
                    }
                }
            },
        },
        400: {
            "model": ErrorResponse,
            "description": "Invalid request data or validation error",
            "content": {
                "application/json": {
                    "example": {
                        "errors": [
                            {
                                "code": "validation_error",
                                "message": "Field 'name' is required and cannot be empty",
                                "target": {"type": "field", "name": "name"},
                            },
                            {
                                "code": "validation_error",
                                "message": "Field 'definition' must be a valid JSON object",
                                "target": {"type": "field", "name": "definition"},
                            },
                        ],
                        "trace": "req-flow-create-400",
                        "status_code": 400,
                    }
                }
            },
        },
        409: {
            "model": ErrorResponse,
            "description": "Flow already exists",
            "content": {
                "application/json": {
                    "example": {
                        "errors": [
                            {
                                "code": "conflict",
                                "message": "A flow named 'customer-onboarding' already exists",
                                "target": {"type": "field", "name": "name"},
                            }
                        ],
                        "trace": "req-flow-create-409",
                        "status_code": 409,
                    }
                }
            },
        },
        500: {
            "model": ErrorResponse,
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "errors": [
                            {
                                "code": "internal_error",
                                "message": "An unexpected error occurred while creating the flow",
                            }
                        ],
                        "trace": "req-flow-create-500",
                        "status_code": 500,
                    }
                }
            },
        },
    },
)
async def create_flow(request: Request, flow: FlowCreateRequest, service: FlowServiceDep):
    """Create and store a new flow.

    Args:
        request: FastAPI request object
        flow: FlowCreateRequest DTO containing flow definition
        service: Injected flow service instance

    Returns:
        FlowResponse: The stored flow with generated metadata

    Raises:
        HTTPException: If flow creation fails (400, 409, 500)
    """
    logger.debug(f"Creating flow: {flow.name}")

    # Convert DTO to domain model
    domain_flow = FlowMapper.create_request_to_domain(flow)

    logger.debug(f"Converted to domain model: {domain_flow.name}")

    # Create flow using service - service raises typed exceptions
    created_flow = service.create_flow(domain_flow)

    logger.info(f"Successfully created flow {created_flow.flow_id}")

    # Convert domain model back to DTO
    return FlowMapper.domain_to_dto(created_flow)


@flows_router.get(
    "/{flow_id}",
    response_model=FlowResponse,
    operation_id="get_flow",
    summary="Get flow by ID",
    responses={
        200: {
            "description": "Flow retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "flow_id": "550e8400-e29b-41d4-a716-446655440000",
                        "name": "Invoice Processing Pipeline",
                        "description": "Extracts entities from invoices",
                        "definition": {"nodes": [], "edges": []},
                        "tags": ["invoice", "extraction"],
                        "container_kind": "project",
                        "container_id": "123e4567-e89b-12d3-a456-426614174000",
                        "is_hidden": False,
                        "flow_version": "2.0",
                        "created_on": "2026-04-01T11:00:00Z",
                        "modified_on": "2026-04-01T11:00:00Z",
                        "job_id": None,
                        "created_by": "user@example.com",
                        "modified_by": None,
                        "href": "/api/v1/flows/550e8400-e29b-41d4-a716-446655440000",
                    }
                }
            },
        },
        400: {
            "model": ErrorResponse,
            "description": "Validation error - invalid parameter format",
            "content": {
                "application/json": {
                    "example": {
                        "errors": [
                            {
                                "code": "validation_error",
                                "message": "flow_id must be a valid UUID format",
                                "target": {"type": "parameter", "name": "flow_id"},
                            }
                        ],
                        "trace": "req-flow-get-400",
                        "status_code": 400,
                    }
                }
            },
        },
        404: {
            "model": ErrorResponse,
            "description": "Flow not found",
            "content": {
                "application/json": {
                    "example": {
                        "errors": [
                            {
                                "code": "not_found",
                                "message": "Flow with ID '550e8400-e29b-41d4-a716-446655440000' not found",
                            }
                        ],
                        "trace": "req-flow-get-404",
                        "status_code": 404,
                    }
                }
            },
        },
        500: {
            "model": ErrorResponse,
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "errors": [
                            {
                                "code": "internal_error",
                                "message": "An unexpected error occurred while retrieving the flow",
                            }
                        ],
                        "trace": "req-flow-get-500",
                        "status_code": 500,
                    }
                }
            },
        },
    },
)
async def get_flow(
    service: FlowServiceDep,
    flow_id: str = Depends(get_flow_id),
):
    """Retrieve a flow by ID.

    Args:
        flow_id: UUID of the flow to retrieve (validated via dependency)
        service: Injected flow service instance

    Returns:
        FlowResponse: The requested flow

    Raises:
        HTTPException: If flow not found or read fails (404, 400, 500)
    """
    logger.debug(f"Retrieving flow: {flow_id}")

    # Get flow using service - service raises typed exceptions
    domain_flow = service.get_flow(flow_id)

    logger.info(f"Successfully retrieved flow {flow_id}")

    # Convert domain model to DTO
    return FlowMapper.domain_to_dto(domain_flow)


@flows_router.get(
    "",
    response_model=PaginatedFlowResponse,
    operation_id="list_flows",
    summary="List flows with pagination",
    responses={
        200: {
            "description": "Flows retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "flows": [
                            {
                                "flow_id": "550e8400-e29b-41d4-a716-446655440000",
                                "name": "Invoice Processing Pipeline",
                                "description": "Extracts entities from invoices",
                                "definition": {"nodes": [], "edges": []},
                                "tags": ["invoice", "extraction"],
                                "container_kind": "project",
                                "container_id": "123e4567-e89b-12d3-a456-426614174000",
                                "is_hidden": False,
                                "flow_version": "2.0",
                                "created_on": "2026-04-01T11:00:00Z",
                                "modified_on": "2026-04-01T11:00:00Z",
                                "job_id": None,
                                "created_by": "user@example.com",
                                "modified_by": None,
                                "href": "/api/v1/flows/550e8400-e29b-41d4-a716-446655440000",
                            }
                        ],
                        "total_count": 1,
                        "offset": 0,
                        "limit": 100,
                        "first": "/api/v1/flows?offset=0&limit=100",
                        "next": None,
                        "prev": None,
                    }
                }
            },
        },
        400: {
            "model": ErrorResponse,
            "description": "Validation error - invalid query parameters",
            "content": {
                "application/json": {
                    "example": {
                        "errors": [
                            {
                                "code": "validation_error",
                                "message": "limit must be between 1 and 1000",
                                "target": {"type": "parameter", "name": "limit"},
                            }
                        ],
                        "trace": "req-flow-list-400",
                        "status_code": 400,
                    }
                }
            },
        },
        500: {
            "model": ErrorResponse,
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "errors": [
                            {
                                "code": "internal_error",
                                "message": "An unexpected error occurred while listing flows",
                            }
                        ],
                        "trace": "req-flow-list-500",
                        "status_code": 500,
                    }
                }
            },
        },
    },
)
async def list_flows(
    request: Request,
    service: FlowServiceDep,
    pagination: PaginationDep,
    filters: FiltersDep,
):
    """List flows with pagination and filtering.

    Args:
        request: FastAPI request object
        service: Injected flow service instance
        pagination: Tuple of (limit, offset) from dependency
        filters: Dictionary of filter parameters from dependency

    Returns:
        PaginatedFlowResponse: Paginated list of flows

    Raises:
        HTTPException: If list operation fails (400, 500)
    """
    limit, offset = pagination
    name = filters["name"]
    tags = filters["tags"]
    is_hidden = filters["is_hidden"]

    logger.debug(f"Listing flows: offset={offset}, limit={limit}, name={name}, tags={tags}, is_hidden={is_hidden}")

    # Get flows using service with pagination and filtering - service raises typed exceptions
    flows = service.list_flows(skip=offset, limit=limit, name_filter=name, tags_filter=tags, is_hidden=is_hidden)

    # Get total count for pagination
    total = service.count_flows(name_filter=name, tags_filter=tags, is_hidden=is_hidden)

    logger.info(f"Successfully retrieved {len(flows)} flows (total: {total})")

    # Generate pagination links following REST API standards
    base_url = str(request.url).split("?")[0]
    first_link = f"{base_url}?offset=0&limit={limit}"
    next_link = f"{base_url}?offset={offset + limit}&limit={limit}" if (offset + len(flows)) < total else None
    prev_link = f"{base_url}?offset={max(0, offset - limit)}&limit={limit}" if offset > 0 else None

    # Convert domain models to DTOs
    return PaginatedFlowResponse(
        flows=[FlowMapper.domain_to_dto(flow) for flow in flows],
        total_count=total,
        offset=offset,
        limit=limit,
        first=first_link,
        next=next_link,
        prev=prev_link,
    )


@flows_router.put(
    "/{flow_id}",
    response_model=FlowResponse,
    operation_id="replace_flow",
    summary="Update a flow",
    responses={
        200: {
            "description": "Flow updated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "flow_id": "550e8400-e29b-41d4-a716-446655440000",
                        "name": "Updated Invoice Pipeline",
                        "description": "Updated description",
                        "definition": {"nodes": [], "edges": []},
                        "tags": ["invoice", "extraction", "updated"],
                        "container_kind": "project",
                        "container_id": "123e4567-e89b-12d3-a456-426614174000",
                        "is_hidden": False,
                        "flow_version": "2.0",
                        "created_on": "2026-04-01T11:00:00Z",
                        "modified_on": "2026-04-01T12:00:00Z",
                        "job_id": None,
                        "created_by": "user@example.com",
                        "modified_by": "user@example.com",
                        "href": "/api/v1/flows/550e8400-e29b-41d4-a716-446655440000",
                    }
                }
            },
        },
        400: {
            "model": ErrorResponse,
            "description": "Invalid request data, validation error, or invalid parameter format",
            "content": {
                "application/json": {
                    "example": {
                        "errors": [
                            {
                                "code": "validation_error",
                                "message": "Field 'definition' must contain at least one node",
                                "target": {"type": "field", "name": "definition"},
                            },
                        ],
                        "trace": "req-flow-update-400",
                        "status_code": 400,
                    }
                }
            },
        },
        404: {
            "model": ErrorResponse,
            "description": "Flow not found",
            "content": {
                "application/json": {
                    "example": {
                        "errors": [
                            {
                                "code": "not_found",
                                "message": "Flow with ID '550e8400-e29b-41d4-a716-446655440000' not found",
                            }
                        ],
                        "trace": "req-flow-update-404",
                        "status_code": 404,
                    }
                }
            },
        },
        500: {
            "model": ErrorResponse,
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "errors": [
                            {
                                "code": "internal_error",
                                "message": "An unexpected error occurred while updating the flow",
                            }
                        ],
                        "trace": "req-flow-update-500",
                        "status_code": 500,
                    }
                }
            },
        },
    },
)
async def update_flow(
    flow: FlowCreateRequest,
    service: FlowServiceDep,
    flow_id: str = Depends(get_flow_id),
):
    """Update an existing flow (full replacement).

    Args:
        flow_id: UUID of the flow to update (validated via dependency)
        flow: FlowCreateRequest DTO containing updated flow definition
        service: Injected flow service instance

    Returns:
        FlowResponse: The updated flow

    Raises:
        HTTPException: If flow not found or update fails (404, 400, 500)
    """
    logger.debug(f"Updating flow: {flow_id}")

    # Convert DTO to domain model
    domain_flow = FlowMapper.create_request_to_domain(flow)

    # Ensure flow_id matches
    domain_flow.flow_id = flow_id

    # Update flow using service - service raises typed exceptions
    updated_flow = service.update_flow(domain_flow)

    logger.info(f"Successfully updated flow {flow_id}")

    # Convert domain model back to DTO
    return FlowMapper.domain_to_dto(updated_flow)


@flows_router.patch(
    "/{flow_id}",
    response_model=FlowResponse,
    operation_id="update_flow",
    summary="Partially update a flow",
    responses={
        200: {
            "description": "Flow partially updated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "flow_id": "550e8400-e29b-41d4-a716-446655440000",
                        "name": "Invoice Processing Pipeline",
                        "description": "Extracts entities from invoices",
                        "definition": {"nodes": [], "edges": []},
                        "tags": ["invoice", "extraction", "updated"],
                        "container_kind": "project",
                        "container_id": "123e4567-e89b-12d3-a456-426614174000",
                        "is_hidden": False,
                        "flow_version": "2.0",
                        "created_on": "2026-04-01T11:00:00Z",
                        "modified_on": "2026-04-01T12:30:00Z",
                        "job_id": None,
                        "created_by": "user@example.com",
                        "modified_by": "user@example.com",
                        "href": "/api/v1/flows/550e8400-e29b-41d4-a716-446655440000",
                    }
                }
            },
        },
        400: {
            "model": ErrorResponse,
            "description": "Invalid request data, validation error, or invalid parameter format",
            "content": {
                "application/json": {
                    "example": {
                        "errors": [
                            {
                                "code": "validation_error",
                                "message": "Field 'tags' must be an array of strings",
                                "target": {"type": "field", "name": "tags"},
                            },
                        ],
                        "trace": "req-flow-patch-400",
                        "status_code": 400,
                    }
                }
            },
        },
        404: {
            "model": ErrorResponse,
            "description": "Flow not found",
            "content": {
                "application/json": {
                    "example": {
                        "errors": [
                            {
                                "code": "not_found",
                                "message": "Flow with ID '550e8400-e29b-41d4-a716-446655440000' not found",
                            }
                        ],
                        "trace": "req-flow-patch-404",
                        "status_code": 404,
                    }
                }
            },
        },
        500: {
            "model": ErrorResponse,
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "errors": [
                            {
                                "code": "internal_error",
                                "message": "An unexpected error occurred while partially updating the flow",
                            }
                        ],
                        "trace": "req-flow-patch-500",
                        "status_code": 500,
                    }
                }
            },
        },
    },
)
async def partial_update_flow(
    updates: FlowUpdateRequest,
    request: Request,
    service: FlowServiceDep,
    flow_id: str = Depends(get_flow_id),
):
    """Partially update a flow (only provided fields).

    Args:
        request: FastAPI request object
        flow_id: UUID of the flow to update (validated via dependency)
        updates: FlowUpdateRequest DTO containing fields to update
        service: Injected flow service instance

    Returns:
        FlowResponse: The updated flow

    Raises:
        HTTPException: If flow not found or update fails (404, 400, 500)
    """
    logger.debug(f"Partially updating flow: {flow_id}")

    # Partial update using service - service raises typed exceptions
    updated_flow = service.partial_update_flow(flow_id, updates.dict(exclude_unset=True))

    logger.info(f"Successfully partially updated flow {flow_id}")

    # Convert domain model back to DTO
    return FlowMapper.domain_to_dto(updated_flow)


@flows_router.delete(
    "/{flow_id}",
    status_code=204,
    operation_id="delete_flow",
    summary="Delete a flow",
    responses={
        204: {"description": "Flow deleted successfully"},
        400: {
            "model": ErrorResponse,
            "description": "Validation error - invalid parameter format",
            "content": {
                "application/json": {
                    "example": {
                        "errors": [
                            {
                                "code": "validation_error",
                                "message": "flow_id must be a valid UUID format",
                                "target": {"type": "parameter", "name": "flow_id"},
                            }
                        ],
                        "trace": "req-flow-delete-400",
                        "status_code": 400,
                    }
                }
            },
        },
        404: {
            "model": ErrorResponse,
            "description": "Flow not found",
            "content": {
                "application/json": {
                    "example": {
                        "errors": [
                            {
                                "code": "not_found",
                                "message": "Flow with ID '550e8400-e29b-41d4-a716-446655440000' not found",
                            }
                        ],
                        "trace": "req-flow-delete-404",
                        "status_code": 404,
                    }
                }
            },
        },
        500: {
            "model": ErrorResponse,
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "errors": [
                            {
                                "code": "internal_error",
                                "message": "An unexpected error occurred while deleting the flow",
                            }
                        ],
                        "trace": "req-flow-delete-500",
                        "status_code": 500,
                    }
                }
            },
        },
    },
)
async def delete_flow(
    request: Request,
    service: FlowServiceDep,
    flow_id: str = Depends(get_flow_id),
):
    """Delete a flow by ID.

    Args:
        request: FastAPI request object
        flow_id: UUID of the flow to delete (validated via dependency)
        service: Injected flow service instance

    Returns:
        No content on success

    Raises:
        HTTPException: If flow not found or delete fails (404, 400, 500)
    """
    logger.debug(f"Deleting flow: {flow_id}")

    # Delete flow using service - service raises typed exceptions
    service.delete_flow(flow_id)

    logger.info(f"Successfully deleted flow {flow_id}")

    # Return 204 No Content on success
    return None


@flows_router.delete(
    "",
    response_model=BulkDeleteResponse,
    status_code=200,
    operation_id="bulk_delete_flows",
    summary="Delete multiple flows",
    responses={
        200: {
            "description": "Bulk delete completed",
            "content": {
                "application/json": {
                    "example": {
                        "deleted": ["550e8400-e29b-41d4-a716-446655440000"],
                        "failed": [{"flow_id": "123e4567-e89b-12d3-a456-426614174000", "error": "Flow not found"}],
                        "total_requested": 2,
                        "total_deleted": 1,
                        "total_failed": 1,
                    }
                }
            },
        },
        400: {
            "model": ErrorResponse,
            "description": "Invalid request data, validation error, or invalid parameter format",
            "content": {
                "application/json": {
                    "example": {
                        "errors": [
                            {
                                "code": "invalid_request",
                                "message": "The 'flow_ids' list cannot be empty",
                                "target": {"type": "parameter", "name": "flow_ids"},
                            },
                            {
                                "code": "validation_error",
                                "message": "Each value in 'flow_ids' must be a valid UUID",
                                "target": {"type": "parameter", "name": "flow_ids"},
                            },
                        ],
                        "trace": "req-flow-bulk-delete-400",
                        "status_code": 400,
                    }
                }
            },
        },
        500: {
            "model": ErrorResponse,
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "errors": [
                            {
                                "code": "internal_error",
                                "message": "An unexpected error occurred while deleting flows",
                            }
                        ],
                        "trace": "req-flow-bulk-delete-500",
                        "status_code": 500,
                    }
                }
            },
        },
    },
)
async def bulk_delete_flows(
    request: Request,
    service: FlowServiceDep,
    flow_ids: FlowIdsQuery,
):
    """Delete multiple flows by their IDs.

    Args:
        request: FastAPI request object
        flow_ids: Comma-separated string of flow UUIDs to delete
        service: Injected flow service instance

    Returns:
        Dictionary with deletion results:
            - deleted: List of successfully deleted flow_ids
            - failed: List of dicts with flow_id and error for failures
            - total_requested: Total number of flows requested for deletion
            - total_deleted: Count of successfully deleted flows
            - total_failed: Count of failed deletions

    Raises:
        HTTPException: If bulk delete operation fails (400, 500)
    """
    # Convert comma-separated string to list
    flow_id_list = [fid.strip() for fid in flow_ids.split(",") if fid.strip()]

    logger.debug(f"Bulk deleting {len(flow_id_list)} flows")

    # Architectural refactoring: Validation moved to service layer
    # Service layer now validates empty flow_ids list and raises FlowInvalidDataException
    result = service.bulk_delete_flows(flow_id_list)

    logger.info(
        f"Bulk delete completed: {result['total_deleted']} deleted, "
        f"{result['total_failed']} failed out of {result['total_requested']} requested"
    )

    return result
