"""
NodeStatsDto - Node-level statistics model (enterprise-compatible)

Complete implementation with 16 fields as per specification.
Reference: JOBSTATS_HEXAGONAL_ARCHITECTURE_SPEC.md Section 2.1.2
"""

from typing import Any, ClassVar

from pydantic import BaseModel, Field

from docpipe.api.dto.field_definitions import (
    BATCH_ID_DESC,
    BATCH_ID_MAX_LENGTH,
    BATCH_ID_PATTERN,
    BATCH_NUM_DESC,
    BATCH_NUM_MAX,
    BATCH_NUM_MIN,
    COL_NAMES_DESC,
    COLUMN_NAME_MAX_LENGTH,
    COLUMN_NAME_MIN_LENGTH,
    COLUMN_NAME_PATTERN,
    COMPLETED_DOCS_DESC,
    DOCS_COMPLETED_COUNT_DESC,
    DOCS_COUNT_MAX,
    DOCS_COUNT_MIN,
    DURATION_MAX_SECONDS,
    END_TIME_DESC,
    ERROR_DESC,
    ERROR_MESSAGE_MAX_LENGTH,
    FAILED_DOCS_DESC,
    MESSAGE_PATTERN,
    NAME_DESC_NODE,
    NODE_ID_DESC,
    NODE_METADATA_DESC,
    NODE_STATUS_DESC,
    SKIPPED_DOCS_DESC,
    START_TIME_DESC,
    TIME_TAKEN_DESC,
    TIMESTAMP_MAX,
    TIMESTAMP_MIN,
    TOTAL_DOCS_DESC,
    UUID_LENGTH,
    UUID_PATTERN,
)
from docpipe.core.constants.constants import ExecutionStatus


class NodeMetadataItem(BaseModel):
    """
    Node metadata item with proper nested structure.

    {
        "id": "node-uuid",
        "operator": "Operator Name",
        "node_metadata": {
            "node_status": "COMPLETED",
            ...operator-specific fields...
        }
    }
    """

    id: str = Field(..., description="Node identifier")
    operator: str = Field(..., description="Operator name")
    node_metadata: dict[str, Any] | None = Field(
        default=None, description="Operator-specific metadata with node_status and custom fields"
    )


class NodeStatsDto(BaseModel):
    """
    Node-level statistics
    """

    # Identity Fields
    id: str = Field(
        ...,
        description=NODE_ID_DESC,
        min_length=UUID_LENGTH,
        max_length=UUID_LENGTH,
        pattern=UUID_PATTERN,
    )
    name: str = Field(
        ...,
        description=NAME_DESC_NODE,
        min_length=1,
        max_length=256,
    )

    # Status & Error
    node_status: str = Field(
        default=ExecutionStatus.PENDING.value,
        description=NODE_STATUS_DESC,
    )
    error: str = Field(
        default="",
        description=ERROR_DESC,
        min_length=0,
        max_length=ERROR_MESSAGE_MAX_LENGTH,
        pattern=MESSAGE_PATTERN,
    )

    # Timing Fields
    start_time: int = Field(
        default=0,
        description=START_TIME_DESC,
        ge=TIMESTAMP_MIN,
        le=TIMESTAMP_MAX,
        json_schema_extra={"format": "int64"},
    )
    end_time: int = Field(
        default=0, description=END_TIME_DESC, ge=TIMESTAMP_MIN, le=TIMESTAMP_MAX, json_schema_extra={"format": "int64"}
    )
    time_taken: int = Field(
        default=0,
        description=TIME_TAKEN_DESC,
        ge=TIMESTAMP_MIN,
        le=DURATION_MAX_SECONDS,
        json_schema_extra={"format": "int32"},
    )

    # Schema Information
    col_names: list[str] = Field(
        default_factory=list,
        description=COL_NAMES_DESC,
        min_length=0,
        max_length=1000,
        json_schema_extra={
            "minItems": 0,
            "maxItems": 1000,
            "items": {
                "type": "string",
                "minLength": COLUMN_NAME_MIN_LENGTH,
                "maxLength": COLUMN_NAME_MAX_LENGTH,
                "pattern": COLUMN_NAME_PATTERN,
            },
        },
    )

    # Document Tracking (Counts)
    total_docs: int = Field(
        default=0,
        description=TOTAL_DOCS_DESC,
        ge=DOCS_COUNT_MIN,
        le=DOCS_COUNT_MAX,
        json_schema_extra={"format": "int64"},
    )
    failed_docs: int = Field(
        default=0,
        description=FAILED_DOCS_DESC,
        ge=DOCS_COUNT_MIN,
        le=DOCS_COUNT_MAX,
        json_schema_extra={"format": "int64"},
    )
    skipped_docs: int = Field(
        default=0,
        description=SKIPPED_DOCS_DESC,
        ge=DOCS_COUNT_MIN,
        le=DOCS_COUNT_MAX,
        json_schema_extra={"format": "int64"},
    )
    docs_completed: int = Field(
        default=0,
        description=COMPLETED_DOCS_DESC,
        ge=DOCS_COUNT_MIN,
        le=DOCS_COUNT_MAX,
        json_schema_extra={"format": "int64"},
    )
    docs_completed_count: int = Field(
        default=0,
        description=DOCS_COMPLETED_COUNT_DESC,
        ge=DOCS_COUNT_MIN,
        le=DOCS_COUNT_MAX,
        json_schema_extra={"format": "int64"},
    )

    # Operator Metadata (Custom per operator)
    node_metadata: dict | None = Field(default=None, description=NODE_METADATA_DESC)

    # Batch Processing Fields (Micro-batching)
    batch_id: str | None = Field(
        default=None,
        description=BATCH_ID_DESC,
        min_length=1,
        max_length=BATCH_ID_MAX_LENGTH,
        pattern=BATCH_ID_PATTERN,
    )
    batch_num: int | None = Field(
        default=None,
        description=BATCH_NUM_DESC,
        ge=BATCH_NUM_MIN,
        le=BATCH_NUM_MAX,
        json_schema_extra={"format": "int32"},
    )

    class Config:
        json_schema_extra: ClassVar[dict[str, Any]] = {
            "example": {
                "id": "extract_docling_1",
                "name": "Extract Documents",
                "node_status": "COMPLETED",
                "start_time": 1704067200,
                "end_time": 1704067260,
                "time_taken": 60,
                "total_docs": 100,
                "docs_completed": 98,
                "failed_docs": 2,
                "batch_id": "123e4567-e89b-12d3-a456-426614174000",
                "batch_num": 0,
            }
        }
