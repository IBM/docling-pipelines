"""
Unit tests for data transformation utilities.
Tests for PyArrow table transformation operations.
"""

import pyarrow as pa
import pytest

from docpipe.utils.data.transform import TransformUtils


class TestTransformUtils:
    """Test TransformUtils functionality."""

    def test_add_column_to_table(self):
        """Test adding a column to a PyArrow table."""
        table = pa.table({"id": [1, 2, 3], "name": ["Alice", "Bob", "Charlie"]})

        new_column_data = [25, 30, 35]
        result = TransformUtils.add_column(table, "age", new_column_data)

        assert result.num_rows == 3
        assert "age" in result.column_names
        assert result["age"].to_pylist() == [25, 30, 35]
        # Original columns should still be present
        assert result["id"].to_pylist() == [1, 2, 3]
        assert result["name"].to_pylist() == ["Alice", "Bob", "Charlie"]

    def test_add_column_with_string_data(self):
        """Test adding a string column."""
        table = pa.table({"id": [1, 2, 3]})

        string_data = ["value1", "value2", "value3"]
        result = TransformUtils.add_column(table, "description", string_data)

        assert "description" in result.column_names
        assert result["description"].to_pylist() == string_data
        assert result.schema.field("description").type == pa.string()

    def test_add_column_with_boolean_data(self):
        """Test adding a boolean column."""
        table = pa.table({"id": [1, 2, 3]})

        bool_data = [True, False, True]
        result = TransformUtils.add_column(table, "active", bool_data)

        assert "active" in result.column_names
        assert result["active"].to_pylist() == bool_data
        assert result.schema.field("active").type == pa.bool_()

    def test_add_column_with_float_data(self):
        """Test adding a float column."""
        table = pa.table({"id": [1, 2, 3]})

        float_data = [1.5, 2.7, 3.9]
        result = TransformUtils.add_column(table, "score", float_data)

        assert "score" in result.column_names
        assert result["score"].to_pylist() == float_data

    def test_add_column_to_empty_table(self):
        """Test adding a column to an empty table."""
        empty_table = pa.table({"id": pa.array([], type=pa.int64())})

        empty_data = []
        result = TransformUtils.add_column(empty_table, "value", empty_data)

        assert result.num_rows == 0
        assert "value" in result.column_names

    def test_add_column_with_null_values(self):
        """Test adding a column with null values."""
        table = pa.table({"id": [1, 2, 3, 4]})

        data_with_nulls = [10, None, 30, None]
        result = TransformUtils.add_column(table, "nullable_col", data_with_nulls)

        assert "nullable_col" in result.column_names
        assert result["nullable_col"].to_pylist() == data_with_nulls

    def test_add_multiple_columns_sequentially(self):
        """Test adding multiple columns one after another."""
        table = pa.table({"id": [1, 2, 3]})

        # Add first column
        table = TransformUtils.add_column(table, "col1", ["a", "b", "c"])
        # Add second column
        table = TransformUtils.add_column(table, "col2", [10, 20, 30])
        # Add third column
        table = TransformUtils.add_column(table, "col3", [True, False, True])

        assert table.num_columns == 4
        assert set(table.column_names) == {"id", "col1", "col2", "col3"}

    def test_add_column_with_list_data(self):
        """Test adding a column with list data."""
        table = pa.table({"id": [1, 2, 3]})

        list_data = [[1, 2, 3], [4, 5], [6, 7, 8, 9]]
        result = TransformUtils.add_column(table, "list_col", list_data)

        assert "list_col" in result.column_names
        assert result["list_col"].to_pylist() == list_data

    def test_add_column_with_dict_data(self):
        """Test adding a column with dictionary/struct data."""
        table = pa.table({"id": [1, 2, 3]})

        dict_data = [{"a": 1, "b": "x"}, {"a": 2, "b": "y"}, {"a": 3, "b": "z"}]
        result = TransformUtils.add_column(table, "struct_col", dict_data)

        assert "struct_col" in result.column_names
        assert result.num_rows == 3

    def test_add_column_preserves_original_table(self):
        """Test that adding a column doesn't modify the original table."""
        original_table = pa.table({"id": [1, 2, 3]})
        original_num_columns = original_table.num_columns

        new_table = TransformUtils.add_column(original_table, "new_col", [10, 20, 30])

        # Original table should be unchanged
        assert original_table.num_columns == original_num_columns
        assert "new_col" not in original_table.column_names
        # New table should have the additional column
        assert new_table.num_columns == original_num_columns + 1
        assert "new_col" in new_table.column_names

    def test_add_column_with_mismatched_length_raises_error(self):
        """Test that adding a column with wrong length raises an error."""
        table = pa.table({"id": [1, 2, 3]})

        # Data with wrong length
        wrong_length_data = [10, 20]  # Only 2 elements instead of 3

        with pytest.raises(pa.ArrowInvalid):
            TransformUtils.add_column(table, "bad_col", wrong_length_data)

    def test_add_column_with_unicode_name(self):
        """Test adding a column with Unicode name."""
        table = pa.table({"id": [1, 2, 3]})

        unicode_name = "列名"  # Chinese characters
        result = TransformUtils.add_column(table, unicode_name, [10, 20, 30])

        assert unicode_name in result.column_names

    def test_add_column_with_unicode_data(self):
        """Test adding a column with Unicode data."""
        table = pa.table({"id": [1, 2, 3]})

        unicode_data = ["你好", "مرحبا", "Привет"]
        result = TransformUtils.add_column(table, "greeting", unicode_data)

        assert result["greeting"].to_pylist() == unicode_data

    def test_add_column_to_large_table(self):
        """Test adding a column to a large table."""
        large_table = pa.table({"id": list(range(10000))})

        new_data = [i * 2 for i in range(10000)]
        result = TransformUtils.add_column(large_table, "doubled", new_data)

        assert result.num_rows == 10000
        assert "doubled" in result.column_names
        assert result["doubled"][0].as_py() == 0
        assert result["doubled"][9999].as_py() == 19998

    def test_add_column_with_mixed_types_in_list(self):
        """Test adding a column with mixed types (should infer appropriate type)."""
        table = pa.table({"id": [1, 2, 3]})

        # PyArrow will try to infer the best type
        mixed_data = [1, 2, 3]  # All integers
        result = TransformUtils.add_column(table, "numbers", mixed_data)

        assert "numbers" in result.column_names

    def test_add_column_with_empty_strings(self):
        """Test adding a column with empty strings."""
        table = pa.table({"id": [1, 2, 3]})

        data_with_empty = ["", "value", ""]
        result = TransformUtils.add_column(table, "text", data_with_empty)

        assert result["text"].to_pylist() == data_with_empty

    def test_add_column_with_zero_values(self):
        """Test adding a column with zero values."""
        table = pa.table({"id": [1, 2, 3]})

        zero_data = [0, 0, 0]
        result = TransformUtils.add_column(table, "zeros", zero_data)

        assert result["zeros"].to_pylist() == zero_data

    def test_add_column_with_negative_values(self):
        """Test adding a column with negative values."""
        table = pa.table({"id": [1, 2, 3]})

        negative_data = [-1, -2, -3]
        result = TransformUtils.add_column(table, "negatives", negative_data)

        assert result["negatives"].to_pylist() == negative_data

    def test_add_column_with_special_characters_in_name(self):
        """Test adding a column with special characters in name."""
        table = pa.table({"id": [1, 2, 3]})

        # Some special characters that might be valid in column names
        special_name = "col_with-special.chars"
        result = TransformUtils.add_column(table, special_name, [10, 20, 30])

        assert special_name in result.column_names


