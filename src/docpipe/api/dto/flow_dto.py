"""Flow API DTOs for request/response serialization and validation.

DTOs maintain separation from domain models (hexagonal architecture) and handle
OpenAPI schema generation with IBM validator compliance.

Request DTOs:
  - ElyraFlowCreateRequest: POST /flows with is_elyra=true (Elyra/UI format)
  - AuthoringFlowCreateRequest: POST /flows with is_elyra=false (Authoring/API format) - see authoring_flow_dto.py
  - ElyraFlowUpdateRequest: PATCH /flows/{id} (all optional, None=no update, []=clear)

Response DTOs:
  - FlowResponse: Single flow with server-generated metadata
  - PaginatedFlowResponse: Paginated list with navigation links

Utility DTOs:
  - RootResponse, HealthCheckResponse, BulkDeleteResponse

Validation: Field-level constraints + custom validators for definition structure
and tag deduplication. Supports DAG and legacy Elyra formats.
"""

from datetime import datetime
from typing import Annotated, Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

from docpipe.utils.core.validation import (
    deduplicate_tags,
    validate_flow_definition,
)

from .field_definitions import (
    # Patterns
    API_PATH_PATTERN,
    # Descriptions
    CONTAINER_ID_DESC,
    CONTAINER_KIND_DESC,
    # Constraints
    CONTAINER_KIND_MAX_LENGTH,
    CONTAINER_KIND_MIN_LENGTH,
    CONTAINER_KIND_PATTERN,
    CREATED_BY_DESC,
    CREATED_ON_DESC,
    DEFINITION_DESC,
    DEFINITION_EXAMPLE,
    DESCRIPTION_DESC,
    DESCRIPTION_MAX_LENGTH,
    DESCRIPTION_MIN_LENGTH,
    DESCRIPTION_PATTERN,
    FIRST_URL_DESC,
    FLOW_ID_DESC,
    FLOW_VERSION_DESC_DEFAULT,
    FLOWS_ARRAY_MAX,
    FLOWS_ARRAY_MIN,
    FLOWS_LIST_DESC,
    HREF_DESC,
    HREF_MAX_LENGTH,
    HREF_MIN_LENGTH,
    IS_HIDDEN_DESC,
    IS_HIDDEN_DESC_RESPONSE,
    JOB_ID_DESC,
    LIMIT_DESC,
    LIMIT_MAX,
    LIMIT_MIN,
    MODIFIED_BY_DESC,
    MODIFIED_ON_DESC,
    NAME_DESC,
    NAME_MAX_LENGTH,
    NAME_MIN_LENGTH,
    NAME_PATTERN,
    NEXT_URL_DESC,
    OFFSET_DESC,
    OFFSET_MAX,
    OFFSET_MIN,
    PREV_URL_DESC,
    TAG_MAX_LENGTH,
    TAG_MIN_LENGTH,
    TAG_PATTERN,
    TAGS_ARRAY_MAX,
    TAGS_ARRAY_MIN,
    TAGS_DESC_ALWAYS_PRESENT,
    TAGS_DESC_DEDUP,
    TOTAL_COUNT_DESC,
    TOTAL_COUNT_MAX,
    TOTAL_COUNT_MIN,
    URL_MAX_LENGTH,
    URL_MIN_LENGTH,
    URL_PATTERN,
    USER_ID_MAX_LENGTH,
    USER_ID_MIN_LENGTH,
    USER_ID_PATTERN,
    UUID_EXAMPLE,
    UUID_EXAMPLE_2,
    UUID_LENGTH,
    UUID_PATTERN,
    VERSION_MAX_LENGTH,
    VERSION_MIN_LENGTH,
    VERSION_PATTERN,
    # Field factories (only those with complex logic)
    datetime_field,
)

# ============================================================================
# REQUEST DTOs
# ============================================================================


