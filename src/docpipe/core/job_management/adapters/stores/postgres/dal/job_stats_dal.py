"""
Data Access Layer for JobRunStats model.

Provides CRUD operations for job-level statistics.
"""

from sqlmodel import select

from docpipe.exceptions.docpipe_exceptions import PostgresOperationException
from docpipe.utils.infrastructure.logging import get_logger

from ..models import JobStatsModel
from .base_dao import BaseDAO

logger = get_logger()


class JobStatsDAL:
    """
    Data Access Layer for JobStatsModel model.

    Handles persistence and retrieval of job-level statistics.
    """

    def __init__(self, *, session_factory):
        """
        Initialize JobStatsDAL with session factory.

        Args:
            session_factory: SQLAlchemy session factory
        """
        self._dao = BaseDAO(model=JobStatsModel, session_factory=session_factory)

    def upsert(self, *, job_run_stats: JobStatsModel) -> None:
        """
        Insert or update job run stats.

        Args:
            job_run_stats: JobStatsModel model instance

        Raises:
            PostgresOperationException: If upsert operation fails
        """
        try:
            self._dao.upsert_no_refresh(obj=job_run_stats)
        except Exception as e:
            logger.error(f"Failed to upsert job run stats: {e}")
            raise PostgresOperationException(
                message=f"Failed to upsert job run stats: {e}", operation="upsert", table="job_run_stats"
            ) from e

    def get_by_job_run_id(self, *, job_run_id: str) -> JobStatsModel | None:
        """
        Get job run stats by job_run_id.

        Args:
            job_run_id: Job run identifier

        Returns:
            JobStatsModel if found, None otherwise

        Raises:
            PostgresOperationException: If retrieval operation fails
        """
        try:
            return self._dao.get_by_id(id=job_run_id)
        except Exception as e:
            logger.error(f"Failed to retrieve job run stats for {job_run_id}: {e}")
            raise PostgresOperationException(
                message=f"Failed to retrieve job run stats for {job_run_id}: {e}",
                operation="get_by_id",
                table="job_run_stats",
            ) from e

    def delete_job_stats(self, *, job_run_id: str) -> int:
        """
        Delete job run stats by job_run_id.

        Args:
            job_run_id: Job run identifier

        Returns:
            Number of rows deleted

        Raises:
            PostgresOperationException: If delete operation fails
        """
        try:
            return self._dao.delete_by_query(condition=JobStatsModel.job_run_id == job_run_id)
        except Exception as e:
            logger.error(f"Failed to delete job run stats for {job_run_id}: {e}")
            raise PostgresOperationException(
                message=f"Failed to delete job run stats for {job_run_id}: {e}",
                operation="delete",
                table="job_run_stats",
            ) from e

    def atomic_increment_fields(
        self, *, job_run_id: str, increments: dict, updates: dict | None = None, jsonb_merges: dict | None = None
    ) -> None:
        """
        Atomically increment numeric fields and update others.

        Args:
            job_run_id: Job run identifier
            increments: Fields to increment {field_name: increment_value}
            updates: Fields to update {field_name: new_value}
            jsonb_merges: JSONB fields to merge {field_name: merge_dict}

        Raises:
            PostgresOperationException: If atomic update fails
        """
        try:
            condition = JobStatsModel.job_run_id == job_run_id
            self._dao.atomic_increment_fields(
                condition=condition, increments=increments, updates=updates, jsonb_merges=jsonb_merges
            )
        except Exception as e:
            logger.error(f"Failed to atomically increment fields for {job_run_id}: {e}")
            raise PostgresOperationException(
                message=f"Failed to atomically increment fields for {job_run_id}: {e}",
                operation="atomic_increment",
                table="job_run_stats",
            ) from e

    def list_job_runs(
        self,
        *,
        job_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[JobStatsModel]:
        """
        List job runs with optional filters.

        Args:
            job_id: Optional filter by job_id
            status: Optional filter by status
            limit: Maximum number of results

        Returns:
            List of JobStatsModel matching filters

        Raises:
            PostgresOperationException: If list operation fails
        """
        try:
            query = select(JobStatsModel)

            if job_id:
                query = query.where(JobStatsModel.job_id == job_id)
            if status:
                query = query.where(JobStatsModel.status == status)

            query = query.order_by(JobStatsModel.start_time.desc()).limit(limit)  # type: ignore[attr-defined]

            return self._dao.get_by_query(query=query)
        except Exception as e:
            logger.error(f"Failed to list jobs: {e}")
            raise PostgresOperationException(
                message=f"Failed to list jobs: {e}", operation="list", table="job_run_stats"
            ) from e
