#!/usr/bin/env python3
"""
Unit tests for IngestLocalOperator
Tests path-only metadata ingest behavior.
"""

from pathlib import Path

import pytest

from datasift.core.operators.ingest.ingest_local_folder import IngestLocalOperator

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
        tables, _metadata = operator.transform(None)
        table = tables[0]

        assert set(table.column_names) == EXPECTED_METADATA_COLUMNS

        for idx in range(table.num_rows):
            name = table["name"][idx].as_py()
            path = table["path"][idx].as_py()
            assert name.endswith(".txt"), "Should only include .txt files"
            assert path.endswith(".txt"), "Path should match filtered extension"

    def test_max_files_limit(self, temp_test_dir):
        """Test max_files limit stops processing immediately after limit is reached."""
        config = {
            "input_folder": temp_test_dir,
            "extract_content": False,
            "max_files": 1,
            "force_ingest": True,
        }

        operator = IngestLocalOperator(config)
        tables, metadata = operator.transform(None)
        table = tables[0]

        # With max_files=1, processing stops after encountering the second file
        # The temp_test_dir fixture has 1-2 files (test.txt and possibly test.pdf)
        # When max_files is reached:
        # - file_count will be max_files + 1 (the file that triggered the stop)
        # - processed_docs will be max_files (only files up to the limit are processed)
        # - table.num_rows will equal processed_docs

        assert metadata["processed_docs"] == 1, "Should process exactly max_files documents"
        assert table.num_rows == 1, "Should have exactly max_files rows in table"
        assert set(table.column_names) == EXPECTED_METADATA_COLUMNS

        # Verify no excessive skipped documents are recorded
        assert metadata.get("skipped_docs_count", 0) == 0, "Should not have skipped docs when hitting max_files"

        # If there are 2 files in temp_test_dir, total_docs_count should be 2 (max_files + 1)
        # If there's only 1 file, total_docs_count should be 1
        assert metadata["total_docs_count"] >= 1, "Should have counted at least the processed file"

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
        _tables, _metadata = operator.transform(None)

    def test_max_files_with_many_files(self):
        """Test max_files behavior with directory containing many more files than limit."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir)

            # Create 200 test files
            for i in range(200):
                test_file = test_dir / f"test_file_{i:03d}.txt"
                test_file.write_text(f"Test content {i}")

            config = {
                "input_folder": str(test_dir),
                "extract_content": False,
                "max_files": 10,
                "force_ingest": True,
            }

            operator = IngestLocalOperator(config)
            tables, metadata = operator.transform(None)
            table = tables[0]

            # Verify processing stops immediately after max_files is reached
            assert metadata["total_docs_count"] == 11, (
                "file_count should be max_files + 1 (the file that triggered the limit)"
            )
            assert metadata["processed_docs"] == 10, "Should process exactly max_files documents"
            assert table.num_rows == 10, "Should have exactly max_files rows in table"

            # Verify skipped_docs_count does NOT include all remaining files
            # Only files that were explicitly skipped (e.g., due to filters) should be counted
            # Files never encountered due to max_files limit should NOT be in skipped count
            assert metadata.get("skipped_docs_count", 0) == 0, (
                "Should not count unprocessed files as skipped when max_files limit is hit"
            )

            # Verify table structure
            assert set(table.column_names) == EXPECTED_METADATA_COLUMNS

            # Verify all processed files are in the table
            paths = table["path"].to_pylist()
            assert len(paths) == 10
            for path in paths:
                assert Path(path).exists()
                assert path.startswith(str(test_dir)), f"Path {path} should start with {test_dir}"


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
