"""Tests for schema template loading functionality in OpenSearchIndexManager."""

import json
from unittest.mock import MagicMock

import pytest

from datasift.core.operators.vectordb.opensearch_index_manager import OpenSearchIndexManager


class TestSchemaTemplateLoading:
    """Test schema template loading with various scenarios."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock OpenSearch client."""
        client = MagicMock()
        client.indices.exists.return_value = False
        return client

    @pytest.fixture
    def sample_schema_template(self):
        """Create a sample schema template with placeholders."""
        return {
            "settings": {"index": {"knn": True, "number_of_shards": 2, "number_of_replicas": 1}},
            "mappings": {
                "properties": {
                    "doc_id": {"type": "keyword"},
                    "text": {"type": "text"},
                    "embeddings": {
                        "type": "knn_vector",
                        "dimension": "__VECTOR_DIMENSION__",
                        "method": {
                            "name": "__ALGORITHM__",
                            "space_type": "__SPACE_TYPE__",
                            "engine": "__ENGINE__",
                            "parameters": "__ENGINE_PARAMETERS__",
                        },
                    },
                }
            },
        }

    def test_load_schema_from_file(self, *, mock_client, sample_schema_template, tmp_path):
        """Test loading schema template from file."""
        # Create temporary schema file
        schema_file = tmp_path / "test_schema.json"
        with open(schema_file, "w") as f:
            json.dump(sample_schema_template, f)

        # Initialize index manager with schema template path
        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            engine="faiss",
            algorithm="hnsw",
            space_type="l2",
            vector_dimension=384,
            schema_template_path=str(schema_file),
        )

        # Build index body
        index_body = manager.build_index_body()

        # Verify placeholders were replaced
        assert index_body["mappings"]["properties"]["embeddings"]["dimension"] == 384
        assert index_body["mappings"]["properties"]["embeddings"]["method"]["name"] == "hnsw"
        assert index_body["mappings"]["properties"]["embeddings"]["method"]["space_type"] == "l2"
        assert index_body["mappings"]["properties"]["embeddings"]["method"]["engine"] == "faiss"
        assert isinstance(index_body["mappings"]["properties"]["embeddings"]["method"]["parameters"], dict)

        # Verify metadata was injected
        assert index_body["mappings"]["_meta"]["engine"] == "faiss"
        assert index_body["mappings"]["_meta"]["algorithm"] == "hnsw"
        assert index_body["mappings"]["_meta"]["created_by"] == "datasift-opensource"

    def test_fallback_when_file_not_found(self, *, mock_client):
        """Test fallback to dynamic generation when schema file not found."""
        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            engine="faiss",
            algorithm="hnsw",
            space_type="l2",
            vector_dimension=384,
            available_features={"embeddings": {"type": "vector", "available_for_vector_db": True}},
            schema_template_path="nonexistent/schema.json",
        )

        # Build index body - should fall back to dynamic generation
        index_body = manager.build_index_body()

        # Verify dynamic generation was used
        assert "mappings" in index_body
        assert "settings" in index_body
        assert index_body["mappings"]["properties"]["embeddings"]["type"] == "knn_vector"

    def test_fallback_when_invalid_json(self, *, mock_client, tmp_path):
        """Test fallback when schema file contains invalid JSON."""
        # Create file with invalid JSON
        schema_file = tmp_path / "invalid_schema.json"
        with open(schema_file, "w") as f:
            f.write("{ invalid json }")

        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            engine="faiss",
            algorithm="hnsw",
            space_type="l2",
            vector_dimension=384,
            available_features={"embeddings": {"type": "vector", "available_for_vector_db": True}},
            schema_template_path=str(schema_file),
        )

        # Build index body - should fall back to dynamic generation
        index_body = manager.build_index_body()

        # Verify dynamic generation was used
        assert "mappings" in index_body
        assert index_body["mappings"]["properties"]["embeddings"]["type"] == "knn_vector"

    def test_no_schema_path_uses_dynamic_generation(self, *, mock_client):
        """Test that no schema_template_path uses dynamic generation (backward compatible)."""
        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            engine="faiss",
            algorithm="hnsw",
            space_type="l2",
            vector_dimension=384,
            available_features={
                "embeddings": {"type": "vector", "available_for_vector_db": True},
                "text": {"type": "string", "available_for_vector_db": True},
            },
        )

        # Build index body
        index_body = manager.build_index_body()

        # Verify dynamic generation was used
        assert "mappings" in index_body
        assert "embeddings" in index_body["mappings"]["properties"]
        assert "text" in index_body["mappings"]["properties"]

    def test_placeholder_replacement_in_nested_structures(self, *, mock_client, tmp_path):
        """Test that placeholders are replaced in deeply nested structures."""
        schema = {
            "settings": {"index": {"knn": True, "knn.algo_param.ef_search": 100}},
            "mappings": {
                "properties": {
                    "embeddings": {
                        "type": "knn_vector",
                        "dimension": "__VECTOR_DIMENSION__",
                        "method": {
                            "name": "__ALGORITHM__",
                            "space_type": "__SPACE_TYPE__",
                            "engine": "__ENGINE__",
                            "parameters": "__ENGINE_PARAMETERS__",
                        },
                    },
                    "metadata": {
                        "properties": {"engine_info": {"type": "text", "fields": {"keyword": {"type": "keyword"}}}}
                    },
                }
            },
        }

        schema_file = tmp_path / "nested_schema.json"
        with open(schema_file, "w") as f:
            json.dump(schema, f)

        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            engine="lucene",
            algorithm="hnsw",
            space_type="cosine",
            vector_dimension=512,
            engine_parameters={"ef_construction": 256, "m": 32},
            schema_template_path=str(schema_file),
        )

        index_body = manager.build_index_body()

        # Verify all placeholders were replaced
        embeddings = index_body["mappings"]["properties"]["embeddings"]
        assert embeddings["dimension"] == 512
        assert embeddings["method"]["name"] == "hnsw"
        assert embeddings["method"]["space_type"] == "cosine"
        assert embeddings["method"]["engine"] == "lucene"
        assert embeddings["method"]["parameters"]["ef_construction"] == 256
        assert embeddings["method"]["parameters"]["m"] == 32

    def test_engine_parameters_placeholder_replacement(self, *, mock_client, tmp_path):
        """Test that __ENGINE_PARAMETERS__ placeholder is replaced with dict."""
        schema = {
            "mappings": {
                "properties": {
                    "embeddings": {
                        "type": "knn_vector",
                        "dimension": "__VECTOR_DIMENSION__",
                        "method": {
                            "name": "__ALGORITHM__",
                            "space_type": "__SPACE_TYPE__",
                            "engine": "__ENGINE__",
                            "parameters": "__ENGINE_PARAMETERS__",
                        },
                    }
                }
            }
        }

        schema_file = tmp_path / "params_schema.json"
        with open(schema_file, "w") as f:
            json.dump(schema, f)

        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            engine="faiss",
            algorithm="ivf",
            space_type="l2",
            vector_dimension=384,
            engine_parameters={"nlist": 256, "nprobe": 16},
            schema_template_path=str(schema_file),
        )

        index_body = manager.build_index_body()

        # Verify ENGINE_PARAMETERS was replaced with actual dict
        params = index_body["mappings"]["properties"]["embeddings"]["method"]["parameters"]
        assert isinstance(params, dict)
        assert params["nlist"] == 256
        assert params["nprobe"] == 16
