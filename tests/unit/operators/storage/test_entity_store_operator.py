"""Unit tests for EntityStoreOperator."""

from unittest.mock import MagicMock, patch

import pyarrow as pa
import pytest

from docpipe.core.constants.constants import ExecutionStatus, Metrics
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.abstract_operator import OperatorCategory
from docpipe.core.operators.storage.entity_store_operator import EntityStoreOperator


@pytest.fixture
def basic_config():
    """Basic configuration for EntityStoreOperator."""
    return {
        "data_backend": "duckdb",
        "database_path": ":memory:",
    }


@pytest.fixture
def sample_table():
    """Create a sample curated-entities table."""
    return pa.table(
        {
            "id": ["doc1", "doc2"],
            "name": ["invoice1.pdf", "invoice2.pdf"],
            "transformed_entities": [
                '{"Invoice": {"invoice_id": "INV-001"}}',
                '{"Invoice": {"invoice_id": "INV-002"}}',
            ],
        }
    )


class TestOperatorMetadata:
    """Test operator metadata and configuration."""

    def test_operator_metadata(self, basic_config):
        """Test operator metadata structure."""
        operator = EntityStoreOperator(basic_config)
        metadata = operator.get_metadata()

        assert metadata["short_name"] == "entity_store"
        assert metadata["category"] == OperatorCategory.Storage.value
        assert metadata["owner"] == "docpipe"
        assert "description" in metadata
        assert "attributes" in metadata

    def test_operator_attributes(self, basic_config):
        """Test operator configuration attributes."""
        operator = EntityStoreOperator(basic_config)
        attributes = operator.get_metadata()["attributes"]

        assert attributes["data_backend"]["default"] == "duckdb"
        assert attributes["data_backend"]["valid_values"] == ["duckdb", "postgres"]
        assert attributes["database_path"]["default"] == ":memory:"

    def test_operator_category(self, basic_config):
        """Test operator category."""
        operator = EntityStoreOperator(basic_config)

        assert operator.category == OperatorCategory.Storage

    def test_operator_short_name(self, basic_config):
        """Test operator short name."""
        operator = EntityStoreOperator(basic_config)

        assert operator.short_name == "entity_store"


class TestOperatorConfiguration:
    """Test operator configuration."""

    def test_default_configuration(self):
        """Test default backend and entity column."""
        with patch(
            "docpipe.core.operators.storage.entity_store_operator.StorageFactory.create_table_storage"
        ) as mock_factory:
            mock_factory.return_value = MagicMock()

            operator = EntityStoreOperator({})

        assert operator.data_backend == "duckdb"
        assert operator.database_path == ":memory:"
        assert operator.entities_column == "transformed_entities"

        mock_factory.assert_called_once_with(
            storage_type="duckdb",
            database_path=":memory:",
        )

    def test_custom_entities_column(self):
        """Test custom entity column configuration."""
        config = {
            "entities_column": "curated_entities",
            "data_backend": "duckdb",
            "database_path": ":memory:",
        }

        with patch(
            "docpipe.core.operators.storage.entity_store_operator.StorageFactory.create_table_storage"
        ) as mock_factory:
            mock_factory.return_value = MagicMock()

            operator = EntityStoreOperator(config)

        assert operator.entities_column == "curated_entities"

    def test_invalid_backend(self):
        """Test unsupported storage backend."""
        with pytest.raises(ValueError, match="Unsupported entity storage backend"):
            EntityStoreOperator({"data_backend": "filesystem"})


class TestOperatorFeatures:
    """Test operator feature requirements."""

    def test_get_required_features(self):
        """Test required pipeline features."""
        required = EntityStoreOperator.get_required_features()

        assert required == [OperatorConstants.Columns.TRANSFORMED_ENTITIES_COLUMN_NAME]

    def test_get_static_required_features(self):
        """Test static required pipeline features."""
        required = EntityStoreOperator.get_static_required_features()

        assert required == [OperatorConstants.Columns.TRANSFORMED_ENTITIES_COLUMN_NAME]

    def test_validate_success(self, basic_config):
        """Test validation with the required feature available."""
        operator = EntityStoreOperator(basic_config)
        errors: list[str] = []
        warnings: list[str] = []

        operator.validate(
            errors=errors,
            warnings=warnings,
            available_features=["id", "name", "transformed_entities"],
        )

        assert errors == []
        assert warnings == []

    def test_validate_missing_entities(self, basic_config):
        """Test validation when curated entities are unavailable."""
        operator = EntityStoreOperator(basic_config)
        errors: list[str] = []
        warnings: list[str] = []

        operator.validate(
            errors=errors,
            warnings=warnings,
            available_features=["id", "name"],
        )

        assert errors
        assert any("transformed_entities" in str(error) for error in errors)


