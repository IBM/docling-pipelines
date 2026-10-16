"""Tests for PostgreSQLTableStorage."""

from unittest.mock import MagicMock

import pyarrow as pa
import pytest

from docpipe.storage.exceptions import StorageConnectionError, StorageValidationError
from docpipe.storage.factory import StorageFactory
from docpipe.storage.postgres.postgresql_table_storage import PostgreSQLTableStorage


@pytest.fixture
def storage(monkeypatch):
    """Create a PostgreSQLTableStorage instance without a live database."""
    monkeypatch.setattr(
        "docpipe.storage.postgres.postgresql_table_storage.get_postgres_connection_string",
        lambda **kwargs: "postgresql+psycopg2://user:password@localhost:5432/docpipe",  # pragma: allowlist secret
    )

    engine = MagicMock()

    monkeypatch.setattr(
        "docpipe.storage.postgres.postgresql_table_storage.create_postgres_engine",
        lambda **kwargs: engine,
    )

    connection = engine.begin.return_value.__enter__.return_value
    existing_columns_result = MagicMock()
    existing_columns_result.mappings.return_value.all.return_value = [
        {"column_name": "id"},
        {"column_name": "name"},
        {"column_name": "amount"},
        {"column_name": "description"},
        {"column_name": "quantity"},
        {"column_name": "details"},
    ]
    connection.execute.return_value = existing_columns_result

    return PostgreSQLTableStorage(
        config={
            "host": "localhost",
            "port": 5432,
            "database": "docpipe",
            "user": "docpipe_user",
            "password": "password",  # pragma: allowlist secret
        }
    )


class TestPostgreSQLTableStorageValidation:
    """Test identifier and type validation."""

    def test_empty_table_name(self, storage):
        with pytest.raises(StorageValidationError, match="table name cannot be empty"):
            storage.create_table(
                table_name="",
                schema=pa.schema([("id", pa.string())]),
            )

    def test_invalid_table_name(self, storage):
        with pytest.raises(StorageValidationError, match="Invalid table name"):
            storage.create_table(
                table_name="invalid-table",
                schema=pa.schema([("id", pa.string())]),
            )

    def test_invalid_column_name(self, storage):
        with pytest.raises(StorageValidationError, match="Invalid column name"):
            storage.create_table(
                table_name="test_table",
                schema=pa.schema([("invalid-column", pa.string())]),
            )

    def test_missing_connection_string(self, monkeypatch):
        monkeypatch.setattr(
            "docpipe.storage.postgres.postgresql_table_storage.get_postgres_connection_string",
            lambda **kwargs: None,
        )

        with pytest.raises(StorageConnectionError, match="PostgreSQL connection is not configured"):
            PostgreSQLTableStorage()

    def test_engine_creation_failure(self, monkeypatch):
        monkeypatch.setattr(
            "docpipe.storage.postgres.postgresql_table_storage.get_postgres_connection_string",
            lambda **kwargs: "postgresql+psycopg2://test@localhost:5432/docpipe",
        )

        def raise_connection_error(**kwargs):
            raise RuntimeError("connection failed")

        monkeypatch.setattr(
            "docpipe.storage.postgres.postgresql_table_storage.create_postgres_engine",
            raise_connection_error,
        )

        with pytest.raises(
            StorageConnectionError,
            match="Failed to initialize PostgreSQL storage: connection failed",
        ):
            PostgreSQLTableStorage()

    @pytest.mark.parametrize(
        ("pa_type", "expected"),
        [
            (pa.string(), "TEXT"),
            (pa.int64(), "BIGINT"),
            (pa.int32(), "INTEGER"),
            (pa.int16(), "SMALLINT"),
            (pa.int8(), "SMALLINT"),
            (pa.float64(), "DOUBLE PRECISION"),
            (pa.float32(), "REAL"),
            (pa.bool_(), "BOOLEAN"),
            (pa.binary(), "BYTEA"),
            (pa.timestamp("us"), "TIMESTAMP"),
            (pa.date32(), "DATE"),
            (pa.time64("us"), "TIME"),
            (pa.list_(pa.string()), "JSONB"),
            (pa.struct([("name", pa.string())]), "JSONB"),
        ],
    )
    def test_pyarrow_to_postgres_type(self, storage, pa_type, expected):
        assert storage._pyarrow_to_postgres_type(pa_type=pa_type) == expected


