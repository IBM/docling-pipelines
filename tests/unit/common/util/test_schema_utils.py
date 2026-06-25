"""
Unit tests for schema alignment and table combination utilities.
Tests for PyArrow table schema operations.
"""

import pyarrow as pa
import pyarrow.compute as pc

from docpipe.utils.data.schema_utils import (
    _combine_tables,
    _total_rows,
    align_table_schema,
)


class TestAlignTableSchema:
    """Test schema alignment functionality."""

    def test_align_table_with_missing_columns(self):
        """Test adding missing columns to a table."""
        table = pa.table({"id": [1, 2, 3], "name": ["Alice", "Bob", "Charlie"]})

        all_cols = {
            "id": pa.int64(),
            "name": pa.string(),
            "age": pa.int64(),
            "active": pa.bool_(),
        }

        aligned = align_table_schema(table, all_cols)

        assert aligned.num_rows == 3
        assert set(aligned.column_names) == {"id", "name", "age", "active"}
        # New columns should have null values
        assert all(v is None for v in aligned["age"].to_pylist())
        assert all(v is None for v in aligned["active"].to_pylist())

    def test_align_table_with_all_columns_present(self):
        """Test aligning table that already has all columns."""
        table = pa.table({"id": [1, 2, 3], "name": ["Alice", "Bob", "Charlie"], "age": [25, 30, 35]})

        all_cols = {"id": pa.int64(), "name": pa.string(), "age": pa.int64()}

        aligned = align_table_schema(table, all_cols)

        assert aligned.num_rows == 3
        assert aligned.column_names == sorted(all_cols.keys())
        assert aligned["id"].to_pylist() == [1, 2, 3]

    def test_align_empty_table(self):
        """Test aligning an empty table."""
        empty_table = pa.table({"id": pa.array([], type=pa.int64())})

        all_cols = {"id": pa.int64(), "name": pa.string(), "value": pa.float64()}

        aligned = align_table_schema(empty_table, all_cols)

        assert aligned.num_rows == 0
        assert set(aligned.column_names) == {"id", "name", "value"}

    def test_align_table_column_order(self):
        """Test that aligned table has sorted column order."""
        table = pa.table({"z_col": [1, 2], "a_col": [3, 4], "m_col": [5, 6]})

        all_cols = {
            "z_col": pa.int64(),
            "a_col": pa.int64(),
            "m_col": pa.int64(),
            "b_col": pa.int64(),
        }

        aligned = align_table_schema(table, all_cols)

        # Columns should be in sorted order
        assert aligned.column_names == ["a_col", "b_col", "m_col", "z_col"]

    def test_align_table_with_different_types(self):
        """Test aligning table with various data types."""
        table = pa.table({"int_col": [1, 2, 3]})

        all_cols = {
            "int_col": pa.int64(),
            "float_col": pa.float64(),
            "string_col": pa.string(),
            "bool_col": pa.bool_(),
            "list_col": pa.list_(pa.int64()),
        }

        aligned = align_table_schema(table, all_cols)

        assert aligned.num_rows == 3
        assert len(aligned.column_names) == 5
        # Check that new columns have correct types
        assert aligned.schema.field("float_col").type == pa.float64()
        assert aligned.schema.field("string_col").type == pa.string()
        assert aligned.schema.field("bool_col").type == pa.bool_()

    def test_align_table_handles_exceptions(self):
        """Test that alignment handles exceptions gracefully."""
        table = pa.table({"id": [1, 2, 3]})

        # Invalid type specification
        all_cols = {
            "id": pa.int64(),
            "bad_col": "not_a_type",  # Invalid type
        }

        # Should not raise, but log warning and return original or partially aligned table
        result = align_table_schema(table, all_cols)
        assert result is not None


