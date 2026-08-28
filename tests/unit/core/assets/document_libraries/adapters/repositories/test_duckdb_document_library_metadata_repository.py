"""Unit tests for DuckDBAssetRepository[DocumentLibrary].

Verifies that the base generic repository works correctly for DocumentLibrary:
- CRUD via KeyValueStoragePort
- document_set_ids stored as a plain list inside the JSON record
- validate_config() on the base class
"""

from unittest.mock import MagicMock

import pytest

from docpipe.core.assets.common.adapters.repositories.duckdb_asset_repository import DuckDBAssetRepository
from docpipe.core.assets.document_libraries.domain.models.document_library import DocumentLibrary
from docpipe.exceptions.docpipe_exceptions import DocpipeException

_COLLECTION = "document_libraries"


# ── FIXTURES ──────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_storage() -> MagicMock:
    """Mock KeyValueStoragePort."""
    storage = MagicMock()
    storage.record_exists.return_value = False
    storage.get_record.return_value = None
    storage.list_records.return_value = []
    storage.save_record.return_value = None
    storage.delete_record.return_value = True
    storage.collection_exists.return_value = True
    return storage


@pytest.fixture
def repo(mock_storage: MagicMock) -> DuckDBAssetRepository:
    """DuckDBAssetRepository[DocumentLibrary] with pinned collection."""
    r = DuckDBAssetRepository(
        asset_type=DocumentLibrary,
        key_value_storage=mock_storage,
        database_path="data/test.duckdb",
    )
    r._collection = _COLLECTION
    return r


@pytest.fixture
def sample_library() -> DocumentLibrary:
    """Simple DocumentLibrary with no document sets."""
    return DocumentLibrary.create(name="Test Library", description="A test library")


@pytest.fixture
def library_with_sets() -> DocumentLibrary:
    """DocumentLibrary pre-loaded with document set IDs."""
    lib = DocumentLibrary.create(name="Library With Sets")
    lib.add_document_set(document_set_id="set-1")
    lib.add_document_set(document_set_id="set-2")
    return lib


def _record_for(library: DocumentLibrary) -> dict:
    return library.to_dict()


# ── INIT ──────────────────────────────────────────────────────────────────────


class TestInit:
    def test_no_extra_storage_calls_on_init(self, mock_storage: MagicMock) -> None:
        """__init__ must not touch storage."""
        r = DuckDBAssetRepository(
            asset_type=DocumentLibrary,
            key_value_storage=mock_storage,
            database_path="data/test.duckdb",
        )
        r._collection = _COLLECTION
        mock_storage.assert_not_called()


# ── SAVE ──────────────────────────────────────────────────────────────────────


class TestSave:
    def test_save_persists_document_set_ids_in_record(
        self, repo: DuckDBAssetRepository, mock_storage: MagicMock, library_with_sets: DocumentLibrary
    ) -> None:
        """document_set_ids must be stored inside the KV record."""
        repo.save(asset=library_with_sets)

        mock_storage.save_record.assert_called_once_with(
            collection=_COLLECTION,
            key=library_with_sets.library_id,
            data=_record_for(library_with_sets),
        )
        saved_data = mock_storage.save_record.call_args.kwargs["data"]
        assert saved_data["document_set_ids"] == ["set-1", "set-2"]

    def test_save_raises_if_id_already_exists(
        self, repo: DuckDBAssetRepository, mock_storage: MagicMock, sample_library: DocumentLibrary
    ) -> None:
        mock_storage.record_exists.return_value = True
        with pytest.raises(DocpipeException, match="already exists"):
            repo.save(asset=sample_library)
        mock_storage.save_record.assert_not_called()

    def test_save_raises_if_name_already_exists(
        self, repo: DuckDBAssetRepository, mock_storage: MagicMock, sample_library: DocumentLibrary
    ) -> None:
        mock_storage.record_exists.return_value = False
        mock_storage.list_records.return_value = [{"name": sample_library.name}]
        with pytest.raises(DocpipeException, match="already exists"):
            repo.save(asset=sample_library)
        mock_storage.save_record.assert_not_called()


# ── FIND BY ID ────────────────────────────────────────────────────────────────


class TestFindById:
    def test_returns_library_with_document_set_ids(
        self, repo: DuckDBAssetRepository, mock_storage: MagicMock, library_with_sets: DocumentLibrary
    ) -> None:
        """document_set_ids must be read from the KV record."""
        mock_storage.get_record.return_value = _record_for(library_with_sets)

        result = repo.find_by_id(asset_id=library_with_sets.library_id)

        assert result is not None
        assert result.document_set_ids == ["set-1", "set-2"]
        mock_storage.get_record.assert_called_once_with(
            collection=_COLLECTION,
            key=library_with_sets.library_id,
        )

    def test_returns_none_when_not_found(self, repo: DuckDBAssetRepository, mock_storage: MagicMock) -> None:
        mock_storage.get_record.return_value = None
        assert repo.find_by_id(asset_id="missing") is None

    def test_returns_empty_document_set_ids_when_missing_from_record(
        self, repo: DuckDBAssetRepository, mock_storage: MagicMock, sample_library: DocumentLibrary
    ) -> None:
        """Records that pre-date this change (no document_set_ids field) default to []."""
        record = _record_for(sample_library)
        del record["document_set_ids"]
        mock_storage.get_record.return_value = record

        result = repo.find_by_id(asset_id=sample_library.library_id)

        assert result is not None
        assert result.document_set_ids == []