class TestPostgreSQLTableStorageFactory:
    """Test storage factory integration."""

    def test_postgres_is_supported(self):
        assert "postgres" in StorageFactory.SUPPORTED_TABLE_TYPES

    def test_factory_creates_postgres_storage(self, monkeypatch):
        monkeypatch.setattr(
            "docpipe.storage.postgres.postgresql_table_storage.get_postgres_connection_string",
            lambda **kwargs: "postgresql+psycopg2://test@localhost:5432/docpipe",
        )

        engine = MagicMock()

        monkeypatch.setattr(
            "docpipe.storage.postgres.postgresql_table_storage.create_postgres_engine",
            lambda **kwargs: engine,
        )

        storage = StorageFactory.create_table_storage(
            storage_type="postgres",
            config={
                "host": "localhost",
                "port": 5432,
                "database": "docpipe",
                "user": "docpipe_user",
                "password": "password",  # pragma: allowlist secret
            },
        )

        assert isinstance(storage, PostgreSQLTableStorage)
        assert storage.engine is engine


class TestPostgreSQLTableStorageOperations:
    """Test PostgreSQL SQL operations without a live database."""

    def test_create_table_executes_create_statement(self, storage):
        connection = storage.engine.begin.return_value.__enter__.return_value

        schema = pa.schema(
            [
                ("id", pa.string()),
                ("name", pa.string()),
                ("amount", pa.float64()),
            ]
        )

        storage.create_table(table_name="invoice", schema=schema)

        connection.execute.assert_called_once()

        query = str(connection.execute.call_args.args[0])
        assert 'CREATE TABLE IF NOT EXISTS "invoice"' in query
        assert '"id" TEXT PRIMARY KEY' in query
        assert '"name" TEXT' in query
        assert '"amount" DOUBLE PRECISION' in query

    def test_upsert_data_executes_rows(self, storage, monkeypatch):
        monkeypatch.setattr(
            storage,
            "table_exists",
            lambda table_name: True,
        )

        connection = storage.engine.begin.return_value.__enter__.return_value

        table = pa.table(
            {
                "id": ["doc1", "doc2"],
                "name": ["Document 1", "Document 2"],
                "amount": [10.5, 20.5],
            }
        )

        storage.upsert_data(table_name="invoice", data=table)

        insert_calls = [call for call in connection.execute.call_args_list if "INSERT INTO" in str(call.args[0])]

        assert len(insert_calls) == 2

        first_call = insert_calls[0]
        query = str(first_call.args[0])
        params = first_call.args[1]

        assert 'INSERT INTO "invoice"' in query
        assert 'ON CONFLICT ("id") DO UPDATE SET' in query
        assert params == {
            "id": "doc1",
            "name": "Document 1",
            "amount": 10.5,
        }

    def test_upsert_adds_new_columns(self, storage, monkeypatch):
        monkeypatch.setattr(
            storage,
            "table_exists",
            lambda table_name: True,
        )

        connection = storage.engine.begin.return_value.__enter__.return_value

        existing_columns_result = MagicMock()
        existing_columns_result.mappings.return_value.all.return_value = [
            {"column_name": "id", "data_type": "text"},
            {"column_name": "invoice_id", "data_type": "text"},
        ]

        connection.execute.return_value = existing_columns_result

        table = pa.table(
            {
                "id": ["doc1"],
                "invoice_id": ["INV-001"],
                "invoice_date": ["2026-10-07"],
            }
        )

        storage.upsert_data(table_name="Invoice", data=table)

        queries = [str(call.args[0]) for call in connection.execute.call_args_list]

        alter_queries = [query for query in queries if "ALTER TABLE" in query]

        assert len(alter_queries) == 1
        assert 'ALTER TABLE "Invoice"' in alter_queries[0]
        assert 'ADD COLUMN "invoice_date" TEXT' in alter_queries[0]

    def test_upsert_empty_table_does_not_execute(self, storage, monkeypatch):
        monkeypatch.setattr(
            storage,
            "table_exists",
            lambda table_name: True,
        )

        connection = storage.engine.begin.return_value.__enter__.return_value

        empty_table = pa.table(
            {
                "id": pa.array([], type=pa.string()),
                "name": pa.array([], type=pa.string()),
            }
        )

        storage.upsert_data(table_name="invoice", data=empty_table)

        connection.execute.assert_not_called()


