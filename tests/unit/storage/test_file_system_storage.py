"""Tests for FileSystemStorage (key-value storage)."""

import pytest

from docpipe.storage.exceptions import StorageValidationError
from docpipe.storage.factory import StorageFactory
from docpipe.storage.file_system.key_value_storage import FileSystemStorage


class TestFileSystemStorageBasicOperations:
    """Test basic CRUD operations."""

    def test_save_and_get_record(self, tmp_path):
        """Test saving and retrieving a record."""
        storage = FileSystemStorage(base_dir=str(tmp_path))
        data = {"id": "test-123", "name": "Test Record", "value": 42}

        storage.save_record(collection="test", key="test-123", data=data)
        retrieved = storage.get_record(collection="test", key="test-123")

        assert retrieved == data

    def test_get_nonexistent_record(self, tmp_path):
        """Test retrieving a non-existent record returns None."""
        storage = FileSystemStorage(base_dir=str(tmp_path))
        result = storage.get_record(collection="test", key="nonexistent")
        assert result is None

    def test_list_records(self, tmp_path):
        """Test listing all records in a collection."""
        storage = FileSystemStorage(base_dir=str(tmp_path))
        data1 = {"id": "rec-1", "name": "Record 1"}
        data2 = {"id": "rec-2", "name": "Record 2"}

        storage.save_record(collection="test", key="rec-1", data=data1)
        storage.save_record(collection="test", key="rec-2", data=data2)

        records = storage.list_records(collection="test")

        assert len(records) == 2
        assert data1 in records
        assert data2 in records

    def test_delete_record(self, tmp_path):
        """Test deleting a record."""
        storage = FileSystemStorage(base_dir=str(tmp_path))
        data = {"id": "test-123", "name": "Test Record"}

        storage.save_record(collection="test", key="test-123", data=data)
        assert storage.record_exists(collection="test", key="test-123")

        deleted = storage.delete_record(collection="test", key="test-123")
        assert deleted is True
        assert not storage.record_exists(collection="test", key="test-123")

    def test_delete_nonexistent_record(self, tmp_path):
        """Test deleting a non-existent record returns False."""
        storage = FileSystemStorage(base_dir=str(tmp_path))
        deleted = storage.delete_record(collection="test", key="nonexistent")
        assert deleted is False


class TestFileSystemStorageExistence:
    """Test existence checking methods."""

    def test_collection_exists(self, tmp_path):
        """Test checking if collection exists."""
        storage = FileSystemStorage(base_dir=str(tmp_path))
        assert not storage.collection_exists(collection="test")

        storage.save_record(collection="test", key="test-123", data={"id": "test-123"})

        assert storage.collection_exists(collection="test")

    def test_record_exists(self, tmp_path):
        """Test checking if record exists."""
        storage = FileSystemStorage(base_dir=str(tmp_path))
        assert not storage.record_exists(collection="test", key="test-123")

        storage.save_record(collection="test", key="test-123", data={"id": "test-123"})

        assert storage.record_exists(collection="test", key="test-123")


class TestFileSystemStorageUpsert:
    """Test upsert behavior."""

    def test_upsert_behavior(self, tmp_path):
        """Test that save_record updates existing records."""
        storage = FileSystemStorage(base_dir=str(tmp_path))
        data1 = {"id": "test-123", "name": "Original", "value": 1}
        data2 = {"id": "test-123", "name": "Updated", "value": 2}

        storage.save_record(collection="test", key="test-123", data=data1)
        storage.save_record(collection="test", key="test-123", data=data2)

        retrieved = storage.get_record(collection="test", key="test-123")
        assert retrieved == data2

        # Should only have one record
        records = storage.list_records(collection="test")
        assert len(records) == 1


class TestFileSystemStorageMultipleCollections:
    """Test isolation between collections."""

    def test_multiple_collections(self, tmp_path):
        """Test that different collections are isolated."""
        storage = FileSystemStorage(base_dir=str(tmp_path))
        data1 = {"id": "test-1", "type": "flows"}
        data2 = {"id": "test-2", "type": "document_sets"}

        storage.save_record(collection="flows", key="test-1", data=data1)
        storage.save_record(collection="document_sets", key="test-2", data=data2)

        flows = storage.list_records(collection="flows")
        doc_sets = storage.list_records(collection="document_sets")

        assert len(flows) == 1
        assert len(doc_sets) == 1
        assert flows[0] == data1
        assert doc_sets[0] == data2


