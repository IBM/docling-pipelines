"""Authoring format flow DTOs for simplified flow creation via HTTP API.

These DTOs support the authoring format which provides a simplified, user-friendly
way to define flows without manually managing UUIDs, edges, and low-level DAG details.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from docpipe.utils.core.validation import deduplicate_tags

from .field_definitions import (
    # Descriptions
    CREATED_BY_DESC,
    CREATED_ON_DESC,
    DESCRIPTION_DESC,
    # Constraints
    DESCRIPTION_MAX_LENGTH,
    DESCRIPTION_MIN_LENGTH,
    DESCRIPTION_PATTERN,
    FLOW_ID_DESC,
    FLOW_VERSION_DESC_DEFAULT,
    LIMIT_MAX,
    LIMIT_MIN,
    MODIFIED_BY_DESC,
    MODIFIED_ON_DESC,
    NAME_MAX_LENGTH,
    NAME_MIN_LENGTH,
    NAME_PATTERN,
    OFFSET_MAX,
    OFFSET_MIN,
    OPERATORS_ARRAY_MAX,
    OPERATORS_ARRAY_MIN,
    TAG_MAX_LENGTH,
    TAG_MIN_LENGTH,
    TAG_PATTERN,
    TAGS_ARRAY_MAX,
    TAGS_ARRAY_MIN,
    TAGS_DESC_DEDUP,
    TOTAL_COUNT_MAX,
    TOTAL_COUNT_MIN,
    TYPE_MAX_LENGTH,
    TYPE_MIN_LENGTH,
    TYPE_PATTERN,
    URL_MAX_LENGTH,
    URL_MIN_LENGTH,
    URL_PATTERN,
    USER_ID_MAX_LENGTH,
    USER_ID_MIN_LENGTH,
    USER_ID_PATTERN,
    UUID_EXAMPLE,
    VERSION_MAX_LENGTH,
    VERSION_MIN_LENGTH,
    VERSION_PATTERN,
    datetime_field,
)


class AuthoringOperatorDTO(BaseModel):
    """Operator definition in authoring format for HTTP API."""

    type: str = Field(
        ...,
        min_length=TYPE_MIN_LENGTH,
        max_length=TYPE_MAX_LENGTH,
        pattern=TYPE_PATTERN,
        description="Operator type identifier",
        examples=["ingest_source", "extract_operator", "embeddings"],
    )

    name: str = Field(
        ...,
        min_length=NAME_MIN_LENGTH,
        max_length=NAME_MAX_LENGTH,
        pattern=NAME_PATTERN,
        description="Unique operator name within the flow",
        examples=["ingest_source_filesystem", "extract_with_docling", "ollama_embeddings"],
    )

    config: dict[str, Any] = Field(
        default_factory=dict,
        description="Operator-specific configuration parameters (optional, defaults to empty dict)",
        examples=[{"paths": "./data", "include_filter": "pdf,docx"}],
    )

    depends_on: list[str] = Field(
        default_factory=list,
        description="List of operator names this operator depends on",
        examples=[["ingest_source_filesystem"], ["extract_with_docling", "semantic_chunker"]],
    )


class AuthoringFlowCreateRequest(BaseModel):
    """Request DTO for creating flows using authoring format via POST /flows.

    The authoring format provides a simplified way to define flows without managing
    UUIDs, edges, or low-level DAG structures. The API automatically compiles this
    format to runtime DAG format before storage.
    """

    flow_name: str = Field(
        ...,
        min_length=NAME_MIN_LENGTH,
        max_length=NAME_MAX_LENGTH,
        pattern=NAME_PATTERN,
        description="Human-readable flow identifier",
        examples=["complete-document-pipeline", "invoice-extraction-flow"],
    )

    description: str | None = Field(
        default=None,
        min_length=DESCRIPTION_MIN_LENGTH,
        max_length=DESCRIPTION_MAX_LENGTH,
        pattern=DESCRIPTION_PATTERN,
        description=DESCRIPTION_DESC,
        examples=["Complete document processing pipeline with vector storage"],
    )

    flow: list[AuthoringOperatorDTO] = Field(
        ...,
        min_length=OPERATORS_ARRAY_MIN,
        max_length=OPERATORS_ARRAY_MAX,
        description="List of operators in authoring format (1-10000 operators)",
    )

    global_config: dict[str, Any] = Field(
        default_factory=dict,
        description="Global configuration applied to all operators. Note: disable_validation must be a boolean (true/false), not a string.",
        examples=[{"doc_column": "content", "disable_validation": False}],
    )

    tags: list[str] = Field(
        default_factory=list,
        min_length=TAGS_ARRAY_MIN,
        max_length=TAGS_ARRAY_MAX,
        description=TAGS_DESC_DEDUP,
        examples=[["document-processing", "production", "vector-db"]],
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

    @field_validator("tags", mode="before")
    @classmethod
    def deduplicate_tags_field(cls, v: list[str] | None) -> list[str]:
        """Remove duplicate tags while preserving order."""
        result = deduplicate_tags(v, allow_none=False)
        return result if result is not None else []


class AuthoringFlowUpdateRequest(BaseModel):
    """Request DTO for partial updates via PATCH /flows/{id} (Authoring format).

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
        flow_name: Update flow name
        description: Update description
        flow: Replace entire flow definition (authoring format operators)
        global_config: Replace global configuration
        tags: Replace tags ([] clears, None keeps existing)

    Validation Rules:
        Same as AuthoringFlowCreateRequest when field is provided (not None)

    Example:
        >>> # Update only flow_name and clear tags
        >>> request = AuthoringFlowUpdateRequest(
        ...     flow_name="new-flow-name",
        ...     tags=[]  # Clear all tags
        ...     # description not included = don't update
        ... )

        >>> # Update flow definition only
        >>> request = AuthoringFlowUpdateRequest(
        ...     flow=[AuthoringOperatorDTO(...)]
        ... )
    """

    flow_name: str | None = Field(
        default=None,
        min_length=NAME_MIN_LENGTH,
        max_length=NAME_MAX_LENGTH,
        pattern=NAME_PATTERN,
        description="Human-readable flow identifier",
        examples=["updated-pipeline-name"],
    )

    description: str | None = Field(
        default=None,
        min_length=DESCRIPTION_MIN_LENGTH,
        max_length=DESCRIPTION_MAX_LENGTH,
        pattern=DESCRIPTION_PATTERN,
        description=DESCRIPTION_DESC,
        examples=["Updated pipeline description"],
    )

    flow: list[AuthoringOperatorDTO] | None = Field(
        default=None,
        min_length=OPERATORS_ARRAY_MIN,
        max_length=OPERATORS_ARRAY_MAX,
        description="List of operators in authoring format (1-10000 operators)",
    )

    global_config: dict[str, Any] | None = Field(
        default=None,
        description="Global configuration applied to all operators. Note: disable_validation must be a boolean (true/false), not a string.",
        examples=[{"doc_column": "content", "disable_validation": False}],
    )

    tags: list[str] | None = Field(
        default=None,
        min_length=TAGS_ARRAY_MIN,
        max_length=TAGS_ARRAY_MAX,
        description=TAGS_DESC_DEDUP,
        examples=[["document-processing", "production"]],
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

    @field_validator("tags", mode="before")
    @classmethod
    def deduplicate_tags_field(cls, v: list[str] | None) -> list[str] | None:
        """Remove duplicate tags while preserving order.

        For PATCH requests, None is preserved (don't update), but if a list
        is provided (even empty), duplicates are removed.

        Args:
            v: List of tags or None

        Returns:
            Deduplicated list of tags or None (None preserved for PATCH semantics)

        Example:
            ["a", "b", "a", "c"] -> ["a", "b", "c"]
            None -> None (don't update)
            [] -> [] (clear tags)
        """
        return deduplicate_tags(v, allow_none=True)


class AuthoringFlowResponse(BaseModel):
    """Response DTO for authoring format flows returned by GET /flows/{id}.

    Combines the authoring format structure with server-generated metadata fields.
    This maintains input/output format consistency while providing necessary metadata.
    """

    # Server-generated metadata
    flow_id: str = Field(
        ...,
        min_length=NAME_MIN_LENGTH,
        max_length=NAME_MAX_LENGTH,
        description=FLOW_ID_DESC,
        examples=[UUID_EXAMPLE],
    )

    # Authoring format fields
    flow_name: str = Field(
        ...,
        min_length=NAME_MIN_LENGTH,
        max_length=NAME_MAX_LENGTH,
        pattern=NAME_PATTERN,
        description="Human-readable flow identifier",
        examples=["complete-document-pipeline", "invoice-extraction-flow"],
    )

    description: str | None = Field(
        default=None,
        min_length=DESCRIPTION_MIN_LENGTH,
        max_length=DESCRIPTION_MAX_LENGTH,
        pattern=DESCRIPTION_PATTERN,
        description=DESCRIPTION_DESC,
        examples=["Complete document processing pipeline with vector storage"],
    )

    flow: list[AuthoringOperatorDTO] = Field(
        ...,
        min_length=OPERATORS_ARRAY_MIN,
        max_length=OPERATORS_ARRAY_MAX,
        description="List of operators in authoring format (1-10000 operators)",
    )

    global_config: dict[str, Any] = Field(
        default_factory=dict,
        description="Global configuration applied to all operators. Note: disable_validation must be a boolean (true/false), not a string.",
        examples=[{"doc_column": "content", "disable_validation": False}],
    )

    flow_source: str = Field(
        default="api",
        min_length=NAME_MIN_LENGTH,
        max_length=NAME_MAX_LENGTH,
        description="Source of flow creation (api, cli, ui, programmatic)",
        examples=["api", "cli"],
    )

    tags: list[str] = Field(
        default_factory=list,
        min_length=TAGS_ARRAY_MIN,
        max_length=TAGS_ARRAY_MAX,
        description=TAGS_DESC_DEDUP,
        examples=[["document-processing", "production", "vector-db"]],
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

    # Additional metadata fields
    flow_version: str = Field(
        default="2.0",
        min_length=VERSION_MIN_LENGTH,
        max_length=VERSION_MAX_LENGTH,
        pattern=VERSION_PATTERN,
        description=FLOW_VERSION_DESC_DEFAULT,
        examples=["2.0"],
    )

    created_on: datetime = datetime_field(
        description=CREATED_ON_DESC,
        example="2026-04-01T11:00:00Z",
    )

    modified_on: datetime = datetime_field(
        description=MODIFIED_ON_DESC,
        example="2026-04-01T11:30:00Z",
    )

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
        examples=["user@example.com"],
    )


class PaginatedAuthoringFlowResponse(BaseModel):
    """Paginated response for GET /flows with authoring format flows.

    Similar to PaginatedFlowResponse but contains AuthoringFlowResponse objects.
    """

    flows: list[AuthoringFlowResponse] = Field(
        default_factory=list,
        description="List of authoring format flows",
    )

    total_count: int = Field(
        ...,
        ge=TOTAL_COUNT_MIN,
        le=TOTAL_COUNT_MAX,
        description="Total number of flows matching the query",
        examples=[150],
        json_schema_extra={"format": "int64"},
    )

    offset: int = Field(
        ...,
        ge=OFFSET_MIN,
        le=OFFSET_MAX,
        description="Starting position in result set (0-based)",
        examples=[20],
        json_schema_extra={"format": "int32"},
    )

    limit: int = Field(
        ...,
        ge=LIMIT_MIN,
        le=LIMIT_MAX,
        description="Maximum items per page",
        examples=[100],
        json_schema_extra={"format": "int32"},
    )

    first: str = Field(
        ...,
        min_length=URL_MIN_LENGTH,
        max_length=URL_MAX_LENGTH,
        pattern=URL_PATTERN,
        description="Link to first page",
        examples=["https://api.example.com/v1/flows?offset=0&limit=10"],
    )

    next: str | None = Field(
        default=None,
        min_length=URL_MIN_LENGTH,
        max_length=URL_MAX_LENGTH,
        pattern=URL_PATTERN,
        description="Link to next page (null if on last page)",
        examples=["https://api.example.com/v1/flows?offset=30&limit=10"],
    )

    prev: str | None = Field(
        default=None,
        min_length=URL_MIN_LENGTH,
        max_length=URL_MAX_LENGTH,
        pattern=URL_PATTERN,
        description="Link to previous page (null if on first page)",
        examples=["https://api.example.com/v1/flows?offset=10&limit=10"],
    )
