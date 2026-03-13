from pydantic import BaseModel, Field

from common.constants.constants import ExecutionStatus, OrchestratorType

message_pattern = r"^[\x20-\x7E\n\r\t]*$"
node_status_pattern = r"^[A-Za-z0-9 _\-.]+$"


def normalize_node_stats_for_dto(job_stats_data: dict) -> dict:
    """
    Normalize node_stats data by ensuring each node has 'id' field instead of 'node_id'.
    This is needed for backward compatibility with old logs that use 'node_id' instead of 'id'.
    New job runs already write the correct format, so this only processes old data.

    Args:
        job_stats_data: Dictionary containing job stats with node_stats

    Returns:
        The same dictionary with normalized node_stats (Pydantic handles conversion to NodeStatsDto)
    """
    if "node_stats" in job_stats_data and isinstance(job_stats_data["node_stats"], dict):
        node_stats = job_stats_data["node_stats"]
        # Quick check: if first node already has 'id', assume all nodes are in new format
        if node_stats:
            first_node = next(iter(node_stats.values()), None)
            if isinstance(first_node, dict) and "id" in first_node:
                # Already in new format, no normalization needed
                return job_stats_data

        # Old format detected, normalize all nodes
        for node_data in node_stats.values():
            if isinstance(node_data, dict) and "node_id" in node_data and "id" not in node_data:
                node_data["id"] = node_data["node_id"]
    return job_stats_data


class JobStatsDto(BaseModel):
    """
    A class to store job statistics. (used only for stand-alone)

    Attributes:
        job_id (str): The ID of the job.
        start_time (float): The time the job started, in seconds since the epoch.
        total_docs (int): The total number of documents in the job.
        processed_docs (int): The number of documents processed so far.
        end_time (int): The time the job ended, in seconds since the epoch.
        duration (float): The duration of the job, in seconds.
        status (str): The status of the job, either " ongoing", "completed", or "failed".

    Methods:
        update_progress(processed_docs): Updates the number of processed documents.
    """

    job_id: str
    job_run_id: str
    status: ExecutionStatus = ExecutionStatus.STARTING
    message: str = "No message"
    start_time: int = 0
    end_time: int = 0
    duration: int = 0
    total_docs: int = 0
    processed_docs: int = 0
    total_pages_processed: int = 0
    execution_time: int | None = None
    failed_docs: int = 0
    skipped_docs: int = 0
    deleted_doc_count: int = 0
    node_stats: dict[str, "NodeStatsDto"] = {}
    orchestrator: str = OrchestratorType.PYTHON.capitalize()
    heartbeat_timestamp: int | None = 0
    flow_id: str | None = ""

    @classmethod
    def create_running_job_stats(
        cls,
        job_id: str,
        job_run_id: str,
        flow_id: str,
        orchestrator_type: str = OrchestratorType.PYTHON,
    ) -> "JobStatsDto":
        """
        Create a JobStatsDto instance with basic initialization for a running job.

        Args:
            job_id: The ID of the job
            job_run_id: The ID of the job run
            flow_id: The ID of the flow for which this job run was created
            orchestrator_type: The type of orchestrator (default: PYTHON)

        Returns:
            A new JobStatsDto instance initialized with running status
        """
        from datetime import datetime

        current_time = round(datetime.now().timestamp())

        return cls(
            job_id=job_id,
            job_run_id=job_run_id,
            start_time=current_time,
            status=ExecutionStatus.RUNNING,
            orchestrator=orchestrator_type.capitalize(),
            heartbeat_timestamp=current_time,
            flow_id=flow_id,
        )

    @classmethod
    def from_model(cls, model: "JobRunStats") -> "JobStatsDto":  # noqa: F821
        """
        Create a JobStatsDto instance from a JobRunStats model.

        Args:
            model: The JobRunStats model instance to convert

        Returns:
            A new JobStatsDto instance with data from the model
        """
        return cls(
            job_id=model.job_id,
            job_run_id=model.job_run_id,
            status=model.status,
            message=model.message,
            start_time=model.start_time,
            end_time=model.end_time,
            duration=model.duration,
            total_docs=model.total_docs,
            processed_docs=model.processed_docs,
            total_pages_processed=model.total_pages_processed,
            execution_time=model.execution_time,
            failed_docs=model.failed_docs,
            skipped_docs=model.skipped_docs,
            deleted_doc_count=model.deleted_doc_count,
            orchestrator=model.orchestrator,
            heartbeat_timestamp=model.heartbeat_timestamp,
            flow_id=model.flow_id,
        )


class NodeStatsDto(BaseModel):
    @classmethod
    def from_model(cls, model: "NodeStats") -> "NodeStatsDto":  # noqa: F821
        new_instance = cls(
            id=model.node_id,
            name=model.name,
            node_status=model.node_status,
            start_time=model.start_time,
            end_time=model.end_time,
            time_taken=model.time_taken,
            col_names=model.col_names,
            total_docs=model.total_docs,
            failed_docs=model.failed_docs,
            skipped_docs=model.skipped_docs,
            docs_completed=model.docs_completed,
            node_metadata=model.node_metadata,
            docs_completed_count=len(model.docs_completed),
            error=model.error,
        )
        new_instance.id = model.node_id
        return new_instance

    id: str = Field(title="id", description="ID of the node", min_length=36, max_length=36)
    name: str = Field(title="name", description="Name of the node")
    node_status: str = Field(
        "Completed",
        title="Node status",
        description="Status of the execution of the node",
        min_length=1,
        max_length=100,
        pattern=node_status_pattern,
    )
    start_time: int = Field(
        default=0,
        title="Start Time of the Node Execution",
        description="Epoch timestamp (in seconds) indicating when the node execution started.",
    )
    end_time: int = Field(
        default=0,
        title="End Time of the Node Execution",
        description="Epoch timestamp (in seconds) indicating when the node execution ended.",
    )
    time_taken: int = Field(default=0, title="Time taken", description="Time taken by the node")
    col_names: list[str] = Field(
        default_factory=list,
        title="Column names",
        description="List of column names resulted from the node",
        min_length=0,
        max_length=100,
    )
    total_docs: list[str] | None = Field(
        default_factory=list,
        title="Total Documents",
        description="List of total documents processed",
    )
    failed_docs: list[str] | None = Field(
        default_factory=list,
        title="Failed Documents",
        description="List of failed documents",
    )
    skipped_docs: list[str] | None = Field(
        default_factory=list,
        title="Skipped Documents",
        description="List of skipped documents",
    )
    docs_completed: list[str] | None = Field(
        default_factory=list,
        title="Completed Documents",
        description="List of successfully completed documents",
    )
    docs_completed_count: int = Field(
        default=0,
        title="Number of documents processed",
        description="Number of documents processed by the node",
    )
    node_metadata: dict | None = Field(default=None, title="Node Metadata of the Operator")
    # increasing the max limit of the errors field to 50000 to accommodate larger error messages,
    error: str = Field(
        default="",
        title="Error message",
        description="The error message",
        min_length=0,
        max_length=50000,
        pattern=message_pattern,
    )

    class Config:
        json_schema_extra = {
            "description": "This model defines the statistics of a node execution.",
            "example": {
                "id": "62e29618-7942-4143-9ce4-ffe5744f4e88",
                "name": "Ingest",
                "node_status": "Completed",
                "time_taken": 100,
                "col_names": ["col1", "col2"],
                "docs_completed": 20,
            },
        }
