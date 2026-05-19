from __future__ import annotations

import json
import os
import shutil
from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from threading import RLock
from typing import Any

from filelock import FileLock, Timeout
from sqlalchemy import BIGINT, Boolean, Column, String, delete, text
from sqlmodel import Field, SQLModel, select

from datasift.core.constants import DatasiftConfigKeys, DatasiftConstants, EnvironmentVariables
from datasift.core.job_management.adapters.config.job_management_factory import (
    StorageBackend,
    get_default_factory,
)
from datasift.core.job_management.adapters.stores.postgres.database import (
    create_postgres_engine,
    create_session_factory,
    get_postgres_connection_string,
)
from datasift.exceptions.datasift_exceptions import (
    FlowExecutionFailedException,
    JobStatsStoreInitializationException,
)
from datasift.utils.infrastructure.filesystem import get_data_path
from datasift.utils.infrastructure.logging import get_logger

logger = get_logger("DATASIFT_INCREMENTAL_METADATA")


class IncrementalMetadataStorageType(StrEnum):
    """Supported incremental metadata storage types."""

    IN_MEMORY = "in_memory"
    FILE_SYSTEM = "file_system"
    POSTGRES = "postgresql"


@dataclass(slots=True)
class IncrementalMetadataRecord:
    job_id: str
    doc_id: str
    name: str | None = None
    modified_time: int | None = None
    job_run_id: str | None = None
    deleted: bool = False


class IncrementalMetadataStore(ABC):
    @abstractmethod
    def get_processed_docs(self, *, job_id: str) -> dict[str, Any]:
        pass

    @abstractmethod
    def upsert_records(self, *, job_id: str, job_run_id: str, records: list[IncrementalMetadataRecord]) -> None:
        pass

    @abstractmethod
    def get_soft_deleted_doc_ids(self, *, job_id: str) -> set[str]:
        pass

    @abstractmethod
    def mark_missing_docs_as_deleted(self, *, job_id: str, doc_ids: list[str]) -> set[str]:
        pass

    @abstractmethod
    def delete_docs(self, *, job_id: str, doc_ids: list[str]) -> None:
        pass

    @abstractmethod
    def clear(self, *, job_id: str) -> None:
        pass


class InMemoryIncrementalMetadataStore(IncrementalMetadataStore):
    """
    In-memory implementation of incremental metadata store.

    Note: This implementation is primarily for testing purposes and should not be used
    in production environments as data is not persisted across restarts.
    """

    def __init__(self) -> None:
        self._global_lock = RLock()
        self._job_locks: dict[str, RLock] = {}
        self._records: dict[str, dict[str, IncrementalMetadataRecord]] = {}

    def _get_job_lock(self, *, job_id: str) -> RLock:
        if job_id in self._job_locks:
            return self._job_locks[job_id]
        with self._global_lock:
            if job_id not in self._job_locks:
                self._job_locks[job_id] = RLock()
            return self._job_locks[job_id]

    def get_processed_docs(self, *, job_id: str) -> dict[str, Any]:
        lock = self._get_job_lock(job_id=job_id)
        with lock:
            records = deepcopy(self._records.get(job_id, {}))
            return {doc_id: record.modified_time for doc_id, record in records.items() if not record.deleted}

    def upsert_records(self, *, job_id: str, job_run_id: str, records: list[IncrementalMetadataRecord]) -> None:
        lock = self._get_job_lock(job_id=job_id)
        with lock:
            job_records = self._records.setdefault(job_id, {})
            for record in records:
                job_records[record.doc_id] = IncrementalMetadataRecord(
                    job_id=job_id,
                    doc_id=record.doc_id,
                    name=record.name,
                    modified_time=record.modified_time,
                    job_run_id=job_run_id,
                    deleted=False,
                )

    def get_soft_deleted_doc_ids(self, *, job_id: str) -> set[str]:
        lock = self._get_job_lock(job_id=job_id)
        with lock:
            return {doc_id for doc_id, record in self._records.get(job_id, {}).items() if record.deleted}

    def mark_missing_docs_as_deleted(self, *, job_id: str, doc_ids: list[str]) -> set[str]:
        lock = self._get_job_lock(job_id=job_id)
        with lock:
            job_records = self._records.get(job_id, {})
            current_doc_ids = set(doc_ids)
            deleted_ids = {
                doc_id for doc_id, record in job_records.items() if doc_id not in current_doc_ids and not record.deleted
            }
            for doc_id in deleted_ids:
                job_records[doc_id].deleted = True
            return deleted_ids

    def delete_docs(self, *, job_id: str, doc_ids: list[str]) -> None:
        if not doc_ids:
            return
        lock = self._get_job_lock(job_id=job_id)
        with lock:
            job_records = self._records.get(job_id, {})
            for doc_id in doc_ids:
                job_records.pop(doc_id, None)

    def clear(self, *, job_id: str) -> None:
        lock = self._get_job_lock(job_id=job_id)
        with lock:
            self._records.pop(job_id, None)
        with self._global_lock:
            self._job_locks.pop(job_id, None)