class TestOperatorTransform:
    """Test operator transform behavior."""

    @patch("docpipe.core.operators.storage.entity_store_operator.StorageFactory.create_table_storage")
    def test_transform_is_pass_through(self, mock_factory, basic_config, sample_table):
        """Test that the operator returns the original table unchanged."""
        mock_factory.return_value = MagicMock()

        operator = EntityStoreOperator(basic_config)

        result_tables, metadata = operator.transform(sample_table)

        assert len(result_tables) == 1
        assert result_tables[0] is sample_table
        assert metadata[Metrics.External.TOTAL_DOCS] == 2
        assert metadata[Metrics.External.PROCESSED_DOCS] == 2
        assert metadata[Metrics.External.FAILED_DOCS_COUNT] == 0
        assert metadata[Metrics.External.SKIPPED_DOCS_COUNT] == 0
        assert metadata[Metrics.External.NODE_STATUS] == ExecutionStatus.COMPLETED.value

    @patch("docpipe.core.operators.storage.entity_store_operator.StorageFactory.create_table_storage")
    def test_transform_empty_table(self, mock_factory, basic_config):
        """Test transforming an empty table."""
        mock_factory.return_value = MagicMock()

        operator = EntityStoreOperator(basic_config)

        empty_table = pa.table(
            {
                "id": pa.array([], type=pa.string()),
                "transformed_entities": pa.array([], type=pa.string()),
            }
        )

        result_tables, metadata = operator.transform(empty_table)

        assert len(result_tables) == 1
        assert result_tables[0] is empty_table
        assert metadata[Metrics.External.TOTAL_DOCS] == 0
        assert metadata[Metrics.External.PROCESSED_DOCS] == 0
        assert metadata[Metrics.External.NODE_STATUS] == ExecutionStatus.COMPLETED.value


class TestPostgresConfiguration:
    """Test PostgreSQL storage configuration."""

    @patch("docpipe.core.operators.storage.entity_store_operator.StorageFactory.create_table_storage")
    def test_postgres_backend(self, mock_factory):
        """Test PostgreSQL backend configuration."""
        mock_factory.return_value = MagicMock()

        postgres_config = {
            "host": "localhost",
            "port": 5432,
            "database": "docpipe",
            "user": "docpipe_user",
            "password": "test-password",
        }

        config = {
            "data_backend": "postgres",
            "postgres": postgres_config,
        }

        EntityStoreOperator(config)

        mock_factory.assert_called_once_with(
            storage_type="postgres",
            config=postgres_config,
        )


class TestEntityStorage:
    """Test storing curated entities."""

    def test_store_single_entity_table(self, basic_config):
        """Store a single entity object as one target-table row."""
        config = {
            **basic_config,
        }

        table = pa.table(
            {
                "id": ["doc1"],
                "name": ["invoice1.pdf"],
                "transformed_entities": ['{"Invoice": {"invoice_id": "INV-001", "vendor_name": "Acme Corp"}}'],
            }
        )

        with patch(
            "docpipe.core.operators.storage.entity_store_operator.StorageFactory.create_table_storage"
        ) as mock_factory:
            storage = MagicMock()
            storage.table_exists.return_value = False
            mock_factory.return_value = storage

            operator = EntityStoreOperator(config)
            result_tables, metadata = operator.transform(table)

        assert len(result_tables) == 1
        assert result_tables[0] is table

        storage.create_table.assert_called_once()
        storage.upsert_data.assert_called_once()

        stored_table = storage.upsert_data.call_args.kwargs["data"]

        assert stored_table.column_names == ["id", "invoice_id", "vendor_name"]
        assert stored_table["id"].to_pylist() == ["doc1:Invoice"]
        assert stored_table["invoice_id"].to_pylist() == ["INV-001"]
        assert stored_table["vendor_name"].to_pylist() == ["Acme Corp"]

        assert metadata[Metrics.External.PROCESSED_DOCS] == 1
        assert metadata[Metrics.External.FAILED_DOCS_COUNT] == 0


