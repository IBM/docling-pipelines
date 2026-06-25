"""Unit tests for DuckDB adapters implementing hexagonal architecture ports."""

import pyarrow as pa
import pytest

from docpipe.core.assets.document_sets.adapters.duckdb.data_store import (
    DuckDBDocumentSetDataStore,
)
from docpipe.core.assets.document_sets.adapters.duckdb.metadata_repository import (
    DuckDBDocumentSetMetadataRepository,
)
from docpipe.core.assets.document_sets.domain.models.document_set import DocumentSet
from docpipe.exceptions.docpipe_exceptions import DocpipeException
from docpipe.exceptions.error_codes import ErrorCode
from docpipe.storage import StorageFactory


@pytest.fixture
def temp_db_path(*, tmp_path):
    """Create temporary database path."""
    return str(tmp_path / "test.db")


@pytest.fixture
def metadata_repository(*, temp_db_path):
    """Create metadata repository for testing with dependency injection."""
    key_value_storage = StorageFactory.create_key_value_storage(storage_type="duckdb", database_path=temp_db_path)
    return DuckDBDocumentSetMetadataRepository(key_value_storage=key_value_storage, database_path=temp_db_path)


@pytest.fixture
def data_store(*, temp_db_path):
    """Create data store for testing with dependency injection."""
    table_storage = StorageFactory.create_table_storage(storage_type="duckdb", database_path=temp_db_path)
    return DuckDBDocumentSetDataStore(table_storage=table_storage)


@pytest.fixture
def sample_document_set(*, temp_db_path):
    """Create a sample document set."""
    return DocumentSet(
        id="test-id-1",
        name="test_set",
        description="Test description",
        table_name="test_table",
        database_path=temp_db_path,
    )


