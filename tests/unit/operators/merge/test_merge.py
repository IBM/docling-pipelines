#!/usr/bin/env python3
"""
Unit tests for MergeOperator.

Tests the operator that combines multiple PyArrow tables using row concatenation
or column joins.
"""

import pyarrow as pa
import pytest

from docpipe.core.constants.constants import Metrics
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.functional.merge import MergeOperator
from docpipe.exceptions.docpipe_exceptions import DocpipeException

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_table(*, num_rows: int = 3, id_prefix: str = "", extra_columns=None) -> pa.Table:
    """
    Create a test PyArrow table with standard columns.

    Args:
        num_rows: Number of rows to create
        id_prefix: Prefix for ID values to ensure uniqueness
        extra_columns: dict of additional columns to include
    """
    data = {
        "id": [f"{id_prefix}{i + 1}" for i in range(num_rows)],
        "name": [f"doc_{id_prefix}{i + 1}.txt" for i in range(num_rows)],
        "size": [100 + i for i in range(num_rows)],
    }
    if extra_columns:
        data.update(extra_columns)
    return pa.table(data)


def make_operator(*, config=None) -> MergeOperator:
    """
    Create a MergeOperator with optional config.

    Args:
        config: Configuration dict
    """
    if config is None:
        config = {
            "merge_type": "rows",
            "input_links": [{"link_name": "branch1"}, {"link_name": "branch2"}],
        }
    return MergeOperator(config)


# ---------------------------------------------------------------------------
# 1. Constructor and initialization
# ---------------------------------------------------------------------------


def test_operator_init_with_row_merge():
    """Operator initializes successfully with row merge config."""
    config = {
        "merge_type": "rows",
        "input_links": [{"link_name": "branch1"}, {"link_name": "branch2"}],
    }
    operator = MergeOperator(config)
    assert operator is not None
    assert operator.merge_type == "rows"


def test_operator_init_with_column_merge():
    """Operator initializes successfully with column merge config."""
    config = {
        "merge_type": "columns",
        "column_option": "inner_join",
        "input_links": [{"link_name": "branch1"}, {"link_name": "branch2"}],
    }
    operator = MergeOperator(config)
    assert operator is not None
    assert operator.merge_type == "columns"
    assert operator.column_option == "inner_join"


def test_operator_init_sets_common_log_arguments():
    """Operator initializes common_log_arguments dict."""
    operator = make_operator()
    assert hasattr(operator, "common_log_arguments")
    assert isinstance(operator.common_log_arguments, dict)


def test_operator_init_with_input_links():
    """Operator stores input_links configuration."""
    config = {
        "merge_type": "rows",
        "input_links": [{"link_name": "a"}, {"link_name": "b"}],
    }
    operator = MergeOperator(config)
    assert len(operator.input_links) == 2


# ---------------------------------------------------------------------------
# 2. Row merge (concatenation) functionality
# ---------------------------------------------------------------------------


def test_row_merge_concatenates_tables():
    """Row merge concatenates two tables vertically."""
    table1 = make_table(num_rows=2, id_prefix="a")
    table2 = make_table(num_rows=2, id_prefix="b")

    config = {
        "merge_type": "rows",
        "input_links": [{"link_name": "branch1"}, {"link_name": "branch2"}],
    }
    operator = MergeOperator(config)

    result_tables, _ = operator.transform(table=pa.table({}), tables={"branch1": table1, "branch2": table2})
    result = result_tables[0]

    assert result.num_rows == 4  # 2 + 2
    assert result.num_columns == table1.num_columns


def test_row_merge_preserves_all_rows():
    """Row merge includes all rows from both tables."""
    table1 = make_table(num_rows=3, id_prefix="a")
    table2 = make_table(num_rows=2, id_prefix="b")

    config = {
        "merge_type": "rows",
        "input_links": [{"link_name": "branch1"}, {"link_name": "branch2"}],
    }
    operator = MergeOperator(config)

    result_tables, _ = operator.transform(table=pa.table({}), tables={"branch1": table1, "branch2": table2})
    result = result_tables[0]

    assert result.num_rows == 5  # 3 + 2


