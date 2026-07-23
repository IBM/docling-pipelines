"""Document Library API DTOs.

Request DTOs:
  - DocumentLibraryPrototype: POST /document_libraries (create)
  - DocumentLibraryPatch: PATCH /document_libraries/{id} (update)

Response DTOs:
  - DocumentLibrary: Single library response
  - DocumentLibraryWithDocumentSets: Library with document set IDs
  - DocumentSetsRetrieved: List of document sets for a library
  - DocumentSetForDocumentLibrary: Document set metadata in library context
"""

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ============================================================================
# FIELD DEFINITIONS (moved from field_definitions.py
# ============================================================================

# Patterns
UUID_PATTERN = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
UUID_PATTERN_LOWER = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
NONEMPTY_PATTERN = r"^.*\S.*$"
ANY_TEXT_PATTERN = r"^[\s\S]*$"
PRINTABLE_ASCII_PATTERN = r"^[ -~]*$"
# Name pattern: must start with letter, contain only letters/digits/spaces/underscores
NAME_PATTERN = r"^[a-zA-Z][a-zA-Z0-9_ ]*$"

# Document Library field definitions
name_field = Field(
    title="Document Library Name",
    description="Name of the document library (3-128 characters, must start with a letter, can contain letters, digits, spaces, and underscores only. Example: 'My Library Name' or 'Test_Library_123')",
    min_length=3,
    max_length=128,
    json_schema_extra={
        "pattern": NAME_PATTERN,  # For OpenAPI docs only
        "pattern_description": "Must start with a letter and contain only letters, digits, spaces, and underscores. Special characters like @#$%-!& are not allowed.",
        "examples": ["My Library", "Test_Library_123", "Document Collection 2024"],
    },
)

patch_name_field = Field(
    default=None,
    title="Document Library Name",
    description="Name of the document library (3-128 characters, must start with a letter, can contain letters, digits, spaces, and underscores only. Example: 'My Library Name' or 'Test_Library_123')",
    min_length=3,
    max_length=128,
    json_schema_extra={
        "pattern": NAME_PATTERN,  # For OpenAPI docs only
        "pattern_description": "Must start with a letter and contain only letters, digits, spaces, and underscores. Special characters like @#$%-!& are not allowed.",
        "examples": ["My Library", "Test_Library_123", "Document Collection 2024"],
    },
)

description_field = Field(
    default=None,
    title="Document Library Description",
    description="Description of the document library",
    min_length=0,
    max_length=2000,
    pattern=ANY_TEXT_PATTERN,
)

purpose_field = Field(
    default=None,
    title="Purpose",
    description="Additional information about the document library",
    min_length=0,
    max_length=1024,
    pattern=ANY_TEXT_PATTERN,
)

original_size_field = Field(
    default=None,
    title="Original Size",
    description="The input size of all document sets related to the document library",
    ge=0,
    le=9007199254740991,
    json_schema_extra={"format": "int64"},
)

final_size_field = Field(
    default=None,
    title="Final Size",
    description="The processed size of all document sets related to the document library",
    ge=0,
    le=9007199254740991,
    json_schema_extra={"format": "int64"},
)

tags_field: list[str] = Field(default_factory=list, title="Tags", description="Tags assigned to the document library")

# ============================================================================
# EXAMPLE PAYLOADS
# ============================================================================

document_library_prototype_example = {
    "name": "Document library",
    "description": "Document library description",
    "purpose": "Leave Policies",
    "original_size": 1073741824,
    "final_size": 1073741824,
    "tags": ["invoice", "billing"],
}

document_library_patch_example = {
    "name": "Document library",
    "description": "Document library description",
    "purpose": "Leave Policies",
    "original_size": 1073741824,
    "final_size": 1073741824,
    "tags": ["invoice", "billing"],
}

document_library_example = {
    "library_id": "7af0b030-05bc-11f0-ad30-153202918e02",
    "name": "Document library",
    "description": "Document library description",
    "purpose": "Leave Policies",
    "original_size": 1073741824,
    "final_size": 1073741824,
    "tags": ["invoice", "billing"],
    "created_by": "userA",
    "href": "https://cloud.ibm.com/data_quality/v3/projects/c19cde3a-5940-4c7a-ad0f-ee18f5f29c00/rules?limit=10",
}

document_example = {"size": 1073741824, "count": 10}

