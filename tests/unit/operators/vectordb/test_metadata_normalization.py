"""
Unit tests for metadata column normalization in OpenSearchBatchProcessor.
"""

from unittest.mock import Mock

import pytest
from opensearchpy import OpenSearch

from docpipe.core.operators.vectordb.adapters.outbound.opensearch.batch_processor import OpenSearchBatchProcessor


class TestMetadataColumnNormalization:
    """Test metadata column name normalization and derivation."""

    @pytest.fixture
    def mock_client(self):
        """Create mock OpenSearch client."""
        return Mock(spec=OpenSearch)

    @pytest.fixture
    def batch_processor(self, *, mock_client):
        """Create a batch processor instance for testing."""
        return OpenSearchBatchProcessor(
            client=mock_client,
            index_name="test_index",
            batch_size=100,
        )

    def test_metadata_column_alias_path_to_source(self, *, batch_processor):
        """Test that 'path' column is normalized to 'source'."""
        row_data = {
            "path": "/path/to/document.pdf",
            "name": "document.pdf",
        }

        value = batch_processor._normalize_metadata_column(row_data=row_data, target_name="source")

        assert value == "/path/to/document.pdf"

    def test_metadata_column_alias_pages_processed_to_page_count(self, *, batch_processor):
        """Test that 'pages_processed' column is normalized to 'page_count'."""
        row_data = {
            "pages_processed": 42,
            "name": "document.pdf",
        }

        value = batch_processor._normalize_metadata_column(row_data=row_data, target_name="page_count")

        assert value == 42

    def test_extension_derived_from_name(self, *, batch_processor):
        """Test that extension is derived from name field."""
        row_data = {
            "name": "document.pdf",
        }

        value = batch_processor._normalize_metadata_column(row_data=row_data, target_name="extension")

        assert value == "pdf"

    def test_extension_derived_from_path(self, *, batch_processor):
        """Test that extension is derived from path field."""
        row_data = {
            "path": "/path/to/document.docx",
        }

        value = batch_processor._normalize_metadata_column(row_data=row_data, target_name="extension")

        assert value == "docx"

    def test_extension_derived_from_source(self, *, batch_processor):
        """Test that extension is derived from source field."""
        row_data = {
            "source": "https://example.com/document.txt",
        }

        value = batch_processor._normalize_metadata_column(row_data=row_data, target_name="extension")

        assert value == "txt"

    def test_extension_prioritizes_name_over_path(self, *, batch_processor):
        """Test that name is checked before path for extension derivation."""
        row_data = {
            "name": "document.pdf",
            "path": "/path/to/document.docx",
        }

        value = batch_processor._normalize_metadata_column(row_data=row_data, target_name="extension")

        assert value == "pdf"

    def test_extension_returns_none_when_no_extension(self, *, batch_processor):
        """Test that extension returns None when file has no extension."""
        row_data = {
            "name": "document_without_extension",
        }

        value = batch_processor._normalize_metadata_column(row_data=row_data, target_name="extension")

        assert value is None

    def test_mimetype_derived_from_extension(self, *, batch_processor):
        """Test that mimetype is derived from extension."""
        row_data = {
            "name": "document.pdf",
        }

        value = batch_processor._normalize_metadata_column(row_data=row_data, target_name="mimetype")

        assert value == "application/pdf"

    def test_mimetype_basic_mappings(self, *, batch_processor):
        """Test basic MIME type mappings for common extensions."""
        test_cases = [
            ("document.pdf", "application/pdf"),
            ("file.txt", "text/plain"),
            ("data.json", "application/json"),
            ("config.xml", "application/xml"),
            ("page.html", "text/html"),
            ("readme.md", "text/markdown"),
            ("data.csv", "text/csv"),
            ("new.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            ("new.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        ]

        for filename, expected_mimetype in test_cases:
            row_data = {"name": filename}
            value = batch_processor._normalize_metadata_column(row_data=row_data, target_name="mimetype")
            assert value == expected_mimetype, f"Failed for {filename}"

    def test_mimetype_returns_none_for_unknown_extension(self, *, batch_processor):
        """Test that mimetype returns None for unknown extensions."""
        row_data = {
            "name": "document.unknown",
        }

        value = batch_processor._normalize_metadata_column(row_data=row_data, target_name="mimetype")

        assert value is None

    def test_mimetype_returns_none_when_no_extension(self, *, batch_processor):
        """Test that mimetype returns None when file has no extension."""
        row_data = {
            "name": "document_without_extension",
        }

        value = batch_processor._normalize_metadata_column(row_data=row_data, target_name="mimetype")

        assert value is None

    def test_aggregate_metadata_uses_normalization(self, *, batch_processor):
        """Test that _aggregate_metadata_columns uses normalization."""
        row_data = {
            "path": "/path/to/document.pdf",  # Should map to 'source'
            "pages_processed": 10,  # Should map to 'page_count'
            "name": "document.pdf",
            "size": 1024,
        }

        metadata = batch_processor._aggregate_metadata_columns(row_data=row_data)

        # Check that aliases were resolved
        assert metadata["source"] == "/path/to/document.pdf"
        assert metadata["page_count"] == 10

        # Check that derived fields were added
        assert metadata["extension"] == "pdf"
        assert metadata["mimetype"] == "application/pdf"

        # Check that direct fields were included
        assert metadata["name"] == "document.pdf"
        assert metadata["size"] == 1024

    def test_aggregate_metadata_handles_missing_columns(self, *, batch_processor):
        """Test that aggregation handles missing columns gracefully."""
        row_data = {
            "name": "document.pdf",
        }

        metadata = batch_processor._aggregate_metadata_columns(row_data=row_data)

        # Should have name and derived fields
        assert metadata["name"] == "document.pdf"
        assert metadata["extension"] == "pdf"
        assert metadata["mimetype"] == "application/pdf"

        # Should not have missing fields
        assert "source" not in metadata
        assert "page_count" not in metadata
        assert "size" not in metadata

    def test_normalize_prefers_direct_column_over_alias(self, *, batch_processor):
        """Test that direct column name is preferred over alias."""
        row_data = {
            "source": "direct_source",
            "path": "alias_path",
        }

        value = batch_processor._normalize_metadata_column(row_data=row_data, target_name="source")

        # Should prefer 'source' over 'path'
        assert value == "direct_source"

    def test_normalize_handles_none_values(self, *, batch_processor):
        """Test that normalization skips None values in aliases."""
        row_data = {
            "source": None,
            "path": "/path/to/document.pdf",
        }

        value = batch_processor._normalize_metadata_column(row_data=row_data, target_name="source")

        # Should skip None and use next alias
        assert value == "/path/to/document.pdf"

    def test_mimetype_alias_variations(self, *, batch_processor):
        """Test that mimetype accepts various alias names."""
        test_cases = [
            {"mimetype": "application/pdf"},
            {"mime_type": "application/pdf"},
            {"content_type": "application/pdf"},
        ]

        for row_data in test_cases:
            value = batch_processor._normalize_metadata_column(row_data=row_data, target_name="mimetype")
            assert value == "application/pdf"

    def test_extension_case_insensitive(self, *, batch_processor):
        """Test that extension is normalized to lowercase."""
        row_data = {
            "name": "DOCUMENT.PDF",
        }

        value = batch_processor._normalize_metadata_column(row_data=row_data, target_name="extension")

        assert value == "pdf"

    def test_aggregate_metadata_backward_compatibility(self, *, batch_processor):
        """Test backward compatibility with existing column names."""
        # Test with old-style column names (should still work)
        row_data = {
            "source": "/path/to/document.pdf",
            "page_count": 10,
            "mimetype": "application/pdf",
            "extension": "pdf",
            "name": "document.pdf",
            "size": 1024,
        }

        metadata = batch_processor._aggregate_metadata_columns(row_data=row_data)

        # All fields should be present
        assert metadata["source"] == "/path/to/document.pdf"
        assert metadata["page_count"] == 10
        assert metadata["mimetype"] == "application/pdf"
        assert metadata["extension"] == "pdf"
        assert metadata["name"] == "document.pdf"
        assert metadata["size"] == 1024
