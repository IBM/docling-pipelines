"""Unit tests for DocumentSetRepository.

Tests cover:
- Creating document sets
- Retrieving by ID and name
- Updating document sets
- Listing with pagination
- Deleting document sets
- Duplicate name/ID handling
- Not found error handling
"""

import pytest

from common.exceptions.datasift_exceptions import DatasiftException
from core.assets_management.document_sets.adapters.repositories.document_set_repository import (
    DocumentSetRepository,
)
from core.assets_management.document_sets.domain.models.document_set import DocumentSet
from storage.duckdb_storage import DuckDBStorage


@pytest.fixture
def storage(temp_duckdb_path):
    """Create a DuckDBStorage instance."""
    return DuckDBStorage(temp_duckdb_path)


@pytest.fixture
def repository(storage):
    """Create a DocumentSetRepository instance."""
    return DocumentSetRepository(storage)


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
        created = repository.create(sample_document_set)

        assert created.id == sample_document_set.id
        assert created.name == sample_document_set.name
        assert created.description == sample_document_set.description

    def test_create_document_set_duplicate_id(self, repository, sample_document_set):
        """Test that creating document set with duplicate ID raises database error."""
        repository.create(sample_document_set)

        duplicate = DocumentSet(
            id=sample_document_set.id,
            name="Different Name",
            database_path="/data/test.db",
            table_name="different_table",
        )

        with pytest.raises(Exception):
            repository.create(duplicate)

    def test_create_document_set_duplicate_name(self, repository, sample_document_set):
        """Test that creating document set with duplicate name raises database error."""
        repository.create(sample_document_set)

        duplicate = DocumentSet(
            name=sample_document_set.name,
            database_path="/data/test.db",
            table_name="different_table",
        )

        with pytest.raises(Exception):
            repository.create(duplicate)

    def test_create_document_set_with_metadata(self, repository):
        """Test creating document set with custom metadata."""
        doc_set = DocumentSet(
            name="Test Documents",
            database_path="/data/test.db",
            table_name="test_table",
            metadata={"source": "test", "version": "1.0"},
        )

        created = repository.create(doc_set)

        assert created.metadata == {"source": "test", "version": "1.0"}


class TestGetByID:
    """Test retrieving document sets by ID."""

    def test_get_by_id_success(self, repository, sample_document_set):
        """Test retrieving existing document set by ID."""
        created = repository.create(sample_document_set)

        retrieved = repository.get_by_id(created.id or "")

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.name == created.name

    def test_get_by_id_not_found(self, repository):
        """Test retrieving nonexistent document set returns None."""
        result = repository.get_by_id("nonexistent-id")

        assert result is None

    def test_get_by_id_preserves_metadata(self, repository):
        """Test that metadata is preserved when retrieving."""
        doc_set = DocumentSet(
            name="Test Documents",
            database_path="/data/test.db",
            table_name="test_table",
            metadata={"key": "value"},
        )
        created = repository.create(doc_set)

        retrieved = repository.get_by_id(created.id or "")

        assert retrieved.metadata == {"key": "value"}


class TestGetByName:
    """Test retrieving document sets by name."""

    def test_get_by_name_success(self, repository, sample_document_set):
        """Test retrieving existing document set by name."""
        created = repository.create(sample_document_set)

        retrieved = repository.get_by_name(created.name)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.name == created.name

    def test_get_by_name_not_found(self, repository):
        """Test retrieving nonexistent document set returns None."""
        result = repository.get_by_name("Nonexistent Name")

        assert result is None


class TestUpdateDocumentSet:
    """Test updating existing document sets."""

    def test_update_document_set(self, repository, sample_document_set):
        """Test updating an existing document set."""
        created = repository.create(sample_document_set)

        created.description = "Updated description"
        created.total_documents = 100

        updated = repository.update(created)

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

        with pytest.raises(DatasiftException):
            repository.update(doc_set)

    def test_update_document_set_updates_timestamp(
        self, repository, sample_document_set
    ):
        """Test that update modifies updated_at timestamp."""
        created = repository.create(sample_document_set)
        original_updated_at = created.updated_at

        created.description = "New description"
        updated = repository.update(created)

        assert updated.updated_at >= original_updated_at


class TestSaveDocumentSet:
    """Test save (upsert) operation."""

    def test_save_creates_new(self, repository, sample_document_set):
        """Test that save creates new document set if it doesn't exist."""
        saved = repository.save(sample_document_set)

        assert saved.id == sample_document_set.id
        assert repository.exists(saved.id or "")

    def test_save_updates_existing(self, repository, sample_document_set):
        """Test that save updates existing document set (true upsert)."""
        created = repository.create(sample_document_set)

        created.description = "Updated via save"
        saved = repository.save(created)

        assert saved.description == "Updated via save"

        all_sets = repository.list_all()
        assert len(all_sets) == 1

    def test_save_handles_constraint_violation(self, repository, sample_document_set):
        """Test that save handles constraint violations gracefully."""
        created = repository.create(sample_document_set)

        duplicate = DocumentSet(
            id=created.id,
            name=created.name,
            description="Different description",
            database_path="/data/test.db",
            table_name="test_table",
        )

        saved = repository.save(duplicate)

        assert saved.id == created.id
        assert saved.description == "Different description"

        all_sets = repository.list_all()
        assert len(all_sets) == 1


