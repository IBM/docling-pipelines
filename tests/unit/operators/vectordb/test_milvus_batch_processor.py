#!/usr/bin/env python3
"""
Unit tests for MilvusBatchProcessor
"""

from unittest.mock import MagicMock

import pytest

from docpipe.core.operators.vectordb.adapters.outbound.milvus.batch_processor import (
    DEFAULT_BATCH_SIZE,
    MilvusBatchProcessor,
)


@pytest.fixture
def mock_client():
    """Mock Milvus client"""
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
        processor = MilvusBatchProcessor(
            client=mock_client,
            collection_name="test_collection",
        )

        assert processor.client == mock_client
        assert processor.collection_name == "test_collection"
        assert processor.batch_size == DEFAULT_BATCH_SIZE
        assert processor.primary_key_field == "pk"

    def test_initialization_with_custom_batch_size(self, mock_client):
        """Test initialization with custom batch size"""
        processor = MilvusBatchProcessor(
            client=mock_client,
            collection_name="test_collection",
            batch_size=500,
        )

        assert processor.batch_size == 500

    def test_initialization_with_features(self, mock_client, basic_features, feature_mappings):
        """Test initialization with feature configuration"""
        processor = MilvusBatchProcessor(
            client=mock_client,
            collection_name="test_collection",
            available_features=basic_features,
            feature_mappings=feature_mappings,
        )

        assert processor.available_features == basic_features
        assert processor.feature_mappings == feature_mappings

    def test_initialization_with_custom_primary_key(self, mock_client):
        """Test initialization with custom primary key field"""
        processor = MilvusBatchProcessor(
            client=mock_client,
            collection_name="test_collection",
            primary_key_field="id",
        )

        assert processor.primary_key_field == "id"


