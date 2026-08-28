"""Unit tests for DocumentSetService.

Tests cover:
- Creating document sets
- Storing data with metrics update
- Previewing data with pagination
- Computing and updating metrics
- Deleting document sets with data cleanup
- PyArrow table validation
"""

import pyarrow as pa
import pytest

from docpipe.core.assets.common.adapters.repositories.duckdb_asset_repository import DuckDBAssetRepository
from docpipe.core.assets.common.adapters.repositories.duckdb_attachment_repository import DuckDBAttachmentRepository
from docpipe.core.assets.document_sets.adapters.duckdb.data_store import (
    DuckDBDocumentSetStorage,
)
from docpipe.core.assets.document_sets.application.services.document_set_service import (
    DocumentSetService,
)
from docpipe.core.assets.document_sets.domain.models.document_set import DocumentSet
from docpipe.exceptions.docpipe_exceptions import DocpipeException
from docpipe.storage.factory import StorageFactory


@pytest.fixture
def metadata_repository(*, temp_duckdb_path):
    """Create DuckDBAssetRepository[DocumentSet] with pinned collection."""
    key_value_storage = StorageFactory.create_key_value_storage(storage_type="duckdb", database_path=temp_duckdb_path)
    repo = DuckDBAssetRepository(
        asset_type=DocumentSet, key_value_storage=key_value_storage, database_path=temp_duckdb_path
    )
    repo._collection = "document_sets"
    return repo


@pytest.fixture
def data_store(*, temp_duckdb_path):
    """Create a DuckDBDocumentSetStorage instance with dependency injection."""
    table_storage = StorageFactory.create_table_storage(storage_type="duckdb", database_path=temp_duckdb_path)
    return DuckDBDocumentSetStorage(table_storage=table_storage, database_path=temp_duckdb_path)


@pytest.fixture
def attachment_repository(*, temp_duckdb_path):
    """Create a DuckDBAttachmentRepository instance."""
    key_value_storage = StorageFactory.create_key_value_storage(storage_type="duckdb", database_path=temp_duckdb_path)
    return DuckDBAttachmentRepository(key_value_storage=key_value_storage, database_path=temp_duckdb_path)


@pytest.fixture
def service(metadata_repository, data_store, attachment_repository):
    """Create a DocumentSetService instance."""
    return DocumentSetService(
        metadata_repository=metadata_repository, data_store=data_store, attachment_repository=attachment_repository
    )


@pytest.fixture
def sample_table():
    """Create a sample PyArrow table."""
    data = {
        "id": ["doc1", "doc2", "doc3"],
        "name": ["Document 1", "Document 2", "Document 3"],
        "content": ["Content 1", "Content 2", "Content 3"],
        "size": [100, 200, 300],
        "pages_processed": [1, 2, 3],
    }
    return pa.table(data)


class TestCreateDocumentSetService:
    """Test document set creation through service."""

    def test_create_document_set_service(self, service):
        """Test creating a new document set."""
        doc_set = service.create_document_set(
            name="Test Documents",
            description="Test description",
            metadata={"source": "test"},
        )

        assert doc_set.asset_id is not None
        assert doc_set.name == "Test Documents"
        assert doc_set.description == "Test description"
        assert doc_set.metadata == {"source": "test"}

    def test_create_document_set_duplicate_name_returns_existing(self, service):
        """Test that creating with duplicate name returns existing (get-or-create)."""
        first = service.create_document_set(name="Test Documents", description="First")

        # Second call with same name should return existing
        second = service.create_document_set(
            name="Test Documents",
            description="Second",  # This description is ignored
        )

        # Should be the same document set
        assert first.asset_id == second.asset_id
        assert second.description == "First"  # Original description preserved

    def test_create_document_set_invalid_name(self, service):
        """Test that creating with invalid name fails."""
        with pytest.raises(DocpipeException):
            service.create_document_set(
                name="123InvalidName",
                description="Test",
            )


class TestStoreData:
    """Test data storage and metrics update."""

    def test_store_data(self, service, sample_table):
        """Test storing PyArrow table data."""
        doc_set = service.create_document_set(name="Test Documents", description="Test")

        updated = service.store_data(document_set_id=doc_set.asset_id, data=sample_table)

        assert updated.total_documents == 3
        assert updated.total_size_bytes == 600
        assert updated.total_pages == 6

    def test_store_data_creates_data(self, service, sample_table, attachment_repository):
        """Test that storing data creates the backing table."""
        doc_set = service.create_document_set(name="Test Documents", description="Test")

        updated = service.store_data(document_set_id=doc_set.asset_id, data=sample_table)

        # Verify attachment ref was persisted and metrics reflect stored data
        assert attachment_repository.get(asset_id=doc_set.asset_id) is not None
        assert updated.total_documents == 3

    def test_store_data_upserts(self, service):
        """Test that storing data performs upsert."""
        doc_set = service.create_document_set(name="Test Documents", description="Test")

        # Store initial data
        initial_data = pa.table(
            {
                "id": ["doc1"],
                "name": ["Original"],
                "content": ["Original content"],
                "size": [100],
                "pages_processed": [1],
            }
        )
        service.store_data(document_set_id=doc_set.asset_id, data=initial_data)

        # Store updated data
        updated_data = pa.table(
            {
                "id": ["doc1"],
                "name": ["Updated"],
                "content": ["Updated content"],
                "size": [200],
                "pages_processed": [2],
            }
        )
        updated = service.store_data(document_set_id=doc_set.asset_id, data=updated_data)

        # Should still have only 1 document
        assert updated.total_documents == 1
        assert updated.total_size_bytes == 200

    def test_store_data_invalid_document_set_id(self, service, sample_table):
        """Test storing data with invalid document set ID."""
        with pytest.raises(DocpipeException):
            service.store_data(document_set_id="", data=sample_table)

    def test_store_data_nonexistent_document_set(self, service, sample_table):
        """Test storing data for nonexistent document set."""
        with pytest.raises(DocpipeException):
            service.store_data(document_set_id="nonexistent-id", data=sample_table)