class TestPostgreSQLTableStorageJson:
    """Test storage of nested entity data."""

    def test_upsert_nested_values(self, storage, monkeypatch):
        monkeypatch.setattr(
            storage,
            "table_exists",
            lambda table_name: True,
        )

        connection = storage.engine.begin.return_value.__enter__.return_value

        table = pa.table(
            {
                "id": ["doc1:Invoice_line_items:0"],
                "description": ["Widget"],
                "quantity": [2],
                "details": [
                    {
                        "unit": "EA",
                        "tags": ["hardware", "sale"],
                    }
                ],
            }
        )

        storage.upsert_data(table_name="Invoice_line_items", data=table)

        insert_calls = [call for call in connection.execute.call_args_list if "INSERT INTO" in str(call.args[0])]

        assert len(insert_calls) == 1

        call = insert_calls[0]
        query = str(call.args[0])
        params = call.args[1]

        assert 'INSERT INTO "Invoice_line_items"' in query
        assert params["id"] == "doc1:Invoice_line_items:0"
        assert params["description"] == "Widget"
        assert params["quantity"] == 2
        assert params["details"] == {
            "unit": "EA",
            "tags": ["hardware", "sale"],
        }


class TestPostgreSQLTableStorageReadOperations:
    """Test PostgreSQL read and metadata operations."""

    def test_read_data_returns_arrow_table(self, storage):
        connection = storage.engine.connect.return_value.__enter__.return_value

        mappings = MagicMock()
        mappings.all.return_value = [
            {"id": "doc1", "name": "Document 1"},
            {"id": "doc2", "name": "Document 2"},
        ]

        result = MagicMock()
        result.mappings.return_value = mappings
        connection.execute.return_value = result

        table = storage.read_data(
            table_name="invoice",
            limit=10,
            offset=5,
        )

        assert table.to_pylist() == [
            {"id": "doc1", "name": "Document 1"},
            {"id": "doc2", "name": "Document 2"},
        ]

        assert connection.execute.call_count == 2

        query = str(connection.execute.call_args_list[1].args[0])
        assert 'SELECT * FROM "invoice"' in query
        assert "LIMIT :limit" in query
        assert "OFFSET :offset" in query

        params = connection.execute.call_args_list[1].args[1]
        assert params == {"limit": 10, "offset": 5}

    def test_delete_table(self, storage):
        connection = storage.engine.begin.return_value.__enter__.return_value

        storage.delete_table(table_name="invoice")

        query = str(connection.execute.call_args.args[0])
        assert 'DROP TABLE IF EXISTS "invoice"' in query

    def test_get_row_count(self, storage):
        connection = storage.engine.connect.return_value.__enter__.return_value

        result = MagicMock()
        result.scalar.return_value = 42
        connection.execute.return_value = result

        assert storage.get_row_count(table_name="invoice") == 42

        query = str(connection.execute.call_args.args[0])
        assert 'SELECT COUNT(*) FROM "invoice"' in query

    def test_table_exists(self, storage):
        connection = storage.engine.connect.return_value.__enter__.return_value

        result = MagicMock()
        result.scalar.return_value = True
        connection.execute.return_value = result

        assert storage.table_exists(table_name="invoice") is True

        query = str(connection.execute.call_args.args[0])
        assert "information_schema.tables" in query
        assert "table_name = :table_name" in query

        params = connection.execute.call_args.args[1]
        assert params == {"table_name": "invoice"}

    def test_execute_query(self, storage):
        connection = storage.engine.connect.return_value.__enter__.return_value

        mappings = MagicMock()
        mappings.all.return_value = [
            {"id": "doc1", "amount": 10.5},
        ]

        result = MagicMock()
        result.mappings.return_value = mappings
        connection.execute.return_value = result

        table = storage.execute_query(
            query='SELECT "id", "amount" FROM "invoice" WHERE "id" = :id',
            params={"id": "doc1"},
        )

        assert table.to_pylist() == [
            {"id": "doc1", "amount": 10.5},
        ]

        connection.execute.assert_called_once()
        params = connection.execute.call_args.args[1]
        assert params == {"id": "doc1"}
