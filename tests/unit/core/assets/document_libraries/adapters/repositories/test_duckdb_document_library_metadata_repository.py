"""Unit tests for DuckDBDocumentLibraryMetadataRepository.

Verifies that the adapter uses KeyValueStoragePort exclusively —
no junction table, no direct SQL. document_set_ids is stored as
a plain list field inside the JSON record.
"""

from unittest.mock import MagicMock

import pytest

from docpipe.core.assets.document_libraries.adapters.duckdb.metadata_repository import (
    DuckDBDocumentLibraryMetadataRepository,
)
from docpipe.core.assets.document_libraries.domain.models.document_library import DocumentLibrary
from docpipe.exceptions.docpipe_exceptions import DocpipeException

# ── FIXTURES ────────────────────────────────────────────────────────────────


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
def repo(mock_storage: MagicMock) -> DuckDBDocumentLibraryMetadataRepository:
    """Repository instance with mocked storage."""
    return DuckDBDocumentLibraryMetadataRepository(
        key_value_storage=mock_storage,
        database_path="data/test.duckdb",
    )


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
    """Build the expected storage record dict for a library."""
    return {
        "library_id": library.library_id,
        "name": library.name,
        "description": library.description,
        "purpose": library.purpose,
        "original_size": library.original_size,
        "final_size": library.final_size,
        "tags": library.tags or [],
        "created_by": library.created_by,
        "href": library.href,
        "document_set_ids": library.document_set_ids or [],
    }


# ── INIT ─────────────────────────────────────────────────────────────────────


class TestInit:
    def test_no_junction_table_initialization(self, mock_storage: MagicMock) -> None:
        """__init__ must NOT create a junction table or open any raw SQL connection."""
        DuckDBDocumentLibraryMetadataRepository(
            key_value_storage=mock_storage,
            database_path="data/test.duckdb",
        )
        # Only legitimate call is none — storage should not be touched during init
        mock_storage.assert_not_called()


# ── CREATE ────────────────────────────────────────────────────────────────────


class TestCreate:
    def test_create_saves_document_set_ids_in_record(
        self, repo: DuckDBDocumentLibraryMetadataRepository, mock_storage: MagicMock, library_with_sets: DocumentLibrary
    ) -> None:
        """document_set_ids must be stored inside the KV record, not a separate table."""
        repo.create(library=library_with_sets)

        mock_storage.save_record.assert_called_once_with(
            collection="document_libraries",
            key=library_with_sets.library_id,
            data=_record_for(library_with_sets),
        )
        saved_data = mock_storage.save_record.call_args.kwargs["data"]
        assert saved_data["document_set_ids"] == ["set-1", "set-2"]

    def test_create_raises_if_id_already_exists(
        self, repo: DuckDBDocumentLibraryMetadataRepository, mock_storage: MagicMock, sample_library: DocumentLibrary
    ) -> None:
        mock_storage.record_exists.return_value = True
        with pytest.raises(DocpipeException, match="already exists"):
            repo.create(library=sample_library)
        mock_storage.save_record.assert_not_called()

    def test_create_raises_if_name_already_exists(
        self, repo: DuckDBDocumentLibraryMetadataRepository, mock_storage: MagicMock, sample_library: DocumentLibrary
    ) -> None:
        mock_storage.record_exists.return_value = False
        mock_storage.list_records.return_value = [{"name": sample_library.name}]
        with pytest.raises(DocpipeException, match="already exists"):
            repo.create(library=sample_library)
        mock_storage.save_record.assert_not_called()


# ── GET BY ID ────────────────────────────────────────────────────────────────


