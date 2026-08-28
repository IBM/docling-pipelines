"""Project DTOs for HTTP API serialisation.

Provides request and response models for all project API endpoints.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from docpipe.api.dto.field_definitions import (
    DESCRIPTION_MAX_LENGTH,
    DESCRIPTION_MIN_LENGTH,
    LIMIT_MAX,
    LIMIT_MIN,
    NAME_MAX_LENGTH,
    NAME_MIN_LENGTH,
    NAME_PATTERN,
    OFFSET_MAX,
    OFFSET_MIN,
    TAG_MAX_LENGTH,
    TAG_MIN_LENGTH,
    TAG_PATTERN,
    TAGS_ARRAY_MAX,
    TAGS_ARRAY_MIN,
    TOTAL_COUNT_MAX,
    TOTAL_COUNT_MIN,
    USER_ID_MAX_LENGTH,
    USER_ID_MIN_LENGTH,
    USER_ID_PATTERN,
    UUID_EXAMPLE,
    UUID_LENGTH,
    UUID_PATTERN,
    datetime_field,
)
from docpipe.utils.core.validation import deduplicate_tags

# ── Field-level constants ────────────────────────────────────────────────

PROJECT_ID_DESC = "Unique identifier for the project (UUID format)"
PROJECT_NAME_DESC = "Human-readable project name"
PROJECT_DESCRIPTION_DESC = "Optional description of the project"
PROJECT_TAGS_DESC = "Tags for categorising and filtering projects (duplicates removed)"
PROJECT_FLOW_COUNT_DESC = "Number of flows associated with this project"
PROJECT_CREATED_BY_DESC = "User identifier of the project creator"
PROJECT_MODIFIED_BY_DESC = "User identifier of the last person to modify the project"
PROJECT_CREATED_ON_DESC = "Timestamp when the project was created (ISO 8601 format)"
PROJECT_MODIFIED_ON_DESC = "Timestamp when the project was last modified (ISO 8601 format)"
PROJECT_HREF_DESC = "API URL reference to this project resource"

PROJECTS_LIST_DESC = "List of projects in the current page"
PROJECTS_TOTAL_DESC = "Total number of projects across all pages"
PROJECTS_LIMIT_DESC = "Maximum number of projects per page"
PROJECTS_OFFSET_DESC = "Number of projects skipped before this page"

TAG_ITEMS_SCHEMA: dict[str, Any] = {
    "type": "string",
    "minLength": TAG_MIN_LENGTH,
    "maxLength": TAG_MAX_LENGTH,
    "pattern": TAG_PATTERN,
}

_tag_field_kwargs: dict[str, Any] = {
    "description": PROJECT_TAGS_DESC,
    "min_length": TAGS_ARRAY_MIN,
    "max_length": TAGS_ARRAY_MAX,
    "examples": [["finance", "invoices"]],
    "json_schema_extra": {"items": TAG_ITEMS_SCHEMA},
}


# ── Request DTOs ────────────────────────────────────────────────────────


class ProjectCreateRequest(BaseModel):
    """Request body for POST /api/v1/projects."""

    name: str = Field(
        ...,
        min_length=NAME_MIN_LENGTH,
        max_length=NAME_MAX_LENGTH,
        pattern=NAME_PATTERN,
        description=PROJECT_NAME_DESC,
        examples=["Invoice Processing"],
    )
    description: str | None = Field(
        None,
        min_length=DESCRIPTION_MIN_LENGTH,
        max_length=DESCRIPTION_MAX_LENGTH,
        description=PROJECT_DESCRIPTION_DESC,
        examples=["Flows for processing invoice documents"],
    )
    tags: list[str] = Field(
        default_factory=list,
        **_tag_field_kwargs,
    )
    created_by: str | None = Field(
        None,
        min_length=USER_ID_MIN_LENGTH,
        max_length=USER_ID_MAX_LENGTH,
        pattern=USER_ID_PATTERN,
        description=PROJECT_CREATED_BY_DESC,
        examples=["user@example.com"],
    )

    @field_validator("tags", mode="before")
    @classmethod
    def deduplicate(cls, v: list[str] | None) -> list[str]:
        """Remove duplicate tags while preserving insertion order."""
        return deduplicate_tags(v) or []


class ProjectUpdateRequest(BaseModel):
    """Request body for PUT /api/v1/projects/{project_id} — full replace."""

    name: str = Field(
        ...,
        min_length=NAME_MIN_LENGTH,
        max_length=NAME_MAX_LENGTH,
        pattern=NAME_PATTERN,
        description=PROJECT_NAME_DESC,
        examples=["Invoice Processing v2"],
    )
    description: str | None = Field(
        None,
        min_length=DESCRIPTION_MIN_LENGTH,
        max_length=DESCRIPTION_MAX_LENGTH,
        description=PROJECT_DESCRIPTION_DESC,
        examples=["Updated flows for processing invoice documents"],
    )
    tags: list[str] = Field(default_factory=list, **_tag_field_kwargs)
    modified_by: str | None = Field(
        None,
        min_length=USER_ID_MIN_LENGTH,
        max_length=USER_ID_MAX_LENGTH,
        pattern=USER_ID_PATTERN,
        description=PROJECT_MODIFIED_BY_DESC,
        examples=["editor@example.com"],
    )

    @field_validator("tags", mode="before")
    @classmethod
    def deduplicate(cls, v: list[str] | None) -> list[str]:
        return deduplicate_tags(v) or []


class ProjectPatchRequest(BaseModel):
    """Request body for PATCH /api/v1/projects/{project_id} — partial update."""

    name: str | None = Field(
        None,
        min_length=NAME_MIN_LENGTH,
        max_length=NAME_MAX_LENGTH,
        pattern=NAME_PATTERN,
        description=PROJECT_NAME_DESC,
        examples=["Invoice Processing v2"],
    )
    description: str | None = Field(
        None,
        min_length=DESCRIPTION_MIN_LENGTH,
        max_length=DESCRIPTION_MAX_LENGTH,
        description=PROJECT_DESCRIPTION_DESC,
        examples=["Updated flows for processing invoice documents"],
    )
    tags: list[str] | None = Field(None, **_tag_field_kwargs)
    modified_by: str | None = Field(
        None,
        min_length=USER_ID_MIN_LENGTH,
        max_length=USER_ID_MAX_LENGTH,
        pattern=USER_ID_PATTERN,
        description=PROJECT_MODIFIED_BY_DESC,
        examples=["editor@example.com"],
    )

    @field_validator("tags", mode="before")
    @classmethod
    def deduplicate(cls, v: list[str] | None) -> list[str] | None:
        return deduplicate_tags(v, allow_none=True)


# ── Response DTOs ───────────────────────────────────────────────────────


class ProjectResponse(BaseModel):
    """Response body for all project endpoints returning a single project."""

    project_id: str = Field(
        ...,
        min_length=UUID_LENGTH,
        max_length=UUID_LENGTH,
        pattern=UUID_PATTERN,
        description=PROJECT_ID_DESC,
        examples=[UUID_EXAMPLE],
    )
    name: str = Field(..., description=PROJECT_NAME_DESC, examples=["Invoice Processing"])
    description: str | None = Field(None, description=PROJECT_DESCRIPTION_DESC)
    tags: list[str] = Field(default_factory=list, description=PROJECT_TAGS_DESC)
    flow_count: int = Field(0, ge=0, description=PROJECT_FLOW_COUNT_DESC, examples=[3])
    created_on: datetime = datetime_field(description=PROJECT_CREATED_ON_DESC, example="2026-07-08T10:00:00Z")
    modified_on: datetime = datetime_field(description=PROJECT_MODIFIED_ON_DESC, example="2026-07-08T11:00:00Z")
    created_by: str | None = Field(None, description=PROJECT_CREATED_BY_DESC)
    modified_by: str | None = Field(None, description=PROJECT_MODIFIED_BY_DESC)
    href: str | None = Field(None, description=PROJECT_HREF_DESC)

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={datetime: lambda v: v.isoformat()},
        json_schema_extra={
            "example": {
                "project_id": UUID_EXAMPLE,
                "name": "Invoice Processing",
                "description": "Flows for processing invoice documents",
                "tags": ["finance", "invoices"],
                "flow_count": 3,
                "created_on": "2026-07-08T10:00:00Z",
                "modified_on": "2026-07-08T11:00:00Z",
                "created_by": "user@example.com",
                "modified_by": "editor@example.com",
                "href": None,
            }
        },
    )


class PaginatedProjectResponse(BaseModel):
    """Response body for GET /api/v1/projects."""

    projects: list[ProjectResponse] = Field(default_factory=list, description=PROJECTS_LIST_DESC)
    total_count: int = Field(
        ...,
        ge=TOTAL_COUNT_MIN,
        le=TOTAL_COUNT_MAX,
        description=PROJECTS_TOTAL_DESC,
        examples=[1],
        json_schema_extra={"format": "int32"},
    )
    offset: int = Field(
        ...,
        ge=OFFSET_MIN,
        le=OFFSET_MAX,
        description=PROJECTS_OFFSET_DESC,
        examples=[0],
        json_schema_extra={"format": "int32"},
    )
    limit: int = Field(
        ...,
        ge=LIMIT_MIN,
        le=LIMIT_MAX,
        description=PROJECTS_LIMIT_DESC,
        examples=[100],
        json_schema_extra={"format": "int32"},
    )
    first: str | None = Field(None, description="URL to the first page of results")
    next: str | None = Field(None, description="URL to the next page of results")
    prev: str | None = Field(None, description="URL to the previous page of results")

    model_config = ConfigDict(from_attributes=True)
