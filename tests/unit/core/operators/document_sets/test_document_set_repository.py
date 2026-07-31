"""Unit tests for DocumentSetRepository.

Tests cover:
- Saving document sets
- Retrieving by ID and name
- Updating document sets
- Listing document sets
- Deleting document sets
- Duplicate name/ID handling
- Not found error handling
"""

import pytest

from docpipe.core.assets.common.adapters.repositories.duckdb_asset_repository import DuckDBAssetRepository
from docpipe.core.assets.document_sets.domain.models.document_set import DocumentSet
from docpipe.exceptions.docpipe_exceptions import DocpipeException
from docpipe.storage.duck_db.duckdb_key_value_storage import DuckDBKeyValueStorage


@pytest.fixture
def storage(temp_duckdb_path):
    """Create a DuckDBKeyValueStorage instance."""
    return DuckDBKeyValueStorage(database_path=temp_duckdb_path)


@pytest.fixture
def repository(storage, temp_duckdb_path):
    """Create a DuckDBAssetRepository[DocumentSet] instance."""
    repo = DuckDBAssetRepository(asset_type=DocumentSet, key_value_storage=storage, database_path=temp_duckdb_path)
    repo._collection = "document_sets"
    return repo


@pytest.fixture
def sample_document_set():
    """Create a sample DocumentSet."""
    return DocumentSet(
        name="Test Documents",
        description="Test description",
    )


class TestCreateDocumentSet:
    """Test saving new document sets."""

    def test_create_document_set(self, repository, sample_document_set):
        """Test saving a new document set."""
        created = repository.save(asset=sample_document_set)

        assert created.asset_id == sample_document_set.asset_id
        assert created.name == sample_document_set.name
        assert created.description == sample_document_set.description

    def test_create_document_set_duplicate_id(self, repository, sample_document_set):
        """Test that saving document set with duplicate ID raises DocpipeException."""
        repository.save(asset=sample_document_set)

        duplicate = DocumentSet(
            asset_id=sample_document_set.asset_id,
            name="Different Name",
        )

        with pytest.raises(DocpipeException):
            repository.save(asset=duplicate)

    def test_create_document_set_duplicate_name(self, repository, sample_document_set):
        """Test that saving document set with duplicate name raises DocpipeException."""
        repository.save(asset=sample_document_set)

        duplicate = DocumentSet(
            name=sample_document_set.name,
        )

        with pytest.raises(DocpipeException):
            repository.save(asset=duplicate)

    def test_create_document_set_with_metadata(self, repository):
        """Test saving document set with custom metadata."""
        doc_set = DocumentSet(
            name="Test Documents",
            metadata={"source": "test", "version": "1.0"},
        )

        created = repository.save(asset=doc_set)

        assert created.metadata == {"source": "test", "version": "1.0"}


class TestGetByID:
    """Test retrieving document sets by ID."""

    def test_get_by_id_success(self, repository, sample_document_set):
        """Test retrieving existing document set by ID."""
        created = repository.save(asset=sample_document_set)

        retrieved = repository.find_by_id(asset_id=created.asset_id or "")

        assert retrieved is not None
        assert retrieved.asset_id == created.asset_id
        assert retrieved.name == created.name

    def test_get_by_id_not_found(self, repository):
        """Test retrieving nonexistent document set returns None."""
        result = repository.find_by_id(asset_id="nonexistent-id")
        assert result is None

    def test_get_by_id_preserves_metadata(self, repository):
        """Test that metadata is preserved when retrieving."""
        doc_set = DocumentSet(
            name="Test Documents",
            metadata={"key": "value"},
        )
        created = repository.save(asset=doc_set)

        retrieved = repository.find_by_id(asset_id=created.asset_id or "")

        assert retrieved is not None
        assert retrieved.metadata == {"key": "value"}


class TestGetByName:
    """Test retrieving document sets by name."""

    def test_get_by_name_success(self, repository, sample_document_set):
        """Test retrieving existing document set by name."""
        created = repository.save(asset=sample_document_set)

        retrieved = repository.find_by_name(name=created.name)

        assert retrieved is not None
        assert retrieved.asset_id == created.asset_id
        assert retrieved.name == created.name

    def test_get_by_name_not_found(self, repository):
        """Test retrieving nonexistent document set returns None."""
        result = repository.find_by_name(name="Nonexistent Name")
        assert result is None