class TestFileSystemStorageSingleton:
    """Test singleton pattern."""

    def test_same_path_returns_same_instance(self, tmp_path):
        """Test that same base directory returns the same instance."""
        base_dir = str(tmp_path / "storage")

        storage1 = FileSystemStorage(base_dir=base_dir)
        storage2 = FileSystemStorage(base_dir=base_dir)

        assert storage1 is storage2

    def test_different_paths_return_different_instances(self, tmp_path):
        """Test that different base directories return different instances."""
        path1 = str(tmp_path / "storage1")
        path2 = str(tmp_path / "storage2")

        storage1 = FileSystemStorage(base_dir=path1)
        storage2 = FileSystemStorage(base_dir=path2)

        assert storage1 is not storage2

    def test_normalized_paths_return_same_instance(self, tmp_path):
        """Test that normalized paths return the same instance."""
        storage_dir = tmp_path / "storage"
        storage_dir.mkdir()

        storage1 = FileSystemStorage(base_dir=str(storage_dir))
        storage2 = FileSystemStorage(base_dir=str(storage_dir.resolve()))

        assert storage1 is storage2


class TestFileSystemStorageFactory:
    """Test factory integration."""

    def test_factory_create_key_value_storage(self, tmp_path):
        """Test creating FileSystemStorage through factory."""
        storage = StorageFactory.create_key_value_storage(storage_type="filesystem", base_dir=str(tmp_path))

        assert isinstance(storage, FileSystemStorage)

        # Test it works
        storage.save_record(collection="test", key="key1", data={"value": 1})
        assert storage.get_record(collection="test", key="key1") == {"value": 1}

    def test_factory_singleton_consistency(self, tmp_path):
        """Test that factory and direct creation return same instance."""
        base_dir = str(tmp_path / "storage")

        storage1 = StorageFactory.create_key_value_storage(storage_type="filesystem", base_dir=base_dir)
        storage2 = FileSystemStorage(base_dir=base_dir)

        assert storage1 is storage2


class TestFileSystemStorageValidation:
    """Test input validation."""

    def test_invalid_collection_name_empty(self, tmp_path):
        """Test that empty collection name is rejected."""
        storage = FileSystemStorage(base_dir=str(tmp_path))
        with pytest.raises(StorageValidationError, match="Collection name cannot be empty"):
            storage.save_record(collection="", key="test", data={"id": "test"})

    def test_invalid_key_empty(self, tmp_path):
        """Test that empty key is rejected."""
        storage = FileSystemStorage(base_dir=str(tmp_path))
        with pytest.raises(StorageValidationError, match="Key cannot be empty"):
            storage.save_record(collection="test", key="", data={"id": "test"})

    def test_invalid_collection_name_path_traversal(self, tmp_path):
        """Test that path traversal in collection name is rejected."""
        storage = FileSystemStorage(base_dir=str(tmp_path))
        with pytest.raises(StorageValidationError, match="Invalid collection name"):
            storage.save_record(collection="../etc", key="test", data={"id": "test"})

    def test_invalid_key_path_traversal(self, tmp_path):
        """Test that path traversal in key is rejected."""
        storage = FileSystemStorage(base_dir=str(tmp_path))
        with pytest.raises(StorageValidationError, match="Invalid key"):
            storage.save_record(collection="test", key="../passwd", data={"id": "test"})


class TestFileSystemStorageAtomicWrites:
    """Test atomic write operations."""

    def test_atomic_write_creates_temp_file(self, tmp_path):
        """Test that writes use temporary files for atomicity."""
        storage = FileSystemStorage(base_dir=str(tmp_path))
        data = {"id": "test-123", "name": "Test Record"}

        storage.save_record(collection="test", key="test-123", data=data)

        # Verify the final file exists
        collection_dir = tmp_path / "test"
        record_file = collection_dir / "test-123.json"
        assert record_file.exists()

        # Verify no temp files remain
        temp_files = list(collection_dir.glob("*.tmp"))
        assert len(temp_files) == 0
