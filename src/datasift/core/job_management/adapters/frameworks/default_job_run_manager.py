"""
DefaultJobRunManager - Default framework adapter for job execution
This adapter provides a simple, synchronous job execution framework
"""

import uuid
from datetime import datetime
from typing import Any

from datasift.core.constants.constants import DatasiftConstants, ExecutionStatus
from datasift.core.job_management.domain.ports import JobRunManager, JobStatsService
from datasift.utils.infrastructure.logging import get_logger

logger = get_logger()


class DefaultJobRunManager(JobRunManager):
    """
    Default job execution framework adapter.

    Uses JobStatsService (which internally uses configured JobStatsStore from YAML).
    Storage is handled by JobStatsStore (pickle, postgresql, redis, etc.)
    configured in datasift-config.yaml

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
            DatasiftConstants.JOB_ID: job_id,
            DatasiftConstants.JOB_RUN_ID: job_run_id,
            DatasiftConstants.STATUS: ExecutionStatus.PENDING.value,
            "created_at": datetime.utcnow().isoformat(),
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

        # Update status
        job_stats.status = status
        job_stats.heartbeat_timestamp = int(datetime.utcnow().timestamp())

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
        Cancel job run via JobStatsService.

        Args:
            job_run_id: Job run identifier

        Raises:
            JobRunNotFoundException: If job run does not exist
            JobRunOperationFailedException: If cancellation fails for other reasons
        """
        try:
            # Use JobStatsService to request cancellation
            self.job_stats_service.request_cancel_job(job_run_id=job_run_id)
            logger.info(f"Canceled job run: job_run_id={job_run_id}")
        except Exception as e:
            from datasift.exceptions.datasift_exceptions import DatasiftException, JobRunOperationFailedException

            if isinstance(e, DatasiftException):
                raise
            logger.error(f"Failed to cancel job run {job_run_id}: {e}")
            raise JobRunOperationFailedException(
                message=f"Failed to cancel job run {job_run_id}: {e!s}", job_run_id=job_run_id, operation="cancel"
            ) from e

    def delete_job_run(self, *, job_run_id: str) -> None:
        """
        Delete job run via JobStatsService.

        Args:
            job_run_id: Job run identifier

        Raises:
            JobRunNotFoundException: If job run does not exist
            JobRunOperationFailedException: If deletion fails for other reasons
        """
        try:
            # Use JobStatsService to delete job run
            self.job_stats_service.request_delete_job_run(job_run_id=job_run_id)
            logger.info(f"Deleted job run: job_run_id={job_run_id}")
        except Exception as e:
            from datasift.exceptions.datasift_exceptions import DatasiftException, JobRunOperationFailedException

            if isinstance(e, DatasiftException):
                raise
            logger.error(f"Failed to delete job run {job_run_id}: {e}")
            raise JobRunOperationFailedException(
                message=f"Failed to delete job run {job_run_id}: {e!s}", job_run_id=job_run_id, operation="delete"
            ) from e