class TestPreviewData:
    """Test data preview with pagination."""

    def test_preview_data(self, service, sample_table):
        """Test previewing stored data."""
        doc_set = service.create_document_set(name="Test Documents", description="Test")
        service.store_data(document_set_id=doc_set.asset_id, data=sample_table)

        preview = service.preview_data(document_set_id=doc_set.asset_id, limit=10, offset=0)

        assert preview.num_rows == 3
        assert preview.num_columns == 5

    def test_preview_data_with_limit(self, service, sample_table):
        """Test previewing with limit."""
        doc_set = service.create_document_set(name="Test Documents", description="Test")
        service.store_data(document_set_id=doc_set.asset_id, data=sample_table)

        preview = service.preview_data(document_set_id=doc_set.asset_id, limit=2, offset=0)

        assert preview.num_rows == 2

    def test_preview_data_with_offset(self, service, sample_table):
        """Test previewing with offset."""
        doc_set = service.create_document_set(name="Test Documents", description="Test")
        service.store_data(document_set_id=doc_set.asset_id, data=sample_table)

        preview = service.preview_data(document_set_id=doc_set.asset_id, limit=10, offset=1)

        assert preview.num_rows == 2

    def test_preview_data_empty_table(self, service):
        """Test previewing when no data stored."""
        doc_set = service.create_document_set(name="Test Documents", description="Test")

        preview = service.preview_data(document_set_id=doc_set.asset_id, limit=10, offset=0)

        assert preview.num_rows == 0

    def test_preview_data_invalid_limit(self, service):
        """Test preview with invalid limit."""
        doc_set = service.create_document_set(name="Test Documents", description="Test")

        with pytest.raises(DocpipeException):
            service.preview_data(document_set_id=doc_set.asset_id, limit=0, offset=0)

    def test_preview_data_invalid_offset(self, service):
        """Test preview with invalid offset."""
        doc_set = service.create_document_set(name="Test Documents", description="Test")

        with pytest.raises(DocpipeException):
            service.preview_data(document_set_id=doc_set.asset_id, limit=10, offset=-1)


class TestComputeAndUpdateMetrics:
    """Test metrics recomputation."""

    def test_compute_and_update_metrics(self, service, sample_table):
        """Test recomputing metrics from stored data."""
        doc_set = service.create_document_set(name="Test Documents", description="Test")
        stored = service.store_data(document_set_id=doc_set.asset_id, data=sample_table)

        # Manually zero out metrics via repository — use the post-store object
        # so storage_reference is preserved in the record
        stored.total_documents = 0
        service._repository.update(asset=stored)

        # Recompute
        updated = service.compute_and_update_metrics(document_set_id=doc_set.asset_id)

        assert updated.total_documents == 3
        assert updated.total_size_bytes == 600
        assert updated.total_pages == 6

    def test_compute_metrics_no_data_table(self, service):
        """Test computing metrics when data table doesn't exist."""
        doc_set = service.create_document_set(name="Test Documents", description="Test")

        updated = service.compute_and_update_metrics(document_set_id=doc_set.asset_id)

        assert updated.total_documents == 0
        assert updated.total_size_bytes == 0
        assert updated.total_pages == 0


class TestDeleteDocumentSetWithData:
    """Test deletion with data cleanup."""

    def test_delete_document_set_with_data(self, service, sample_table):
        """Test deleting document set and its data table."""
        doc_set = service.create_document_set(name="Test Documents", description="Test")
        service.store_data(document_set_id=doc_set.asset_id, data=sample_table)

        # Delete with data
        result = service.delete_document_set(document_set_id=doc_set.asset_id, delete_data=True)

        assert result is True
        assert service.exists(asset_id=doc_set.asset_id) is False

    def test_delete_document_set_preserve_data(self, service, sample_table):
        """Test deleting document set metadata but preserving data table."""
        doc_set = service.create_document_set(name="Test Documents", description="Test")
        service.store_data(document_set_id=doc_set.asset_id, data=sample_table)

        # Delete without data
        result = service.delete_document_set(document_set_id=doc_set.asset_id, delete_data=False)

        assert result is True
        # Metadata is gone
        assert service.exists(asset_id=doc_set.asset_id) is False

    def test_delete_nonexistent_document_set(self, service):
        """Test deleting nonexistent document set."""
        with pytest.raises(DocpipeException):
            service.delete_document_set(document_set_id="nonexistent-id")


