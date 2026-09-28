"""Tests for DuckDBConnectionManager — new methods from micro-batch concurrency fix.

All tests use patch to prevent any real DuckDB connection from being opened.
"""

from unittest.mock import MagicMock, patch

import pytest

from docpipe.utils.duckdb.connection_manager import DuckDBConnectionManager

_PATCH = "docpipe.utils.duckdb.connection_manager.duckdb.connect"


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the singleton before and after each test for isolation."""
    DuckDBConnectionManager.reset_instance()
    yield
    DuckDBConnectionManager.reset_instance()


@pytest.fixture
def manager():
    """Return a clean singleton manager."""
    return DuckDBConnectionManager()


class TestPerPathLock:
    def test_same_path_returns_same_lock(self, tmp_path, manager):
        path = str(tmp_path / "a.duckdb")
        assert manager._get_file_lock(path) is manager._get_file_lock(path)

    def test_different_paths_return_different_locks(self, tmp_path, manager):
        assert manager._get_file_lock(str(tmp_path / "a.duckdb")) is not manager._get_file_lock(
            str(tmp_path / "b.duckdb")
        )

    def test_lock_released_after_normal_use(self, tmp_path, manager):
        path = str(tmp_path / "a.duckdb")
        with patch(_PATCH, return_value=MagicMock()):
            with manager.get_connection(path):
                pass
        lock = manager._get_file_lock(path)
        acquired = lock.acquire(blocking=False)
        assert acquired, "Lock not released after normal exit"
        lock.release()

    def test_lock_released_when_close_raises(self, tmp_path, manager):
        """Lines 81-82: conn.close() raises — lock must still be released."""
        mock_conn = MagicMock()
        mock_conn.close.side_effect = Exception("close failed")
        path = str(tmp_path / "a.duckdb")
        with patch(_PATCH, return_value=mock_conn):
            with manager.get_connection(path):
                pass
        lock = manager._get_file_lock(path)
        acquired = lock.acquire(blocking=False)
        assert acquired, "Lock not released after conn.close() error"
        lock.release()


class TestCloseAll:
    def test_closes_injected_connection_and_clears_connections(self, manager):
        """close_all closes every persistent connection and clears _connections.

        _file_locks is intentionally kept alive — clearing it while a thread
        holds a per-path lock would create a new lock for the same path and
        silently break serialization.
        """
        mock_conn = MagicMock()
        sentinel_key = "__test_close_all__"
        manager._connections[sentinel_key] = mock_conn

        manager.close_all()

        mock_conn.close.assert_called_once()
        assert sentinel_key not in manager._connections

    def test_close_error_does_not_propagate(self, manager):
        """Lines 92-93: exception in close() is swallowed."""
        mock_conn = MagicMock()
        mock_conn.close.side_effect = Exception("boom")
        manager._connections["__test_err__"] = mock_conn

        manager.close_all()  # must not raise