document_set_for_library_example = {
    "id": "8100c691-05d5-11f0-8ca4-c3576acbd7ce",
    "name": "Document set",
    "container_id": "fc25ac1b-b603-4011-a11c-1be0f41d7b51",
    "container_type": "project",
    "description": "Document set description",
    "documents": document_example,
    "tags": ["invoice", "billing"],
    "propagate_source_acls": True,
    "is_derivative_available": True,
}

document_sets_retrieved_example = {"document_sets": [document_set_for_library_example]}

document_library_with_document_sets_example = {
    **document_library_example,
    "document_sets": [
        "268264d6-0e19-4267-ad66-70ab3da725d1",
        "8153c440-6b47-4332-af2a-129e6e3db7ac",
    ],
}

# ============================================================================
# NESTED MODELS
# ============================================================================


class Document(BaseModel):
    """Document metadata for size and count information.

    Used within DocumentSetForDocumentLibrary to provide aggregate
    document statistics.
    """

    size: int | None = Field(
        default=None,
        title="Size",
        description="Total size of documents in bytes",
        ge=0,
        le=9007199254740991,
        json_schema_extra={"format": "int64"},
    )
    count: int | None = Field(
        default=None,
        title="Count",
        description="Total number of documents",
        ge=0,
        le=2147483647,
        json_schema_extra={"format": "int32"},
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": document_example,  # type: ignore[dict-item]
            "description": "Document size and count metadata",
        }
    )


# ============================================================================
# REQUEST DTOs
# ============================================================================


class DocumentLibraryPrototype(BaseModel):
    """Request DTO for creating document libraries via POST /document_libraries.


    Fields:
        library_id: Optional identifier (can be provided on create)
        name: Required library name (3-128 chars)
        description: Optional description (max 2000 chars)
        purpose: Optional additional information (max 1024 chars)
        original_size: Optional input size in bytes
        final_size: Optional processed size in bytes
        tags: Optional list of tags
    """

    library_id: str | None = Field(
        default=None,
        title="Asset ID",
        description="Identifier of the document library",
        min_length=36,
        max_length=36,
        pattern=UUID_PATTERN,
    )
    name: str = name_field
    description: str | None = description_field
    purpose: str | None = purpose_field
    original_size: int | None = original_size_field
    final_size: int | None = final_size_field
    tags: list[str] | None = tags_field

    @field_validator("name")
    @classmethod
    def validate_name_pattern(cls, v: str) -> str:
        """Validate name matches required pattern with user-friendly error message."""
        if not re.match(NAME_PATTERN, v):
            raise ValueError(
                "Name must start with a letter and can only contain letters, digits, spaces, and underscores. "
                "Special characters like @#$%-!& are not allowed. "
                "Examples: 'My Library', 'Test_Library_123', 'Document Collection 2024'"
            )
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": document_library_prototype_example,  # type: ignore[dict-item]
            "description": "The metadata for the collection of documents (document library prototype)",
        }
    )


class DocumentLibraryPatch(BaseModel):
    """Request DTO for updating document libraries via PATCH /document_libraries/{id}.

    All fields optional.

    Fields:
        name: Optional new library name
        description: Optional new description
        purpose: Optional new purpose
        original_size: Optional new original size
        final_size: Optional new final size
        tags: Optional new tags list
    """

    name: str | None = patch_name_field
    description: str | None = description_field
    purpose: str | None = purpose_field
    original_size: int | None = original_size_field
    final_size: int | None = final_size_field
    tags: list[str] | None = tags_field

    @field_validator("name")
    @classmethod
    def validate_name_pattern(cls, v: str | None) -> str | None:
        """Validate name matches required pattern with user-friendly error message."""
        if v is not None and not re.match(NAME_PATTERN, v):
            raise ValueError(
                "Name must start with a letter and can only contain letters, digits, spaces, and underscores. "
                "Special characters like @#$%-!& are not allowed. "
                "Examples: 'My Library', 'Test_Library_123', 'Document Collection 2024'"
            )
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": document_library_patch_example,  # type: ignore[dict-item]
            "description": "The metadata for the collection of documents (document library patch)",
        }
    )


# ============================================================================
# RESPONSE DTOs
# ============================================================================