class TestGetById:
    def test_returns_library_with_document_set_ids(
        self, repo: DuckDBDocumentLibraryMetadataRepository, mock_storage: MagicMock, library_with_sets: DocumentLibrary
    ) -> None:
        """document_set_ids must be read from the KV record, not a junction query."""
        mock_storage.get_record.return_value = _record_for(library_with_sets)

        result = repo.get_by_id(library_id=library_with_sets.library_id)

        assert result is not None
        assert result.document_set_ids == ["set-1", "set-2"]
        # Only one storage call — no junction table lookup
        mock_storage.get_record.assert_called_once_with(
            collection="document_libraries",
            key=library_with_sets.library_id,
        )

    def test_returns_none_when_not_found(
        self, repo: DuckDBDocumentLibraryMetadataRepository, mock_storage: MagicMock
    ) -> None:
        mock_storage.get_record.return_value = None
        assert repo.get_by_id(library_id="missing") is None

    def test_returns_empty_document_set_ids_when_missing_from_record(
        self, repo: DuckDBDocumentLibraryMetadataRepository, mock_storage: MagicMock, sample_library: DocumentLibrary
    ) -> None:
        """Records that pre-date this change (no document_set_ids field) default to []."""
        record = _record_for(sample_library)
        del record["document_set_ids"]
        mock_storage.get_record.return_value = record

        result = repo.get_by_id(library_id=sample_library.library_id)

        assert result is not None
        assert result.document_set_ids == []


# ── GET BY NAME ───────────────────────────────────────────────────────────────


class TestGetByName:
    def test_returns_library_with_document_set_ids(
        self, repo: DuckDBDocumentLibraryMetadataRepository, mock_storage: MagicMock, library_with_sets: DocumentLibrary
    ) -> None:
        mock_storage.list_records.return_value = [_record_for(library_with_sets)]

        result = repo.get_by_name(name=library_with_sets.name)

        assert result is not None
        assert result.document_set_ids == ["set-1", "set-2"]

    def test_returns_none_when_not_found(
        self, repo: DuckDBDocumentLibraryMetadataRepository, mock_storage: MagicMock
    ) -> None:
        mock_storage.list_records.return_value = []
        assert repo.get_by_name(name="nonexistent") is None


# ── UPDATE ────────────────────────────────────────────────────────────────────


class TestUpdate:
    def test_update_persists_document_set_ids_in_record(
        self, repo: DuckDBDocumentLibraryMetadataRepository, mock_storage: MagicMock, library_with_sets: DocumentLibrary
    ) -> None:
        mock_storage.record_exists.return_value = True

        repo.update(library=library_with_sets)

        saved_data = mock_storage.save_record.call_args.kwargs["data"]
        assert saved_data["document_set_ids"] == ["set-1", "set-2"]

    def test_update_raises_if_not_found(
        self, repo: DuckDBDocumentLibraryMetadataRepository, mock_storage: MagicMock, sample_library: DocumentLibrary
    ) -> None:
        mock_storage.record_exists.return_value = False
        with pytest.raises(DocpipeException, match="not found"):
            repo.update(library=sample_library)


# ── DELETE ────────────────────────────────────────────────────────────────────


class TestDelete:
    def test_delete_uses_only_kv_storage(
        self, repo: DuckDBDocumentLibraryMetadataRepository, mock_storage: MagicMock
    ) -> None:
        """delete() must only call KV storage — no junction table SQL."""
        mock_storage.delete_record.return_value = True

        result = repo.delete(library_id="lib-abc")

        assert result is True
        mock_storage.delete_record.assert_called_once_with(collection="document_libraries", key="lib-abc")
        # Ensure no raw SQL connection was opened
        assert not hasattr(repo, "_connection_manager")

    def test_delete_returns_false_when_not_found(
        self, repo: DuckDBDocumentLibraryMetadataRepository, mock_storage: MagicMock
    ) -> None:
        mock_storage.delete_record.return_value = False
        assert repo.delete(library_id="missing") is False


# ── LIST ALL ──────────────────────────────────────────────────────────────────


