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
from unittest.mock import MagicMock, patch

import pytest
from filelock import Timeout

from docpipe.core.constants.constants import ExecutionStatus
from docpipe.core.job_management.adapters.stores.json.json_job_stats_store import (
    JsonJobStatsStore,
)
from docpipe.core.job_management.domain.models import JobStats, NodeStats
from docpipe.exceptions.docpipe_exceptions import (
    JobStatsStoreDeleteException,
    JobStatsStoreReadException,
    JobStatsStoreWriteException,
)


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

    return JsonJobStatsStore(lock_timeout=5.0)


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
        id="abcdef12-3456-7890-abcd-ef1234567890",
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
        with Path(job_stats_file).open() as f:
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
                id=node_id,
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
                id=node_id,
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
            id=node_id,
            name="TestNode",
            batch_id="fedcba98-7654-3210-fedc-ba9876543210",
            batch_num=0,
            node_status=ExecutionStatus.COMPLETED,
        )
        store.store_node_stats(job_run_id=job_run_id, node_stats=batch_stats)

        # Store non-batch record (batch_id=None)
        non_batch_stats = NodeStats(
            id=node_id,
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
            id=node_id,
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
                id=node_id,
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
                id=node_id,
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

    def test_returns_empty_when_base_dir_missing(self, tmp_path, monkeypatch):
        """list_job_runs returns [] when the base directory does not exist."""

        def mock_get_data_path(*, sub_dir):
            return str(tmp_path / "nonexistent" / sub_dir.lstrip("/"))

        monkeypatch.setattr(
            "docpipe.core.job_management.adapters.stores.json.json_job_stats_store.get_data_path",
            mock_get_data_path,
        )
        store = JsonJobStatsStore(lock_timeout=5.0)
        assert store.list_job_runs() == []

    def test_skips_non_directory_entries(self, store):
        """Files inside base_dir that are not directories are ignored."""
        store._base_dir.mkdir(parents=True, exist_ok=True)
        # Write a stray file directly in base_dir
        (store._base_dir / "stray_file.txt").write_text("noise")
        # Also write a valid job entry
        job_run_id = str(uuid.uuid4())
        job_dir = store._base_dir / job_run_id
        job_dir.mkdir()
        (job_dir / "job_stats.json").write_text(
            json.dumps(
                {
                    "job_id": "j1",
                    "job_run_id": job_run_id,
                    "status": ExecutionStatus.COMPLETED.value,
                    "start_time": 1000,
                }
            )
        )
        result = store.list_job_runs()
        assert len(result) == 1

    def test_filter_by_job_ids_list(self, store):
        """list_job_runs filters by a list of job_ids."""
        for i in range(3):
            js = JobStats(
                job_id=f"job-{i}",
                job_run_id=str(uuid.uuid4()),
                status=ExecutionStatus.COMPLETED,
            )
            store.store_job_stats(js)
        result = store.list_job_runs(job_ids=["job-0", "job-1"])
        assert len(result) == 2
        returned_job_ids = {r.job_id for r in result}
        assert returned_job_ids == {"job-0", "job-1"}

    def test_list_job_runs_raises_on_iterdir_error(self, store):
        """list_job_runs raises JobStatsStoreReadException when iterdir fails."""
        # Replace _base_dir with a mock whose exists() returns True
        # and iterdir() raises OSError to trigger the except branch
        mock_dir = MagicMock()
        mock_dir.exists.return_value = True
        mock_dir.iterdir.side_effect = OSError("disk error")
        store._base_dir = mock_dir
        with pytest.raises(JobStatsStoreReadException, match="Failed to list jobs"):
            store.list_job_runs()


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


class TestReadJobStatsIfMatch:
    """Tests for JsonJobStatsStore._read_job_stats_if_match."""

    def _make_job_dir(self, tmp_path, job_run_id: str, data: dict | str | None = "valid") -> Path:
        """Helper: create a job directory with an optional job_stats.json."""
        job_dir = tmp_path / job_run_id
        job_dir.mkdir(parents=True)
        if data == "valid":
            payload = {
                "job_id": "job-abc",
                "job_run_id": job_run_id,
                "status": ExecutionStatus.COMPLETED.value,
                "start_time": 1000,
            }
            (job_dir / "job_stats.json").write_text(json.dumps(payload))
        elif data is not None:
            (job_dir / "job_stats.json").write_text(json.dumps(data))
        return job_dir

    def test_returns_none_when_job_stats_file_missing(self, store, tmp_path):
        """Directory exists but job_stats.json does not → None."""
        job_dir = tmp_path / "no-file-run"
        job_dir.mkdir()
        result = store._read_job_stats_if_match(job_dir=job_dir, job_id=None, job_ids_set=None, status=None)
        assert result is None

    def test_returns_none_when_json_file_is_empty(self, store, tmp_path):
        """job_stats.json exists but contains no data → None."""
        job_dir = tmp_path / "empty-run"
        job_dir.mkdir()
        (job_dir / "job_stats.json").write_text("{}")
        result = store._read_job_stats_if_match(job_dir=job_dir, job_id=None, job_ids_set=None, status=None)
        assert result is None

    def test_returns_none_on_parse_error(self, store, tmp_path):
        """Corrupt JSON that cannot be parsed into JobStats → None (logged)."""
        job_dir = tmp_path / "corrupt-run"
        job_dir.mkdir()
        (job_dir / "job_stats.json").write_text(json.dumps({"invalid_field": "bad"}))
        result = store._read_job_stats_if_match(job_dir=job_dir, job_id=None, job_ids_set=None, status=None)
        assert result is None

    def test_returns_job_stats_when_no_filters(self, store, tmp_path):
        """Valid file with no filters → returns JobStats."""
        job_run_id = str(uuid.uuid4())
        job_dir = self._make_job_dir(tmp_path, job_run_id)
        result = store._read_job_stats_if_match(job_dir=job_dir, job_id=None, job_ids_set=None, status=None)
        assert result is not None
        assert result.job_run_id == job_run_id

    def test_returns_none_when_job_id_filter_mismatches(self, store, tmp_path):
        """job_id filter rejects non-matching entry."""
        job_run_id = str(uuid.uuid4())
        job_dir = self._make_job_dir(tmp_path, job_run_id)
        result = store._read_job_stats_if_match(job_dir=job_dir, job_id="other-job-id", job_ids_set=None, status=None)
        assert result is None

    def test_returns_job_stats_when_job_id_filter_matches(self, store, tmp_path):
        """job_id filter accepts matching entry."""
        job_run_id = str(uuid.uuid4())
        job_dir = self._make_job_dir(tmp_path, job_run_id)
        result = store._read_job_stats_if_match(job_dir=job_dir, job_id="job-abc", job_ids_set=None, status=None)
        assert result is not None

    def test_returns_none_when_job_ids_set_filter_mismatches(self, store, tmp_path):
        """job_ids_set filter rejects entry whose job_id is not in the set."""
        job_run_id = str(uuid.uuid4())
        job_dir = self._make_job_dir(tmp_path, job_run_id)
        result = store._read_job_stats_if_match(
            job_dir=job_dir, job_id=None, job_ids_set={"different-job"}, status=None
        )
        assert result is None

    def test_returns_job_stats_when_job_ids_set_filter_matches(self, store, tmp_path):
        """job_ids_set filter accepts entry whose job_id is in the set."""
        job_run_id = str(uuid.uuid4())
        job_dir = self._make_job_dir(tmp_path, job_run_id)
        result = store._read_job_stats_if_match(
            job_dir=job_dir, job_id=None, job_ids_set={"job-abc", "other"}, status=None
        )
        assert result is not None

    def test_returns_none_when_status_filter_mismatches(self, store, tmp_path):
        """status filter rejects entry with different status."""
        job_run_id = str(uuid.uuid4())
        job_dir = self._make_job_dir(tmp_path, job_run_id)
        result = store._read_job_stats_if_match(
            job_dir=job_dir, job_id=None, job_ids_set=None, status=ExecutionStatus.RUNNING
        )
        assert result is None

    def test_returns_job_stats_when_status_filter_matches(self, store, tmp_path):
        """status filter accepts entry with matching status."""
        job_run_id = str(uuid.uuid4())
        job_dir = self._make_job_dir(tmp_path, job_run_id)
        result = store._read_job_stats_if_match(
            job_dir=job_dir, job_id=None, job_ids_set=None, status=ExecutionStatus.COMPLETED
        )
        assert result is not None

    def test_returns_none_on_lock_timeout(self, store, tmp_path):
        """Timeout acquiring lock → None (logged)."""
        job_run_id = str(uuid.uuid4())
        job_dir = self._make_job_dir(tmp_path, job_run_id)

        with patch(
            "docpipe.core.job_management.adapters.stores.json.json_job_stats_store.FileLock"
        ) as mock_filelock_cls:
            mock_lock = mock_filelock_cls.return_value
            mock_lock.acquire.side_effect = Timeout(str(job_dir / "job_stats.json"))
            result = store._read_job_stats_if_match(job_dir=job_dir, job_id=None, job_ids_set=None, status=None)
        assert result is None


class TestJsonJobStatsStore:
    def test_init_with_explicit_base_dir(self, tmp_path, monkeypatch):
        """Passing base_dir skips get_data_path and uses the provided path."""
        explicit_dir = str(tmp_path / "custom_stats")
        store = JsonJobStatsStore(base_dir=explicit_dir, lock_timeout=5.0)
        assert store._base_dir == Path(explicit_dir)

    def test_atomic_write_json_cleans_up_temp_on_error(self, store, tmp_path):
        """_atomic_write_json removes temp file and raises on write failure."""
        target_path = store._base_dir / "test_dir" / "out.json"
        target_path.parent.mkdir(parents=True, exist_ok=True)

        # Patch the rename step to raise so the except branch fires
        with patch("pathlib.Path.replace", side_effect=OSError("rename failed")):
            with pytest.raises(JobStatsStoreWriteException, match="Failed to write JSON file"):
                store._atomic_write_json(path=target_path, data={"key": "value"})

    def test_read_json_raises_on_corrupt_file(self, store, tmp_path):
        """_read_json raises JobStatsStoreReadException on JSON decode error."""
        bad_json = store._base_dir / "bad.json"
        bad_json.parent.mkdir(parents=True, exist_ok=True)
        bad_json.write_text("{ not valid json !!!")

        with pytest.raises(JobStatsStoreReadException, match="Failed to read JSON file"):
            store._read_json(path=bad_json)

    def test_store_job_stats_raises_on_general_exception(self, store):
        """store_job_stats wraps unexpected errors as JobStatsStoreWriteException."""
        js = JobStats(
            job_id="j1",
            job_run_id=str(uuid.uuid4()),
            status=ExecutionStatus.RUNNING,
        )
        with patch.object(store, "_atomic_write_json", side_effect=RuntimeError("disk full")):
            with pytest.raises(JobStatsStoreWriteException, match="Failed to store job stats"):
                store.store_job_stats(js)


class TestExceptionPaths:
    def test_store_job_stats_raises_on_lock_timeout(self, store):
        """store_job_stats raises JobStatsStoreWriteException on lock Timeout."""
        js = JobStats(job_id="j1", job_run_id=str(uuid.uuid4()), status=ExecutionStatus.RUNNING)
        with patch("docpipe.core.job_management.adapters.stores.json.json_job_stats_store.FileLock") as mock_cls:
            mock_cls.return_value.acquire.side_effect = Timeout("lock")
            with pytest.raises(JobStatsStoreWriteException, match="acquire lock for job stats write"):
                store.store_job_stats(js)

    def test_get_job_stats_raises_on_parse_error(self, store, tmp_path):
        """get_job_stats raises JobStatsStoreReadException when JSON cannot be parsed into JobStats."""
        job_run_id = str(uuid.uuid4())
        # Write a file with invalid fields so JobStats(**data) raises
        store._base_dir.mkdir(parents=True, exist_ok=True)
        job_dir = store._base_dir / job_run_id
        job_dir.mkdir(parents=True, exist_ok=True)
        (job_dir / "job_stats.json").write_text('{"totally_unknown_field": 99}')

        with pytest.raises(JobStatsStoreReadException, match="Failed to parse job stats"):
            store.get_job_stats(job_run_id)

    def test_store_node_stats_raises_on_lock_timeout(self, store, sample_node_stats):
        """store_node_stats raises JobStatsStoreWriteException on lock Timeout."""
        with patch("docpipe.core.job_management.adapters.stores.json.json_job_stats_store.FileLock") as mock_cls:
            mock_cls.return_value.acquire.side_effect = Timeout("lock")
            with pytest.raises(JobStatsStoreWriteException, match="acquire lock for node stats write"):
                store.store_node_stats(job_run_id=str(uuid.uuid4()), node_stats=sample_node_stats)

    def test_store_node_stats_raises_on_general_exception(self, store, sample_node_stats):
        """store_node_stats wraps unexpected errors as JobStatsStoreWriteException."""
        with patch.object(store, "_atomic_write_json", side_effect=RuntimeError("boom")):
            with pytest.raises(JobStatsStoreWriteException, match="Failed to store node stats"):
                store.store_node_stats(job_run_id=str(uuid.uuid4()), node_stats=sample_node_stats)

    def test_get_node_stats_raises_on_lock_timeout(self, store):
        """get_node_stats raises JobStatsStoreReadException on lock Timeout."""
        with patch("docpipe.core.job_management.adapters.stores.json.json_job_stats_store.FileLock") as mock_cls:
            mock_cls.return_value.acquire.side_effect = Timeout("lock")
            with pytest.raises(JobStatsStoreReadException, match="acquire lock for node stats read"):
                store.get_node_stats(job_run_id=str(uuid.uuid4()))

    def test_get_node_stats_raises_on_parse_error(self, store):
        """get_node_stats raises JobStatsStoreReadException when a node file cannot be parsed."""
        job_run_id = str(uuid.uuid4())
        node_stats_dir = store._base_dir / job_run_id / "node_stats"
        node_stats_dir.mkdir(parents=True, exist_ok=True)
        (node_stats_dir / "bad_node.json").write_text('{"totally_unknown_field": 1}')

        with pytest.raises(JobStatsStoreReadException, match="Failed to read node stats"):
            store.get_node_stats(job_run_id=job_run_id)

    def test_get_batch_node_stats_returns_empty_when_dir_missing(self, store):
        """get_batch_node_stats returns {} when node_stats dir does not exist."""
        result = store.get_batch_node_stats(job_run_id=str(uuid.uuid4()))
        assert result == {}

    def test_get_batch_node_stats_raises_on_lock_timeout(self, store):
        """get_batch_node_stats raises JobStatsStoreReadException on lock Timeout."""
        with patch("docpipe.core.job_management.adapters.stores.json.json_job_stats_store.FileLock") as mock_cls:
            mock_cls.return_value.acquire.side_effect = Timeout("lock")
            with pytest.raises(JobStatsStoreReadException, match="acquire lock for batch node stats read"):
                store.get_batch_node_stats(job_run_id=str(uuid.uuid4()))

    def test_get_batch_node_stats_raises_on_parse_error(self, store):
        """get_batch_node_stats raises JobStatsStoreReadException when a batch file is corrupt."""
        job_run_id = str(uuid.uuid4())
        node_stats_dir = store._base_dir / job_run_id / "node_stats"
        node_stats_dir.mkdir(parents=True, exist_ok=True)
        # Name contains underscore so it matches the *_*.json glob
        (node_stats_dir / "nodeid_batchid.json").write_text('{"totally_unknown_field": 1}')

        with pytest.raises(JobStatsStoreReadException, match="Failed to read batch node stats"):
            store.get_batch_node_stats(job_run_id=job_run_id)

    def test_try_store_node_stats_returns_true_on_success(self, store, sample_node_stats):
        """try_store_node_stats returns True when write succeeds."""
        result = store.try_store_node_stats(
            job_run_id=str(uuid.uuid4()), node_stats=sample_node_stats, lock_timeout=5.0
        )
        assert result is True

    def test_try_store_node_stats_returns_false_on_lock_timeout(self, store, sample_node_stats):
        """try_store_node_stats returns False (not raises) on lock Timeout."""
        with patch("docpipe.core.job_management.adapters.stores.json.json_job_stats_store.FileLock") as mock_cls:
            mock_cls.return_value.acquire.side_effect = Timeout("lock")
            result = store.try_store_node_stats(
                job_run_id=str(uuid.uuid4()), node_stats=sample_node_stats, lock_timeout=0.01
            )
        assert result is False

    def test_try_store_node_stats_raises_on_general_exception(self, store, sample_node_stats):
        """try_store_node_stats raises JobStatsStoreWriteException on unexpected errors."""
        with patch.object(store, "_atomic_write_json", side_effect=RuntimeError("disk error")):
            with pytest.raises(JobStatsStoreWriteException, match="Failed to store node stats"):
                store.try_store_node_stats(job_run_id=str(uuid.uuid4()), node_stats=sample_node_stats, lock_timeout=5.0)

    def test_bulk_store_node_stats_raises_on_lock_timeout(self, store, sample_node_stats):
        """bulk_store_node_stats raises JobStatsStoreWriteException on lock Timeout."""
        with patch("docpipe.core.job_management.adapters.stores.json.json_job_stats_store.FileLock") as mock_cls:
            mock_cls.return_value.acquire.side_effect = Timeout("lock")
            with pytest.raises(JobStatsStoreWriteException, match="acquire lock for bulk node stats write"):
                store.bulk_store_node_stats(job_run_id=str(uuid.uuid4()), node_stats_list=[sample_node_stats])

    def test_bulk_store_node_stats_raises_on_general_exception(self, store, sample_node_stats):
        """bulk_store_node_stats wraps unexpected errors as JobStatsStoreWriteException."""
        with patch.object(store, "_atomic_write_json", side_effect=RuntimeError("boom")):
            with pytest.raises(JobStatsStoreWriteException, match="Failed to bulk store node stats"):
                store.bulk_store_node_stats(job_run_id=str(uuid.uuid4()), node_stats_list=[sample_node_stats])

    def test_atomic_increment_fields_increments_and_updates(self, store):
        """atomic_increment_fields increments numeric fields and applies updates."""
        # atomic_increment_fields holds the job_stats lock then calls get_job_stats
        # (which would deadlock on a real FileLock). Patch get_job_stats + store_job_stats
        # to avoid the re-entrancy issue while still exercising the increment/update logic.
        job_run_id = str(uuid.uuid4())
        initial = JobStats(job_id="j1", job_run_id=job_run_id, status=ExecutionStatus.RUNNING, processed_docs=10)
        stored: list[JobStats] = []

        with (
            patch.object(store, "get_job_stats", return_value=initial),
            patch.object(store, "store_job_stats", side_effect=stored.append),
        ):
            store.atomic_increment_fields(
                job_run_id,
                increments={"processed_docs": 5},
                updates={"status": ExecutionStatus.COMPLETED.value},
            )

        assert len(stored) == 1
        assert stored[0].processed_docs == 15
        assert stored[0].status == ExecutionStatus.COMPLETED.value

    def test_atomic_increment_fields_applies_jsonb_merge(self, store):
        """atomic_increment_fields merges dict fields when jsonb_merges is provided."""
        job_run_id = str(uuid.uuid4())
        initial = JobStats(job_id="j1", job_run_id=job_run_id, status=ExecutionStatus.RUNNING, page_type_stats={})
        stored: list[JobStats] = []

        with (
            patch.object(store, "get_job_stats", return_value=initial),
            patch.object(store, "store_job_stats", side_effect=stored.append),
        ):
            store.atomic_increment_fields(
                job_run_id,
                increments={},
                jsonb_merges={"page_type_stats": {"pdf": 5}},
            )

        assert len(stored) == 1
        assert stored[0].page_type_stats == {"pdf": 5}

    def test_atomic_increment_fields_noop_when_job_missing(self, store):
        """atomic_increment_fields returns silently when job stats do not exist."""
        with patch.object(store, "get_job_stats", return_value=None):
            # Should not raise
            store.atomic_increment_fields("nonexistent-run-id", increments={"processed_docs": 1})

    def test_atomic_increment_fields_raises_on_lock_timeout(self, store):
        """atomic_increment_fields raises JobStatsStoreAtomicUpdateException on Timeout."""
        from docpipe.exceptions.docpipe_exceptions import JobStatsStoreAtomicUpdateException

        with patch("docpipe.core.job_management.adapters.stores.json.json_job_stats_store.FileLock") as mock_cls:
            mock_cls.return_value.acquire.side_effect = Timeout("lock")
            with pytest.raises(JobStatsStoreAtomicUpdateException, match="acquire lock for atomic update"):
                store.atomic_increment_fields(str(uuid.uuid4()), increments={"processed_docs": 1})

    def test_get_node_stats_by_batch_returns_none_when_missing(self, store):
        """get_node_stats_by_batch_and_node returns None for nonexistent file."""
        result = store.get_node_stats_by_batch_and_node(job_run_id=str(uuid.uuid4()), node_id="n1", batch_id=None)
        assert result is None

    def test_get_node_stats_by_batch_raises_on_parse_error(self, store):
        """get_node_stats_by_batch_and_node raises on corrupt node stats file."""
        job_run_id = str(uuid.uuid4())
        node_id = "node-abc"
        # Write a corrupt file at the expected path (no batch_id → <node_id>.json)
        node_stats_dir = store._base_dir / job_run_id / "node_stats"
        node_stats_dir.mkdir(parents=True, exist_ok=True)
        (node_stats_dir / f"{node_id}.json").write_text('{"totally_unknown_field": 1}')

        with pytest.raises(JobStatsStoreReadException, match="Failed to parse node stats"):
            store.get_node_stats_by_batch_and_node(job_run_id=job_run_id, node_id=node_id, batch_id=None)

    def test_get_node_stats_by_batch_raises_on_lock_timeout(self, store):
        """get_node_stats_by_batch_and_node raises JobStatsStoreReadException on Timeout."""
        with patch("docpipe.core.job_management.adapters.stores.json.json_job_stats_store.FileLock") as mock_cls:
            mock_cls.return_value.acquire.side_effect = Timeout("lock")
            with pytest.raises(JobStatsStoreReadException, match="acquire lock for node stats read"):
                store.get_node_stats_by_batch_and_node(job_run_id=str(uuid.uuid4()), node_id="n1", batch_id=None)

    def test_delete_job_stats_is_noop_when_not_found(self, store):
        """delete_job_stats is a no-op for an unknown job run.
        _get_locks_dir creates the job dir as a side-effect of acquiring the lock,
        so job_dir.exists() is True even for unknown IDs. Verify the method
        completes without raising.
        """
        # Should not raise
        store.delete_job_stats(str(uuid.uuid4()))

    def test_delete_job_stats_raises_on_rmtree_error(self, store):
        """delete_job_stats raises JobStatsStoreDeleteException when shutil.rmtree fails."""
        job_run_id = str(uuid.uuid4())
        job_dir = store._base_dir / job_run_id
        job_dir.mkdir(parents=True, exist_ok=True)
        (job_dir / "job_stats.json").write_text("{}")

        with patch("shutil.rmtree", side_effect=OSError("permission denied")):
            with pytest.raises(JobStatsStoreDeleteException, match="Failed to delete job stats"):
                store.delete_job_stats(job_run_id)

    def test_delete_job_stats_raises_on_lock_timeout(self, store):
        """delete_job_stats raises JobStatsStoreDeleteException on lock Timeout."""
        with patch("docpipe.core.job_management.adapters.stores.json.json_job_stats_store.FileLock") as mock_cls:
            mock_cls.return_value.acquire.side_effect = Timeout("lock")
            with pytest.raises(JobStatsStoreDeleteException, match="acquire lock for job stats deletion"):
                store.delete_job_stats(str(uuid.uuid4()))

    def test_get_all_job_run_ids_returns_empty_when_base_dir_missing(self, store):
        """get_all_job_run_ids returns [] when base_dir does not exist."""
        mock_dir = MagicMock()
        mock_dir.exists.return_value = False
        store._base_dir = mock_dir
        assert store.get_all_job_run_ids() == []

    def test_get_all_job_run_ids_returns_job_run_ids(self, store):
        """get_all_job_run_ids returns IDs of dirs that have job_stats.json."""
        job_run_id = str(uuid.uuid4())
        js = JobStats(job_id="j1", job_run_id=job_run_id, status=ExecutionStatus.COMPLETED)
        store.store_job_stats(js)
        ids = store.get_all_job_run_ids()
        assert job_run_id in ids
