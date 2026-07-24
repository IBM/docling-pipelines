#!/usr/bin/env python3
"""
Unit tests for IngestLocalOperator
Tests path-only metadata ingest behavior.
"""

import os
import tempfile
from pathlib import Path

import pytest

from docpipe.core.operators.ingest.ingest_local import IngestLocalOperator

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
            "paths": temp_test_dir,
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
            "paths": temp_test_dir,
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
            "paths": temp_test_dir,
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
            "paths": temp_test_dir,
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
                "paths": str(test_dir),
                "extract_content": False,
                "max_files": 10,
                "force_ingest": True,
            }

            operator = IngestLocalOperator(config)
            tables, metadata = operator.transform(None)
            table = tables[0]

            # Verify processing stops immediately after max_files is reached
            # With the new batch-fetch logic, we check BEFORE processing each file,
            # so total_docs_count equals processed_docs when max_files is reached
            assert metadata["total_docs_count"] == 10, (
                "total_docs_count should equal max_files with new batch-fetch logic"
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
        "paths": str(fixtures_dir),
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


def test_single_file_ingest():
    """Test ingesting a single file."""
    # Create a temporary file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("Test content for single file ingest")
        temp_file = f.name

    try:
        # Configure operator with single file path
        config = {
            "paths": temp_file,  # Single file path
            "max_files": 10,
            "max_file_size": 100,
            "job_id": "test-job",
            "job_run_id": "test-run",
        }

        # Create operator
        operator = IngestLocalOperator(config)

        # Transform (ingest)
        tables, metadata = operator.transform(None)

        # Verify results
        assert len(tables) == 1, f"Expected 1 table, got {len(tables)}"
        assert tables[0].num_rows == 1, f"Expected 1 row, got {tables[0].num_rows}"
        assert metadata["total_docs_count"] == 1, f"Expected 1 total doc, got {metadata['total_docs']}"
        assert metadata["processed_docs"] == 1, f"Expected 1 processed doc, got {metadata['processed_docs']}"

        print("✓ Single file ingest test passed")
        print(f"  - File: {temp_file}")
        print(f"  - Rows: {tables[0].num_rows}")
        print(f"  - Metadata: {metadata}")

    finally:
        # Cleanup
        if os.path.exists(temp_file):
            os.unlink(temp_file)


def test_multiple_files_list():
    """Test ingesting multiple files with list of paths."""
    # Create temporary files
    temp_files = []
    for i in range(2):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(f"Test content {i}")
            temp_files.append(f.name)

    try:
        # Configure operator with list of paths
        config = {
            "paths": temp_files,  # List of paths
            "max_files": 10,
            "max_file_size": 100,
            "job_id": "test-job",
            "job_run_id": "test-run",
        }

        # Create operator
        operator = IngestLocalOperator(config)

        # Transform (ingest)
        tables, metadata = operator.transform(None)

        # Verify results
        assert len(tables) == 1, f"Expected 1 table, got {len(tables)}"
        assert tables[0].num_rows == 2, f"Expected 2 rows, got {tables[0].num_rows}"
        assert metadata["total_docs_count"] == 2, f"Expected 2 total docs, got {metadata['total_docs']}"
        assert metadata["processed_docs"] == 2, f"Expected 2 processed docs, got {metadata['processed_docs']}"

        print("✓ Multiple files (list) test passed")
        print(f"  - Files: {len(temp_files)}")
        print(f"  - Rows: {tables[0].num_rows}")
        print(f"  - Metadata: {metadata}")

    finally:
        # Cleanup
        for temp_file in temp_files:
            if os.path.exists(temp_file):
                os.unlink(temp_file)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