class TestListAll:
    """Test listing document sets with pagination."""

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
            repository.create(doc_set)

        result = repository.list_all()

        assert len(result) == 5

    def test_list_all_with_limit(self, repository):
        """Test listing with limit."""
        for i in range(5):
            doc_set = DocumentSet(
                name=f"Documents {i}",
                database_path="/data/test.db",
                table_name=f"table_{i}",
            )
            repository.create(doc_set)

        result = repository.list_all(limit=3)

        assert len(result) == 3

    def test_list_all_with_offset(self, repository):
        """Test listing with offset."""
        for i in range(5):
            doc_set = DocumentSet(
                name=f"Documents {i}",
                database_path="/data/test.db",
                table_name=f"table_{i}",
            )
            repository.create(doc_set)

        result = repository.list_all(offset=2)

        assert len(result) == 3

    def test_list_all_pagination(self, repository):
        """Test listing with limit and offset."""
        for i in range(5):
            doc_set = DocumentSet(
                name=f"Documents {i}",
                database_path="/data/test.db",
                table_name=f"table_{i}",
            )
            repository.create(doc_set)

        result = repository.list_all(limit=2, offset=1)

        assert len(result) == 2

    def test_list_all_ordered_by_created_at(self, repository):
        """Test that results are ordered by created_at descending."""
        doc_sets = []
        for i in range(3):
            doc_set = DocumentSet(
                name=f"Documents {i}",
                database_path="/data/test.db",
                table_name=f"table_{i}",
            )
            created = repository.create(doc_set)
            doc_sets.append(created)

        result = repository.list_all()

        assert result[0].id == doc_sets[2].id
        assert result[2].id == doc_sets[0].id


class TestExists:
    """Test checking document set existence."""

    def test_exists_true(self, repository, sample_document_set):
        """Test exists returns True for existing document set."""
        created = repository.create(sample_document_set)

        assert repository.exists(created.id or "") is True

    def test_exists_false(self, repository):
        """Test exists returns False for nonexistent document set."""
        assert repository.exists("nonexistent-id") is False


class TestExistsByName:
    """Test checking document set existence by name."""

    def test_exists_by_name_true(self, repository, sample_document_set):
        """Test exists_by_name returns True for existing name."""
        created = repository.create(sample_document_set)

        assert repository.exists_by_name(created.name) is True

    def test_exists_by_name_false(self, repository):
        """Test exists_by_name returns False for nonexistent name."""
        assert repository.exists_by_name("Nonexistent Name") is False


class TestDeleteDocumentSet:
    """Test deleting document sets."""

    def test_delete_document_set(self, repository, sample_document_set):
        """Test deleting an existing document set."""
        created = repository.create(sample_document_set)

        result = repository.delete(created.id or "")

        assert result is True
        assert repository.exists(created.id or "") is False

    def test_delete_document_set_not_found(self, repository):
        """Test deleting nonexistent document set returns False."""
        result = repository.delete("nonexistent-id")

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
            created = repository.create(doc_set)
            doc_sets.append(created)

        repository.delete(doc_sets[1].id or "")

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

        with pytest.raises(DatasiftException, match="ID cannot be None"):
            repository.create(doc_set)

    def test_update_without_id_raises_error(self, repository):
        """Test that updating without ID raises error."""
        doc_set = DocumentSet(
            name="Test Documents",
            database_path="/data/test.db",
            table_name="test_table",
        )
        doc_set.id = None

        with pytest.raises(DatasiftException, match="ID cannot be None"):
            repository.update(doc_set)

    def test_save_without_id_raises_error(self, repository):
        """Test that saving without ID raises error."""
        doc_set = DocumentSet(
            name="Test Documents",
            database_path="/data/test.db",
            table_name="test_table",
        )
        doc_set.id = None

        with pytest.raises(DatasiftException, match="ID cannot be None"):
            repository.save(doc_set)


class TestRepositoryWithInMemoryDatabase:
    """Test repository with in-memory database."""

    def test_in_memory_repository(self):
        """Test repository operations with in-memory database."""
        storage = DuckDBStorage(":memory:")
        repository = DocumentSetRepository(storage)

        doc_set = DocumentSet(
            name="Test Documents", database_path=":memory:", table_name="test_table"
        )
        created = repository.create(doc_set)

        retrieved = repository.get_by_id(created.id or "")
        assert retrieved is not None
        assert retrieved.name == "Test Documents"

        all_sets = repository.list_all()
        assert len(all_sets) == 1
