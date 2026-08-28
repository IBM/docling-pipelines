"""DTOs for GET /api/v1/projects/{project_id}/flows.

Three classes, each with a distinct role:

- FlowJobRunSummaryDTO  — Pydantic serialisation of the core FlowJobRunSummary
                          dataclass.  Carries aggregated run counts, the most
                          recent run's id/status/start_time, and a per-status
                          count map.  Absent (null in JSON) when a flow has
                          never been executed.

- ProjectFlowSummary    — Lightweight per-flow projection returned in the list.
                          Excludes the definition payload (Elyra pipeline JSON /
                          authoring DAG) — the endpoint is format-agnostic and
                          the UI only needs identity, provenance, tags, and run
                          status to render project flow cards.

- PaginatedProjectFlowResponse — Top-level paginated envelope.  Wraps a list of
                                  ProjectFlowSummary objects with total_count,
                                  offset/limit, and first/next/prev cursor links.

All integer fields carry explicit format (int32/int64) and min/max bounds so that
generated OpenAPI schemas satisfy ibm-integer-attributes.  All string fields carry
pattern/minLength/maxLength from field_definitions.py for the same reason.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from docpipe.api.dto.field_definitions import (
    CREATED_BY_DESC,
    JOB_STATUS_MAX_LENGTH,
    JOB_STATUS_MIN_LENGTH,
    JOB_STATUS_PATTERN,
    LIMIT_MAX,
    LIMIT_MIN,
    MODIFIED_BY_DESC,
    NAME_MAX_LENGTH,
    NAME_MIN_LENGTH,
    OFFSET_MAX,
    OFFSET_MIN,
    TAG_MAX_LENGTH,
    TAG_MIN_LENGTH,
    TAG_PATTERN,
    TAGS_ARRAY_MAX,
    TAGS_ARRAY_MIN,
    TOTAL_COUNT_MAX,
    TOTAL_COUNT_MIN,
    URL_MAX_LENGTH,
    URL_MIN_LENGTH,
    URL_PATTERN,
    USER_ID_MAX_LENGTH,
    USER_ID_MIN_LENGTH,
    USER_ID_PATTERN,
    UUID_LENGTH,
    UUID_PATTERN,
    datetime_field,
)


class FlowJobRunSummaryDTO(BaseModel):
    """Pydantic serialisation of FlowJobRunSummary for the API response layer.

    ProjectFlowMapper.to_dto() converts the core FlowJobRunSummary dataclass
    into this model before it is embedded in ProjectFlowSummary.

    None is used at the ProjectFlowSummary level (not here) to represent a flow
    that has never been executed — when this object exists, total_runs is always
    >= 1 and last_run_id/last_run_status/last_run_start_time are always set.

    Integer fields use json_schema_extra to inject format/minimum/maximum into
    the generated OpenAPI schema (Pydantic does not emit these from ge/le alone).
    """

    total_runs: int = Field(
        ...,
        ge=0,
        description="Total number of job runs recorded for this flow",
        json_schema_extra={"format": "int32", "maximum": 2_147_483_647},
    )
    last_run_id: str | None = Field(
        default=None,
        min_length=UUID_LENGTH,
        max_length=UUID_LENGTH,
        pattern=UUID_PATTERN,
        description="job_run_id of the most recent run, ordered by start_time desc",
        examples=["9a5137a7-15d5-431c-b945-b147a3043694"],
    )
    last_run_status: str | None = Field(
        default=None,
        min_length=JOB_STATUS_MIN_LENGTH,
        max_length=JOB_STATUS_MAX_LENGTH,
        pattern=JOB_STATUS_PATTERN,
        description="ExecutionStatus value of the most recent run",
        examples=["Completed", "Failed", "Running"],
    )
    last_run_start_time: int | None = Field(
        default=None,
        description="Epoch milliseconds of the most recent run start_time",
        json_schema_extra={"format": "int64", "minimum": 0, "maximum": 9_007_199_254_740_991},
    )
    status_counts: dict[str, int] = Field(
        default_factory=dict,
        description="Count of runs per ExecutionStatus value across all runs for this flow",
        examples=[{"Completed": 3, "Failed": 2}],
        json_schema_extra={
            "additionalProperties": {
                "type": "integer",
                "format": "int32",
                "minimum": 0,
                "maximum": 2_147_483_647,
            }
        },
    )


class ProjectFlowSummary(BaseModel):
    """Per-flow item in the GET /projects/{project_id}/flows response.

    Deliberately excludes the flow definition payload (the Elyra pipeline JSON
    or authoring DAG).  The endpoint serves project-overview UI cards that only
    need identity (flow_id, name), classification (tags), provenance
    (created_on, modified_on, created_by, modified_by), and last execution
    status (job_run_summary).

    job_run_summary is None when the flow has no recorded job runs.
    tags is always present — an empty list when the flow has no tags.
    """

    flow_id: str = Field(
        ...,
        min_length=UUID_LENGTH,
        max_length=UUID_LENGTH,
        pattern=UUID_PATTERN,
        description="Unique identifier for the flow",
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    )
    name: str = Field(
        ...,
        min_length=NAME_MIN_LENGTH,
        max_length=NAME_MAX_LENGTH,
        description="Flow name",
        examples=["Invoice Processing Pipeline"],
    )
    tags: list[str] = Field(
        ...,
        min_length=TAGS_ARRAY_MIN,
        max_length=TAGS_ARRAY_MAX,
        description="Flow tags (always present, empty array if no tags)",
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
    created_on: datetime | None = datetime_field(
        description="Timestamp when the flow was created",
        example="2026-04-01T11:00:00Z",
    )
    modified_on: datetime | None = datetime_field(
        description="Timestamp of the last modification",
        example="2026-04-01T12:30:00Z",
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
        examples=["editor@example.com"],
    )
    job_run_summary: FlowJobRunSummaryDTO | None = Field(
        default=None,
        description="Aggregated job run statistics. null if the flow has never been run.",
    )


class PaginatedProjectFlowResponse(BaseModel):
    """Paginated envelope for GET /api/v1/projects/{project_id}/flows.

    Follows the same offset/limit/link convention used by other list endpoints
    in this API (PaginatedAuthoringFlowResponse, PaginatedProjectResponse).

    Navigation links (first, next, prev) are absolute URLs.  next is None when
    the current page is the last page.  prev is None on the first page.
    """

    flows: list[ProjectFlowSummary] = Field(
        ...,
        description="List of flow summaries belonging to the project",
    )
    total_count: int = Field(
        ...,
        ge=TOTAL_COUNT_MIN,
        le=TOTAL_COUNT_MAX,
        description="Total number of flows matching the query (before pagination)",
        json_schema_extra={"format": "int32"},
    )
    offset: int = Field(
        ...,
        ge=OFFSET_MIN,
        le=OFFSET_MAX,
        description="Number of flows skipped",
        json_schema_extra={"format": "int32"},
    )
    limit: int = Field(
        ...,
        ge=LIMIT_MIN,
        le=LIMIT_MAX,
        description="Maximum flows returned per page",
        json_schema_extra={"format": "int32"},
    )
    first: str | None = Field(
        default=None,
        min_length=URL_MIN_LENGTH,
        max_length=URL_MAX_LENGTH,
        pattern=URL_PATTERN,
        description="Link to the first page",
    )
    next: str | None = Field(
        default=None,
        min_length=URL_MIN_LENGTH,
        max_length=URL_MAX_LENGTH,
        pattern=URL_PATTERN,
        description="Link to the next page, null if on last page",
    )
    prev: str | None = Field(
        default=None,
        min_length=URL_MIN_LENGTH,
        max_length=URL_MAX_LENGTH,
        pattern=URL_PATTERN,
        description="Link to the previous page, null if on first page",
    )
