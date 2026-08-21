"""Unit tests for OpenSearchIndexManager."""

from unittest.mock import MagicMock

import numpy as np
import pyarrow as pa
import pytest

from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.vectordb.adapters.outbound.opensearch.index_manager import (
    OpenSearchIndexManager,
)
from docpipe.exceptions.docpipe_exceptions import DocpipeException


@pytest.fixture
def mock_client():
    """Mock OpenSearch client"""
    client = MagicMock()
    client.indices.exists.return_value = False
    return client


@pytest.fixture
def basic_features():
    """Basic feature configuration"""
    return {
        "doc_id": {
            "name": "Document ID",
            "available_for_vector_db": True,
            "type": "string",
            "is_primary": True,
        },
        "content": {
            "name": "Content",
            "available_for_vector_db": True,
            "type": "string",
        },
        "embeddings": {
            "name": "Embeddings",
            "available_for_vector_db": True,
            "type": "vector",
        },
    }


@pytest.fixture
def feature_mappings():
    """Feature mappings"""
    return [
        {"feature_name": "doc_id", "mapped_column_name": "pk"},
        {"feature_name": "content", "mapped_column_name": "text"},
        {"feature_name": "embeddings", "mapped_column_name": "vector_embeddings"},
    ]


class TestIndexManagerInitialization:
    """Test index manager initialization"""

    def test_basic_initialization(self, mock_client):
        """Test basic initialization with default parameters"""
        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
        )

        assert manager.client == mock_client
        assert manager.index_name == "test_index"
        assert manager.engine == "faiss"
        assert manager.algorithm == "hnsw"
        assert manager.space_type == "l2"

    def test_initialization_with_custom_parameters(self, mock_client):
        """Test initialization with custom parameters"""
        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="custom_index",
            engine="lucene",
            algorithm="hnsw",
            space_type="cosine",
        )

        assert manager.index_name == "custom_index"
        assert manager.engine == "lucene"
        assert manager.algorithm == "hnsw"
        assert manager.space_type == "cosine"

    def test_initialization_with_features(self, mock_client, basic_features, feature_mappings):
        """Test initialization with feature configuration"""
        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            available_features=basic_features,
            feature_mappings=feature_mappings,
        )

        assert manager.available_features == basic_features
        assert manager.feature_mappings == feature_mappings


class TestEngineAlgorithmValidation:
    """Test engine and algorithm validation"""

    def test_invalid_engine_raises_error(self, mock_client):
        """Test that invalid engine raises DocpipeException"""
        with pytest.raises(DocpipeException, match="Invalid engine"):
            OpenSearchIndexManager(
                client=mock_client,
                index_name="test_index",
                engine="invalid_engine",
            )

    def test_invalid_algorithm_raises_error(self, mock_client):
        """Test that invalid algorithm raises DocpipeException"""
        with pytest.raises(DocpipeException, match="Invalid algorithm"):
            OpenSearchIndexManager(
                client=mock_client,
                index_name="test_index",
                algorithm="invalid_algorithm",
            )

    def test_faiss_hnsw_compatibility(self, mock_client):
        """Test FAISS with HNSW is valid"""
        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            engine="faiss",
            algorithm="hnsw",
        )
        assert manager.engine == "faiss"
        assert manager.algorithm == "hnsw"

    def test_faiss_ivf_compatibility(self, mock_client):
        """Test FAISS with IVF is valid"""
        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            engine="faiss",
            algorithm="ivf",
        )
        assert manager.engine == "faiss"
        assert manager.algorithm == "ivf"

    def test_lucene_hnsw_compatibility(self, mock_client):
        """Test Lucene with HNSW is valid"""
        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            engine="lucene",
            algorithm="hnsw",
        )
        assert manager.engine == "lucene"
        assert manager.algorithm == "hnsw"

    def test_lucene_ivf_incompatibility(self, mock_client):
        """Test Lucene with IVF is invalid"""
        with pytest.raises(DocpipeException, match="not supported by engine"):
            OpenSearchIndexManager(
                client=mock_client,
                index_name="test_index",
                engine="lucene",
                algorithm="ivf",
            )

    def test_nmslib_hnsw_compatibility(self, mock_client):
        """Test NMSLIB with HNSW is valid"""
        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            engine="nmslib",
            algorithm="hnsw",
        )
        assert manager.engine == "nmslib"
        assert manager.algorithm == "hnsw"

    def test_jvector_hnsw_compatibility(self, mock_client):
        """Test JVector with HNSW is valid"""
        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            engine="jvector",
            algorithm="hnsw",
        )
        assert manager.engine == "jvector"
        assert manager.algorithm == "hnsw"


