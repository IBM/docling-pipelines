"""Unit tests for DocumentSetRepository.

Tests cover:
- Creating document sets
- Retrieving by ID and name
- Updating document sets
- Listing document sets
- Deleting document sets
- Duplicate name/ID handling
- Not found error handling
"""

import pytest

from docpipe.core.assets.document_sets.adapters.duckdb.metadata_repository import (
    DuckDBDocumentSetMetadataRepository,
)
from docpipe.core.assets.document_sets.domain.models.document_set import DocumentSet
from docpipe.exceptions.docpipe_exceptions import DocpipeException
from docpipe.storage.duck_db.key_value_storage import DuckDBKeyValueStorage


@pytest.fixture
def storage(temp_duckdb_path):
    """Create a DuckDBKeyValueStorage instance."""
    return DuckDBKeyValueStorage(database_path=temp_duckdb_path)


@pytest.fixture
def repository(storage, temp_duckdb_path):
    """Create a DocumentSetRepository instance."""
    return DuckDBDocumentSetMetadataRepository(key_value_storage=storage, database_path=temp_duckdb_path)


@pytest.fixture
def sample_document_set():
    """Create a sample DocumentSet."""
    return DocumentSet(
        name="Test Documents",
        description="Test description",
        database_path="/data/test.db",
        table_name="test_table",
    )


class TestCreateDocumentSet:
    """Test creating new document sets."""

    def test_create_document_set(self, repository, sample_document_set):
        """Test creating a new document set."""
        created = repository.create(document_set=sample_document_set)

        assert created.id == sample_document_set.id
        assert created.name == sample_document_set.name
        assert created.description == sample_document_set.description

    def test_create_document_set_duplicate_id(self, repository, sample_document_set):
        """Test that creating document set with duplicate ID raises DocpipeException."""
        repository.create(document_set=sample_document_set)

        duplicate = DocumentSet(
            id=sample_document_set.id,
            name="Different Name",
            database_path="/data/test.db",
            table_name="different_table",
        )

        with pytest.raises(DocpipeException):
            repository.create(document_set=duplicate)

    def test_create_document_set_duplicate_name(self, repository, sample_document_set):
        """Test that creating document set with duplicate name raises DocpipeException."""
        repository.create(document_set=sample_document_set)

        duplicate = DocumentSet(
            name=sample_document_set.name,
            database_path="/data/test.db",
            table_name="different_table",
        )

        with pytest.raises(DocpipeException):
            repository.create(document_set=duplicate)

    def test_create_document_set_with_metadata(self, repository):
        """Test creating document set with custom metadata."""
        doc_set = DocumentSet(
            name="Test Documents",
            database_path="/data/test.db",
            table_name="test_table",
            metadata={"source": "test", "version": "1.0"},
        )

        created = repository.create(document_set=doc_set)

        assert created.metadata == {"source": "test", "version": "1.0"}


class TestGetByID:
    """Test retrieving document sets by ID."""

    def test_get_by_id_success(self, repository, sample_document_set):
        """Test retrieving existing document set by ID."""
        created = repository.create(document_set=sample_document_set)

        retrieved = repository.get_by_id(document_set_id=created.id or "")

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.name == created.name

    def test_get_by_id_not_found(self, repository):
        """Test retrieving nonexistent document set raises exception."""
        with pytest.raises(DocpipeException):
            repository.get_by_id(document_set_id="nonexistent-id")

    def test_get_by_id_preserves_metadata(self, repository):
        """Test that metadata is preserved when retrieving."""
        doc_set = DocumentSet(
            name="Test Documents",
            database_path="/data/test.db",
            table_name="test_table",
            metadata={"key": "value"},
        )
        created = repository.create(document_set=doc_set)

        retrieved = repository.get_by_id(document_set_id=created.id or "")

        assert retrieved.metadata == {"key": "value"}


class TestGetByName:
    """Test retrieving document sets by name."""

    def test_get_by_name_success(self, repository, sample_document_set):
        """Test retrieving existing document set by name."""
        created = repository.create(document_set=sample_document_set)

        retrieved = repository.get_by_name(name=created.name)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.name == created.name

    def test_get_by_name_not_found(self, repository):
        """Test retrieving nonexistent document set raises exception."""
        with pytest.raises(DocpipeException):
            repository.get_by_name(name="Nonexistent Name")


class TestUpdateDocumentSet:
    """Test updating existing document sets."""

    def test_update_document_set(self, repository, sample_document_set):
        """Test updating an existing document set."""
        created = repository.create(document_set=sample_document_set)

        created.description = "Updated description"
        created.total_documents = 100

        updated = repository.update(document_set=created)

        assert updated.description == "Updated description"
        assert updated.total_documents == 100

    def test_update_document_set_not_found(self, repository):
        """Test updating nonexistent document set raises error."""
        doc_set = DocumentSet(
            id="nonexistent-id",
            name="Test Documents",
            database_path="/data/test.db",
            table_name="test_table",
        )

        with pytest.raises(DocpipeException):
            repository.update(document_set=doc_set)

    def test_update_document_set_updates_timestamp(self, repository, sample_document_set):
        """Test that update modifies updated_at timestamp."""
        created = repository.create(document_set=sample_document_set)
        original_updated_at = created.updated_at

        created.description = "New description"
        updated = repository.update(document_set=created)

        assert updated.updated_at >= original_updated_at


