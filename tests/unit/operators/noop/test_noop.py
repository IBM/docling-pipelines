#!/usr/bin/env python3
"""
Unit tests for NOOPOperator.

Tests the pass-through operator that returns data unchanged while optionally
adding metadata. Used for testing and debugging pipelines.
"""

import time

import pyarrow as pa
import pytest

from docpipe.core.constants.constants import Metrics
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.functional.noop import NOOPOperator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_table(num_rows: int = 3, extra_columns=None) -> pa.Table:
    """
    Create a test PyArrow table with standard columns.

    Args:
        num_rows: Number of rows to create
        extra_columns: dict of additional columns to include
    """
    data = {
        "id": [str(i + 1) for i in range(num_rows)],
        "content": [f"Document content {i + 1}" for i in range(num_rows)],
        "name": [f"doc_{i + 1}.txt" for i in range(num_rows)],
    }
    if extra_columns:
        data.update(extra_columns)
    return pa.table(data)


def make_operator(config=None) -> NOOPOperator:
    """
    Create a NOOPOperator with optional config.

    Args:
        config: Configuration dict. Defaults to sleep_sec=0 for fast tests.
    """
    base = {"sleep_sec": 0}  # Default to no sleep for fast tests
    if config:
        base.update(config)
    return NOOPOperator(base)


# ---------------------------------------------------------------------------
# 1. Constructor and initialization
# ---------------------------------------------------------------------------


def test_operator_init_with_empty_config():
    """Operator initializes successfully with an empty config dict."""
    operator = NOOPOperator({})
    assert operator is not None
    assert operator.sleep == 1  # Default sleep value


def test_operator_init_with_custom_sleep():
    """Operator initializes with custom sleep_sec value."""
    operator = NOOPOperator({"sleep_sec": 5})
    assert operator.sleep == 5


def test_operator_init_with_zero_sleep():
    """Operator initializes with sleep_sec=0."""
    operator = NOOPOperator({"sleep_sec": 0})
    assert operator.sleep == 0


def test_operator_init_sets_common_log_arguments():
    """Operator initializes common_log_arguments dict."""
    operator = make_operator()
    assert hasattr(operator, "common_log_arguments")
    assert isinstance(operator.common_log_arguments, dict)


# ---------------------------------------------------------------------------
# 2. Basic pass-through functionality
# ---------------------------------------------------------------------------


def test_basic_passthrough_returns_unchanged_data():
    """Operator returns input table unchanged."""
    table = make_table()
    operator = make_operator()
    result_tables, _ = operator.transform(table)

    assert len(result_tables) == 1
    result = result_tables[0]

    # Verify data is identical
    assert result.num_rows == table.num_rows
    assert result.column_names == table.column_names
    assert result.equals(table)


def test_passthrough_preserves_all_columns():
    """Operator preserves all input columns."""
    table = make_table()
    operator = make_operator()
    result_tables, _ = operator.transform(table)
    result = result_tables[0]

    for col in table.column_names:
        assert col in result.column_names, f"Column '{col}' missing from output"


def test_passthrough_preserves_row_count():
    """Output table has the same number of rows as input."""
    table = make_table(num_rows=10)
    operator = make_operator()
    result_tables, _ = operator.transform(table)
    result = result_tables[0]

    assert result.num_rows == table.num_rows


def test_passthrough_preserves_data_types():
    """Operator preserves column data types."""
    table = pa.table(
        {
            "id": pa.array(["1", "2", "3"], type=pa.string()),
            "score": pa.array([1.5, 2.5, 3.5], type=pa.float64()),
            "count": pa.array([10, 20, 30], type=pa.int64()),
            "flag": pa.array([True, False, True], type=pa.bool_()),
        }
    )
    operator = make_operator()
    result_tables, _ = operator.transform(table)
    result = result_tables[0]

    assert result.schema.equals(table.schema)


def test_passthrough_preserves_column_order():
    """Operator preserves the order of columns."""
    table = make_table()
    operator = make_operator()
    result_tables, _ = operator.transform(table)
    result = result_tables[0]

    assert result.column_names == table.column_names


# ---------------------------------------------------------------------------
# 3. Metadata generation
# ---------------------------------------------------------------------------


def test_transform_returns_metadata_dict():
    """transform() returns a metadata dictionary."""
    table = make_table()
    operator = make_operator()
    _, metadata = operator.transform(table)

    assert isinstance(metadata, dict)