class TestEngineParameters:
    """Test engine parameter management"""

    def test_faiss_hnsw_default_parameters(self, mock_client):
        """Test FAISS HNSW default parameters"""
        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            engine="faiss",
            algorithm="hnsw",
        )

        params = manager._get_engine_parameters()
        assert "ef_construction" in params
        assert "m" in params
        assert params["ef_construction"] == 128
        assert params["m"] == 24

    def test_faiss_ivf_default_parameters(self, mock_client):
        """Test FAISS IVF default parameters"""
        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            engine="faiss",
            algorithm="ivf",
        )

        params = manager._get_engine_parameters()
        assert "nlist" in params
        assert "nprobe" in params
        assert params["nlist"] == 128
        assert params["nprobe"] == 8

    def test_lucene_hnsw_default_parameters(self, mock_client):
        """Test Lucene HNSW default parameters"""
        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            engine="lucene",
            algorithm="hnsw",
        )

        params = manager._get_engine_parameters()
        assert "ef_construction" in params
        assert "m" in params
        assert params["ef_construction"] == 128
        assert params["m"] == 16

    def test_custom_parameters_override_defaults(self, mock_client):
        """Test custom parameters override defaults"""
        custom_params = {"ef_construction": 256, "m": 32}
        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            engine="faiss",
            algorithm="hnsw",
            engine_parameters=custom_params,
        )

        params = manager._get_engine_parameters()
        assert params["ef_construction"] == 256
        assert params["m"] == 32

    def test_partial_custom_parameters_merge(self, mock_client):
        """Test partial custom parameters merge with defaults"""
        custom_params = {"ef_construction": 256}
        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            engine="faiss",
            algorithm="hnsw",
            engine_parameters=custom_params,
        )

        params = manager._get_engine_parameters()
        assert params["ef_construction"] == 256
        assert params["m"] == 24  # Default value


