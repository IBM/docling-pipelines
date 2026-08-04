"""Mapper between the Flow domain model and ProjectFlowSummary DTO.

Used exclusively by the GET /api/v1/projects/{project_id}/flows route handler.
The mapper is the only place in the codebase that crosses the core→API boundary
for this feature: it receives a Flow domain object and a FlowJobRunSummary core
dataclass, and produces a ProjectFlowSummary Pydantic model ready for JSON
serialisation.
"""

from docpipe.api.dto.project_flow_dto import FlowJobRunSummaryDTO, ProjectFlowSummary
from docpipe.core.assets.flows.domain.models.flow import Flow
from docpipe.core.projects.domain.models.flow_job_run_summary import FlowJobRunSummary


class ProjectFlowMapper:
    """Converts Flow + FlowJobRunSummary pairs into ProjectFlowSummary DTOs.

    Stateless — all methods are static.  Format-agnostic: the mapping omits the
    flow definition payload entirely, so it works identically for Elyra-format
    and authoring-format flows.
    """

    @staticmethod
    def to_dto(
        *,
        flow: Flow,
        summary: FlowJobRunSummary | None,
    ) -> ProjectFlowSummary:
        """Convert a single Flow and its optional run summary to a ProjectFlowSummary.

        Converts FlowJobRunSummary (core dataclass) to FlowJobRunSummaryDTO
        (Pydantic) when a summary is present, preserving all five fields.
        Passes None through unchanged so the API response carries
        job_run_summary: null for flows that have never been executed.

        Args:
            flow: Flow domain model. flow_id, name, tags, created_on,
                  modified_on, created_by, and modified_by are mapped.
                  The definition payload is intentionally excluded.
            summary: Aggregated run stats built by
                     ProjectService._build_job_run_summaries(), or None
                     if the flow has no recorded job runs.

        Returns:
            ProjectFlowSummary DTO ready for inclusion in
            PaginatedProjectFlowResponse.
        """
        summary_dto = (
            FlowJobRunSummaryDTO(
                total_runs=summary.total_runs,
                last_run_id=summary.last_run_id,
                last_run_status=summary.last_run_status,
                last_run_start_time=summary.last_run_start_time,
                status_counts=summary.status_counts,
            )
            if summary is not None
            else None
        )
        return ProjectFlowSummary(
            flow_id=flow.flow_id,
            name=flow.name,
            tags=flow.tags,
            created_on=flow.created_on,
            modified_on=flow.modified_on,
            created_by=flow.created_by,
            modified_by=flow.modified_by,
            job_run_summary=summary_dto,
        )
