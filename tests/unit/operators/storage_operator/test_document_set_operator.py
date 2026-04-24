"""Unit tests for DocumentSetOperator.

Tests cover:
- Operator metadata and parameters
- Creating new document sets
- Updating existing document sets
- Soft-delete handling
- Validation errors
- Pass-through behavior
"""

import pytest
import pyarrow as pa

from core.operators.storage.document_set_operator import DocumentSetOperator
from core.operators.abstract_operator import OperatorCategory
from common.constants.constants import ExecutionStatus, Metrics
from common.constants.operator_constants import OperatorConstants
from common.exceptions.datasift_exceptions import (
    FlowValidationException,
)


@pytest.fixture
def basic_config():
    """Basic configuration for DocumentSetOperator."""
    # database_path removed - operator always uses default
    return {
        "document_set_name": "Test Documents",
        "description": "Test description",
        "metadata": {"source": "test"},
    }


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


@pytest.mark.usefixtures("cleanup_test_document_sets")
class TestOperatorMetadata:
    """Test operator metadata and parameters."""

    def test_operator_metadata(self, basic_config):
        """Test operator metadata structure."""
        operator = DocumentSetOperator(basic_config)
        metadata = operator.get_metadata()

        assert metadata["name"] == "DocumentSetOperator"
        assert metadata["category"] == OperatorCategory.Storage.value
        assert "description" in metadata
        assert "parameters" in metadata

    def test_operator_parameters(self, basic_config):
        """Test operator parameters definition."""
        operator = DocumentSetOperator(basic_config)
        metadata = operator.get_metadata()

        params = metadata["parameters"]
        assert "document_set_name" in params
        assert params["document_set_name"]["required"] is True
        # database_path removed - always uses default
        assert "description" in params
        assert "metadata" in params
        assert "retain_deleted_docs" in params
        assert "document_set_id" in params

    def test_operator_category(self, basic_config):
        """Test operator category is Storage."""
        operator = DocumentSetOperator(basic_config)
        assert operator.category == OperatorCategory.Storage

    def test_operator_short_name(self, basic_config):
        """Test operator short name."""
        operator = DocumentSetOperator(basic_config)
        assert operator.short_name == "document_set"

    def test_get_required_features(self, basic_config):
        """Test required features (columns)."""
        operator = DocumentSetOperator(basic_config)
        required = operator.get_required_features()

        assert OperatorConstants.Columns.ID in required


@pytest.mark.usefixtures("cleanup_test_document_sets")
class TestTransformCreateNew:
    """Test creating new document sets."""

    def test_transform_create_new(self, basic_config, sample_table):
        """Test transforming data creates new document set."""
        operator = DocumentSetOperator(basic_config)

        result_tables, metadata = operator.transform(sample_table)

        assert len(result_tables) == 1
        assert result_tables[0].num_rows == sample_table.num_rows
        assert metadata[Metrics.External.NODE_STATUS] == ExecutionStatus.COMPLETED.value
        assert metadata["stored_documents"] == 3
        assert metadata["total_size_bytes"] == 600
        assert metadata["total_pages"] == 6

    def test_transform_creates_document_set(self, basic_config, sample_table):
        """Test that transform creates document set in repository."""
        operator = DocumentSetOperator(basic_config)

        result_tables, metadata = operator.transform(sample_table)

        assert "document_set_id" in metadata
        assert metadata["document_set_name"] == "Test Documents"

    def test_transform_empty_table(self, basic_config):
        """Test transforming empty table."""
        operator = DocumentSetOperator(basic_config)
        empty_table = pa.table({"id": [], "name": [], "content": []})

        result_tables, metadata = operator.transform(empty_table)

        assert len(result_tables) == 1
        assert metadata["stored_documents"] == 0


@pytest.mark.usefixtures("cleanup_test_document_sets")
class TestTransformUpdateExisting:
    """Test updating existing document sets."""

    def test_transform_update_existing(self, basic_config, sample_table):
        """Test updating existing document set."""
        operator = DocumentSetOperator(basic_config)

        # First transform creates document set
        result1, metadata1 = operator.transform(sample_table)
        doc_set_id = metadata1["document_set_id"]

        # Second transform with same name updates
        result2, metadata2 = operator.transform(sample_table)

        assert metadata2["document_set_id"] == doc_set_id
        assert metadata2["stored_documents"] == 3

    def test_transform_with_document_set_id(self, basic_config, sample_table):
        """Test transform with explicit document_set_id."""
        # Create initial document set
        operator1 = DocumentSetOperator(basic_config)
        result1, metadata1 = operator1.transform(sample_table)
        doc_set_id = metadata1["document_set_id"]

        # Update using document_set_id
        update_config = basic_config.copy()
        update_config["document_set_id"] = doc_set_id
        update_config["description"] = "Updated description"

        operator2 = DocumentSetOperator(update_config)
        result2, metadata2 = operator2.transform(sample_table)

        assert metadata2["document_set_id"] == doc_set_id


