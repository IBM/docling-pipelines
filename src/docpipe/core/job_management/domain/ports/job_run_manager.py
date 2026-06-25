"""
JobRunManager Port - Interface for job execution frameworks
See DefaultJobRunManager for a reference implementation.
"""

from abc import ABC, abstractmethod
from typing import Any


class JobRunManager(ABC):
    """
    Port interface for pluggable job execution frameworks.

    Users can implement this interface to integrate their own job execution systems.
    The framework handles job lifecycle management: creation, monitoring, cancellation,
    and deletion.

    Default Implementation:
    - DefaultJobRunManager: Internal execution using JobTracker

    Custom Implementation Examples (User's Choice):
    - KubernetesJobRunManager: Execute jobs in Kubernetes pods
    - CeleryJobRunManager: Distribute jobs via Celery task queue
    - AirflowJobRunManager: Trigger Airflow DAGs
    - BatchJobRunManager: Submit to AWS Batch or similar

    Responsibilities:
    - Create job run records in your execution system
    - Retrieve job run information and status
    - Update job run status (for async/external executors)
    - Cancel running jobs
    - Delete job run records
    """

    @abstractmethod
    def create_job_run(self, *, job_id: str, job_config: dict[str, Any]) -> dict[str, Any]:
        """
        Create job run in framework's system.

        Implement this method to create a job run in your execution framework.

        Args:
            job_id: Flow/job identifier
            job_config: Flow configuration and parameters

        Returns:
            Job run metadata from framework, including generated job_run_id

        Raises:
            ValueError: If job_id or configuration is invalid
            RuntimeError: If framework communication fails
        """
        pass

    @abstractmethod
    def get_job_run(self, *, job_id: str, job_run_id: str) -> dict[str, Any]:
        """
        Retrieve job run information from framework.

        Implement this method to fetch job run details from your execution framework.

        Args:
            job_id: Flow/job identifier
            job_run_id: Job run identifier

        Returns:
            Job run information from framework

        Raises:
            ValueError: If job_run_id not found
        """
        pass

    @abstractmethod
    def update_job_run_status(
        self, *, job_run_id: str, status: str, job_run_stats: dict[str, Any] | None = None
    ) -> None:
        """
        Update job run status (called from external executor).

        Implement this method to handle status updates from your execution framework.
        This is critical for external frameworks to report back completion status.

        Args:
            job_run_id: Job run identifier
            status: New status (RUNNING, COMPLETED, FAILED, CANCELED)
            job_run_stats: Optional stats dictionary with any key-value pairs
        """
        pass

    @abstractmethod
    def cancel_job_run(self, *, job_run_id: str) -> None:
        """
        Cancel job run in framework.

        Implement this method to cancel a running job in your execution framework.

        Args:
            job_run_id: Job run identifier

        Raises:
            JobRunNotFoundException: If job run does not exist
            JobRunOperationFailedException: If cancellation fails for other reasons
        """
        pass

    @abstractmethod
    def delete_job_run(self, *, job_run_id: str) -> None:
        """
        Delete job run from framework.

        Implement this method to delete job run records from your execution framework.

        Args:
            job_run_id: Job run identifier

        Raises:
            JobRunNotFoundException: If job run does not exist
            JobRunOperationFailedException: If deletion fails for other reasons
        """
        pass
