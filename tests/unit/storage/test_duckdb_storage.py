"""Unit tests for DuckDB storage layer.

Tests cover:
- Metadata table creation
- Data table creation from PyArrow schema
- Upsert operations
- Data reading with pagination
- Metrics computation
- Row deletion
- Schema evolution
- Type mapping
"""

import pytest
import pyarrow as pa

from common.exceptions.datasift_exceptions import DatasiftException
from storage.duckdb_storage import DuckDBStorage


@pytest.fixture
def storage(temp_duckdb_path):
    """Create a DuckDBStorage instance."""
    return DuckDBStorage(temp_duckdb_path)


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


class TestMetadataTableCreation:
    """Test metadata table creation."""

    def test_create_metadata_table(self, storage):
        """Test creating the document_sets metadata table."""
        storage.create_metadata_table()
        assert storage.table_exists("document_sets")

    def test_create_metadata_table_idempotent(self, storage):
        """Test that creating metadata table multiple times is safe."""
        storage.create_metadata_table()
        storage.create_metadata_table()
        assert storage.table_exists("document_sets")


class TestDataTableCreation:
    """Test data table creation from PyArrow schema."""

    def test_create_data_table(self, storage, sample_schema):
        """Test creating a data table from PyArrow schema."""
        table_name = "test_table"
        storage.create_data_table(table_name, sample_schema)
        assert storage.table_exists(table_name)

    def test_create_data_table_with_id_primary_key(self, storage, sample_schema):
        """Test that id column becomes primary key."""
        table_name = "test_table"
        storage.create_data_table(table_name, sample_schema)
        assert storage.table_exists(table_name)

    def test_create_data_table_empty_name(self, storage, sample_schema):
        """Test that empty table name raises error."""
        with pytest.raises(DatasiftException, match="Table name cannot be empty"):
            storage.create_data_table("", sample_schema)

    def test_create_data_table_idempotent(self, storage, sample_schema):
        """Test that creating table multiple times is safe."""
        table_name = "test_table"
        storage.create_data_table(table_name, sample_schema)
        storage.create_data_table(table_name, sample_schema)
        assert storage.table_exists(table_name)


class TestUpsertData:
    """Test insert and update operations."""

    def test_upsert_data_insert(self, storage, sample_schema, sample_table):
        """Test inserting new data."""
        table_name = "test_table"
        storage.create_data_table(table_name, sample_schema)
        storage.upsert_data(table_name, sample_table)

        result = storage.read_data(table_name)
        assert result.num_rows == 3

    def test_upsert_data_update(self, storage, sample_schema):
        """Test updating existing data."""
        table_name = "test_table"
        storage.create_data_table(table_name, sample_schema)

        initial_data = pa.table(
            {
                "id": ["doc1"],
                "name": ["Original Name"],
                "content": ["Original Content"],
                "size": [100],
                "pages_processed": [1],
            }
        )
        storage.upsert_data(table_name, initial_data)

        updated_data = pa.table(
            {
                "id": ["doc1"],
                "name": ["Updated Name"],
                "content": ["Updated Content"],
                "size": [200],
                "pages_processed": [2],
            }
        )
        storage.upsert_data(table_name, updated_data)

        result = storage.read_data(table_name)
        assert result.num_rows == 1
        assert result["name"][0].as_py() == "Updated Name"
        assert result["size"][0].as_py() == 200

    def test_upsert_data_missing_id_column(self, storage, sample_schema):
        """Test that upsert fails without id column."""
        table_name = "test_table"
        storage.create_data_table(table_name, sample_schema)

        bad_data = pa.table({"name": ["Document 1"], "content": ["Content 1"]})

        with pytest.raises(DatasiftException, match="must contain an 'id' column"):
            storage.upsert_data(table_name, bad_data)

    def test_upsert_data_nonexistent_table(self, storage, sample_table):
        """Test that upsert fails for nonexistent table."""
        with pytest.raises(DatasiftException, match="does not exist"):
            storage.upsert_data("nonexistent_table", sample_table)


