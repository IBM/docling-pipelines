"""Unit tests for DuckDBAttachmentRepository.

Coverage:
- validate_config() — all three error paths + valid case
- create() classmethod — happy path and storage-failure wrapping
- save() — persist and overwrite (upsert)
- get() — present, absent, and storage-error propagation
- delete() — existing record, absent record, and storage-error propagation
- exists() — before and after save, and storage-error propagation
"""

from unittest.mock import MagicMock, patch

import pytest

from docpipe.core.assets.common.adapters.repositories.duckdb_attachment_repository import (
    DuckDBAttachmentRepository,
)
from docpipe.core.assets.common.domain.models.attachment_ref import AttachmentRef
from docpipe.exceptions.docpipe_exceptions import DocpipeException
from docpipe.exceptions.error_codes import ErrorCode
from docpipe.storage import StorageFactory

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def temp_db_path(tmp_path):
    return str(tmp_path / "attachments.db")


@pytest.fixture
def repo(temp_db_path):
    """Real DuckDB-backed repository — exercises the full storage stack."""
    kv = StorageFactory.create_key_value_storage(storage_type="duckdb", database_path=temp_db_path)
    return DuckDBAttachmentRepository(key_value_storage=kv, database_path=temp_db_path)


@pytest.fixture
def mock_storage():
    """Isolated mock storage for error-propagation tests."""
    return MagicMock()


@pytest.fixture
def repo_with_mock(mock_storage, temp_db_path):
    return DuckDBAttachmentRepository(key_value_storage=mock_storage, database_path=temp_db_path)


@pytest.fixture
def sample_ref():
    return AttachmentRef(
        backend_type="duckdb",
        name="my_table",
        details={"database_path": "/data/test.db", "table_name": "my_table"},
    )


# ---------------------------------------------------------------------------
# validate_config
# ---------------------------------------------------------------------------


class TestValidateConfig:
    """validate_config() must surface all invalid configurations."""

    def test_valid_config_returns_no_errors(self):
        assert DuckDBAttachmentRepository.validate_config(config={"database_path": "test.db"}) == []

    def test_missing_database_path_returns_error(self):
        errors = DuckDBAttachmentRepository.validate_config(config={})
        assert len(errors) == 1
        assert "database_path" in errors[0]
        assert "Missing" in errors[0]

    def test_non_string_database_path_returns_error(self):
        errors = DuckDBAttachmentRepository.validate_config(config={"database_path": 42})
        assert len(errors) == 1
        assert "must be a string" in errors[0]

    def test_empty_string_database_path_returns_error(self):
        errors = DuckDBAttachmentRepository.validate_config(config={"database_path": ""})
        assert len(errors) == 1
        assert "cannot be empty" in errors[0]


# ---------------------------------------------------------------------------
# create() classmethod
# ---------------------------------------------------------------------------


class TestCreate:
    """create() is the factory entry-point used by AttachmentRepositoryFactory."""

    def test_create_returns_instance(self, temp_db_path):
        repo = DuckDBAttachmentRepository.create(config={"database_path": temp_db_path})
        assert isinstance(repo, DuckDBAttachmentRepository)
        assert repo._database_path == temp_db_path

    def test_create_with_in_memory_database(self):
        repo = DuckDBAttachmentRepository.create(config={"database_path": ":memory:"})
        assert isinstance(repo, DuckDBAttachmentRepository)

    def test_create_wraps_unexpected_exceptions_in_docpipe_exception(self):
        with patch(
            "docpipe.core.assets.common.adapters.repositories.duckdb_attachment_repository.StorageFactory.create_key_value_storage",
            side_effect=RuntimeError("disk full"),
        ):
            with pytest.raises(DocpipeException) as exc_info:
                DuckDBAttachmentRepository.create(config={"database_path": "/bad/path.db"})

        assert exc_info.value.status_code == 500
        assert exc_info.value.error_code == ErrorCode.DOCUMENT_SET_REPOSITORY_ERROR

    def test_create_reraises_docpipe_exception_unchanged(self):
        original = DocpipeException("already a docpipe error", status_code=400)
        with patch(
            "docpipe.core.assets.common.adapters.repositories.duckdb_attachment_repository.StorageFactory.create_key_value_storage",
            side_effect=original,
        ):
            with pytest.raises(DocpipeException) as exc_info:
                DuckDBAttachmentRepository.create(config={"database_path": "/any/path.db"})

        assert exc_info.value is original