class TestTransformWithSoftDeletes:
    """Test soft-delete handling."""

    def test_transform_retain_deleted_docs(self, basic_config, sample_table):
        """Test that retain_deleted_docs flag works."""
        config = basic_config.copy()
        config["retain_deleted_docs"] = True

        operator = DocumentSetOperator(config)
        result_tables, metadata = operator.transform(sample_table)

        assert metadata["deleted_documents"] == 0

    def test_transform_without_retain_deleted_docs(self, basic_config, sample_table):
        """Test default behavior without retaining deleted docs."""
        operator = DocumentSetOperator(basic_config)
        result_tables, metadata = operator.transform(sample_table)

        # Should have deleted_documents key (even if 0)
        assert "deleted_documents" in metadata


class TestTransformMissingIDColumn:
    """Test validation error for missing ID column."""

    def test_transform_missing_id_column(self, basic_config):
        """Test that missing id column causes error."""
        operator = DocumentSetOperator(basic_config)

        # Table without id column
        bad_table = pa.table({"name": ["Document 1"], "content": ["Content 1"]})

        result_tables, metadata = operator.transform(bad_table)

        assert metadata[Metrics.External.NODE_STATUS] == ExecutionStatus.FAILED.value
        assert "error" in metadata
        assert "id" in metadata["error"].lower()


class TestTransformInvalidName:
    """Test name validation."""

    def test_transform_invalid_name(self, temp_duckdb_path, sample_table):
        """Test that invalid document set name raises error."""
        config = {
            "document_set_name": "",  # Empty name
            "database_path": temp_duckdb_path,
        }

        with pytest.raises(FlowValidationException):
            DocumentSetOperator(config)

    def test_transform_missing_name(self, temp_duckdb_path, sample_table):
        """Test that missing document set name raises error."""
        config = {"database_path": temp_duckdb_path}

        with pytest.raises(FlowValidationException):
            DocumentSetOperator(config)


class TestOperatorPassThrough:
    """Test that original table is returned unchanged."""

    def test_operator_pass_through(self, basic_config, sample_table):
        """Test that transform returns original table unchanged."""
        operator = DocumentSetOperator(basic_config)

        result_tables, metadata = operator.transform(sample_table)

        # Should return exactly one table
        assert len(result_tables) == 1

        # Should be the same table (pass-through)
        result_table = result_tables[0]
        assert result_table.num_rows == sample_table.num_rows
        assert result_table.num_columns == sample_table.num_columns
        assert result_table.schema.equals(sample_table.schema)

    def test_operator_preserves_all_columns(self, basic_config, sample_table):
        """Test that all columns are preserved in output."""
        operator = DocumentSetOperator(basic_config)

        result_tables, metadata = operator.transform(sample_table)
        result_table = result_tables[0]

        # All original columns should be present
        for col_name in sample_table.schema.names:
            assert col_name in result_table.schema.names


class TestOperatorInitialization:
    """Test operator initialization."""

    def test_init_with_valid_config(self, basic_config):
        """Test initialization with valid configuration."""
        operator = DocumentSetOperator(basic_config)

        assert operator.document_set_name == "Test Documents"
        assert operator.description == "Test description"
        assert operator.metadata_config == {"source": "test"}
        assert operator.retain_deleted_docs is False

    def test_init_with_minimal_config(self, temp_duckdb_path):
        """Test initialization with minimal configuration."""
        config = {
            "document_set_name": "Test Documents",
            "database_path": temp_duckdb_path,
        }

        operator = DocumentSetOperator(config)

        assert operator.document_set_name == "Test Documents"
        assert operator.description is None
        assert operator.metadata_config is None

    def test_init_with_default_database_path(self):
        """Test initialization with default database path."""
        config = {"document_set_name": "Test Documents"}

        operator = DocumentSetOperator(config)

        # Path is normalized to absolute, so check it ends with the default filename
        assert operator.database_path.endswith("document_sets.duckdb")

    def test_init_services_created(self, basic_config):
        """Test that services are initialized."""
        operator = DocumentSetOperator(basic_config)

        assert operator.storage is not None
        assert operator.repository is not None
        assert operator.service is not None


