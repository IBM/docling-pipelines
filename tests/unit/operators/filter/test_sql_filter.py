#!/usr/bin/env python3
"""
Unit tests for SQLFilterOperator.
Tests filtering rows from a PyArrow table using SQL WHERE clause criteria.
"""

import sys
import pytest
from pathlib import Path

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent.parent.parent.parent.parent / "src" / "datasift_opensource" / "backend"
sys.path.insert(0, str(backend_dir))

import pyarrow as pa

from core.operators.universal.filter.sql_filter import (
    SQLFilterOperator,
    json_to_sql_where,
    convert_operator,
    format_value,
    process_condition,
    FILTER_LOGICAL_OPERATOR_AND,
    FILTER_LOGICAL_OPERATOR_OR,
)
from common.util.constants import OperatorConstants, Metrics
from common.exceptions.datasift_exceptions import DatasiftException


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_table(num_rows: int = 5) -> pa.Table:
    """
    Create a standard test PyArrow table.
    Includes 'name' column required by OperatorUtils.find_skipped_docs.
    """
    return pa.table({
        "id": [str(i) for i in range(1, num_rows + 1)],
        "name": [f"doc_{i}.txt" for i in range(1, num_rows + 1)],
        "content": [f"Document content {i}" for i in range(1, num_rows + 1)],
        "score": [float(i * 2) for i in range(1, num_rows + 1)],
        "language": ["en", "fr", "en", "de", "en"][:num_rows],
        "word_count": [100, 200, 50, 300, 150][:num_rows],
    })


def make_operator(config: dict) -> SQLFilterOperator:
    return SQLFilterOperator(config)


# ---------------------------------------------------------------------------
# 1. Basic filtering
# ---------------------------------------------------------------------------

def test_basic_filter_greater_than():
    """Filter rows where score > 5 keeps only rows with score 6, 8, 10."""
    table = make_table()
    operator = make_operator({OperatorConstants.FILTER_CRITERIA_LIST: ["score > 5"]})
    result_tables, metadata = operator.transform(table)
    result = result_tables[0]

    assert result.num_rows == 3, f"Expected 3 rows, got {result.num_rows}"
    scores = result["score"].to_pylist()
    assert all(s > 5 for s in scores), f"All scores should be > 5, got {scores}"


def test_basic_filter_equals():
    """Filter rows where language = 'en'."""
    table = make_table()
    operator = make_operator({OperatorConstants.FILTER_CRITERIA_LIST: ["language = 'en'"]})
    result_tables, metadata = operator.transform(table)
    result = result_tables[0]

    assert result.num_rows == 3
    languages = result["language"].to_pylist()
    assert all(lang == "en" for lang in languages)


def test_basic_filter_less_than_or_equal():
    """Filter rows where word_count <= 150."""
    table = make_table()
    operator = make_operator({OperatorConstants.FILTER_CRITERIA_LIST: ["word_count <= 150"]})
    result_tables, metadata = operator.transform(table)
    result = result_tables[0]

    word_counts = result["word_count"].to_pylist()
    assert all(wc <= 150 for wc in word_counts)


# ---------------------------------------------------------------------------
# 2. AND logical operator
# ---------------------------------------------------------------------------

def test_and_logical_operator():
    """Multiple criteria with AND: score > 2 AND language = 'en'."""
    table = make_table()
    operator = make_operator({
        OperatorConstants.FILTER_CRITERIA_LIST: ["score > 2", "language = 'en'"],
        OperatorConstants.FILTER_LOGICAL_OPERATOR_KEY: FILTER_LOGICAL_OPERATOR_AND,
    })
    result_tables, metadata = operator.transform(table)
    result = result_tables[0]

    for row_idx in range(result.num_rows):
        score = result["score"][row_idx].as_py()
        lang = result["language"][row_idx].as_py()
        assert score > 2, f"score should be > 2, got {score}"
        assert lang == "en", f"language should be 'en', got {lang}"