# ---------------------------------------------------------------------------
# save()
# ---------------------------------------------------------------------------


class TestSave:
    """save() persists an AttachmentRef; repeated calls overwrite (upsert)."""

    def test_save_delegates_to_storage_with_correct_args(self, repo_with_mock, mock_storage, sample_ref):
        repo_with_mock.save(asset_id="asset-1", data=sample_ref)

        mock_storage.save_record.assert_called_once_with(
            collection=DuckDBAttachmentRepository.COLLECTION_NAME,
            key="asset-1",
            data=sample_ref.to_dict(),
        )

    def test_save_overwrites_existing_record(self, repo, sample_ref):
        """Second save with the same asset_id replaces the first (upsert)."""
        repo.save(asset_id="asset-upsert", data=sample_ref)

        updated_ref = AttachmentRef(backend_type="duckdb", name="updated_table", details={"extra": True})
        repo.save(asset_id="asset-upsert", data=updated_ref)

        retrieved = repo.get(asset_id="asset-upsert")
        assert retrieved is not None
        assert retrieved.name == "updated_table"

    def test_save_wraps_unexpected_exception(self, repo_with_mock, mock_storage, sample_ref):
        mock_storage.save_record.side_effect = OSError("I/O error")

        with pytest.raises(DocpipeException) as exc_info:
            repo_with_mock.save(asset_id="asset-err", data=sample_ref)

        assert exc_info.value.status_code == 500
        assert exc_info.value.error_code == ErrorCode.DOCUMENT_SET_REPOSITORY_ERROR
        assert "asset-err" in str(exc_info.value)

    def test_save_reraises_docpipe_exception(self, repo_with_mock, mock_storage, sample_ref):
        original = DocpipeException("storage locked", status_code=503)
        mock_storage.save_record.side_effect = original

        with pytest.raises(DocpipeException) as exc_info:
            repo_with_mock.save(asset_id="asset-1", data=sample_ref)

        assert exc_info.value is original


# ---------------------------------------------------------------------------
# get()
# ---------------------------------------------------------------------------


class TestGet:
    """get() retrieves a persisted AttachmentRef or returns None."""

    def test_get_returns_attachment_ref_after_save(self, repo, sample_ref):
        repo.save(asset_id="asset-get", data=sample_ref)
        result = repo.get(asset_id="asset-get")

        assert result is not None
        assert result.backend_type == sample_ref.backend_type
        assert result.name == sample_ref.name
        assert result.details == sample_ref.details

    def test_get_returns_none_for_unknown_asset(self, repo):
        assert repo.get(asset_id="does-not-exist") is None

    def test_get_returns_none_after_delete(self, repo, sample_ref):
        repo.save(asset_id="asset-gone", data=sample_ref)
        repo.delete(asset_id="asset-gone")

        assert repo.get(asset_id="asset-gone") is None

    def test_get_preserves_optional_fields(self, repo):
        ref = AttachmentRef(
            backend_type="duckdb",
            name="tbl",
            details={"k": "v"},
            attachment_id="att-123",
            created_at="2025-01-01T00:00:00Z",
        )
        repo.save(asset_id="asset-optional", data=ref)
        result = repo.get(asset_id="asset-optional")

        assert result is not None
        assert result.attachment_id == "att-123"
        assert result.created_at == "2025-01-01T00:00:00Z"

    def test_get_wraps_unexpected_exception(self, repo_with_mock, mock_storage):
        mock_storage.get_record.side_effect = RuntimeError("corrupted db")

        with pytest.raises(DocpipeException) as exc_info:
            repo_with_mock.get(asset_id="asset-err")

        assert exc_info.value.status_code == 500
        assert exc_info.value.error_code == ErrorCode.DOCUMENT_SET_REPOSITORY_ERROR
        assert "asset-err" in str(exc_info.value)

    def test_get_reraises_docpipe_exception(self, repo_with_mock, mock_storage):
        original = DocpipeException("read failed", status_code=503)
        mock_storage.get_record.side_effect = original

        with pytest.raises(DocpipeException) as exc_info:
            repo_with_mock.get(asset_id="asset-1")

        assert exc_info.value is original