class TestTransformUtilsEdgeCases:
    """Test edge cases and error conditions."""

    def test_add_column_with_single_row(self):
        """Test adding a column to a single-row table."""
        table = pa.table({"id": [1]})

        result = TransformUtils.add_column(table, "value", [100])

        assert result.num_rows == 1
        assert result["value"].to_pylist() == [100]

    def test_add_column_with_all_nulls(self):
        """Test adding a column with all null values."""
        table = pa.table({"id": [1, 2, 3]})

        all_nulls = [None, None, None]
        result = TransformUtils.add_column(table, "nulls", all_nulls)

        assert "nulls" in result.column_names
        assert all(v is None for v in result["nulls"].to_pylist())

    def test_add_column_with_very_long_name(self):
        """Test adding a column with a very long name."""
        table = pa.table({"id": [1, 2, 3]})

        long_name = "a" * 1000  # Very long column name
        result = TransformUtils.add_column(table, long_name, [10, 20, 30])

        assert long_name in result.column_names

    def test_add_column_duplicate_name_overwrites(self):
        """Test that adding a column with existing name creates new column."""
        table = pa.table({"id": [1, 2, 3], "value": [10, 20, 30]})

        # Adding column with same name should append, not replace
        result = TransformUtils.add_column(table, "new_value", [100, 200, 300])

        assert "new_value" in result.column_names
        # Original value column should still exist
        assert "value" in result.column_names
