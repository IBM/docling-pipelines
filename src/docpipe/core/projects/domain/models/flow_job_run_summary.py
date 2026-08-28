"""Core domain model for aggregated flow job run statistics.

Lives in the core layer (not docpipe.api) so that ProjectService can import and
construct it without creating a circular dependency through the API package.

The API layer never imports this class directly — ProjectFlowMapper is the only
consumer, and it immediately converts instances to FlowJobRunSummaryDTO before
handing them to the response model.
"""

from dataclasses import dataclass, field


@dataclass
class FlowJobRunSummary:
    """Aggregated job run statistics for a single flow, produced by ProjectService.

    Built in ProjectService._build_job_run_summaries() via a single bulk call to
    JobStatsService.list_job_runs(job_id=None).  The service groups all returned
    JobStats records by job_id (which equals flow_id in the standard OSS execution
    path) and collapses each group into one FlowJobRunSummary.

    Flows with no recorded job runs are absent from the summaries dict returned by
    get_project_flows_with_run_summary() — the absence is represented as None in
    ProjectFlowSummary.job_run_summary.

    Fields:
        total_runs:           Total number of JobStats records for this flow.
        last_run_id:          job_run_id of the most recent run (highest start_time).
        last_run_status:      ExecutionStatus string of the most recent run.
        last_run_start_time:  Epoch milliseconds of the most recent run's start_time.
                              None when start_time is not recorded.
        status_counts:        Mapping of ExecutionStatus string → count across all runs.
    """

    total_runs: int
    last_run_id: str | None = None
    last_run_status: str | None = None
    last_run_start_time: int | None = None
    status_counts: dict[str, int] = field(default_factory=dict)
