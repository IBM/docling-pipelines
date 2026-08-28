"""Document set API DTOs for request/response serialization and validation.

DTOs maintain separation from domain models (hexagonal architecture) and handle
OpenAPI schema generation with IBM validator compliance.

Request DTOs:
  - DocumentSetCreateRequest: POST /document-sets (name required)
  - DocumentSetUpdateRequest: PATCH /document-sets/{id} (all optional)

Response DTOs:
  - DocumentSetResponse: Single document set with server-generated metadata
  - DocumentSetListResponse: Paginated list of document sets
  - DocumentSetPreviewResponse: Preview of document set data

Validation: Field-level constraints with proper OpenAPI schema generation.
"""

from datetime import datetime
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field

from .field_definitions import (
    # Constraints
    DESCRIPTION_MAX_LENGTH,
    DESCRIPTION_MIN_LENGTH,
    DESCRIPTION_PATTERN,
    NAME_MAX_LENGTH,
    NAME_MIN_LENGTH,
    NAME_PATTERN,
    OFFSET_MAX,
    OFFSET_MIN,
    TOTAL_COUNT_MAX,
    TOTAL_COUNT_MIN,
    UUID_EXAMPLE,
    UUID_LENGTH,
    UUID_PATTERN,
    # Field factories
    datetime_field,
)

# ============================================================================
# DOCUMENT SET SPECIFIC CONSTANTS
# ============================================================================

# Document Set Field Descriptions
DOCUMENT_SET_ID_DESC = "Unique identifier for the document set (UUID format)"
DOCUMENT_SET_NAME_DESC = "Unique document set name"
DOCUMENT_SET_DESCRIPTION_DESC = "Optional human-readable description of the document set"
STORAGE_BACKEND_DESC = "Storage backend used for the document set"
DATABASE_PATH_DESC = "Path to the database file used for storage"
TABLE_NAME_DESC = "Physical table name used to store document rows"
TOTAL_DOCUMENTS_DESC = "Total number of documents stored in the document set"
TOTAL_SIZE_BYTES_DESC = "Total size in bytes across all stored documents"
TOTAL_PAGES_DESC = "Total number of pages across all stored documents"
METADATA_DESC = "Arbitrary metadata associated with the document set"
CREATED_AT_DESC = "Timestamp when the document set was created (ISO 8601 format)"
UPDATED_AT_DESC = "Timestamp when the document set was last updated (ISO 8601 format)"

# Preview Field Descriptions
PREVIEW_COLUMNS_DESC = "Column names present in the preview result"
PREVIEW_DATA_DESC = "Preview rows converted to JSON-serializable dictionaries"
PREVIEW_TOTAL_ROWS_DESC = "Number of rows returned in this preview payload"

# List Response Field Descriptions
DOCUMENT_SETS_LIST_DESC = "Document sets returned for the current page"
DOCUMENT_SETS_TOTAL_DESC = "Total number of matching document sets"
DOCUMENT_SETS_LIMIT_DESC = "Maximum number of document sets requested"
DOCUMENT_SETS_OFFSET_DESC = "Number of document sets skipped before this page"

# Length Constraints
STORAGE_BACKEND_MIN_LENGTH = 1
STORAGE_BACKEND_MAX_LENGTH = 50
DATABASE_PATH_MIN_LENGTH = 1
DATABASE_PATH_MAX_LENGTH = 500
TABLE_NAME_MIN_LENGTH = 1
TABLE_NAME_MAX_LENGTH = 128

# Array Constraints
DOCUMENT_SETS_ARRAY_MIN = 0
DOCUMENT_SETS_ARRAY_MAX = 1000
PREVIEW_COLUMNS_MIN = 0
PREVIEW_COLUMNS_MAX = 100
PREVIEW_DATA_MIN = 0
PREVIEW_DATA_MAX = 1000

# Pagination Constraints
DOCUMENT_SETS_LIMIT_MIN = 1
DOCUMENT_SETS_LIMIT_MAX = 1000

# ============================================================================
# REQUEST DTOs
# ============================================================================