def test_metadata_contains_total_docs():
    """Metadata contains documents_in_scope."""
    table = make_table(num_rows=5)
    operator = make_operator()
    _, metadata = operator.transform(table)

    assert Metrics.External.TOTAL_DOCS in metadata
    assert metadata[Metrics.External.TOTAL_DOCS] == 5


def test_metadata_contains_processed_docs():
    """Metadata contains processed_docs count."""
    table = make_table(num_rows=5)
    operator = make_operator()
    _, metadata = operator.transform(table)

    assert Metrics.External.PROCESSED_DOCS in metadata
    assert metadata[Metrics.External.PROCESSED_DOCS] == 5


def test_metadata_contains_nfiles():
    """Metadata contains nfiles field."""
    table = make_table()
    operator = make_operator()
    _, metadata = operator.transform(table)

    assert "nfiles" in metadata
    assert metadata["nfiles"] == 0


def test_metadata_contains_nrows():
    """Metadata contains nrows field matching table row count."""
    table = make_table(num_rows=7)
    operator = make_operator()
    _, metadata = operator.transform(table)

    assert "nrows" in metadata
    assert metadata["nrows"] == 7


def test_metadata_processed_docs_equals_total_docs():
    """For NOOP operator, processed_docs should equal total_docs."""
    table = make_table(num_rows=10)
    operator = make_operator()
    _, metadata = operator.transform(table)

    assert metadata[Metrics.External.PROCESSED_DOCS] == metadata[Metrics.External.TOTAL_DOCS]


# ---------------------------------------------------------------------------
# 4. Multiple table handling
# ---------------------------------------------------------------------------


def test_transform_returns_single_table_in_list():
    """transform() returns a list containing exactly one table."""
    table = make_table()
    operator = make_operator()
    result_tables, _ = operator.transform(table)

    assert isinstance(result_tables, list)
    assert len(result_tables) == 1
    assert isinstance(result_tables[0], pa.Table)


def test_multiple_transforms_independent():
    """Multiple transform calls are independent and produce identical results."""
    table = make_table()
    operator = make_operator()

    result1, meta1 = operator.transform(table)
    result2, meta2 = operator.transform(table)

    assert result1[0].equals(result2[0])
    assert meta1[Metrics.External.TOTAL_DOCS] == meta2[Metrics.External.TOTAL_DOCS]


# ---------------------------------------------------------------------------
# 5. Empty table handling
# ---------------------------------------------------------------------------


def test_empty_table_returns_empty_table():
    """Operator handles empty table gracefully."""
    table = pa.table(
        {
            "id": pa.array([], type=pa.string()),
            "content": pa.array([], type=pa.string()),
            "name": pa.array([], type=pa.string()),
        }
    )
    operator = make_operator()
    result_tables, _metadata = operator.transform(table)
    result = result_tables[0]

    assert result.num_rows == 0
    assert result.column_names == table.column_names


def test_empty_table_metadata():
    """Metadata for empty table has zero counts."""
    table = pa.table(
        {
            "id": pa.array([], type=pa.string()),
            "content": pa.array([], type=pa.string()),
        }
    )
    operator = make_operator()
    _, metadata = operator.transform(table)

    assert metadata[Metrics.External.TOTAL_DOCS] == 0
    assert metadata[Metrics.External.PROCESSED_DOCS] == 0
    assert metadata["nrows"] == 0


# ---------------------------------------------------------------------------
# 6. Large table handling
# ---------------------------------------------------------------------------


def test_large_table_passthrough():
    """Operator handles large tables efficiently."""
    num_rows = 10000
    table = make_table(num_rows=num_rows)
    operator = make_operator()
    result_tables, metadata = operator.transform(table)
    result = result_tables[0]

    assert result.num_rows == num_rows
    assert metadata[Metrics.External.TOTAL_DOCS] == num_rows


def test_large_content_preserved():
    """Large content strings are preserved unchanged."""
    large_content = "A" * 100000
    table = pa.table(
        {
            "id": ["1"],
            "content": [large_content],
        }
    )
    operator = make_operator()
    result_tables, _ = operator.transform(table)
    result = result_tables[0]

    assert result["content"][0].as_py() == large_content


# ---------------------------------------------------------------------------
# 7. Edge cases: None values, empty strings, special characters
# ---------------------------------------------------------------------------


def test_none_values_preserved():
    """None/null values are preserved in the output."""
    table = pa.table(
        {
            "id": ["1", "2", "3"],
            "content": ["text", None, "more text"],
            "optional": [None, None, "value"],
        }
    )
    operator = make_operator()
    result_tables, _ = operator.transform(table)
    result = result_tables[0]

    assert result["content"][1].as_py() is None
    assert result["optional"][0].as_py() is None
    assert result["optional"][1].as_py() is None