class TestListAll:
    def test_list_all_includes_document_set_ids(
        self, repo: DuckDBDocumentLibraryMetadataRepository, mock_storage: MagicMock, library_with_sets: DocumentLibrary
    ) -> None:
        mock_storage.list_records.return_value = [_record_for(library_with_sets)]

        results = repo.list_all()

        assert len(results) == 1
        assert results[0].document_set_ids == ["set-1", "set-2"]

    def test_list_all_pagination(self, repo: DuckDBDocumentLibraryMetadataRepository, mock_storage: MagicMock) -> None:
        records = [{"library_id": f"lib-{i}", "name": f"Library {i}", "document_set_ids": []} for i in range(5)]
        mock_storage.list_records.return_value = records

        results = repo.list_all(offset=1, limit=2)

        assert len(results) == 2


# ── DOCUMENT SET RELATIONSHIP ─────────────────────────────────────────────────


class TestDocumentSetRelationship:
    def test_add_document_set_stores_in_record(
        self, repo: DuckDBDocumentLibraryMetadataRepository, mock_storage: MagicMock, sample_library: DocumentLibrary
    ) -> None:
        """Adding a document set mutates the record — no junction INSERT."""
        mock_storage.get_record.return_value = _record_for(sample_library)
        mock_storage.record_exists.return_value = True

        repo.add_document_set_to_library(
            library_id=sample_library.library_id,
            document_set_id="new-set",
        )

        saved_data = mock_storage.save_record.call_args.kwargs["data"]
        assert "new-set" in saved_data["document_set_ids"]

    def test_remove_document_set_updates_record(
        self, repo: DuckDBDocumentLibraryMetadataRepository, mock_storage: MagicMock, library_with_sets: DocumentLibrary
    ) -> None:
        """Removing a document set mutates the record — no junction DELETE."""
        mock_storage.get_record.return_value = _record_for(library_with_sets)
        mock_storage.record_exists.return_value = True

        repo.remove_document_set_from_library(
            library_id=library_with_sets.library_id,
            document_set_id="set-1",
        )

        saved_data = mock_storage.save_record.call_args.kwargs["data"]
        assert "set-1" not in saved_data["document_set_ids"]
        assert "set-2" in saved_data["document_set_ids"]

    def test_get_document_sets_reads_from_record(
        self, repo: DuckDBDocumentLibraryMetadataRepository, mock_storage: MagicMock, library_with_sets: DocumentLibrary
    ) -> None:
        """get_document_sets_for_library reads from the KV record, not a junction query."""
        mock_storage.get_record.return_value = _record_for(library_with_sets)

        result = repo.get_document_sets_for_library(library_id=library_with_sets.library_id)

        assert result == ["set-1", "set-2"]
        # Only one storage call — get_record
        mock_storage.get_record.assert_called_once()

    def test_add_duplicate_document_set_raises(
        self, repo: DuckDBDocumentLibraryMetadataRepository, mock_storage: MagicMock, library_with_sets: DocumentLibrary
    ) -> None:
        mock_storage.get_record.return_value = _record_for(library_with_sets)

        with pytest.raises(DocpipeException, match="already exists"):
            repo.add_document_set_to_library(
                library_id=library_with_sets.library_id,
                document_set_id="set-1",  # already present
            )

    def test_remove_nonexistent_document_set_raises(
        self, repo: DuckDBDocumentLibraryMetadataRepository, mock_storage: MagicMock, sample_library: DocumentLibrary
    ) -> None:
        mock_storage.get_record.return_value = _record_for(sample_library)

        with pytest.raises(DocpipeException):
            repo.remove_document_set_from_library(
                library_id=sample_library.library_id,
                document_set_id="nonexistent",
            )

    def test_add_document_sets_bulk_single_update(
        self, repo: DuckDBDocumentLibraryMetadataRepository, mock_storage: MagicMock, sample_library: DocumentLibrary
    ) -> None:
        """Bulk add does ONE get + ONE save — not N gets + N saves."""
        mock_storage.get_record.return_value = _record_for(sample_library)
        mock_storage.record_exists.return_value = True

        repo.add_document_sets_bulk(
            library_id=sample_library.library_id,
            document_set_ids=["set-a", "set-b", "set-c"],
        )

        assert mock_storage.get_record.call_count == 1  # load once
        assert mock_storage.save_record.call_count == 1  # save once
        saved_data = mock_storage.save_record.call_args.kwargs["data"]
        assert saved_data["document_set_ids"] == ["set-a", "set-b", "set-c"]

    def test_remove_document_sets_bulk_single_update(
        self, repo: DuckDBDocumentLibraryMetadataRepository, mock_storage: MagicMock, library_with_sets: DocumentLibrary
    ) -> None:
        """Bulk remove does ONE get + ONE save — not N gets + N saves."""
        mock_storage.get_record.return_value = _record_for(library_with_sets)
        mock_storage.record_exists.return_value = True

        repo.remove_document_sets_bulk(
            library_id=library_with_sets.library_id,
            document_set_ids=["set-1", "set-2"],
        )

        assert mock_storage.get_record.call_count == 1
        assert mock_storage.save_record.call_count == 1
        saved_data = mock_storage.save_record.call_args.kwargs["data"]
        assert saved_data["document_set_ids"] == []

    def test_add_document_sets_bulk_empty_list_is_noop(
        self, repo: DuckDBDocumentLibraryMetadataRepository, mock_storage: MagicMock
    ) -> None:
        repo.add_document_sets_bulk(library_id="lib-abc", document_set_ids=[])
        mock_storage.get_record.assert_not_called()
        mock_storage.save_record.assert_not_called()

    def test_remove_document_sets_bulk_empty_list_is_noop(
        self, repo: DuckDBDocumentLibraryMetadataRepository, mock_storage: MagicMock
    ) -> None:
        repo.remove_document_sets_bulk(library_id="lib-abc", document_set_ids=[])
        mock_storage.get_record.assert_not_called()
        mock_storage.save_record.assert_not_called()


