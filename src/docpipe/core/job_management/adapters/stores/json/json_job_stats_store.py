"""
JsonJobStatsStore - Filesystem-based storage adapter

Production-grade filesystem persistence implementation of JobStatsStore port.
Process-safe and thread-safe with file-level locking for concurrent micro-batch execution.

File Layout:
    /data/job_stats/
        {job_run_id}/
            job_stats.json          # Job-level statistics (contains job_id)
            node_stats/
                <node_id>_<batch_id>.json  # Batch-scoped node stats (micro-batching)
                <node_id>.json             # Non-batch node stats (e.g., ingest operator)
            .locks/                 # Lock files directory
                job_stats.lock      # Lock for job_stats.json
                node_stats.lock     # Lock for node_stats operations
"""

import json
from enum import Enum
from pathlib import Path
from typing import Any

from filelock import FileLock, Timeout

from docpipe.core.constants.constants import ExecutionStatus
from docpipe.core.job_management.domain.models import JobStats, NodeStats
from docpipe.core.job_management.domain.ports import JobStatsStore
from docpipe.exceptions.docpipe_exceptions import (
    JobStatsStoreAtomicUpdateException,
    JobStatsStoreDeleteException,
    JobStatsStoreReadException,
    JobStatsStoreWriteException,
)
from docpipe.utils.infrastructure.filesystem import get_data_path
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger()

# Constants
JOB_STATS_SUBDIR = "/job_stats"