class DocumentSetCreateRequest(BaseModel):
    """Request DTO for creating new document sets via POST /document-sets.

    Used for document set creation where only 'name' is required. All other fields
    are optional with sensible defaults.

    Required Fields:
        name: Unique document set identifier (1-256 chars)

    Optional Fields (None if not provided):
        description: Detailed document set description (0-10000 chars)
        metadata: Arbitrary metadata dictionary

    Validation Rules:
        - name: Unicode characters excluding control characters (0x00-0x1F)
        - description: Any characters including newlines
        - metadata: Any valid JSON object

    Example:
        >>> request = DocumentSetCreateRequest(
        ...     name="Research Documents",
        ...     description="Collection of research papers and reports",
        ...     metadata={"source": "research_portal", "team": "nlp"}
        ... )
    """

    # Required fields
    name: str = Field(
        ...,
        min_length=NAME_MIN_LENGTH,
        max_length=NAME_MAX_LENGTH,
        pattern=NAME_PATTERN,
        description=DOCUMENT_SET_NAME_DESC,
        examples=["Research Documents", "Invoice Archive"],
    )

    # Optional content fields
    description: str | None = Field(
        default=None,
        min_length=DESCRIPTION_MIN_LENGTH,
        max_length=DESCRIPTION_MAX_LENGTH,
        pattern=DESCRIPTION_PATTERN,
        description=DOCUMENT_SET_DESCRIPTION_DESC,
        examples=["Collection of research papers and reports."],
    )
    metadata: dict[str, Any] | None = Field(
        default=None,
        description=METADATA_DESC,
        examples=[{"source": "research_portal", "team": "nlp"}],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "Research Documents",
                    "description": "Collection of research papers and reports.",
                    "metadata": {"source": "research_portal", "team": "nlp"},
                }
            ]
        }
    )


class DocumentSetUpdateRequest(BaseModel):
    """Request DTO for partial updates via PATCH /document-sets/{id}.

    Implements REST PATCH semantics where all fields are optional and None means
    "don't update". This enables true partial updates where clients only send
    fields they want to change.

    PATCH Semantics:
        - Field omitted or None: Don't update this field (keep existing value)
        - Field with value: Update to this value
        - Empty dict (metadata={}): Clear the field

    Optional Fields (all default to None):
        description: Update description
        metadata: Replace metadata ({} clears, None keeps existing)

    Validation Rules:
        Same as DocumentSetCreateRequest when field is provided (not None)

    Example:
        >>> # Update only description
        >>> request = DocumentSetUpdateRequest(
        ...     description="Updated document set description"
        ...     # metadata not included = don't update
        ... )

        >>> # Clear metadata
        >>> request = DocumentSetUpdateRequest(
        ...     metadata={}  # Clear all metadata
        ... )
    """

    # Optional content fields
    description: str | None = Field(
        default=None,
        min_length=DESCRIPTION_MIN_LENGTH,
        max_length=DESCRIPTION_MAX_LENGTH,
        pattern=DESCRIPTION_PATTERN,
        description="Updated description. Omit or set null to leave unchanged.",
        examples=["Updated document set description."],
    )
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Updated metadata. Omit or set null to leave unchanged.",
        examples=[{"version": "2.0", "owner": "platform-team"}],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "description": "Updated document set description.",
                    "metadata": {"version": "2.0", "owner": "platform-team"},
                }
            ]
        }
    )


# ============================================================================
# RESPONSE DTOs
# ============================================================================