class TestDocumentPreparation:
    """Test document preparation"""

    def test_prepare_simple_document(self, mock_client, basic_features, feature_mappings):
        """Test preparing a simple document"""
        processor = MilvusBatchProcessor(
            client=mock_client,
            collection_name="test_collection",
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

    def test_prepare_document_with_metadata(self, mock_client, basic_features, feature_mappings):
        """Test preparing document with metadata"""
        processor = MilvusBatchProcessor(
            client=mock_client,
            collection_name="test_collection",
            available_features=basic_features,
            feature_mappings=feature_mappings,
        )

        row_data = {
            "doc_id": "doc1",
            "content": "Test content",
            "embeddings": [0.1, 0.2, 0.3],
            "metadata": {"source": "test", "page": 1},
        }

        doc = processor.prepare_document(row_data=row_data)

        assert doc["meta"] == {"source": "test", "page": 1}

    def test_prepare_document_skips_none_values(self, mock_client, basic_features, feature_mappings):
        """Test that None values are skipped"""
        processor = MilvusBatchProcessor(
            client=mock_client,
            collection_name="test_collection",
            available_features=basic_features,
            feature_mappings=feature_mappings,
        )

        row_data = {
            "doc_id": "doc1",
            "content": None,
            "embeddings": [0.1, 0.2, 0.3],
        }

        doc = processor.prepare_document(row_data=row_data)

        assert "text" not in doc
        assert "pk" in doc
        assert "vector_embeddings" in doc

    def test_prepare_document_skips_binary_data(self, mock_client, basic_features, feature_mappings):
        """Test that binary data is skipped"""
        processor = MilvusBatchProcessor(
            client=mock_client,
            collection_name="test_collection",
            available_features=basic_features,
            feature_mappings=feature_mappings,
        )

        row_data = {
            "doc_id": "doc1",
            "content": b"binary content",
            "embeddings": [0.1, 0.2, 0.3],
        }

        doc = processor.prepare_document(row_data=row_data)

        assert "text" not in doc

    def test_prepare_document_converts_numpy_arrays(self, mock_client, basic_features, feature_mappings):
        """Test that numpy arrays are converted to lists"""
        import numpy as np

        processor = MilvusBatchProcessor(
            client=mock_client,
            collection_name="test_collection",
            available_features=basic_features,
            feature_mappings=feature_mappings,
        )

        row_data = {
            "doc_id": "doc1",
            "content": "Test content",
            "embeddings": np.array([0.1, 0.2, 0.3]),
        }

        doc = processor.prepare_document(row_data=row_data)

        assert isinstance(doc["vector_embeddings"], list)
        assert doc["vector_embeddings"] == [0.1, 0.2, 0.3]

    def test_prepare_document_parses_json_strings(self, mock_client, basic_features, feature_mappings):
        """Test that JSON strings are parsed for object types"""
        processor = MilvusBatchProcessor(
            client=mock_client,
            collection_name="test_collection",
            available_features=basic_features,
            feature_mappings=feature_mappings,
        )

        row_data = {
            "doc_id": "doc1",
            "content": "Test content",
            "embeddings": [0.1, 0.2, 0.3],
            "metadata": '{"source": "test", "page": 1}',
        }

        doc = processor.prepare_document(row_data=row_data)

        assert isinstance(doc["meta"], dict)
        assert doc["meta"]["source"] == "test"
        assert doc["meta"]["page"] == 1

    def test_prepare_document_handles_invalid_json(self, mock_client, basic_features, feature_mappings):
        """Test that invalid JSON is kept as string"""
        processor = MilvusBatchProcessor(
            client=mock_client,
            collection_name="test_collection",
            available_features=basic_features,
            feature_mappings=feature_mappings,
        )

        row_data = {
            "doc_id": "doc1",
            "content": "Test content",
            "embeddings": [0.1, 0.2, 0.3],
            "metadata": "invalid json {",
        }

        doc = processor.prepare_document(row_data=row_data)

        assert isinstance(doc["meta"], str)
        assert doc["meta"] == "invalid json {"

    def test_prepare_document_only_mapped_features(self, mock_client, basic_features, feature_mappings):
        """Test that only mapped features are included"""
        processor = MilvusBatchProcessor(
            client=mock_client,
            collection_name="test_collection",
            available_features=basic_features,
            feature_mappings=feature_mappings,
        )

        row_data = {
            "doc_id": "doc1",
            "content": "Test content",
            "embeddings": [0.1, 0.2, 0.3],
            "unmapped_field": "should not appear",
        }

        doc = processor.prepare_document(row_data=row_data)

        assert "unmapped_field" not in doc
        assert len(doc) == 3  # pk, text, vector_embeddings


class TestBatchSizeCalculation:
    """Test batch size calculation"""

    def test_calculate_batch_size_bytes(self, mock_client):
        """Test calculating batch size in bytes using shared utility"""
        from docpipe.utils.operators.vectordb_utils import calculate_batch_size_bytes

        documents = [
            {"pk": "doc1", "text": "content1"},
            {"pk": "doc2", "text": "content2"},
        ]

        size = calculate_batch_size_bytes(documents=documents)
        assert size > 0
        assert isinstance(size, int)

    def test_calculate_batch_size_empty_list(self, mock_client):
        """Test calculating size of empty list using shared utility"""
        from docpipe.utils.operators.vectordb_utils import calculate_batch_size_bytes

        size = calculate_batch_size_bytes(documents=[])
        assert size >= 0

    def test_calculate_batch_size_with_vectors(self, mock_client):
        """Test calculating size with vector embeddings using shared utility"""
        from docpipe.utils.operators.vectordb_utils import calculate_batch_size_bytes

        documents = [
            {"pk": "doc1", "vector": [0.1] * 384},
            {"pk": "doc2", "vector": [0.2] * 384},
        ]

        size = calculate_batch_size_bytes(documents=documents)
        assert size > 1000  # Should be substantial with vectors


class TestBatchCreation:
    """Test batch creation"""

    def test_create_batches_by_count(self, mock_client, basic_features, feature_mappings):
        """Test creating batches based on count limit"""
        processor = MilvusBatchProcessor(
            client=mock_client,
            collection_name="test_collection",
            batch_size=2,
            available_features=basic_features,
            feature_mappings=feature_mappings,
        )

        documents = [
            ("doc1", {"doc_id": "doc1", "content": "text1", "embeddings": [0.1, 0.2]}),
            ("doc2", {"doc_id": "doc2", "content": "text2", "embeddings": [0.3, 0.4]}),
            ("doc3", {"doc_id": "doc3", "content": "text3", "embeddings": [0.5, 0.6]}),
        ]

        batches = processor.create_batches(documents=documents)

        assert len(batches) == 2
        assert len(batches[0]) == 2
        assert len(batches[1]) == 1

    def test_create_batches_single_batch(self, mock_client, basic_features, feature_mappings):
        """Test creating single batch when all fit"""
        processor = MilvusBatchProcessor(
            client=mock_client,
            collection_name="test_collection",
            batch_size=10,
            available_features=basic_features,
            feature_mappings=feature_mappings,
        )

        documents = [
            ("doc1", {"doc_id": "doc1", "content": "text1", "embeddings": [0.1, 0.2]}),
            ("doc2", {"doc_id": "doc2", "content": "text2", "embeddings": [0.3, 0.4]}),
        ]

        batches = processor.create_batches(documents=documents)

        assert len(batches) == 1
        assert len(batches[0]) == 2

    def test_create_batches_empty_documents(self, mock_client):
        """Test creating batches with empty document list"""
        processor = MilvusBatchProcessor(
            client=mock_client,
            collection_name="test_collection",
        )

        batches = processor.create_batches(documents=[])

        assert len(batches) == 0


class TestBulkOperations:
    """Test bulk operations"""

    def test_process_batches_success(self, mock_client, basic_features, feature_mappings):
        """Test successful batch processing"""
        mock_client.insert.return_value = {"insert_count": 2}

        processor = MilvusBatchProcessor(
            client=mock_client,
            collection_name="test_collection",
            available_features=basic_features,
            feature_mappings=feature_mappings,
        )

        # Create batches
        batch1 = [
            {"pk": "doc1", "text": "text1", "vector_embeddings": [0.1, 0.2]},
            {"pk": "doc2", "text": "text2", "vector_embeddings": [0.3, 0.4]},
        ]
        batches = [batch1]

        success_count, failed_items = processor.process_batches(batches=batches)

        assert success_count == 2
        assert len(failed_items) == 0
        mock_client.insert.assert_called_once()

    def test_delete_documents_success(self, mock_client):
        """Test successful document deletion"""
        mock_client.delete.return_value = {"delete_count": 3}

        processor = MilvusBatchProcessor(
            client=mock_client,
            collection_name="test_collection",
        )

        doc_ids = ["doc1", "doc2", "doc3"]
        success_count, failed_count = processor.delete_documents_by_ids(doc_ids=doc_ids)

        assert success_count == 3
        assert failed_count == 0
        mock_client.delete.assert_called_once()