def test_and_logical_operator_no_match():
    """AND criteria that cannot both be satisfied returns empty table."""
    table = make_table()
    operator = make_operator({
        OperatorConstants.FILTER_CRITERIA_LIST: ["score > 8", "score < 2"],
        OperatorConstants.FILTER_LOGICAL_OPERATOR_KEY: FILTER_LOGICAL_OPERATOR_AND,
    })
    result_tables, metadata = operator.transform(table)
    result = result_tables[0]

    assert result.num_rows == 0


# ---------------------------------------------------------------------------
# 3. OR logical operator
# ---------------------------------------------------------------------------

def test_or_logical_operator():
    """Multiple criteria with OR: language = 'fr' OR language = 'de'."""
    table = make_table()
    operator = make_operator({
        OperatorConstants.FILTER_CRITERIA_LIST: ["language = 'fr'", "language = 'de'"],
        OperatorConstants.FILTER_LOGICAL_OPERATOR_KEY: FILTER_LOGICAL_OPERATOR_OR,
    })
    result_tables, metadata = operator.transform(table)
    result = result_tables[0]

    assert result.num_rows == 2
    languages = result["language"].to_pylist()
    assert set(languages) == {"fr", "de"}


def test_or_logical_operator_broader_match():
    """OR criteria: score < 3 OR score > 8 — picks rows at both ends."""
    table = make_table()
    operator = make_operator({
        OperatorConstants.FILTER_CRITERIA_LIST: ["score < 3", "score > 8"],
        OperatorConstants.FILTER_LOGICAL_OPERATOR_KEY: FILTER_LOGICAL_OPERATOR_OR,
    })
    result_tables, metadata = operator.transform(table)
    result = result_tables[0]

    scores = result["score"].to_pylist()
    assert all(s < 3 or s > 8 for s in scores)


# ---------------------------------------------------------------------------
# 4. JSON criteria
# ---------------------------------------------------------------------------

def test_filter_criteria_json_simple():
    """Filter using filter_criteria_json dict with a single condition."""
    table = make_table()
    criteria_json = {
        "variable": "score",
        "operator": ">",
        "value": 5,
    }
    operator = make_operator({OperatorConstants.FILTER_CRITERIA_JSON: criteria_json})
    result_tables, metadata = operator.transform(table)
    result = result_tables[0]

    scores = result["score"].to_pylist()
    assert all(s > 5 for s in scores)


def test_filter_criteria_json_nested_and():
    """Filter using filter_criteria_json with nested AND conditions."""
    table = make_table()
    criteria_json = {
        "logical_operator": "AND",
        "criteria_list": [
            {"variable": "score", "operator": ">", "value": 2},
            {"variable": "language", "operator": "=", "value": "en"},
        ],
    }
    operator = make_operator({OperatorConstants.FILTER_CRITERIA_JSON: criteria_json})
    result_tables, metadata = operator.transform(table)
    result = result_tables[0]

    for row_idx in range(result.num_rows):
        score = result["score"][row_idx].as_py()
        lang = result["language"][row_idx].as_py()
        assert score > 2
        assert lang == "en"


def test_filter_criteria_json_nested_or():
    """Filter using filter_criteria_json with nested OR conditions."""
    table = make_table()
    criteria_json = {
        "logical_operator": "OR",
        "criteria_list": [
            {"variable": "language", "operator": "=", "value": "fr"},
            {"variable": "language", "operator": "=", "value": "de"},
        ],
    }
    operator = make_operator({OperatorConstants.FILTER_CRITERIA_JSON: criteria_json})
    result_tables, metadata = operator.transform(table)
    result = result_tables[0]

    assert result.num_rows == 2
    languages = result["language"].to_pylist()
    assert set(languages) == {"fr", "de"}


# ---------------------------------------------------------------------------
# 5. Features to drop
# ---------------------------------------------------------------------------

def test_features_to_drop_removes_column():
    """features_to_drop removes specified columns from output."""
    table = make_table()
    operator = make_operator({
        OperatorConstants.FILTER_CRITERIA_LIST: ["score > 0"],
        OperatorConstants.FILTER_FEATURES_TO_DROP_KEY: ["language"],
    })
    result_tables, metadata = operator.transform(table)
    result = result_tables[0]

    assert "language" not in result.column_names
    assert "score" in result.column_names
    assert "content" in result.column_names