class TestSaveDocumentSet:
    """Test save (upsert) operation - not implemented in new architecture."""

    def test_save_not_implemented(self, repository, sample_document_set):
        """Test that save method is not available in new architecture."""
        # The new architecture doesn't have a save method
        # Use create or update explicitly instead
        assert not hasattr(repository, "save")


class TestListAll:
    """Test listing document sets."""

    def test_list_all_empty(self, repository):
        """Test listing when no document sets exist."""
        result = repository.list_all()

        assert result == []

    def test_list_all_multiple(self, repository):
        """Test listing multiple document sets."""
        for i in range(5):
            doc_set = DocumentSet(
                name=f"Documents {i}",
                database_path="/data/test.db",
                table_name=f"table_{i}",
            )
            repository.create(document_set=doc_set)

        result = repository.list_all()

        assert len(result) == 5

    def test_list_all_ordered_by_created_at(self, repository):
        """Test that results are ordered by created_at descending."""
        doc_sets = []
        for i in range(3):
            doc_set = DocumentSet(
                name=f"Documents {i}",
                database_path="/data/test.db",
                table_name=f"table_{i}",
            )
            created = repository.create(document_set=doc_set)
            doc_sets.append(created)

        result = repository.list_all()

        assert result[0].id == doc_sets[2].id
        assert result[2].id == doc_sets[0].id


class TestExists:
    """Test checking document set existence."""

    def test_exists_true(self, repository, sample_document_set):
        """Test exists returns True for existing document set."""
        created = repository.create(document_set=sample_document_set)

        assert repository.exists(document_set_id=created.id or "") is True

    def test_exists_false(self, repository):
        """Test exists returns False for nonexistent document set."""
        assert repository.exists(document_set_id="nonexistent-id") is False


class TestExistsByName:
    """Test checking document set existence by name - not implemented in new architecture."""

    def test_exists_by_name_not_implemented(self, repository):
        """Test that exists_by_name is not available in new architecture."""
        # The new architecture doesn't have exists_by_name method
        # Use get_by_name and catch exception instead
        assert not hasattr(repository, "exists_by_name")


class TestDeleteDocumentSet:
    """Test deleting document sets."""

    def test_delete_document_set(self, repository, sample_document_set):
        """Test deleting an existing document set."""
        created = repository.create(document_set=sample_document_set)

        result = repository.delete(document_set_id=created.id or "")

        assert result is True
        assert repository.exists(document_set_id=created.id or "") is False

    def test_delete_document_set_not_found(self, repository):
        """Test deleting nonexistent document set returns False."""
        result = repository.delete(document_set_id="nonexistent-id")

        assert result is False

    def test_delete_document_set_removes_from_list(self, repository):
        """Test that deleted document set is removed from list."""
        doc_sets = []
        for i in range(3):
            doc_set = DocumentSet(
                name=f"Documents {i}",
                database_path="/data/test.db",
                table_name=f"table_{i}",
            )
            created = repository.create(document_set=doc_set)
            doc_sets.append(created)

        repository.delete(document_set_id=doc_sets[1].id or "")

        all_sets = repository.list_all()
        assert len(all_sets) == 2
        assert doc_sets[1].id not in [ds.id for ds in all_sets]


class TestRepositoryErrorHandling:
    """Test error handling in repository operations."""

    def test_create_without_id_raises_error(self, repository):
        """Test that creating without ID raises error."""
        doc_set = DocumentSet(
            name="Test Documents",
            database_path="/data/test.db",
            table_name="test_table",
        )
        doc_set.id = None

        with pytest.raises(DocpipeException, match="ID cannot be None"):
            repository.create(document_set=doc_set)

    def test_update_without_id_raises_error(self, repository):
        """Test that updating without ID raises error."""
        doc_set = DocumentSet(
            name="Test Documents",
            database_path="/data/test.db",
            table_name="test_table",
        )
        doc_set.id = None

        with pytest.raises(DocpipeException, match="ID cannot be None"):
            repository.update(document_set=doc_set)


class TestRepositoryWithInMemoryDatabase:
    """Test repository with in-memory database."""

    def test_in_memory_repository(self):
        """Test repository operations with in-memory database."""
        storage = DuckDBKeyValueStorage(database_path=":memory:")
        repository = DuckDBDocumentSetMetadataRepository(key_value_storage=storage, database_path=":memory:")

        doc_set = DocumentSet(name="Test Documents", database_path=":memory:", table_name="test_table")
        created = repository.create(document_set=doc_set)

        retrieved = repository.get_by_id(document_set_id=created.id or "")
        assert retrieved is not None
        assert retrieved.name == "Test Documents"

        all_sets = repository.list_all()
        assert len(all_sets) == 1