class TestCombineTables:
    """Test table combination functionality."""

    def test_combine_simple_tables(self):
        """Test combining multiple simple tables."""
        table1 = pa.table({"id": [1, 2], "name": ["Alice", "Bob"]})
        table2 = pa.table({"id": [3, 4], "name": ["Charlie", "David"]})
        table3 = pa.table({"id": [5], "name": ["Eve"]})

        combined = _combine_tables([table1, table2, table3], "test_tables")

        assert combined is not None
        assert combined.num_rows == 5
        assert combined["id"].to_pylist() == [1, 2, 3, 4, 5]

    def test_combine_empty_list(self):
        """Test combining empty list of tables returns None."""
        result = _combine_tables([], "empty_tables")
        assert result is None

    def test_combine_single_table(self):
        """Test combining a single table."""
        table = pa.table({"id": [1, 2, 3], "value": ["a", "b", "c"]})

        combined = _combine_tables([table], "single_table")

        assert combined is not None
        assert combined.num_rows == 3
        assert combined.equals(table)

    def test_combine_tables_with_different_schemas(self):
        """Test combining tables with different schemas (promote=True)."""
        table1 = pa.table({"id": [1, 2], "name": ["Alice", "Bob"]})
        table2 = pa.table({"id": [3, 4], "age": [25, 30]})

        combined = _combine_tables([table1, table2], "mixed_schema")

        assert combined is not None
        assert combined.num_rows == 4
        # Should have all columns from both tables
        assert set(combined.column_names) == {"id", "name", "age"}

    def test_combine_tables_detects_duplicate_ids(self):
        """Test that duplicate IDs are detected and logged."""
        table1 = pa.table({"id": [1, 2, 3], "value": ["a", "b", "c"]})
        table2 = pa.table({"id": [2, 3, 4], "value": ["d", "e", "f"]})

        # Should log warning about duplicates but still combine
        combined = _combine_tables([table1, table2], "duplicate_ids")

        assert combined is not None
        assert combined.num_rows == 6
        # Check that duplicates exist
        unique_ids = pc.count_distinct(combined["id"]).as_py()
        assert unique_ids == 4  # Only 4 unique IDs (1, 2, 3, 4)

    def test_combine_tables_without_id_column(self):
        """Test combining tables without 'id' column."""
        table1 = pa.table({"name": ["Alice", "Bob"], "age": [25, 30]})
        table2 = pa.table({"name": ["Charlie"], "age": [35]})

        combined = _combine_tables([table1, table2], "no_id_column")

        assert combined is not None
        assert combined.num_rows == 3
        # Should not check for duplicates without id column

    def test_combine_tables_with_nulls(self):
        """Test combining tables with null values."""
        table1 = pa.table({"id": [1, None, 3], "value": ["a", "b", None]})
        table2 = pa.table({"id": [4, 5], "value": [None, "e"]})

        combined = _combine_tables([table1, table2], "tables_with_nulls")

        assert combined is not None
        assert combined.num_rows == 5

    def test_combine_tables_handles_exceptions(self):
        """Test that combination handles exceptions gracefully."""
        # Create tables that might cause issues
        table1 = pa.table({"col": [1, 2, 3]})

        # Passing None in the list should be handled gracefully
        # The function filters out None values and returns the valid table
        result = _combine_tables([table1, None], "error_tables")

        # Should return the valid table (None values are filtered out)
        assert result is not None
        assert result.num_rows == 3

    def test_combine_tables_all_none(self):
        """Test that combination returns None when all tables are None."""
        # When all tables are None, should return None
        result = _combine_tables([None, None], "all_none_tables")
        assert result is None

    def test_combine_large_number_of_tables(self):
        """Test combining many tables."""
        tables = [pa.table({"id": [i], "value": [f"val_{i}"]}) for i in range(100)]

        combined = _combine_tables(tables, "many_tables")

        assert combined is not None
        assert combined.num_rows == 100

    def test_combine_tables_with_complex_types(self):
        """Test combining tables with complex data types."""
        table1 = pa.table(
            {
                "id": [1, 2],
                "list_col": [[1, 2], [3, 4]],
                "struct_col": [{"a": 1, "b": "x"}, {"a": 2, "b": "y"}],
            }
        )
        table2 = pa.table({"id": [3], "list_col": [[5, 6]], "struct_col": [{"a": 3, "b": "z"}]})

        combined = _combine_tables([table1, table2], "complex_types")

        assert combined is not None
        assert combined.num_rows == 3


