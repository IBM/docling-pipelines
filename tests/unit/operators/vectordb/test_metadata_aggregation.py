#!/usr/bin/env python3
"""
Unit tests for metadata aggregation in OpenSearch VectorDB operations.
"""

from unittest.mock import MagicMock, Mock

import pytest
from opensearchpy import OpenSearch

from docpipe.core.operators.vectordb.adapters.outbound.opensearch.batch_processor import (
    METADATA_COLUMNS,
    OpenSearchBatchProcessor,
)
from docpipe.core.operators.vectordb.adapters.outbound.opensearch.index_manager import OpenSearchIndexManager


class TestMetadataAggregation:
    """Test metadata column aggregation in batch processor."""

    @pytest.fixture
    def mock_client(self):
        """Create mock OpenSearch client."""
        return Mock(spec=OpenSearch)

    @pytest.fixture
    def available_features(self):
        """Standard available features configuration."""
        return {
            "doc_id_hash": {
                "available_for_vector_db": True,
                "mandatory_for_vector_db": True,
                "type": "string",
                "is_primary": True,
            },
            "content": {
                "available_for_vector_db": True,
                "type": "string",
            },
            "embeddings": {
                "available_for_vector_db": True,
                "mandatory_for_vector_db": True,
                "type": "vector",
            },
        }

    @pytest.fixture
    def feature_mappings(self):
        """Standard feature mappings."""
        return {
            "doc_id_hash": "id",
            "content": "text",
            "embeddings": "vector",
        }

    @pytest.fixture
    def batch_processor(self, *, mock_client, available_features, feature_mappings):
        """Create batch processor instance."""
        return OpenSearchBatchProcessor(
            client=mock_client,
            index_name="test_index",
            available_features=available_features,
            feature_mappings=feature_mappings,
        )

    def test_metadata_aggregation_all_columns(self, *, batch_processor):
        """Test that all metadata columns are aggregated correctly."""
        row_data = {
            "doc_id_hash": "doc_1",
            "content": "Sample text",
            "embeddings": [0.1, 0.2, 0.3],
            "name": "/path/to/file.pdf",
            "size": 1024000,
            "created_time": 1704067200,
            "modified_time": 1704153600,
            "source": "s3://bucket/file.pdf",
            "mimetype": "application/pdf",
            "extension": "pdf",
            "page_count": 10,
        }

        doc = batch_processor.prepare_document(row_data=row_data)

        # Check mapped fields
        assert doc["id"] == "doc_1"
        assert doc["text"] == "Sample text"
        assert doc["vector"] == [0.1, 0.2, 0.3]

        # Check metadata object
        assert "metadata" in doc
        assert doc["metadata"]["name"] == "/path/to/file.pdf"
        assert doc["metadata"]["size"] == 1024000
        assert doc["metadata"]["created_time"] == 1704067200
        assert doc["metadata"]["modified_time"] == 1704153600
        assert doc["metadata"]["source"] == "s3://bucket/file.pdf"
        assert doc["metadata"]["mimetype"] == "application/pdf"
        assert doc["metadata"]["extension"] == "pdf"
        assert doc["metadata"]["page_count"] == 10

    def test_metadata_aggregation_missing_columns(self, *, batch_processor):
        """Test that missing metadata columns are silently ignored or derived."""
        row_data = {
            "doc_id_hash": "doc_1",
            "content": "Sample text",
            "embeddings": [0.1, 0.2, 0.3],
            "name": "/path/to/file.pdf",
            "size": 1024000,
            # Missing: created_time, modified_time, source, page_count
            # Note: extension and mimetype will be derived from name
        }

        doc = batch_processor.prepare_document(row_data=row_data)

        # Check metadata only contains present columns
        assert "metadata" in doc
        assert doc["metadata"]["name"] == "/path/to/file.pdf"
        assert doc["metadata"]["size"] == 1024000
        assert "created_time" not in doc["metadata"]
        assert "modified_time" not in doc["metadata"]
        assert "source" not in doc["metadata"]
        assert "page_count" not in doc["metadata"]
        # Extension and mimetype are now derived from name
        assert doc["metadata"]["extension"] == "pdf"
        assert doc["metadata"]["mimetype"] == "application/pdf"

    def test_metadata_aggregation_none_values_excluded(self, *, batch_processor):
        """Test that None values are excluded from metadata."""
        row_data = {
            "doc_id_hash": "doc_1",
            "content": "Sample text",
            "embeddings": [0.1, 0.2, 0.3],
            "name": "/path/to/file.pdf",
            "size": None,  # None value
            "created_time": 1704067200,
            "source": None,  # None value
        }

        doc = batch_processor.prepare_document(row_data=row_data)

        # Check metadata excludes None values
        assert "metadata" in doc
        assert doc["metadata"]["name"] == "/path/to/file.pdf"
        assert doc["metadata"]["created_time"] == 1704067200
        assert "size" not in doc["metadata"]
        assert "source" not in doc["metadata"]

    def test_metadata_aggregation_empty_when_no_columns(self, *, batch_processor):
        """Test that metadata is not added when no metadata columns present."""
        row_data = {
            "doc_id_hash": "doc_1",
            "content": "Sample text",
            "embeddings": [0.1, 0.2, 0.3],
            # No metadata columns
        }

        doc = batch_processor.prepare_document(row_data=row_data)

        # Check metadata is not added
        assert "metadata" not in doc

    def test_metadata_with_mapped_column(self, *, mock_client, available_features):
        """Test that metadata column can be both mapped and in metadata."""
        feature_mappings = {
            "doc_id_hash": "id",
            "content": "text",
            "embeddings": "vector",
            "name": "document_name",  # Explicitly mapped
        }

        processor = OpenSearchBatchProcessor(
            client=mock_client,
            index_name="test_index",
            available_features=available_features,
            feature_mappings=feature_mappings,
        )

        row_data = {
            "doc_id_hash": "doc_1",
            "content": "Sample text",
            "embeddings": [0.1, 0.2, 0.3],
            "name": "/path/to/file.pdf",
            "size": 1024000,
        }

        doc = processor.prepare_document(row_data=row_data)

        # Check name is in both mapped field and metadata
        assert doc["document_name"] == "/path/to/file.pdf"
        assert "metadata" in doc
        assert doc["metadata"]["name"] == "/path/to/file.pdf"
        assert doc["metadata"]["size"] == 1024000

    def test_metadata_aggregation_binary_data_excluded(self, *, batch_processor):
        """Test that binary data is excluded from metadata."""
        row_data = {
            "doc_id_hash": "doc_1",
            "content": "Sample text",
            "embeddings": [0.1, 0.2, 0.3],
            "name": b"binary_name",  # Binary data
            "size": 1024000,
        }

        doc = batch_processor.prepare_document(row_data=row_data)

        # Check binary data excluded from metadata
        assert "metadata" in doc
        assert "name" not in doc["metadata"]
        assert doc["metadata"]["size"] == 1024000

    def test_metadata_aggregation_numpy_arrays_converted(self, *, batch_processor):
        """Test that numpy arrays in metadata are converted to lists."""
        import numpy as np

        row_data = {
            "doc_id_hash": "doc_1",
            "content": "Sample text",
            "embeddings": [0.1, 0.2, 0.3],
            "name": "/path/to/file.pdf",
            "size": np.int64(1024000),  # Numpy type
        }

        doc = batch_processor.prepare_document(row_data=row_data)

        # Check numpy type converted
        assert "metadata" in doc
        assert doc["metadata"]["name"] == "/path/to/file.pdf"
        assert doc["metadata"]["size"] == 1024000
        assert isinstance(doc["metadata"]["size"], int)

    def test_metadata_columns_constant(self):
        """Test that METADATA_COLUMNS constant contains expected columns."""
        expected_columns = [
            "name",
            "size",
            "created_time",
            "modified_time",
            "source",
            "mimetype",
            "extension",
            "page_count",
        ]

        assert METADATA_COLUMNS == expected_columns