class TestEntityStorageDuckDB:
    """Test entity storage with the real DuckDB backend."""

    def test_store_single_entity_in_duckdb(self, tmp_path):
        """Store a single entity and read it back from DuckDB."""
        database_path = str(tmp_path / "entities.db")

        config = {
            "data_backend": "duckdb",
            "database_path": database_path,
        }

        table = pa.table(
            {
                "id": ["doc1"],
                "name": ["invoice1.pdf"],
                "transformed_entities": ['{"Invoice": {"invoice_id": "INV-001", "vendor_name": "Acme Corp"}}'],
            }
        )

        operator = EntityStoreOperator(config)
        result_tables, metadata = operator.transform(table)

        assert result_tables[0] is table
        assert metadata[Metrics.External.PROCESSED_DOCS] == 1
        assert metadata[Metrics.External.FAILED_DOCS_COUNT] == 0

        stored = operator.storage.read_data(table_name="Invoice")

        assert stored.column("id").to_pylist() == ["doc1:Invoice"]
        assert stored.column("invoice_id").to_pylist() == ["INV-001"]
        assert stored.column("vendor_name").to_pylist() == ["Acme Corp"]


class TestEntityStorageArrays:
    """Test storing array-valued entity tables."""

    def test_store_entity_array(self, tmp_path):
        """Store multiple rows from an array-valued entity table."""
        config = {
            "data_backend": "duckdb",
            "database_path": str(tmp_path / "entities.db"),
        }

        table = pa.table(
            {
                "id": ["doc1"],
                "name": ["invoice1.pdf"],
                "transformed_entities": [
                    (
                        '{"Invoice_line_items": ['
                        '{"description": "Item A", "quantity": 2},'
                        '{"description": "Item B", "quantity": 1}'
                        "]}"
                    )
                ],
            }
        )

        operator = EntityStoreOperator(config)
        result_tables, metadata = operator.transform(table)

        assert result_tables[0] is table
        assert metadata[Metrics.External.PROCESSED_DOCS] == 1
        assert metadata[Metrics.External.FAILED_DOCS_COUNT] == 0

        stored = operator.storage.read_data(table_name="Invoice_line_items")

        assert stored.column("id").to_pylist() == [
            "doc1:Invoice_line_items:0",
            "doc1:Invoice_line_items:1",
        ]
        assert stored.column("description").to_pylist() == ["Item A", "Item B"]
        assert stored.column("quantity").to_pylist() == [2, 1]


class TestEntityStorageMultipleDocuments:
    """Test storing entities from multiple documents."""

    def test_store_entities_from_multiple_documents(self, tmp_path):
        """Store entities from multiple documents without collisions."""
        config = {
            "data_backend": "duckdb",
            "database_path": str(tmp_path / "entities.db"),
        }

        table = pa.table(
            {
                "id": ["doc1", "doc2"],
                "name": ["invoice1.pdf", "invoice2.pdf"],
                "transformed_entities": [
                    '{"Invoice": {"invoice_id": "INV-001", "vendor_name": "Acme Corp"}}',
                    '{"Invoice": {"invoice_id": "INV-002", "vendor_name": "Beta Corp"}}',
                ],
            }
        )

        operator = EntityStoreOperator(config)
        result_tables, metadata = operator.transform(table)

        assert result_tables[0] is table
        assert metadata[Metrics.External.PROCESSED_DOCS] == 2
        assert metadata[Metrics.External.FAILED_DOCS_COUNT] == 0

        stored = operator.storage.read_data(table_name="Invoice")

        assert stored.num_rows == 2
        assert stored.column("id").to_pylist() == [
            "doc1:Invoice",
            "doc2:Invoice",
        ]
        assert stored.column("invoice_id").to_pylist() == [
            "INV-001",
            "INV-002",
        ]
        assert stored.column("vendor_name").to_pylist() == [
            "Acme Corp",
            "Beta Corp",
        ]