class ElyraFlowCreateRequest(BaseModel):
    """Request DTO for creating flows in Elyra format via POST /flows (UI format).

    This DTO is used when is_elyra=True query parameter is set, indicating the flow
    is coming from the Elyra-based UI. The definition field contains the Elyra pipeline
    structure with doc_type, pipelines, and schemas.

    Required Fields:
        name: Human-readable flow identifier (1-255 chars, no control characters)

    Optional Fields with Defaults:
        tags: [] (empty list, duplicates auto-removed)
        is_hidden: False (visible by default)
        flow_version: "2.0" (current format version)

    Optional Fields (None if not provided):
        description: Detailed flow description (1-2000 chars)
        definition: Elyra pipeline structure with doc_type, pipelines, schemas
        container_kind: 'project' or 'space' (container type)
        container_id: UUID of parent container
        job_id: UUID of associated Prefect job
        created_by: User identifier (email or username)

    Validation Rules:
        - name: No control characters (0x00-0x1F), supports Unicode
        - description: Any characters including newlines
        - definition: Must have {doc_type, version, pipelines, schemas} (Elyra format)
        - tags: Lowercase alphanumeric with hyphens/underscores, auto-deduplicated
        - container_kind: Exactly 'project' or 'space' (case-sensitive)
        - UUIDs: Standard v4 format (lowercase hex with hyphens)
        - created_by: Alphanumeric with @._- characters

    Auto-Processing:
        - Tags are deduplicated while preserving order (first occurrence kept)
        - None values for optional fields are preserved (not converted to defaults)
        - flow_source automatically set to "UI"

    Example:
        >>> request = ElyraFlowCreateRequest(
        ...     name="Invoice Processing",
        ...     description="Extracts invoice data",
        ...     definition={"doc_type": "pipeline", "pipelines": [...]},
        ...     tags=["invoice", "production"],
        ...     container_kind="project",
        ...     container_id="550e8400-e29b-41d4-a716-446655440000"
        ... )
    """

    # Required fields
    name: str = Field(
        ...,
        min_length=NAME_MIN_LENGTH,
        max_length=NAME_MAX_LENGTH,
        pattern=NAME_PATTERN,
        description=NAME_DESC,
        examples=["Invoice Processing Pipeline", "Document Extraction Flow"],
    )

    # Optional content fields
    description: str | None = Field(
        default=None,
        min_length=DESCRIPTION_MIN_LENGTH,
        max_length=DESCRIPTION_MAX_LENGTH,
        pattern=DESCRIPTION_PATTERN,
        description=DESCRIPTION_DESC,
        examples=["Extracts entities from invoices and stores them in OpenSearch"],
    )
    definition: dict[str, Any] | None = Field(
        default=None,
        description=DEFINITION_DESC,
        examples=[DEFINITION_EXAMPLE],
    )
    tags: list[str] = Field(
        default_factory=list,
        min_length=TAGS_ARRAY_MIN,
        max_length=TAGS_ARRAY_MAX,
        description=TAGS_DESC_DEDUP,
        examples=[["invoice", "extraction", "production"]],
        json_schema_extra={
            "minItems": TAGS_ARRAY_MIN,
            "maxItems": TAGS_ARRAY_MAX,
            "items": {
                "type": "string",
                "minLength": TAG_MIN_LENGTH,
                "maxLength": TAG_MAX_LENGTH,
                "pattern": TAG_PATTERN,
            },
        },
    )

    # Optional container fields
    container_kind: str | None = Field(
        default=None,
        min_length=CONTAINER_KIND_MIN_LENGTH,
        max_length=CONTAINER_KIND_MAX_LENGTH,
        pattern=CONTAINER_KIND_PATTERN,
        description=CONTAINER_KIND_DESC,
        examples=["project", "space"],
    )
    container_id: str | None = Field(
        default=None,
        min_length=UUID_LENGTH,
        max_length=UUID_LENGTH,
        pattern=UUID_PATTERN,
        description=CONTAINER_ID_DESC,
        examples=[UUID_EXAMPLE],
    )

    # Optional metadata fields
    is_hidden: bool = Field(
        default=False,
        description=IS_HIDDEN_DESC,
        examples=[False, True],
    )
    flow_version: str | None = Field(
        default="2.0",
        min_length=VERSION_MIN_LENGTH,
        max_length=VERSION_MAX_LENGTH,
        pattern=VERSION_PATTERN,
        description=FLOW_VERSION_DESC_DEFAULT,
        examples=["2.0", "1.0"],
    )
    job_id: str | None = Field(
        default=None,
        min_length=UUID_LENGTH,
        max_length=UUID_LENGTH,
        pattern=UUID_PATTERN,
        description=JOB_ID_DESC,
        examples=[UUID_EXAMPLE_2],
    )
    created_by: str | None = Field(
        default=None,
        min_length=USER_ID_MIN_LENGTH,
        max_length=USER_ID_MAX_LENGTH,
        pattern=USER_ID_PATTERN,
        description=CREATED_BY_DESC,
        examples=["user@example.com"],
    )

    @field_validator("definition", mode="before")
    @classmethod
    def validate_definition_field(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        """Validate flow definition structure.

        Ensures definition contains required fields for supported formats:
        - Authoring format: Must have 'flow_name' and 'flow' keys
        - Legacy Elyra: Must have 'doc_type', 'version', 'pipelines', 'schemas' keys

        Args:
            v: Definition dictionary or None

        Returns:
            Validated definition or None

        Raises:
            ValueError: If definition is provided but missing required fields
        """
        return validate_flow_definition(v)

    @field_validator("tags", mode="before")
    @classmethod
    def deduplicate_tags_field(cls, v: list[str] | None) -> list[str]:
        """Remove duplicate tags while preserving order.

        Deduplication keeps the first occurrence of each tag. This validator
        always returns a list (converts None to []) since tags has a default_factory.

        Args:
            v: List of tags or None

        Returns:
            Deduplicated list of tags (empty list if input was None)

        Example:
            ["a", "b", "a", "c"] -> ["a", "b", "c"]
        """
        result = deduplicate_tags(v, allow_none=False)
        return result if result is not None else []


class ElyraFlowUpdateRequest(BaseModel):
    """Request DTO for partial updates via PATCH /flows/{id} (Elyra format).

    Implements REST PATCH semantics where all fields are optional and None means
    "don't update". This enables true partial updates where clients only send
    fields they want to change.

    PATCH Semantics:
        - Field omitted or None: Don't update this field (keep existing value)
        - Field with value: Update to this value
        - Empty collection (tags=[]): Clear the field (remove all tags)

    This distinction is critical:
        PATCH {"tags": null}  -> Don't update tags (keep existing)
        PATCH {"tags": []}    -> Clear all tags (set to empty list)
        PATCH {}              -> Don't update anything

    Optional Fields (all default to None):
        name: Update flow name
        description: Update description
        definition: Replace entire definition (Elyra format)
        tags: Replace tags ([] clears, None keeps existing)
        is_hidden: Update visibility
        container_kind: Update container type
        container_id: Update container reference

    Validation Rules:
        Same as ElyraFlowCreateRequest when field is provided (not None)

    Example:
        >>> # Update only name and clear tags
        >>> request = ElyraFlowUpdateRequest(
        ...     name="New Name",
        ...     tags=[]  # Clear all tags
        ...     # description not included = don't update
        ... )

        >>> # Update definition only
        >>> request = ElyraFlowUpdateRequest(
        ...     definition={"doc_type": "pipeline", "pipelines": [...]}
        ... )
    """

    # Optional content fields
    name: str | None = Field(
        default=None,
        min_length=NAME_MIN_LENGTH,
        max_length=NAME_MAX_LENGTH,
        pattern=NAME_PATTERN,
        description=NAME_DESC,
        examples=["Updated Flow Name"],
    )
    description: str | None = Field(
        default=None,
        min_length=DESCRIPTION_MIN_LENGTH,
        max_length=DESCRIPTION_MAX_LENGTH,
        pattern=DESCRIPTION_PATTERN,
        description=DESCRIPTION_DESC,
        examples=["Extracts entities from invoices and stores them in OpenSearch"],
    )
    definition: dict[str, Any] | None = Field(
        default=None,
        description=DEFINITION_DESC,
        examples=[DEFINITION_EXAMPLE],
    )
    tags: (
        list[Annotated[str, Field(min_length=TAG_MIN_LENGTH, max_length=TAG_MAX_LENGTH, pattern=TAG_PATTERN)]] | None
    ) = Field(
        default=None,
        min_length=TAGS_ARRAY_MIN,
        max_length=TAGS_ARRAY_MAX,
        description=TAGS_DESC_DEDUP,
        examples=[["invoice", "extraction", "production"]],
        json_schema_extra={
            "minItems": TAGS_ARRAY_MIN,
            "maxItems": TAGS_ARRAY_MAX,
            "items": {
                "type": "string",
                "minLength": TAG_MIN_LENGTH,
                "maxLength": TAG_MAX_LENGTH,
                "pattern": TAG_PATTERN,
            },
        },
    )

    # Optional metadata fields
    is_hidden: bool | None = Field(
        default=None,
        description=IS_HIDDEN_DESC,
        examples=[False, True],
    )

    # Optional container fields
    container_kind: str | None = Field(
        default=None,
        min_length=CONTAINER_KIND_MIN_LENGTH,
        max_length=CONTAINER_KIND_MAX_LENGTH,
        pattern=CONTAINER_KIND_PATTERN,
        description=CONTAINER_KIND_DESC,
        examples=["project", "space"],
    )
    container_id: str | None = Field(
        default=None,
        min_length=UUID_LENGTH,
        max_length=UUID_LENGTH,
        pattern=UUID_PATTERN,
        description=CONTAINER_ID_DESC,
        examples=[UUID_EXAMPLE],
    )

    @field_validator("definition", mode="before")
    @classmethod
    def validate_definition_field(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        """Validate flow definition structure.

        Ensures definition contains required fields for supported formats:
        - Authoring format: Must have 'flow_name' and 'flow' keys
        - Legacy Elyra: Must have 'doc_type', 'version', 'pipelines', 'schemas' keys

        Args:
            v: Definition dictionary or None

        Returns:
            Validated definition or None (None preserved for PATCH semantics)

        Raises:
            ValueError: If definition is provided but missing required fields
        """
        return validate_flow_definition(v)

    @field_validator("tags", mode="before")
    @classmethod
    def deduplicate_tags_field(cls, v: list[str] | None) -> list[str] | None:
        """Remove duplicate tags while preserving order.

        For PATCH requests, None is preserved to indicate "don't update tags".
        Empty list [] is preserved to indicate "clear all tags".

        Args:
            v: List of tags or None

        Returns:
            Deduplicated list of tags, or None if input was None

        Example:
            None -> None (don't update)
            [] -> [] (clear tags)
            ["a", "b", "a"] -> ["a", "b"] (deduplicate)
        """
        return deduplicate_tags(v, allow_none=True)


# ============================================================================
# RESPONSE DTOs
# ============================================================================


class FlowResponse(BaseModel):
    """Response DTO for flow data returned by API.

    Represents a complete flow including both user-provided fields and
    server-generated metadata. Used for GET /flows/{id} and in paginated lists.

    Field Categories:
        Identity: flow_id (server-generated UUID)
        Content: name, description, definition, tags (user-provided)
        Container: container_kind, container_id (optional organization)
        Metadata: is_hidden, flow_version, job_id (configuration)
        Timestamps: created_on, modified_on (server-generated)
        Users: created_by, modified_by (audit trail)
        Links: href (HATEOAS self-reference)

    Server-Generated Fields:
        - flow_id: Unique identifier assigned at creation
        - created_on: Timestamp when flow was created
        - modified_on: Timestamp of last modification
        - href: API URL to access this flow resource

    Required Fields:
        - flow_id: Always present (server-generated)
        - name: Always present (user-provided)
        - definition: Always present (user-provided)

    Optional Fields (may be None):
        - description, container_kind, container_id, job_id
        - created_by, modified_by, href

    Fields with Defaults:
        - tags: [] (empty list if no tags)
        - is_hidden: False (visible by default)
        - flow_version: "2.0" (current format)

    Example:
        >>> response = FlowResponse(
        ...     flow_id="550e8400-e29b-41d4-a716-446655440000",
        ...     name="Invoice Pipeline",
        ...     definition={"doc_type": "pipeline", "pipelines": [...]},
        ...     tags=["invoice", "production"],
        ...     created_on=datetime(2026, 4, 1, 11, 0, 0),
        ...     modified_on=datetime(2026, 4, 1, 11, 30, 0),
        ...     href="/api/v1/flows/550e8400-e29b-41d4-a716-446655440000"
        ... )
    """

    # Identity field (server-generated)
    flow_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        pattern=r"^[^/]+$",
        description=FLOW_ID_DESC,
        examples=[UUID_EXAMPLE],
    )

    # Content fields (user-provided)
    name: str = Field(
        ...,
        min_length=NAME_MIN_LENGTH,
        max_length=NAME_MAX_LENGTH,
        pattern=NAME_PATTERN,
        description=NAME_DESC,
        examples=["Invoice Processing Pipeline", "Document Extraction Flow"],
    )
    description: str | None = Field(
        default=None,
        min_length=DESCRIPTION_MIN_LENGTH,
        max_length=DESCRIPTION_MAX_LENGTH,
        pattern=DESCRIPTION_PATTERN,
        description=DESCRIPTION_DESC,
        examples=["Extracts entities from invoices and stores them in OpenSearch"],
    )
    definition: dict[str, Any] = Field(
        ...,
        description=DEFINITION_DESC,
        examples=[DEFINITION_EXAMPLE],
    )
    tags: list[str] = Field(
        default_factory=list,
        min_length=TAGS_ARRAY_MIN,
        max_length=TAGS_ARRAY_MAX,
        description=TAGS_DESC_ALWAYS_PRESENT,
        examples=[["invoice", "extraction", "production"]],
        json_schema_extra={
            "minItems": TAGS_ARRAY_MIN,
            "maxItems": TAGS_ARRAY_MAX,
            "items": {
                "type": "string",
                "minLength": TAG_MIN_LENGTH,
                "maxLength": TAG_MAX_LENGTH,
                "pattern": TAG_PATTERN,
            },
        },
    )

    # Container fields (optional organization)
    container_kind: str | None = Field(
        default=None,
        min_length=CONTAINER_KIND_MIN_LENGTH,
        max_length=CONTAINER_KIND_MAX_LENGTH,
        pattern=CONTAINER_KIND_PATTERN,
        description=CONTAINER_KIND_DESC,
        examples=["project", "space"],
    )
    container_id: str | None = Field(
        default=None,
        min_length=UUID_LENGTH,
        max_length=UUID_LENGTH,
        pattern=UUID_PATTERN,
        description=CONTAINER_ID_DESC,
        examples=[UUID_EXAMPLE],
    )

    # Metadata fields (configuration)
    is_hidden: bool = Field(
        default=False,
        description=IS_HIDDEN_DESC_RESPONSE,
        examples=[False],
    )
    flow_version: str = Field(
        default="2.0",
        min_length=VERSION_MIN_LENGTH,
        max_length=VERSION_MAX_LENGTH,
        pattern=VERSION_PATTERN,
        description=FLOW_VERSION_DESC_DEFAULT,
        examples=["2.0", "1.0"],
    )
    job_id: str | None = Field(
        default=None,
        min_length=UUID_LENGTH,
        max_length=UUID_LENGTH,
        pattern=UUID_PATTERN,
        description=JOB_ID_DESC,
        examples=[UUID_EXAMPLE_2],
    )

    # Timestamp fields (server-generated audit trail)
    created_on: datetime = datetime_field(
        description=CREATED_ON_DESC, example="2026-04-01T11:00:00Z"
    )  # Uses factory for complex json_schema_extra
    modified_on: datetime = datetime_field(
        description=MODIFIED_ON_DESC, example="2026-04-01T11:30:00Z"
    )  # Uses factory for complex json_schema_extra

    # User fields (audit trail)
    created_by: str | None = Field(
        default=None,
        min_length=USER_ID_MIN_LENGTH,
        max_length=USER_ID_MAX_LENGTH,
        pattern=USER_ID_PATTERN,
        description=CREATED_BY_DESC,
        examples=["user@example.com"],
    )
    modified_by: str | None = Field(
        default=None,
        min_length=USER_ID_MIN_LENGTH,
        max_length=USER_ID_MAX_LENGTH,
        pattern=USER_ID_PATTERN,
        description=MODIFIED_BY_DESC,
        examples=["admin@example.com"],
    )

    # Link field (HATEOAS self-reference)
    href: str | None = Field(
        default=None,
        min_length=HREF_MIN_LENGTH,
        max_length=HREF_MAX_LENGTH,
        pattern=API_PATH_PATTERN,
        description=HREF_DESC,
        examples=["/api/v1/flows/550e8400-e29b-41d4-a716-446655440000"],
    )

    class Config:
        """Pydantic model configuration.

        Configures JSON serialization and enables ORM mode for database models.
        """

        json_encoders: ClassVar[dict] = {datetime: lambda v: v.isoformat()}
        from_attributes = True
        json_schema_extra: ClassVar[dict] = {
            "examples": [
                {
                    "flow_id": "550e8400-e29b-41d4-a716-446655440000",
                    "name": "Invoice Processing Pipeline",
                    "description": "Extracts entities from invoices and stores them in OpenSearch",
                    "definition": {
                        "doc_type": "pipeline",
                        "version": "3.0",
                        "pipelines": [
                            {
                                "id": "550e8400-e29b-41d4-a716-446655440000",
                                "nodes": [],
                                "app_data": {"ui_data": {}, "version": 3.0},
                            }
                        ],
                        "schemas": [],
                    },
                    "tags": ["invoice", "extraction", "production"],
                    "container_kind": "project",
                    "container_id": "123e4567-e89b-12d3-a456-426614174000",
                    "is_hidden": False,
                    "flow_version": "2.0",
                    "created_on": "2026-04-01T11:00:00Z",
                    "modified_on": "2026-04-01T11:30:00Z",
                    "job_id": "9a5137a7-15d5-431c-b945-b147a3043694",
                    "created_by": "user@example.com",
                    "modified_by": "admin@example.com",
                    "href": "/api/v1/flows/550e8400-e29b-41d4-a716-446655440000",
                }
            ]
        }


class PaginatedFlowResponse(BaseModel):
    """Paginated response for GET /flows with offset-based pagination.

    Wraps a list of flows with pagination metadata and navigation links.
    Implements standard offset/limit pagination pattern.

    Pagination Model:
        - offset: Starting position in result set (0-based)
        - limit: Maximum items per page (1-100)
        - total_count: Total items across all pages

    Navigation Links (HATEOAS):
        - first: Always present, links to first page
        - next: Present if more pages exist, null otherwise
        - prev: Present if not on first page, null otherwise

    Example Response:
        {
            "flows": [...],
            "total_count": 150,
            "offset": 20,
            "limit": 10,
            "first": "https://api.example.com/v1/flows?offset=0&limit=10",
            "next": "https://api.example.com/v1/flows?offset=30&limit=10",
            "prev": "https://api.example.com/v1/flows?offset=10&limit=10"
        }

    Pagination Logic:
        - Page 1: offset=0, prev=null
        - Page 2: offset=10, prev=first
        - Last page: next=null
        - Empty result: flows=[], total_count=0
    """

    flows: list[FlowResponse] = Field(
        min_length=FLOWS_ARRAY_MIN,
        max_length=FLOWS_ARRAY_MAX,
        description=FLOWS_LIST_DESC,
        json_schema_extra={
            "minItems": FLOWS_ARRAY_MIN,
            "maxItems": FLOWS_ARRAY_MAX,
        },
    )
    total_count: int = Field(
        description=TOTAL_COUNT_DESC,
        ge=TOTAL_COUNT_MIN,
        le=TOTAL_COUNT_MAX,
        examples=[100],
        json_schema_extra={"format": "int64"},
    )
    offset: int = Field(
        description=OFFSET_DESC,
        ge=OFFSET_MIN,
        le=OFFSET_MAX,
        examples=[0, 10, 20],
        json_schema_extra={"format": "int32"},
    )
    limit: int = Field(
        description=LIMIT_DESC,
        ge=LIMIT_MIN,
        le=LIMIT_MAX,
        examples=[10],
        json_schema_extra={"format": "int32"},
    )
    first: str | None = Field(
        default=None,
        min_length=URL_MIN_LENGTH,
        max_length=URL_MAX_LENGTH,
        pattern=URL_PATTERN,
        description=FIRST_URL_DESC,
        examples=["https://api.example.com/v1/flows?offset=0&limit=10"],
    )
    next: str | None = Field(
        default=None,
        min_length=URL_MIN_LENGTH,
        max_length=URL_MAX_LENGTH,
        pattern=URL_PATTERN,
        description=NEXT_URL_DESC,
        examples=["https://api.example.com/v1/flows?offset=20&limit=10"],
    )
    prev: str | None = Field(
        default=None,
        min_length=URL_MIN_LENGTH,
        max_length=URL_MAX_LENGTH,
        pattern=URL_PATTERN,
        description=PREV_URL_DESC,
        examples=["https://api.example.com/v1/flows?offset=0&limit=10"],
    )

    class Config:
        """Pydantic model configuration."""

        json_schema_extra: ClassVar[dict] = {
            "examples": [
                {
                    "flows": [
                        {
                            "flow_id": "550e8400-e29b-41d4-a716-446655440000",
                            "name": "example-flow",
                            "description": "An example flow",
                            "definition": {"doc_type": "pipeline", "pipelines": []},
                            "tags": ["example"],
                            "container_kind": None,
                            "container_id": None,
                            "is_hidden": False,
                            "flow_version": "2.0",
                            "created_on": "2024-01-01T00:00:00Z",
                            "modified_on": "2024-01-01T00:00:00Z",
                            "job_id": None,
                            "created_by": None,
                            "modified_by": None,
                            "href": "/api/v1/flows/550e8400-e29b-41d4-a716-446655440000",
                        }
                    ],
                    "total_count": 100,
                    "offset": 0,
                    "limit": 10,
                    "first": "https://api.example.com/v1/flows?offset=0&limit=10",
                    "next": "https://api.example.com/v1/flows?offset=10&limit=10",
                    "prev": None,
                }
            ]
        }


# ============================================================================
# UTILITY DTOs
# ============================================================================


class RootResponse(BaseModel):
    """Response for GET / (API root endpoint).

    Simple welcome message for API discovery. Useful for health checks
    and verifying API is accessible.
    """

    message: str = Field(
        description="Welcome message for the API",
        examples=["Welcome to Docpipe Opensource API"],
        json_schema_extra={
            "minLength": 1,
            "maxLength": 500,
        },
    )

    model_config = ConfigDict(
        json_schema_extra={
            "description": "API root endpoint information",
            "examples": [{"message": "Welcome to Docpipe Opensource API"}],
        }
    )


class HealthCheckResponse(BaseModel):
    """Response for GET /health (health check endpoint).

    Indicates service health status. Used by load balancers, monitoring
    systems, and orchestration platforms (Kubernetes, etc.).
    """

    status: str = Field(
        description="Health status of the service",
        examples=["healthy"],
        json_schema_extra={
            "minLength": 1,
            "maxLength": 50,
            "pattern": "^[a-z_]+$",
        },
    )

    model_config = ConfigDict(
        json_schema_extra={"description": "API health check status", "examples": [{"status": "healthy"}]}
    )


class BulkDeleteResponse(BaseModel):
    """Response for DELETE /flows (bulk delete operation).

    Provides detailed results of bulk deletion, including which flows
    were successfully deleted and which failed with error messages.

    Response Structure:
        - deleted: List of successfully deleted flow IDs
        - failed: List of {flow_id, error} objects for failures
        - total_requested: Count of flows in delete request
        - total_deleted: Count of successful deletions
        - total_failed: Count of failed deletions

    Use Cases:
        - Cleanup operations (delete multiple test flows)
        - Batch management (remove flows by criteria)
        - Error handling (identify which deletions failed and why)

    Example:
        {
            "deleted": ["550e8400-...", "123e4567-..."],
            "failed": [{"flow_id": "9a5137a7-...", "error": "Flow not found"}],
            "total_requested": 3,
            "total_deleted": 2,
            "total_failed": 1
        }
    """

    deleted: list[str] = Field(
        description="List of successfully deleted flow IDs",
        json_schema_extra={
            "minItems": 0,
            "maxItems": 1000,
            "items": {
                "type": "string",
                "minLength": 1,
                "maxLength": 255,
                "pattern": "^[^/]+$",
            },
        },
    )
    failed: list[dict[str, str]] = Field(
        description="List of failed deletions with flow_id and error message",
        json_schema_extra={
            "minItems": 0,
            "maxItems": 1000,
            "items": {
                "type": "object",
                "properties": {
                    "flow_id": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 255,
                        "pattern": "^[^/]+$",
                    },
                    "error": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 1000,
                    },
                },
                "required": ["flow_id", "error"],
            },
        },
    )
    total_requested: int = Field(
        description="Total number of flows requested for deletion",
        ge=0,
        le=1000,
        json_schema_extra={"format": "int32"},
    )
    total_deleted: int = Field(
        description="Count of successfully deleted flows",
        ge=0,
        le=1000,
        json_schema_extra={"format": "int32"},
    )
    total_failed: int = Field(
        description="Count of failed deletions",
        ge=0,
        le=1000,
        json_schema_extra={"format": "int32"},
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "deleted": ["550e8400-e29b-41d4-a716-446655440000"],
                    "failed": [
                        {
                            "flow_id": "123e4567-e89b-12d3-a456-426614174000",
                            "error": "Flow not found",
                        }
                    ],
                    "total_requested": 2,
                    "total_deleted": 1,
                    "total_failed": 1,
                }
            ]
        }
    )