class TestDimensionDetection:
    """Test vector dimension detection"""

    def test_detect_dimension_from_flat_embeddings(self, mock_client):
        """Test dimension detection from flat embeddings using shared utility"""
        from docpipe.utils.operators.vectordb_utils import detect_vector_dimension

        # Create table with flat embeddings
        data = {
            "doc_id": ["doc1", "doc2"],
            "embeddings": [
                np.random.rand(384).tolist(),
                np.random.rand(384).tolist(),
            ],
        }
        table = pa.table(data)

        dimension = detect_vector_dimension(table=table, embeddings_column="embeddings")
        assert dimension == 384

    def test_detect_dimension_from_chunked_embeddings(self, mock_client):
        """Test dimension detection from chunked embeddings using shared utility"""
        from docpipe.utils.operators.vectordb_utils import detect_vector_dimension

        # Create table with chunked embeddings
        data = {
            "doc_id": ["doc1", "doc2"],
            "embeddings": [
                [np.random.rand(384).tolist(), np.random.rand(384).tolist()],
                [np.random.rand(384).tolist()],
            ],
        }
        table = pa.table(data)

        dimension = detect_vector_dimension(table=table, embeddings_column="embeddings")
        assert dimension == 384

    def test_detect_dimension_empty_table(self, mock_client):
        """Test dimension detection with empty table using shared utility"""
        from docpipe.utils.operators.vectordb_utils import detect_vector_dimension

        empty_table = pa.table({"doc_id": [], "embeddings": []})

        dimension = detect_vector_dimension(table=empty_table, embeddings_column="embeddings")
        assert dimension is None

    def test_detect_dimension_missing_column(self, mock_client):
        """Test dimension detection with missing embeddings column using shared utility"""
        from docpipe.utils.operators.vectordb_utils import detect_vector_dimension

        table = pa.table({"doc_id": ["doc1"], "content": ["test"]})

        dimension = detect_vector_dimension(table=table, embeddings_column="embeddings")
        assert dimension is None

    def test_detect_dimension_with_none_values(self, mock_client):
        """Test dimension detection skips None values using shared utility"""
        from docpipe.utils.operators.vectordb_utils import detect_vector_dimension

        data = {
            "doc_id": ["doc1", "doc2", "doc3"],
            "embeddings": [None, None, np.random.rand(384).tolist()],
        }
        table = pa.table(data)

        dimension = detect_vector_dimension(table=table, embeddings_column="embeddings")
        assert dimension == 384

    def test_detect_dimension_with_empty_lists(self, mock_client):
        """Test dimension detection skips empty lists using shared utility"""
        from docpipe.utils.operators.vectordb_utils import detect_vector_dimension

        data = {
            "doc_id": ["doc1", "doc2"],
            "embeddings": [[], np.random.rand(384).tolist()],
        }
        table = pa.table(data)

        dimension = detect_vector_dimension(table=table, embeddings_column="embeddings")
        assert dimension == 384

    def test_detect_dimension_malformed_data(self, mock_client):
        """Test dimension detection with malformed data using shared utility"""
        from docpipe.utils.operators.vectordb_utils import detect_vector_dimension

        # Non-list value
        data = {"doc_id": ["doc1"], "embeddings": ["not a list"]}
        table = pa.table(data)

        dimension = detect_vector_dimension(table=table, embeddings_column="embeddings")
        assert dimension is None

    def test_detect_dimension_with_different_dimensions(self, mock_client):
        """Test dimension detection uses first valid embedding using shared utility"""
        from docpipe.utils.operators.vectordb_utils import detect_vector_dimension

        # All embeddings have same dimension - should detect 384
        data = {
            "doc_id": ["doc1", "doc2", "doc3"],
            "embeddings": [
                np.random.rand(384).tolist(),
                np.random.rand(384).tolist(),
                np.random.rand(384).tolist(),
            ],
        }
        table = pa.table(data)

        dimension = detect_vector_dimension(table=table, embeddings_column="embeddings")
        assert dimension == 384


