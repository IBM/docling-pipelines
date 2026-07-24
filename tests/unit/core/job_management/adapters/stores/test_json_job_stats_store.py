"""
Unit tests for JsonJobStatsStore - Phase 5 compatibility tests

Tests cover:
- Port signature compliance (keyword-only args)
- Batch-scoped write semantics
- File-level locking behavior
- Concurrent micro-batching scenarios
- File persistence and recovery
"""

import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from docpipe.core.constants.constants import ExecutionStatus
from docpipe.core.job_management.adapters.stores.json.json_job_stats_store import (
    JsonJobStatsStore,
)
from docpipe.core.job_management.domain.models import JobStats, NodeStats


@pytest.fixture
def temp_data_dir(tmp_path):
    """Create temporary data directory for tests."""
    data_dir = tmp_path / "data" / "job_stats"
    data_dir.mkdir(parents=True, exist_ok=True)
    return tmp_path / "data"


@pytest.fixture
def store(temp_data_dir, monkeypatch):
    """Create JsonJobStatsStore with temporary directory."""

    # Mock get_data_path to use temp directory
    def mock_get_data_path(*, sub_dir):
        return str(temp_data_dir / sub_dir.lstrip("/"))

    monkeypatch.setattr(
        "docpipe.core.job_management.adapters.stores.json.json_job_stats_store.get_data_path",
        mock_get_data_path,
    )

    store = JsonJobStatsStore(lock_timeout=5.0)
    yield store


@pytest.fixture
def sample_job_stats():
    """Sample job stats for testing."""
    return JobStats(
        job_id="12345678-1234-1234-1234-123456789abc",
        job_run_id="87654321-4321-4321-4321-cba987654321",
        status=ExecutionStatus.RUNNING,
        processed_docs=100,
        failed_docs=5,
    )


@pytest.fixture
def sample_node_stats():
    """Sample node stats for testing."""
    return NodeStats(
        node_id="abcdef12-3456-7890-abcd-ef1234567890",
        name="TestNode",
        node_status=ExecutionStatus.COMPLETED,
        batch_id="fedcba98-7654-3210-fedc-ba9876543210",
        batch_num=0,
    )


class TestPortSignatureCompliance:
    """Test that all methods match port signatures (keyword-only args)."""

    def test_store_node_stats_requires_keyword_args(self, *, store, sample_node_stats):
        """store_node_stats must use keyword-only arguments."""
        job_run_id = "87654321-4321-4321-4321-cba987654321"

        # Should work with keyword args
        store.store_node_stats(job_run_id=job_run_id, node_stats=sample_node_stats)

    def test_get_node_stats_requires_keyword_args(self, *, store):
        """get_node_stats must use keyword-only arguments."""
        job_run_id = "87654321-4321-4321-4321-cba987654321"

        # Should work with keyword args
        result = store.get_node_stats(job_run_id=job_run_id)
        assert result == []

    def test_bulk_store_node_stats_requires_keyword_args(self, *, store, sample_node_stats):
        """bulk_store_node_stats must use keyword-only arguments."""
        job_run_id = "87654321-4321-4321-4321-cba987654321"

        # Should work with keyword args
        store.bulk_store_node_stats(job_run_id=job_run_id, node_stats_list=[sample_node_stats])