class ValidationAlertDTO(BaseModel):
    """DTO for a single validation alert (error or warning).

    Represents issues found during flow validation such as missing features,
    invalid operator configurations, or incompatible operator sequences.

    Matches the structure of ValidationAlert from docpipe_exceptions.py.
    """

    code: str | None = Field(
        default=None,
        description="Error or warning code",
        max_length=100,
        examples=["MISSING_REQUIRED_FEATURE", "INVALID_OPERATOR_CONFIG"],
    )
    message: str | None = Field(
        default=None,
        description="Human-readable description of the issue",
        max_length=1000,
        examples=["Required feature 'content' not available for operator 'chunker'"],
    )
    message_code: str | None = Field(
        default=None,
        description="Message code for internationalization",
        max_length=100,
        examples=["MISSING_REQUIRED_FEATURE"],
    )
    node_id: str | None = Field(
        default=None,
        description="ID of the operator node where the issue was found",
        min_length=UUID_LENGTH,
        max_length=UUID_LENGTH,
        pattern=UUID_PATTERN,
        examples=[UUID_EXAMPLE],
    )
    node_name: str | None = Field(
        default=None,
        description="Name of the operator where the issue was found",
        max_length=200,
        examples=["Extract Documents", "Chunk Content"],
    )
    operator: str | None = Field(
        default=None,
        description="Operator type where the issue was found",
        max_length=200,
        examples=["ExtractOperator", "Chunker"],
    )

    # Allow extra fields to match ValidationAlert's **kwargs behavior
    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={
            "examples": [
                {
                    "code": "MISSING_REQUIRED_FEATURE",
                    "message": "Required feature 'content' not available for operator 'chunker'",
                    "message_code": "MISSING_REQUIRED_FEATURE",
                    "node_id": "550e8400-e29b-41d4-a716-446655440000",
                    "node_name": "Chunk Content",
                    "operator": "Chunker",
                },
                {
                    "code": "INVALID_OPERATOR_CONFIG",
                    "message": "Embeddings operator should come after chunker for better performance",
                    "message_code": "SUBOPTIMAL_OPERATOR_SEQUENCE",
                    "node_id": "550e8400-e29b-41d4-a716-446655440001",
                    "node_name": "Generate Embeddings",
                    "operator": "EmbeddingsOperator",
                },
            ]
        },
    )


