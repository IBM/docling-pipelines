"""Unit tests for DocumentSetService.

All external dependencies (metadata repository, data store, attachment repository)
are mocked.  Tests verify observable service behaviour only — no real DuckDB, no disk I/O.
"""

from unittest.mock import Mock

import pyarrow as pa
import pytest

from docpipe.core.assets.common.domain.models.attachment_ref import AttachmentRef
from docpipe.core.assets.document_sets.application.services.document_set_service import (
    DocumentSetService,
)
from docpipe.core.assets.document_sets.domain.models.document_set import DocumentSet
from docpipe.exceptions.docpipe_exceptions import DocpipeException

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DB_PATH = "/tmp/test.duckdb"
_TABLE_NAME = "my_set"
_ASSET_ID = "abc-123"
_SET_NAME = "My Set"


def _make_attachment_ref() -> AttachmentRef:
    return AttachmentRef(
        backend_type="duckdb",
        name=_TABLE_NAME,
        details={"database_path": _DB_PATH, "table_name": _TABLE_NAME},
    )


def _make_doc_set(*, total_documents: int = 0) -> DocumentSet:
    return DocumentSet(
        asset_id=_ASSET_ID,
        name=_SET_NAME,
        total_documents=total_documents,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_repo():
    """Mock AssetRepository[DocumentSet]."""
    repo = Mock()
    repo.find_by_name.return_value = None
    repo.find_by_id.return_value = _make_doc_set()
    repo.save.return_value = _make_doc_set()
    repo.update.return_value = _make_doc_set(total_documents=2)
    repo.delete.return_value = True
    repo.exists.return_value = True
    repo.list_all.return_value = [_make_doc_set(), _make_doc_set()]
    return repo


@pytest.fixture
def mock_store():
    """Mock DocumentSetStorage."""
    store = Mock()
    store.store.return_value = _make_attachment_ref()
    store.exists.return_value = True
    store.load.return_value = pa.table({"id": ["1", "2"], "content": ["a", "b"]})
    store.get_metrics.return_value = {"total_documents": 2, "total_size_bytes": 512, "total_pages": 0}
    return store


@pytest.fixture
def mock_attachment_repo():
    """Mock AttachmentRepository."""
    repo = Mock()
    repo.get.return_value = _make_attachment_ref()
    repo.save.return_value = None
    repo.delete.return_value = True
    repo.exists.return_value = True
    return repo


@pytest.fixture
def service(mock_repo, mock_store, mock_attachment_repo):
    return DocumentSetService(
        metadata_repository=mock_repo,
        data_store=mock_store,
        attachment_repository=mock_attachment_repo,
    )


# ---------------------------------------------------------------------------
# create_document_set
# ---------------------------------------------------------------------------


class TestCreateDocumentSet:
    def test_creates_new_document_set_when_name_is_unique(self, service, mock_repo):
        result = service.create_document_set(name=_SET_NAME, description="test")

        assert result.asset_id == _ASSET_ID
        mock_repo.save.assert_called_once()

    def test_returns_existing_when_name_already_taken(self, service, mock_repo):
        existing = _make_doc_set()
        mock_repo.find_by_name.return_value = existing

        result = service.create_document_set(name=_SET_NAME, description="test")

        assert result is existing
        mock_repo.save.assert_not_called()


# ---------------------------------------------------------------------------
# get_document_set
# ---------------------------------------------------------------------------


class TestGetDocumentSet:
    def test_returns_document_set_for_valid_id(self, service, mock_repo):
        result = service.get_document_set(document_set_id=_ASSET_ID)

        assert result.asset_id == _ASSET_ID
        mock_repo.find_by_id.assert_called_once_with(asset_id=_ASSET_ID)

    def test_raises_404_when_not_found(self, service, mock_repo):
        mock_repo.find_by_id.return_value = None

        with pytest.raises(DocpipeException) as exc_info:
            service.get_document_set(document_set_id="missing-id")

        assert exc_info.value.status_code == 404

    def test_raises_400_for_empty_id(self, service):
        with pytest.raises(DocpipeException) as exc_info:
            service.get_document_set(document_set_id="")

        assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# store_data
# ---------------------------------------------------------------------------


class TestStoreData:
    def test_stores_data_and_updates_metrics(self, service, mock_store, mock_attachment_repo):
        table = pa.table({"id": ["1", "2"], "content": ["a", "b"]})

        result = service.store_data(document_set_id=_ASSET_ID, data=table)

        mock_store.store.assert_called_once()
        mock_attachment_repo.save.assert_called_once()
        assert result.total_documents == 2

    def test_raises_400_when_data_missing_id_column(self, service):
        table = pa.table({"content": ["a", "b"]})

        with pytest.raises(DocpipeException) as exc_info:
            service.store_data(document_set_id=_ASSET_ID, data=table)

        assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# preview_data
# ---------------------------------------------------------------------------


class TestPreviewData:
    def test_returns_rows_from_storage(self, service, mock_store):
        result = service.preview_data(document_set_id=_ASSET_ID, limit=10)

        assert len(result) == 2
        mock_store.load.assert_called_once()

    def test_returns_empty_table_when_attachment_ref_absent(self, service, mock_repo, mock_store, mock_attachment_repo):
        mock_repo.find_by_id.return_value = DocumentSet(asset_id=_ASSET_ID, name=_SET_NAME)
        mock_attachment_repo.get.return_value = None

        result = service.preview_data(document_set_id=_ASSET_ID, limit=10)

        assert len(result) == 0
        mock_store.load.assert_not_called()


# ---------------------------------------------------------------------------
# delete_document_set
# ---------------------------------------------------------------------------


class TestDeleteDocumentSet:
    def test_deletes_data_attachment_and_metadata(self, service, mock_repo, mock_store, mock_attachment_repo):
        result = service.delete_document_set(document_set_id=_ASSET_ID)

        assert result is True
        mock_store.delete.assert_called_once()
        mock_attachment_repo.delete.assert_called_once_with(asset_id=_ASSET_ID)
        mock_repo.delete.assert_called_once_with(asset_id=_ASSET_ID)

    def test_raises_400_for_empty_id(self, service):
        with pytest.raises(DocpipeException) as exc_info:
            service.delete_document_set(document_set_id="  ")

        assert exc_info.value.status_code == 400
