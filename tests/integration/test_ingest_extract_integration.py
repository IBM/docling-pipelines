#!/usr/bin/env python3
"""
Integration tests for IngestLocalOperator + ExtractOperator sequence.
Tests the complete flow from path-only file ingestion to extraction.
"""

from pathlib import Path

import pytest

from datasift.core.operators.extract.extract_operator import ExtractOperator
from datasift.core.operators.ingest.ingest_local import IngestLocalOperator

EXPECTED_INGEST_COLUMNS = {
    "id",
    "name",
    "path",
    "size",
    "created_time",
    "modified_time",
}


class TestIngestExtractIntegration:
    """Integration tests for Ingest + Extract sequence."""

    @pytest.fixture
    def fixtures_dir(self):
        """Get the fixtures directory."""
        fixtures_path = Path(__file__).parent.parent / "fixtures" / "invoices"
        if not fixtures_path.exists():
            pytest.skip(f"Fixtures directory not found: {fixtures_path}")
        return str(fixtures_path)

    def test_path_only_ingest_to_extract_sequence(self, fixtures_dir):
        """Test the sequence: path-only IngestLocal -> ExtractOperator."""
        ingest_config = {
            "paths": fixtures_dir,
            "include_filter": "pdf",
            "max_files": 3,
            "force_ingest": True,
        }

        ingest_operator = IngestLocalOperator(config=ingest_config)
        ingest_tables, ingest_metadata = ingest_operator.transform(None)
        ingest_table = ingest_tables[0]

        assert ingest_table.num_rows > 0, "Should have ingested files"
        assert set(ingest_table.column_names) == EXPECTED_INGEST_COLUMNS
        assert "doc_content" not in ingest_table.column_names
        assert all(path.endswith(".pdf") for path in ingest_table["path"].to_pylist())
        assert ingest_metadata.get("processed_docs", 0) == ingest_table.num_rows

        extract_config = {
            "text_extraction_mode": "docling_library",
            "entity_extraction_mode": "none",
            "doc_column": "doc_content",
            "extract_tables": True,
            "extract_images": True,
        }

        extract_operator = ExtractOperator(config=extract_config)
        extract_tables, extract_metadata = extract_operator.transform(ingest_table)
        extract_table = extract_tables[0]

        assert extract_table.num_rows > 0, "Should have extracted content"
        assert "doc_content" in extract_table.column_names
        assert "doc_id_hash" in extract_table.column_names
        assert "pages_processed" in extract_table.column_names

        content_count = 0
        for idx in range(extract_table.num_rows):
            content = extract_table["doc_content"][idx].as_py()
            if content and len(content) > 0:
                content_count += 1

        assert content_count > 0, "Should have extracted content from at least one document"
        assert extract_metadata.get("processed_docs", 0) > 0
        assert "pages_by_format" in extract_metadata
        assert "total_pages_converted" in extract_metadata
        assert isinstance(extract_metadata["pages_by_format"], dict)
        assert extract_metadata["total_pages_converted"] > 0

    def test_path_only_ingest_to_combined_docling_text_entity_extraction(self, fixtures_dir):
        """Test combined docling text+entity extraction works with path-only ingest."""
        ingest_config = {
            "paths": fixtures_dir,
            "include_filter": "pdf",
            "max_files": 2,
            "force_ingest": True,
        }

        ingest_operator = IngestLocalOperator(config=ingest_config)
        ingest_tables, _ingest_metadata = ingest_operator.transform(None)
        ingest_table = ingest_tables[0]

        assert set(ingest_table.column_names) == EXPECTED_INGEST_COLUMNS
        assert "binary_content" not in ingest_table.column_names

        extract_config = {
            "text_extraction_mode": "docling_library",
            "entity_extraction_mode": "docling",
            "doc_column": "doc_content",
            "extract_tables": False,
            "extract_images": False,
        }

        extract_operator = ExtractOperator(config=extract_config)
        extract_tables, extract_metadata = extract_operator.transform(ingest_table)
        extract_table = extract_tables[0]

        assert extract_table.num_rows == ingest_table.num_rows
        assert "doc_content" in extract_table.column_names
        assert "doc_id_hash" in extract_table.column_names
        assert "pages_processed" in extract_table.column_names
        assert extract_metadata.get("processed_docs", 0) > 0
        assert "pages_by_format" in extract_metadata
        assert "total_pages_converted" in extract_metadata

    def test_metadata_preservation(self, fixtures_dir):
        """Test that ingest metadata columns are preserved through extraction."""
        ingest_config = {
            "paths": fixtures_dir,
            "include_filter": "pdf",
            "max_files": 2,
            "force_ingest": True,
        }

        ingest_operator = IngestLocalOperator(config=ingest_config)
        ingest_tables, _ = ingest_operator.transform(None)
        ingest_table = ingest_tables[0]

        original_columns = set(ingest_table.column_names)
        assert original_columns == EXPECTED_INGEST_COLUMNS

        extract_config = {
            "text_extraction_mode": "docling_library",
            "entity_extraction_mode": "none",
            "doc_column": "doc_content",
            "extract_tables": False,
            "extract_images": False,
        }

        extract_operator = ExtractOperator(config=extract_config)
        extract_tables, _ = extract_operator.transform(ingest_table)
        extract_table = extract_tables[0]

        final_columns = set(extract_table.column_names)
        assert original_columns.issubset(final_columns), "Original metadata should be preserved"
        assert "doc_content" in final_columns
        assert "doc_id_hash" in final_columns
        assert extract_table.num_rows == ingest_table.num_rows


def test_basic_integration():
    """Basic path-only integration test without fixtures."""
    fixtures_dir = Path(__file__).parent.parent / "fixtures" / "invoices"

    if not fixtures_dir.exists():
        pytest.skip(f"Fixtures directory not found: {fixtures_dir}")

    ingest_config = {
        "paths": str(fixtures_dir),
        "include_filter": "pdf",
        "max_files": 1,
        "force_ingest": True,
    }

    ingest_op = IngestLocalOperator(config=ingest_config)
    ingest_tables, _ = ingest_op.transform(None)

    assert set(ingest_tables[0].column_names) == EXPECTED_INGEST_COLUMNS

    extract_config = {
        "text_extraction_mode": "docling_library",
        "entity_extraction_mode": "none",
        "doc_column": "doc_content",
    }

    extract_op = ExtractOperator(config=extract_config)
    extract_tables, _ = extract_op.transform(ingest_tables[0])

    assert extract_tables[0].num_rows > 0
    assert "doc_content" in extract_tables[0].column_names


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