def test_features_to_drop_multiple_columns():
    """features_to_drop removes multiple columns."""
    table = make_table()
    operator = make_operator({
        OperatorConstants.FILTER_CRITERIA_LIST: ["score > 0"],
        OperatorConstants.FILTER_FEATURES_TO_DROP_KEY: ["language", "word_count"],
    })
    result_tables, metadata = operator.transform(table)
    result = result_tables[0]

    assert "language" not in result.column_names
    assert "word_count" not in result.column_names
    assert "score" in result.column_names


def test_features_to_drop_without_filter():
    """features_to_drop works even without filter criteria (no WHERE clause)."""
    table = make_table()
    operator = make_operator({
        OperatorConstants.FILTER_FEATURES_TO_DROP_KEY: ["language"],
    })
    result_tables, metadata = operator.transform(table)
    result = result_tables[0]

    assert "language" not in result.column_names
    assert result.num_rows == table.num_rows


# ---------------------------------------------------------------------------
# 6. Empty result
# ---------------------------------------------------------------------------

def test_filter_returns_empty_table():
    """Filter that matches no rows returns an empty table."""
    table = make_table()
    operator = make_operator({OperatorConstants.FILTER_CRITERIA_LIST: ["score > 9999"]})
    result_tables, metadata = operator.transform(table)
    result = result_tables[0]

    assert result.num_rows == 0
    # Schema should still be intact
    assert set(result.column_names) == set(table.column_names)


# ---------------------------------------------------------------------------
# 7. All rows pass
# ---------------------------------------------------------------------------

def test_filter_all_rows_pass():
    """Filter that matches all rows returns the full table."""
    table = make_table()
    operator = make_operator({OperatorConstants.FILTER_CRITERIA_LIST: ["score > 0"]})
    result_tables, metadata = operator.transform(table)
    result = result_tables[0]

    assert result.num_rows == table.num_rows


def test_no_filter_criteria_returns_full_table():
    """No filter criteria at all returns the full table unchanged."""
    table = make_table()
    operator = make_operator({})
    result_tables, metadata = operator.transform(table)
    result = result_tables[0]

    assert result.num_rows == table.num_rows


# ---------------------------------------------------------------------------
# 8. Validation errors — protected columns
# ---------------------------------------------------------------------------

def test_validate_rejects_drop_of_id_column():
    """Dropping the protected 'id' column should add a validation error."""
    operator = make_operator({
        OperatorConstants.FILTER_FEATURES_TO_DROP_KEY: [OperatorConstants.ID],
    })
    errors = []
    warnings = []
    available_features = ["id", "name", "content", "score", "language", "word_count"]
    operator.validate(errors, warnings, available_features)

    assert len(errors) > 0, "Expected a validation error for dropping 'id'"


def test_validate_rejects_drop_of_content_column():
    """Dropping the protected 'content' column should add a validation error."""
    operator = make_operator({
        OperatorConstants.FILTER_FEATURES_TO_DROP_KEY: [OperatorConstants.DOC_COLUMN_DEFAULT],
    })
    errors = []
    warnings = []
    available_features = ["id", "name", "content", "score", "language", "word_count"]
    operator.validate(errors, warnings, available_features)

    assert len(errors) > 0, "Expected a validation error for dropping 'content'"


def test_validate_rejects_drop_of_pages_processed_column():
    """Dropping the protected 'pages_processed' column should add a validation error."""
    operator = make_operator({
        OperatorConstants.FILTER_FEATURES_TO_DROP_KEY: [OperatorConstants.PAGES_PROCESSED_COLUMN],
    })
    errors = []
    warnings = []
    available_features = ["id", "name", "content", "score", "language", "word_count", "pages_processed"]
    operator.validate(errors, warnings, available_features)

    assert len(errors) > 0, "Expected a validation error for dropping 'pages_processed'"


# ---------------------------------------------------------------------------
# 9. Column not found
# ---------------------------------------------------------------------------