def test_row_merge_detects_duplicate_ids():
    """Row merge raises error when duplicate IDs detected."""
    table1 = make_table(num_rows=2, id_prefix="a")
    table2 = make_table(num_rows=2, id_prefix="a")  # Same IDs

    config = {
        "merge_type": "rows",
        "input_links": [{"link_name": "branch1"}, {"link_name": "branch2"}],
    }
    operator = MergeOperator(config)

    with pytest.raises(DocpipeException):
        operator.transform(table=pa.table({}), tables={"branch1": table1, "branch2": table2})


def test_row_merge_with_three_tables():
    """Row merge works with more than two tables."""
    table1 = make_table(num_rows=2, id_prefix="a")
    table2 = make_table(num_rows=2, id_prefix="b")
    table3 = make_table(num_rows=2, id_prefix="c")

    config = {
        "merge_type": "rows",
        "input_links": [
            {"link_name": "branch1"},
            {"link_name": "branch2"},
            {"link_name": "branch3"},
        ],
    }
    operator = MergeOperator(config)

    result_tables, _ = operator.transform(
        table=pa.table({}), tables={"branch1": table1, "branch2": table2, "branch3": table3}
    )
    result = result_tables[0]

    assert result.num_rows == 6  # 2 + 2 + 2


# ---------------------------------------------------------------------------
# 3. Column merge (join) functionality
# ---------------------------------------------------------------------------


def test_column_merge_inner_join():
    """Column merge with inner_join combines tables horizontally."""
    table1 = make_table(num_rows=3, id_prefix="")
    table2 = make_table(num_rows=3, id_prefix="")

    config = {
        "merge_type": "columns",
        "column_option": "inner_join",
        "input_links": [{"link_name": "branch1"}, {"link_name": "branch2"}],
    }
    operator = MergeOperator(config)

    result_tables, _ = operator.transform(table=pa.table({}), tables={"branch1": table1, "branch2": table2})
    result = result_tables[0]

    # Should have original columns + suffixed columns from second table
    assert result.num_rows == 3
    assert "name_branch2" in result.column_names
    assert "size_branch2" in result.column_names


def test_column_merge_full_outer_join():
    """Column merge with full_outer join includes all rows."""
    table1 = make_table(num_rows=2, id_prefix="a")
    table2 = make_table(num_rows=2, id_prefix="b")

    config = {
        "merge_type": "columns",
        "column_option": "full_outer",
        "input_links": [{"link_name": "branch1"}, {"link_name": "branch2"}],
    }
    operator = MergeOperator(config)

    result_tables, _ = operator.transform(table=pa.table({}), tables={"branch1": table1, "branch2": table2})
    result = result_tables[0]

    # Should have all rows from both tables
    assert result.num_rows == 4  # 2 + 2 (no overlap)


def test_column_merge_preserves_id_column():
    """Column merge preserves the ID column without suffix."""
    table1 = make_table(num_rows=3, id_prefix="")
    table2 = make_table(num_rows=3, id_prefix="")

    config = {
        "merge_type": "columns",
        "column_option": "inner_join",
        "input_links": [{"link_name": "branch1"}, {"link_name": "branch2"}],
    }
    operator = MergeOperator(config)

    result_tables, _ = operator.transform(table=pa.table({}), tables={"branch1": table1, "branch2": table2})
    result = result_tables[0]

    assert "id" in result.column_names
    assert "id_branch2" not in result.column_names  # ID should not be suffixed


def test_column_merge_adds_suffix_to_other_columns():
    """Column merge adds _branch2 suffix to non-ID columns from second table."""
    table1 = make_table(num_rows=3, id_prefix="")
    table2 = make_table(num_rows=3, id_prefix="")

    config = {
        "merge_type": "columns",
        "column_option": "inner_join",
        "input_links": [{"link_name": "branch1"}, {"link_name": "branch2"}],
    }
    operator = MergeOperator(config)

    result_tables, _ = operator.transform(table=pa.table({}), tables={"branch1": table1, "branch2": table2})
    result = result_tables[0]

    # Original columns from table1
    assert "name" in result.column_names
    assert "size" in result.column_names

    # Suffixed columns from table2
    assert "name_branch2" in result.column_names
    assert "size_branch2" in result.column_names


# ---------------------------------------------------------------------------
# 4. Validation tests
# ---------------------------------------------------------------------------


def test_validation_requires_merge_type():
    """Validation fails when merge_type is missing."""
    config = {
        "input_links": [{"link_name": "branch1"}, {"link_name": "branch2"}],
    }
    operator = MergeOperator(config)

    errors = []
    warnings = []
    available_features = []
    operator.validate(errors=errors, warnings=warnings, available_features=available_features)
    assert len(errors) > 0
    assert any("merge_type" in str(err).lower() for err in errors)