def test_empty_strings_preserved():
    """Empty strings are preserved unchanged."""
    table = pa.table(
        {
            "id": ["1", "2", "3"],
            "content": ["", "text", ""],
        }
    )
    operator = make_operator()
    result_tables, _ = operator.transform(table)
    result = result_tables[0]

    assert result["content"][0].as_py() == ""
    assert result["content"][2].as_py() == ""


def test_special_characters_preserved():
    """Special characters and unicode are preserved."""
    table = pa.table(
        {
            "id": ["1", "2", "3"],
            "content": [
                "Hello\nWorld\t!",
                "こんにちは世界",
                "Special: @#$%^&*()",
            ],
        }
    )
    operator = make_operator()
    result_tables, _ = operator.transform(table)
    result = result_tables[0]

    assert result["content"][0].as_py() == "Hello\nWorld\t!"
    assert result["content"][1].as_py() == "こんにちは世界"
    assert result["content"][2].as_py() == "Special: @#$%^&*()"


def test_single_row_table():
    """Operator works correctly on single-row table."""
    table = make_table(num_rows=1)
    operator = make_operator()
    result_tables, metadata = operator.transform(table)
    result = result_tables[0]

    assert result.num_rows == 1
    assert metadata[Metrics.External.PROCESSED_DOCS] == 1


# ---------------------------------------------------------------------------
# 8. Column preservation with various data types
# ---------------------------------------------------------------------------


def test_mixed_data_types_preserved():
    """Tables with mixed data types are preserved correctly."""
    table = pa.table(
        {
            "id": ["1", "2"],
            "text": ["hello", "world"],
            "integer": [42, 100],
            "float": [3.14, 2.71],
            "boolean": [True, False],
            "list": [[1, 2, 3], [4, 5]],
        }
    )
    operator = make_operator()
    result_tables, _ = operator.transform(table)
    result = result_tables[0]

    assert result.equals(table)
    assert result.schema.equals(table.schema)


def test_extra_columns_preserved():
    """Tables with extra columns are fully preserved."""
    extra_cols = {
        "score": [1.0, 2.0, 3.0],
        "language": ["en", "fr", "de"],
        "metadata": ["meta1", "meta2", "meta3"],
    }
    table = make_table(extra_columns=extra_cols)
    operator = make_operator()
    result_tables, _ = operator.transform(table)
    result = result_tables[0]

    for col in extra_cols.keys():
        assert col in result.column_names


# ---------------------------------------------------------------------------
# 9. Operator properties
# ---------------------------------------------------------------------------


def test_short_name_matches_constant():
    """short_name matches OperatorConstants.Operators.NOOP."""
    assert NOOPOperator.short_name == OperatorConstants.Operators.NOOP


def test_short_name_value():
    """short_name is 'noop'."""
    assert NOOPOperator.short_name == "noop"


def test_category_is_functional():
    """Operator category is Functional."""
    from docpipe.core.operators.abstract_operator import OperatorCategory

    assert NOOPOperator.category == OperatorCategory.Functional


# ---------------------------------------------------------------------------
# 10. get_metadata() method
# ---------------------------------------------------------------------------


def test_get_metadata_returns_dict():
    """get_metadata() returns a dictionary."""
    operator = make_operator()
    meta = operator.get_metadata()

    assert isinstance(meta, dict)


def test_get_metadata_contains_is_operator_available():
    """get_metadata() contains IS_OPERATOR_AVAILABLE key."""
    operator = make_operator()
    meta = operator.get_metadata()

    assert OperatorConstants.Misc.IS_OPERATOR_AVAILABLE in meta


def test_get_metadata_is_operator_available_value():
    """get_metadata() IS_OPERATOR_AVAILABLE returns result of is_available()."""
    operator = make_operator()
    meta = operator.get_metadata()

    # Should match the is_available() method result
    assert meta[OperatorConstants.Misc.IS_OPERATOR_AVAILABLE] == operator.is_available()


def test_get_metadata_attributes_has_sleep_sec():
    """get_metadata() attributes contain 'sleep_sec' key."""
    meta = NOOPOperator.get_metadata()
    assert OperatorConstants.Config.ATTRIBUTES in meta
    assert OperatorConstants.Misc.SLEEP_SEC in meta[OperatorConstants.Config.ATTRIBUTES]
    attr = meta[OperatorConstants.Config.ATTRIBUTES][OperatorConstants.Misc.SLEEP_SEC]
    assert attr[OperatorConstants.Config.REQUIRED] is False
    assert attr[OperatorConstants.Config.DEFAULT] == 1


