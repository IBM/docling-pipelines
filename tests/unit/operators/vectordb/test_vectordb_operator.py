#!/usr/bin/env python3
"""
Unit tests for VectorDB operator with OpenSearch adapter
"""

from unittest.mock import MagicMock, Mock, patch

import numpy as np
import pyarrow as pa
import pytest

from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.vectordb import VectorDBOperator
from docpipe.exceptions.docpipe_exceptions import DocpipeException
from docpipe.utils.infrastructure.config import get_opensearch_config


@pytest.fixture
def basic_config():
    """Basic configuration for VectorDB operator with OpenSearch adapter"""
    env_config = get_opensearch_config()

    # The config structure now has all connection params in provider_config
    config = {
        OperatorConstants.Config.PROVIDER: "opensearch",
        OperatorConstants.VectorDB.INDEX_NAME: "test_index",
        OperatorConstants.VectorDB.CREATE_INDEX: True,
        OperatorConstants.Columns.DOC_ID_COLUMN: env_config.get(OperatorConstants.Columns.DOC_ID_COLUMN, "doc_id_hash"),
        OperatorConstants.Config.AVAILABLE_FEATURES: {
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
        OperatorConstants.Config.FEATURE_MAPPINGS: {
            "doc_id_hash": "pk",
            "content": "text",
            "embeddings": "vector_embeddings",
        },
        OperatorConstants.Config.PROVIDER_CONFIG: env_config.get(OperatorConstants.Config.PROVIDER_CONFIG, {}),
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


class TestVectorDBOperatorInitialization:
    """Test operator initialization and configuration"""

    def test_basic_initialization(self, basic_config):
        """Test basic operator initialization"""
        with patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.client.OpenSearch"):
            operator = VectorDBOperator(basic_config)
            assert operator.index_name == "test_index"
            assert operator.provider == "opensearch"
            assert operator.adapter is not None

    def test_missing_required_index_name(self, basic_config):
        """Test that missing index name raises error"""
        config = basic_config.copy()
        del config[OperatorConstants.VectorDB.INDEX_NAME]

        operator = VectorDBOperator(config=config)
        errors = []
        operator.validate(errors=errors, warnings=[], available_features=[])

        assert len(errors) > 0
        assert any("index_name is required" in str(error) for error in errors)

    def test_invalid_provider(self, basic_config):
        """Test that invalid provider raises error"""
        config = basic_config.copy()
        config["provider"] = "invalid_db"

        with pytest.raises(DocpipeException, match="Failed to initialize vector database adapter"):
            VectorDBOperator(config)

    def test_missing_provider_config(self, basic_config):
        """Test that missing provider_config raises clear error"""
        config = basic_config.copy()
        del config[OperatorConstants.Config.PROVIDER_CONFIG]

        with pytest.raises(DocpipeException, match="'provider_config' is required but missing or empty"):
            VectorDBOperator(config)

    def test_empty_provider_config(self, basic_config):
        """Test that empty provider_config raises clear error"""
        config = basic_config.copy()
        config[OperatorConstants.Config.PROVIDER_CONFIG] = {}

        with pytest.raises(DocpipeException, match="'provider_config' is required but missing or empty"):
            VectorDBOperator(config)


class TestBatchProcessing:
    """Test batch processing functionality through public interface"""

    @patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.client.OpenSearch")
    @patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.batch_processor.helpers.bulk")
    def test_transform_basic(self, mock_bulk, mock_opensearch, basic_config, sample_table):
        """Test basic transform operation"""
        mock_client = MagicMock()
        mock_client.indices.exists.return_value = True
        mock_client.indices.get_mapping.return_value = {
            "test_index": {
                "mappings": {
                    "_meta": {"engine": "faiss", "algorithm": "hnsw"},
                    "properties": {
                        "vector_embeddings": {"type": "knn_vector", "dimension": 384},
                    },
                }
            }
        }
        mock_client.info.return_value = {"version": {"number": "2.11.0"}}
        mock_opensearch.return_value = mock_client
        mock_bulk.return_value = (3, [])

        operator = VectorDBOperator(basic_config)
        result_tables, metadata = operator.transform(sample_table)

        assert len(result_tables) == 1
        assert result_tables[0].num_rows == 3
        assert metadata["total_docs_count"] == 3
        assert metadata["processed_docs"] == 3
        assert metadata["failed_docs_count"] == 0

    @patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.client.OpenSearch")
    def test_transform_missing_doc_id_column(self, mock_opensearch, basic_config):
        """Test transform with missing doc_id column"""
        mock_client = MagicMock()
        mock_client.info.return_value = {"version": {"number": "2.11.0"}}
        mock_opensearch.return_value = mock_client

        table = pa.table({"content": ["Test"], "embeddings": [[0.1, 0.2]]})

        operator = VectorDBOperator(basic_config)
        _result_tables, metadata = operator.transform(table)

        assert metadata["node_status"] == "Failed"

    @patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.client.OpenSearch")
    def test_transform_empty_table(self, mock_opensearch, basic_config):
        """Test transform with empty table"""
        mock_client = MagicMock()
        mock_client.info.return_value = {"version": {"number": "2.11.0"}}
        mock_opensearch.return_value = mock_client

        empty_table = pa.table({"doc_id_hash": [], "content": [], "embeddings": []})

        operator = VectorDBOperator(basic_config)
        _result_tables, metadata = operator.transform(empty_table)

        assert metadata["total_docs_count"] == 0
        assert metadata["processed_docs"] == 0

    def test_transform_validates_existing_schema_before_insert(self, basic_config, sample_table):
        """Test existing vector store schema is validated before insert on reruns."""
        mock_adapter = Mock()
        mock_adapter.index_exists.return_value = True
        mock_adapter.detect_all_vector_dimensions.return_value = {"embeddings": 384}
        mock_adapter.validate_existing_schema = Mock()
        mock_adapter.create_index = Mock()
        mock_adapter.index_documents.return_value = (3, [])

        with patch(
            "docpipe.core.operators.vectordb.vectordb_operator.VectorStoreFactory.create",
            return_value=mock_adapter,
        ):
            operator = VectorDBOperator(basic_config)
            _result_tables, metadata = operator.transform(sample_table)

        mock_adapter.create_index.assert_not_called()
        mock_adapter.validate_existing_schema.assert_called_once_with(dimension_mapping={"embeddings": 384})
        mock_adapter.index_documents.assert_called_once()
        assert metadata["processed_docs"] == 3
        assert metadata["failed_docs_count"] == 0


class TestChunkedEmbeddings:
    """Test chunked embeddings produce correct OpenSearch documents"""

    @patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.client.OpenSearch")
    @patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.batch_processor.helpers.bulk")
    def test_chunks_store_chunk_specific_text(self, mock_bulk, mock_opensearch, basic_config):
        """Verify OpenSearch documents contain chunk-specific text, not full document content"""
        # Real scenario: 2 documents with 3 chunks each = 6 total chunks
        data = {
            "doc_id_hash": ["doc1_hash", "doc2_hash"],
            "content": [
                "Full content of document 1 that should NOT be in chunks",
                "Full content of document 2 that should NOT be in chunks",
            ],
            "chunked_content": [
                [
                    {"chunk": "First chunk of doc1", "start_index": 0},
                    {"chunk": "Second chunk of doc1", "start_index": 100},
                    {"chunk": "Third chunk of doc1", "start_index": 200},
                ],
                [
                    {"chunk": "First chunk of doc2", "start_index": 0},
                    {"chunk": "Second chunk of doc2", "start_index": 100},
                    {"chunk": "Third chunk of doc2", "start_index": 200},
                ],
            ],
            "embeddings": [
                [np.random.rand(384).tolist() for _ in range(3)],
                [np.random.rand(384).tolist() for _ in range(3)],
            ],
        }
        table = pa.table(data)

        mock_client = MagicMock()
        mock_client.indices.exists.return_value = True
        mock_client.indices.get_mapping.return_value = {
            "test_index": {
                "mappings": {
                    "_meta": {"engine": "faiss", "algorithm": "hnsw"},
                    "properties": {
                        "vector_embeddings": {"type": "knn_vector", "dimension": 384},
                    },
                }
            }
        }
        mock_client.info.return_value = {"version": {"number": "2.11.0"}}
        mock_opensearch.return_value = mock_client
        mock_bulk.return_value = (6, [])

        operator = VectorDBOperator(basic_config)
        operator.transform(table)

        # Extract documents sent to OpenSearch (like real query results)
        all_actions = []
        for call in mock_bulk.call_args_list:
            all_actions.extend(call[0][1])

        assert len(all_actions) == 6, "Should create 6 chunk documents"

        # Verify structure matches real OpenSearch output
        for action in all_actions:
            assert "_id" in action
            assert "_source" in action
            assert "text" in action["_source"]
            assert "vector_embeddings" in action["_source"]
            assert "pk" in action["_source"]

            # Key assertion: text field contains chunk content, not full document
            text_content = action["_source"]["text"]
            assert "Full content of document" not in text_content
            assert "chunk of doc" in text_content


class TestQueryCapabilities:
    """Test query and delete capabilities through public interface"""

    @patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.client.OpenSearch")
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

        operator = VectorDBOperator(basic_config)
        docs = operator.query_by_doc_names(["doc1", "doc2"])

        assert len(docs) == 2
        assert docs[0]["name"] == "doc1"
        assert docs[1]["name"] == "doc2"

    @patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.client.OpenSearch")
    @patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.batch_processor.helpers.bulk")
    def test_delete_documents_by_ids(self, mock_bulk, mock_opensearch, basic_config):
        """Test deleting documents by IDs"""
        mock_client = MagicMock()
        mock_client.info.return_value = {"version": {"number": "2.11.0"}}
        mock_opensearch.return_value = mock_client
        mock_bulk.return_value = (2, [])

        operator = VectorDBOperator(basic_config)
        success, failed = operator.delete_documents_by_ids(["doc1", "doc2"])

        assert success == 2
        assert failed == 0

    @patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.client.OpenSearch")
    def test_get_document_count(self, mock_opensearch, basic_config):
        """Test getting document count"""
        mock_client = MagicMock()
        mock_client.info.return_value = {"version": {"number": "2.11.0"}}
        mock_client.count.return_value = {"count": 100}
        mock_opensearch.return_value = mock_client

        operator = VectorDBOperator(basic_config)
        count = operator.get_document_count()

        assert count == 100


class TestMetadata:
    """Test operator metadata"""

    def test_get_metadata(self):
        """Test get_metadata returns correct structure"""
        config = {
            "provider": "opensearch",
            "index_name": "test_index",
            "doc_id_column": "doc_id_hash",
            "embeddings_column": "embeddings",
            "vector_dimension": 384,
            "provider_config": {
                "host": "localhost",
                "port": 9200,
                "engine": "faiss",
                "algorithm": "hnsw",
            },
        }

        with patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.client.OpenSearch"):
            operator = VectorDBOperator(config)
            metadata = operator.get_metadata()

        assert metadata["sdk"] is True
        assert metadata["category"] == "VectorDB"
        assert metadata["is_operator_available"] is True
        assert "features" in metadata
        assert "attributes" in metadata


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