class TestInvalidPyArrowTable:
    """Test validation of PyArrow tables."""

    def test_invalid_pyarrow_table_none(self, service):
        """Test that None table raises error."""
        doc_set = service.create_document_set(name="Test Documents", description="Test")

        with pytest.raises(DocpipeException):
            service.store_data(document_set_id=doc_set.asset_id, data=None)

    def test_invalid_pyarrow_table_wrong_type(self, service):
        """Test that non-PyArrow table raises error."""
        doc_set = service.create_document_set(name="Test Documents", description="Test")

        with pytest.raises(DocpipeException):
            service.store_data(document_set_id=doc_set.asset_id, data={"not": "a table"})

    def test_invalid_pyarrow_table_missing_id(self, service):
        """Test that table without id column raises error."""
        doc_set = service.create_document_set(name="Test Documents", description="Test")

        bad_table = pa.table({"name": ["Document 1"], "content": ["Content 1"]})

        with pytest.raises(DocpipeException):
            service.store_data(document_set_id=doc_set.asset_id, data=bad_table)


class TestGetDocumentSet:
    """Test retrieving document sets."""

    def test_get_document_set(self, service):
        """Test retrieving document set by ID."""
        created = service.create_document_set(name="Test Documents", description="Test")

        retrieved = service.get_document_set(document_set_id=created.asset_id)

        assert retrieved.asset_id == created.asset_id
        assert retrieved.name == created.name

    def test_get_document_set_not_found(self, service):
        """Test retrieving nonexistent document set."""
        with pytest.raises(DocpipeException):
            service.get_document_set(document_set_id="nonexistent-id")

    def test_get_document_set_empty_id(self, service):
        """Test retrieving with empty ID."""
        with pytest.raises(DocpipeException):
            service.get_document_set(document_set_id="")


class TestGetDocumentSetByName:
    """Test retrieving document sets by name."""

    def test_get_document_set_by_name(self, service):
        """Test retrieving document set by name."""
        created = service.create_document_set(name="Test Documents", description="Test")

        retrieved = service.get_by_name(name="Test Documents")

        assert retrieved.asset_id == created.asset_id
        assert retrieved.name == created.name

    def test_get_document_set_by_name_not_found(self, service):
        """Test retrieving nonexistent document set by name."""
        with pytest.raises(DocpipeException):
            service.get_by_name(name="Nonexistent Name")

    def test_get_document_set_by_name_empty(self, service):
        """Test retrieving with empty name."""
        with pytest.raises(DocpipeException):
            service.get_by_name(name="")


class TestListDocumentSets:
    """Test listing document sets."""

    def test_list_document_sets(self, service):
        """Test listing all document sets."""
        for i in range(3):
            service.create_document_set(
                name=f"Documents {i}",
                description=f"Test {i}",
            )

        result = service.list_document_sets()

        assert len(result) == 3

    def test_list_document_sets_with_limit(self, service):
        """Test listing with limit."""
        for i in range(5):
            service.create_document_set(
                name=f"Documents {i}",
                description=f"Test {i}",
            )

        result = service.list_document_sets(limit=3)

        assert len(result) == 3

    def test_list_document_sets_with_offset(self, service):
        """Test listing with offset."""
        for i in range(5):
            service.create_document_set(
                name=f"Documents {i}",
                description=f"Test {i}",
            )

        result = service.list_document_sets(offset=2)

        assert len(result) == 3

    def test_list_document_sets_invalid_limit(self, service):
        """Test listing with invalid limit."""
        with pytest.raises(DocpipeException):
            service.list_document_sets(limit=0)

    def test_list_document_sets_invalid_offset(self, service):
        """Test listing with invalid offset."""
        with pytest.raises(DocpipeException):
            service.list_document_sets(offset=-1)


class TestUpdateDocumentSet:
    """Test updating document sets."""

    def test_update_document_set(self, service):
        """Test updating document set metadata."""
        created = service.create_document_set(
            name="Test Documents",
            description="Original",
        )

        updated = service.update_document_set(
            document_set_id=created.asset_id,
            description="Updated",
            metadata={"version": "2.0"},
        )

        assert updated.description == "Updated"
        assert updated.metadata == {"version": "2.0"}

    def test_update_document_set_not_found(self, service):
        """Test updating nonexistent document set."""
        with pytest.raises(DocpipeException):
            service.update_document_set(document_set_id="nonexistent-id", description="Updated")

    def test_update_document_set_empty_id(self, service):
        """Test updating with empty ID."""
        with pytest.raises(DocpipeException):
            service.update_document_set(document_set_id="", description="Updated")