# ---------------------------------------------------------------------------
# 11. Sleep functionality
# ---------------------------------------------------------------------------


def test_sleep_functionality_with_short_duration():
    """Operator sleeps for the configured duration."""
    sleep_duration = 0.1  # 100ms for fast test
    operator = NOOPOperator({"sleep_sec": sleep_duration})
    table = make_table(num_rows=1)

    start_time = time.time()
    operator.transform(table)
    elapsed_time = time.time() - start_time

    # Should have slept for at least the configured duration
    assert elapsed_time >= sleep_duration


def test_no_sleep_when_zero():
    """Operator does not sleep when sleep_sec is 0."""
    operator = NOOPOperator({"sleep_sec": 0})
    table = make_table(num_rows=1)

    start_time = time.time()
    operator.transform(table)
    elapsed_time = time.time() - start_time

    # Should complete very quickly (< 0.05 seconds)
    assert elapsed_time < 0.05


def test_sleep_with_none_value():
    """Operator handles None sleep value gracefully."""
    operator = NOOPOperator({"sleep_sec": None})
    table = make_table(num_rows=1)

    # Should not raise an exception
    result_tables, _metadata = operator.transform(table)
    assert len(result_tables) == 1


# ---------------------------------------------------------------------------
# 12. Data integrity verification
# ---------------------------------------------------------------------------


def test_data_values_unchanged():
    """All data values remain exactly the same after transform."""
    table = pa.table(
        {
            "id": ["1", "2", "3"],
            "content": ["First doc", "Second doc", "Third doc"],
            "score": [1.5, 2.5, 3.5],
        }
    )
    operator = make_operator()
    result_tables, _ = operator.transform(table)
    result = result_tables[0]

    # Check each value
    for col in table.column_names:
        for i in range(table.num_rows):
            assert result[col][i].as_py() == table[col][i].as_py()


def test_table_schema_unchanged():
    """Table schema remains unchanged after transform."""
    table = make_table()
    operator = make_operator()
    result_tables, _ = operator.transform(table)
    result = result_tables[0]

    assert result.schema.equals(table.schema)


def test_table_metadata_preserved():
    """PyArrow table metadata is preserved if present."""
    table = make_table()
    # Add custom metadata to the table
    table = table.replace_schema_metadata({"custom_key": "custom_value"})

    operator = make_operator()
    result_tables, _ = operator.transform(table)
    result = result_tables[0]

    # Schema metadata should be preserved
    if table.schema.metadata:
        assert result.schema.metadata == table.schema.metadata


# ---------------------------------------------------------------------------
# 13. Integration with PyArrow tables
# ---------------------------------------------------------------------------


def test_accepts_pyarrow_table():
    """Operator accepts PyArrow Table as input."""
    table = pa.table({"id": ["1"], "content": ["test"]})
    operator = make_operator()

    result_tables, _metadata = operator.transform(table)

    assert isinstance(result_tables[0], pa.Table)


def test_returns_pyarrow_table():
    """Operator returns PyArrow Table in output list."""
    table = make_table()
    operator = make_operator()
    result_tables, _ = operator.transform(table)

    assert isinstance(result_tables[0], pa.Table)


def test_pyarrow_table_operations_work():
    """Standard PyArrow operations work on output table."""
    table = make_table()
    operator = make_operator()
    result_tables, _ = operator.transform(table)
    result = result_tables[0]

    # Test various PyArrow operations
    assert result.num_rows == table.num_rows
    assert result.num_columns == table.num_columns
    assert result.column_names == table.column_names
    assert result.to_pandas() is not None


# ---------------------------------------------------------------------------
# 14. Operator behavior consistency
# ---------------------------------------------------------------------------


def test_deterministic_behavior():
    """Operator produces identical results for identical inputs."""
    table = make_table()
    operator = make_operator()

    result1, meta1 = operator.transform(table)
    result2, meta2 = operator.transform(table)

    assert result1[0].equals(result2[0])
    assert meta1["nrows"] == meta2["nrows"]


def test_no_side_effects_on_input():
    """Transform does not modify the input table."""
    table = make_table()
    original_num_rows = table.num_rows
    original_columns = table.column_names.copy()

    operator = make_operator()
    operator.transform(table)

    # Input table should be unchanged
    assert table.num_rows == original_num_rows
    assert table.column_names == original_columns


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