class TestIndexMappingWithMetadata:
    """Test index mapping generation with metadata object."""

    @pytest.fixture
    def mock_client(self):
        """Create mock OpenSearch client."""
        client = Mock(spec=OpenSearch)
        client.indices = MagicMock()
        client.indices.exists.return_value = False
        return client

    @pytest.fixture
    def available_features(self):
        """Standard available features configuration."""
        return {
            "doc_id_hash": {
                "available_for_vector_db": True,
                "mandatory_for_vector_db": True,
                "type": "string",
                "is_primary": True,
            },
            "content": {
                "available_for_vector_db": True,
                "type": "string",
            },
            "embeddings": {
                "available_for_vector_db": True,
                "mandatory_for_vector_db": True,
                "type": "vector",
            },
        }

    @pytest.fixture
    def feature_mappings(self):
        """Standard feature mappings."""
        return {
            "doc_id_hash": "id",
            "content": "text",
            "embeddings": "vector",
        }

    @pytest.fixture
    def index_manager(self, *, mock_client, available_features, feature_mappings):
        """Create index manager instance."""
        return OpenSearchIndexManager(
            client=mock_client,
            index_name="test_index",
            available_features=available_features,
            feature_mappings=feature_mappings,
        )

    def test_metadata_object_in_mapping(self, *, index_manager):
        """Test that metadata object is added to index mapping."""
        dimension_mapping = {"embeddings": 384}
        mapping = index_manager.create_index_mapping(dimension_mapping=dimension_mapping)

        properties = mapping["mappings"]["properties"]

        # Check metadata object exists
        assert "metadata" in properties
        assert properties["metadata"]["type"] == "object"
        assert properties["metadata"]["dynamic"] is True

    def test_metadata_mapping_with_other_fields(self, *, index_manager):
        """Test that metadata mapping coexists with other field mappings."""
        dimension_mapping = {"embeddings": 384}
        mapping = index_manager.create_index_mapping(dimension_mapping=dimension_mapping)

        properties = mapping["mappings"]["properties"]

        # Check all expected fields
        assert "id" in properties
        assert "text" in properties
        assert "vector" in properties
        assert "metadata" in properties

        # Check vector field configuration
        assert properties["vector"]["type"] == "knn_vector"
        assert properties["vector"]["dimension"] == 384

    def test_index_body_includes_metadata(self, *, index_manager):
        """Test that full index body includes metadata mapping."""
        dimension_mapping = {"embeddings": 384}

        index_body = index_manager.build_index_body(dimension_mapping=dimension_mapping)

        properties = index_body["mappings"]["properties"]

        # Check metadata in full index body
        assert "metadata" in properties
        assert properties["metadata"]["type"] == "object"
        assert properties["metadata"]["dynamic"] is True

        # Check settings exist
        assert "settings" in index_body