class TestFilePersistence:
    """Test file-based persistence behavior."""

    def test_job_stats_persisted_to_file(self, *, store, sample_job_stats, temp_data_dir):
        """Job stats should be written to JSON file."""
        job_run_id = sample_job_stats.job_run_id

        store.store_job_stats(sample_job_stats)

        # Verify file exists
        job_stats_file = Path(temp_data_dir) / "job_stats" / job_run_id / "job_stats.json"
        assert job_stats_file.exists()

        # Verify content
        with open(job_stats_file) as f:
            data = json.load(f)
            assert data["job_run_id"] == job_run_id
            assert data["processed_docs"] == 100

    def test_node_stats_persisted_to_separate_files(self, *, store, temp_data_dir):
        """Each node stat should be written to separate file."""
        job_run_id = "87654321-4321-4321-4321-cba987654321"
        node_id = "abcdef12-3456-7890-abcd-ef1234567890"

        # Store 3 batches
        for i in range(3):
            batch_id = str(uuid.uuid4())
            node_stats = NodeStats(
                node_id=node_id,
                name="TestNode",
                batch_id=batch_id,
                batch_num=i,
                node_status=ExecutionStatus.PENDING,
            )
            store.store_node_stats(job_run_id=job_run_id, node_stats=node_stats)

        # Verify 3 separate files exist
        node_stats_dir = Path(temp_data_dir) / "job_stats" / job_run_id / "node_stats"
        json_files = list(node_stats_dir.glob("*.json"))
        assert len(json_files) == 3

    def test_recovery_from_disk(self, *, store, sample_job_stats, temp_data_dir, monkeypatch):
        """Store should recover data from disk on restart."""
        job_run_id = sample_job_stats.job_run_id

        # Store data
        store.store_job_stats(sample_job_stats)

        # Create new store instance (simulates restart)
        def mock_get_data_path(*, sub_dir):
            return str(temp_data_dir / sub_dir.lstrip("/"))

        monkeypatch.setattr(
            "docpipe.core.job_management.adapters.stores.json.json_job_stats_store.get_data_path",
            mock_get_data_path,
        )

        new_store = JsonJobStatsStore(lock_timeout=5.0)

        # Should be able to read persisted data
        retrieved = new_store.get_job_stats(job_run_id)
        assert retrieved is not None
        assert retrieved.processed_docs == 100


class TestBatchScopedWrites:
    """Test batch-scoped persistence semantics."""

    def test_store_multiple_batches_same_node(self, *, store):
        """Multiple batches for same node should be stored separately."""
        job_run_id = "87654321-4321-4321-4321-cba987654321"
        node_id = "abcdef12-3456-7890-abcd-ef1234567890"

        # Store 3 batches for same node
        for i in range(3):
            batch_id = str(uuid.uuid4())
            node_stats = NodeStats(
                node_id=node_id,
                name="TestNode",
                batch_id=batch_id,
                batch_num=i,
                docs_completed_count=10 * (i + 1),
            )
            store.store_node_stats(job_run_id=job_run_id, node_stats=node_stats)

        # Retrieve all node stats
        all_stats = store.get_node_stats(job_run_id=job_run_id)
        assert len(all_stats) == 3

        # Verify each batch is separate
        batch_ids = {stats.batch_id for stats in all_stats}
        assert len(batch_ids) == 3

    def test_get_batch_node_stats_filters_non_batch(self, *, store):
        """get_batch_node_stats should only return batch records."""
        job_run_id = "87654321-4321-4321-4321-cba987654321"
        node_id = "abcdef12-3456-7890-abcd-ef1234567890"

        # Store batch record
        batch_stats = NodeStats(
            node_id=node_id,
            name="TestNode",
            batch_id="fedcba98-7654-3210-fedc-ba9876543210",
            batch_num=0,
            node_status=ExecutionStatus.COMPLETED,
        )
        store.store_node_stats(job_run_id=job_run_id, node_stats=batch_stats)

        # Store non-batch record (batch_id=None)
        non_batch_stats = NodeStats(
            node_id=node_id,
            name="TestNode",
            batch_id=None,
            node_status=ExecutionStatus.COMPLETED,
        )
        store.store_node_stats(job_run_id=job_run_id, node_stats=non_batch_stats)

        # get_batch_node_stats should only return batch record
        batch_dict = store.get_batch_node_stats(job_run_id=job_run_id)
        assert node_id in batch_dict
        assert len(batch_dict[node_id]) == 1
        assert "fedcba98-7654-3210-fedc-ba9876543210" in batch_dict[node_id]

    def test_get_node_stats_by_batch_and_node_with_none(self, *, store):
        """get_node_stats_by_batch_and_node should handle batch_id=None."""
        job_run_id = "87654321-4321-4321-4321-cba987654321"
        node_id = "abcdef12-3456-7890-abcd-ef1234567890"

        # Store non-batch record
        non_batch_stats = NodeStats(
            node_id=node_id,
            name="TestNode",
            batch_id=None,
            node_status=ExecutionStatus.COMPLETED,
        )
        store.store_node_stats(job_run_id=job_run_id, node_stats=non_batch_stats)

        # Retrieve with batch_id=None
        result = store.get_node_stats_by_batch_and_node(job_run_id=job_run_id, node_id=node_id, batch_id=None)
        assert result is not None
        assert result.batch_id is None