class TestIndexMapping:
    """Test index mapping creation"""

    def test_create_basic_mapping(self, mock_client, basic_features, feature_mappings):
        """Test creating basic index mapping"""
        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            available_features=basic_features,
            feature_mappings=feature_mappings,
        )

        dimension_mapping = {"embeddings": 384, "vector_embeddings": 384}
        mapping = manager.build_index_body(dimension_mapping=dimension_mapping)

        assert "mappings" in mapping
        assert "properties" in mapping["mappings"]

    def test_mapping_vector_field(self, mock_client, basic_features, feature_mappings):
        """Test vector field in mapping"""
        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            engine="faiss",
            algorithm="hnsw",
            available_features=basic_features,
            feature_mappings=feature_mappings,
        )

        dimension_mapping = {"embeddings": 384, "vector_embeddings": 384}
        mapping = manager.build_index_body(dimension_mapping=dimension_mapping)
        properties = mapping["mappings"]["properties"]

        assert "vector_embeddings" in properties
        assert properties["vector_embeddings"]["type"] == "knn_vector"
        assert properties["vector_embeddings"]["dimension"] == 384
        assert properties["vector_embeddings"]["method"]["name"] == "hnsw"
        assert properties["vector_embeddings"]["method"]["engine"] == "faiss"

    def test_mapping_string_field(self, mock_client, basic_features, feature_mappings):
        """Test string field in mapping"""
        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            available_features=basic_features,
            feature_mappings=feature_mappings,
        )

        dimension_mapping = {"embeddings": 384}
        mapping = manager.build_index_body(dimension_mapping=dimension_mapping)
        properties = mapping["mappings"]["properties"]

        assert "text" in properties
        assert properties["text"]["type"] == "text"

    def test_mapping_metadata(self, mock_client, basic_features, feature_mappings):
        """Test metadata in mapping - now in settings"""
        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            engine="lucene",
            algorithm="hnsw",
            space_type="cosine",
            available_features=basic_features,
            feature_mappings=feature_mappings,
        )

        dimension_mapping = {"embeddings": 384}
        mapping = manager.build_index_body(dimension_mapping=dimension_mapping)

        # Metadata is now stored in settings, not mappings._meta
        assert "settings" in mapping
        assert "mappings" in mapping

    def test_mapping_different_feature_types(self, mock_client):
        """Test mapping with different feature types"""
        features = {
            "text_field": {"available_for_vector_db": True, "type": "string"},
            "int_field": {"available_for_vector_db": True, "type": "int64"},
            "float_field": {"available_for_vector_db": True, "type": "float"},
            "bool_field": {"available_for_vector_db": True, "type": "boolean"},
            "object_field": {"available_for_vector_db": True, "type": "object"},
            "json_field": {"available_for_vector_db": True, "type": "json"},
            "nested_field": {"available_for_vector_db": True, "type": "nested"},
        }

        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            available_features=features,
        )

        dimension_mapping: dict[str, int] = {}
        mapping = manager.build_index_body(dimension_mapping=dimension_mapping)
        properties = mapping["mappings"]["properties"]

        assert properties["text_field"]["type"] == "text"
        assert properties["int_field"]["type"] == "long"
        assert properties["float_field"]["type"] == "float"
        assert properties["bool_field"]["type"] == "boolean"
        assert properties["object_field"]["type"] == "object"
        assert properties["json_field"]["type"] == "object"
        assert properties["nested_field"]["type"] == "nested"

    def test_mapping_excludes_unavailable_features(self, mock_client):
        """Test mapping excludes features not available for vector db"""
        features = {
            "included": {"available_for_vector_db": True, "type": "string"},
            "excluded": {"available_for_vector_db": False, "type": "string"},
        }

        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            available_features=features,
        )

        dimension_mapping: dict[str, int] = {}
        mapping = manager.build_index_body(dimension_mapping=dimension_mapping)
        properties = mapping["mappings"]["properties"]

        assert "included" in properties
        assert "excluded" not in properties


class TestIndexCreation:
    """Test index creation"""

    def test_create_index_when_not_exists(self, mock_client, basic_features, feature_mappings):
        """Test creating index when it doesn't exist"""
        mock_client.indices.exists.return_value = False

        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            available_features=basic_features,
            feature_mappings=feature_mappings,
        )

        dimension_mapping = {"embeddings": 384}
        manager.create_index(dimension_mapping=dimension_mapping)

        mock_client.indices.create.assert_called_once()
        call_args = mock_client.indices.create.call_args
        assert call_args[1]["index"] == "test_index"
        assert "body" in call_args[1]

    def test_create_index_with_custom_settings(self, mock_client):
        """Test creating index with custom settings"""
        mock_client.indices.exists.return_value = False
        custom_settings = {
            "index": {
                "number_of_shards": 5,
                "number_of_replicas": 2,
            }
        }

        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            index_settings=custom_settings,
        )

        dimension_mapping: dict[str, int] = {}
        manager.create_index(dimension_mapping=dimension_mapping)

        call_args = mock_client.indices.create.call_args
        body = call_args[1]["body"]
        assert body["settings"]["index"]["number_of_shards"] == 5
        assert body["settings"]["index"]["number_of_replicas"] == 2

    def test_create_index_with_default_settings(self, mock_client):
        """Test creating index with default KNN settings"""
        mock_client.indices.exists.return_value = False

        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
        )

        dimension_mapping: dict[str, int] = {}
        manager.create_index(dimension_mapping=dimension_mapping)

        call_args = mock_client.indices.create.call_args
        body = call_args[1]["body"]
        assert "settings" in body
        assert body["settings"]["index"]["knn"] is True

    def test_create_index_when_exists(self, mock_client):
        """Test creating index when it already exists"""
        mock_client.indices.exists.return_value = True

        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
        )

        dimension_mapping: dict[str, int] = {}
        manager.create_index(dimension_mapping=dimension_mapping)

        mock_client.indices.create.assert_not_called()