class FileSystemIncrementalMetadataStore(IncrementalMetadataStore):
    def __init__(self, *, backend_config: dict[str, Any] | None = None) -> None:
        backend_config = backend_config or {}
        base_dir = backend_config.get(DatasiftConfigKeys.BASE_DIR)
        self._base_dir = Path(base_dir) if base_dir is not None else Path(get_data_path())
        self._lock_timeout = backend_config.get("lock_timeout", 30.0)

    def _get_job_dir(self, *, job_id: str) -> Path:
        return self._base_dir / job_id / DatasiftConstants.INCREMENTAL_PROCESSING_METADATA_PATH

    def _get_lock_path(self, *, job_id: str) -> Path:
        lock_dir = self._get_job_dir(job_id=job_id) / ".locks"
        lock_dir.mkdir(parents=True, exist_ok=True)
        return lock_dir / "incremental_metadata.lock"

    def _get_records_path(self, *, job_id: str) -> Path:
        return self._get_job_dir(job_id=job_id) / "incremental_metadata.json"

    def _read_records(self, *, job_id: str) -> dict[str, IncrementalMetadataRecord]:
        path = self._get_records_path(job_id=job_id)
        if not path.exists():
            return {}
        with open(path, encoding="utf-8") as file:
            payload = json.load(file)
        return {item["doc_id"]: IncrementalMetadataRecord(**item) for item in payload}

    def _write_records(self, *, job_id: str, records: dict[str, IncrementalMetadataRecord]) -> None:
        path = self._get_records_path(job_id=job_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as file:
            json.dump([asdict(record) for record in records.values()], file, indent=2)
        temp_path.replace(path)

    def get_processed_docs(self, *, job_id: str) -> dict[str, Any]:
        lock = FileLock(str(self._get_lock_path(job_id=job_id)), timeout=self._lock_timeout)
        try:
            with lock.acquire(timeout=self._lock_timeout):
                records = self._read_records(job_id=job_id)
                return {doc_id: record.modified_time for doc_id, record in records.items() if not record.deleted}
        except Timeout as exc:
            raise FlowExecutionFailedException(
                f"Failed to acquire incremental metadata read lock for job_id={job_id}"
            ) from exc

    def upsert_records(self, *, job_id: str, job_run_id: str, records: list[IncrementalMetadataRecord]) -> None:
        lock = FileLock(str(self._get_lock_path(job_id=job_id)), timeout=self._lock_timeout)
        try:
            with lock.acquire(timeout=self._lock_timeout):
                existing = self._read_records(job_id=job_id)
                for record in records:
                    existing[record.doc_id] = IncrementalMetadataRecord(
                        job_id=job_id,
                        doc_id=record.doc_id,
                        name=record.name,
                        modified_time=record.modified_time,
                        job_run_id=job_run_id,
                        deleted=False,
                    )
                self._write_records(job_id=job_id, records=existing)
        except Timeout as exc:
            raise FlowExecutionFailedException(
                f"Failed to acquire incremental metadata write lock for job_id={job_id}"
            ) from exc

    def get_soft_deleted_doc_ids(self, *, job_id: str) -> set[str]:
        lock = FileLock(str(self._get_lock_path(job_id=job_id)), timeout=self._lock_timeout)
        try:
            with lock.acquire(timeout=self._lock_timeout):
                records = self._read_records(job_id=job_id)
                return {doc_id for doc_id, record in records.items() if record.deleted}
        except Timeout as exc:
            raise FlowExecutionFailedException(
                f"Failed to acquire incremental metadata deleted-doc read lock for job_id={job_id}"
            ) from exc

    def mark_missing_docs_as_deleted(self, *, job_id: str, doc_ids: list[str]) -> set[str]:
        lock = FileLock(str(self._get_lock_path(job_id=job_id)), timeout=self._lock_timeout)
        try:
            with lock.acquire(timeout=self._lock_timeout):
                records = self._read_records(job_id=job_id)
                current_doc_ids = set(doc_ids)
                deleted_ids = {
                    doc_id for doc_id, record in records.items() if doc_id not in current_doc_ids and not record.deleted
                }
                for doc_id in deleted_ids:
                    records[doc_id].deleted = True
                self._write_records(job_id=job_id, records=records)
                return deleted_ids
        except Timeout as exc:
            raise FlowExecutionFailedException(
                f"Failed to acquire incremental metadata soft-delete lock for job_id={job_id}"
            ) from exc

    def delete_docs(self, *, job_id: str, doc_ids: list[str]) -> None:
        if not doc_ids:
            return
        lock = FileLock(str(self._get_lock_path(job_id=job_id)), timeout=self._lock_timeout)
        try:
            with lock.acquire(timeout=self._lock_timeout):
                records = self._read_records(job_id=job_id)
                for doc_id in doc_ids:
                    records.pop(doc_id, None)
                self._write_records(job_id=job_id, records=records)
        except Timeout as exc:
            raise FlowExecutionFailedException(
                f"Failed to acquire incremental metadata delete lock for job_id={job_id}"
            ) from exc

    def clear(self, *, job_id: str) -> None:
        job_dir = self._get_job_dir(job_id=job_id)
        if not job_dir.exists():
            return

        lock = FileLock(str(self._get_lock_path(job_id=job_id)), timeout=self._lock_timeout)
        try:
            with lock.acquire(timeout=self._lock_timeout):
                records_path = self._get_records_path(job_id=job_id)
                if records_path.exists():
                    records_path.unlink()

                locks_dir = job_dir / ".locks"
                if locks_dir.exists():
                    shutil.rmtree(locks_dir)

                if job_dir.exists():
                    remaining_entries = list(job_dir.iterdir())
                    if not remaining_entries:
                        job_dir.rmdir()
        except Timeout as exc:
            raise FlowExecutionFailedException(
                f"Failed to acquire incremental metadata clear lock for job_id={job_id}"
            ) from exc


class IncrementalMetadataPostgresModel(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "inc_update_metadata"
    __table_args__ = {"schema": os.getenv("DATASIFT_POSTGRES_SCHEMA", DatasiftConstants.INCREMENTAL_METADATA)}

    job_id: str = Field(sa_column=Column(String, primary_key=True))
    doc_id: str = Field(sa_column=Column(String, primary_key=True))
    name: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    modified_time: int | None = Field(default=None, sa_column=Column(BIGINT, nullable=True))
    job_run_id: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    deleted: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, server_default="false"))