# ── FIND BY NAME ──────────────────────────────────────────────────────────────


class TestFindByName:
    def test_returns_library_with_document_set_ids(
        self, repo: DuckDBAssetRepository, mock_storage: MagicMock, library_with_sets: DocumentLibrary
    ) -> None:
        mock_storage.list_records.return_value = [_record_for(library_with_sets)]

        result = repo.find_by_name(name=library_with_sets.name)

        assert result is not None
        assert result.document_set_ids == ["set-1", "set-2"]

    def test_returns_none_when_not_found(self, repo: DuckDBAssetRepository, mock_storage: MagicMock) -> None:
        mock_storage.list_records.return_value = []
        assert repo.find_by_name(name="nonexistent") is None


# ── UPDATE ────────────────────────────────────────────────────────────────────


class TestUpdate:
    def test_update_persists_document_set_ids_in_record(
        self, repo: DuckDBAssetRepository, mock_storage: MagicMock, library_with_sets: DocumentLibrary
    ) -> None:
        mock_storage.record_exists.return_value = True

        repo.update(asset=library_with_sets)

        saved_data = mock_storage.save_record.call_args.kwargs["data"]
        assert saved_data["document_set_ids"] == ["set-1", "set-2"]

    def test_update_raises_if_not_found(
        self, repo: DuckDBAssetRepository, mock_storage: MagicMock, sample_library: DocumentLibrary
    ) -> None:
        mock_storage.record_exists.return_value = False
        with pytest.raises(DocpipeException, match="not found"):
            repo.update(asset=sample_library)


# ── DELETE ────────────────────────────────────────────────────────────────────


class TestDelete:
    def test_delete_uses_only_kv_storage(self, repo: DuckDBAssetRepository, mock_storage: MagicMock) -> None:
        """delete() must only call KV storage — no junction table SQL."""
        mock_storage.delete_record.return_value = True

        result = repo.delete(asset_id="lib-abc")

        assert result is True
        mock_storage.delete_record.assert_called_once_with(collection=_COLLECTION, key="lib-abc")
        assert not hasattr(repo, "_connection_manager")

    def test_delete_returns_false_when_not_found(self, repo: DuckDBAssetRepository, mock_storage: MagicMock) -> None:
        mock_storage.delete_record.return_value = False
        assert repo.delete(asset_id="missing") is False


# ── LIST ALL ──────────────────────────────────────────────────────────────────


class TestListAll:
    def test_list_all_includes_document_set_ids(
        self, repo: DuckDBAssetRepository, mock_storage: MagicMock, library_with_sets: DocumentLibrary
    ) -> None:
        mock_storage.list_records.return_value = [_record_for(library_with_sets)]

        results = repo.list_all()

        assert len(results) == 1
        assert results[0].document_set_ids == ["set-1", "set-2"]

    def test_list_all_pagination(self, repo: DuckDBAssetRepository, mock_storage: MagicMock) -> None:
        records = [{"library_id": f"lib-{i}", "name": f"Library {i}", "document_set_ids": []} for i in range(5)]
        mock_storage.list_records.return_value = records

        results = repo.list_all(offset=1, limit=2)

        assert len(results) == 2


# ── HEALTH CHECK & VALIDATE CONFIG ───────────────────────────────────────────


class TestCountAndHealth:
    def test_health_check_healthy(self, repo: DuckDBAssetRepository, mock_storage: MagicMock) -> None:
        result = repo.health_check()
        assert result["status"] == "healthy"
        assert result["details"]["database_path"] == "data/test.duckdb"

    def test_health_check_unhealthy_on_error(self, repo: DuckDBAssetRepository, mock_storage: MagicMock) -> None:
        mock_storage.collection_exists.side_effect = RuntimeError("disk full")
        result = repo.health_check()
        assert result["status"] == "unhealthy"


class TestNoDirectSQL:
    def test_repo_has_no_connection_manager(self, repo: DuckDBAssetRepository) -> None:
        assert not hasattr(repo, "_connection_manager")

    def test_validate_config_valid(self) -> None:
        assert DuckDBAssetRepository.validate_config(config={"database_path": "test.db"}) == []

    def test_validate_config_missing_path(self) -> None:
        assert DuckDBAssetRepository.validate_config(config={}) == ["Missing required configuration: 'database_path'"]

    def test_validate_config_empty_path(self) -> None:
        assert DuckDBAssetRepository.validate_config(config={"database_path": ""}) == [
            "Configuration 'database_path' cannot be empty"
        ]