def test_validate_rejects_filter_on_nonexistent_column():
    """Filtering on a non-existent column should add a validation error."""
    operator = make_operator({
        OperatorConstants.FILTER_CRITERIA_LIST: ["nonexistent_col > 5"],
    })
    errors = []
    warnings = []
    available_features = ["id", "name", "content", "score", "language", "word_count"]
    operator.validate(errors, warnings, available_features)

    assert len(errors) > 0, "Expected a validation error for non-existent column"
    # The error message should mention the invalid feature
    error_messages = [str(e) for e in errors]
    assert any("nonexistent_col" in msg for msg in error_messages)


def test_validate_warns_when_no_criteria_provided():
    """No filter criteria at all should produce a warning."""
    operator = make_operator({})
    errors = []
    warnings = []
    available_features = ["id", "name", "content", "score", "language", "word_count"]
    operator.validate(errors, warnings, available_features)

    assert len(warnings) > 0, "Expected a warning when no filter criteria is provided"


def test_invalid_column_in_transform_returns_original_table():
    """
    When filter criteria references a column not in the table,
    has_invalid_columns returns True and the original table is returned.
    """
    table = make_table()
    operator = make_operator({
        OperatorConstants.FILTER_CRITERIA_LIST: ["nonexistent_col > 5"],
    })
    result_tables, metadata = operator.transform(table)
    result = result_tables[0]

    # Original table is returned unchanged
    assert result.num_rows == table.num_rows


# ---------------------------------------------------------------------------
# 10. get_metadata()
# ---------------------------------------------------------------------------

def test_get_metadata_is_operator_available():
    """get_metadata() returns IS_OPERATOR_AVAILABLE: True."""
    operator = make_operator({})
    meta = operator.get_metadata()

    assert meta[OperatorConstants.IS_OPERATOR_AVAILABLE] is True


def test_get_metadata_structure():
    """get_metadata() returns expected keys."""
    operator = make_operator({})
    meta = operator.get_metadata()

    assert OperatorConstants.CATEGORY in meta
    assert OperatorConstants.LABEL in meta
    assert OperatorConstants.ATTRIBUTES in meta
    assert meta[OperatorConstants.LABEL] == "Annotation Filter"


def test_get_metadata_attributes_keys():
    """get_metadata() attributes contain all expected operator parameters."""
    operator = make_operator({})
    meta = operator.get_metadata()
    attrs = meta[OperatorConstants.ATTRIBUTES]

    assert OperatorConstants.FILTER_CRITERIA_LIST in attrs
    assert OperatorConstants.FILTER_CRITERIA_JSON in attrs
    assert OperatorConstants.FILTER_LOGICAL_OPERATOR_KEY in attrs
    assert OperatorConstants.FILTER_FEATURES_TO_DROP_KEY in attrs


# ---------------------------------------------------------------------------
# 11. Helper functions
# ---------------------------------------------------------------------------

class TestConvertOperator:
    def test_equals(self):
        assert convert_operator("=") == "="

    def test_double_equals(self):
        assert convert_operator("==") == "="

    def test_not_equals(self):
        assert convert_operator("!=") == "!="

    def test_greater_than(self):
        assert convert_operator(">") == ">"

    def test_less_than(self):
        assert convert_operator("<") == "<"

    def test_greater_than_or_equal(self):
        assert convert_operator(">=") == ">="

    def test_less_than_or_equal(self):
        assert convert_operator("<=") == "<="

    def test_in_operator(self):
        assert convert_operator("in") == "IN"

    def test_not_in_operator(self):
        assert convert_operator("not in") == "NOT IN"

    def test_like_operator(self):
        assert convert_operator("like") == "LIKE"

    def test_is_null(self):
        assert convert_operator("is null") == "IS NULL"

    def test_is_not_null(self):
        assert convert_operator("is not null") == "IS NOT NULL"

    def test_between(self):
        assert convert_operator("between") == "BETWEEN"

    def test_case_insensitive(self):
        assert convert_operator("IN") == "IN"
        assert convert_operator("Like") == "LIKE"

    def test_unknown_operator_raises(self):
        with pytest.raises(DatasiftException):
            convert_operator("UNKNOWN_OP")

    def test_non_string_raises(self):
        with pytest.raises(DatasiftException):
            convert_operator(123)


