"""Data transfer objects for Custom Operator API endpoints.

This module provides Pydantic models for custom operator request and response
serialization, OpenAPI documentation, and schema validation.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from docpipe.api.dto.field_definitions import (
    DESCRIPTION_DESC,
    DESCRIPTION_MAX_LENGTH,
    DESCRIPTION_MIN_LENGTH,
    NAME_DESC,
    NAME_MAX_LENGTH,
    NAME_MIN_LENGTH,
    OPERATOR_FILE_MAX_LENGTH,
    OPERATOR_FILE_MIN_LENGTH,
    OPERATOR_SHORT_NAME_MAX_LENGTH,
    OPERATOR_SHORT_NAME_MIN_LENGTH,
    UUID_EXAMPLE,
    UUID_LENGTH,
    UUID_PATTERN,
    datetime_field,
)
from docpipe.core.custom_operators.models import CustomOperatorStatus

# ============================================================================
# RESPONSE DTOs
# ============================================================================


class CustomOperatorResponse(BaseModel):
    """Response DTO for custom operator data returned by the API.

    Represents a custom operator including its identity, lifecycle status,
    stored file metadata, and timestamps.
    """

    id: str = Field(
        ...,
        min_length=UUID_LENGTH,
        max_length=UUID_LENGTH,
        pattern=UUID_PATTERN,
        description="Unique identifier of the custom operator (UUID v4)",
        examples=[UUID_EXAMPLE],
    )
    name: str = Field(
        ...,
        min_length=NAME_MIN_LENGTH,
        max_length=NAME_MAX_LENGTH,
        description=NAME_DESC,
        examples=["Custom Invoice Extractor"],
    )
    description: str = Field(
        default="",
        min_length=DESCRIPTION_MIN_LENGTH,
        max_length=DESCRIPTION_MAX_LENGTH,
        description=DESCRIPTION_DESC,
        examples=["Custom operator for extracting fields from financial invoices"],
    )
    short_name: str = Field(
        ...,
        min_length=OPERATOR_SHORT_NAME_MIN_LENGTH,
        max_length=OPERATOR_SHORT_NAME_MAX_LENGTH,
        description="Short identifier used in pipeline flows",
        examples=["custom_invoice_extractor"],
    )
    status: CustomOperatorStatus = Field(
        ...,
        description="Lifecycle validation status of the operator",
        examples=[CustomOperatorStatus.VALIDATED],
    )
    message: str = Field(
        default="",
        description="Status explanation or validation error message",
        examples=["Operator validated and stored successfully"],
    )
    operator_file: str = Field(
        ...,
        min_length=OPERATOR_FILE_MIN_LENGTH,
        max_length=OPERATOR_FILE_MAX_LENGTH,
        description="Filename of the operator Python script",
        examples=["custom_invoice_extractor.py"],
    )
    created_at: datetime = datetime_field(
        description="Timestamp when operator was uploaded",
        example="2026-01-01T12:00:00Z",
    )
    updated_at: datetime = datetime_field(
        description="Timestamp of last update",
        example="2026-01-01T12:00:00Z",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Extracted operator metadata (category, class_name)",
        examples=[{"category": "Extract", "class_name": "CustomInvoiceExtractor"}],
    )

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        json_schema_extra={
            "description": "Custom operator response representation",
        },
    )


class CustomOperatorListResponse(BaseModel):
    """Response DTO for listing custom operators."""

    operators: list[CustomOperatorResponse] = Field(
        default_factory=list,
        description="List of custom operators",
    )
    count: int = Field(
        ...,
        ge=0,
        description="Total number of operators in the list",
        examples=[1],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "description": "List of custom operators with count",
        }
    )


class FileUploadResponse(BaseModel):
    """Response DTO for custom operator upload and update operations."""

    success: bool = Field(
        ...,
        description="Whether the upload/update operation succeeded",
        examples=[True],
    )
    operator_id: str = Field(
        ...,
        pattern=UUID_PATTERN,
        description="Unique identifier of the created or updated custom operator",
        examples=[UUID_EXAMPLE],
    )
    message: str = Field(
        ...,
        description="Operation result message",
        examples=["Custom operator created successfully"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "description": "Response for operator upload/update operations",
        }
    )


class CustomOperatorDeleteResponse(BaseModel):
    """Response DTO for custom operator deletion."""

    success: bool = Field(
        ...,
        description="Whether the deletion succeeded",
        examples=[True],
    )
    operator_id: str = Field(
        ...,
        pattern=UUID_PATTERN,
        description="Unique identifier of the deleted custom operator",
        examples=[UUID_EXAMPLE],
    )
    message: str = Field(
        ...,
        description="Deletion confirmation message",
        examples=["Custom operator deleted successfully"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "description": "Response for custom operator deletion",
        }
    )


class DirectoryTreeResponse(BaseModel):
    """Response DTO for custom operators directory tree."""

    directory_tree: dict[str, Any] = Field(
        ...,
        description="Nested dictionary representing the custom operators directory tree",
        examples=[
            {
                "name": "custom_operators",
                "type": "directory",
                "children": [],
            }
        ],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "description": "Directory tree structure of stored custom operators",
        }
    )