class FlowValidationResponse(BaseModel):
    """Response DTO for POST /flows/validate endpoint.

    Matches FlowValidationResult from docling-pipelines-api for compatibility.
    """

    status: str = Field(
        description="Status of the flow validation: SUCCEEDED, FAILED, or SUCCEEDED_WITH_WARNINGS",
        min_length=1,
        max_length=50,
        pattern="^[ -~]{1,50}$",
        examples=["SUCCEEDED", "FAILED", "SUCCEEDED_WITH_WARNINGS"],
    )
    message: str | None = Field(
        default=None,
        description="Overall validation message",
        min_length=1,
        max_length=10000,
        examples=["Flow validation failed.", "Flow validation succeeded."],
    )
    errors: list[ValidationAlertDTO] = Field(
        default_factory=list, description="List of validation errors that prevent flow execution", max_length=30
    )
    warnings: list[ValidationAlertDTO] = Field(
        default_factory=list, description="List of validation warnings (non-blocking issues)", max_length=30
    )

    model_config = ConfigDict(
        json_schema_extra={
            "description": "This model contains results from flow validation.",
            "examples": [
                {"status": "SUCCEEDED", "message": None, "errors": [], "warnings": []},
                {
                    "status": "FAILED",
                    "message": "Flow validation failed.",
                    "errors": [
                        {
                            "code": "flow_validation_failed",
                            "message": "Required feature 'content' not available",
                            "node_id": "123e4567-e89b-12d3-a456-426614174000",
                            "node_name": "Chunk Content",
                            "operator": "Chunker",
                        }
                    ],
                    "warnings": [],
                },
            ],
        }
    )