class TestFormatValue:
    def test_none_returns_null(self):
        assert format_value(None) == "NULL"

    def test_integer(self):
        assert format_value(42) == "42"

    def test_float(self):
        assert format_value(3.14) == "3.14"

    def test_string_number_int(self):
        assert format_value("10") == "10"

    def test_string_number_float(self):
        assert format_value("3.14") == "3.14"

    def test_string_text(self):
        assert format_value("hello") == "'hello'"

    def test_string_with_single_quote(self):
        # Single quotes in strings should be escaped
        result = format_value("it's")
        assert "it''s" in result

    def test_list_of_ints(self):
        result = format_value([1, 2, 3])
        assert result == "(1, 2, 3)"

    def test_list_of_strings(self):
        result = format_value(["a", "b"])
        assert result == "('a', 'b')"

    def test_zero(self):
        assert format_value(0) == "0"

    def test_negative_number(self):
        assert format_value(-5) == "-5"


class TestProcessCondition:
    def test_simple_equals(self):
        condition = {"variable": "score", "operator": "=", "value": 5}
        result = process_condition(condition)
        assert result == "score = 5"

    def test_greater_than(self):
        condition = {"variable": "score", "operator": ">", "value": 3}
        result = process_condition(condition)
        assert result == "score > 3"

    def test_string_value(self):
        condition = {"variable": "language", "operator": "=", "value": "en"}
        result = process_condition(condition)
        assert result == "language = 'en'"

    def test_is_null(self):
        condition = {"variable": "score", "operator": "is null"}
        result = process_condition(condition)
        assert result == "score IS NULL"

    def test_is_not_null(self):
        condition = {"variable": "score", "operator": "is not null"}
        result = process_condition(condition)
        assert result == "score IS NOT NULL"

    def test_between_list(self):
        condition = {"variable": "score", "operator": "between", "value": [1, 10]}
        result = process_condition(condition)
        assert result == "score BETWEEN 1 AND 10"

    def test_between_string(self):
        condition = {"variable": "score", "operator": "between", "value": "1, 10"}
        result = process_condition(condition)
        assert result == "score BETWEEN 1 AND 10"

    def test_in_list(self):
        condition = {"variable": "language", "operator": "in", "value": ["en", "fr"]}
        result = process_condition(condition)
        assert "language IN" in result
        assert "'en'" in result
        assert "'fr'" in result

    def test_in_string(self):
        condition = {"variable": "language", "operator": "in", "value": "en, fr"}
        result = process_condition(condition)
        assert "language IN" in result

    def test_missing_variable_raises(self):
        condition = {"operator": "=", "value": 5}
        with pytest.raises(DatasiftException):
            process_condition(condition)

    def test_missing_operator_raises(self):
        condition = {"variable": "score", "value": 5}
        with pytest.raises(DatasiftException):
            process_condition(condition)


class TestJsonToSqlWhere:
    def test_empty_dict_returns_empty(self):
        result = json_to_sql_where({})
        assert result == ""

    def test_none_returns_empty(self):
        result = json_to_sql_where(None)
        assert result == ""

    def test_simple_condition(self):
        condition = {"variable": "score", "operator": ">", "value": 5}
        result = json_to_sql_where(condition)
        assert result.startswith("WHERE")
        assert "score > 5" in result

    def test_nested_and_group(self):
        group = {
            "logical_operator": "AND",
            "criteria_list": [
                {"variable": "score", "operator": ">", "value": 2},
                {"variable": "language", "operator": "=", "value": "en"},
            ],
        }
        result = json_to_sql_where(group)
        assert result.startswith("WHERE")
        assert "AND" in result
        assert "score > 2" in result
        assert "language = 'en'" in result

    def test_nested_or_group(self):
        group = {
            "logical_operator": "OR",
            "criteria_list": [
                {"variable": "language", "operator": "=", "value": "fr"},
                {"variable": "language", "operator": "=", "value": "de"},
            ],
        }
        result = json_to_sql_where(group)
        assert result.startswith("WHERE")
        assert "OR" in result


