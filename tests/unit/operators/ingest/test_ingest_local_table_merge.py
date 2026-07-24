#!/usr/bin/env python3
"""
Unit tests for IngestLocalOperator table merge functionality.
Tests table concatenation for path-only ingest schema.
"""

from pathlib import Path

import pyarrow as pa
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


class TestIngestLocalOperatorTableMerge:
    """Test suite for IngestLocalOperator table merge functionality."""

    def test_transform_with_none_input_table(self, temp_test_dir):
        """Test transform with None input table."""
        config = {
            "paths": temp_test_dir,
            "max_files": 10,
            "force_ingest": True,
        }

        operator = IngestLocalOperator(config)
        tables, metadata = operator.transform(None)
        table = tables[0]

        assert table is not None
        assert table.num_rows > 0
        assert set(table.column_names) == EXPECTED_METADATA_COLUMNS
        assert metadata["processed_docs"] == table.num_rows

    def test_transform_with_existing_input_table(self, temp_test_dir):
        """Test transform with existing input table concatenates path-only rows."""
        input_data = [
            {
                "id": "existing_1",
                "name": "/path/to/existing1.txt",
                "path": "/path/to/existing1.txt",
                "size": 100,
                "created_time": 1234567890,
                "modified_time": 1234567890,
            },
            {
                "id": "existing_2",
                "name": "/path/to/existing2.txt",
                "path": "/path/to/existing2.txt",
                "size": 200,
                "created_time": 1234567891,
                "modified_time": 1234567891,
            },
        ]
        input_table = pa.Table.from_pylist(input_data)

        config = {
            "paths": temp_test_dir,
            "max_files": 10,
            "force_ingest": True,
        }

        operator = IngestLocalOperator(config)
        tables, metadata = operator.transform(input_table)
        result_table = tables[0]

        assert result_table.num_rows > input_table.num_rows
        assert result_table.num_rows >= 2
        assert EXPECTED_METADATA_COLUMNS.issubset(set(result_table.column_names))
        assert "binary_content" not in result_table.column_names
        assert result_table.num_rows == input_table.num_rows + metadata["processed_docs"]

    def test_transform_with_schema_mismatch(self, temp_test_dir):
        """Test transform handles schema differences gracefully."""
        input_data = [
            {
                "id": "existing_1",
                "name": "/path/to/existing1.txt",
                "custom_field": "custom_value",
            }
        ]
        input_table = pa.Table.from_pylist(input_data)

        config = {
            "paths": temp_test_dir,
            "max_files": 10,
            "force_ingest": True,
        }

        operator = IngestLocalOperator(config)
        tables, metadata = operator.transform(input_table)
        result_table = tables[0]

        assert result_table.num_rows > input_table.num_rows
        assert "id" in result_table.column_names
        assert "name" in result_table.column_names
        assert "custom_field" in result_table.column_names
        assert "path" in result_table.column_names
        assert "binary_content" not in result_table.column_names
        assert metadata["processed_docs"] > 0

        first_row_custom = result_table["custom_field"][0].as_py()
        assert first_row_custom == "custom_value"

        last_row_custom = result_table["custom_field"][result_table.num_rows - 1].as_py()
        assert last_row_custom is None

    def test_transform_preserves_input_table_data(self, temp_test_dir):
        """Test that input table data is preserved in concatenation."""
        input_data = [
            {
                "id": "test_id_123",
                "name": "/unique/path/test.txt",
                "path": "/unique/path/test.txt",
                "size": 999,
                "created_time": 1111111111,
                "modified_time": 1111111111,
            }
        ]
        input_table = pa.Table.from_pylist(input_data)

        config = {
            "paths": temp_test_dir,
            "max_files": 10,
            "force_ingest": True,
        }

        operator = IngestLocalOperator(config)
        tables, metadata = operator.transform(input_table)
        result_table = tables[0]

        found_original = False
        for idx in range(result_table.num_rows):
            row_id = result_table["id"][idx].as_py()
            if row_id == "test_id_123":
                found_original = True
                assert result_table["name"][idx].as_py() == "/unique/path/test.txt"
                assert result_table["path"][idx].as_py() == "/unique/path/test.txt"
                assert result_table["size"][idx].as_py() == 999
                break

        assert found_original, "Original input table data should be preserved"
        assert metadata["processed_docs"] > 0

    def test_transform_empty_input_table(self, temp_test_dir):
        """Test transform with empty input table."""
        input_table = pa.Table.from_pylist([])

        config = {
            "paths": temp_test_dir,
            "max_files": 10,
            "force_ingest": True,
        }

        operator = IngestLocalOperator(config)
        tables, metadata = operator.transform(input_table)
        result_table = tables[0]

        assert result_table.num_rows > 0
        assert set(result_table.column_names) == EXPECTED_METADATA_COLUMNS
        assert metadata["processed_docs"] == result_table.num_rows


def test_table_concatenation_basic():
    """Basic test for table concatenation without fixtures."""
    fixtures_dir = Path(__file__).parent.parent.parent.parent / "fixtures" / "invoices"

    if not fixtures_dir.exists():
        pytest.skip(f"Fixtures directory not found: {fixtures_dir}")

    input_data = [
        {
            "id": "input_1",
            "name": "/input/file.txt",
            "path": "/input/file.txt",
            "size": 100,
            "created_time": 1000000000,
            "modified_time": 1000000000,
        }
    ]
    input_table = pa.Table.from_pylist(input_data)

    config = {
        "paths": str(fixtures_dir),
        "include_filter": "pdf",
        "max_files": 2,
        "force_ingest": True,
    }

    operator = IngestLocalOperator(config)
    tables, metadata = operator.transform(input_table)
    result_table = tables[0]

    assert result_table.num_rows > 1, "Should have input row + ingested rows"
    assert result_table.num_rows == input_table.num_rows + metadata["processed_docs"]
    assert "binary_content" not in result_table.column_names
    assert EXPECTED_METADATA_COLUMNS.issubset(set(result_table.column_names))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