class JsonJobStatsStore(JobStatsStore):
    """
    Process-safe and thread-safe JSON file-based storage for job statistics.

    Features:
    - File-level locking using filelock library for concurrent access
    - Human-readable JSON files for inspection
    - Deterministic file layout per job_run_id
    - Atomic writes using temp files
    - No pickle dependencies
    - Supports concurrent micro-batch execution

    File Structure:
    - /data/job_stats/{job_run_id}/job_stats.json: Job-level statistics (contains job_id)
    - /data/job_stats/{job_run_id}/node_stats/<node_id>_<batch_id>.json: Batch-scoped node stats
    - /data/job_stats/{job_run_id}/node_stats/<node_id>.json: Non-batch node stats
    - /data/job_stats/{job_run_id}/.locks/: Lock files directory

    Concurrency Safety:
    - File-level locks prevent race conditions across processes/threads
    - Separate locks for job_stats and node_stats operations
    - Atomic writes prevent partial file corruption
    - Lock timeout prevents deadlocks
    """

    def __init__(self, *, base_dir: str | Path | None = None, lock_timeout: float = 30.0):
        """
        Initialize JSON storage with deterministic base path and lock timeout.

        If ``base_dir`` is provided, it is used directly. Otherwise falls back to
        [`get_data_path()`](src/docpipe_app/backend/common/util/infrastructure/filesystem.py:13).

        Args:
            base_dir: Optional explicit storage root for job stats
            lock_timeout: Maximum time to wait for lock acquisition (seconds)
        """
        if base_dir is None:
            resolved_base_dir = Path(get_data_path(sub_dir=JOB_STATS_SUBDIR))
        else:
            resolved_base_dir = Path(base_dir)

        self._base_dir = resolved_base_dir
        self._lock_timeout = lock_timeout

        logger.info(f"JsonJobStatsStore initialized: base_dir={self._base_dir}, lock_timeout={lock_timeout}s")

    def _get_job_dir(self, *, job_run_id: str) -> Path:
        """Get directory path for a specific job run: /data/job_stats/{job_run_id}/"""
        return self._base_dir / job_run_id

    def _get_locks_dir(self, *, job_run_id: str) -> Path:
        """Get locks directory for a specific job run."""
        locks_dir = self._get_job_dir(job_run_id=job_run_id) / ".locks"
        locks_dir.mkdir(parents=True, exist_ok=True)
        return locks_dir

    def _get_node_stats_dir(self, *, job_run_id: str) -> Path:
        """Get node stats directory for a specific job run."""
        return self._get_job_dir(job_run_id=job_run_id) / "node_stats"

    def _get_job_stats_path(self, *, job_run_id: str) -> Path:
        """Get file path for job stats."""
        return self._get_job_dir(job_run_id=job_run_id) / "job_stats.json"

    def _get_job_stats_lock_path(self, *, job_run_id: str) -> Path:
        """Get lock file path for job stats."""
        return self._get_locks_dir(job_run_id=job_run_id) / "job_stats.lock"

    def _get_node_stats_lock_path(self, *, job_run_id: str) -> Path:
        """Get lock file path for node stats operations."""
        return self._get_locks_dir(job_run_id=job_run_id) / "node_stats.lock"

    def _get_node_stats_path(self, *, job_run_id: str, node_id: str, batch_id: str | None = None) -> Path:
        """Get file path for node stats."""
        node_stats_dir = self._get_node_stats_dir(job_run_id=job_run_id)

        if batch_id is not None:
            filename = f"{node_id}_{batch_id}.json"
        else:
            filename = f"{node_id}.json"

        return node_stats_dir / filename

    def _atomic_write_json(self, *, path: Path, data: dict[str, Any]) -> None:
        """
        Atomically write JSON data to file.

        Uses temp file + rename for atomic operation.

        Args:
            path: Target file path
            data: Data to write as JSON
        """
        path.parent.mkdir(parents=True, exist_ok=True)

        temp_path = path.with_suffix(".tmp")
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(
                    data,
                    f,
                    indent=2,
                    ensure_ascii=False,
                    default=lambda obj: obj.value if isinstance(obj, Enum) else str(obj),
                )

            # Atomic rename
            temp_path.replace(path)
        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            raise JobStatsStoreWriteException(
                message=f"Failed to write JSON file {path}: {e}", job_run_id=None, operation="atomic_write"
            ) from e

    def _read_json(self, *, path: Path) -> dict[str, Any] | None:
        """
        Read JSON data from file.

        Args:
            path: File path to read

        Returns:
            Parsed JSON data or None if file doesn't exist
        """
        if not path.exists():
            return None

        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to read JSON file {path}: {e}")
            raise JobStatsStoreReadException(
                message=f"Failed to read JSON file {path}: {e}", job_run_id=None, operation="read_json"
            ) from e

    def store_job_stats(self, job_stats: JobStats) -> None:
        """
        Store job-level statistics with file-level locking.

        Stores JobStats as JSON, excluding nested node_stats to avoid duplication.

        Args:
            job_stats: Job statistics to store

        Raises:
            IOError: If storage operation fails
            TimeoutError: If lock cannot be acquired
        """
        job_run_id = job_stats.job_run_id
        lock_path = self._get_job_stats_lock_path(job_run_id=job_run_id)
        lock = FileLock(str(lock_path), timeout=self._lock_timeout)

        try:
            with lock.acquire(timeout=self._lock_timeout):
                path = self._get_job_stats_path(job_run_id=job_run_id)

                # Convert to dict, excluding nested node_stats
                data = job_stats.model_dump(exclude={"node_stats", "batch_node_stats"})

                self._atomic_write_json(path=path, data=data)
                logger.debug(f"Stored job stats: job_run_id={job_run_id}")
        except Timeout as e:
            raise JobStatsStoreWriteException(
                message=f"Failed to acquire lock for job stats write: timeout={self._lock_timeout}s",
                job_run_id=job_run_id,
                operation="store_job_stats",
            ) from e
        except Exception as e:
            logger.error(f"Failed to store job stats: {e}")
            raise JobStatsStoreWriteException(
                message=f"Failed to store job stats: {e}", job_run_id=job_run_id, operation="store_job_stats"
            ) from e

    def get_job_stats(self, job_run_id: str) -> JobStats | None:
        """
        Retrieve job-level statistics with file-level locking.

        Args:
            job_run_id: Job run identifier

        Returns:
            JobStats if found, None otherwise
        """
        lock_path = self._get_job_stats_lock_path(job_run_id=job_run_id)
        lock = FileLock(str(lock_path), timeout=self._lock_timeout)

        try:
            with lock.acquire(timeout=self._lock_timeout):
                path = self._get_job_stats_path(job_run_id=job_run_id)
                data = self._read_json(path=path)

                if data is None:
                    return None

                try:
                    # Reconstruct JobStats from JSON
                    return JobStats(**data)
                except Exception as e:
                    logger.error(f"Failed to parse job stats from {path}: {e}")
                    raise JobStatsStoreReadException(
                        message=f"Failed to parse job stats: {e}", job_run_id=job_run_id, operation="get_job_stats"
                    ) from e
        except Timeout as e:
            raise JobStatsStoreReadException(
                message=f"Failed to acquire lock for job stats read: timeout={self._lock_timeout}s",
                job_run_id=job_run_id,
                operation="get_job_stats",
            ) from e

    def store_node_stats(self, *, job_run_id: str, node_stats: NodeStats) -> None:
        """
        Store node-level statistics with file-level locking.

        Args:
            job_run_id: Job run identifier (globally unique)
            node_stats: Node statistics to store

        Raises:
            IOError: If storage operation fails
            TimeoutError: If lock cannot be acquired
        """
        lock_path = self._get_node_stats_lock_path(job_run_id=job_run_id)
        lock = FileLock(str(lock_path), timeout=self._lock_timeout)

        try:
            with lock.acquire(timeout=self._lock_timeout):
                node_id = node_stats.node_id
                batch_id = getattr(node_stats, "batch_id", None)

                path = self._get_node_stats_path(job_run_id=job_run_id, node_id=node_id, batch_id=batch_id)
                data = node_stats.model_dump(by_alias=True)

                self._atomic_write_json(path=path, data=data)

                logger.debug(f"Stored node stats: job_run_id={job_run_id}, node_id={node_id}, batch_id={batch_id}")
        except Timeout as e:
            raise JobStatsStoreWriteException(
                message=f"Failed to acquire lock for node stats write: timeout={self._lock_timeout}s",
                job_run_id=job_run_id,
                operation="store_node_stats",
            ) from e
        except Exception as e:
            logger.error(f"Failed to store node stats: {e}")
            raise JobStatsStoreWriteException(
                message=f"Failed to store node stats: {e}", job_run_id=job_run_id, operation="store_node_stats"
            ) from e

    def get_node_stats(self, *, job_run_id: str) -> list[NodeStats]:
        """
        Retrieve ALL node statistics records (NO AGGREGATION) with file-level locking.

        Returns a flat list of all node stats (batch and non-batch).
        Aggregation is handled by NodeStatsAggregator service layer.

        Args:
            job_run_id: Job run identifier (globally unique)

        Returns:
            List of ALL NodeStats records
        """
        lock_path = self._get_node_stats_lock_path(job_run_id=job_run_id)
        lock = FileLock(str(lock_path), timeout=self._lock_timeout)

        try:
            with lock.acquire(timeout=self._lock_timeout):
                result: list[NodeStats] = []
                node_stats_dir = self._get_node_stats_dir(job_run_id=job_run_id)

                if not node_stats_dir.exists():
                    return result

                try:
                    # Read all JSON files in node_stats directory
                    for json_file in node_stats_dir.glob("*.json"):
                        data = self._read_json(path=json_file)
                        if data:
                            node_stats = NodeStats(**data)
                            result.append(node_stats)

                    logger.debug(f"Retrieved {len(result)} node stats records: job_run_id={job_run_id}")
                    return result
                except Exception as e:
                    logger.error(f"Failed to read node stats: {e}")
                    raise JobStatsStoreReadException(
                        message=f"Failed to read node stats: {e}", job_run_id=job_run_id, operation="get_node_stats"
                    ) from e
        except Timeout as e:
            raise JobStatsStoreReadException(
                message=f"Failed to acquire lock for node stats read: timeout={self._lock_timeout}s",
                job_run_id=job_run_id,
                operation="get_node_stats",
            ) from e

    def get_batch_node_stats(self, *, job_run_id: str) -> dict[str, dict[str, NodeStats]]:
        """
        Retrieve batch-level node statistics for micro-batching with file-level locking.

        Returns nested dictionary grouped by node_id, then batch_id.
        Used for detailed batch-level progress tracking.

        Args:
            job_run_id: Job run identifier (globally unique)

        Returns:
            Nested dict: {node_id: {batch_id: NodeStats}}
        """
        lock_path = self._get_node_stats_lock_path(job_run_id=job_run_id)
        lock = FileLock(str(lock_path), timeout=self._lock_timeout)

        try:
            with lock.acquire(timeout=self._lock_timeout):
                result: dict[str, dict[str, NodeStats]] = {}
                node_stats_dir = self._get_node_stats_dir(job_run_id=job_run_id)

                if not node_stats_dir.exists():
                    return result

                try:
                    # Read all JSON files with batch_id pattern
                    for json_file in node_stats_dir.glob("*_*.json"):
                        data = self._read_json(path=json_file)
                        if data:
                            node_stats = NodeStats(**data)
                            batch_id = getattr(node_stats, "batch_id", None)

                            if batch_id is not None:
                                node_id = node_stats.node_id
                                if node_id not in result:
                                    result[node_id] = {}
                                result[node_id][batch_id] = node_stats

                    logger.debug(f"Retrieved batch node stats: job_run_id={job_run_id}, nodes={len(result)}")
                    return result
                except Exception as e:
                    logger.error(f"Failed to read batch node stats: {e}")
                    raise JobStatsStoreReadException(
                        message=f"Failed to read batch node stats: {e}",
                        job_run_id=job_run_id,
                        operation="get_batch_node_stats",
                    ) from e
        except Timeout as e:
            raise JobStatsStoreReadException(
                message=f"Failed to acquire lock for batch node stats read: timeout={self._lock_timeout}s",
                job_run_id=job_run_id,
                operation="get_batch_node_stats",
            ) from e

    def bulk_store_node_stats(self, *, job_run_id: str, node_stats_list: list[NodeStats]) -> None:
        """
        Bulk store multiple node statistics (micro-batching) with file-level locking.

        Used to create pending node stats for all batches at once.

        Args:
            job_run_id: Job run identifier (globally unique)
            node_stats_list: List of node statistics to store

        Raises:
            IOError: If bulk operation fails
            TimeoutError: If lock cannot be acquired
        """
        lock_path = self._get_node_stats_lock_path(job_run_id=job_run_id)
        lock = FileLock(str(lock_path), timeout=self._lock_timeout)

        try:
            with lock.acquire(timeout=self._lock_timeout):
                for node_stats in node_stats_list:
                    node_id = node_stats.node_id
                    batch_id = getattr(node_stats, "batch_id", None)

                    path = self._get_node_stats_path(job_run_id=job_run_id, node_id=node_id, batch_id=batch_id)
                    data = node_stats.model_dump(by_alias=True)

                    self._atomic_write_json(path=path, data=data)

                logger.debug(f"Bulk stored {len(node_stats_list)} node stats: job_run_id={job_run_id}")
        except Timeout as e:
            raise JobStatsStoreWriteException(
                message=f"Failed to acquire lock for bulk node stats write: timeout={self._lock_timeout}s",
                job_run_id=job_run_id,
                operation="bulk_store_node_stats",
            ) from e
        except Exception as e:
            logger.error(f"Failed to bulk store node stats: {e}")
            raise JobStatsStoreWriteException(
                message=f"Failed to bulk store node stats: {e}",
                job_run_id=job_run_id,
                operation="bulk_store_node_stats",
            ) from e

    def atomic_increment_fields(
        self,
        job_run_id: str,
        increments: dict[str, int],
        updates: dict[str, Any] | None = None,
        jsonb_merges: dict[str, dict] | None = None,
    ) -> None:
        """
        Atomically increment numeric fields and update others with file-level locking.

        File-level lock ensures atomicity across processes/threads.

        Args:
            job_run_id: Job run identifier
            increments: Fields to increment {field_name: increment_value}
            updates: Fields to update {field_name: new_value}
            jsonb_merges: JSONB fields to merge (treated as dict merge)

        Example:
            atomic_increment_fields(
                job_run_id="job_123",
                increments={DocpipeConstants.PROCESSED_DOCS: 10, DocpipeConstants.FAILED_DOCS: 2},
                updates={DocpipeConstants.STATUS: ExecutionStatus.RUNNING.value, "heartbeat_timestamp": 1704067260}
            )
        """
        lock_path = self._get_job_stats_lock_path(job_run_id=job_run_id)
        lock = FileLock(str(lock_path), timeout=self._lock_timeout)

        try:
            with lock.acquire(timeout=self._lock_timeout):
                job_stats = self.get_job_stats(job_run_id)
                if not job_stats:
                    logger.warning(f"Job stats not found for atomic update: {job_run_id}")
                    return

                # Apply increments
                for field_name, increment_value in increments.items():
                    current_value = getattr(job_stats, field_name, 0)
                    setattr(job_stats, field_name, current_value + increment_value)

                # Apply updates
                if updates:
                    for field_name, new_value in updates.items():
                        setattr(job_stats, field_name, new_value)

                # Apply JSONB merges (dict merge)
                if jsonb_merges:
                    for field_name, merge_dict in jsonb_merges.items():
                        current_dict = getattr(job_stats, field_name, {})
                        if isinstance(current_dict, dict):
                            current_dict.update(merge_dict)
                            setattr(job_stats, field_name, current_dict)

                # Write back atomically
                self.store_job_stats(job_stats)
                logger.debug(f"Atomic update applied: job_run_id={job_run_id}")
        except Timeout as e:
            raise JobStatsStoreAtomicUpdateException(
                message=f"Failed to acquire lock for atomic update: timeout={self._lock_timeout}s",
                job_run_id=job_run_id,
            ) from e

    def get_node_stats_by_batch_and_node(
        self, job_run_id: str, node_id: str, batch_id: str | None = None
    ) -> NodeStats | None:
        """
        Get specific node stats for batch and node combination with file-level locking.

        Args:
            job_run_id: Job run identifier
            node_id: Node identifier
            batch_id: Batch identifier (None for aggregated stats)

        Returns:
            NodeStats if found, None otherwise
        """
        lock_path = self._get_node_stats_lock_path(job_run_id=job_run_id)
        lock = FileLock(str(lock_path), timeout=self._lock_timeout)

        try:
            with lock.acquire(timeout=self._lock_timeout):
                path = self._get_node_stats_path(job_run_id=job_run_id, node_id=node_id, batch_id=batch_id)
                data = self._read_json(path=path)

                if data is None:
                    return None

                try:
                    return NodeStats(**data)
                except Exception as e:
                    logger.error(f"Failed to parse node stats from {path}: {e}")
                    raise JobStatsStoreReadException(
                        message=f"Failed to parse node stats: {e}",
                        job_run_id=job_run_id,
                        operation="get_node_stats_by_batch_and_node",
                    ) from e
        except Timeout as e:
            raise JobStatsStoreReadException(
                message=f"Failed to acquire lock for node stats read: timeout={self._lock_timeout}s",
                job_run_id=job_run_id,
                operation="get_node_stats_by_batch_and_node",
            ) from e

    def delete_job_stats(self, job_run_id: str) -> None:
        """
        Delete job statistics and all associated node statistics with file-level locking.

        Args:
            job_run_id: Job run identifier

        Raises:
            ValueError: If job_run_id not found
        """
        # Acquire both locks to ensure no concurrent operations
        job_lock_path = self._get_job_stats_lock_path(job_run_id=job_run_id)
        node_lock_path = self._get_node_stats_lock_path(job_run_id=job_run_id)

        job_lock = FileLock(str(job_lock_path), timeout=self._lock_timeout)
        node_lock = FileLock(str(node_lock_path), timeout=self._lock_timeout)

        try:
            with job_lock.acquire(timeout=self._lock_timeout):
                with node_lock.acquire(timeout=self._lock_timeout):
                    job_dir = self._get_job_dir(job_run_id=job_run_id)

                    if not job_dir.exists():
                        raise JobStatsStoreDeleteException(
                            message=f"Job run not found: {job_run_id}", job_run_id=job_run_id
                        )

                    try:
                        # Delete entire job directory
                        import shutil

                        shutil.rmtree(job_dir)

                        logger.info(f"Deleted job stats: job_run_id={job_run_id}")
                    except Exception as e:
                        logger.error(f"Failed to delete job stats: {e}")
                        raise JobStatsStoreDeleteException(
                            message=f"Failed to delete job stats: {e}", job_run_id=job_run_id
                        ) from e
        except Timeout as e:
            raise JobStatsStoreDeleteException(
                message=f"Failed to acquire lock for job stats deletion: timeout={self._lock_timeout}s",
                job_run_id=job_run_id,
            ) from e

    def get_all_job_run_ids(self) -> list[str]:
        """
        Get all job run IDs (useful for testing and debugging).

        Not part of JobStatsStore interface.

        Returns:
            List of all job_run_ids
        """
        if not self._base_dir.exists():
            return []

        return [d.name for d in self._base_dir.iterdir() if d.is_dir() and (d / "job_stats.json").exists()]

    def list_job_runs(  # NOSONAR python:S3776
        self,
        job_id: str | None = None,
        status: ExecutionStatus | str | None = None,
        limit: int = 100,
    ) -> list[JobStats]:
        """
        List job runs with optional filters.

        Args:
            job_id: Optional filter by job_id
            status: Optional filter by status
            limit: Maximum number of results

        Returns:
            List of JobStats matching filters (sorted by start_time desc)
        """
        result: list[JobStats] = []

        if not self._base_dir.exists():
            return result

        try:
            # Iterate through all job run directories
            for job_dir in self._base_dir.iterdir():
                if not job_dir.is_dir():
                    continue

                job_stats_path = job_dir / "job_stats.json"
                if not job_stats_path.exists():
                    continue

                # Read job stats with lock
                job_run_id = job_dir.name
                lock_path = self._get_job_stats_lock_path(job_run_id=job_run_id)
                lock = FileLock(str(lock_path), timeout=self._lock_timeout)

                try:
                    with lock.acquire(timeout=self._lock_timeout):
                        data = self._read_json(path=job_stats_path)
                        if not data:
                            continue

                        try:
                            job_stats = JobStats(**data)

                            # Apply filters
                            if job_id and job_stats.job_id != job_id:
                                continue
                            if status and job_stats.status != status:
                                continue

                            result.append(job_stats)
                        except Exception as e:
                            logger.warning(f"Failed to parse job stats from {job_stats_path}: {e}")
                            continue
                except Timeout:
                    logger.warning(f"Timeout acquiring lock for job stats read: {job_run_id}")
                    continue

            # Sort by start_time descending (most recent first)
            result.sort(key=lambda x: x.start_time or 0, reverse=True)

            # Apply limit
            return result[:limit]
        except Exception as e:
            logger.error(f"Failed to list jobs: {e}")
            raise JobStatsStoreReadException(
                message=f"Failed to list jobs: {e}", job_run_id=None, operation="list_job_runs"
            ) from e
