"""Tests for DuckDBTableStorage (PyArrow table storage)."""

import pyarrow as pa
import pytest

from docpipe.storage.duck_db.table_storage import DuckDBTableStorage
from docpipe.storage.exceptions import StorageException, StorageValidationError
from docpipe.storage.factory import StorageFactory


@pytest.fixture
def storage(tmp_path):
    """Create a DuckDBTableStorage instance."""
    return DuckDBTableStorage(database_path=str(tmp_path / "test.db"))


@pytest.fixture
def sample_schema():
    """Create a sample PyArrow schema."""
    return pa.schema(
        [
            ("id", pa.string()),
            ("name", pa.string()),
            ("content", pa.string()),
            ("size", pa.int64()),
            ("pages_processed", pa.int32()),
        ]
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


class TestDuckDBTableStorageTableCreation:
    """Test table creation."""

    def test_create_table(self, storage, sample_schema):
        """Test creating a table from PyArrow schema."""
        table_name = "test_table"
        storage.create_table(table_name=table_name, schema=sample_schema)
        assert storage.table_exists(table_name=table_name)

    def test_create_table_with_id_primary_key(self, storage, sample_schema):
        """Test that id column becomes primary key."""
        table_name = "test_table"
        storage.create_table(table_name=table_name, schema=sample_schema)
        assert storage.table_exists(table_name=table_name)

    def test_create_table_empty_name(self, storage, sample_schema):
        """Test that empty table name raises error."""
        with pytest.raises(StorageValidationError, match="Table name cannot be empty"):
            storage.create_table(table_name="", schema=sample_schema)

    def test_create_table_idempotent(self, storage, sample_schema):
        """Test that creating table multiple times is safe."""
        table_name = "test_table"
        storage.create_table(table_name=table_name, schema=sample_schema)
        storage.create_table(table_name=table_name, schema=sample_schema)
        assert storage.table_exists(table_name=table_name)


class TestDuckDBTableStorageUpsertData:
    """Test insert and update operations."""

    def test_upsert_data_insert(self, storage, sample_schema, sample_table):
        """Test inserting new data."""
        table_name = "test_table"
        storage.create_table(table_name=table_name, schema=sample_schema)
        storage.upsert_data(table_name=table_name, data=sample_table)

        result = storage.read_data(table_name=table_name)
        assert result.num_rows == 3

    def test_upsert_data_update(self, storage, sample_schema):
        """Test updating existing data."""
        table_name = "test_table"
        storage.create_table(table_name=table_name, schema=sample_schema)

        initial_data = pa.table(
            {
                "id": ["doc1"],
                "name": ["Original Name"],
                "content": ["Original Content"],
                "size": [100],
                "pages_processed": [1],
            }
        )
        storage.upsert_data(table_name=table_name, data=initial_data)

        updated_data = pa.table(
            {
                "id": ["doc1"],
                "name": ["Updated Name"],
                "content": ["Updated Content"],
                "size": [200],
                "pages_processed": [2],
            }
        )
        storage.upsert_data(table_name=table_name, data=updated_data)

        result = storage.read_data(table_name=table_name)
        assert result.num_rows == 1
        assert result["name"][0].as_py() == "Updated Name"
        assert result["size"][0].as_py() == 200

    def test_upsert_data_missing_id_column(self, storage, sample_schema):
        """Test that upsert fails without id column."""
        table_name = "test_table"
        storage.create_table(table_name=table_name, schema=sample_schema)

        bad_data = pa.table({"name": ["Document 1"], "content": ["Content 1"]})

        with pytest.raises(StorageException, match="must contain an 'id' column"):
            storage.upsert_data(table_name=table_name, data=bad_data)

    def test_upsert_data_nonexistent_table(self, storage, sample_table):
        """Test that upsert fails for nonexistent table."""
        with pytest.raises(StorageException, match="does not exist"):
            storage.upsert_data(table_name="nonexistent_table", data=sample_table)


class TestDuckDBTableStorageReadData:
    """Test data reading with pagination."""

    def test_read_data_all(self, storage, sample_schema, sample_table):
        """Test reading all data."""
        table_name = "test_table"
        storage.create_table(table_name=table_name, schema=sample_schema)
        storage.upsert_data(table_name=table_name, data=sample_table)

        result = storage.read_data(table_name=table_name)

        assert result.num_rows == 3
        assert result.num_columns == 5

    def test_read_data_with_limit(self, storage, sample_schema, sample_table):
        """Test reading data with limit."""
        table_name = "test_table"
        storage.create_table(table_name=table_name, schema=sample_schema)
        storage.upsert_data(table_name=table_name, data=sample_table)

        result = storage.read_data(table_name=table_name, limit=2)

        assert result.num_rows == 2

    def test_read_data_with_offset(self, storage, sample_schema, sample_table):
        """Test reading data with offset."""
        table_name = "test_table"
        storage.create_table(table_name=table_name, schema=sample_schema)
        storage.upsert_data(table_name=table_name, data=sample_table)

        result = storage.read_data(table_name=table_name, offset=1)

        assert result.num_rows == 2

    def test_read_data_pagination(self, storage, sample_schema, sample_table):
        """Test reading data with limit and offset."""
        table_name = "test_table"
        storage.create_table(table_name=table_name, schema=sample_schema)
        storage.upsert_data(table_name=table_name, data=sample_table)

        result = storage.read_data(table_name=table_name, limit=1, offset=1)

        assert result.num_rows == 1
        assert result["id"][0].as_py() == "doc2"

    def test_read_data_nonexistent_table(self, storage):
        """Test that reading from nonexistent table raises error."""
        with pytest.raises(StorageException, match="does not exist"):
            storage.read_data(table_name="nonexistent_table")


class TestDuckDBTableStorageDeleteTable:
    """Test table deletion."""

    def test_delete_table(self, storage, sample_schema):
        """Test deleting a table."""
        table_name = "test_table"
        storage.create_table(table_name=table_name, schema=sample_schema)
        assert storage.table_exists(table_name=table_name)

        storage.delete_table(table_name=table_name)
        assert not storage.table_exists(table_name=table_name)

    def test_delete_nonexistent_table(self, storage):
        """Test deleting a nonexistent table."""
        # Should not raise error
        storage.delete_table(table_name="nonexistent_table")


class TestDuckDBTableStorageTableExists:
    """Test table existence checking."""

    def test_table_exists_true(self, storage, sample_schema):
        """Test checking if table exists."""
        table_name = "test_table"
        storage.create_table(table_name=table_name, schema=sample_schema)

        assert storage.table_exists(table_name=table_name) is True

    def test_table_exists_false(self, storage):
        """Test checking if nonexistent table exists."""
        assert storage.table_exists(table_name="nonexistent_table") is False


class TestDuckDBTableStorageGetRowCount:
    """Test row counting."""

    def test_get_row_count(self, storage, sample_schema, sample_table):
        """Test getting row count."""
        table_name = "test_table"
        storage.create_table(table_name=table_name, schema=sample_schema)
        storage.upsert_data(table_name=table_name, data=sample_table)

        count = storage.get_row_count(table_name=table_name)
        assert count == 3

    def test_get_row_count_empty_table(self, storage, sample_schema):
        """Test getting row count for empty table."""
        table_name = "test_table"
        storage.create_table(table_name=table_name, schema=sample_schema)

        count = storage.get_row_count(table_name=table_name)
        assert count == 0

    def test_get_row_count_nonexistent_table(self, storage):
        """Test that getting row count for nonexistent table raises error."""
        with pytest.raises(StorageException, match="does not exist"):
            storage.get_row_count(table_name="nonexistent_table")


class TestDuckDBTableStorageExecuteQuery:
    """Test SQL query execution."""

    def test_execute_query_select(self, storage, sample_schema, sample_table):
        """Test executing SELECT query."""
        table_name = "test_table"
        storage.create_table(table_name=table_name, schema=sample_schema)
        storage.upsert_data(table_name=table_name, data=sample_table)

        result = storage.execute_query(query=f"SELECT * FROM {table_name} WHERE size > 150")

        assert result.num_rows == 2

    def test_execute_query_with_parameters(self, storage, sample_schema, sample_table):
        """Test executing query with parameters."""
        table_name = "test_table"
        storage.create_table(table_name=table_name, schema=sample_schema)
        storage.upsert_data(table_name=table_name, data=sample_table)

        result = storage.execute_query(query=f"SELECT * FROM {table_name} WHERE id = ?", params=["doc2"])

        assert result.num_rows == 1
        assert result["id"][0].as_py() == "doc2"


class TestDuckDBTableStorageSchemaEvolution:
    """Test adding new columns (schema evolution)."""

    def test_schema_evolution_add_column(self, storage, sample_schema):
        """Test adding new columns to existing table."""
        table_name = "test_table"
        storage.create_table(table_name=table_name, schema=sample_schema)

        initial_data = pa.table(
            {
                "id": ["doc1"],
                "name": ["Document 1"],
                "content": ["Content 1"],
                "size": [100],
                "pages_processed": [1],
            }
        )
        storage.upsert_data(table_name=table_name, data=initial_data)

        new_data = pa.table(
            {
                "id": ["doc2"],
                "name": ["Document 2"],
                "content": ["Content 2"],
                "size": [200],
                "pages_processed": [2],
                "new_column": ["New Value"],
            }
        )
        storage.upsert_data(table_name=table_name, data=new_data)

        result = storage.read_data(table_name=table_name)
        assert result.num_rows == 2
        assert "new_column" in result.schema.names


class TestDuckDBTableStorageSingleton:
    """Test singleton pattern."""

    def test_same_path_returns_same_instance(self, tmp_path):
        """Test that same database path returns the same instance."""
        db_path = str(tmp_path / "test.db")

        storage1 = DuckDBTableStorage(database_path=db_path)
        storage2 = DuckDBTableStorage(database_path=db_path)

        assert storage1 is storage2

    def test_different_paths_return_different_instances(self, tmp_path):
        """Test that different database paths return different instances."""
        path1 = str(tmp_path / "db1.duckdb")
        path2 = str(tmp_path / "db2.duckdb")

        storage1 = DuckDBTableStorage(database_path=path1)
        storage2 = DuckDBTableStorage(database_path=path2)

        assert storage1 is not storage2

    def test_memory_database_singleton(self):
        """Test that :memory: database uses singleton pattern."""
        storage1 = DuckDBTableStorage(database_path=":memory:")
        storage2 = DuckDBTableStorage(database_path=":memory:")

        assert storage1 is storage2


class TestDuckDBTableStorageFactory:
    """Test factory integration."""

    def test_factory_create_table_storage(self, tmp_path):
        """Test creating DuckDBTableStorage through factory."""
        storage = StorageFactory.create_table_storage(storage_type="duckdb", database_path=str(tmp_path / "test.db"))

        assert isinstance(storage, DuckDBTableStorage)

        # Test it works
        schema = pa.schema([("id", pa.string()), ("value", pa.int64())])
        storage.create_table(table_name="test", schema=schema)
        assert storage.table_exists(table_name="test")

    def test_factory_singleton_consistency(self, tmp_path):
        """Test that factory and direct creation return same instance."""
        db_path = str(tmp_path / "test.db")

        storage1 = StorageFactory.create_table_storage(storage_type="duckdb", database_path=db_path)
        storage2 = DuckDBTableStorage(database_path=db_path)

        assert storage1 is storage2


class TestDuckDBTableStorageInMemory:
    """Test in-memory database operations."""

    def test_in_memory_database(self):
        """Test using in-memory database."""
        storage = DuckDBTableStorage(database_path=":memory:")

        schema = pa.schema([("id", pa.string()), ("value", pa.string())])
        storage.create_table(table_name="test_table", schema=schema)

        data = pa.table({"id": ["1"], "value": ["test"]})
        storage.upsert_data(table_name="test_table", data=data)

        result = storage.read_data(table_name="test_table")
        assert result.num_rows == 1


class TestDuckDBTableStorageValidation:
    """Test input validation."""

    def test_invalid_table_name_sql_injection(self, storage, sample_schema):
        """Test that SQL injection attempts in table name are rejected."""
        with pytest.raises(StorageValidationError, match="Invalid table name"):
            storage.create_table(table_name="test; DROP TABLE users;", schema=sample_schema)

    def test_invalid_table_name_empty(self, storage, sample_schema):
        """Test that empty table name is rejected."""
        with pytest.raises(StorageValidationError, match="Table name cannot be empty"):
            storage.create_table(table_name="", schema=sample_schema)


class TestDuckDBTableStorageErrorHandling:
    """Test error handling branches in table storage operations."""

    def test_create_table_with_invalid_column_name_raises(self, tmp_path):
        """Test that schema with invalid column name raises StorageValidationError."""
        storage = DuckDBTableStorage(database_path=str(tmp_path / "err.db"))
        # Create schema with invalid column name directly via _validate_column_name
        with pytest.raises(StorageValidationError, match="Invalid column name"):
            storage._validate_column_name(column_name="col-bad!")

    def test_upsert_missing_id_column_raises_storage_validation_error(self, storage, sample_schema):
        """Test upsert with missing id column raises StorageValidationError."""
        table_name = "test_table"
        storage.create_table(table_name=table_name, schema=sample_schema)
        bad_data = pa.table({"name": ["Doc"], "content": ["Content"]})
        with pytest.raises(StorageValidationError, match="must contain an 'id' column"):
            storage.upsert_data(table_name=table_name, data=bad_data)

    def test_delete_table_invalid_name_raises(self, storage):
        """Test deleting table with invalid name raises StorageValidationError."""
        with pytest.raises(StorageValidationError, match="Invalid table name"):
            storage.delete_table(table_name="bad-name!")

    def test_read_data_invalid_name_raises(self, storage):
        """Test reading table with invalid name raises StorageValidationError."""
        with pytest.raises(StorageValidationError, match="Invalid table name"):
            storage.read_data(table_name="bad-name!")

    def test_get_row_count_invalid_name_raises(self, storage):
        """Test getting row count with invalid name raises StorageValidationError."""
        with pytest.raises(StorageValidationError, match="Invalid table name"):
            storage.get_row_count(table_name="bad-name!")


class TestDuckDBTableStorageGetTableSchema:
    """Test getting table schema."""

    def test_get_table_schema(self, storage, sample_schema):
        """Test getting schema of existing table."""
        table_name = "test_table"
        storage.create_table(table_name=table_name, schema=sample_schema)
        schema = storage.get_table_schema(table_name=table_name)
        assert "id" in schema.names
        assert "name" in schema.names

    def test_get_table_schema_nonexistent_raises(self, storage):
        """Test getting schema of nonexistent table raises error."""
        from docpipe.storage.exceptions import StorageException

        with pytest.raises(StorageException, match="does not exist"):
            storage.get_table_schema(table_name="nonexistent_table")


class TestDuckDBTableStorageTypeConversion:
    """Test PyArrow to DuckDB type conversion."""

    def test_various_pyarrow_types(self, tmp_path):
        """Test that various PyArrow types convert correctly and can be used in tables."""
        storage = DuckDBTableStorage(database_path=str(tmp_path / "types.db"))

        schema = pa.schema(
            [
                ("id", pa.string()),
                ("int8_col", pa.int8()),
                ("int16_col", pa.int16()),
                ("float32_col", pa.float32()),
                ("float64_col", pa.float64()),
                ("bool_col", pa.bool_()),
                ("binary_col", pa.binary()),
                ("timestamp_col", pa.timestamp("ms")),
                ("list_col", pa.list_(pa.string())),
            ]
        )
        storage.create_table(table_name="types_table", schema=schema)
        assert storage.table_exists(table_name="types_table")

    def test_unknown_type_defaults_to_varchar(self, tmp_path):
        """Test that unknown PyArrow types default to VARCHAR."""
        storage = DuckDBTableStorage(database_path=str(tmp_path / "unknown.db"))
        # decimal type is not directly mapped — should default to VARCHAR
        duckdb_type = storage._pyarrow_to_duckdb_type(pa_type=pa.decimal128(10, 2))
        assert duckdb_type == "VARCHAR"

    def test_large_binary_type(self, tmp_path):
        """Test that large binary type converts correctly."""
        storage = DuckDBTableStorage(database_path=str(tmp_path / "binary.db"))
        duckdb_type = storage._pyarrow_to_duckdb_type(pa_type=pa.large_binary())
        assert duckdb_type == "BLOB"

    def test_large_string_type(self, tmp_path):
        """Test that large string type converts to VARCHAR."""
        storage = DuckDBTableStorage(database_path=str(tmp_path / "lstring.db"))
        duckdb_type = storage._pyarrow_to_duckdb_type(pa_type=pa.large_utf8())
        assert duckdb_type == "VARCHAR"

    def test_struct_type(self, tmp_path):
        """Test that struct type converts to JSON."""
        storage = DuckDBTableStorage(database_path=str(tmp_path / "struct.db"))
        duckdb_type = storage._pyarrow_to_duckdb_type(pa_type=pa.struct([pa.field("x", pa.int32())]))
        assert duckdb_type == "JSON"

    def test_map_type(self, tmp_path):
        """Test that map type converts to JSON."""
        storage = DuckDBTableStorage(database_path=str(tmp_path / "maptype.db"))
        duckdb_type = storage._pyarrow_to_duckdb_type(pa_type=pa.map_(pa.string(), pa.int32()))
        assert duckdb_type == "JSON"

    def test_large_list_type(self, tmp_path):
        """Test that large list type converts to JSON."""
        storage = DuckDBTableStorage(database_path=str(tmp_path / "llist.db"))
        duckdb_type = storage._pyarrow_to_duckdb_type(pa_type=pa.large_list(pa.string()))
        assert duckdb_type == "JSON"

    def test_date_type(self, tmp_path):
        """Test that date type converts to DATE."""
        storage = DuckDBTableStorage(database_path=str(tmp_path / "date.db"))
        duckdb_type = storage._pyarrow_to_duckdb_type(pa_type=pa.date32())
        assert duckdb_type == "DATE"

    def test_time_type(self, tmp_path):
        """Test that time type converts to TIME."""
        storage = DuckDBTableStorage(database_path=str(tmp_path / "time.db"))
        duckdb_type = storage._pyarrow_to_duckdb_type(pa_type=pa.time32("s"))
        assert duckdb_type == "TIME"


class TestDuckDBTableStorageValidateColumnName:
    """Test column name validation."""

    def test_invalid_column_name_empty_raises(self, storage, sample_schema):
        """Test that empty column name raises StorageValidationError."""
        from docpipe.storage.exceptions import StorageValidationError

        with pytest.raises(StorageValidationError, match="Column name cannot be empty"):
            storage._validate_column_name(column_name="")

    def test_invalid_column_name_sql_chars_raises(self, storage):
        """Test that SQL chars in column name raise StorageValidationError."""
        from docpipe.storage.exceptions import StorageValidationError

        with pytest.raises(StorageValidationError, match="Invalid column name"):
            storage._validate_column_name(column_name="col; DROP TABLE t;")


class TestDuckDBTableStorageDirectoryValidation:
    """Test directory validation logic."""

    def test_validate_database_path_nonexistent_directory(self, tmp_path):
        """Test validate_database_path logs warning for nonexistent directory."""
        # A path inside a nonexistent subdir
        fake_path = str(tmp_path / "nonexistent_dir" / "test.db")
        # Should not raise, just log
        DuckDBTableStorage.validate_database_path(db_path=fake_path)
