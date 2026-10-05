"""Unit tests for DuckDBDocumentLibraryMetadataRepository (adapters/duckdb/).

Verifies that add_document_set_to_library and add_document_sets_bulk pass
timezone-aware UTC timestamps into the junction table — covering the
datetime.now(UTC) fix at metadata_repository.py:400 and :559.

This class uses:
  __init__(self, *, key_value_storage: KeyValueStorage, database_path: str)
  Junction-table SQL: self._connection_manager.get_connection(...) -> conn.execute(query, params)
  Existence check:   self.storage.record_exists(...)
"""

from unittest.mock import MagicMock, patch

import pytest

import docpipe.core.assets.document_libraries.adapters.duckdb.metadata_repository as repo_module
from docpipe.core.assets.document_libraries.adapters.duckdb.metadata_repository import (
    DuckDBDocumentLibraryMetadataRepository,
)


def _make_repo(mock_conn: MagicMock) -> DuckDBDocumentLibraryMetadataRepository:
    """Instantiate DuckDBDocumentLibraryMetadataRepository with all I/O mocked.

    DuckDBConnectionManager is patched at module level so _initialize_junction_table()
    runs without a real DB. mock_conn is reset afterwards so tests start clean.
    """
    key_value_storage = MagicMock()
    key_value_storage.record_exists.return_value = True  # exists() passes

    mock_connection_manager = MagicMock()
    mock_connection_manager.get_connection.return_value.__enter__.return_value = mock_conn

    with patch.object(repo_module, "DuckDBConnectionManager", return_value=mock_connection_manager):
        repo = DuckDBDocumentLibraryMetadataRepository(
            key_value_storage=key_value_storage,
            database_path="data/test.duckdb",
        )

    # _initialize_junction_table() called conn.execute() 3x (CREATE TABLE + 2 indexes)
    # reset so individual tests see only their own calls.
    mock_conn.reset_mock()
    return repo


class TestAddDocumentSetTimestamp:
    """Verify add_document_set_to_library and add_document_sets_bulk pass
    timezone-aware UTC timestamps into the junction table.

    Targets adapters/duckdb/metadata_repository.py which routes junction-table
    SQL through _connection_manager.get_connection() -> conn.execute(query, params).
    """

    @pytest.fixture
    def mock_conn(self) -> MagicMock:
        """Mock DuckDB connection yielded by the connection manager's context manager."""
        conn = MagicMock()
        conn.execute.return_value = None
        return conn

    @pytest.fixture
    def lib_repo(self, mock_conn: MagicMock) -> DuckDBDocumentLibraryMetadataRepository:
        return _make_repo(mock_conn)

    def test_add_document_set_passes_timezone_aware_timestamp(
        self, lib_repo: DuckDBDocumentLibraryMetadataRepository, mock_conn: MagicMock
    ) -> None:
        """add_document_set_to_library must insert a timezone-aware UTC timestamp."""
        lib_repo.add_document_set_to_library(library_id="lib-1", document_set_id="ds-1")

        mock_conn.execute.assert_called_once()
        # conn.execute(query, (library_id, document_set_id, timestamp))
        params = mock_conn.execute.call_args.args[1]
        timestamp = params[2]

        assert timestamp.tzinfo is not None, "added_at must be timezone-aware"
        assert timestamp.utcoffset().total_seconds() == 0

    def test_bulk_add_document_sets_passes_timezone_aware_timestamp(
        self, lib_repo: DuckDBDocumentLibraryMetadataRepository, mock_conn: MagicMock
    ) -> None:
        """add_document_sets_bulk must insert timezone-aware UTC timestamps for all rows."""
        lib_repo.add_document_sets_bulk(library_id="lib-1", document_set_ids=["ds-1", "ds-2"])

        mock_conn.execute.assert_called_once()
        # Flat params tuple: (lib_id, ds_id, timestamp) * n_sets
        params = mock_conn.execute.call_args.args[1]

        # Timestamps are at indices 2, 5, ...
        timestamps = [params[i] for i in range(2, len(params), 3)]
        assert len(timestamps) == 2
        for ts in timestamps:
            assert ts.tzinfo is not None, "added_at must be timezone-aware"
            assert ts.utcoffset().total_seconds() == 0

    def test_bulk_add_empty_list_is_noop(
        self, lib_repo: DuckDBDocumentLibraryMetadataRepository, mock_conn: MagicMock
    ) -> None:
        """Bulk add with an empty list must not call conn.execute."""
        lib_repo.add_document_sets_bulk(library_id="lib-1", document_set_ids=[])

        mock_conn.execute.assert_not_called()

    def test_add_document_set_raises_when_library_not_found(
        self, lib_repo: DuckDBDocumentLibraryMetadataRepository, mock_conn: MagicMock
    ) -> None:
        """add_document_set_to_library must raise DocpipeException(404) when library is absent."""
        from docpipe.exceptions.docpipe_exceptions import DocpipeException

        lib_repo.storage.record_exists.return_value = False  # exists() → False
        with pytest.raises(DocpipeException, match="not found"):
            lib_repo.add_document_set_to_library(library_id="bad-id", document_set_id="ds-1")
        mock_conn.execute.assert_not_called()

    def test_bulk_add_raises_when_library_not_found(
        self, lib_repo: DuckDBDocumentLibraryMetadataRepository, mock_conn: MagicMock
    ) -> None:
        """add_document_sets_bulk must raise DocpipeException(404) when library is absent."""
        from docpipe.exceptions.docpipe_exceptions import DocpipeException

        lib_repo.storage.record_exists.return_value = False  # exists() → False
        with pytest.raises(DocpipeException, match="not found"):
            lib_repo.add_document_sets_bulk(library_id="bad-id", document_set_ids=["ds-1"])
        mock_conn.execute.assert_not_called()
