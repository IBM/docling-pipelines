#!/usr/bin/env python3
"""
Unit tests for OpenSearch operator
"""

import pytest
import pyarrow as pa
import numpy as np
from unittest.mock import Mock, MagicMock, patch
from core.operators.universal.vectordb.opensearch_operator import (
    OpenSearchOperator,
    OpenSearchEngineTypes,
    OpenSearchAlgorithmTypes,
    VectorSimilarityTypes,
    ENGINE_KEY,
    ALGORITHM_KEY,
    SPACE_TYPE_KEY,
    ENGINE_PARAMETERS_KEY,
    SPARSE_EMBEDDINGS_COLUMN_KEY,
)
from common.util.constants import OperatorConstants
from common.util.env_config import get_opensearch_config


@pytest.fixture
def basic_config():
    """Basic configuration for OpenSearch operator - uses environment variables with test overrides"""
    # Get config from environment variables
    env_config = get_opensearch_config()

    # Override with test-specific values
    config = {
        **env_config,
        OperatorConstants.INDEX_NAME: "test_index",  # Use test index name
        OperatorConstants.CREATE_INDEX: True,
        OperatorConstants.AVAILABLE_FEATURES: {
            "doc_id_hash": {
                "name": "Document ID",
                "available_for_vector_db": True,
                "mandatory_for_vector_db": True,
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
                "mandatory_for_vector_db": True,
                "type": "vector",
            },
        },
        OperatorConstants.FEATURE_MAPPINGS: {
            "doc_id_hash": "pk",
            "content": "text",
            "embeddings": "vector_embeddings",
        },
    }
    return config


@pytest.fixture
def sample_table():
    """Sample PyArrow table with documents"""
    data = {
        "doc_id_hash": ["doc1", "doc2", "doc3"],
        "content": [
            "This is the first document",
            "This is the second document",
            "This is the third document",
        ],
        "embeddings": [
            np.random.rand(384).tolist(),
            np.random.rand(384).tolist(),
            np.random.rand(384).tolist(),
        ],
    }
    return pa.table(data)


class TestOpenSearchOperatorInitialization:
    """Test operator initialization and configuration"""

    def test_basic_initialization(self, basic_config):
        """Test basic operator initialization"""
        with patch(
            "core.operators.universal.vectordb.opensearch_operator.OpenSearch"
        ):
            operator = OpenSearchOperator(basic_config)
            assert operator.host == "localhost"
            assert operator.port == 9200
            assert operator.index_name == "test_index"
            assert operator.engine == "faiss"
            assert operator.algorithm == "hnsw"

    def test_missing_required_host(self, basic_config):
        """Test that missing host raises error"""
        config = basic_config.copy()
        del config[OperatorConstants.OPENSEARCH_HOST]

        with pytest.raises(ValueError, match="opensearch_host is required"):
            OpenSearchOperator(config)

    def test_missing_required_index_name(self, basic_config):
        """Test that missing index name raises error"""
        config = basic_config.copy()
        del config[OperatorConstants.INDEX_NAME]

        with pytest.raises(ValueError, match="index_name is required"):
            OpenSearchOperator(config)

    def test_invalid_engine(self, basic_config):
        """Test that invalid engine raises error"""
        config = basic_config.copy()
        config[ENGINE_KEY] = "invalid_engine"

        with pytest.raises(ValueError, match="Invalid engine"):
            OpenSearchOperator(config)

    def test_invalid_algorithm(self, basic_config):
        """Test that invalid algorithm raises error"""
        config = basic_config.copy()
        config[ALGORITHM_KEY] = "invalid_algorithm"

        with pytest.raises(ValueError, match="Invalid algorithm"):
            OpenSearchOperator(config)

    def test_incompatible_engine_algorithm(self, basic_config):
        """Test that incompatible engine-algorithm combination raises error"""
        config = basic_config.copy()
        config[ENGINE_KEY] = "lucene"
        config[ALGORITHM_KEY] = "ivf"  # Lucene doesn't support IVF

        with pytest.raises(ValueError, match="not supported by engine"):
            OpenSearchOperator(config)