def test_validation_requires_column_option_for_column_merge():
    """Validation fails when column_option missing for column merge."""
    config = {
        "merge_type": "columns",
        "input_links": [{"link_name": "branch1"}, {"link_name": "branch2"}],
    }
    operator = MergeOperator(config)

    errors = []
    warnings = []
    available_features = []
    operator.validate(errors=errors, warnings=warnings, available_features=available_features)
    assert len(errors) > 0
    assert any("column_option" in str(err).lower() for err in errors)


def test_validation_requires_minimum_two_input_links():
    """Validation fails when fewer than 2 input links provided."""
    config = {
        "merge_type": "rows",
        "input_links": [{"link_name": "branch1"}],
    }
    operator = MergeOperator(config)

    errors = []
    warnings = []
    available_features = []
    operator.validate(errors=errors, warnings=warnings, available_features=available_features)
    assert len(errors) > 0


def test_validation_rejects_invalid_merge_type():
    """Validation fails for invalid merge_type value."""
    config = {
        "merge_type": "invalid",
        "input_links": [{"link_name": "branch1"}, {"link_name": "branch2"}],
    }
    operator = MergeOperator(config)

    errors = []
    warnings = []
    available_features = []
    operator.validate(errors=errors, warnings=warnings, available_features=available_features)
    assert len(errors) > 0


def test_validation_rejects_invalid_column_option():
    """Validation fails for invalid column_option value."""
    config = {
        "merge_type": "columns",
        "column_option": "invalid",
        "input_links": [{"link_name": "branch1"}, {"link_name": "branch2"}],
    }
    operator = MergeOperator(config)

    errors = []
    warnings = []
    available_features = []
    operator.validate(errors=errors, warnings=warnings, available_features=available_features)
    assert len(errors) > 0


def test_validation_passes_with_valid_row_config():
    """Validation passes with valid row merge configuration."""
    config = {
        "merge_type": "rows",
        "input_links": [{"link_name": "branch1"}, {"link_name": "branch2"}],
    }
    operator = MergeOperator(config)

    errors = []
    warnings = []
    available_features = []
    operator.validate(errors=errors, warnings=warnings, available_features=available_features)
    assert len(errors) == 0


def test_validation_passes_with_valid_column_config():
    """Validation passes with valid column merge configuration."""
    config = {
        "merge_type": "columns",
        "column_option": "inner_join",
        "input_links": [{"link_name": "branch1"}, {"link_name": "branch2"}],
    }
    operator = MergeOperator(config)

    errors = []
    warnings = []
    available_features = []
    operator.validate(errors=errors, warnings=warnings, available_features=available_features)
    assert len(errors) == 0


# ---------------------------------------------------------------------------
# 5. Metadata generation
# ---------------------------------------------------------------------------


def test_transform_returns_metadata():
    """transform() returns metadata dictionary when merging tables."""
    table1 = make_table(num_rows=2, id_prefix="a")
    table2 = make_table(num_rows=2, id_prefix="b")

    operator = make_operator()
    _, metadata = operator.transform(table=pa.table({}), tables={"branch1": table1, "branch2": table2})

    assert isinstance(metadata, dict)


def test_metadata_contains_total_docs():
    """Metadata contains total_docs_count."""
    table1 = make_table(num_rows=2, id_prefix="a")
    table2 = make_table(num_rows=2, id_prefix="b")

    operator = make_operator()
    _, metadata = operator.transform(table=pa.table({}), tables={"branch1": table1, "branch2": table2})

    assert Metrics.External.TOTAL_DOCS in metadata
    assert metadata[Metrics.External.TOTAL_DOCS] == 4


def test_metadata_contains_processed_docs():
    """Metadata contains processed_docs count."""
    table1 = make_table(num_rows=2, id_prefix="a")
    table2 = make_table(num_rows=2, id_prefix="b")

    operator = make_operator()
    _, metadata = operator.transform(table=pa.table({}), tables={"branch1": table1, "branch2": table2})

    assert Metrics.External.PROCESSED_DOCS in metadata
    assert metadata[Metrics.External.PROCESSED_DOCS] == 4


# ---------------------------------------------------------------------------
# 6. Edge cases
# ---------------------------------------------------------------------------