class PostgresIncrementalMetadataStore(IncrementalMetadataStore):
    def __init__(self, *, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}
        connection_string = get_postgres_connection_string(config=self.config)
        if not connection_string:
            raise JobStatsStoreInitializationException(
                message="PostgreSQL connection not configured for incremental metadata.",
                store_type="postgres",
            )
        self._engine = create_postgres_engine(connection_string=connection_string, config=self.config)
        self._session_factory = create_session_factory(engine=self._engine)
        schema_name = IncrementalMetadataPostgresModel.__table_args__["schema"]
        with self._engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))
        SQLModel.metadata.create_all(self._engine)

    def get_processed_docs(self, *, job_id: str) -> dict[str, Any]:
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
            return {row.doc_id: row.modified_time for row in rows}

    def upsert_records(self, *, job_id: str, job_run_id: str, records: list[IncrementalMetadataRecord]) -> None:
        with self._session_factory() as session:
            for record in records:
                model = session.get(IncrementalMetadataPostgresModel, (job_id, record.doc_id))
                if model is None:
                    model = IncrementalMetadataPostgresModel(job_id=job_id, doc_id=record.doc_id)
                model.name = record.name
                model.modified_time = record.modified_time
                model.job_run_id = job_run_id
                model.deleted = False
                session.add(model)
            session.commit()

    def get_soft_deleted_doc_ids(self, *, job_id: str) -> set[str]:
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
            return set(rows)

    def mark_missing_docs_as_deleted(self, *, job_id: str, doc_ids: list[str]) -> set[str]:
        current_doc_ids = set(doc_ids)
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
            deleted_ids = {row.doc_id for row in rows if row.doc_id not in current_doc_ids}
            for row in rows:
                if row.doc_id in deleted_ids:
                    row.deleted = True
                    session.add(row)
            session.commit()
            return deleted_ids

    def delete_docs(self, *, job_id: str, doc_ids: list[str]) -> None:
        if not doc_ids:
            return
        with self._session_factory() as session:
            session.execute(
                delete(IncrementalMetadataPostgresModel).where(
                    Column("job_id", String) == job_id,
                    Column("doc_id", String).in_(doc_ids),
                )
            )
            session.commit()

    def clear(self, *, job_id: str) -> None:
        with self._session_factory() as session:
            session.execute(
                delete(IncrementalMetadataPostgresModel).where(
                    Column("job_id", String) == job_id,
                )
            )
            session.commit()