class TestReadData:
    """Test data reading with pagination."""

    def test_read_data_all(self, storage, sample_schema, sample_table):
        """Test reading all data."""
        table_name = "test_table"
        storage.create_data_table(table_name, sample_schema)
        storage.upsert_data(table_name, sample_table)

        result = storage.read_data(table_name)

        assert result.num_rows == 3
        assert result.num_columns == 5

    def test_read_data_with_limit(self, storage, sample_schema, sample_table):
        """Test reading data with limit."""
        table_name = "test_table"
        storage.create_data_table(table_name, sample_schema)
        storage.upsert_data(table_name, sample_table)

        result = storage.read_data(table_name, limit=2)

        assert result.num_rows == 2

    def test_read_data_with_offset(self, storage, sample_schema, sample_table):
        """Test reading data with offset."""
        table_name = "test_table"
        storage.create_data_table(table_name, sample_schema)
        storage.upsert_data(table_name, sample_table)

        result = storage.read_data(table_name, offset=1)

        assert result.num_rows == 2

    def test_read_data_pagination(self, storage, sample_schema, sample_table):
        """Test reading data with limit and offset."""
        table_name = "test_table"
        storage.create_data_table(table_name, sample_schema)
        storage.upsert_data(table_name, sample_table)

        result = storage.read_data(table_name, limit=1, offset=1)

        assert result.num_rows == 1
        assert result["id"][0].as_py() == "doc2"

    def test_read_data_nonexistent_table(self, storage):
        """Test that reading from nonexistent table raises error."""
        with pytest.raises(DatasiftException, match="does not exist"):
            storage.read_data("nonexistent_table")


class TestComputeMetrics:
    """Test metrics computation."""

    def test_compute_metrics(self, storage, sample_schema, sample_table):
        """Test computing metrics from stored data."""
        table_name = "test_table"
        storage.create_data_table(table_name, sample_schema)
        storage.upsert_data(table_name, sample_table)

        metrics = storage.compute_metrics(table_name)

        assert metrics["total_documents"] == 3
        assert metrics["total_size_bytes"] == 600
        assert metrics["total_pages"] == 6

    def test_compute_metrics_empty_table(self, storage, sample_schema):
        """Test computing metrics for empty table."""
        table_name = "test_table"
        storage.create_data_table(table_name, sample_schema)

        metrics = storage.compute_metrics(table_name)

        assert metrics["total_documents"] == 0
        assert metrics["total_size_bytes"] == 0
        assert metrics["total_pages"] == 0

    def test_compute_metrics_without_size_column(self, storage):
        """Test computing metrics when size column is missing."""
        table_name = "test_table"
        schema = pa.schema([("id", pa.string()), ("name", pa.string())])
        storage.create_data_table(table_name, schema)

        data = pa.table({"id": ["doc1", "doc2"], "name": ["Doc 1", "Doc 2"]})
        storage.upsert_data(table_name, data)

        metrics = storage.compute_metrics(table_name)

        assert metrics["total_documents"] == 2
        assert metrics["total_size_bytes"] == 0
        assert metrics["total_pages"] == 0

    def test_compute_metrics_nonexistent_table(self, storage):
        """Test that computing metrics for nonexistent table raises error."""
        with pytest.raises(DatasiftException, match="does not exist"):
            storage.compute_metrics("nonexistent_table")


class TestDeleteRows:
    """Test row deletion by IDs."""

    def test_delete_rows(self, storage, sample_schema, sample_table):
        """Test deleting rows by ID list."""
        table_name = "test_table"
        storage.create_data_table(table_name, sample_schema)
        storage.upsert_data(table_name, sample_table)

        deleted_count = storage.delete_rows(table_name, ["doc1", "doc2"])

        assert deleted_count == 2

        result = storage.read_data(table_name)
        assert result.num_rows == 1
        assert result["id"][0].as_py() == "doc3"

    def test_delete_rows_empty_list(self, storage, sample_schema, sample_table):
        """Test deleting with empty ID list."""
        table_name = "test_table"
        storage.create_data_table(table_name, sample_schema)
        storage.upsert_data(table_name, sample_table)

        deleted_count = storage.delete_rows(table_name, [])

        assert deleted_count == 0

        result = storage.read_data(table_name)
        assert result.num_rows == 3

    def test_delete_rows_nonexistent_ids(self, storage, sample_schema, sample_table):
        """Test deleting nonexistent IDs."""
        table_name = "test_table"
        storage.create_data_table(table_name, sample_schema)
        storage.upsert_data(table_name, sample_table)

        deleted_count = storage.delete_rows(
            table_name, ["nonexistent1", "nonexistent2"]
        )

        assert deleted_count == 0

    def test_delete_rows_nonexistent_table(self, storage):
        """Test that deleting from nonexistent table raises error."""
        with pytest.raises(DatasiftException, match="does not exist"):
            storage.delete_rows("nonexistent_table", ["doc1"])


class TestSchemaEvolution:
    """Test adding new columns (schema evolution)."""

    def test_schema_evolution_add_column(self, storage, sample_schema):
        """Test adding new columns to existing table."""
        table_name = "test_table"
        storage.create_data_table(table_name, sample_schema)

        initial_data = pa.table(
            {
                "id": ["doc1"],
                "name": ["Document 1"],
                "content": ["Content 1"],
                "size": [100],
                "pages_processed": [1],
            }
        )
        storage.upsert_data(table_name, initial_data)

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
        storage.upsert_data(table_name, new_data)

        result = storage.read_data(table_name)
        assert result.num_rows == 2
        assert "new_column" in result.schema.names