class TestIndexValidation:
    """Test index validation"""

    def test_validate_existing_index_matching(self, mock_client):
        """Test validation with matching configuration"""
        mock_client.indices.exists.return_value = True
        mock_client.indices.get_mapping.return_value = {
            "test_index": {
                "mappings": {
                    "_meta": {
                        "engine": "faiss",
                        "algorithm": "hnsw",
                    },
                    "properties": {
                        "embeddings": {
                            "type": "knn_vector",
                            "dimension": 384,
                        }
                    },
                }
            }
        }

        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            engine="faiss",
            algorithm="hnsw",
        )

        manager.validate_existing_index(dimension_mapping={"embeddings": 384})

    def test_validate_existing_index_engine_mismatch(self, mock_client):
        """Test validation with engine mismatch"""
        mock_client.indices.get_mapping.return_value = {
            "test_index": {
                "mappings": {
                    "_meta": {
                        "engine": "lucene",
                        "algorithm": "hnsw",
                    },
                    "properties": {
                        "embeddings": {
                            "type": "knn_vector",
                            "dimension": 384,
                        }
                    },
                }
            }
        }

        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            engine="faiss",
            algorithm="hnsw",
        )

        manager.validate_existing_index(dimension_mapping={"embeddings": 384})

    def test_validate_existing_index_dimension_mismatch(self, mock_client):
        """Test validation fails on dimension mismatch."""
        mock_client.indices.get_mapping.return_value = {
            "test_index": {
                "mappings": {
                    "_meta": {
                        "engine": "faiss",
                        "algorithm": "hnsw",
                    },
                    "properties": {
                        "embeddings": {
                            "type": "knn_vector",
                            "dimension": 768,
                        }
                    },
                }
            }
        }

        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            engine="faiss",
            algorithm="hnsw",
        )

        with pytest.raises(DocpipeException, match="existing dimension 768 but current run produced 384"):
            manager.validate_existing_index(dimension_mapping={"embeddings": 384})

    def test_validate_existing_index_no_metadata(self, mock_client):
        """Test validation when index has no metadata"""
        mock_client.indices.get_mapping.return_value = {
            "test_index": {
                "mappings": {
                    "properties": {
                        "embeddings": {
                            "type": "knn_vector",
                            "dimension": 384,
                        }
                    }
                }
            }
        }

        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
        )

        manager.validate_existing_index(dimension_mapping={"embeddings": 384})

    def test_validate_existing_index_error(self, mock_client):
        """Test validation handles errors gracefully"""
        mock_client.indices.get_mapping.side_effect = Exception("API error")

        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
        )

        manager.validate_existing_index(dimension_mapping={"embeddings": 384})