class TestUpdateDocumentSet:
    """Test updating existing document sets."""

    def test_update_document_set(self, repository, sample_document_set):
        """Test updating an existing document set."""
        created = repository.save(asset=sample_document_set)

        created.description = "Updated description"
        created.total_documents = 100

        updated = repository.update(asset=created)

        assert updated.description == "Updated description"
        assert updated.total_documents == 100

    def test_update_document_set_not_found(self, repository):
        """Test updating nonexistent document set raises error."""
        doc_set = DocumentSet(
            asset_id="nonexistent-id",
            name="Test Documents",
        )

        with pytest.raises(DocpipeException):
            repository.update(asset=doc_set)

    def test_update_document_set_updates_timestamp(self, repository, sample_document_set):
        """Test that update modifies updated_at timestamp."""
        created = repository.save(asset=sample_document_set)
        original_updated_at = created.updated_at

        created.description = "New description"
        updated = repository.update(asset=created)

        assert updated.updated_at >= original_updated_at


class TestSaveDocumentSet:
    """Test save is implemented via AssetRepository contract."""

    def test_save_is_implemented(self, repository, sample_document_set):
        """Test that save method is available (AssetRepository contract)."""
        assert hasattr(repository, "save")
        created = repository.save(asset=sample_document_set)
        assert created.asset_id == sample_document_set.asset_id


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
            )
            repository.save(asset=doc_set)

        result = repository.list_all()

        assert len(result) == 5

    def test_list_all_ordered_by_created_at(self, repository):
        """Test that results are ordered by created_at descending."""
        doc_sets = []
        for i in range(3):
            doc_set = DocumentSet(
                name=f"Documents {i}",
            )
            created = repository.save(asset=doc_set)
            doc_sets.append(created)

        result = repository.list_all()

        assert result[0].asset_id == doc_sets[2].asset_id
        assert result[2].asset_id == doc_sets[0].asset_id


class TestExists:
    """Test checking document set existence."""

    def test_exists_true(self, repository, sample_document_set):
        """Test exists returns True for existing document set."""
        created = repository.save(asset=sample_document_set)

        assert repository.exists(asset_id=created.asset_id or "") is True

    def test_exists_false(self, repository):
        """Test exists returns False for nonexistent document set."""
        assert repository.exists(asset_id="nonexistent-id") is False


class TestExistsByName:
    """Test exists_by_name is implemented via AssetRepository contract."""

    def test_exists_by_name_implemented(self, repository, sample_document_set):
        """Test that exists_by_name method is available (AssetRepository contract)."""
        assert hasattr(repository, "exists_by_name")
        repository.save(asset=sample_document_set)
        assert repository.exists_by_name(name=sample_document_set.name) is True
        assert repository.exists_by_name(name="Nonexistent") is False


class TestDeleteDocumentSet:
    """Test deleting document sets."""

    def test_delete_document_set(self, repository, sample_document_set):
        """Test deleting an existing document set."""
        created = repository.save(asset=sample_document_set)

        result = repository.delete(asset_id=created.asset_id or "")

        assert result is True
        assert repository.exists(asset_id=created.asset_id or "") is False

    def test_delete_document_set_not_found(self, repository):
        """Test deleting nonexistent document set returns False."""
        result = repository.delete(asset_id="nonexistent-id")

        assert result is False

    def test_delete_document_set_removes_from_list(self, repository):
        """Test that deleted document set is removed from list."""
        doc_sets = []
        for i in range(3):
            doc_set = DocumentSet(
                name=f"Documents {i}",
            )
            created = repository.save(asset=doc_set)
            doc_sets.append(created)

        repository.delete(asset_id=doc_sets[1].asset_id or "")

        all_sets = repository.list_all()
        assert len(all_sets) == 2
        assert doc_sets[1].asset_id not in [ds.asset_id for ds in all_sets]


class TestRepositoryErrorHandling:
    """Test error handling in repository operations."""

    def test_create_without_id_raises_error(self, repository):
        """Test that saving without asset_id raises error."""
        doc_set = DocumentSet(
            name="Test Documents",
        )
        doc_set.asset_id = None

        with pytest.raises(DocpipeException, match="asset_id cannot be None"):
            repository.save(asset=doc_set)

    def test_update_without_id_raises_error(self, repository):
        """Test that updating without asset_id raises error."""
        doc_set = DocumentSet(
            name="Test Documents",
        )
        doc_set.asset_id = None

        with pytest.raises(DocpipeException, match="asset_id cannot be None"):
            repository.update(asset=doc_set)


class TestRepositoryWithInMemoryDatabase:
    """Test repository with in-memory database."""

    def test_in_memory_repository(self):
        """Test repository operations with in-memory database."""
        storage = DuckDBKeyValueStorage(database_path=":memory:")
        repository = DuckDBAssetRepository(asset_type=DocumentSet, key_value_storage=storage, database_path=":memory:")
        repository._collection = "document_sets"

        doc_set = DocumentSet(name="Test Documents")
        created = repository.save(asset=doc_set)

        retrieved = repository.find_by_id(asset_id=created.asset_id or "")
        assert retrieved is not None
        assert retrieved.name == "Test Documents"

        all_sets = repository.list_all()
        assert len(all_sets) == 1