# ---------------------------------------------------------------------------
# delete()
# ---------------------------------------------------------------------------


class TestDelete:
    """delete() removes a record and reports whether it existed."""

    def test_delete_returns_true_for_existing_record(self, repo, sample_ref):
        repo.save(asset_id="asset-del", data=sample_ref)
        assert repo.delete(asset_id="asset-del") is True

    def test_delete_returns_false_for_absent_record(self, repo):
        assert repo.delete(asset_id="never-saved") is False

    def test_delete_removes_record_so_get_returns_none(self, repo, sample_ref):
        repo.save(asset_id="asset-remove", data=sample_ref)
        repo.delete(asset_id="asset-remove")
        assert repo.get(asset_id="asset-remove") is None

    def test_delete_wraps_unexpected_exception(self, repo_with_mock, mock_storage):
        mock_storage.delete_record.side_effect = RuntimeError("lock timeout")

        with pytest.raises(DocpipeException) as exc_info:
            repo_with_mock.delete(asset_id="asset-err")

        assert exc_info.value.status_code == 500
        assert exc_info.value.error_code == ErrorCode.DOCUMENT_SET_REPOSITORY_ERROR
        assert "asset-err" in str(exc_info.value)

    def test_delete_reraises_docpipe_exception(self, repo_with_mock, mock_storage):
        original = DocpipeException("delete failed", status_code=500)
        mock_storage.delete_record.side_effect = original

        with pytest.raises(DocpipeException) as exc_info:
            repo_with_mock.delete(asset_id="asset-1")

        assert exc_info.value is original


# ---------------------------------------------------------------------------
# exists()
# ---------------------------------------------------------------------------


class TestExists:
    """exists() reflects the current presence of a record in the store."""

    def test_exists_returns_false_before_save(self, repo):
        assert repo.exists(asset_id="no-record") is False

    def test_exists_returns_true_after_save(self, repo, sample_ref):
        repo.save(asset_id="asset-present", data=sample_ref)
        assert repo.exists(asset_id="asset-present") is True

    def test_exists_returns_false_after_delete(self, repo, sample_ref):
        repo.save(asset_id="asset-deleted", data=sample_ref)
        repo.delete(asset_id="asset-deleted")
        assert repo.exists(asset_id="asset-deleted") is False

    def test_exists_wraps_unexpected_exception(self, repo_with_mock, mock_storage):
        mock_storage.record_exists.side_effect = RuntimeError("connection lost")

        with pytest.raises(DocpipeException) as exc_info:
            repo_with_mock.exists(asset_id="asset-err")

        assert exc_info.value.status_code == 500
        assert exc_info.value.error_code == ErrorCode.DOCUMENT_SET_REPOSITORY_ERROR
        assert "asset-err" in str(exc_info.value)

    def test_exists_reraises_docpipe_exception(self, repo_with_mock, mock_storage):
        original = DocpipeException("check failed", status_code=500)
        mock_storage.record_exists.side_effect = original

        with pytest.raises(DocpipeException) as exc_info:
            repo_with_mock.exists(asset_id="asset-1")

        assert exc_info.value is original


# ---------------------------------------------------------------------------
# COLLECTION_NAME constant
# ---------------------------------------------------------------------------


class TestCollectionName:
    """COLLECTION_NAME must not collide with the document_sets metadata collection."""

    def test_collection_name_is_document_set_attachments(self):
        assert DuckDBAttachmentRepository.COLLECTION_NAME == "document_set_attachments"

    def test_collection_name_differs_from_metadata_collection(self):
        assert DuckDBAttachmentRepository.COLLECTION_NAME != "document_sets"
