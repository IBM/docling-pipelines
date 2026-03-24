#!/usr/bin/env python3
"""
Unit tests for IngestLocalOperator
Tests both metadata-only mode and legacy extraction mode
"""

from pathlib import Path
import pytest

from core.operators.ingest.ingest_local_folder import IngestLocalOperator


class TestIngestLocalOperator:
    """Test suite for IngestLocalOperator"""

    def test_metadata_only_mode(self, temp_test_dir):
        """Test metadata-only mode with binary content storage"""
        config = {
            "input_folder": temp_test_dir,
            "store_binary_content": True,
            "max_files": 10,
            "force_ingest": True,  # Skip incremental processing for tests
        }

        operator = IngestLocalOperator(config)
        tables, metadata = operator.transform(None)
        table = tables[0]

        # Verify table structure
        assert table.num_rows > 0, "Should have ingested files"
        assert "path" in table.column_names, "Should have path column"
        assert "binary_content" in table.column_names, (
            "Should have binary_content column"
        )
        assert "content" not in table.column_names, (
            "Should NOT have content column in metadata-only mode"
        )

        # Verify metadata
        assert "id" in table.column_names
        assert "name" in table.column_names
        assert "size" in table.column_names

        # Verify binary content is stored
        for idx in range(table.num_rows):
            binary_content = table["binary_content"][idx].as_py()
            assert binary_content is not None, "Binary content should be stored"
            assert len(binary_content) > 0, "Binary content should not be empty"

    def test_metadata_only_without_binary(self, temp_test_dir):
        """Test metadata-only mode without storing binary content"""
        config = {
            "input_folder": temp_test_dir,
            "store_binary_content": False,
            "max_files": 10,
            "force_ingest": True,  # Skip incremental processing for tests
        }

        operator = IngestLocalOperator(config)
        tables, metadata = operator.transform(None)
        table = tables[0]

        # Verify table structure
        assert table.num_rows > 0, "Should have ingested files"
        assert "path" in table.column_names, "Should have path column"
        assert "binary_content" not in table.column_names, (
            "Should NOT have binary_content when store_binary_content=False"
        )
        assert "content" not in table.column_names, "Should NOT have content column"

    def test_file_filtering(self, temp_test_dir):
        """Test file filtering by extension"""
        # Test include filter
        config = {
            "input_folder": temp_test_dir,
            "include_filter": "txt",
            "extract_content": False,
            "store_binary_content": True,
            "max_files": 10,
            "force_ingest": True,  # Skip incremental processing for tests
        }

        operator = IngestLocalOperator(config)
        tables, metadata = operator.transform(None)
        table = tables[0]

        # Verify only txt files are included
        for idx in range(table.num_rows):
            name = table["name"][idx].as_py()
            assert name.endswith(".txt"), "Should only include .txt files"

    def test_max_files_limit(self, temp_test_dir):
        """Test max_files limit"""
        config = {
            "input_folder": temp_test_dir,
            "extract_content": False,
            "store_binary_content": True,
            "max_files": 1,
            "force_ingest": True,  # Skip incremental processing for tests
        }

        operator = IngestLocalOperator(config)
        tables, metadata = operator.transform(None)
        table = tables[0]

        # Should respect max_files limit
        assert table.num_rows <= 1, "Should respect max_files limit"

    def test_get_metadata(self, temp_test_dir):
        """Test get_metadata method"""
        # Test metadata-only mode with binary content
        config = {"store_binary_content": True, "input_folder": temp_test_dir}
        operator = IngestLocalOperator(config)
        metadata = operator.get_metadata()

        assert "features" in metadata
        assert "path" in metadata["features"]
        assert "binary_content" in metadata["features"]
        assert "attributes" in metadata
        assert "store_binary_content" in metadata["attributes"]

        # Test metadata-only mode without binary content
        config_no_binary = {
            "store_binary_content": False,
            "input_folder": temp_test_dir,
        }
        operator_no_binary = IngestLocalOperator(config_no_binary)
        metadata_no_binary = operator_no_binary.get_metadata()

        assert "features" in metadata_no_binary
        assert "path" in metadata_no_binary["features"]
        assert "binary_content" not in metadata_no_binary["features"]


def test_ingest_local_operator_basic():
    """Basic test without fixtures for simple verification"""
    # Use the fixtures directory that should exist
    fixtures_dir = Path(__file__).parent.parent.parent.parent / "fixtures" / "invoices"

    if not fixtures_dir.exists():
        pytest.skip(f"Fixtures directory not found: {fixtures_dir}")

    config = {
        "input_folder": str(fixtures_dir),
        "store_binary_content": True,
        "include_filter": "pdf",
        "max_files": 5,
        "force_ingest": True
    }

    operator = IngestLocalOperator(config)
    tables, metadata = operator.transform(None)
    table = tables[0]

    # Basic assertions
    assert table.num_rows > 0, "Should have ingested PDF files"
    assert "path" in table.column_names
    assert "binary_content" in table.column_names
    assert "content" not in table.column_names


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