# ── COUNT / HEALTH ────────────────────────────────────────────────────────────


class TestCountAndHealth:
    def test_count_all(self, repo: DuckDBDocumentLibraryMetadataRepository, mock_storage: MagicMock) -> None:
        mock_storage.list_records.return_value = [{}, {}, {}]
        assert repo.count_all() == 3

    def test_health_check_healthy(self, repo: DuckDBDocumentLibraryMetadataRepository, mock_storage: MagicMock) -> None:
        mock_storage.collection_exists.return_value = True
        result = repo.health_check()
        assert result["healthy"] is True
        assert "junction_table" not in str(result.get("details"))

    def test_health_check_unhealthy_on_error(
        self, repo: DuckDBDocumentLibraryMetadataRepository, mock_storage: MagicMock
    ) -> None:
        mock_storage.collection_exists.side_effect = RuntimeError("DB down")
        result = repo.health_check()
        assert result["healthy"] is False


# ── NO DIRECT SQL ANYWHERE ────────────────────────────────────────────────────


class TestNoDirectSQL:
    def test_repo_has_no_connection_manager(self, repo: DuckDBDocumentLibraryMetadataRepository) -> None:
        """The adapter must not hold a DuckDBConnectionManager — no raw SQL."""
        assert not hasattr(repo, "_connection_manager")

    def test_validate_config_valid(self) -> None:
        errors = DuckDBDocumentLibraryMetadataRepository.validate_config(config={"database_path": "data/test.duckdb"})
        assert errors == []

    def test_validate_config_missing_path(self) -> None:
        errors = DuckDBDocumentLibraryMetadataRepository.validate_config(config={})
        assert len(errors) == 1
        assert "database_path" in errors[0]

    def test_validate_config_empty_path(self) -> None:
        errors = DuckDBDocumentLibraryMetadataRepository.validate_config(config={"database_path": ""})
        assert len(errors) == 1
