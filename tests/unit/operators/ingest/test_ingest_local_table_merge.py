#!/usr/bin/env python3
"""
Unit tests for IngestLocalOperator table merge functionality
Tests the table concatenation logic when an input table is provided
"""

from pathlib import Path
import pytest
import pyarrow as pa

from core.operators.ingest.ingest_local_folder import IngestLocalOperator


class TestIngestLocalOperatorTableMerge:
    """Test suite for IngestLocalOperator table merge functionality"""

    def test_transform_with_none_input_table(self, temp_test_dir):
        """Test transform with None input table (normal case)"""
        config = {
            "input_folder": temp_test_dir,
            "store_binary_content": True,
            "max_files": 10,
            "force_ingest": True,
        }

        operator = IngestLocalOperator(config)
        tables, metadata = operator.transform(None)
        table = tables[0]

        # Verify table was created
        assert table is not None
        assert table.num_rows > 0
        assert "path" in table.column_names
        assert "binary_content" in table.column_names

    def test_transform_with_existing_input_table(self, temp_test_dir):
        """Test transform with existing input table (edge case - table concatenation)"""
        # Create a mock input table with some existing data
        input_data = [
            {
                "id": "existing_1",
                "name": "/path/to/existing1.txt",
                "path": "/path/to/existing1.txt",
                "size": 100,
                "created_time": 1234567890,
                "modified_time": 1234567890,
                "binary_content": b"existing content 1",
            },
            {
                "id": "existing_2",
                "name": "/path/to/existing2.txt",
                "path": "/path/to/existing2.txt",
                "size": 200,
                "created_time": 1234567891,
                "modified_time": 1234567891,
                "binary_content": b"existing content 2",
            },
        ]
        input_table = pa.Table.from_pylist(input_data)

        config = {
            "input_folder": temp_test_dir,
            "store_binary_content": True,
            "max_files": 10,
            "force_ingest": True,
        }

        operator = IngestLocalOperator(config)
        tables, metadata = operator.transform(input_table)
        result_table = tables[0]

        # Verify tables were concatenated
        assert result_table.num_rows > input_table.num_rows, (
            "Result should have more rows than input table"
        )
        
        # Verify input table rows are preserved
        assert result_table.num_rows >= 2, "Should have at least the 2 input rows"
        
        # Verify schema is consistent
        assert "path" in result_table.column_names
        assert "binary_content" in result_table.column_names
        assert "id" in result_table.column_names
        assert "name" in result_table.column_names

    def test_transform_with_schema_mismatch(self, temp_test_dir):
        """Test transform handles schema differences gracefully"""
        # Create input table with different schema (missing some columns)
        input_data = [
            {
                "id": "existing_1",
                "name": "/path/to/existing1.txt",
                "custom_field": "custom_value",  # Extra field not in new data
            }
        ]
        input_table = pa.Table.from_pylist(input_data)

        config = {
            "input_folder": temp_test_dir,
            "store_binary_content": True,
            "max_files": 10,
            "force_ingest": True,
        }

        operator = IngestLocalOperator(config)
        tables, metadata = operator.transform(input_table)
        result_table = tables[0]

        # Verify concatenation succeeded despite schema differences
        assert result_table.num_rows > input_table.num_rows
        
        # Verify all columns from both tables are present
        assert "id" in result_table.column_names
        assert "name" in result_table.column_names
        assert "custom_field" in result_table.column_names  # From input table
        assert "path" in result_table.column_names  # From new data
        assert "binary_content" in result_table.column_names  # From new data
        
        # Verify null handling for missing columns
        # First row should have custom_field value
        first_row_custom = result_table["custom_field"][0].as_py()
        assert first_row_custom == "custom_value"
        
        # New rows should have null for custom_field
        last_row_custom = result_table["custom_field"][result_table.num_rows - 1].as_py()
        assert last_row_custom is None

    def test_transform_preserves_input_table_data(self, temp_test_dir):
        """Test that input table data is preserved in concatenation"""
        # Create input table with specific identifiable data
        input_data = [
            {
                "id": "test_id_123",
                "name": "/unique/path/test.txt",
                "path": "/unique/path/test.txt",
                "size": 999,
                "created_time": 1111111111,
                "modified_time": 1111111111,
                "binary_content": b"unique test content",
            }
        ]
        input_table = pa.Table.from_pylist(input_data)

        config = {
            "input_folder": temp_test_dir,
            "store_binary_content": True,
            "max_files": 10,
            "force_ingest": True,
        }

        operator = IngestLocalOperator(config)
        tables, metadata = operator.transform(input_table)
        result_table = tables[0]

        # Find the original row in the result
        found_original = False
        for idx in range(result_table.num_rows):
            row_id = result_table["id"][idx].as_py()
            if row_id == "test_id_123":
                found_original = True
                # Verify all fields are preserved
                assert result_table["name"][idx].as_py() == "/unique/path/test.txt"
                assert result_table["size"][idx].as_py() == 999
                assert result_table["binary_content"][idx].as_py() == b"unique test content"
                break

        assert found_original, "Original input table data should be preserved"

    def test_transform_empty_input_table(self, temp_test_dir):
        """Test transform with empty input table"""
        # Create empty table with schema
        input_table = pa.Table.from_pylist([])

        config = {
            "input_folder": temp_test_dir,
            "store_binary_content": True,
            "max_files": 10,
            "force_ingest": True,
        }

        operator = IngestLocalOperator(config)
        tables, metadata = operator.transform(input_table)
        result_table = tables[0]

        # Should have rows from ingested files
        assert result_table.num_rows > 0
        assert "path" in result_table.column_names


def test_table_concatenation_basic():
    """Basic test for table concatenation without fixtures"""
    fixtures_dir = Path(__file__).parent.parent.parent.parent / "fixtures" / "invoices"

    if not fixtures_dir.exists():
        pytest.skip(f"Fixtures directory not found: {fixtures_dir}")

    # Create input table
    input_data = [
        {
            "id": "input_1",
            "name": "/input/file.txt",
            "path": "/input/file.txt",
            "size": 100,
            "created_time": 1000000000,
            "modified_time": 1000000000,
            "binary_content": b"input content",
        }
    ]
    input_table = pa.Table.from_pylist(input_data)

    config = {
        "input_folder": str(fixtures_dir),
        "store_binary_content": True,
        "include_filter": "pdf",
        "max_files": 2,
        "force_ingest": True,
    }

    operator = IngestLocalOperator(config)
    tables, metadata = operator.transform(input_table)
    result_table = tables[0]

    # Verify concatenation
    assert result_table.num_rows > 1, "Should have input row + ingested rows"
    assert result_table.num_rows == input_table.num_rows + metadata["processed_docs"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