class TestEngineConfiguration:
    """Test engine and algorithm configuration"""

    def test_faiss_hnsw_configuration(self, basic_config):
        """Test FAISS with HNSW configuration"""
        config = basic_config.copy()
        config[ENGINE_KEY] = "faiss"
        config[ALGORITHM_KEY] = "hnsw"

        with patch(
            "core.operators.universal.vectordb.opensearch_operator.OpenSearch"
        ):
            operator = OpenSearchOperator(config)
            params = operator._get_engine_parameters()
            assert "ef_construction" in params
            assert "m" in params

    def test_faiss_ivf_configuration(self, basic_config):
        """Test FAISS with IVF configuration"""
        config = basic_config.copy()
        config[ENGINE_KEY] = "faiss"
        config[ALGORITHM_KEY] = "ivf"

        with patch(
            "core.operators.universal.vectordb.opensearch_operator.OpenSearch"
        ):
            operator = OpenSearchOperator(config)
            params = operator._get_engine_parameters()
            assert "nlist" in params
            assert "nprobe" in params

    def test_custom_engine_parameters(self, basic_config):
        """Test custom engine parameters override defaults"""
        config = basic_config.copy()
        config[ENGINE_PARAMETERS_KEY] = {"ef_construction": 256, "m": 32}

        with patch(
            "core.operators.universal.vectordb.opensearch_operator.OpenSearch"
        ):
            operator = OpenSearchOperator(config)
            params = operator._get_engine_parameters()
            assert params["ef_construction"] == 256
            assert params["m"] == 32


class TestIndexManagement:
    """Test index creation and management"""

    @patch(
        "core.operators.universal.vectordb.opensearch_operator.OpenSearch"
    )
    def test_create_index_mapping(self, mock_opensearch, basic_config):
        """Test index mapping creation"""
        operator = OpenSearchOperator(basic_config)
        mapping = operator._create_index_mapping()

        assert "mappings" in mapping
        assert "properties" in mapping["mappings"]
        assert "_meta" in mapping["mappings"]

        # Check vector field configuration
        properties = mapping["mappings"]["properties"]
        assert "vector_embeddings" in properties
        assert properties["vector_embeddings"]["type"] == "knn_vector"
        assert properties["vector_embeddings"]["dimension"] == 384

        # Check metadata
        meta = mapping["mappings"]["_meta"]
        assert meta["engine"] == "faiss"
        assert meta["algorithm"] == "hnsw"

    @patch(
        "core.operators.universal.vectordb.opensearch_operator.OpenSearch"
    )
    def test_index_creation(self, mock_opensearch, basic_config):
        """Test index creation"""
        mock_client = MagicMock()
        mock_client.indices.exists.return_value = False
        mock_opensearch.return_value = mock_client

        operator = OpenSearchOperator(basic_config)
        operator._create_index()

        # Verify index creation was called
        mock_client.indices.create.assert_called_once()
        call_args = mock_client.indices.create.call_args
        assert call_args[1]["index"] == "test_index"
        assert "body" in call_args[1]


class TestDocumentProcessing:
    """Test document preparation and processing"""

    @patch(
        "core.operators.universal.vectordb.opensearch_operator.OpenSearch"
    )
    def test_prepare_document(self, mock_opensearch, basic_config):
        """Test document preparation"""
        operator = OpenSearchOperator(basic_config)

        row_data = {
            "doc_id_hash": "doc1",
            "content": "Test content",
            "embeddings": [0.1, 0.2, 0.3],
        }

        doc = operator._prepare_document(row_data)

        # Check feature mappings are applied
        assert "pk" in doc  # doc_id_hash mapped to pk
        assert "text" in doc  # content mapped to text
        assert "vector_embeddings" in doc  # embeddings mapped to vector_embeddings
        assert doc["pk"] == "doc1"
        assert doc["text"] == "Test content"

    @patch(
        "core.operators.universal.vectordb.opensearch_operator.OpenSearch"
    )
    def test_prepare_document_with_none_values(self, mock_opensearch, basic_config):
        """Test document preparation with None values"""
        operator = OpenSearchOperator(basic_config)

        row_data = {
            "doc_id_hash": "doc1",
            "content": None,  # None value should be skipped
            "embeddings": [0.1, 0.2, 0.3],
        }

        doc = operator._prepare_document(row_data)

        assert "pk" in doc
        assert "text" not in doc  # None value should be excluded
        assert "vector_embeddings" in doc


