"""
Data Access Layer for NodeStats model.

Provides CRUD operations for node-level statistics with batch support.
"""

from sqlalchemy import text
from sqlmodel import select

from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.job_management.domain.models import NodeStatsFields
from docpipe.exceptions.docpipe_exceptions import PostgresOperationException
from docpipe.utils.infrastructure.logging import get_logger

from .base_dao import BaseDAO

logger = get_logger()


class NodeStatsDAL:
    """
    Data Access Layer for NodeStatsModel model.

    Handles persistence and retrieval of node-level statistics with micro-batching support.
    """

    def __init__(self, *, session_factory, model=None):
        """
        Initialize NodeStatsDAL with session factory.

        Args:
            session_factory: SQLAlchemy session factory
            model: Optional SQLModel class to use instead of the default
        """
        from ..models import NodeStatsModel

        self._dao = BaseDAO(model=model or NodeStatsModel, session_factory=session_factory)

    def upsert(self, *, node_stat) -> None:
        """
        Insert or update node stats using PostgreSQL's ON CONFLICT.

        Args:
            node_stat: Node stats model instance

        Raises:
            PostgresOperationException: If upsert operation fails
        """
        try:
            if node_stat.batch_id is None:
                # Aggregated record - use partial index for batch_id IS NULL
                self._dao.upsert_with_conflict(
                    obj=node_stat,
                    index_elements=[NodeStatsFields.NODE_ID, "job_run_id"],
                    where_clause=text("batch_id IS NULL"),
                    update_fields=[
                        NodeStatsFields.NAME,
                        NodeStatsFields.NODE_STATUS,
                        NodeStatsFields.START_TIME,
                        NodeStatsFields.END_TIME,
                        NodeStatsFields.TIME_TAKEN,
                        NodeStatsFields.COL_NAMES,
                        NodeStatsFields.TOTAL_DOCS,
                        NodeStatsFields.FAILED_DOCS,
                        NodeStatsFields.SKIPPED_DOCS,
                        NodeStatsFields.DOCS_COMPLETED,
                        OperatorConstants.Metadata.NODE_METADATA,
                        NodeStatsFields.ERROR,
                    ],
                )
            else:
                # Batch record - use full index including batch_id
                self._dao.upsert_with_conflict(
                    obj=node_stat,
                    index_elements=[NodeStatsFields.NODE_ID, "job_run_id", NodeStatsFields.BATCH_ID],
                    where_clause=text("batch_id IS NOT NULL"),
                    update_fields=[
                        NodeStatsFields.NAME,
                        NodeStatsFields.NODE_STATUS,
                        NodeStatsFields.START_TIME,
                        NodeStatsFields.END_TIME,
                        NodeStatsFields.TIME_TAKEN,
                        NodeStatsFields.COL_NAMES,
                        NodeStatsFields.TOTAL_DOCS,
                        NodeStatsFields.FAILED_DOCS,
                        NodeStatsFields.SKIPPED_DOCS,
                        NodeStatsFields.DOCS_COMPLETED,
                        OperatorConstants.Metadata.NODE_METADATA,
                        NodeStatsFields.ERROR,
                    ],
                )
        except Exception as e:
            logger.error(f"Failed to upsert node stats: {e}")
            raise PostgresOperationException(
                message=f"Failed to upsert node stats: {e}", operation="upsert", table="node_stats"
            ) from e

    def bulk_insert(self, *, node_stats: list) -> None:
        """
        Bulk insert multiple node stats records.

        Args:
            node_stats: List of node stats model instances

        Raises:
            PostgresOperationException: If bulk insert fails
        """
        if not node_stats:
            return

        try:
            self._dao.bulk_add_no_refresh(objs=node_stats)
        except Exception as e:
            logger.error(f"Failed to bulk insert node stats: {e}")
            raise PostgresOperationException(
                message=f"Failed to bulk insert node stats: {e}", operation="bulk_insert", table="node_stats"
            ) from e

    def get_node_stats_by_run_batch(self, *, node_id: str, job_run_id: str, batch_id: str | None = None):
        """
        Get node stats by node_id, job_run_id, and batch_id.

        Args:
            node_id: Node identifier
            job_run_id: Job run identifier
            batch_id: Batch identifier (None for aggregated stats)

        Returns:
            Model instance if found, None otherwise

        Raises:
            PostgresOperationException: If query fails
        """
        try:
            model = self._dao.model
            query = select(model).where(model.node_id == node_id).where(model.job_run_id == job_run_id)

            if batch_id is None:
                query = query.where(model.batch_id.is_(None))  # type: ignore[union-attr]
            else:
                query = query.where(model.batch_id == batch_id)

            return self._dao.get_first_by_query(query=query)
        except Exception as e:
            logger.error(f"Failed to get node stats: {e}")
            raise PostgresOperationException(
                message=f"Failed to get node stats: {e}", operation="get", table="node_stats"
            ) from e

    def get_aggregated_node_stats(self, *, job_run_id: str):
        """
        Get all aggregated node stats (batch_id IS NULL) for a job run.

        Args:
            job_run_id: Job run identifier

        Returns:
            List of model instances with batch_id=NULL

        Raises:
            PostgresOperationException: If query fails
        """
        try:
            model = self._dao.model
            query = (
                select(model).where(model.job_run_id == job_run_id).where(model.batch_id.is_(None))  # type: ignore[union-attr]
            )
            return self._dao.get_by_query(query=query)
        except Exception as e:
            logger.error(f"Failed to get aggregated node stats: {e}")
            raise PostgresOperationException(
                message=f"Failed to get aggregated node stats: {e}", operation="get_aggregated", table="node_stats"
            ) from e

    def get_batch_node_stats(self, *, job_run_id: str):
        """
        Get all batch-level node stats (batch_id IS NOT NULL) for a job run.

        Args:
            job_run_id: Job run identifier

        Returns:
            List of model instances with batch_id NOT NULL

        Raises:
            PostgresOperationException: If query fails
        """
        try:
            model = self._dao.model
            query = (
                select(model).where(model.job_run_id == job_run_id).where(model.batch_id.isnot(None))  # type: ignore[union-attr]
            )
            return self._dao.get_by_query(query=query)
        except Exception as e:
            logger.error(f"Failed to get batch node stats: {e}")
            raise PostgresOperationException(
                message=f"Failed to get batch node stats: {e}", operation="get_batch", table="node_stats"
            ) from e

    def get_all_node_stats(self, *, job_run_id: str):
        """
        Get ALL node stats (both batch and non-batch) for a job run.

        Args:
            job_run_id: Job run identifier

        Returns:
            List of all model instances for the job run

        Raises:
            PostgresOperationException: If query fails
        """
        try:
            model = self._dao.model
            query = select(model).where(model.job_run_id == job_run_id)
            return self._dao.get_by_query(query=query)
        except Exception as e:
            logger.error(f"Failed to get all node stats: {e}")
            raise PostgresOperationException(
                message=f"Failed to get all node stats: {e}", operation="get_all", table="node_stats"
            ) from e

    def has_batch_records(self, *, job_run_id: str) -> bool:
        """
        Check if a job has batch records (micro-batching enabled).

        Args:
            job_run_id: Job run identifier

        Returns:
            True if job has batch records, False otherwise
        """
        try:
            model = self._dao.model
            condition = (
                (model.job_run_id == job_run_id) & (model.batch_id.isnot(None))  # type: ignore[union-attr]
            )
            return self._dao.exists(condition=condition)
        except Exception:
            return False
