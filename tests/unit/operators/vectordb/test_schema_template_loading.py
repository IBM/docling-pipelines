"""Tests for schema template loading functionality in OpenSearchIndexManager."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from docpipe.core.operators.vectordb.adapters.outbound.opensearch.index_manager import OpenSearchIndexManager
from docpipe.exceptions.docpipe_exceptions import DocpipeException


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
            "field_types": {
                "vector": {
                    "type": "knn_vector",
                    "dimension": "__VECTOR_DIMENSION__",
                    "method": {
                        "name": "__ALGORITHM__",
                        "space_type": "__SPACE_TYPE__",
                        "engine": "__ENGINE__",
                        "parameters": "__ENGINE_PARAMETERS__",
                    },
                },
                "string": {"type": "text", "fields": {"keyword": {"type": "keyword", "ignore_above": 256}}},
                "keyword": {"type": "keyword"},
            },
            "indexing_rules": {
                "doc_id": {"field_type": "keyword"},
                "text": {"field_type": "string"},
                "embeddings": {"field_type": "vector"},
            },
        }

    def test_load_schema_from_file(self, *, mock_client, sample_schema_template, tmp_path):
        """Test loading schema template from file."""
        # Create temporary schema file
        schema_file = tmp_path / "test_schema.json"
        with Path(schema_file).open("w") as f:
            json.dump(sample_schema_template, f)

        # Initialize index manager with schema template path and available features
        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            engine="faiss",
            algorithm="hnsw",
            space_type="l2",
            schema_template_path=str(schema_file),
            available_features={
                "doc_id": {"type": "string", "available_for_vector_db": True},
                "text": {"type": "string", "available_for_vector_db": True},
                "embeddings": {"type": "vector", "available_for_vector_db": True},
            },
        )

        # Build index body
        dimension_mapping = {"embeddings": 384}
        index_body = manager.build_index_body(dimension_mapping=dimension_mapping)

        # Verify placeholders were replaced
        assert index_body["mappings"]["properties"]["embeddings"]["dimension"] == 384
        assert index_body["mappings"]["properties"]["embeddings"]["method"]["name"] == "hnsw"
        assert index_body["mappings"]["properties"]["embeddings"]["method"]["space_type"] == "l2"
        assert index_body["mappings"]["properties"]["embeddings"]["method"]["engine"] == "faiss"
        assert isinstance(index_body["mappings"]["properties"]["embeddings"]["method"]["parameters"], dict)

        # Verify metadata was injected
        assert index_body["mappings"]["_meta"]["engine"] == "faiss"
        assert index_body["mappings"]["_meta"]["algorithm"] == "hnsw"
        assert index_body["mappings"]["_meta"]["created_by"] == "docling-pipelines"

    def test_fallback_when_file_not_found(self, *, mock_client):
        """Test fallback to dynamic generation when schema file not found."""
        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            engine="faiss",
            algorithm="hnsw",
            space_type="l2",
            available_features={"embeddings": {"type": "vector", "available_for_vector_db": True}},
            schema_template_path="nonexistent/schema.json",
        )

        # Build index body - should fall back to dynamic generation
        dimension_mapping = {"embeddings": 384}
        index_body = manager.build_index_body(dimension_mapping=dimension_mapping)

        # Verify dynamic generation was used
        assert "mappings" in index_body
        assert "settings" in index_body
        assert index_body["mappings"]["properties"]["embeddings"]["type"] == "knn_vector"

    def test_fallback_when_invalid_json(self, *, mock_client, tmp_path):
        """Test fallback when schema file contains invalid JSON."""
        # Create file with invalid JSON
        schema_file = tmp_path / "invalid_schema.json"
        with Path(schema_file).open("w") as f:
            f.write("{ invalid json }")

        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            engine="faiss",
            algorithm="hnsw",
            space_type="l2",
            available_features={"embeddings": {"type": "vector", "available_for_vector_db": True}},
            schema_template_path=str(schema_file),
        )

        # Build index body - should fall back to dynamic generation
        dimension_mapping = {"embeddings": 384}
        index_body = manager.build_index_body(dimension_mapping=dimension_mapping)

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
            available_features={
                "embeddings": {"type": "vector", "available_for_vector_db": True},
                "text": {"type": "string", "available_for_vector_db": True},
            },
        )

        # Build index body
        dimension_mapping = {"embeddings": 384}
        index_body = manager.build_index_body(dimension_mapping=dimension_mapping)

        # Verify dynamic generation was used
        assert "mappings" in index_body
        assert "embeddings" in index_body["mappings"]["properties"]
        assert "text" in index_body["mappings"]["properties"]

    def test_placeholder_replacement_in_nested_structures(self, *, mock_client, tmp_path):
        """Test that placeholders are replaced in deeply nested structures."""
        schema = {
            "settings": {"index": {"knn": True, "knn.algo_param.ef_search": 100}},
            "field_types": {
                "vector": {
                    "type": "knn_vector",
                    "dimension": "__VECTOR_DIMENSION__",
                    "method": {
                        "name": "__ALGORITHM__",
                        "space_type": "__SPACE_TYPE__",
                        "engine": "__ENGINE__",
                        "parameters": "__ENGINE_PARAMETERS__",
                    },
                },
                "nested_text": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            },
            "indexing_rules": {
                "embeddings": {"field_type": "vector"},
                "metadata": {"properties": {"engine_info": {"field_type": "nested_text"}}},
            },
        }

        schema_file = tmp_path / "nested_schema.json"
        with Path(schema_file).open("w") as f:
            json.dump(schema, f)

        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            engine="lucene",
            algorithm="hnsw",
            space_type="cosine",
            engine_parameters={"ef_construction": 256, "m": 32},
            schema_template_path=str(schema_file),
            available_features={
                "embeddings": {"type": "vector", "available_for_vector_db": True},
                "metadata": {"type": "object", "available_for_vector_db": True},
            },
        )

        dimension_mapping = {"embeddings": 512}
        index_body = manager.build_index_body(dimension_mapping=dimension_mapping)

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
            "field_types": {
                "vector": {
                    "type": "knn_vector",
                    "dimension": "__VECTOR_DIMENSION__",
                    "method": {
                        "name": "__ALGORITHM__",
                        "space_type": "__SPACE_TYPE__",
                        "engine": "__ENGINE__",
                        "parameters": "__ENGINE_PARAMETERS__",
                    },
                }
            },
            "indexing_rules": {"embeddings": {"field_type": "vector"}},
        }

        schema_file = tmp_path / "params_schema.json"
        with Path(schema_file).open("w") as f:
            json.dump(schema, f)

        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            engine="faiss",
            algorithm="ivf",
            space_type="l2",
            engine_parameters={"nlist": 256, "nprobe": 16},
            schema_template_path=str(schema_file),
            available_features={
                "embeddings": {"type": "vector", "available_for_vector_db": True},
            },
        )

        dimension_mapping = {"embeddings": 384}
        index_body = manager.build_index_body(dimension_mapping=dimension_mapping)

        # Verify ENGINE_PARAMETERS was replaced with actual dict
        params = index_body["mappings"]["properties"]["embeddings"]["method"]["parameters"]
        assert isinstance(params, dict)
        assert params["nlist"] == 256
        assert params["nprobe"] == 16

    def test_indexing_rules_with_feature_mappings_and_custom_analyzer(self, *, mock_client, tmp_path):
        """Test that custom analyzers are applied correctly with feature mappings."""
        schema = {
            "settings": {
                "index": {"knn": True},
                "analysis": {
                    "analyzer": {
                        "content_analyzer": {
                            "type": "custom",
                            "tokenizer": "standard",
                            "filter": ["lowercase", "stop", "snowball"],
                        }
                    }
                },
            },
            "field_types": {
                "vector": {
                    "type": "knn_vector",
                    "dimension": "__VECTOR_DIMENSION__",
                    "method": {
                        "name": "__ALGORITHM__",
                        "space_type": "__SPACE_TYPE__",
                        "engine": "__ENGINE__",
                        "parameters": "__ENGINE_PARAMETERS__",
                    },
                },
                "content_text": {
                    "type": "text",
                    "analyzer": "content_analyzer",
                    "fields": {"keyword": {"type": "keyword", "ignore_above": 256}},
                },
                "string": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            },
            "indexing_rules": {
                "content": {"field_type": "content_text"},
                "title": {"field_type": "string"},
                "embeddings": {"field_type": "vector"},
            },
        }

        schema_file = tmp_path / "analyzer_test_schema.json"
        with Path(schema_file).open("w") as f:
            json.dump(schema, f)

        # Use feature mappings to rename content -> document_content
        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            engine="faiss",
            algorithm="hnsw",
            space_type="l2",
            schema_template_path=str(schema_file),
            available_features={
                "content": {"type": "string", "available_for_vector_db": True},
                "title": {"type": "string", "available_for_vector_db": True},
                "embeddings": {"type": "vector", "available_for_vector_db": True},
            },
            feature_mappings=[
                {"feature_name": "content", "mapped_column_name": "document_content"},
                {"feature_name": "title", "mapped_column_name": "document_title"},
            ],
        )

        dimension_mapping = {"embeddings": 384}
        index_body = manager.build_index_body(dimension_mapping=dimension_mapping)

        # Verify content field was renamed to document_content and has custom analyzer
        assert "document_content" in index_body["mappings"]["properties"]
        assert "content" not in index_body["mappings"]["properties"]
        assert index_body["mappings"]["properties"]["document_content"]["type"] == "text"
        assert index_body["mappings"]["properties"]["document_content"]["analyzer"] == "content_analyzer"

        # Verify title field was renamed to document_title and does NOT have custom analyzer
        assert "document_title" in index_body["mappings"]["properties"]
        assert "title" not in index_body["mappings"]["properties"]
        assert index_body["mappings"]["properties"]["document_title"]["type"] == "text"
        assert "analyzer" not in index_body["mappings"]["properties"]["document_title"]

        # Verify embeddings field is not renamed (no mapping provided)
        assert "embeddings" in index_body["mappings"]["properties"]
        assert index_body["mappings"]["properties"]["embeddings"]["type"] == "knn_vector"

        # Verify analyzer definition is preserved in settings
        assert "analysis" in index_body["settings"]
        assert "analyzer" in index_body["settings"]["analysis"]
        assert "content_analyzer" in index_body["settings"]["analysis"]["analyzer"]


class TestIndexingRules:
    """Comprehensive tests for indexing_rules functionality."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock OpenSearch client."""
        client = MagicMock()
        client.indices.exists.return_value = False
        return client

    def test_indexing_rules_basic_field_type_override(self, *, mock_client, tmp_path):
        """Test simple field_type override: content (string) -> content_text."""
        schema = {
            "field_types": {
                "content_text": {
                    "type": "text",
                    "analyzer": "standard",
                },
                "string": {
                    "type": "text",
                    "fields": {"keyword": {"type": "keyword"}},
                },
            },
            "indexing_rules": {
                "content": {"field_type": "content_text"},
            },
        }

        schema_file = tmp_path / "basic_override.json"
        with Path(schema_file).open("w") as f:
            json.dump(schema, f)

        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            schema_template_path=str(schema_file),
            available_features={
                "content": {"type": "string", "available_for_vector_db": True},
            },
        )

        dimension_mapping = {"embeddings": 384}
        index_body = manager.build_index_body(dimension_mapping=dimension_mapping)

        # Verify correct field_type template is used
        assert index_body["mappings"]["properties"]["content"]["type"] == "text"
        assert index_body["mappings"]["properties"]["content"]["analyzer"] == "standard"

    def test_indexing_rules_with_boost_override(self, *, mock_client, tmp_path):
        """Test field_type + boost override."""
        schema = {
            "field_types": {
                "string": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            },
            "indexing_rules": {
                "title": {"field_type": "string", "boost": 2.0},
            },
        }

        schema_file = tmp_path / "boost_override.json"
        with Path(schema_file).open("w") as f:
            json.dump(schema, f)

        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            schema_template_path=str(schema_file),
            available_features={
                "title": {"type": "string", "available_for_vector_db": True},
            },
        )

        dimension_mapping = {"embeddings": 384}
        index_body = manager.build_index_body(dimension_mapping=dimension_mapping)

        # Verify boost is applied correctly
        assert index_body["mappings"]["properties"]["title"]["boost"] == 2.0
        assert index_body["mappings"]["properties"]["title"]["type"] == "text"

    def test_indexing_rules_with_copy_to_override(self, *, mock_client, tmp_path):
        """Test field_type + copy_to override."""
        schema = {
            "field_types": {
                "string": {"type": "text"},
            },
            "indexing_rules": {
                "content": {"field_type": "string", "copy_to": ["all_text", "searchable"]},
            },
        }

        schema_file = tmp_path / "copy_to_override.json"
        with Path(schema_file).open("w") as f:
            json.dump(schema, f)

        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            schema_template_path=str(schema_file),
            available_features={
                "content": {"type": "string", "available_for_vector_db": True},
            },
        )

        dimension_mapping = {"embeddings": 384}
        index_body = manager.build_index_body(dimension_mapping=dimension_mapping)

        # Verify copy_to array is applied
        assert index_body["mappings"]["properties"]["content"]["copy_to"] == ["all_text", "searchable"]

    def test_indexing_rules_with_multiple_overrides(self, *, mock_client, tmp_path):
        """Test field_type + boost + copy_to + analyzer."""
        schema = {
            "settings": {
                "analysis": {
                    "analyzer": {
                        "custom_analyzer": {"type": "standard", "stopwords": "_english_"},
                    }
                }
            },
            "field_types": {
                "string": {"type": "text"},
            },
            "indexing_rules": {
                "content": {
                    "field_type": "string",
                    "boost": 1.5,
                    "copy_to": ["all_text"],
                    "analyzer": "custom_analyzer",
                },
            },
        }

        schema_file = tmp_path / "multiple_overrides.json"
        with Path(schema_file).open("w") as f:
            json.dump(schema, f)

        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            schema_template_path=str(schema_file),
            available_features={
                "content": {"type": "string", "available_for_vector_db": True},
            },
        )

        dimension_mapping = {"embeddings": 384}
        index_body = manager.build_index_body(dimension_mapping=dimension_mapping)

        # Verify all overrides are applied correctly
        content_field = index_body["mappings"]["properties"]["content"]
        assert content_field["type"] == "text"
        assert content_field["boost"] == 1.5
        assert content_field["copy_to"] == ["all_text"]
        assert content_field["analyzer"] == "custom_analyzer"

    def test_indexing_rules_priority_feature_name_over_mapped_name(self, *, mock_client, tmp_path):
        """Test that feature_name takes priority over mapped_name in indexing_rules lookup."""
        schema = {
            "field_types": {
                "high_priority": {"type": "text", "boost": 3.0},
                "low_priority": {"type": "text", "boost": 1.0},
            },
            "indexing_rules": {
                "content": {"field_type": "high_priority"},  # Feature name rule
                "document_content": {"field_type": "low_priority"},  # Mapped name rule
            },
        }

        schema_file = tmp_path / "priority_test.json"
        with Path(schema_file).open("w") as f:
            json.dump(schema, f)

        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            schema_template_path=str(schema_file),
            available_features={
                "content": {"type": "string", "available_for_vector_db": True},
            },
            feature_mappings=[{"feature_name": "content", "mapped_column_name": "document_content"}],
        )

        dimension_mapping = {"embeddings": 384}
        index_body = manager.build_index_body(dimension_mapping=dimension_mapping)

        # Verify feature_name rule takes priority (boost should be 3.0, not 1.0)
        assert "document_content" in index_body["mappings"]["properties"]
        assert index_body["mappings"]["properties"]["document_content"]["boost"] == 3.0

    def test_indexing_rules_fallback_to_mapped_name(self, *, mock_client, tmp_path):
        """Test fallback to mapped_name when feature_name not in indexing_rules."""
        schema = {
            "field_types": {
                "custom_text": {"type": "text", "boost": 2.0},
            },
            "indexing_rules": {
                "document_content": {"field_type": "custom_text"},  # Only mapped name rule
            },
        }

        schema_file = tmp_path / "fallback_test.json"
        with Path(schema_file).open("w") as f:
            json.dump(schema, f)

        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            schema_template_path=str(schema_file),
            available_features={
                "content": {"type": "string", "available_for_vector_db": True},
            },
            feature_mappings=[{"feature_name": "content", "mapped_column_name": "document_content"}],
        )

        dimension_mapping = {"embeddings": 384}
        index_body = manager.build_index_body(dimension_mapping=dimension_mapping)

        # Verify mapped_name rule is used
        assert "document_content" in index_body["mappings"]["properties"]
        assert index_body["mappings"]["properties"]["document_content"]["boost"] == 2.0

    def test_indexing_rules_fallback_to_system_type(self, *, mock_client, tmp_path):
        """Test fallback to system_type when no rule exists."""
        schema = {
            "field_types": {
                "string": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            },
            "indexing_rules": {},  # No rules
        }

        schema_file = tmp_path / "system_type_fallback.json"
        with Path(schema_file).open("w") as f:
            json.dump(schema, f)

        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            schema_template_path=str(schema_file),
            available_features={
                "content": {"type": "string", "available_for_vector_db": True},
            },
        )

        dimension_mapping = {"embeddings": 384}
        index_body = manager.build_index_body(dimension_mapping=dimension_mapping)

        # Verify system_type is used as fallback
        assert "content" in index_body["mappings"]["properties"]
        assert index_body["mappings"]["properties"]["content"]["type"] == "text"
        assert "keyword" in index_body["mappings"]["properties"]["content"]["fields"]

    def test_indexing_rules_invalid_field_type_logs_warning(self, *, mock_client, tmp_path):
        """Test that referencing non-existent field_type logs warning."""
        schema = {
            "field_types": {
                "string": {"type": "text"},
            },
            "indexing_rules": {
                "content": {"field_type": "nonexistent_type"},
            },
        }

        schema_file = tmp_path / "invalid_field_type.json"
        with Path(schema_file).open("w") as f:
            json.dump(schema, f)

        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            schema_template_path=str(schema_file),
            available_features={
                "content": {"type": "string", "available_for_vector_db": True},
            },
        )

        # Should raise DocpipeException for unknown field type
        with pytest.raises(DocpipeException) as exc_info:
            dimension_mapping: dict[str, int] = {}
            manager.build_index_body(dimension_mapping=dimension_mapping)

        # Verify error message contains helpful information
        assert "Unknown field type 'nonexistent_type'" in str(exc_info.value)
        assert "content" in str(exc_info.value)
        assert "Available field types" in str(exc_info.value)

    def test_indexing_rules_empty_analysis_block_removed(self, *, mock_client, tmp_path):
        """Test that empty analysis blocks are removed from settings."""
        schema = {
            "settings": {
                "index": {"knn": True},
                "analysis": {},  # Empty analysis block
            },
            "field_types": {
                "string": {"type": "text"},
            },
            "indexing_rules": {
                "content": {"field_type": "string"},
            },
        }

        schema_file = tmp_path / "empty_analysis.json"
        with Path(schema_file).open("w") as f:
            json.dump(schema, f)

        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            schema_template_path=str(schema_file),
            available_features={
                "content": {"type": "string", "available_for_vector_db": True},
            },
        )

        dimension_mapping = {"embeddings": 384}
        index_body = manager.build_index_body(dimension_mapping=dimension_mapping)

        # Verify empty analysis block is removed
        assert "analysis" not in index_body["settings"]

    def test_indexing_rules_with_nested_override_merge(self, *, mock_client, tmp_path):
        """Test deep merge of nested structures (e.g., fields.keyword)."""
        schema = {
            "field_types": {
                "string": {
                    "type": "text",
                    "fields": {
                        "keyword": {"type": "keyword", "ignore_above": 256},
                        "raw": {"type": "keyword"},
                    },
                },
            },
            "indexing_rules": {
                "content": {
                    "field_type": "string",
                    "fields": {
                        "keyword": {"ignore_above": 512},  # Override nested property
                    },
                },
            },
        }

        schema_file = tmp_path / "nested_merge.json"
        with Path(schema_file).open("w") as f:
            json.dump(schema, f)

        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            schema_template_path=str(schema_file),
            available_features={
                "content": {"type": "string", "available_for_vector_db": True},
            },
        )

        dimension_mapping = {"embeddings": 384}
        index_body = manager.build_index_body(dimension_mapping=dimension_mapping)

        # Verify nested properties are correctly merged
        content_fields = index_body["mappings"]["properties"]["content"]["fields"]
        assert content_fields["keyword"]["type"] == "keyword"
        assert content_fields["keyword"]["ignore_above"] == 512  # Overridden value
        assert "raw" in content_fields  # Original field preserved

    def test_indexing_rules_allowlist_enforcement(self, *, mock_client, tmp_path):
        """Test that only allowlisted properties are applied."""
        schema = {
            "field_types": {
                "string": {"type": "text"},
            },
            "indexing_rules": {
                "content": {
                    "field_type": "string",
                    "boost": 2.0,  # Allowlisted
                    "analyzer": "standard",  # Allowlisted
                    "custom_property": "should_be_ignored",  # Not allowlisted
                    "another_invalid": 123,  # Not allowlisted
                },
            },
        }

        schema_file = tmp_path / "allowlist_test.json"
        with Path(schema_file).open("w") as f:
            json.dump(schema, f)

        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            schema_template_path=str(schema_file),
            available_features={
                "content": {"type": "string", "available_for_vector_db": True},
            },
        )

        dimension_mapping = {"embeddings": 384}
        index_body = manager.build_index_body(dimension_mapping=dimension_mapping)

        # Verify only allowlisted properties are applied
        content_field = index_body["mappings"]["properties"]["content"]
        assert content_field["boost"] == 2.0
        assert content_field["analyzer"] == "standard"
        assert "custom_property" not in content_field
        assert "another_invalid" not in content_field

    def test_indexing_rules_dict_format_required(self, *, mock_client, tmp_path):
        """Test that indexing_rules requires dict format with 'field_type' key."""
        schema = {
            "field_types": {
                "content_text": {"type": "text", "analyzer": "standard"},
                "string": {"type": "text"},
            },
            "indexing_rules": {
                "content": {"field_type": "content_text"},  # Dict format required
            },
        }

        schema_file = tmp_path / "dict_format.json"
        with Path(schema_file).open("w") as f:
            json.dump(schema, f)

        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            schema_template_path=str(schema_file),
            available_features={
                "content": {"type": "string", "available_for_vector_db": True},
            },
        )

        dimension_mapping = {"embeddings": 384}
        index_body = manager.build_index_body(dimension_mapping=dimension_mapping)

        # Verify dict format with field_type works correctly
        assert "content" in index_body["mappings"]["properties"]
        assert index_body["mappings"]["properties"]["content"]["type"] == "text"
        assert index_body["mappings"]["properties"]["content"]["analyzer"] == "standard"
