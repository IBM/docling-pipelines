#!/usr/bin/env python3
"""
Integration tests for IngestLocalOperator + ExtractDoclingOperator sequence
Tests the complete flow from file ingestion to content extraction
"""

from pathlib import Path
import pytest

from core.operators.ingest.ingest_local_folder import IngestLocalOperator
from core.operators.extract.extract_docling import ExtractDoclingOperator


class TestIngestExtractIntegration:
    """Integration tests for Ingest + Extract sequence"""

    @pytest.fixture
    def fixtures_dir(self):
        """Get the fixtures directory"""
        fixtures_path = Path(__file__).parent.parent / "fixtures" / "invoices"
        if not fixtures_path.exists():
            pytest.skip(f"Fixtures directory not found: {fixtures_path}")
        return str(fixtures_path)

    def test_metadata_only_to_extract_sequence(self, fixtures_dir):
        """Test the complete sequence: IngestLocal (metadata-only) -> ExtractDocling"""
        # Step 1: Ingest with metadata-only mode
        ingest_config = {
            "input_folder": fixtures_dir,
            "include_filter": "pdf",
            "store_binary_content": True,
            "max_files": 3,
            "force_ingest": True,  # Skip incremental processing for tests
        }

        ingest_operator = IngestLocalOperator(ingest_config)
        ingest_tables, ingest_metadata = ingest_operator.transform(None)
        ingest_table = ingest_tables[0]

        # Verify ingest output
        assert ingest_table.num_rows > 0, "Should have ingested files"
        assert "path" in ingest_table.column_names, "Should have path column"
        assert "binary_content" in ingest_table.column_names, (
            "Should have binary_content column"
        )
        assert "content" not in ingest_table.column_names, "Should NOT have content yet"

        # Step 2: Extract content using Docling
        extract_config = {
            "doc_column": "content",
            "extract_tables": True,
            "extract_images": True,
            "use_template": False,
        }

        extract_operator = ExtractDoclingOperator(extract_config)
        extract_tables, extract_metadata = extract_operator.transform(ingest_table)
        extract_table = extract_tables[0]

        # Verify extract output
        assert extract_table.num_rows > 0, "Should have extracted content"
        assert "content" in extract_table.column_names, "Should have content column"
        assert "doc_id_hash" in extract_table.column_names, (
            "Should have doc_id_hash column"
        )

        # Verify content was actually extracted
        content_count = 0
        for idx in range(extract_table.num_rows):
            content = extract_table["content"][idx].as_py()
            if content and len(content) > 0:
                content_count += 1

        assert content_count > 0, (
            "Should have extracted content from at least one document"
        )
        assert extract_metadata.get("processed_docs", 0) > 0, (
            "Should have processed documents"
        )

    def test_path_only_to_extract_sequence(self, fixtures_dir):
        """Test sequence with path-only (no binary content stored)"""
        # Step 1: Ingest with path-only mode
        ingest_config = {
            "input_folder": fixtures_dir,
            "include_filter": "pdf",
            "store_binary_content": False,  # Don't store binary content
            "max_files": 2,
            "force_ingest": True,  # Skip incremental processing for tests
        }

        ingest_operator = IngestLocalOperator(ingest_config)
        ingest_tables, ingest_metadata = ingest_operator.transform(None)
        ingest_table = ingest_tables[0]

        # Verify ingest output
        assert ingest_table.num_rows > 0, "Should have ingested files"
        assert "path" in ingest_table.column_names, "Should have path column"
        assert "binary_content" not in ingest_table.column_names, (
            "Should NOT have binary_content"
        )

        # Step 2: Extract content using paths
        extract_config = {
            "doc_column": "content",
            "extract_tables": True,
            "extract_images": False,
            "use_template": False,
        }

        extract_operator = ExtractDoclingOperator(extract_config)
        extract_tables, extract_metadata = extract_operator.transform(ingest_table)
        extract_table = extract_tables[0]

        # Verify extract output
        assert extract_table.num_rows > 0, "Should have extracted content"
        assert "content" in extract_table.column_names, "Should have content column"

        # Verify content was extracted from paths
        content_count = 0
        for idx in range(extract_table.num_rows):
            content = extract_table["content"][idx].as_py()
            if content and len(content) > 0:
                content_count += 1

        assert content_count > 0, "Should have extracted content using file paths"

    def test_metadata_preservation(self, fixtures_dir):
        """Test that metadata is preserved through the pipeline"""
        # Step 1: Ingest
        ingest_config = {
            "input_folder": fixtures_dir,
            "include_filter": "pdf",
            "store_binary_content": True,
            "max_files": 2,
            "force_ingest": True,  # Skip incremental processing for tests
        }

        ingest_operator = IngestLocalOperator(ingest_config)
        ingest_tables, _ = ingest_operator.transform(None)
        ingest_table = ingest_tables[0]

        # Get original metadata columns
        original_columns = set(ingest_table.column_names)

        # Step 2: Extract
        extract_config = {
            "doc_column": "content",
            "extract_tables": False,
            "extract_images": False,
        }

        extract_operator = ExtractDoclingOperator(extract_config)
        extract_tables, _ = extract_operator.transform(ingest_table)
        extract_table = extract_tables[0]

        # Verify all original columns are preserved
        final_columns = set(extract_table.column_names)
        assert original_columns.issubset(final_columns), (
            "Original metadata should be preserved"
        )

        # Verify new columns were added
        assert "content" in final_columns, "Content column should be added"
        assert "doc_id_hash" in final_columns, "Hash column should be added"

        # Verify row count is preserved
        assert extract_table.num_rows == ingest_table.num_rows, (
            "Row count should be preserved"
        )


def test_basic_integration():
    """Basic integration test without fixtures"""
    fixtures_dir = Path(__file__).parent.parent / "fixtures" / "invoices"

    if not fixtures_dir.exists():
        pytest.skip(f"Fixtures directory not found: {fixtures_dir}")

    # Quick integration test
    ingest_config = {
        "input_folder": str(fixtures_dir),
        "store_binary_content": True,
        "include_filter": "pdf",
        "max_files": 1,
        "force_ingest": True,  # Skip incremental processing for tests
    }

    ingest_op = IngestLocalOperator(ingest_config)
    ingest_tables, _ = ingest_op.transform(None)

    extract_config = {"doc_column": "content"}

    extract_op = ExtractDoclingOperator(extract_config)
    extract_tables, _ = extract_op.transform(ingest_tables[0])

    assert extract_tables[0].num_rows > 0
    assert "content" in extract_tables[0].column_names


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
