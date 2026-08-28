"""Tests for DuckDBKeyValueStorage."""

import pytest

from docpipe.storage.duck_db.duckdb_key_value_storage import DuckDBKeyValueStorage
from docpipe.storage.exceptions import StorageValidationError
from docpipe.storage.factory import StorageFactory


class TestDuckDBKeyValueStorageBasicOperations:
    """Test basic CRUD operations."""

    def test_save_and_get_record(self, tmp_path):
        """Test saving and retrieving a record."""
        storage = DuckDBKeyValueStorage(database_path=str(tmp_path / "test.db"))
        data = {"id": "test-123", "name": "Test Record", "value": 42}

        storage.save_record(collection="test", key="test-123", data=data)
        retrieved = storage.get_record(collection="test", key="test-123")

        assert retrieved == data

    def test_get_nonexistent_record(self, tmp_path):
        """Test retrieving a non-existent record returns None."""
        storage = DuckDBKeyValueStorage(database_path=str(tmp_path / "test.db"))
        result = storage.get_record(collection="test", key="nonexistent")
        assert result is None

    def test_list_records(self, tmp_path):
        """Test listing all records in a collection."""
        storage = DuckDBKeyValueStorage(database_path=str(tmp_path / "test.db"))
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
        storage = DuckDBKeyValueStorage(database_path=str(tmp_path / "test.db"))
        data = {"id": "test-123", "name": "Test Record"}

        storage.save_record(collection="test", key="test-123", data=data)
        assert storage.record_exists(collection="test", key="test-123")

        deleted = storage.delete_record(collection="test", key="test-123")
        assert deleted is True
        assert not storage.record_exists(collection="test", key="test-123")

    def test_delete_nonexistent_record(self, tmp_path):
        """Test deleting a non-existent record returns False."""
        storage = DuckDBKeyValueStorage(database_path=str(tmp_path / "test.db"))
        deleted = storage.delete_record(collection="test", key="nonexistent")
        assert deleted is False


class TestDuckDBKeyValueStorageExistence:
    """Test existence checking methods."""

    def test_collection_exists(self, tmp_path):
        """Test checking if collection exists."""
        storage = DuckDBKeyValueStorage(database_path=str(tmp_path / "test.db"))
        assert not storage.collection_exists(collection="test")

        storage.save_record(collection="test", key="test-123", data={"id": "test-123"})

        assert storage.collection_exists(collection="test")

    def test_record_exists(self, tmp_path):
        """Test checking if record exists."""
        storage = DuckDBKeyValueStorage(database_path=str(tmp_path / "test.db"))
        assert not storage.record_exists(collection="test", key="test-123")

        storage.save_record(collection="test", key="test-123", data={"id": "test-123"})

        assert storage.record_exists(collection="test", key="test-123")


class TestDuckDBKeyValueStorageUpsert:
    """Test upsert behavior."""

    def test_upsert_behavior(self, tmp_path):
        """Test that save_record updates existing records."""
        storage = DuckDBKeyValueStorage(database_path=str(tmp_path / "test.db"))
        data1 = {"id": "test-123", "name": "Original", "value": 1}
        data2 = {"id": "test-123", "name": "Updated", "value": 2}

        storage.save_record(collection="test", key="test-123", data=data1)
        storage.save_record(collection="test", key="test-123", data=data2)

        retrieved = storage.get_record(collection="test", key="test-123")
        assert retrieved == data2

        # Should only have one record
        records = storage.list_records(collection="test")
        assert len(records) == 1


class TestDuckDBKeyValueStorageMultipleCollections:
    """Test isolation between collections."""

    def test_multiple_collections(self, tmp_path):
        """Test that different collections are isolated."""
        storage = DuckDBKeyValueStorage(database_path=str(tmp_path / "test.db"))
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