class TestBatchProcessing:
    """Test batch processing functionality"""

    @patch(
        "core.operators.universal.vectordb.opensearch_operator.OpenSearch"
    )
    @patch(
        "core.operators.universal.vectordb.opensearch_operator.helpers.bulk"
    )
    def test_transform_basic(
        self, mock_bulk, mock_opensearch, basic_config, sample_table
    ):
        """Test basic transform operation"""
        # Setup mocks
        mock_client = MagicMock()
        mock_client.indices.exists.return_value = True
        mock_client.info.return_value = {"version": {"number": "2.11.0"}}
        mock_opensearch.return_value = mock_client
        mock_bulk.return_value = (3, [])  # 3 successful, 0 failed

        operator = OpenSearchOperator(basic_config)
        result_tables, metadata = operator.transform(sample_table)

        # Verify results
        assert len(result_tables) == 1
        assert result_tables[0].num_rows == 3
        assert metadata["total_docs_count"] == 3
        assert metadata["processed_docs"] == 3
        assert metadata["failed_docs_count"] == 0

    @patch(
        "core.operators.universal.vectordb.opensearch_operator.OpenSearch"
    )
    def test_transform_missing_doc_id_column(self, mock_opensearch, basic_config):
        """Test transform with missing doc_id column"""
        mock_client = MagicMock()
        mock_client.info.return_value = {"version": {"number": "2.11.0"}}
        mock_opensearch.return_value = mock_client

        # Create table without doc_id_hash column
        data = {"content": ["Test"], "embeddings": [[0.1, 0.2]]}
        table = pa.table(data)

        operator = OpenSearchOperator(basic_config)
        result_tables, metadata = operator.transform(table)

        assert metadata["node_status"] == "failed"

    @patch(
        "core.operators.universal.vectordb.opensearch_operator.OpenSearch"
    )
    def test_transform_empty_table(self, mock_opensearch, basic_config):
        """Test transform with empty table"""
        mock_client = MagicMock()
        mock_client.info.return_value = {"version": {"number": "2.11.0"}}
        mock_opensearch.return_value = mock_client

        empty_table = pa.table({"doc_id_hash": [], "content": [], "embeddings": []})

        operator = OpenSearchOperator(basic_config)
        result_tables, metadata = operator.transform(empty_table)

        assert metadata["total_docs_count"] == 0
        assert metadata["processed_docs"] == 0


class TestQueryCapabilities:
    """Test query and delete capabilities"""

    @patch(
        "core.operators.universal.vectordb.opensearch_operator.OpenSearch"
    )
    def test_query_by_doc_names(self, mock_opensearch, basic_config):
        """Test querying documents by names"""
        mock_client = MagicMock()
        mock_client.info.return_value = {"version": {"number": "2.11.0"}}
        mock_client.search.return_value = {
            "hits": {
                "hits": [
                    {"_source": {"name": "doc1", "content": "Test 1"}},
                    {"_source": {"name": "doc2", "content": "Test 2"}},
                ]
            }
        }
        mock_opensearch.return_value = mock_client

        operator = OpenSearchOperator(basic_config)
        docs = operator.query_by_doc_names(["doc1", "doc2"])

        assert len(docs) == 2
        assert docs[0]["name"] == "doc1"
        assert docs[1]["name"] == "doc2"

    @patch(
        "core.operators.universal.vectordb.opensearch_operator.OpenSearch"
    )
    @patch(
        "core.operators.universal.vectordb.opensearch_operator.helpers.bulk"
    )
    def test_delete_documents_by_ids(self, mock_bulk, mock_opensearch, basic_config):
        """Test deleting documents by IDs"""
        mock_client = MagicMock()
        mock_client.info.return_value = {"version": {"number": "2.11.0"}}
        mock_opensearch.return_value = mock_client
        mock_bulk.return_value = (2, [])  # 2 successful, 0 failed

        operator = OpenSearchOperator(basic_config)
        success, failed = operator.delete_documents_by_ids(["doc1", "doc2"])

        assert success == 2
        assert failed == 0

    @patch(
        "core.operators.universal.vectordb.opensearch_operator.OpenSearch"
    )
    def test_get_document_count(self, mock_opensearch, basic_config):
        """Test getting document count"""
        mock_client = MagicMock()
        mock_client.info.return_value = {"version": {"number": "2.11.0"}}
        mock_client.count.return_value = {"count": 100}
        mock_opensearch.return_value = mock_client

        operator = OpenSearchOperator(basic_config)
        count = operator.get_document_count()

        assert count == 100


class TestMetadata:
    """Test operator metadata"""

    def test_get_metadata(self):
        """Test get_metadata returns correct structure"""
        # Create a minimal config to instantiate the operator
        config = {
            "opensearch_host": "localhost",
            "opensearch_port": 9200,
            "index_name": "test_index",
            "doc_id_column": "doc_id_hash",
            "embeddings_column": "embeddings",
            "vector_dimension": 384,
            "engine": "faiss",
            "algorithm": "hnsw",
        }

        with patch(
            "core.operators.universal.vectordb.opensearch_operator.OpenSearch"
        ):
            operator = OpenSearchOperator(config)
            metadata = operator.get_metadata()

        assert metadata["sdk"] is True
        assert metadata["category"] == "vectordb"
        assert metadata["is_operator_available"] is True
        assert "features" in metadata
        assert "attributes" in metadata

        # Check features
        features = metadata["features"]
        assert "doc_id_hash" in features
        assert "embeddings" in features

        # Check attributes
        attributes = metadata["attributes"]
        assert "opensearch_host" in attributes
        assert "engine" in attributes
        assert "algorithm" in attributes


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

# Made with Bob