class TestMetadataAggregationIntegration:
    """Integration tests for metadata aggregation workflow."""

    @pytest.fixture
    def mock_client(self):
        """Create mock OpenSearch client."""
        return Mock(spec=OpenSearch)

    def test_full_document_preparation_workflow(self, *, mock_client):
        """Test complete workflow from row data to prepared document."""
        available_features = {
            "doc_id_hash": {
                "available_for_vector_db": True,
                "type": "string",
                "is_primary": True,
            },
            "content": {"available_for_vector_db": True, "type": "string"},
            "embeddings": {"available_for_vector_db": True, "type": "vector"},
        }

        feature_mappings = {
            "doc_id_hash": "id",
            "content": "text",
            "embeddings": "vector",
        }

        processor = OpenSearchBatchProcessor(
            client=mock_client,
            index_name="test_index",
            available_features=available_features,
            feature_mappings=feature_mappings,
        )

        # Simulate row from IngestLocalOperator + ExtractOperator
        row_data = {
            "doc_id_hash": "doc_123",
            "content": "This is a sample document content.",
            "embeddings": [0.1, 0.2, 0.3, 0.4],
            # IngestLocalOperator columns
            "name": "/data/documents/sample.pdf",
            "size": 2048000,
            "created_time": 1704067200,
            "modified_time": 1704153600,
            # ExtractOperator columns
            "page_count": 15,
        }

        doc = processor.prepare_document(row_data=row_data)

        # Verify structure
        assert doc["id"] == "doc_123"
        assert doc["text"] == "This is a sample document content."
        assert doc["vector"] == [0.1, 0.2, 0.3, 0.4]

        # Verify metadata aggregation
        assert "metadata" in doc
        metadata = doc["metadata"]
        assert metadata["name"] == "/data/documents/sample.pdf"
        assert metadata["size"] == 2048000
        assert metadata["created_time"] == 1704067200
        assert metadata["modified_time"] == 1704153600
        assert metadata["page_count"] == 15
        # Extension and mimetype are now derived from name
        assert metadata["extension"] == "pdf"
        assert metadata["mimetype"] == "application/pdf"

        # Verify expected field count (now includes derived fields)
        assert len(metadata) == 7

    def test_path_column_normalized_to_source(self, *, mock_client):
        """Test that 'path' column is normalized to 'source' in metadata."""
        available_features = {
            "doc_id_hash": {"available_for_vector_db": True, "type": "string"},
            "content": {"available_for_vector_db": True, "type": "string"},
            "embeddings": {"available_for_vector_db": True, "type": "vector"},
        }

        feature_mappings = {
            "doc_id_hash": "id",
            "content": "text",
            "embeddings": "vector",
        }

        processor = OpenSearchBatchProcessor(
            client=mock_client,
            index_name="test_index",
            available_features=available_features,
            feature_mappings=feature_mappings,
        )

        # Simulate row from IngestLocalOperator (uses 'path' not 'source')
        row_data = {
            "doc_id_hash": "doc_789",
            "content": "Local document content",
            "embeddings": [0.8, 0.9, 1.0],
            "path": "/local/path/to/document.pdf",  # IngestLocalOperator uses 'path'
            "name": "document.pdf",
            "size": 1024000,
        }

        doc = processor.prepare_document(row_data=row_data)

        # Verify 'path' was normalized to 'source' in metadata
        assert "metadata" in doc
        assert doc["metadata"]["source"] == "/local/path/to/document.pdf"
        assert doc["metadata"]["name"] == "document.pdf"

    def test_pages_processed_normalized_to_page_count(self, *, mock_client):
        """Test that 'pages_processed' column is normalized to 'page_count' in metadata."""
        available_features = {
            "doc_id_hash": {"available_for_vector_db": True, "type": "string"},
            "content": {"available_for_vector_db": True, "type": "string"},
            "embeddings": {"available_for_vector_db": True, "type": "vector"},
        }

        feature_mappings = {
            "doc_id_hash": "id",
            "content": "text",
            "embeddings": "vector",
        }

        processor = OpenSearchBatchProcessor(
            client=mock_client,
            index_name="test_index",
            available_features=available_features,
            feature_mappings=feature_mappings,
        )

        # Simulate row from ExtractOperator (uses 'pages_processed' not 'page_count')
        row_data = {
            "doc_id_hash": "doc_101",
            "content": "Extracted document content",
            "embeddings": [0.3, 0.4, 0.5],
            "pages_processed": 25,  # ExtractOperator uses 'pages_processed'
            "name": "report.pdf",
        }

        doc = processor.prepare_document(row_data=row_data)

        # Verify 'pages_processed' was normalized to 'page_count' in metadata
        assert "metadata" in doc
        assert doc["metadata"]["page_count"] == 25

    def test_extension_derived_from_name(self, *, mock_client):
        """Test that extension is derived from name when not present."""
        available_features = {
            "doc_id_hash": {"available_for_vector_db": True, "type": "string"},
            "content": {"available_for_vector_db": True, "type": "string"},
            "embeddings": {"available_for_vector_db": True, "type": "vector"},
        }

        feature_mappings = {
            "doc_id_hash": "id",
            "content": "text",
            "embeddings": "vector",
        }

        processor = OpenSearchBatchProcessor(
            client=mock_client,
            index_name="test_index",
            available_features=available_features,
            feature_mappings=feature_mappings,
        )

        # Row without explicit extension field
        row_data = {
            "doc_id_hash": "doc_202",
            "content": "Document content",
            "embeddings": [0.1, 0.2, 0.3],
            "name": "document.docx",
            # No 'extension' field
        }

        doc = processor.prepare_document(row_data=row_data)

        # Verify extension was derived from name
        assert "metadata" in doc
        assert doc["metadata"]["extension"] == "docx"

    def test_mimetype_derived_from_extension(self, *, mock_client):
        """Test that mimetype is derived from extension when not present."""
        available_features = {
            "doc_id_hash": {"available_for_vector_db": True, "type": "string"},
            "content": {"available_for_vector_db": True, "type": "string"},
            "embeddings": {"available_for_vector_db": True, "type": "vector"},
        }

        feature_mappings = {
            "doc_id_hash": "id",
            "content": "text",
            "embeddings": "vector",
        }

        processor = OpenSearchBatchProcessor(
            client=mock_client,
            index_name="test_index",
            available_features=available_features,
            feature_mappings=feature_mappings,
        )

        # Row without explicit mimetype field
        row_data = {
            "doc_id_hash": "doc_303",
            "content": "PDF content",
            "embeddings": [0.4, 0.5, 0.6],
            "name": "document.pdf",
            # No 'mimetype' field
        }

        doc = processor.prepare_document(row_data=row_data)

        # Verify mimetype was derived from extension
        assert "metadata" in doc
        assert doc["metadata"]["mimetype"] == "application/pdf"
        assert doc["metadata"]["extension"] == "pdf"

    def test_ingest_source_operator_metadata(self, *, mock_client):
        """Test metadata from IngestSourceOperator."""
        available_features = {
            "doc_id_hash": {"available_for_vector_db": True, "type": "string"},
            "content": {"available_for_vector_db": True, "type": "string"},
            "embeddings": {"available_for_vector_db": True, "type": "vector"},
        }

        feature_mappings = {
            "doc_id_hash": "id",
            "content": "text",
            "embeddings": "vector",
        }

        processor = OpenSearchBatchProcessor(
            client=mock_client,
            index_name="test_index",
            available_features=available_features,
            feature_mappings=feature_mappings,
        )

        # Simulate row from IngestSourceOperator
        row_data = {
            "doc_id_hash": "doc_456",
            "content": "Document from S3",
            "embeddings": [0.5, 0.6, 0.7],
            # IngestSourceOperator columns
            "name": "documents/report.docx",
            "size": 512000,
            "created_time": 1704240000,
            "modified_time": 1704326400,
            "source": "s3://my-bucket/documents/report.docx",
            "mimetype": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "extension": "docx",
        }

        doc = processor.prepare_document(row_data=row_data)

        # Verify metadata from IngestSourceOperator
        metadata = doc["metadata"]
        assert metadata["name"] == "documents/report.docx"
        assert metadata["size"] == 512000
        assert metadata["source"] == "s3://my-bucket/documents/report.docx"
        assert metadata["mimetype"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        assert metadata["extension"] == "docx"