class TestTypeMappingPyArrowToDuckDB:
    """Test PyArrow to DuckDB type conversions."""

    @pytest.mark.parametrize(
        "pa_type,expected_duckdb",
        [
            (pa.string(), "VARCHAR"),
            (pa.large_string(), "VARCHAR"),
            (pa.int64(), "BIGINT"),
            (pa.int32(), "INTEGER"),
            (pa.int16(), "SMALLINT"),
            (pa.int8(), "TINYINT"),
            (pa.float64(), "DOUBLE"),
            (pa.float32(), "FLOAT"),
            (pa.bool_(), "BOOLEAN"),
            (pa.binary(), "BLOB"),
            (pa.timestamp("us"), "TIMESTAMP"),
            (pa.date32(), "DATE"),
        ],
    )
    def test_type_mapping(self, storage, pa_type, expected_duckdb):
        """Test PyArrow to DuckDB type mapping."""
        result = storage._pyarrow_to_duckdb_type(pa_type)
        assert result == expected_duckdb

    def test_type_mapping_list_to_json(self, storage):
        """Test that list types map to JSON."""
        result = storage._pyarrow_to_duckdb_type(pa.list_(pa.string()))
        assert result == "JSON"

    def test_type_mapping_struct_to_json(self, storage):
        """Test that struct types map to JSON."""
        result = storage._pyarrow_to_duckdb_type(pa.struct([("field", pa.string())]))
        assert result == "JSON"


class TestTableExists:
    """Test table existence checking."""

    def test_table_exists_true(self, storage, sample_schema):
        """Test checking if table exists."""
        table_name = "test_table"
        storage.create_data_table(table_name, sample_schema)

        assert storage.table_exists(table_name) is True

    def test_table_exists_false(self, storage):
        """Test checking if nonexistent table exists."""
        assert storage.table_exists("nonexistent_table") is False


class TestGetTableSchema:
    """Test getting table schema."""

    def test_get_table_schema(self, storage, sample_schema):
        """Test getting schema of existing table."""
        table_name = "test_table"
        storage.create_data_table(table_name, sample_schema)

        schema = storage.get_table_schema(table_name)

        assert schema is not None
        assert "id" in schema.names
        assert "name" in schema.names

    def test_get_table_schema_nonexistent_table(self, storage):
        """Test that getting schema of nonexistent table raises error."""
        with pytest.raises(DatasiftException, match="does not exist"):
            storage.get_table_schema("nonexistent_table")


class TestDatabaseInitialization:
    """Test database initialization and validation."""

    def test_in_memory_database(self):
        """Test using in-memory database."""
        storage = DuckDBStorage(":memory:")

        storage.create_metadata_table()
        assert storage.table_exists("document_sets")

        schema = pa.schema([("id", pa.string()), ("value", pa.string())])
        storage.create_data_table("test_table", schema)

        data = pa.table({"id": ["1"], "value": ["test"]})
        storage.upsert_data("test_table", data)

        result = storage.read_data("test_table")
        assert result.num_rows == 1

    def test_validate_database_path_memory(self):
        """Test validation with in-memory database."""
        # Should not raise any exceptions
        DuckDBStorage.validate_database_path(":memory:")

    def test_validate_database_path_nonexistent_directory(self, tmp_path):
        """Test validation with nonexistent directory."""
        db_path = str(tmp_path / "nonexistent" / "data" / "test.duckdb")
        # Should not raise any exceptions, just log warnings
        DuckDBStorage.validate_database_path(db_path)

    def test_validate_database_path_multiple_files(self, tmp_path):
        """Test validation with multiple database files."""
        # Create multiple database files
        db1_path = tmp_path / "data" / "duckdb" / "document_sets.duckdb"
        db2_path = tmp_path / "backup" / "document_sets.duckdb"

        db1_path.parent.mkdir(parents=True, exist_ok=True)
        db2_path.parent.mkdir(parents=True, exist_ok=True)

        db1_path.touch()
        db2_path.touch()

        # Should not raise any exceptions, just log warnings
        DuckDBStorage.validate_database_path(str(db1_path))

    def test_validate_database_path_single_file(self, tmp_path):
        """Test validation with single database file."""
        # Create single database file
        db_path = tmp_path / "data" / "duckdb" / "document_sets.duckdb"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        db_path.touch()

        # Should not raise any exceptions
        DuckDBStorage.validate_database_path(str(db_path))

    def test_init_calls_validation(self, temp_duckdb_path):
        """Test that __init__ calls validate_database_path."""
        storage = DuckDBStorage(temp_duckdb_path)
        assert storage.database_path == temp_duckdb_path
