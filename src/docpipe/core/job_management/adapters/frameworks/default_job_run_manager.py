"""
DefaultJobRunManager - Default framework adapter for job execution
This adapter provides a simple, synchronous job execution framework
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from docpipe.core.constants.constants import DocpipeConstants, ExecutionStatus
from docpipe.core.job_management.domain.ports import JobRunManager, JobStatsService
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger()


class DefaultJobRunManager(JobRunManager):
    """
    Default job execution framework adapter.

    Uses JobStatsService (which internally uses configured JobStatsStore from YAML).
    Storage is handled by JobStatsStore (pickle, postgresql, redis, etc.)
    configured in docling-pipelines-config.yaml

    Features:
    - Delegates to JobStatsService for all storage operations
    - Synchronous execution model
    - Simple status management

    """

    def __init__(self, *, job_stats_service: JobStatsService):
        """
        Initialize default job run manager.

        Args:
            job_stats_service: Job statistics service (uses configured store from YAML)
        """
        self.job_stats_service = job_stats_service

    def create_job_run(self, *, job_id: str, job_config: dict[str, Any]) -> dict[str, Any]:
        """
        Create job run using default framework behavior.

        Args:
            job_id: Flow/job identifier
            job_config: Flow configuration and parameters

        Returns:
            Job run metadata including generated job_run_id

        Raises:
            ValueError: If job_id or configuration is invalid
        """
        if not job_id:
            raise ValueError("job_id is required")
        if job_config is None:
            raise ValueError("job_config is required")

        job_run_id = str(uuid.uuid4())
        logger.info(f"Creating job run: {job_run_id}")

        logger.info(f"Created job run in default framework: job_id={job_id}, job_run_id={job_run_id}")

        return {
            DocpipeConstants.JOB_ID: job_id,
            DocpipeConstants.JOB_RUN_ID: job_run_id,
            DocpipeConstants.STATUS: ExecutionStatus.PENDING.value,
            "created_at": datetime.now(UTC).replace(tzinfo=None).isoformat(),
        }

    def get_job_run(self, *, job_id: str, job_run_id: str) -> dict[str, Any]:
        """
        Retrieve job run via JobStatsService.

        Args:
            job_id: Flow/job identifier
            job_run_id: Job run identifier

        Returns:
            Job run information from configured storage

        Raises:
            ValueError: If job_run_id not found
        """
        # Get from JobStatsService (which uses configured JobStatsStore)
        job_stats = self.job_stats_service.get_job_run_stats(job_run_id=job_run_id)

        if not job_stats:
            raise ValueError(f"Job run not found: {job_run_id}")

        return job_stats.model_dump()

    def update_job_run_status(
        self, *, job_run_id: str, status: str, job_run_stats: dict[str, Any] | None = None
    ) -> None:
        """
        Update job run status via JobStatsService.

        Args:
            job_run_id: Job run identifier
            status: New status (RUNNING, COMPLETED, FAILED, CANCELED)
            job_run_stats: Optional stats dictionary with any key-value pairs
        """
        # Get current job stats
        job_stats = self.job_stats_service.get_job_run_stats(job_run_id=job_run_id)

        if not job_stats:
            logger.warning(f"Job run not found for status update: {job_run_id}")
            return

        # Protect terminal states from being overwritten by delayed subflow updates
        from docpipe.core.constants.constants import TERMINAL_JOB_STATUSES

        # Convert to string just in case, though StrEnum handles this
        current_status = str(job_stats.status) if job_stats.status else ""
        new_status = str(status)

        if current_status in TERMINAL_JOB_STATUSES and new_status not in TERMINAL_JOB_STATUSES:
            logger.info(
                f"Ignoring status update to {new_status} because job run {job_run_id} "
                f"is already in terminal state {current_status}"
            )
            return

        # Update status
        job_stats.status = status
        job_stats.heartbeat_timestamp = int(datetime.now(UTC).timestamp())

        # Merge additional stats if provided
        if job_run_stats:
            for key, value in job_run_stats.items():
                if hasattr(job_stats, key):
                    setattr(job_stats, key, value)

        # Store updated stats via JobStatsService
        self.job_stats_service.store_job_stats(job_stats=job_stats)

        logger.info(f"Updated job run status: job_run_id={job_run_id}, status={status}")

    def cancel_job_run(self, *, job_run_id: str) -> None:
        """
        Cancel job run framework resources.

        Note: Job cancellation is handled by JobManagementService layer.
        This method is for framework-specific cleanup only.

        Args:
            job_run_id: Job run identifier

        Raises:
            JobRunNotFoundException: If job run does not exist
            JobRunOperationFailedException: If cancellation fails for other reasons
        """
        # Framework-specific cancellation would go here
        # Job cancellation is handled by the service layer already for default job run manager
        logger.info(f"Canceled job run framework resources: job_run_id={job_run_id}")

    def delete_job_run(self, *, job_run_id: str) -> None:
        """
        Delete job run framework resources.

        Note: Job stats deletion is handled by JobManagementService layer.
        This method is for framework-specific cleanup only.

        Args:
            job_run_id: Job run identifier

        Raises:
            JobRunNotFoundException: If job run does not exist
            JobRunOperationFailedException: If deletion fails for other reasons
        """
        # Framework-specific cleanup would go here
        # Job stats deletion is handled by the service layer already for default job run manager
        logger.info(f"Deleted job run framework resources: job_run_id={job_run_id}")