class TestEntityStorageErrors:
    """Test entity storage error handling."""

    def test_malformed_json_records_failed_document(self):
        """Malformed entity JSON should fail the document without raising."""
        config = {
            "data_backend": "duckdb",
            "database_path": ":memory:",
        }

        table = pa.table(
            {
                "id": ["doc1"],
                "name": ["invoice1.pdf"],
                "transformed_entities": ["{invalid-json"],
            }
        )

        operator = EntityStoreOperator(config)
        result_tables, metadata = operator.transform(table)

        assert result_tables[0] is table
        assert metadata[Metrics.External.PROCESSED_DOCS] == 0
        assert metadata[Metrics.External.FAILED_DOCS_COUNT] == 1
        assert metadata[Metrics.External.FAILED_DOCS] == [
            {
                "id": "doc1",
                "name": "invoice1.pdf",
                "reason": "Expecting property name enclosed in double quotes: line 1 column 2 (char 1)",
                "document_url": "",
            }
        ]
        assert metadata[Metrics.External.NODE_STATUS] == ExecutionStatus.COMPLETED_WITH_ERRORS

    def test_invalid_entity_shape_records_failed_document(self):
        """A non-object curated entity value should fail the document."""
        config = {
            "data_backend": "duckdb",
            "database_path": ":memory:",
        }

        table = pa.table(
            {
                "id": ["doc1"],
                "name": ["invoice1.pdf"],
                "transformed_entities": ['["not", "an", "object"]'],
            }
        )

        operator = EntityStoreOperator(config)
        result_tables, metadata = operator.transform(table)

        assert result_tables[0] is table
        assert metadata[Metrics.External.PROCESSED_DOCS] == 0
        assert metadata[Metrics.External.FAILED_DOCS_COUNT] == 1
        assert metadata[Metrics.External.FAILED_DOCS][0]["id"] == "doc1"
        assert metadata[Metrics.External.FAILED_DOCS][0]["name"] == "invoice1.pdf"
        assert metadata[Metrics.External.FAILED_DOCS][0]["reason"] == ("Curated entities must be a JSON object")
        assert metadata[Metrics.External.NODE_STATUS] == ExecutionStatus.COMPLETED_WITH_ERRORS


class TestEntityStorageSchemaEvolution:
    """Test storing entities whose fields evolve between documents."""

    def test_store_entities_with_different_fields(self, tmp_path):
        """Store documents with different entity fields in the same table."""
        config = {
            "data_backend": "duckdb",
            "database_path": str(tmp_path / "entities.db"),
        }

        table = pa.table(
            {
                "id": ["doc1", "doc2"],
                "name": ["invoice1.pdf", "invoice2.pdf"],
                "transformed_entities": [
                    '{"Invoice": {"invoice_id": "INV-001", "vendor_name": "Acme Corp"}}',
                    '{"Invoice": {"invoice_id": "INV-002", "vendor_name": "Beta Corp", "invoice_date": "2026-10-07"}}',
                ],
            }
        )

        operator = EntityStoreOperator(config)
        result_tables, metadata = operator.transform(table)

        assert result_tables[0] is table
        assert metadata[Metrics.External.PROCESSED_DOCS] == 2
        assert metadata[Metrics.External.FAILED_DOCS_COUNT] == 0

        stored = operator.storage.read_data(table_name="Invoice")

        assert stored.num_rows == 2
        assert stored.column("id").to_pylist() == [
            "doc1:Invoice",
            "doc2:Invoice",
        ]
        assert stored.column("invoice_id").to_pylist() == [
            "INV-001",
            "INV-002",
        ]
        assert stored.column("vendor_name").to_pylist() == [
            "Acme Corp",
            "Beta Corp",
        ]
        assert stored.column("invoice_date").to_pylist() == [
            None,
            "2026-10-07",
        ]