class TestOperatorMetadataOutput:
    """Test metadata output from transform."""

    def test_metadata_includes_document_set_info(self, basic_config, sample_table):
        """Test that metadata includes document set information."""
        operator = DocumentSetOperator(basic_config)

        result_tables, metadata = operator.transform(sample_table)

        assert "document_set_name" in metadata
        assert "document_set_id" in metadata
        assert "database_path" in metadata
        assert "table_name" in metadata

    def test_metadata_includes_metrics(self, basic_config, sample_table):
        """Test that metadata includes computed metrics."""
        operator = DocumentSetOperator(basic_config)

        result_tables, metadata = operator.transform(sample_table)

        assert "stored_documents" in metadata
        assert "total_size_bytes" in metadata
        assert "total_pages" in metadata
        assert metadata["stored_documents"] == 3

    def test_metadata_includes_status(self, basic_config, sample_table):
        """Test that metadata includes execution status."""
        operator = DocumentSetOperator(basic_config)

        result_tables, metadata = operator.transform(sample_table)

        assert Metrics.External.NODE_STATUS in metadata
        assert Metrics.External.PROCESSED_DOCS in metadata


class TestOperatorErrorHandling:
    """Test error handling in operator."""

    def test_error_handling_invalid_table(self, basic_config):
        """Test error handling for invalid table."""
        operator = DocumentSetOperator(basic_config)

        # Table without required id column
        bad_table = pa.table({"name": ["doc1"]})

        result_tables, metadata = operator.transform(bad_table)

        assert metadata[Metrics.External.NODE_STATUS] == ExecutionStatus.FAILED.value
        assert "error" in metadata

    def test_error_handling_preserves_table(self, basic_config):
        """Test that table is still returned on error."""
        operator = DocumentSetOperator(basic_config)

        bad_table = pa.table({"name": ["doc1"]})

        result_tables, metadata = operator.transform(bad_table)

        # Should still return the table
        assert len(result_tables) == 1
        assert result_tables[0].equals(bad_table)


@pytest.mark.usefixtures("cleanup_test_document_sets")
class TestOperatorWithDifferentSchemas:
    """Test operator with different table schemas."""

    def test_transform_with_minimal_schema(self):
        """Test transform with minimal schema (only id)."""
        config = {"document_set_name": "Minimal Schema Test"}
        operator = DocumentSetOperator(config)

        minimal_table = pa.table(
            {"id": ["doc1", "doc2"], "content": ["Content 1", "Content 2"]}
        )

        result_tables, metadata = operator.transform(minimal_table)

        assert metadata[Metrics.External.NODE_STATUS] == ExecutionStatus.COMPLETED.value
        assert metadata["stored_documents"] == 2

    def test_transform_with_extended_schema(self):
        """Test transform with extended schema."""
        config = {"document_set_name": "Extended Schema Test"}
        operator = DocumentSetOperator(config)

        extended_table = pa.table(
            {
                "id": ["doc1"],
                "name": ["Document 1"],
                "content": ["Content 1"],
                "size": [100],
                "pages_processed": [1],
                "custom_field": ["custom value"],
                "another_field": [42],
            }
        )

        result_tables, metadata = operator.transform(extended_table)

        assert metadata[Metrics.External.NODE_STATUS] == ExecutionStatus.COMPLETED.value
        assert metadata["stored_documents"] == 1


@pytest.mark.usefixtures("cleanup_test_document_sets")
class TestOperatorMultipleTransforms:
    """Test multiple transforms on same operator."""

    def test_multiple_transforms_accumulate(self, basic_config):
        """Test that multiple transforms accumulate data."""
        operator = DocumentSetOperator(basic_config)

        # First batch
        batch1 = pa.table(
            {
                "id": ["doc1", "doc2"],
                "name": ["Doc 1", "Doc 2"],
                "content": ["Content 1", "Content 2"],
                "size": [100, 200],
                "pages_processed": [1, 2],
            }
        )
        result1, metadata1 = operator.transform(batch1)

        # Second batch with new documents
        batch2 = pa.table(
            {
                "id": ["doc3", "doc4"],
                "name": ["Doc 3", "Doc 4"],
                "content": ["Content 3", "Content 4"],
                "size": [300, 400],
                "pages_processed": [3, 4],
            }
        )
        result2, metadata2 = operator.transform(batch2)

        # Should have 4 total documents
        assert metadata2["stored_documents"] == 4
        assert metadata2["total_size_bytes"] == 1000

    def test_multiple_transforms_update_existing(self):
        """Test that multiple transforms update existing documents."""
        config = {"document_set_name": "Update Test"}
        operator = DocumentSetOperator(config)

        # First batch
        batch1 = pa.table(
            {
                "id": ["doc1"],
                "name": ["Original"],
                "content": ["Original content"],
                "size": [100],
                "pages_processed": [1],
            }
        )
        result1, metadata1 = operator.transform(batch1)

        # Second batch updates same document
        batch2 = pa.table(
            {
                "id": ["doc1"],
                "name": ["Updated"],
                "content": ["Updated content"],
                "size": [200],
                "pages_processed": [2],
            }
        )
        result2, metadata2 = operator.transform(batch2)

        # Should still have only 1 document (updated)
        assert metadata2["stored_documents"] == 1
        assert metadata2["total_size_bytes"] == 200