class TestDuckDBMetadataRepository:
    """Test DuckDBDocumentSetMetadataRepository adapter."""

    def test_create_document_set(self, *, metadata_repository, sample_document_set):
        """Test creating a document set."""
        created = metadata_repository.create(document_set=sample_document_set)

        assert created.id == sample_document_set.id
        assert created.name == sample_document_set.name
        assert created.description == sample_document_set.description
        assert created.table_name == sample_document_set.table_name

    def test_get_by_id(self, *, metadata_repository, temp_db_path):
        """Test retrieving document set by ID."""
        doc_set = DocumentSet(
            id="test-id-2",
            name="test_set_2",
            description="Test",
            table_name="test_table_2",
            database_path=temp_db_path,
        )
        metadata_repository.create(document_set=doc_set)

        retrieved = metadata_repository.get_by_id(document_set_id="test-id-2")

        assert retrieved.id == doc_set.id
        assert retrieved.name == doc_set.name
        assert retrieved.database_path == temp_db_path

    def test_get_by_name(self, *, metadata_repository, temp_db_path):
        """Test retrieving document set by name."""
        doc_set = DocumentSet(
            id="test-id-3",
            name="unique_name",
            description="Test",
            table_name="test_table_3",
            database_path=temp_db_path,
        )
        metadata_repository.create(document_set=doc_set)

        retrieved = metadata_repository.get_by_name(name="unique_name")

        assert retrieved.id == doc_set.id
        assert retrieved.name == "unique_name"

    def test_get_nonexistent_raises_error(self, *, metadata_repository):
        """Test getting nonexistent document set raises error."""
        with pytest.raises(DocpipeException) as exc_info:
            metadata_repository.get_by_id(document_set_id="nonexistent")

        assert exc_info.value.error_code == ErrorCode.DOCUMENT_SET_NOT_FOUND

    def test_get_by_name_nonexistent_raises_error(self, *, metadata_repository):
        """Test getting nonexistent document set by name raises error."""
        with pytest.raises(DocpipeException) as exc_info:
            metadata_repository.get_by_name(name="missing_name")

        assert exc_info.value.error_code == ErrorCode.DOCUMENT_SET_NOT_FOUND

    def test_list_all(self, *, metadata_repository, temp_db_path):
        """Test listing all document sets."""
        for i in range(3):
            doc_set = DocumentSet(
                id=f"test-id-{i}",
                name=f"test_set_{i}",
                description=f"Test {i}",
                table_name=f"test_table_{i}",
                database_path=temp_db_path,
            )
            metadata_repository.create(document_set=doc_set)

        all_sets = metadata_repository.list_all()

        assert len(all_sets) == 3
        assert {document_set.name for document_set in all_sets} == {
            "test_set_0",
            "test_set_1",
            "test_set_2",
        }

    def test_update_document_set(self, *, metadata_repository, temp_db_path):
        """Test updating document set metadata."""
        doc_set = DocumentSet(
            id="test-id-update",
            name="original_name",
            description="Original description",
            table_name="test_table",
            database_path=temp_db_path,
        )
        created = metadata_repository.create(document_set=doc_set)

        created.description = "Updated description"
        updated = metadata_repository.update(document_set=created)

        assert updated.description == "Updated description"
        assert updated.name == "original_name"

        retrieved = metadata_repository.get_by_id(document_set_id="test-id-update")
        assert retrieved.description == "Updated description"

    def test_update_nonexistent_document_set_raises_error(self, *, metadata_repository, temp_db_path):
        """Test that updating a nonexistent document set raises an error."""
        doc_set = DocumentSet(
            id="missing-id",
            name="missing_name",
            description="Missing",
            table_name="missing_table",
            database_path=temp_db_path,
        )

        # Should raise error when trying to update nonexistent document set
        with pytest.raises(DocpipeException) as exc_info:
            metadata_repository.update(document_set=doc_set)
        assert exc_info.value.error_code == ErrorCode.DOCUMENT_SET_NOT_FOUND

    def test_delete_document_set(self, *, metadata_repository, temp_db_path):
        """Test deleting document set."""
        doc_set = DocumentSet(
            id="test-id-delete",
            name="to_delete",
            description="Will be deleted",
            table_name="test_table",
            database_path=temp_db_path,
        )
        metadata_repository.create(document_set=doc_set)

        result = metadata_repository.delete(document_set_id="test-id-delete")

        assert result is True
        with pytest.raises(DocpipeException) as exc_info:
            metadata_repository.get_by_id(document_set_id="test-id-delete")
        assert exc_info.value.error_code == ErrorCode.DOCUMENT_SET_NOT_FOUND

    def test_delete_nonexistent_document_set_returns_false(self, *, metadata_repository):
        """Test deleting nonexistent document set returns False."""
        result = metadata_repository.delete(document_set_id="missing-id")
        assert result is False

    def test_exists(self, *, metadata_repository, sample_document_set):
        """Test checking document set existence."""
        assert metadata_repository.exists(document_set_id=sample_document_set.id) is False

        metadata_repository.create(document_set=sample_document_set)

        assert metadata_repository.exists(document_set_id=sample_document_set.id) is True

    def test_create_duplicate_name_raises_error(self, *, metadata_repository, temp_db_path):
        """Test creating document sets with duplicate name raises error."""
        first = DocumentSet(
            id="test-id-a",
            name="duplicate_name",
            description="First",
            table_name="test_table_a",
            database_path=temp_db_path,
        )
        second = DocumentSet(
            id="test-id-b",
            name="duplicate_name",
            description="Second",
            table_name="test_table_b",
            database_path=temp_db_path,
        )

        metadata_repository.create(document_set=first)

        with pytest.raises(DocpipeException) as exc_info:
            metadata_repository.create(document_set=second)

        assert exc_info.value.error_code == ErrorCode.DOCUMENT_SET_ALREADY_EXISTS

    def test_health_check(self, *, metadata_repository, temp_db_path):
        """Test health check returns success."""
        result = metadata_repository.health_check()

        assert result["healthy"] is True
        assert result["details"]["database_path"] == temp_db_path

    def test_validate_config(self):
        """Test config validation."""
        assert DuckDBDocumentSetMetadataRepository.validate_config(config={"database_path": "test.db"}) == []
        assert DuckDBDocumentSetMetadataRepository.validate_config(config={}) == [
            "Missing required configuration: 'database_path'"
        ]
        assert DuckDBDocumentSetMetadataRepository.validate_config(config={"database_path": ""}) == [
            "Configuration 'database_path' cannot be empty"
        ]

    def test_commit_without_active_transaction_raises_error(self, *, metadata_repository):
        """Test commit without active transaction raises error."""
        with pytest.raises(DocpipeException) as exc_info:
            metadata_repository.commit_transaction()

        assert exc_info.value.error_code == ErrorCode.DOCUMENT_SET_TRANSACTION_FAILED

    def test_rollback_without_active_transaction_raises_error(self, *, metadata_repository):
        """Test rollback without active transaction raises error."""
        with pytest.raises(DocpipeException) as exc_info:
            metadata_repository.rollback_transaction()

        assert exc_info.value.error_code == ErrorCode.DOCUMENT_SET_TRANSACTION_FAILED