class TestIndexOperations:
    """Test index operations"""

    def test_index_exists_true(self, mock_client):
        """Test index_exists returns True when index exists"""
        mock_client.indices.exists.return_value = True

        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
        )

        assert manager.index_exists() is True

    def test_index_exists_false(self, mock_client):
        """Test index_exists returns False when index doesn't exist"""
        mock_client.indices.exists.return_value = False

        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
        )

        assert manager.index_exists() is False

    def test_index_exists_error(self, mock_client):
        """Test index_exists handles errors"""
        mock_client.indices.exists.side_effect = Exception("API error")

        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
        )

        assert manager.index_exists() is False

    def test_delete_index_success(self, mock_client):
        """Test successful index deletion"""
        mock_client.indices.exists.return_value = True

        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
        )

        result = manager.delete_index()

        assert result is True
        mock_client.indices.delete.assert_called_once_with(index="test_index")

    def test_delete_index_not_exists(self, mock_client):
        """Test deleting non-existent index"""
        mock_client.indices.exists.return_value = False

        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
        )

        result = manager.delete_index()

        assert result is False
        mock_client.indices.delete.assert_not_called()

    def test_delete_index_error(self, mock_client):
        """Test delete index handles errors"""
        mock_client.indices.exists.return_value = True
        mock_client.indices.delete.side_effect = Exception("Delete error")

        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
        )

        result = manager.delete_index()

        assert result is False

    def test_refresh_index_success(self, mock_client):
        """Test successful index refresh"""
        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
        )

        manager.refresh_index()

        mock_client.indices.refresh.assert_called_once_with(index="test_index")

    def test_refresh_index_error(self, mock_client):
        """Test refresh index handles errors"""
        mock_client.indices.refresh.side_effect = Exception("Refresh error")

        manager = OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
        )

        # Should not raise exception
        manager.refresh_index()


class TestUpdateFeatureMappingsInIndex:
    """update_feature_mappings_in_index() writes _meta.feature_mappings via put_mapping."""

    def _manager(self, *, mock_client: MagicMock, feature_mappings: list | None = None) -> OpenSearchIndexManager:
        return OpenSearchIndexManager(
            mock_client,
            index_name="test_index",
            feature_mappings=feature_mappings,
        )

    def test_calls_put_mapping_with_correct_body(self, mock_client):
        mappings = [
            {"feature_name": "doc_id_hash", "mapped_column_name": "pk"},
            {"feature_name": "embeddings", "mapped_column_name": "vector_embeddings"},
        ]
        manager = self._manager(mock_client=mock_client, feature_mappings=mappings)
        manager.update_feature_mappings_in_index()

        mock_client.indices.put_mapping.assert_called_once_with(
            index="test_index",
            body={OperatorConstants.VectorDB.SCHEMA_KEY_META: {"feature_mappings": mappings}},
        )

    def test_skips_put_mapping_when_feature_mappings_empty(self, mock_client):
        manager = self._manager(mock_client=mock_client, feature_mappings=[])
        manager.update_feature_mappings_in_index()
        mock_client.indices.put_mapping.assert_not_called()

    def test_skips_put_mapping_when_feature_mappings_is_none(self, mock_client):
        manager = self._manager(mock_client=mock_client, feature_mappings=None)
        manager.update_feature_mappings_in_index()
        mock_client.indices.put_mapping.assert_not_called()

    def test_does_not_raise_on_put_mapping_exception(self, mock_client):
        """put_mapping failure must be swallowed (logged as warning) — never raise."""
        mock_client.indices.put_mapping.side_effect = Exception("connection refused")
        manager = self._manager(
            mock_client=mock_client, feature_mappings=[{"feature_name": "feat", "mapped_column_name": "col"}]
        )
        manager.update_feature_mappings_in_index()  # must not raise

    def test_create_index_calls_update_on_new_index(self, mock_client):
        """create_index() calls update_feature_mappings_in_index() after creating a new index."""
        mock_client.indices.exists.return_value = False
        mock_client.indices.create.return_value = {}

        manager = self._manager(
            mock_client=mock_client,
            feature_mappings=[{"feature_name": "doc_id_hash", "mapped_column_name": "pk"}],
        )
        manager.update_feature_mappings_in_index = MagicMock()
        manager.create_index(dimension_mapping={})

        manager.update_feature_mappings_in_index.assert_called()

    def test_create_index_calls_update_on_existing_index(self, mock_client):
        """create_index() calls update_feature_mappings_in_index() for an already-existing index."""
        mock_client.indices.exists.return_value = True
        mock_client.indices.get_mapping.return_value = {
            "test_index": {
                "mappings": {
                    "_meta": {"engine": "faiss", "algorithm": "hnsw"},
                    "properties": {"vector_embeddings": {"type": "knn_vector", "dimension": 384}},
                }
            }
        }

        manager = self._manager(
            mock_client=mock_client,
            feature_mappings=[{"feature_name": "doc_id_hash", "mapped_column_name": "pk"}],
        )
        manager.update_feature_mappings_in_index = MagicMock()
        manager.create_index(dimension_mapping={"vector_embeddings": 384})

        manager.update_feature_mappings_in_index.assert_called()


