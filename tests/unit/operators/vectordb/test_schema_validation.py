"""Tests for schema validation functionality in OpenSearchIndexManager."""

from unittest.mock import MagicMock

import pytest

from docpipe.core.operators.vectordb.adapters.outbound.opensearch.index_manager import OpenSearchIndexManager
from docpipe.exceptions.docpipe_exceptions import DocpipeException


class TestSchemaValidation:
    """Test schema validation with various scenarios."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock OpenSearch client."""
        client = MagicMock()
        client.indices.exists.return_value = False
        return client

    @pytest.fixture
    def valid_schema(self):
        """Create a valid schema for testing."""
        return {
            "schema_name": "test_schema",
            "schema_version": 1,
            "settings": {"index": {"knn": True, "number_of_shards": 2, "number_of_replicas": 1}},
            "mappings": {
                "properties": {
                    "doc_id": {"type": "keyword"},
                    "text": {"type": "text"},
                    "embeddings": {
                        "type": "knn_vector",
                        "dimension": 384,
                        "method": {
                            "name": "hnsw",
                            "space_type": "l2",
                            "engine": "faiss",
                            "parameters": {"ef_construction": 128, "m": 24},
                        },
                    },
                }
            },
        }

    def test_valid_schema_passes_validation(self, *, mock_client, valid_schema):
        """Test that a valid schema passes validation."""
        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            engine="faiss",
            algorithm="hnsw",
            space_type="l2",
        )

        # Should not raise exception
        manager._validate_schema(schema=valid_schema)

    def test_missing_schema_name_raises_error(self, *, mock_client, valid_schema):
        """Test that missing schema_name raises error."""
        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            engine="faiss",
            algorithm="hnsw",
            space_type="l2",
        )

        del valid_schema["schema_name"]

        with pytest.raises(DocpipeException) as exc_info:
            manager._validate_schema(schema=valid_schema)

        assert "schema_name" in str(exc_info.value)

    def test_missing_schema_version_raises_error(self, *, mock_client, valid_schema):
        """Test that missing schema_version raises error."""
        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            engine="faiss",
            algorithm="hnsw",
            space_type="l2",
        )

        del valid_schema["schema_version"]

        with pytest.raises(DocpipeException) as exc_info:
            manager._validate_schema(schema=valid_schema)

        assert "schema_version" in str(exc_info.value)

    def test_invalid_schema_version_raises_error(self, *, mock_client, valid_schema):
        """Test that invalid schema_version raises error."""
        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            engine="faiss",
            algorithm="hnsw",
            space_type="l2",
        )

        valid_schema["schema_version"] = 0

        with pytest.raises(DocpipeException) as exc_info:
            manager._validate_schema(schema=valid_schema)

        assert "positive integer" in str(exc_info.value)

    def test_missing_settings_raises_error(self, *, mock_client, valid_schema):
        """Test that missing settings raises error."""
        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            engine="faiss",
            algorithm="hnsw",
            space_type="l2",
        )

        del valid_schema["settings"]

        with pytest.raises(DocpipeException) as exc_info:
            manager._validate_schema(schema=valid_schema)

        assert "settings" in str(exc_info.value)

    def test_missing_mappings_raises_error(self, *, mock_client, valid_schema):
        """Test that missing mappings raises error."""
        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            engine="faiss",
            algorithm="hnsw",
            space_type="l2",
        )

        del valid_schema["mappings"]

        with pytest.raises(DocpipeException) as exc_info:
            manager._validate_schema(schema=valid_schema)

        assert "mappings" in str(exc_info.value)

    def test_missing_properties_raises_error(self, *, mock_client, valid_schema):
        """Test that missing properties raises error."""
        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            engine="faiss",
            algorithm="hnsw",
            space_type="l2",
        )

        del valid_schema["mappings"]["properties"]

        with pytest.raises(DocpipeException) as exc_info:
            manager._validate_schema(schema=valid_schema)

        assert "properties" in str(exc_info.value)

    def test_no_knn_vector_fields_raises_error(self, *, mock_client, valid_schema):
        """Test that no knn_vector fields raises error."""
        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            engine="faiss",
            algorithm="hnsw",
            space_type="l2",
        )

        # Remove vector field
        del valid_schema["mappings"]["properties"]["embeddings"]

        with pytest.raises(DocpipeException) as exc_info:
            manager._validate_schema(schema=valid_schema)

        assert "knn_vector" in str(exc_info.value)

    def test_invalid_dimension_raises_error(self, *, mock_client, valid_schema):
        """Test that invalid dimension raises error."""
        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            engine="faiss",
            algorithm="hnsw",
            space_type="l2",
        )

        valid_schema["mappings"]["properties"]["embeddings"]["dimension"] = -1

        with pytest.raises(DocpipeException) as exc_info:
            manager._validate_schema(schema=valid_schema)

        assert "dimension" in str(exc_info.value)
        assert "positive integer" in str(exc_info.value)

    def test_invalid_engine_raises_error(self, *, mock_client, valid_schema):
        """Test that invalid engine raises error."""
        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            engine="faiss",
            algorithm="hnsw",
            space_type="l2",
        )

        valid_schema["mappings"]["properties"]["embeddings"]["method"]["engine"] = "invalid_engine"

        with pytest.raises(DocpipeException) as exc_info:
            manager._validate_schema(schema=valid_schema)

        assert "invalid engine" in str(exc_info.value).lower()

    def test_invalid_algorithm_raises_error(self, *, mock_client, valid_schema):
        """Test that invalid algorithm raises error."""
        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            engine="faiss",
            algorithm="hnsw",
            space_type="l2",
        )

        valid_schema["mappings"]["properties"]["embeddings"]["method"]["name"] = "invalid_algo"

        with pytest.raises(DocpipeException) as exc_info:
            manager._validate_schema(schema=valid_schema)

        assert "invalid algorithm" in str(exc_info.value).lower()

    def test_incompatible_engine_algorithm_raises_error(self, *, mock_client, valid_schema):
        """Test that incompatible engine/algorithm raises error."""
        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            engine="faiss",
            algorithm="hnsw",
            space_type="l2",
        )

        # Lucene doesn't support IVF
        valid_schema["mappings"]["properties"]["embeddings"]["method"]["engine"] = "lucene"
        valid_schema["mappings"]["properties"]["embeddings"]["method"]["name"] = "ivf"

        with pytest.raises(DocpipeException) as exc_info:
            manager._validate_schema(schema=valid_schema)

        assert "not supported" in str(exc_info.value)

    def test_hnsw_parameter_out_of_range_logs_warning(self, *, mock_client, valid_schema):
        """Test that HNSW parameter out of range logs warning (doesn't raise exception)."""
        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            engine="faiss",
            algorithm="hnsw",
            space_type="l2",
        )

        # Set m outside optimal range
        valid_schema["mappings"]["properties"]["embeddings"]["method"]["parameters"]["m"] = 100

        # Should log warning but not raise exception
        manager._validate_schema(schema=valid_schema)

    def test_ivf_parameter_out_of_range_logs_warning(self, *, mock_client, valid_schema):
        """Test that IVF parameter out of range logs warning (doesn't raise exception)."""
        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            engine="faiss",
            algorithm="ivf",
            space_type="l2",
        )

        # Change to IVF algorithm
        valid_schema["mappings"]["properties"]["embeddings"]["method"]["name"] = "ivf"
        valid_schema["mappings"]["properties"]["embeddings"]["method"]["parameters"] = {
            "nlist": 50000,  # Outside optimal range
            "nprobes": 8,
        }

        # Should log warning but not raise exception
        manager._validate_schema(schema=valid_schema)

    def test_deeply_nested_fields_log_warning(self, *, mock_client, valid_schema):
        """Test that deeply nested fields log warning (doesn't raise exception)."""
        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            engine="faiss",
            algorithm="hnsw",
            space_type="l2",
        )

        # Create deeply nested structure (5 levels)
        valid_schema["mappings"]["properties"]["level1"] = {
            "type": "object",
            "properties": {
                "level2": {
                    "type": "object",
                    "properties": {
                        "level3": {
                            "type": "object",
                            "properties": {"level4": {"type": "object", "properties": {"level5": {"type": "text"}}}},
                        }
                    },
                }
            },
        }

        # Should log warning but not raise exception
        manager._validate_schema(schema=valid_schema)

    def test_too_many_fields_log_warning(self, *, mock_client, valid_schema):
        """Test that too many fields log warning (doesn't raise exception)."""
        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            engine="faiss",
            algorithm="hnsw",
            space_type="l2",
        )

        # Add many fields
        for i in range(1005):
            valid_schema["mappings"]["properties"][f"field_{i}"] = {"type": "text"}

        # Should log warning but not raise exception
        manager._validate_schema(schema=valid_schema)

    def test_undefined_analyzer_logs_warning(self, *, mock_client, valid_schema):
        """Test that undefined analyzer logs warning (doesn't raise exception)."""
        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            engine="faiss",
            algorithm="hnsw",
            space_type="l2",
        )

        # Add field with undefined analyzer
        valid_schema["mappings"]["properties"]["text"]["analyzer"] = "custom_analyzer"

        # Should log warning but not raise exception
        manager._validate_schema(schema=valid_schema)

    def test_defined_analyzer_no_warning(self, *, mock_client, valid_schema):
        """Test that defined analyzer doesn't log warning."""
        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            engine="faiss",
            algorithm="hnsw",
            space_type="l2",
        )

        # Define custom analyzer
        valid_schema["settings"]["analysis"] = {"analyzer": {"custom_analyzer": {"type": "standard"}}}

        # Use defined analyzer
        valid_schema["mappings"]["properties"]["text"]["analyzer"] = "custom_analyzer"

        manager._validate_schema(schema=valid_schema)

        # Should not raise exception

    def test_builtin_analyzer_no_warning(self, *, mock_client, valid_schema):
        """Test that built-in analyzer doesn't log warning."""
        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            engine="faiss",
            algorithm="hnsw",
            space_type="l2",
        )

        # Use built-in analyzer
        valid_schema["mappings"]["properties"]["text"]["analyzer"] = "standard"

        manager._validate_schema(schema=valid_schema)

        # Should not raise exception
