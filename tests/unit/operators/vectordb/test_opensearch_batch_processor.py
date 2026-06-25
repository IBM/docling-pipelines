#!/usr/bin/env python3
"""
Unit tests for OpenSearchBatchProcessor
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from docpipe.core.operators.vectordb.adapters.outbound.opensearch.batch_processor import (
    BULK_DELETE_BATCH_SIZE,
    BULK_INSERT_TIMEOUT,
    DEFAULT_BATCH_SIZE,
    OpenSearchBatchProcessor,
)


@pytest.fixture
def mock_client():
    """Mock OpenSearch client"""
    return MagicMock()


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
        "metadata": {
            "name": "Metadata",
            "available_for_vector_db": True,
            "type": "object",
        },
    }


@pytest.fixture
def feature_mappings():
    """Feature mappings"""
    return {
        "doc_id": "pk",
        "content": "text",
        "embeddings": "vector_embeddings",
        "metadata": "meta",
    }


class TestBatchProcessorInitialization:
    """Test batch processor initialization"""

    def test_basic_initialization(self, mock_client):
        """Test basic initialization with default parameters"""
        processor = OpenSearchBatchProcessor(
            client=mock_client,
            index_name="test_index",
        )

        assert processor.client == mock_client
        assert processor.index_name == "test_index"
        assert processor.batch_size == DEFAULT_BATCH_SIZE

    def test_initialization_with_custom_batch_size(self, mock_client):
        """Test initialization with custom batch size"""
        processor = OpenSearchBatchProcessor(
            client=mock_client,
            index_name="test_index",
            batch_size=500,
        )

        assert processor.batch_size == 500

    def test_initialization_with_features(self, mock_client, basic_features, feature_mappings):
        """Test initialization with feature configuration"""
        processor = OpenSearchBatchProcessor(
            client=mock_client,
            index_name="test_index",
            available_features=basic_features,
            feature_mappings=feature_mappings,
        )

        assert processor.available_features == basic_features
        assert processor.feature_mappings == feature_mappings


class TestDocumentPreparation:
    """Test document preparation"""

    def test_prepare_basic_document(self, mock_client, basic_features, feature_mappings):
        """Test preparing basic document"""
        processor = OpenSearchBatchProcessor(
            client=mock_client,
            index_name="test_index",
            available_features=basic_features,
            feature_mappings=feature_mappings,
        )

        row_data = {
            "doc_id": "doc1",
            "content": "Test content",
            "embeddings": [0.1, 0.2, 0.3],
        }

        doc = processor.prepare_document(row_data=row_data)

        assert doc["pk"] == "doc1"
        assert doc["text"] == "Test content"
        assert doc["vector_embeddings"] == [0.1, 0.2, 0.3]

    def test_prepare_document_with_none_values(self, mock_client, basic_features, feature_mappings):
        """Test preparing document with None values"""
        processor = OpenSearchBatchProcessor(
            client=mock_client,
            index_name="test_index",
            available_features=basic_features,
            feature_mappings=feature_mappings,
        )

        row_data = {
            "doc_id": "doc1",
            "content": None,
            "embeddings": [0.1, 0.2, 0.3],
        }

        doc = processor.prepare_document(row_data=row_data)

        assert doc["pk"] == "doc1"
        assert "text" not in doc  # None values should be excluded
        assert doc["vector_embeddings"] == [0.1, 0.2, 0.3]

    def test_prepare_document_with_numpy_array(self, mock_client, basic_features, feature_mappings):
        """Test preparing document with numpy array"""
        import numpy as np

        processor = OpenSearchBatchProcessor(
            client=mock_client,
            index_name="test_index",
            available_features=basic_features,
            feature_mappings=feature_mappings,
        )

        row_data = {
            "doc_id": "doc1",
            "content": "Test",
            "embeddings": np.array([0.1, 0.2, 0.3]),
        }

        doc = processor.prepare_document(row_data=row_data)

        assert isinstance(doc["vector_embeddings"], list)
        assert doc["vector_embeddings"] == [0.1, 0.2, 0.3]

    def test_prepare_document_with_json_string(self, mock_client, basic_features, feature_mappings):
        """Test preparing document with JSON string for object type"""
        processor = OpenSearchBatchProcessor(
            client=mock_client,
            index_name="test_index",
            available_features=basic_features,
            feature_mappings=feature_mappings,
        )

        metadata_dict = {"key": "value", "count": 42}
        row_data = {
            "doc_id": "doc1",
            "content": "Test",
            "embeddings": [0.1, 0.2],
            "metadata": json.dumps(metadata_dict),
        }

        doc = processor.prepare_document(row_data=row_data)

        assert doc["meta"] == metadata_dict

    def test_prepare_document_with_invalid_json(self, mock_client, basic_features, feature_mappings):
        """Test preparing document with invalid JSON string"""
        processor = OpenSearchBatchProcessor(
            client=mock_client,
            index_name="test_index",
            available_features=basic_features,
            feature_mappings=feature_mappings,
        )

        row_data = {
            "doc_id": "doc1",
            "content": "Test",
            "embeddings": [0.1, 0.2],
            "metadata": "invalid json {",
        }

        doc = processor.prepare_document(row_data=row_data)

        # Should keep as string if JSON parsing fails
        assert doc["meta"] == "invalid json {"

    def test_prepare_document_excludes_unavailable_features(self, mock_client):
        """Test that unavailable features are excluded"""
        features = {
            "included": {"available_for_vector_db": True, "type": "string"},
            "excluded": {"available_for_vector_db": False, "type": "string"},
        }

        # feature_mappings defines which fields to include
        mappings = {
            "included": "included",
            "excluded": "excluded",
        }

        processor = OpenSearchBatchProcessor(
            client=mock_client,
            index_name="test_index",
            available_features=features,
            feature_mappings=mappings,
        )

        row_data = {
            "included": "value1",
            "excluded": "value2",
        }

        doc = processor.prepare_document(row_data=row_data)

        assert "included" in doc
        assert "excluded" not in doc


class TestBatchSizeCalculation:
    """Test batch size calculation"""

    def test_calculate_batch_size_bytes(self, mock_client):
        """Test calculating batch size in bytes using shared utility"""
        from docpipe.utils.operators.vectordb_utils import calculate_batch_size_bytes

        documents = [
            {"id": "doc1", "content": "test"},
            {"id": "doc2", "content": "test2"},
        ]

        size = calculate_batch_size_bytes(documents=documents)

        assert size > 0
        assert isinstance(size, int)

    def test_calculate_batch_size_empty_list(self, mock_client):
        """Test calculating batch size for empty list using shared utility"""
        from docpipe.utils.operators.vectordb_utils import calculate_batch_size_bytes

        size = calculate_batch_size_bytes(documents=[])

        assert size >= 0

    def test_calculate_batch_size_handles_error(self, mock_client):
        """Test batch size calculation handles errors using shared utility"""
        from docpipe.utils.operators.vectordb_utils import calculate_batch_size_bytes

        # Non-serializable object
        documents = [{"obj": object()}]

        size = calculate_batch_size_bytes(documents=documents)

        assert size == 0


class TestBatchCreation:
    """Test batch creation logic"""

    def test_create_batches_single_batch(self, mock_client):
        """Test creating single batch when documents fit"""
        processor = OpenSearchBatchProcessor(
            client=mock_client,
            index_name="test_index",
            batch_size=100,
        )

        documents = [
            ("doc1", {"content": "test1"}),
            ("doc2", {"content": "test2"}),
            ("doc3", {"content": "test3"}),
        ]

        batches = processor.create_batches(documents)

        assert len(batches) == 1
        assert len(batches[0]) == 3

    def test_create_batches_multiple_batches_by_count(self, mock_client):
        """Test creating multiple batches based on count limit"""
        processor = OpenSearchBatchProcessor(
            client=mock_client,
            index_name="test_index",
            batch_size=2,
        )

        documents = [
            ("doc1", {"content": "test1"}),
            ("doc2", {"content": "test2"}),
            ("doc3", {"content": "test3"}),
        ]

        batches = processor.create_batches(documents)

        assert len(batches) == 2
        assert len(batches[0]) == 2
        assert len(batches[1]) == 1

    def test_create_batches_multiple_batches_by_size(self, mock_client):
        """Test creating multiple batches based on size limit"""
        # Define features so documents aren't filtered out
        features = {"content": {"available_for_vector_db": True, "type": "string"}}
        mappings = {"content": "content"}

        processor = OpenSearchBatchProcessor(
            client=mock_client,
            index_name="test_index",
            batch_size=1000,
            available_features=features,
            feature_mappings=mappings,
        )

        # Create large documents that exceed 3MB when combined
        large_content = "x" * (2 * 1024 * 1024)  # 2MB per document
        documents = [
            ("doc1", {"content": large_content}),
            ("doc2", {"content": large_content}),
        ]

        batches = processor.create_batches(documents)

        # Should split into separate batches due to size
        assert len(batches) >= 2

    def test_create_batches_action_structure(self, mock_client):
        """Test batch action structure"""
        # Define features so documents aren't filtered out
        features = {"content": {"available_for_vector_db": True, "type": "string"}}
        mappings = {"content": "content"}

        processor = OpenSearchBatchProcessor(
            client=mock_client,
            index_name="test_index",
            available_features=features,
            feature_mappings=mappings,
        )

        documents = [("doc1", {"content": "test"})]

        batches = processor.create_batches(documents)

        action = batches[0][0]
        assert action["_index"] == "test_index"
        assert action["_id"] == "doc1"
        assert action["_source"] == {"content": "test"}

    def test_create_batches_empty_documents(self, mock_client):
        """Test creating batches with empty document list"""
        processor = OpenSearchBatchProcessor(
            client=mock_client,
            index_name="test_index",
        )

        batches = processor.create_batches([])

        assert len(batches) == 0


class TestBulkIndexing:
    """Test bulk indexing operations"""

    @patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.batch_processor.helpers.bulk")
    def test_bulk_index_success(self, mock_bulk, mock_client):
        """Test successful bulk indexing"""
        mock_bulk.return_value = (3, [])

        processor = OpenSearchBatchProcessor(
            client=mock_client,
            index_name="test_index",
        )

        actions = [
            {"_index": "test_index", "_id": "doc1", "_source": {"content": "test1"}},
            {"_index": "test_index", "_id": "doc2", "_source": {"content": "test2"}},
            {"_index": "test_index", "_id": "doc3", "_source": {"content": "test3"}},
        ]

        success, failed = processor.bulk_index(actions)

        assert success == 3
        assert len(failed) == 0
        mock_bulk.assert_called_once()

    @patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.batch_processor.helpers.bulk")
    def test_bulk_index_with_failures(self, mock_bulk, mock_client):
        """Test bulk indexing with some failures"""
        failed_items = [{"_id": "doc2", "error": "version conflict"}]
        mock_bulk.return_value = (2, failed_items)

        processor = OpenSearchBatchProcessor(
            client=mock_client,
            index_name="test_index",
        )

        actions = [
            {"_index": "test_index", "_id": "doc1", "_source": {"content": "test1"}},
            {"_index": "test_index", "_id": "doc2", "_source": {"content": "test2"}},
            {"_index": "test_index", "_id": "doc3", "_source": {"content": "test3"}},
        ]

        success, failed = processor.bulk_index(actions)

        assert success == 2
        assert len(failed) == 1

    @patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.batch_processor.helpers.bulk")
    def test_bulk_index_error(self, mock_bulk, mock_client):
        """Test bulk indexing handles errors"""
        mock_bulk.side_effect = Exception("Bulk error")

        processor = OpenSearchBatchProcessor(
            client=mock_client,
            index_name="test_index",
        )

        actions = [{"_index": "test_index", "_id": "doc1", "_source": {"content": "test"}}]

        success, failed = processor.bulk_index(actions)

        assert success == 0
        assert len(failed) == 1

    @patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.batch_processor.helpers.bulk")
    def test_bulk_index_timeout_parameter(self, mock_bulk, mock_client):
        """Test bulk indexing uses correct timeout"""
        mock_bulk.return_value = (1, [])

        processor = OpenSearchBatchProcessor(
            client=mock_client,
            index_name="test_index",
        )

        actions = [{"_index": "test_index", "_id": "doc1", "_source": {"content": "test"}}]

        processor.bulk_index(actions)

        call_kwargs = mock_bulk.call_args[1]
        assert call_kwargs["request_timeout"] == BULK_INSERT_TIMEOUT


class TestBatchProcessing:
    """Test batch processing"""

    @patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.batch_processor.helpers.bulk")
    def test_process_batches_single_batch(self, mock_bulk, mock_client):
        """Test processing single batch"""
        mock_bulk.return_value = (3, [])

        processor = OpenSearchBatchProcessor(
            client=mock_client,
            index_name="test_index",
        )

        batches = [
            [
                {
                    "_index": "test_index",
                    "_id": "doc1",
                    "_source": {"content": "test1"},
                },
                {
                    "_index": "test_index",
                    "_id": "doc2",
                    "_source": {"content": "test2"},
                },
                {
                    "_index": "test_index",
                    "_id": "doc3",
                    "_source": {"content": "test3"},
                },
            ]
        ]

        success, failed = processor.process_batches(batches)

        assert success == 3
        assert len(failed) == 0

    @patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.batch_processor.helpers.bulk")
    def test_process_batches_multiple_batches(self, mock_bulk, mock_client):
        """Test processing multiple batches"""
        mock_bulk.side_effect = [(2, []), (3, [])]

        processor = OpenSearchBatchProcessor(
            client=mock_client,
            index_name="test_index",
        )

        batches = [
            [
                {
                    "_index": "test_index",
                    "_id": "doc1",
                    "_source": {"content": "test1"},
                },
                {
                    "_index": "test_index",
                    "_id": "doc2",
                    "_source": {"content": "test2"},
                },
            ],
            [
                {
                    "_index": "test_index",
                    "_id": "doc3",
                    "_source": {"content": "test3"},
                },
                {
                    "_index": "test_index",
                    "_id": "doc4",
                    "_source": {"content": "test4"},
                },
                {
                    "_index": "test_index",
                    "_id": "doc5",
                    "_source": {"content": "test5"},
                },
            ],
        ]

        success, failed = processor.process_batches(batches)

        assert success == 5
        assert len(failed) == 0

    @patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.batch_processor.helpers.bulk")
    def test_process_batches_with_failures(self, mock_bulk, mock_client):
        """Test processing batches with failures"""
        failed_items = [{"_id": "doc2", "error": "error"}]
        mock_bulk.side_effect = [(1, failed_items), (2, [])]

        processor = OpenSearchBatchProcessor(
            client=mock_client,
            index_name="test_index",
        )

        batches = [
            [
                {
                    "_index": "test_index",
                    "_id": "doc1",
                    "_source": {"content": "test1"},
                },
                {
                    "_index": "test_index",
                    "_id": "doc2",
                    "_source": {"content": "test2"},
                },
            ],
            [
                {
                    "_index": "test_index",
                    "_id": "doc3",
                    "_source": {"content": "test3"},
                },
                {
                    "_index": "test_index",
                    "_id": "doc4",
                    "_source": {"content": "test4"},
                },
            ],
        ]

        success, failed = processor.process_batches(batches)

        assert success == 3
        assert len(failed) == 1

    @patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.batch_processor.helpers.bulk")
    def test_process_batches_batch_error(self, mock_bulk, mock_client):
        """Test processing batches when one batch fails"""
        mock_bulk.side_effect = [Exception("Batch error"), (2, [])]

        processor = OpenSearchBatchProcessor(
            client=mock_client,
            index_name="test_index",
        )

        batches = [
            [{"_index": "test_index", "_id": "doc1", "_source": {"content": "test1"}}],
            [
                {
                    "_index": "test_index",
                    "_id": "doc2",
                    "_source": {"content": "test2"},
                },
                {
                    "_index": "test_index",
                    "_id": "doc3",
                    "_source": {"content": "test3"},
                },
            ],
        ]

        success, failed = processor.process_batches(batches)

        assert success == 2
        assert len(failed) == 1


class TestQueryOperations:
    """Test query operations"""

    def test_query_by_doc_names_success(self, mock_client):
        """Test querying documents by names"""
        mock_client.search.return_value = {
            "hits": {
                "hits": [
                    {"_source": {"name": "doc1", "content": "test1"}},
                    {"_source": {"name": "doc2", "content": "test2"}},
                ]
            }
        }

        processor = OpenSearchBatchProcessor(
            client=mock_client,
            index_name="test_index",
        )

        docs = processor.query_by_doc_names(["doc1", "doc2"])

        assert len(docs) == 2
        assert docs[0]["name"] == "doc1"
        assert docs[1]["name"] == "doc2"

    def test_query_by_doc_names_with_fields(self, mock_client):
        """Test querying with specific fields"""
        mock_client.search.return_value = {
            "hits": {
                "hits": [
                    {"_source": {"name": "doc1"}},
                ]
            }
        }

        processor = OpenSearchBatchProcessor(
            client=mock_client,
            index_name="test_index",
        )

        processor.query_by_doc_names(["doc1"], fields=["name"])

        call_kwargs = mock_client.search.call_args[1]
        assert "_source" in call_kwargs["body"]
        assert call_kwargs["body"]["_source"] == ["name"]

    def test_query_by_doc_names_empty_list(self, mock_client):
        """Test querying with empty list"""
        processor = OpenSearchBatchProcessor(
            client=mock_client,
            index_name="test_index",
        )

        docs = processor.query_by_doc_names([])

        assert len(docs) == 0
        mock_client.search.assert_not_called()

    def test_query_by_doc_names_error(self, mock_client):
        """Test query handles errors"""
        mock_client.search.side_effect = Exception("Search error")

        processor = OpenSearchBatchProcessor(
            client=mock_client,
            index_name="test_index",
        )

        docs = processor.query_by_doc_names(["doc1"])

        assert len(docs) == 0

    def test_query_constructs_correct_query(self, mock_client):
        """Test query construction"""
        mock_client.search.return_value = {"hits": {"hits": []}}

        processor = OpenSearchBatchProcessor(
            client=mock_client,
            index_name="test_index",
        )

        processor.query_by_doc_names(["doc1", "doc2"])

        call_kwargs = mock_client.search.call_args[1]
        query = call_kwargs["body"]["query"]
        assert "terms" in query
        assert "name.keyword" in query["terms"]
        assert query["terms"]["name.keyword"] == ["doc1", "doc2"]


class TestDeleteOperations:
    """Test delete operations"""

    @patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.batch_processor.helpers.bulk")
    def test_delete_documents_by_ids_success(self, mock_bulk, mock_client):
        """Test successful document deletion"""
        mock_bulk.return_value = (3, [])

        processor = OpenSearchBatchProcessor(
            client=mock_client,
            index_name="test_index",
        )

        success, failed = processor.delete_documents_by_ids(["doc1", "doc2", "doc3"])

        assert success == 3
        assert failed == 0

    @patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.batch_processor.helpers.bulk")
    def test_delete_documents_by_ids_with_failures(self, mock_bulk, mock_client):
        """Test document deletion with failures"""
        failed_items = [{"_id": "doc2"}]
        mock_bulk.return_value = (2, failed_items)

        processor = OpenSearchBatchProcessor(
            client=mock_client,
            index_name="test_index",
        )

        success, failed = processor.delete_documents_by_ids(["doc1", "doc2", "doc3"])

        assert success == 2
        assert failed == 1

    @patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.batch_processor.helpers.bulk")
    def test_delete_documents_empty_list(self, mock_bulk, mock_client):
        """Test deleting with empty list"""
        processor = OpenSearchBatchProcessor(
            client=mock_client,
            index_name="test_index",
        )

        success, failed = processor.delete_documents_by_ids([])

        assert success == 0
        assert failed == 0
        mock_bulk.assert_not_called()

    @patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.batch_processor.helpers.bulk")
    def test_delete_documents_large_batch(self, mock_bulk, mock_client):
        """Test deleting large batch splits into multiple requests"""
        mock_bulk.return_value = (BULK_DELETE_BATCH_SIZE, [])

        processor = OpenSearchBatchProcessor(
            client=mock_client,
            index_name="test_index",
        )

        # Create more IDs than batch size
        doc_ids = [f"doc{i}" for i in range(BULK_DELETE_BATCH_SIZE + 100)]

        processor.delete_documents_by_ids(doc_ids)

        # Should be called twice (one full batch + one partial)
        assert mock_bulk.call_count == 2

    @patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.batch_processor.helpers.bulk")
    def test_delete_documents_action_structure(self, mock_bulk, mock_client):
        """Test delete action structure"""
        mock_bulk.return_value = (1, [])

        processor = OpenSearchBatchProcessor(
            client=mock_client,
            index_name="test_index",
        )

        processor.delete_documents_by_ids(["doc1"])

        call_args = mock_bulk.call_args[0]
        actions = call_args[1]
        action = actions[0]

        assert action["_op_type"] == "delete"
        assert action["_index"] == "test_index"
        assert action["_id"] == "doc1"

    @patch("docpipe.core.operators.vectordb.adapters.outbound.opensearch.batch_processor.helpers.bulk")
    def test_delete_documents_error(self, mock_bulk, mock_client):
        """Test delete handles errors"""
        mock_bulk.side_effect = Exception("Delete error")

        processor = OpenSearchBatchProcessor(
            client=mock_client,
            index_name="test_index",
        )

        success, failed = processor.delete_documents_by_ids(["doc1", "doc2"])

        assert success == 0
        assert failed == 2


class TestDocumentCount:
    """Test document count operations"""

    def test_get_document_count_success(self, mock_client):
        """Test getting document count"""
        mock_client.count.return_value = {"count": 100}

        processor = OpenSearchBatchProcessor(
            client=mock_client,
            index_name="test_index",
        )

        count = processor.get_document_count()

        assert count == 100
        mock_client.count.assert_called_once_with(index="test_index")

    def test_get_document_count_zero(self, mock_client):
        """Test getting zero document count"""
        mock_client.count.return_value = {"count": 0}

        processor = OpenSearchBatchProcessor(
            client=mock_client,
            index_name="test_index",
        )

        count = processor.get_document_count()

        assert count == 0

    def test_get_document_count_error(self, mock_client):
        """Test document count handles errors"""
        mock_client.count.side_effect = Exception("Count error")

        processor = OpenSearchBatchProcessor(
            client=mock_client,
            index_name="test_index",
        )

        count = processor.get_document_count()

        assert count == 0

    def test_get_document_count_missing_key(self, mock_client):
        """Test document count with missing count key"""
        mock_client.count.return_value = {}

        processor = OpenSearchBatchProcessor(
            client=mock_client,
            index_name="test_index",
        )

        count = processor.get_document_count()

        assert count == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
