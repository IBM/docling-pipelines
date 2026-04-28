#!/usr/bin/env python3
"""
Unit tests for IngestLocalOperator
Tests path-only metadata ingest behavior.
"""

from pathlib import Path

import pytest

from core.operators.ingest.ingest_local_folder import IngestLocalOperator


EXPECTED_METADATA_COLUMNS = {
    "id",
    "name",
    "path",
    "size",
    "created_time",
    "modified_time",
}


class TestIngestLocalOperator:
    """Test suite for IngestLocalOperator"""

    def test_metadata_only_mode(self, temp_test_dir):
        """Test metadata-only mode returns path-based metadata columns only."""
        config = {
            "input_folder": temp_test_dir,
            "max_files": 10,
            "force_ingest": True,
        }

        operator = IngestLocalOperator(config)
        tables, metadata = operator.transform(None)
        table = tables[0]

        assert table.num_rows > 0, "Should have ingested files"
        assert set(table.column_names) == EXPECTED_METADATA_COLUMNS
        assert "content" not in table.column_names

        for idx in range(table.num_rows):
            path = table["path"][idx].as_py()
            name = table["name"][idx].as_py()
            assert path is not None and len(path) > 0
            assert name == path

        assert metadata["processed_docs"] == table.num_rows

    def test_file_filtering(self, temp_test_dir):
        """Test file filtering by extension."""
        config = {
            "input_folder": temp_test_dir,
            "include_filter": "txt",
            "extract_content": False,
            "max_files": 10,
            "force_ingest": True,
        }

        operator = IngestLocalOperator(config)
        tables, metadata = operator.transform(None)
        table = tables[0]

        assert set(table.column_names) == EXPECTED_METADATA_COLUMNS

        for idx in range(table.num_rows):
            name = table["name"][idx].as_py()
            path = table["path"][idx].as_py()
            assert name.endswith(".txt"), "Should only include .txt files"
            assert path.endswith(".txt"), "Path should match filtered extension"

    def test_max_files_limit(self, temp_test_dir):
        """Test max_files limit."""
        config = {
            "input_folder": temp_test_dir,
            "extract_content": False,
            "max_files": 1,
            "force_ingest": True,
        }

        operator = IngestLocalOperator(config)
        tables, metadata = operator.transform(None)
        table = tables[0]

        assert table.num_rows <= 1, "Should respect max_files limit"
        assert set(table.column_names) == EXPECTED_METADATA_COLUMNS

    def test_get_metadata(self, temp_test_dir):
        """Test get_metadata method."""
        metadata = IngestLocalOperator.get_metadata()

        assert "features" in metadata
        assert "path" in metadata["features"]
        assert "binary_content" not in metadata["features"]
        assert "attributes" in metadata
        assert "store_binary_content" not in metadata["attributes"]

    def test_path_column_contains_expected_file_paths(self, temp_test_dir):
        """Test path column always exists and contains absolute file paths."""
        config = {
            "input_folder": temp_test_dir,
            "max_files": 10,
            "force_ingest": True,
        }

        operator = IngestLocalOperator(config)
        tables, _metadata = operator.transform(None)
        table = tables[0]

        paths = table["path"].to_pylist()
        assert paths
        for path in paths:
            assert path.startswith(temp_test_dir)
            assert Path(path).exists()


def test_ingest_local_operator_basic():
    """Basic test without fixtures for simple verification."""
    fixtures_dir = Path(__file__).parent.parent.parent.parent / "fixtures" / "invoices"

    if not fixtures_dir.exists():
        pytest.skip(f"Fixtures directory not found: {fixtures_dir}")

    config = {
        "input_folder": str(fixtures_dir),
        "include_filter": "pdf",
        "max_files": 5,
        "force_ingest": True,
    }

    operator = IngestLocalOperator(config)
    tables, metadata = operator.transform(None)
    table = tables[0]

    assert table.num_rows > 0, "Should have ingested PDF files"
    assert set(table.column_names) == EXPECTED_METADATA_COLUMNS
    assert "content" not in table.column_names
    assert all(path.endswith(".pdf") for path in table["path"].to_pylist())
    assert metadata["processed_docs"] == table.num_rows


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