class TestDuckDBDataStore:
    """Test DuckDBDocumentSetDataStore adapter."""

    def test_create_data_table(self, *, data_store):
        """Test creating data table with schema."""
        schema = pa.schema(
            [
                ("id", pa.string()),
                ("content", pa.string()),
                ("metadata", pa.string()),
            ]
        )

        data_store.create_data_table(table_name="test_table", schema=schema)

        assert data_store.table_exists(table_name="test_table")

    def test_create_duplicate_table_raises_error(self, *, data_store):
        """Test creating duplicate table raises error."""
        schema = pa.schema([("id", pa.string())])

        data_store.create_data_table(table_name="duplicate_table", schema=schema)

        with pytest.raises(DocpipeException) as exc_info:
            data_store.create_data_table(table_name="duplicate_table", schema=schema)

        assert exc_info.value.error_code == ErrorCode.DOCUMENT_SET_TABLE_ALREADY_EXISTS

    def test_table_exists(self, *, data_store):
        """Test checking if table exists."""
        assert data_store.table_exists(table_name="nonexistent_table") is False

        schema = pa.schema([("id", pa.string())])
        data_store.create_data_table(table_name="exists_table", schema=schema)

        assert data_store.table_exists(table_name="exists_table") is True

    def test_upsert_data(self, *, data_store):
        """Test upserting data into table."""
        schema = pa.schema(
            [
                ("id", pa.string()),
                ("content", pa.string()),
            ]
        )
        data_store.create_data_table(table_name="upsert_table", schema=schema)

        data = pa.table(
            {
                "id": ["1", "2", "3"],
                "content": ["test1", "test2", "test3"],
            }
        )

        data_store.upsert_document_set_data(table_name="upsert_table", data=data)

        count = data_store.get_row_count(table_name="upsert_table")
        assert count == 3

    def test_upsert_nonexistent_table_raises_error(self, *, data_store):
        """Test upserting into nonexistent table raises error."""
        data = pa.table({"id": ["1"], "content": ["test1"]})

        with pytest.raises(DocpipeException) as exc_info:
            data_store.upsert_document_set_data(table_name="missing_table", data=data)

        assert exc_info.value.error_code == ErrorCode.DOCUMENT_SET_TABLE_NOT_FOUND

    def test_upsert_without_id_column_raises_error(self, *, data_store):
        """Test upserting data without id column raises error."""
        schema = pa.schema([("content", pa.string())])
        data_store.create_data_table(table_name="bad_upsert_table", schema=schema)

        data = pa.table({"content": ["test1"]})

        with pytest.raises(DocpipeException) as exc_info:
            data_store.upsert_document_set_data(table_name="bad_upsert_table", data=data)

        assert exc_info.value.error_code == ErrorCode.DOCUMENT_SET_SCHEMA_MISMATCH

    def test_get_row_count(self, *, data_store):
        """Test getting row count from table."""
        schema = pa.schema([("id", pa.string())])
        data_store.create_data_table(table_name="count_table", schema=schema)

        assert data_store.get_row_count(table_name="count_table") == 0

        data = pa.table({"id": ["1", "2"]})
        data_store.upsert_document_set_data(table_name="count_table", data=data)

        assert data_store.get_row_count(table_name="count_table") == 2

    def test_get_row_count_nonexistent_table_raises_error(self, *, data_store):
        """Test getting row count for nonexistent table raises error."""
        with pytest.raises(DocpipeException) as exc_info:
            data_store.get_row_count(table_name="missing_table")

        assert exc_info.value.error_code == ErrorCode.DOCUMENT_SET_TABLE_NOT_FOUND

    def test_get_document_set_data(self, *, data_store):
        """Test retrieving data from table."""
        schema = pa.schema(
            [
                ("id", pa.string()),
                ("value", pa.int64()),
            ]
        )
        data_store.create_data_table(table_name="query_table", schema=schema)

        data = pa.table(
            {
                "id": ["1", "2", "3"],
                "value": [10, 20, 30],
            }
        )
        data_store.upsert_document_set_data(table_name="query_table", data=data)

        result = data_store.get_document_set_data(table_name="query_table", limit=None)

        assert result.num_rows == 3
        assert result.column("id")[1].as_py() == "2"
        assert result.column("value")[1].as_py() == 20

    def test_get_document_set_data_with_limit(self, *, data_store):
        """Test retrieving limited data from table."""
        schema = pa.schema(
            [
                ("id", pa.string()),
                ("value", pa.int64()),
            ]
        )
        data_store.create_data_table(table_name="limited_query_table", schema=schema)

        data = pa.table(
            {
                "id": ["1", "2", "3"],
                "value": [10, 20, 30],
            }
        )
        data_store.upsert_document_set_data(table_name="limited_query_table", data=data)

        result = data_store.get_document_set_data(table_name="limited_query_table", limit=2)

        assert result.num_rows == 2

    def test_get_document_set_data_nonexistent_table_raises_error(self, *, data_store):
        """Test retrieving data from nonexistent table raises error."""
        with pytest.raises(DocpipeException) as exc_info:
            data_store.get_document_set_data(table_name="missing_table", limit=None)

        assert exc_info.value.error_code == ErrorCode.DOCUMENT_SET_TABLE_NOT_FOUND

    def test_delete_data(self, *, data_store):
        """Test deleting data table."""
        schema = pa.schema([("id", pa.string())])
        data_store.create_data_table(table_name="delete_table", schema=schema)

        data = pa.table({"id": ["1", "2", "3"]})
        data_store.upsert_document_set_data(table_name="delete_table", data=data)

        result = data_store.delete_document_set_data(table_name="delete_table")

        assert result is True
        assert data_store.table_exists(table_name="delete_table") is False

    def test_delete_nonexistent_table_returns_false(self, *, data_store):
        """Test deleting nonexistent table returns False."""
        result = data_store.delete_document_set_data(table_name="missing_table")
        assert result is False

    def test_health_check(self, *, data_store, temp_db_path):
        """Test health check after database file is initialized."""
        schema = pa.schema([("id", pa.string())])
        data_store.create_data_table(table_name="health_table", schema=schema)

        result = data_store.health_check()

        assert result["healthy"] is True
        assert result["details"]["database_path"] == temp_db_path

    def test_validate_config(self):
        """Test config validation."""
        assert DuckDBDocumentSetDataStore.validate_config(config={"database_path": "test.db"}) == []
        assert DuckDBDocumentSetDataStore.validate_config(config={}) == [
            "Missing required configuration: 'database_path'"
        ]
        assert DuckDBDocumentSetDataStore.validate_config(config={"database_path": ""}) == [
            "Configuration 'database_path' cannot be empty"
        ]

    def test_get_table_metrics(self, *, data_store):
        """Test efficient metrics computation without loading full table."""
        # Create table with metrics columns
        schema = pa.schema(
            [
                ("id", pa.string()),
                ("content", pa.string()),
                ("size", pa.int64()),
                ("pages_processed", pa.int64()),
            ]
        )
        data_store.create_data_table(table_name="metrics_table", schema=schema)

        # Insert test data
        data = pa.table(
            {
                "id": ["1", "2", "3"],
                "content": ["test1", "test2", "test3"],
                "size": [100, 200, 300],
                "pages_processed": [1, 2, 3],
            }
        )
        data_store.upsert_document_set_data(table_name="metrics_table", data=data)

        # Get metrics using SQL aggregation
        metrics = data_store.get_table_metrics(table_name="metrics_table")

        # Verify correct aggregates
        assert metrics["total_documents"] == 3
        assert metrics["total_size_bytes"] == 600  # 100 + 200 + 300
        assert metrics["total_pages"] == 6  # 1 + 2 + 3

    def test_get_table_metrics_empty_table(self, *, data_store):
        """Test metrics computation for empty table."""
        schema = pa.schema(
            [
                ("id", pa.string()),
                ("size", pa.int64()),
                ("pages_processed", pa.int64()),
            ]
        )
        data_store.create_data_table(table_name="empty_metrics_table", schema=schema)

        metrics = data_store.get_table_metrics(table_name="empty_metrics_table")

        assert metrics["total_documents"] == 0
        assert metrics["total_size_bytes"] == 0
        assert metrics["total_pages"] == 0

    def test_get_table_metrics_nonexistent_table_raises_error(self, *, data_store):
        """Test getting metrics for nonexistent table raises error."""
        with pytest.raises(DocpipeException) as exc_info:
            data_store.get_table_metrics(table_name="missing_table")

        assert exc_info.value.error_code == ErrorCode.DOCUMENT_SET_TABLE_NOT_FOUND
