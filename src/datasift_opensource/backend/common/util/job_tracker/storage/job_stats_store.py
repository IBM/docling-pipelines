from abc import ABC, abstractmethod
from typing import Any
from datasift_opensource.backend.common.util.job_tracker.model.models import JobStatsDto, NodeStatsDto
from datasift_opensource.backend.common.util.constants import ExecutionStatus
from datasift_opensource.backend.common.util.log import get_logger

logger = get_logger()


class JobStatsStore(ABC):
    """
    Abstract base class for storing and retrieving job and node statistics.

    This class defines the interface for implementations that persist and retrieve
    job-level and node-level statistics, including support for merging stats and
    determining job execution status.
    """

    @staticmethod
    def _merge_status(old_stat: ExecutionStatus, new_stat: ExecutionStatus) -> str:
        """
        Merge two execution statuses and return the one that is closer to failure.

        Args:
            old_stat (ExecutionStatus): The previous execution status.
            new_stat (ExecutionStatus): The new execution status to compare.

        Returns:
            str: The execution status that is considered more severe (lower code).
        """
        status_codes = {
            ExecutionStatus.FAILED: 1,
            ExecutionStatus.COMPLETED_WITH_ERRORS: 2,
            ExecutionStatus.COMPLETED_WITH_WARNINGS: 3,
            ExecutionStatus.CANCELED: 4,
            ExecutionStatus.CANCELING: 5,
            ExecutionStatus.PAUSED: 6,
            ExecutionStatus.RESUMING: 7,
            ExecutionStatus.RUNNING: 8,
            ExecutionStatus.STARTING: 9,
            ExecutionStatus.QUEUED: 10,
            ExecutionStatus.COMPLETED: 1000
        }
        if status_codes[old_stat] < status_codes[new_stat]:
            return old_stat
        else:
            return new_stat

    @staticmethod
    def _roll_up_stats(old_stats: JobStatsDto, new_stats: JobStatsDto) -> JobStatsDto:
        """
        Merge two JobStatsDto objects, updating document counts and status.

        Args:
            old_stats (JobStatsDto): The existing job statistics.
            new_stats (JobStatsDto): The new job statistics to merge.

        Returns:
            JobStatsDto: The merged job statistics.
        """
        if not old_stats:
            return new_stats

        if old_stats.job_id != new_stats.job_id:
            logger.warning(f"Job ids not matching: {old_stats.job_id}, {new_stats.job_id}")

        if old_stats.job_run_id != new_stats.job_run_id:
            logger.warning(f"Job run ids not matching: {old_stats.job_run_id}, {new_stats.job_run_id}")

        new_stats.status = JobStatsStore._merge_status(old_stats.status, new_stats.status)
        new_stats.processed_docs += old_stats.processed_docs
        new_stats.skipped_docs += old_stats.skipped_docs
        new_stats.failed_docs += old_stats.failed_docs

        return new_stats

    @abstractmethod
    def store_job_stats(self, job_stats: JobStatsDto, merge=True):
        """
        Store job-level statistics.

        Args:
            job_stats (JobStatsDto): The job statistics to store.
            merge (bool): Whether to merge with existing stats if present.
        """
        pass

    @abstractmethod
    def get_job_stats(self, job_run_id: str) -> JobStatsDto:
        """
        Retrieve job-level statistics for a given job run ID.

        Args:
            job_run_id (str): The unique identifier for the job run.

        Returns:
            JobStatsDto: The retrieved job statistics.
        """
        pass

    @abstractmethod
    def get_node_stats(self, job_id: str, job_run_id: str) -> dict[str, NodeStatsDto]:
        """
        Retrieve node-level statistics for a given job ID and job run ID.

        Args:
            job_id (str): The job identifier.
            job_run_id (str): The job run identifier.

        Returns:
            dict[str, NodeStatsDto]: A dictionary mapping node IDs to their statistics.
        """
        pass

    @abstractmethod
    def store_node_stats(self, job_id: str, job_run_id: str, node_stats: NodeStatsDto):
        """
        Store node-level statistics for a specific job and job run.

        Args:
            job_id (str): The job identifier.
            job_run_id (str): The job run identifier.
            node_stats (NodeStatsDto): The node statistics to store.
        """
        pass

    @abstractmethod
    def atomic_increment_fields(self, *, job_run_id: str, increments: dict, updates: dict | None = None):
        """
        Atomically increment numeric fields and update other fields.
        
        Args:
            job_run_id: The job run ID to update
            increments: Dict mapping metric names to increment values
            updates: Dict of metadata fields to update
        """
        pass

    @staticmethod
    def get_job_stats_store():
        """
        Factory method to retrieve the appropriate JobStatsStore implementation
        based on session configuration.

        Returns:
            JobStatsStore: An instance of PostgresJobStatsStore or PickleJobStatsStore.
        """
        from .pickle_job_stats_store import PickleJobStatsStore
        # from .postgres_job_stats_store import PostgresJobStatsStore

        # if JobStatsStore._is_cmd_line_mode():
        return PickleJobStatsStore()
        # else:
        #     return PostgresJobStatsStore()

    @staticmethod
    def _is_cmd_line_mode() -> bool:
        from datasift_opensource.backend.common.models.session_info import get_session_info, SessionInfo
        
        session_info: SessionInfo = get_session_info()
        orchestrator: Any | None = session_info.orchestrator
        return orchestrator.__class__.__name__ == "CommandLineOrchestrator"