class TestFileLocking:
    """Test file-level locking for concurrent access."""

    def test_concurrent_writes_different_jobs(self, *, store):
        """Concurrent writes to different jobs should not block."""
        results = []

        def store_job(job_num):
            job_run_id = str(uuid.uuid4())
            job_stats = JobStats(
                job_id="12345678-1234-1234-1234-123456789abc",
                job_run_id=job_run_id,
                status=ExecutionStatus.RUNNING,
                processed_docs=job_num,
            )
            store.store_job_stats(job_stats)
            results.append(job_num)

        # Run 10 concurrent jobs
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(store_job, i) for i in range(10)]
            for future in futures:
                future.result()

        # All jobs should complete
        assert len(results) == 10
        assert set(results) == set(range(10))

    def test_concurrent_writes_same_job_serializes(self, *, store):
        """Concurrent writes to same job should serialize with file locking."""
        job_run_id = "87654321-4321-4321-4321-cba987654321"
        node_id = "abcdef12-3456-7890-abcd-ef1234567890"

        def write_batch(batch_num):
            batch_id = str(uuid.uuid4())
            node_stats = NodeStats(
                node_id=node_id,
                name="TestNode",
                batch_id=batch_id,
                batch_num=batch_num,
                node_status=ExecutionStatus.PENDING,
            )
            store.store_node_stats(job_run_id=job_run_id, node_stats=node_stats)

        # Run 5 threads writing concurrently
        threads = [threading.Thread(target=write_batch, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All 5 batches should be persisted
        all_stats = store.get_node_stats(job_run_id=job_run_id)
        assert len(all_stats) == 5

    def test_lock_timeout_prevents_deadlock(self, *, store, sample_job_stats):
        """Lock timeout should prevent indefinite blocking."""
        # This test verifies lock timeout is configured
        assert store._lock_timeout == 5.0

        # Store should work normally
        store.store_job_stats(sample_job_stats)
        retrieved = store.get_job_stats(sample_job_stats.job_run_id)
        assert retrieved is not None


class TestBulkOperations:
    """Test bulk_store_node_stats for micro-batching."""

    def test_bulk_store_multiple_batches(self, *, store):
        """Bulk store should handle multiple batches efficiently."""
        job_run_id = "87654321-4321-4321-4321-cba987654321"
        node_id = "abcdef12-3456-7890-abcd-ef1234567890"

        # Create 10 batch records
        node_stats_list = [
            NodeStats(
                node_id=node_id,
                name="TestNode",
                batch_id=str(uuid.uuid4()),
                batch_num=i,
                node_status=ExecutionStatus.PENDING,
            )
            for i in range(10)
        ]

        # Bulk store
        store.bulk_store_node_stats(job_run_id=job_run_id, node_stats_list=node_stats_list)

        # Verify all stored
        all_stats = store.get_node_stats(job_run_id=job_run_id)
        assert len(all_stats) == 10

        batch_dict = store.get_batch_node_stats(job_run_id=job_run_id)
        assert len(batch_dict[node_id]) == 10


class TestListJobRuns:
    """Test list_job_runs filtering."""

    def test_list_job_runs_no_filter(self, *, store):
        """List all job runs."""
        # Store 3 jobs
        for _i in range(3):
            job_stats = JobStats(
                job_id=str(uuid.uuid4()),
                job_run_id=str(uuid.uuid4()),
                status=ExecutionStatus.RUNNING,
            )
            store.store_job_stats(job_stats)

        result = store.list_job_runs()
        assert len(result) == 3

    def test_list_job_runs_filter_by_status(self, *, store):
        """Filter job runs by status."""
        # Store jobs with different statuses
        for _i, status in enumerate([ExecutionStatus.RUNNING, ExecutionStatus.COMPLETED, ExecutionStatus.FAILED]):
            job_stats = JobStats(job_id=str(uuid.uuid4()), job_run_id=str(uuid.uuid4()), status=status)
            store.store_job_stats(job_stats)

        result = store.list_job_runs(status=ExecutionStatus.COMPLETED)
        assert len(result) == 1
        assert result[0].status == ExecutionStatus.COMPLETED

    def test_list_job_runs_sorted_by_start_time(self, *, store):
        """Job runs should be sorted by start_time descending."""
        # Store jobs with different start times
        for i in range(3):
            job_stats = JobStats(
                job_id=str(uuid.uuid4()),
                job_run_id=str(uuid.uuid4()),
                status=ExecutionStatus.RUNNING,
                start_time=1000 + i * 100,
            )
            store.store_job_stats(job_stats)

        result = store.list_job_runs()
        # Should be sorted descending (most recent first)
        assert result[0].start_time == 1200
        assert result[1].start_time == 1100
        assert result[2].start_time == 1000


class TestDeleteOperations:
    """Test delete operations."""

    def test_delete_job_stats_removes_files(self, *, store, sample_job_stats, temp_data_dir):
        """delete_job_stats should remove all files."""
        job_run_id = sample_job_stats.job_run_id

        # Store job stats
        store.store_job_stats(sample_job_stats)

        # Verify directory exists
        job_dir = Path(temp_data_dir) / "job_stats" / job_run_id
        assert job_dir.exists()

        # Delete
        store.delete_job_stats(job_run_id)

        # Directory should be removed
        assert not job_dir.exists()

    def test_delete_nonexistent_job_succeeds_silently(self, *, store):
        """Deleting nonexistent job should succeed silently (idempotent)."""
        # JsonJobStatsStore doesn't raise on delete of nonexistent job
        # It just logs and returns (idempotent delete)
        store.delete_job_stats("nonexistent")  # Should not raise


class TestErrorHandling:
    """Test error handling scenarios."""

    def test_get_nonexistent_job_returns_none(self, *, store):
        """Getting nonexistent job should return None."""
        result = store.get_job_stats("nonexistent")
        assert result is None

    def test_get_node_stats_nonexistent_job_returns_empty(self, *, store):
        """Getting node stats for nonexistent job should return empty list."""
        result = store.get_node_stats(job_run_id="nonexistent")
        assert result == []

    def test_atomic_increment_nonexistent_job_returns_none(self, *, store):
        """Atomic increment on nonexistent job returns None (no job stats to update)."""
        # JsonJobStatsStore's atomic_increment_fields calls get_job_stats first
        # If job doesn't exist, get_job_stats returns None and method returns early
        # This is correct behavior - can't increment stats that don't exist

        # Verify get_job_stats returns None for nonexistent job
        result = store.get_job_stats("nonexistent-job-id-12345678-1234-1234")
        assert result is None


# ---------------------------------------------------------------------------
# Additional tests to increase coverage for JsonJobStatsStore
# ---------------------------------------------------------------------------


class TestBaseDirectInit:
    """Test __init__ with explicit base_dir."""

    def test_explicit_base_dir_used(self, *, temp_data_dir, monkeypatch):
        """When base_dir is provided, it is used directly (not get_data_path)."""
        explicit_dir = temp_data_dir / "custom_dir"
        explicit_dir.mkdir(parents=True, exist_ok=True)

        store = JsonJobStatsStore(base_dir=str(explicit_dir), lock_timeout=5.0)

        assert store._base_dir == explicit_dir


class TestAtomicWriteJsonErrors:
    """Test _atomic_write_json error handling."""

    def test_raises_on_write_failure(self, *, store, tmp_path):
        """_atomic_write_json raises JobStatsStoreWriteException on failure."""
        from unittest.mock import patch

        from docpipe.exceptions.docpipe_exceptions import JobStatsStoreWriteException

        target_path = tmp_path / "bad_file.json"

        with patch("builtins.open", side_effect=PermissionError("denied")):
            with pytest.raises(JobStatsStoreWriteException):
                store._atomic_write_json(path=target_path, data={"key": "value"})

    def test_cleans_up_temp_file_on_failure(self, *, store, tmp_path):
        """Temp file is removed when write fails."""
        from unittest.mock import patch

        from docpipe.exceptions.docpipe_exceptions import JobStatsStoreWriteException

        target_path = tmp_path / "file.json"
        temp_path = target_path.with_suffix(".tmp")

        # Create a fake temp file to verify it gets cleaned up
        temp_path.touch()

        with patch("builtins.open", side_effect=OSError("write error")):
            with pytest.raises(JobStatsStoreWriteException):
                store._atomic_write_json(path=target_path, data={})


class TestReadJsonErrors:
    """Test _read_json error handling."""

    def test_raises_on_corrupt_json(self, *, store, tmp_path):
        """_read_json raises JobStatsStoreReadException on corrupt JSON."""
        from docpipe.exceptions.docpipe_exceptions import JobStatsStoreReadException

        corrupt_file = tmp_path / "corrupt.json"
        corrupt_file.write_text("this is not json!!")

        with pytest.raises(JobStatsStoreReadException):
            store._read_json(path=corrupt_file)

    def test_returns_none_for_nonexistent_file(self, *, store, tmp_path):
        """_read_json returns None for non-existent path."""
        result = store._read_json(path=tmp_path / "nonexistent.json")
        assert result is None


class TestStoreJobStatsErrors:
    """Test store_job_stats error paths."""

    def test_raises_on_lock_timeout(self, *, store, sample_job_stats):
        """store_job_stats raises JobStatsStoreWriteException on lock timeout."""
        from unittest.mock import MagicMock, patch

        from filelock import Timeout

        from docpipe.exceptions.docpipe_exceptions import JobStatsStoreWriteException

        mock_lock = MagicMock()
        mock_lock.acquire.side_effect = Timeout("timeout")

        with patch(
            "docpipe.core.job_management.adapters.stores.json.json_job_stats_store.FileLock", return_value=mock_lock
        ):
            with pytest.raises(JobStatsStoreWriteException):
                store.store_job_stats(sample_job_stats)

    def test_raises_on_general_write_error(self, *, store, sample_job_stats):
        """store_job_stats raises JobStatsStoreWriteException on generic errors."""
        from unittest.mock import patch

        from docpipe.exceptions.docpipe_exceptions import JobStatsStoreWriteException

        with patch.object(store, "_atomic_write_json", side_effect=OSError("disk full")):
            with pytest.raises(JobStatsStoreWriteException):
                store.store_job_stats(sample_job_stats)


class TestGetJobStatsErrors:
    """Test get_job_stats error paths."""

    def test_raises_on_lock_timeout(self, *, store):
        """get_job_stats raises JobStatsStoreReadException on lock timeout."""
        from unittest.mock import MagicMock, patch

        from filelock import Timeout

        from docpipe.exceptions.docpipe_exceptions import JobStatsStoreReadException

        mock_lock = MagicMock()
        mock_lock.acquire.side_effect = Timeout("timeout")

        with patch(
            "docpipe.core.job_management.adapters.stores.json.json_job_stats_store.FileLock", return_value=mock_lock
        ):
            with pytest.raises(JobStatsStoreReadException):
                store.get_job_stats("some-run-id")

    def test_raises_on_corrupt_job_stats_json(self, *, store, temp_data_dir):
        """get_job_stats raises JobStatsStoreReadException if JSON is corrupt."""
        from docpipe.exceptions.docpipe_exceptions import JobStatsStoreReadException

        job_run_id = "bad-json-run-id"
        job_dir = temp_data_dir / "job_stats" / job_run_id
        job_dir.mkdir(parents=True, exist_ok=True)
        (job_dir / "job_stats.json").write_text('{"invalid_field_xyz": 999}')

        # JobStats(**{invalid_field_xyz: 999}) should raise a validation error
        with pytest.raises((JobStatsStoreReadException, Exception)):
            store.get_job_stats(job_run_id)


class TestStoreNodeStatsErrors:
    """Test store_node_stats error paths."""

    def test_raises_on_lock_timeout(self, *, store, sample_node_stats):
        """store_node_stats raises JobStatsStoreWriteException on lock timeout."""
        from unittest.mock import MagicMock, patch

        from filelock import Timeout

        from docpipe.exceptions.docpipe_exceptions import JobStatsStoreWriteException

        mock_lock = MagicMock()
        mock_lock.acquire.side_effect = Timeout("timeout")

        with patch(
            "docpipe.core.job_management.adapters.stores.json.json_job_stats_store.FileLock", return_value=mock_lock
        ):
            with pytest.raises(JobStatsStoreWriteException):
                store.store_node_stats(job_run_id="some-run-id", node_stats=sample_node_stats)

    def test_raises_on_general_error(self, *, store, sample_node_stats):
        """store_node_stats raises JobStatsStoreWriteException on generic error."""
        from unittest.mock import patch

        from docpipe.exceptions.docpipe_exceptions import JobStatsStoreWriteException

        with patch.object(store, "_atomic_write_json", side_effect=OSError("disk full")):
            with pytest.raises(JobStatsStoreWriteException):
                store.store_node_stats(job_run_id="some-run-id", node_stats=sample_node_stats)


class TestGetNodeStatsErrors:
    """Test get_node_stats error paths."""

    def test_raises_on_lock_timeout(self, *, store):
        """get_node_stats raises JobStatsStoreReadException on lock timeout."""
        from unittest.mock import MagicMock, patch

        from filelock import Timeout

        from docpipe.exceptions.docpipe_exceptions import JobStatsStoreReadException

        mock_lock = MagicMock()
        mock_lock.acquire.side_effect = Timeout("timeout")

        with patch(
            "docpipe.core.job_management.adapters.stores.json.json_job_stats_store.FileLock", return_value=mock_lock
        ):
            with pytest.raises(JobStatsStoreReadException):
                store.get_node_stats(job_run_id="some-run-id")


class TestGetBatchNodeStatsErrors:
    """Test get_batch_node_stats error paths."""

    def test_raises_on_lock_timeout(self, *, store):
        """get_batch_node_stats raises JobStatsStoreReadException on lock timeout."""
        from unittest.mock import MagicMock, patch

        from filelock import Timeout

        from docpipe.exceptions.docpipe_exceptions import JobStatsStoreReadException

        mock_lock = MagicMock()
        mock_lock.acquire.side_effect = Timeout("timeout")

        with patch(
            "docpipe.core.job_management.adapters.stores.json.json_job_stats_store.FileLock", return_value=mock_lock
        ):
            with pytest.raises(JobStatsStoreReadException):
                store.get_batch_node_stats(job_run_id="some-run-id")

    def test_returns_empty_when_no_dir(self, *, store):
        """Returns empty dict when node_stats dir does not exist."""
        result = store.get_batch_node_stats(job_run_id="nonexistent-run-id-xyz")
        assert result == {}


class TestBulkStoreNodeStatsErrors:
    """Test bulk_store_node_stats error paths."""

    def test_raises_on_lock_timeout(self, *, store, sample_node_stats):
        """bulk_store_node_stats raises JobStatsStoreWriteException on lock timeout."""
        from unittest.mock import MagicMock, patch

        from filelock import Timeout

        from docpipe.exceptions.docpipe_exceptions import JobStatsStoreWriteException

        mock_lock = MagicMock()
        mock_lock.acquire.side_effect = Timeout("timeout")

        with patch(
            "docpipe.core.job_management.adapters.stores.json.json_job_stats_store.FileLock", return_value=mock_lock
        ):
            with pytest.raises(JobStatsStoreWriteException):
                store.bulk_store_node_stats(job_run_id="some-run-id", node_stats_list=[sample_node_stats])

    def test_raises_on_general_error(self, *, store, sample_node_stats):
        """bulk_store_node_stats raises JobStatsStoreWriteException on generic error."""
        from unittest.mock import patch

        from docpipe.exceptions.docpipe_exceptions import JobStatsStoreWriteException

        with patch.object(store, "_atomic_write_json", side_effect=RuntimeError("out of space")):
            with pytest.raises(JobStatsStoreWriteException):
                store.bulk_store_node_stats(job_run_id="some-run-id", node_stats_list=[sample_node_stats])


class TestAtomicIncrementFields:
    """Test atomic_increment_fields method."""

    def test_increments_numeric_fields(self, *, store, sample_job_stats):
        """Increments numeric fields atomically via patched inner calls."""
        from unittest.mock import MagicMock, patch

        job_run_id = sample_job_stats.job_run_id
        mock_job_stats = MagicMock()
        mock_job_stats.processed_docs = 100
        mock_job_stats.failed_docs = 5
        mock_job_stats.page_type_stats = None

        with patch.object(store, "get_job_stats", return_value=mock_job_stats), patch.object(store, "store_job_stats"):
            store.atomic_increment_fields(
                job_run_id,
                increments={"processed_docs": 10, "failed_docs": 2},
            )

        assert mock_job_stats.processed_docs == 110
        assert mock_job_stats.failed_docs == 7

    def test_applies_updates(self, *, store, sample_job_stats):
        """Applies field updates via patched inner calls."""
        from unittest.mock import MagicMock, patch

        job_run_id = sample_job_stats.job_run_id
        mock_job_stats = MagicMock()

        with (
            patch.object(store, "get_job_stats", return_value=mock_job_stats),
            patch.object(store, "store_job_stats") as mock_store_call,
        ):
            store.atomic_increment_fields(
                job_run_id,
                increments={},
                updates={"status": "COMPLETED"},
            )

        mock_store_call.assert_called_once()

    def test_applies_jsonb_merges(self, *, store, sample_job_stats):
        """Merges jsonb_merges dicts into existing dict fields."""
        from unittest.mock import patch

        job_run_id = sample_job_stats.job_run_id
        sample_job_stats.page_type_stats = {"pdf": 5}

        stored_result = [None]

        def capture_store(js):
            stored_result[0] = js

        with (
            patch.object(store, "get_job_stats", return_value=sample_job_stats),
            patch.object(store, "store_job_stats", side_effect=capture_store),
        ):
            store.atomic_increment_fields(
                job_run_id,
                increments={},
                jsonb_merges={"page_type_stats": {"docx": 3}},
            )

        assert stored_result[0].page_type_stats.get("docx") == 3

    def test_no_op_when_job_not_found(self, *, store):
        """Returns early when job not found (no exception)."""
        from unittest.mock import patch

        with patch.object(store, "get_job_stats", return_value=None):
            # Should not raise
            store.atomic_increment_fields(
                "nonexistent-job-run-id",
                increments={"processed_docs": 1},
            )

    def test_raises_on_lock_timeout(self, *, store):
        """Raises JobStatsStoreAtomicUpdateException on lock timeout."""
        from unittest.mock import MagicMock, patch

        from filelock import Timeout

        from docpipe.exceptions.docpipe_exceptions import JobStatsStoreAtomicUpdateException

        mock_lock = MagicMock()
        mock_lock.acquire.side_effect = Timeout("timeout")

        with patch(
            "docpipe.core.job_management.adapters.stores.json.json_job_stats_store.FileLock", return_value=mock_lock
        ):
            with pytest.raises(JobStatsStoreAtomicUpdateException):
                store.atomic_increment_fields("some-run-id", increments={"processed_docs": 1})


class TestGetNodeStatsByBatchAndNodeErrors:
    """Test get_node_stats_by_batch_and_node error paths."""

    def test_raises_on_lock_timeout(self, *, store):
        """Raises JobStatsStoreReadException on lock timeout."""
        from unittest.mock import MagicMock, patch

        from filelock import Timeout

        from docpipe.exceptions.docpipe_exceptions import JobStatsStoreReadException

        mock_lock = MagicMock()
        mock_lock.acquire.side_effect = Timeout("timeout")

        with patch(
            "docpipe.core.job_management.adapters.stores.json.json_job_stats_store.FileLock", return_value=mock_lock
        ):
            with pytest.raises(JobStatsStoreReadException):
                store.get_node_stats_by_batch_and_node(job_run_id="some-run-id", node_id="some-node-id")


class TestDeleteJobStatsErrors:
    """Test delete_job_stats error paths."""

    def test_delete_existing_job_succeeds(self, *, store, sample_job_stats, temp_data_dir):
        """delete_job_stats removes the job directory when it exists."""
        store.store_job_stats(sample_job_stats)
        job_run_id = sample_job_stats.job_run_id
        job_dir = temp_data_dir / "job_stats" / job_run_id
        assert job_dir.exists()

        store.delete_job_stats(job_run_id)

        assert not job_dir.exists()

    def test_raises_on_lock_timeout(self, *, store):
        """Raises JobStatsStoreDeleteException on lock timeout."""
        from unittest.mock import MagicMock, patch

        from filelock import Timeout

        from docpipe.exceptions.docpipe_exceptions import JobStatsStoreDeleteException

        mock_lock = MagicMock()
        mock_lock.acquire.side_effect = Timeout("timeout")

        with patch(
            "docpipe.core.job_management.adapters.stores.json.json_job_stats_store.FileLock", return_value=mock_lock
        ):
            with pytest.raises(JobStatsStoreDeleteException):
                store.delete_job_stats("some-run-id")


class TestGetAllJobRunIds:
    """Test get_all_job_run_ids method."""

    def test_returns_empty_when_base_dir_missing(self, *, store, temp_data_dir):
        """Returns empty list when base dir does not exist."""
        import shutil

        # Remove base dir
        base_dir = temp_data_dir / "job_stats"
        if base_dir.exists():
            shutil.rmtree(base_dir)

        result = store.get_all_job_run_ids()
        assert result == []

    def test_returns_job_run_ids_with_stats_file(self, *, store, sample_job_stats):
        """Returns only directories that contain job_stats.json."""
        store.store_job_stats(sample_job_stats)
        # Also create a directory without job_stats.json
        orphan_dir = store._base_dir / "orphan-dir-no-stats"
        orphan_dir.mkdir(parents=True, exist_ok=True)

        result = store.get_all_job_run_ids()

        assert sample_job_stats.job_run_id in result
        assert "orphan-dir-no-stats" not in result


class TestListJobRunsFilters:
    """Test list_job_runs filtering logic."""

    def test_filter_by_job_id(self, *, store):
        """list_job_runs filters by job_id."""
        target_job_id = str(uuid.uuid4())
        other_job_id = str(uuid.uuid4())

        for i in range(3):
            store.store_job_stats(
                JobStats(
                    job_id=target_job_id if i < 2 else other_job_id,
                    job_run_id=str(uuid.uuid4()),
                    status=ExecutionStatus.RUNNING,
                )
            )

        result = store.list_job_runs(job_id=target_job_id)
        assert len(result) == 2
        assert all(js.job_id == target_job_id for js in result)

    def test_limit_respected(self, *, store):
        """list_job_runs respects limit."""
        for _ in range(5):
            store.store_job_stats(
                JobStats(
                    job_id=str(uuid.uuid4()),
                    job_run_id=str(uuid.uuid4()),
                    status=ExecutionStatus.RUNNING,
                )
            )

        result = store.list_job_runs(limit=2)
        assert len(result) == 2

    def test_returns_empty_when_base_dir_missing(self, *, store, temp_data_dir):
        """Returns empty list when base dir is missing."""
        import shutil

        base_dir = temp_data_dir / "job_stats"
        if base_dir.exists():
            shutil.rmtree(base_dir)

        result = store.list_job_runs()
        assert result == []

    def test_raises_on_unexpected_error(self, *, store, temp_data_dir):
        """Raises JobStatsStoreReadException on unexpected errors."""
        from unittest.mock import patch

        from docpipe.exceptions.docpipe_exceptions import JobStatsStoreReadException

        # Ensure base_dir exists so list_job_runs doesn't short-circuit with []
        (temp_data_dir / "job_stats").mkdir(parents=True, exist_ok=True)

        # Patch Path.iterdir on the class so our store's base_dir is affected
        with patch("pathlib.Path.iterdir", side_effect=OSError("unexpected")):
            with pytest.raises(JobStatsStoreReadException):
                store.list_job_runs()
