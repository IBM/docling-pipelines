"""
PostgreSQL-based implementation of IncrementalMetadataStore.

Provides persistent storage for incremental metadata using PostgreSQL database,
offering ACID compliance and scalability for production environments.

Features:
- Persistent storage in PostgreSQL database
- ACID transactions for data consistency
- Efficient querying with indexes
- Separate schema for isolation from job stats
"""

from typing import Any, cast

from sqlalchemy import Column, String, Table, delete, text
from sqlmodel import select

from docpipe.core.incremental_metadata.domain import (
    IncrementalMetadataRecord,
    IncrementalMetadataStore,
)
from docpipe.core.job_management.adapters.stores.postgres.database import (
    create_postgres_engine,
    create_session_factory,
    get_postgres_connection_string,
)
from docpipe.exceptions.docpipe_exceptions import (
    FlowExecutionFailedException,
    JobStatsStoreInitializationException,
)
from docpipe.utils.infrastructure.logging import get_logger

from .models import IncrementalMetadataPostgresModel

logger = get_logger("INCREMENTAL_METADATA_POSTGRES")


class PostgresIncrementalMetadataStore(IncrementalMetadataStore):
    """
    PostgreSQL-based storage adapter for incremental metadata.

    Stores metadata in PostgreSQL database with separate schema:
    Schema: incremental_metadata (configurable)
    Table: inc_update_metadata

    Primary Key: (job_id, doc_id)

    Configuration:
        Set environment variables or provide config dict:
        - DOCPIPE_POSTGRES_HOST (default: localhost)
        - DOCPIPE_POSTGRES_PORT (default: 5432)
        - DOCPIPE_POSTGRES_DB (default: docpipe)
        - DOCPIPE_POSTGRES_USER (default: docpipe_user)
        - DOCPIPE_POSTGRES_PASSWORD (required)
        - DOCPIPE_INCREMENTAL_POSTGRES_SCHEMA (default: incremental_metadata)
    """

    def __init__(self, *, config: dict[str, Any] | None = None):
        """
        Initialize PostgreSQL incremental metadata store.

        Args:
            config: Optional configuration dict with PostgreSQL connection settings

        Raises:
            JobStatsStoreInitializationException: If initialization fails
        """
        self.config = config or {}

        # Log the config keys being used (without password value)
        config_keys = list(self.config.keys())
        logger.debug(f"PostgresIncrementalMetadataStore config keys: {config_keys}")

        # Wrap config in expected structure for get_postgres_connection_string
        # The function expects config["postgres"]["password"], etc.
        wrapped_config = {"postgres": self.config}

        # Get connection string from config or environment
        connection_string = get_postgres_connection_string(config=wrapped_config)
        if not connection_string:
            raise JobStatsStoreInitializationException(
                message="PostgreSQL connection not configured for incremental metadata. "
                "Set password in config or DOCPIPE_POSTGRES_PASSWORD environment variable.",
                store_type="postgres",
            )

        try:
            # Create engine and session factory
            self._engine = create_postgres_engine(connection_string=connection_string, config=wrapped_config)
            self._session_factory = create_session_factory(engine=self._engine)

            # Create schema and incremental metadata table if they don't exist
            schema_name = self.config.get("schema", "incremental_metadata")
            incremental_table = cast(Table, IncrementalMetadataPostgresModel.__table__)  # type: ignore[attr-defined]
            incremental_table.schema = schema_name

            with self._engine.begin() as connection:
                connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))

            incremental_table.create(self._engine, checkfirst=True)

            logger.info(
                f"PostgresIncrementalMetadataStore initialized successfully "
                f"(schema: {schema_name}, table: {incremental_table.name})"
            )

        except JobStatsStoreInitializationException:
            raise
        except Exception as e:
            logger.error(f"Failed to initialize PostgresIncrementalMetadataStore: {e}")
            raise JobStatsStoreInitializationException(
                message=f"PostgreSQL initialization failed: {e}", store_type="postgres"
            ) from e

    def get_processed_docs(self, *, job_id: str) -> dict[str, Any]:
        """Retrieve processed document IDs with modification times (non-deleted only)."""
        try:
            with self._session_factory() as session:
                rows = (
                    session.execute(
                        select(IncrementalMetadataPostgresModel).where(
                            IncrementalMetadataPostgresModel.job_id == job_id,
                            IncrementalMetadataPostgresModel.deleted == False,  # noqa: E712
                        )
                    )
                    .scalars()
                    .all()
                )
                result = {row.doc_id: row.modified_time for row in rows}
                logger.debug(f"Retrieved {len(result)} processed docs for job_id={job_id}")
                return result

        except Exception as exc:
            raise FlowExecutionFailedException(f"Failed to retrieve processed docs for job_id={job_id}: {exc}") from exc

    def upsert_records(self, *, job_id: str, job_run_id: str, records: list[IncrementalMetadataRecord]) -> None:
        """Insert or update incremental metadata records."""
        if not records:
            return

        try:
            with self._session_factory() as session:
                for record in records:
                    # Check if record exists
                    model = session.get(IncrementalMetadataPostgresModel, (job_id, record.doc_id))

                    if model is None:
                        # Insert new record
                        model = IncrementalMetadataPostgresModel(job_id=job_id, doc_id=record.doc_id)

                    # Update fields
                    model.name = record.name
                    model.modified_time = record.modified_time
                    model.job_run_id = job_run_id
                    model.deleted = False

                    session.add(model)

                session.commit()
                logger.info(f"Upserted {len(records)} records for job_id={job_id}")

        except Exception as exc:
            raise FlowExecutionFailedException(f"Failed to upsert records for job_id={job_id}: {exc}") from exc

    def get_soft_deleted_doc_ids(self, *, job_id: str) -> set[str]:
        """Retrieve document IDs marked as soft-deleted."""
        try:
            with self._session_factory() as session:
                rows = (
                    session.execute(
                        select(IncrementalMetadataPostgresModel.doc_id).where(
                            IncrementalMetadataPostgresModel.job_id == job_id,
                            IncrementalMetadataPostgresModel.deleted == True,  # noqa: E712
                        )
                    )
                    .scalars()
                    .all()
                )
                result = set(rows)
                logger.debug(f"Retrieved {len(result)} soft-deleted docs for job_id={job_id}")
                return result

        except Exception as exc:
            raise FlowExecutionFailedException(
                f"Failed to retrieve soft-deleted docs for job_id={job_id}: {exc}"
            ) from exc

    def mark_missing_docs_as_deleted(self, *, job_id: str, doc_ids: list[str]) -> set[str]:
        """Mark documents as soft-deleted if not in provided list."""
        try:
            current_doc_ids = set(doc_ids)

            with self._session_factory() as session:
                # Get all non-deleted records for this job
                rows = (
                    session.execute(
                        select(IncrementalMetadataPostgresModel).where(
                            IncrementalMetadataPostgresModel.job_id == job_id,
                            IncrementalMetadataPostgresModel.deleted == False,  # noqa: E712
                        )
                    )
                    .scalars()
                    .all()
                )

                # Find documents to mark as deleted
                deleted_ids = {row.doc_id for row in rows if row.doc_id not in current_doc_ids}

                # Mark as deleted
                for row in rows:
                    if row.doc_id in deleted_ids:
                        row.deleted = True
                        session.add(row)

                session.commit()

                if deleted_ids:
                    logger.info(f"Marked {len(deleted_ids)} docs as deleted for job_id={job_id}")

                return deleted_ids

        except Exception as exc:
            raise FlowExecutionFailedException(
                f"Failed to mark missing docs as deleted for job_id={job_id}: {exc}"
            ) from exc

    def delete_docs(self, *, job_id: str, doc_ids: list[str]) -> None:
        """Permanently delete metadata records for specified documents."""
        if not doc_ids:
            return

        try:
            with self._session_factory() as session:
                session.execute(
                    delete(IncrementalMetadataPostgresModel).where(
                        Column("job_id", String) == job_id,
                        Column("doc_id", String).in_(doc_ids),
                    )
                )
                session.commit()
                logger.info(f"Deleted {len(doc_ids)} docs for job_id={job_id}")

        except Exception as exc:
            raise FlowExecutionFailedException(f"Failed to delete docs for job_id={job_id}: {exc}") from exc

    def clear(self, *, job_id: str) -> None:
        """Clear all incremental metadata for a specific job."""
        try:
            with self._session_factory() as session:
                session.execute(
                    delete(IncrementalMetadataPostgresModel).where(
                        Column("job_id", String) == job_id,
                    )
                )
                session.commit()
                logger.info(f"Cleared all metadata for job_id={job_id}")

        except Exception as exc:
            raise FlowExecutionFailedException(f"Failed to clear metadata for job_id={job_id}: {exc}") from exc