class TestOpenSearchConfig:
    """Tests for OpenSearchConfig — Literal constraints, defaults, JSON schema."""

    def setup_method(self):
        from docpipe.core.operators.vectordb.adapters.outbound.opensearch.config import OpenSearchConfig

        self.Config = OpenSearchConfig

    # --- defaults ---

    def test_defaults(self):
        cfg = self.Config(index_name="my-index")
        assert cfg.host == "localhost"
        assert cfg.port == 9200
        assert cfg.engine == "faiss"
        assert cfg.algorithm == "hnsw"
        assert cfg.space_type == "l2"
        assert cfg.batch_size == 100
        assert cfg.use_ssl is True
        assert cfg.verify_certs is True
        assert cfg.aws_auth is False
        assert cfg.engine_parameters is None
        assert cfg.index_settings is None
        assert cfg.schema_template_path is None

    # --- index_name required ---

    def test_missing_index_name_raises(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            self.Config()

    # --- Literal: engine ---

    @pytest.mark.parametrize("value", ["faiss", "lucene", "nmslib", "jvector"])
    def test_engine_valid(self, value):
        cfg = self.Config(index_name="idx", engine=value)
        assert cfg.engine == value

    def test_engine_invalid_raises(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            self.Config(index_name="idx", engine="annoy")

    # --- Literal: algorithm ---

    @pytest.mark.parametrize("value", ["hnsw", "ivf"])
    def test_algorithm_valid(self, value):
        cfg = self.Config(index_name="idx", algorithm=value)
        assert cfg.algorithm == value

    def test_algorithm_invalid_raises(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            self.Config(index_name="idx", algorithm="flat")

    # --- Literal: space_type ---

    @pytest.mark.parametrize("value", ["l2", "cosine", "inner_product"])
    def test_space_type_valid(self, value):
        cfg = self.Config(index_name="idx", space_type=value)
        assert cfg.space_type == value

    def test_space_type_innerproduct_typo_rejected(self):
        """Regression: old description said 'innerproduct' — correct value is 'inner_product'."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            self.Config(index_name="idx", space_type="innerproduct")

    def test_space_type_invalid_raises(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            self.Config(index_name="idx", space_type="dot_product")

    # --- extra fields ignored ---

    def test_extra_fields_ignored(self):
        cfg = self.Config(index_name="idx", unknown_field="value")
        assert not hasattr(cfg, "unknown_field")

    # --- valid_values surfaces in JSON schema ---

    def test_engine_enum_in_json_schema(self):
        schema = self.Config.model_json_schema()
        assert "enum" in schema["properties"]["engine"]

    def test_algorithm_enum_in_json_schema(self):
        schema = self.Config.model_json_schema()
        assert "enum" in schema["properties"]["algorithm"]

    def test_space_type_enum_in_json_schema(self):
        schema = self.Config.model_json_schema()
        assert "enum" in schema["properties"]["space_type"]

    def test_enum_values_match_index_manager_constants(self):
        """Config Literal values must match the runtime allowlists in index_manager.py."""
        from docpipe.core.operators.vectordb.adapters.outbound.opensearch.index_manager import (
            OpenSearchEngineTypes,
            VectorSimilarityTypes,
        )

        schema = self.Config.model_json_schema()
        assert set(schema["properties"]["engine"]["enum"]) == set(OpenSearchEngineTypes.ALL_ENGINES)
        assert set(schema["properties"]["space_type"]["enum"]) == set(VectorSimilarityTypes.ALL_TYPES)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