def test_empty_table_handling():
    """Operator handles empty tables gracefully."""
    table1 = pa.table({"id": [], "name": [], "size": []})
    table2 = make_table(num_rows=2, id_prefix="b")

    operator = make_operator()
    result_tables, _ = operator.transform(table=pa.table({}), tables={"branch1": table1, "branch2": table2})
    result = result_tables[0]

    assert result.num_rows == 2


def test_single_row_tables():
    """Operator works with single-row tables."""
    table1 = make_table(num_rows=1, id_prefix="a")
    table2 = make_table(num_rows=1, id_prefix="b")

    operator = make_operator()
    result_tables, _ = operator.transform(table=pa.table({}), tables={"branch1": table1, "branch2": table2})
    result = result_tables[0]

    assert result.num_rows == 2


def test_tables_with_different_column_counts():
    """Column merge handles tables with different numbers of columns."""
    table1 = make_table(num_rows=2, id_prefix="", extra_columns={"extra1": [1, 2]})
    table2 = make_table(num_rows=2, id_prefix="")

    config = {
        "merge_type": "columns",
        "column_option": "inner_join",
        "input_links": [{"link_name": "branch1"}, {"link_name": "branch2"}],
    }
    operator = MergeOperator(config)

    result_tables, _ = operator.transform(table=pa.table({}), tables={"branch1": table1, "branch2": table2})
    result = result_tables[0]

    assert "extra1" in result.column_names


# ---------------------------------------------------------------------------
# 7. Operator properties
# ---------------------------------------------------------------------------


def test_short_name_matches_constant():
    """short_name matches OperatorConstants.Operators.MERGE."""
    assert MergeOperator.short_name == OperatorConstants.Operators.MERGE


def test_short_name_value():
    """short_name is 'merge'."""
    assert MergeOperator.short_name == "merge"


def test_category_is_functional():
    """Operator category is Functional."""
    from docpipe.core.operators.abstract_operator import OperatorCategory

    assert MergeOperator.category == OperatorCategory.Functional


def test_get_metadata_returns_dict():
    """get_metadata() returns a dictionary."""
    meta = MergeOperator.get_metadata()
    assert isinstance(meta, dict)


def test_get_metadata_contains_required_keys():
    """get_metadata() contains required operator metadata keys."""
    meta = MergeOperator.get_metadata()

    assert OperatorConstants.Misc.IS_OPERATOR_AVAILABLE in meta
    assert OperatorConstants.Misc.LABEL in meta
    assert OperatorConstants.Config.ATTRIBUTES in meta


# ---------------------------------------------------------------------------
# 8. Complex type handling
# ---------------------------------------------------------------------------


def test_column_merge_with_list_columns():
    """Column merge handles list columns correctly by remapping without suffix."""
    table1 = pa.table(
        {
            "id": ["1", "2"],
            "tags": [[1, 2], [3, 4]],
        }
    )
    table2 = pa.table(
        {
            "id": ["1", "2"],
            "categories": [["a", "b"], ["c", "d"]],
        }
    )

    config = {
        "merge_type": "columns",
        "column_option": "inner_join",
        "input_links": [{"link_name": "branch1"}, {"link_name": "branch2"}],
    }
    operator = MergeOperator(config)

    result_tables, _ = operator.transform(table=pa.table({}), tables={"branch1": table1, "branch2": table2})
    result = result_tables[0]

    # Complex types (lists, structs) are remapped without suffix
    assert "tags" in result.column_names
    assert "categories" in result.column_names
    assert result.num_rows == 2


def test_column_merge_with_struct_columns():
    """Column merge handles struct columns correctly by remapping without suffix."""
    table1 = pa.table(
        {
            "id": ["1", "2"],
            "metadata": [{"key": "value1"}, {"key": "value2"}],
        }
    )
    table2 = pa.table(
        {
            "id": ["1", "2"],
            "info": [{"data": "info1"}, {"data": "info2"}],
        }
    )

    config = {
        "merge_type": "columns",
        "column_option": "inner_join",
        "input_links": [{"link_name": "branch1"}, {"link_name": "branch2"}],
    }
    operator = MergeOperator(config)

    result_tables, _ = operator.transform(table=pa.table({}), tables={"branch1": table1, "branch2": table2})
    result = result_tables[0]

    # Complex types (lists, structs) are remapped without suffix
    assert "metadata" in result.column_names
    assert "info" in result.column_names
    assert result.num_rows == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