class TestTotalRows:
    """Test total rows calculation functionality."""

    def test_total_rows_single_table(self):
        """Test counting rows in a single table."""
        table = pa.table({"id": [1, 2, 3, 4, 5]})
        assert _total_rows(table) == 5

    def test_total_rows_list_of_tables(self):
        """Test counting rows in a list of tables."""
        tables = [
            pa.table({"id": [1, 2, 3]}),
            pa.table({"id": [4, 5]}),
            pa.table({"id": [6, 7, 8, 9]}),
        ]
        assert _total_rows(tables) == 9

    def test_total_rows_dict_of_tables(self):
        """Test counting rows in a dictionary of tables."""
        tables = {
            "table1": pa.table({"id": [1, 2]}),
            "table2": pa.table({"id": [3, 4, 5]}),
            "table3": pa.table({"id": [6]}),
        }
        assert _total_rows(tables) == 6

    def test_total_rows_empty_table(self):
        """Test counting rows in an empty table."""
        empty_table = pa.table({"id": pa.array([], type=pa.int64())})
        assert _total_rows(empty_table) == 0

    def test_total_rows_empty_list(self):
        """Test counting rows in an empty list."""
        assert _total_rows([]) == 0

    def test_total_rows_empty_dict(self):
        """Test counting rows in an empty dictionary."""
        assert _total_rows({}) == 0

    def test_total_rows_none(self):
        """Test counting rows when input is None."""
        assert _total_rows(None) == 0

    def test_total_rows_mixed_empty_and_non_empty_tables(self):
        """Test counting rows with mix of empty and non-empty tables."""
        tables = [
            pa.table({"id": [1, 2, 3]}),
            pa.table({"id": pa.array([], type=pa.int64())}),
            pa.table({"id": [4, 5]}),
        ]
        assert _total_rows(tables) == 5

    def test_total_rows_dict_with_empty_tables(self):
        """Test counting rows in dict with empty tables."""
        tables = {
            "table1": pa.table({"id": [1, 2]}),
            "table2": pa.table({"id": pa.array([], type=pa.int64())}),
            "table3": pa.table({"id": [3]}),
        }
        assert _total_rows(tables) == 3

    def test_total_rows_large_tables(self):
        """Test counting rows in large tables."""
        large_table = pa.table({"id": list(range(10000))})
        assert _total_rows(large_table) == 10000

    def test_total_rows_list_with_large_tables(self):
        """Test counting rows in list of large tables."""
        tables = [
            pa.table({"id": list(range(5000))}),
            pa.table({"id": list(range(3000))}),
            pa.table({"id": list(range(2000))}),
        ]
        assert _total_rows(tables) == 10000


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_align_table_with_no_columns(self):
        """Test aligning table with no additional columns needed."""
        table = pa.table({"id": [1, 2, 3]})
        all_cols = {"id": pa.int64()}

        aligned = align_table_schema(table, all_cols)
        assert aligned.column_names == ["id"]

    def test_combine_tables_all_empty(self):
        """Test combining all empty tables."""
        tables = [
            pa.table({"id": pa.array([], type=pa.int64())}),
            pa.table({"id": pa.array([], type=pa.int64())}),
        ]

        combined = _combine_tables(tables, "all_empty")
        assert combined is not None
        assert combined.num_rows == 0

    def test_total_rows_with_single_row_tables(self):
        """Test counting rows with many single-row tables."""
        tables = [pa.table({"id": [i]}) for i in range(100)]
        assert _total_rows(tables) == 100