# ---------------------------------------------------------------------------
# 12. Metadata structure from transform
# ---------------------------------------------------------------------------

def test_transform_metadata_contains_processed_docs():
    """transform() metadata contains processed_docs key."""
    table = make_table()
    operator = make_operator({OperatorConstants.FILTER_CRITERIA_LIST: ["score > 0"]})
    _, metadata = operator.transform(table)

    assert Metrics.External.PROCESSED_DOCS in metadata
    assert metadata[Metrics.External.PROCESSED_DOCS] == table.num_rows


def test_transform_metadata_contains_total_docs():
    """transform() metadata contains total_docs_count key."""
    table = make_table()
    operator = make_operator({OperatorConstants.FILTER_CRITERIA_LIST: ["score > 0"]})
    _, metadata = operator.transform(table)

    assert Metrics.External.TOTAL_DOCS in metadata
    assert metadata[Metrics.External.TOTAL_DOCS] == table.num_rows


def test_transform_metadata_docs_after_filter():
    """transform() metadata contains docs_after_filter key."""
    table = make_table()
    operator = make_operator({OperatorConstants.FILTER_CRITERIA_LIST: ["score > 5"]})
    _, metadata = operator.transform(table)

    assert "docs_after_filter" in metadata
    assert metadata["docs_after_filter"] == 3


def test_transform_metadata_filter_stats_per_criterion():
    """transform() metadata contains per-criterion filter stats."""
    table = make_table()
    criterion = "score > 5"
    operator = make_operator({OperatorConstants.FILTER_CRITERIA_LIST: [criterion]})
    _, metadata = operator.transform(table)

    key = f"docs_filtered_out_by '{criterion}'"
    assert key in metadata
    assert metadata[key] == 2  # 5 rows total, 3 pass, 2 filtered


# ---------------------------------------------------------------------------
# 13. short_name
# ---------------------------------------------------------------------------

def test_short_name():
    """short_name matches OperatorConstants.SQL_FILTER."""
    assert SQLFilterOperator.short_name == OperatorConstants.SQL_FILTER


# ---------------------------------------------------------------------------
# 14. Edge cases
# ---------------------------------------------------------------------------

def test_filter_with_single_row_table():
    """Filter works correctly on a single-row table."""
    table = pa.table({
        "id": ["1"],
        "name": ["doc_1.txt"],
        "content": ["hello"],
        "score": [5.0],
        "language": ["en"],
        "word_count": [10],
    })
    operator = make_operator({OperatorConstants.FILTER_CRITERIA_LIST: ["score > 3"]})
    result_tables, metadata = operator.transform(table)
    result = result_tables[0]

    assert result.num_rows == 1


def test_filter_with_single_row_table_no_match():
    """Filter on single-row table that doesn't match returns empty table."""
    table = pa.table({
        "id": ["1"],
        "name": ["doc_1.txt"],
        "content": ["hello"],
        "score": [1.0],
        "language": ["en"],
        "word_count": [10],
    })
    operator = make_operator({OperatorConstants.FILTER_CRITERIA_LIST: ["score > 3"]})
    result_tables, metadata = operator.transform(table)
    result = result_tables[0]

    assert result.num_rows == 0


def test_filter_preserves_column_names():
    """Filtered table preserves all column names from input."""
    table = make_table()
    operator = make_operator({OperatorConstants.FILTER_CRITERIA_LIST: ["score > 5"]})
    result_tables, _ = operator.transform(table)
    result = result_tables[0]

    assert set(result.column_names) == set(table.column_names)


def test_filter_and_drop_combined():
    """Filter criteria and features_to_drop can be combined."""
    table = make_table()
    operator = make_operator({
        OperatorConstants.FILTER_CRITERIA_LIST: ["score > 5"],
        OperatorConstants.FILTER_FEATURES_TO_DROP_KEY: ["language"],
    })
    result_tables, _ = operator.transform(table)
    result = result_tables[0]

    # Filtered rows
    assert result.num_rows == 3
    # Dropped column
    assert "language" not in result.column_names
    # Other columns still present
    assert "score" in result.column_names
    assert "content" in result.column_names


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