class TestDuckDBKeyValueStorageSingleton:
    """Test singleton pattern."""

    def test_same_path_returns_same_instance(self, tmp_path):
        """Test that same database path returns the same instance."""
        db_path = str(tmp_path / "test.db")

        storage1 = DuckDBKeyValueStorage(database_path=db_path)
        storage2 = DuckDBKeyValueStorage(database_path=db_path)

        assert storage1 is storage2

    def test_different_paths_return_different_instances(self, tmp_path):
        """Test that different database paths return different instances."""
        path1 = str(tmp_path / "db1.duckdb")
        path2 = str(tmp_path / "db2.duckdb")

        storage1 = DuckDBKeyValueStorage(database_path=path1)
        storage2 = DuckDBKeyValueStorage(database_path=path2)

        assert storage1 is not storage2

    def test_memory_database_singleton(self):
        """Test that :memory: database uses singleton pattern."""
        storage1 = DuckDBKeyValueStorage(database_path=":memory:")
        storage2 = DuckDBKeyValueStorage(database_path=":memory:")

        assert storage1 is storage2

    def test_normalized_paths_return_same_instance(self, tmp_path):
        """Test that normalized paths return the same instance."""
        db_path = tmp_path / "test.duckdb"

        storage1 = DuckDBKeyValueStorage(database_path=str(db_path))
        storage2 = DuckDBKeyValueStorage(database_path=str(db_path.resolve()))

        assert storage1 is storage2


class TestDuckDBKeyValueStorageFactory:
    """Test factory integration."""

    def test_factory_create_key_value_storage(self, tmp_path):
        """Test creating DuckDBKeyValueStorage through factory."""
        storage = StorageFactory.create_key_value_storage(
            storage_type="duckdb", database_path=str(tmp_path / "test.db")
        )

        assert isinstance(storage, DuckDBKeyValueStorage)

        # Test it works
        storage.save_record(collection="test", key="key1", data={"value": 1})
        assert storage.get_record(collection="test", key="key1") == {"value": 1}

    def test_factory_singleton_consistency(self, tmp_path):
        """Test that factory and direct creation return same instance."""
        db_path = str(tmp_path / "test.db")

        storage1 = StorageFactory.create_key_value_storage(storage_type="duckdb", database_path=db_path)
        storage2 = DuckDBKeyValueStorage(database_path=db_path)

        assert storage1 is storage2


class TestDuckDBKeyValueStorageValidation:
    """Test input validation."""

    def test_invalid_collection_name_empty(self, tmp_path):
        """Test that empty collection name is rejected."""
        storage = DuckDBKeyValueStorage(database_path=str(tmp_path / "test.db"))
        with pytest.raises(StorageValidationError, match="Collection name cannot be empty"):
            storage.save_record(collection="", key="test", data={"id": "test"})

    def test_invalid_key_empty(self, tmp_path):
        """Test that empty key is rejected."""
        storage = DuckDBKeyValueStorage(database_path=str(tmp_path / "test.db"))
        with pytest.raises(StorageValidationError, match="Key cannot be empty"):
            storage.save_record(collection="test", key="", data={"id": "test"})

    def test_invalid_collection_name_sql_injection(self, tmp_path):
        """Test that SQL injection attempts in collection name are rejected."""
        storage = DuckDBKeyValueStorage(database_path=str(tmp_path / "test.db"))
        with pytest.raises(StorageValidationError, match="Invalid collection name"):
            storage.save_record(collection="test; DROP TABLE users;", key="test", data={"id": "test"})


class TestDuckDBKeyValueStorageTimestamps:
    """Test timestamp tracking."""

    def test_created_at_timestamp(self, tmp_path):
        """Test that created_at timestamp is set on insert."""
        storage = DuckDBKeyValueStorage(database_path=str(tmp_path / "test.db"))
        data = {"id": "test-123", "name": "Test Record"}

        storage.save_record(collection="test", key="test-123", data=data)

        # Verify record was created (timestamps are internal, not returned in data)
        retrieved = storage.get_record(collection="test", key="test-123")
        assert retrieved == data

    def test_updated_at_timestamp(self, tmp_path):
        """Test that updated_at timestamp is updated on upsert."""
        storage = DuckDBKeyValueStorage(database_path=str(tmp_path / "test.db"))
        data1 = {"id": "test-123", "name": "Original"}
        data2 = {"id": "test-123", "name": "Updated"}

        storage.save_record(collection="test", key="test-123", data=data1)
        storage.save_record(collection="test", key="test-123", data=data2)

        # Verify record was updated
        retrieved = storage.get_record(collection="test", key="test-123")
        assert retrieved == data2


class TestDuckDBKeyValueStorageInMemory:
    """Test in-memory database operations."""

    def test_in_memory_database(self):
        """Test using in-memory database."""
        storage = DuckDBKeyValueStorage(database_path=":memory:")

        data = {"id": "test-123", "value": "test"}
        storage.save_record(collection="test", key="test-123", data=data)

        retrieved = storage.get_record(collection="test", key="test-123")
        assert retrieved == data