class DocumentSetResponse(BaseModel):
    """Response DTO for document set data returned by API.

    Represents a complete document set including both user-provided fields and
    server-generated metadata. Used for GET /document-sets/{id} and in paginated lists.

    Field Categories:
        Identity: id (server-generated UUID)
        Content: name, description, metadata (user-provided)
        Storage: storage_backend, database_path, table_name (system-generated)
        Statistics: total_documents, total_size_bytes, total_pages (computed)
        Timestamps: created_at, updated_at (server-generated)

    Server-Generated Fields:
        - id: Unique identifier assigned at creation
        - storage_backend: Storage system used (e.g., "duckdb")
        - database_path: Physical database file path
        - table_name: Physical table name in database
        - total_documents, total_size_bytes, total_pages: Computed statistics
        - created_at: Timestamp when document set was created
        - updated_at: Timestamp of last modification

    Required Fields:
        - id, name, storage_backend, database_path, table_name
        - total_documents, total_size_bytes, total_pages
        - created_at, updated_at

    Optional Fields (may be None):
        - description

    Fields with Defaults:
        - metadata: {} (empty dict if no metadata)

    Example:
        >>> response = DocumentSetResponse(
        ...     id="550e8400-e29b-41d4-a716-446655440000",
        ...     name="Research Documents",
        ...     storage_backend="duckdb",
        ...     database_path="/var/data/document_sets.duckdb",
        ...     table_name="research_documents",
        ...     total_documents=125,
        ...     total_size_bytes=1048576,
        ...     total_pages=820,
        ...     created_at=datetime(2026, 4, 1, 11, 0, 0),
        ...     updated_at=datetime(2026, 4, 1, 11, 30, 0)
        ... )
    """

    # Identity field (server-generated)
    id: str = Field(
        ...,
        min_length=UUID_LENGTH,
        max_length=UUID_LENGTH,
        pattern=UUID_PATTERN,
        description=DOCUMENT_SET_ID_DESC,
        examples=[UUID_EXAMPLE],
    )

    # Content fields (user-provided)
    name: str = Field(
        ...,
        min_length=NAME_MIN_LENGTH,
        max_length=NAME_MAX_LENGTH,
        pattern=NAME_PATTERN,
        description=DOCUMENT_SET_NAME_DESC,
        examples=["Research Documents"],
    )
    description: str | None = Field(
        default=None,
        min_length=DESCRIPTION_MIN_LENGTH,
        max_length=DESCRIPTION_MAX_LENGTH,
        pattern=DESCRIPTION_PATTERN,
        description=DOCUMENT_SET_DESCRIPTION_DESC,
        examples=["Collection of research papers and reports."],
    )

    # Storage fields (system-generated)
    storage_backend: str = Field(
        ...,
        min_length=STORAGE_BACKEND_MIN_LENGTH,
        max_length=STORAGE_BACKEND_MAX_LENGTH,
        description=STORAGE_BACKEND_DESC,
        examples=["duckdb"],
    )
    database_path: str | None = Field(
        default=None,
        min_length=DATABASE_PATH_MIN_LENGTH,
        max_length=DATABASE_PATH_MAX_LENGTH,
        description=DATABASE_PATH_DESC,
        examples=["/var/data/document_sets.duckdb"],
    )
    table_name: str | None = Field(
        default=None,
        min_length=TABLE_NAME_MIN_LENGTH,
        max_length=TABLE_NAME_MAX_LENGTH,
        description=TABLE_NAME_DESC,
        examples=["research_documents"],
    )

    # Statistics fields (computed)
    total_documents: int = Field(
        ...,
        ge=0,
        description=TOTAL_DOCUMENTS_DESC,
        examples=[125],
        json_schema_extra={"format": "int32"},
    )
    total_size_bytes: int = Field(
        ...,
        ge=0,
        description=TOTAL_SIZE_BYTES_DESC,
        examples=[1048576],
        json_schema_extra={"format": "int64"},
    )
    total_pages: int = Field(
        ...,
        ge=0,
        description=TOTAL_PAGES_DESC,
        examples=[820],
        json_schema_extra={"format": "int32"},
    )

    # Timestamp fields (server-generated audit trail)
    created_at: datetime = datetime_field(description=CREATED_AT_DESC, example="2026-04-01T11:00:00Z")
    updated_at: datetime = datetime_field(description=UPDATED_AT_DESC, example="2026-04-01T11:30:00Z")

    # Metadata field (user-provided)
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description=METADATA_DESC,
        examples=[{"source": "research_portal", "team": "nlp"}],
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
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "name": "Research Documents",
                    "description": "Collection of research papers and reports.",
                    "storage_backend": "duckdb",
                    "database_path": "/var/data/document_sets.duckdb",
                    "table_name": "research_documents",
                    "total_documents": 125,
                    "total_size_bytes": 1048576,
                    "total_pages": 820,
                    "created_at": "2026-04-01T11:00:00Z",
                    "updated_at": "2026-04-01T11:30:00Z",
                    "metadata": {"source": "research_portal", "team": "nlp"},
                }
            ]
        }