class DocumentLibrary(BaseModel):
    """Response DTO for single document library.


    Fields:
        library_id: Library identifier (UUID)
        name: Library name
        description: Optional description
        purpose: Optional purpose/additional info
        original_size: Optional input size in bytes
        final_size: Optional processed size in bytes
        tags: Optional list of tags
        created_by: Optional creator username
        href: Optional hyperlink reference
        document_set_ids: List of document set IDs associated with this library
    """

    library_id: str | None = Field(
        default=None,
        title="Asset ID",
        description="Identifier of the document library",
        min_length=36,
        max_length=36,
        pattern=UUID_PATTERN,
    )
    name: str | None = name_field
    description: str | None = description_field
    purpose: str | None = purpose_field
    original_size: int | None = original_size_field
    final_size: int | None = final_size_field
    tags: list[str] | None = tags_field
    created_by: str | None = Field(
        default=None,
        title="Created By",
        description="The user who created the document library",
        min_length=0,
        max_length=63,
        pattern=NONEMPTY_PATTERN,
    )
    href: str | None = Field(
        default=None, title="Href", description="The target of the hyperlink", min_length=5, max_length=8000
    )
    document_set_ids: list[str] = Field(
        default_factory=list,
        title="Document Set IDs",
        description="List of document set IDs associated with this library",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": document_library_example,  # type: ignore[dict-item]
            "description": "The metadata for the collection of documents (document library)",
        }
    )


class DocumentSetForDocumentLibrary(BaseModel):
    """Document set metadata when listed under a library.


    Fields:
        id: Document set identifier
        name: Document set name
        container_id: Container (project/catalog) ID
        container_type: Type of container (project/catalog)
        description: Optional description
        documents: Document size/count metadata
        tags: Optional list of tags
        propagate_source_acls: Whether ACLs are fetched from source
        is_derivative_available: Whether datacard has derivatives
    """

    id: str | None = Field(
        default=None,
        title="Document Set ID",
        description="Identifier of the document set",
        min_length=36,
        max_length=36,
        pattern=UUID_PATTERN,
    )
    name: str | None = Field(
        default=None,
        title="Document Set Name",
        description="Name of the document set",
        min_length=1,
        max_length=256,
        pattern=NONEMPTY_PATTERN,
    )
    container_id: str | None = Field(
        default=None,
        title="Container ID",
        description="Identifier of the container",
        min_length=1,
        max_length=124,
        pattern=UUID_PATTERN_LOWER,
    )
    container_type: str | None = Field(
        default=None,
        title="Container Type",
        description="Type of the container project or catalog",
        min_length=1,
        max_length=124,
        pattern=NONEMPTY_PATTERN,
    )
    description: str | None = Field(
        default=None,
        title="Description",
        description="Description of the document set",
        min_length=0,
        max_length=1024,
        pattern=ANY_TEXT_PATTERN,
    )
    documents: Document | None = Field(
        default=None,
        title="Documents",
        description="Document size/count/pages metadata",
    )
    tags: list[str] | None = Field(
        default_factory=list,
        title="Tags",
        description="Tags assigned to the document set",
    )
    propagate_source_acls: bool | None = Field(
        default=None,
        title="Propagate Source ACLs",
        description="Boolean value to indicate if ACLs are fetched from data source",
    )
    is_derivative_available: bool | None = Field(
        default=None,
        title="Is Derivative Available",
        description="Boolean value to indicate if datacard has any derivative",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": document_set_for_library_example,  # type: ignore[dict-item]
            "description": "The metadata for the document set when listed under a library",
        }
    )


class DocumentSetsRetrieved(BaseModel):
    """Response DTO for list of document sets in a library.


    Fields:
        document_sets: List of document set metadata objects
    """

    document_sets: list[DocumentSetForDocumentLibrary] = Field(
        ...,
        title="Document Sets",
        description="Information about the document set for the given document library",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": document_sets_retrieved_example,  # type: ignore[dict-item]
            "description": "The list of document sets for the given document library",
        }
    )


class DocumentLibraryWithDocumentSets(DocumentLibrary):
    """Document library including list of related document set IDs.

    Extends DocumentLibrary with document_sets field.

    Fields:
        All DocumentLibrary fields plus:
        document_sets: List of document set IDs (UUIDs)
    """

    document_sets: list[str] | None = Field(
        default_factory=list,
        title="Document Set IDs",
        description="The list of document set ids",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": document_library_with_document_sets_example,  # type: ignore[dict-item]
            "description": "Document library including the list of related document set IDs",
        }
    )