def create_incremental_metadata_store(
    *, config: dict[str, Any] | None = None, flow_config: dict[str, Any] | None = None
) -> IncrementalMetadataStore:
    """
    Create an incremental metadata store.

    Args:
        config: Legacy config parameter (for backward compatibility)
        flow_config: Flow-level incremental metadata configuration from global_config.incremental_metadata

    Returns:
        IncrementalMetadataStore: Configured store instance

    Flow-level config takes precedence over default factory config.
    Expected flow_config structure:
    {
        "storage_type": "file_system" | "postgresql" | "in_memory",
        "config": {
            # Backend-specific configuration
            # For file_system: {"base_dir": "path/to/dir", "lock_timeout": 30.0}
            # For PostgreSQL: {"host": "...", "port": 5432, "database": "...", ...}
        }
    }
    """
    # If flow-level config is provided, use it directly
    if flow_config:
        storage_type_str = flow_config.get("storage_type", "").lower()
        backend_config = flow_config.get("config", {})

        if storage_type_str == IncrementalMetadataStorageType.IN_MEMORY:
            return InMemoryIncrementalMetadataStore()

        if storage_type_str == IncrementalMetadataStorageType.FILE_SYSTEM:
            return FileSystemIncrementalMetadataStore(backend_config=backend_config)

        if storage_type_str == IncrementalMetadataStorageType.POSTGRES:
            return PostgresIncrementalMetadataStore(config=backend_config)

        raise ValueError(f"Unknown storage backend in flow config: {storage_type_str}")

    # Fallback to existing default behavior
    factory = get_default_factory()
    backend = factory.storage_backend
    resolved_config = config or factory.config

    if backend == StorageBackend.IN_MEMORY:
        return InMemoryIncrementalMetadataStore()

    if backend == StorageBackend.JSON:
        base_dir_override = os.getenv(EnvironmentVariables.DATASIFT_JOB_STATS_BASE_DIR)
        configured_base_dir = resolved_config.get(DatasiftConfigKeys.BASE_DIR)
        resolved_base_dir = None

        if base_dir_override:
            resolved_base_dir = Path(base_dir_override) / DatasiftConstants.INCREMENTAL_METADATA
        elif configured_base_dir:
            configured_path = Path(configured_base_dir)
            resolved_base_dir = (
                configured_path if configured_path.is_absolute() else configured_path.resolve()
            ) / DatasiftConstants.INCREMENTAL_METADATA

        backend_config = {
            "base_dir": str(resolved_base_dir) if resolved_base_dir else None,
            "lock_timeout": resolved_config.get(DatasiftConfigKeys.LOCK_TIMEOUT, 30.0),
        }
        return FileSystemIncrementalMetadataStore(backend_config=backend_config)

    if backend == StorageBackend.POSTGRESQL:
        return PostgresIncrementalMetadataStore(config=resolved_config)

    raise ValueError(f"Unknown storage backend for incremental metadata: {backend}")