class DocumentSetListResponse(BaseModel):
    """Paginated response for GET /document-sets with offset-based pagination.

    Wraps a list of document sets with pagination metadata. Implements standard
    offset/limit pagination pattern.

    Pagination Model:
        - offset: Starting position in result set (0-based)
        - limit: Maximum items per page (1-1000)
        - total: Total items across all pages

    Example Response:
        {
            "items": [...],
            "total": 150,
            "limit": 100,
            "offset": 0
        }

    Pagination Logic:
        - Page 1: offset=0
        - Page 2: offset=100
        - Empty result: items=[], total=0
    """

    items: list[DocumentSetResponse] = Field(
        default_factory=list,
        min_length=DOCUMENT_SETS_ARRAY_MIN,
        max_length=DOCUMENT_SETS_ARRAY_MAX,
        description=DOCUMENT_SETS_LIST_DESC,
        json_schema_extra={
            "minItems": DOCUMENT_SETS_ARRAY_MIN,
            "maxItems": DOCUMENT_SETS_ARRAY_MAX,
        },
    )
    total: int = Field(
        ...,
        ge=TOTAL_COUNT_MIN,
        le=TOTAL_COUNT_MAX,
        description=DOCUMENT_SETS_TOTAL_DESC,
        examples=[1],
        json_schema_extra={"format": "int64"},
    )
    limit: int = Field(
        ...,
        ge=DOCUMENT_SETS_LIMIT_MIN,
        le=DOCUMENT_SETS_LIMIT_MAX,
        description=DOCUMENT_SETS_LIMIT_DESC,
        examples=[100],
        json_schema_extra={"format": "int32"},
    )
    offset: int = Field(
        ...,
        ge=OFFSET_MIN,
        le=OFFSET_MAX,
        description=DOCUMENT_SETS_OFFSET_DESC,
        examples=[0],
        json_schema_extra={"format": "int32"},
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "items": [
                        {
                            "id": "550e8400-e29b-41d4-a716-446655440000",
                            "name": "Research Documents",
                            "description": "Collection of research papers and reports.",
                            "storage_backend": "duckdb",
                            "database_path": "/var/data/document_sets.duckdb",
                            "table_name": "research_documents",
                            "total_documents": 125,
                            "total_size_bytes": 1048576,
                            "total_pages": 820,
                            "created_at": "2026-04-01T11:00:00Z",
                            "updated_at": "2026-04-01T11:30:00Z",
                            "metadata": {"source": "research_portal", "team": "nlp"},
                        }
                    ],
                    "total": 1,
                    "limit": 100,
                    "offset": 0,
                }
            ]
        }
    )


class DocumentSetPreviewResponse(BaseModel):
    """Preview response DTO containing JSON-serializable table data.

    Used for GET /document-sets/{id}/preview to return a sample of document
    set data in a format suitable for API responses.

    Fields:
        columns: List of column names in the result
        data: List of row dictionaries (column_name -> value)
        total_rows: Number of rows in this preview

    Example:
        {
            "columns": ["id", "title", "size"],
            "data": [
                {"id": "doc-1", "title": "Document A", "size": 1024},
                {"id": "doc-2", "title": "Document B", "size": 2048}
            ],
            "total_rows": 2
        }
    """

    columns: list[str] = Field(
        default_factory=list,
        min_length=PREVIEW_COLUMNS_MIN,
        max_length=PREVIEW_COLUMNS_MAX,
        description=PREVIEW_COLUMNS_DESC,
        examples=[["id", "title", "size"]],
        json_schema_extra={
            "minItems": PREVIEW_COLUMNS_MIN,
            "maxItems": PREVIEW_COLUMNS_MAX,
            "items": {"type": "string", "minLength": 1, "maxLength": 128},
        },
    )
    data: list[dict[str, Any]] = Field(
        default_factory=list,
        min_length=PREVIEW_DATA_MIN,
        max_length=PREVIEW_DATA_MAX,
        description=PREVIEW_DATA_DESC,
        examples=[[{"id": "doc-1", "title": "Document A", "size": 1024}]],
        json_schema_extra={
            "minItems": PREVIEW_DATA_MIN,
            "maxItems": PREVIEW_DATA_MAX,
        },
    )
    total_rows: int = Field(
        ...,
        ge=0,
        description=PREVIEW_TOTAL_ROWS_DESC,
        examples=[10],
        json_schema_extra={"format": "int32"},
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "columns": ["id", "title", "size"],
                    "data": [
                        {"id": "doc-1", "title": "Document A", "size": 1024},
                        {"id": "doc-2", "title": "Document B", "size": 2048},
                    ],
                    "total_rows": 2,
                }
            ]
        }
    )
