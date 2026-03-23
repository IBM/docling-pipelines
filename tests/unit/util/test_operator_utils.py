#!/usr/bin/env python3
"""
Unit tests for operator_utils module.
Tests utility functions for table manipulation, validation, and feature management.
"""

import pytest
import pyarrow as pa

from common.util.operator_utils import (
    remove_rows,
    remove_all_rows,
    find_doc_count,
    find_doc_count_from_tables,
    validate_link_name,
    doc_id_hash,
    decode_binary_content,
    upsert_fields_in_schema,
    remove_internal_metrics_from_metadata,
    drop_features_from_table,
    rename_features_and_save_original,
    get_mandatory_features,
    validate_filter_criteria,
    _validate_criteria_json,
)
from common.constants.operator_constants import OperatorConstants
from common.constants.constants import internal_metrics
from common.exceptions.datasift_exceptions import FlowValidationException


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_table(num_rows=3, include_name=True, extra_columns=None) -> pa.Table:
    """Create a test PyArrow table with id and optional name columns."""
    data = {
        OperatorConstants.Columns.ID: [str(i + 1) for i in range(num_rows)],
    }
    if include_name:
        data[OperatorConstants.Columns.NAME] = [f"doc_{i + 1}" for i in range(num_rows)]
    if extra_columns:
        data.update(extra_columns)
    return pa.table(data)


# ---------------------------------------------------------------------------
# 1. remove_rows tests
# ---------------------------------------------------------------------------


def test_remove_rows_basic():
    """Remove specific rows by index."""
    table = make_table(num_rows=5)
    result = remove_rows(table=table, remove_row_idx=[1, 3])

    assert result.num_rows == 3
    ids = result[OperatorConstants.Columns.ID].to_pylist()
    assert ids == ["1", "3", "5"]


def test_remove_rows_empty_list():
    """Removing no rows returns original table."""
    table = make_table(num_rows=3)
    result = remove_rows(table=table, remove_row_idx=[])

    assert result.num_rows == 3


def test_remove_rows_all_rows():
    """Remove all rows returns empty table."""
    table = make_table(num_rows=3)
    result = remove_rows(table=table, remove_row_idx=[0, 1, 2])

    assert result.num_rows == 0


def test_remove_rows_preserves_columns():
    """Removing rows preserves all columns."""
    table = make_table(num_rows=3, extra_columns={"content": ["a", "b", "c"]})
    result = remove_rows(table=table, remove_row_idx=[1])

    assert set(result.column_names) == set(table.column_names)


# ---------------------------------------------------------------------------
# 2. remove_all_rows tests
# ---------------------------------------------------------------------------


def test_remove_all_rows_by_id():
    """Remove rows by document ID."""
    table = make_table(num_rows=5)
    result = remove_all_rows(table=table, remove_row_id=["2", "4"])

    assert result.num_rows == 3
    ids = result[OperatorConstants.Columns.ID].to_pylist()
    assert ids == ["1", "3", "5"]


def test_remove_all_rows_empty_list():
    """Removing no IDs returns original table."""
    table = make_table(num_rows=3)
    result = remove_all_rows(table=table, remove_row_id=[])

    assert result.num_rows == 3


def test_remove_all_rows_nonexistent_id():
    """Removing nonexistent ID doesn't affect table."""
    table = make_table(num_rows=3)
    result = remove_all_rows(table=table, remove_row_id=["999"])

    assert result.num_rows == 3


def test_remove_all_rows_all_ids():
    """Remove all rows by ID."""
    table = make_table(num_rows=3)
    result = remove_all_rows(table=table, remove_row_id=["1", "2", "3"])

    assert result.num_rows == 0


# ---------------------------------------------------------------------------
# 3. find_doc_count tests
# ---------------------------------------------------------------------------


def test_find_doc_count_with_name_column():
    """Count unique documents using name column."""
    table = pa.table(
        {
            OperatorConstants.Columns.ID: ["1", "2", "3", "4"],
            OperatorConstants.Columns.NAME: ["doc_a", "doc_a", "doc_b", "doc_b"],
        }
    )
    count = find_doc_count(table=table)

    assert count == 2  # Two unique document names


def test_find_doc_count_without_name_column():
    """Count rows when name column is missing."""
    table = pa.table(
        {
            OperatorConstants.Columns.ID: ["1", "2", "3"],
        }
    )
    count = find_doc_count(table=table)

    assert count == 3  # Falls back to row count


def test_find_doc_count_empty_table():
    """Count for empty table returns 0."""
    table = pa.table(
        {
            OperatorConstants.Columns.ID: pa.array([], type=pa.string()),
        }
    )
    count = find_doc_count(table=table)

    assert count == 0


def test_find_doc_count_none_table():
    """Count for None table returns 0."""
    count = find_doc_count(table=None)

    assert count == 0


# ---------------------------------------------------------------------------
# 4. find_doc_count_from_tables tests
# ---------------------------------------------------------------------------


def test_find_doc_count_from_tables_multiple():
    """Count unique documents across multiple tables."""
    table1 = pa.table(
        {
            OperatorConstants.Columns.NAME: ["doc_a", "doc_b"],
        }
    )
    table2 = pa.table(
        {
            OperatorConstants.Columns.NAME: ["doc_b", "doc_c"],
        }
    )
    count = find_doc_count_from_tables(tables=[table1, table2])

    assert count == 3  # Three unique documents


def test_find_doc_count_from_tables_empty_list():
    """Count from empty list returns 0."""
    count = find_doc_count_from_tables(tables=[])

    assert count == 0


def test_find_doc_count_from_tables_with_empty_table():
    """Count handles empty tables in list."""
    table1 = pa.table(
        {
            OperatorConstants.Columns.NAME: ["doc_a"],
        }
    )
    table2 = pa.table(
        {
            OperatorConstants.Columns.NAME: pa.array([], type=pa.string()),
        }
    )
    count = find_doc_count_from_tables(tables=[table1, table2])

    assert count == 1


# ---------------------------------------------------------------------------
# 5. validate_link_name tests
# ---------------------------------------------------------------------------


def test_validate_link_name_valid():
    """Valid link name passes validation."""
    existing = set()
    errors = []
    validate_link_name(link_name="link1", existing_link_names=existing, errors=errors)

    assert len(errors) == 0
    assert "link1" in existing


def test_validate_link_name_duplicate():
    """Duplicate link name adds error."""
    existing = {"link1"}
    errors = []
    validate_link_name(link_name="Link1", existing_link_names=existing, errors=errors)

    assert len(errors) == 1
    assert "Duplicate link name" in errors[0]


def test_validate_link_name_case_insensitive():
    """Link name validation is case-insensitive."""
    existing = {"link1"}
    errors = []
    validate_link_name(link_name="LINK1", existing_link_names=existing, errors=errors)

    assert len(errors) == 1


def test_validate_link_name_empty():
    """Empty link name adds error."""
    existing = set()
    errors = []
    validate_link_name(link_name="", existing_link_names=existing, errors=errors)

    assert len(errors) == 1
    assert "Missing link name" in errors[0]


def test_validate_link_name_none():
    """None link name adds error."""
    existing = set()
    errors = []
    validate_link_name(link_name=None, existing_link_names=existing, errors=errors)

    assert len(errors) == 1


# ---------------------------------------------------------------------------
# 6. doc_id_hash tests
# ---------------------------------------------------------------------------


def test_doc_id_hash_basic():
    """Hash content produces hex string."""
    content = "test content"
    result = doc_id_hash(content=content)

    assert isinstance(result, str)
    assert len(result) == 128  # SHA3-512 produces 128 hex chars


def test_doc_id_hash_deterministic():
    """Same content produces same hash."""
    content = "test content"
    hash1 = doc_id_hash(content=content)
    hash2 = doc_id_hash(content=content)

    assert hash1 == hash2


def test_doc_id_hash_different_content():
    """Different content produces different hash."""
    hash1 = doc_id_hash(content="content1")
    hash2 = doc_id_hash(content="content2")

    assert hash1 != hash2


def test_doc_id_hash_empty_string():
    """Empty string can be hashed."""
    result = doc_id_hash(content="")

    assert isinstance(result, str)
    assert len(result) == 128


def test_doc_id_hash_unicode():
    """Unicode content can be hashed."""
    content = "こんにちは世界"
    result = doc_id_hash(content=content)

    assert isinstance(result, str)
    assert len(result) == 128


# ---------------------------------------------------------------------------
# 7. decode_binary_content tests
# ---------------------------------------------------------------------------


def test_decode_binary_content_utf8():
    """Decode UTF-8 binary content."""
    binary = "Hello, World!".encode("utf-8")
    result = decode_binary_content(binary_content=binary)

    assert result == "Hello, World!"


def test_decode_binary_content_unicode():
    """Decode Unicode binary content."""
    text = "こんにちは"
    binary = text.encode("utf-8")
    result = decode_binary_content(binary_content=binary)

    assert result == text


def test_decode_binary_content_latin1():
    """Decode Latin-1 encoded content."""
    text = "Café"
    binary = text.encode("latin-1")
    result = decode_binary_content(binary_content=binary)

    # charset_normalizer may detect encoding differently, just verify it returns a string
    assert isinstance(result, str)
    assert len(result) > 0


def test_decode_binary_content_empty():
    """Decode empty binary content."""
    binary = b""
    result = decode_binary_content(binary_content=binary)

    assert result == ""


# ---------------------------------------------------------------------------
# 8. upsert_fields_in_schema tests
# ---------------------------------------------------------------------------


def test_upsert_fields_in_schema_add_new():
    """Add new field to schema."""
    schema = pa.schema(
        [
            pa.field("id", pa.string()),
            pa.field("name", pa.string()),
        ]
    )
    updates = {"age": pa.int64()}

    result = upsert_fields_in_schema(schema=schema, updates=updates)

    assert "age" in result.names
    assert result.field("age").type == pa.int64()


def test_upsert_fields_in_schema_update_existing():
    """Update existing field type."""
    schema = pa.schema(
        [
            pa.field("id", pa.string()),
            pa.field("count", pa.int32()),
        ]
    )
    updates = {"count": pa.int64()}

    result = upsert_fields_in_schema(schema=schema, updates=updates)

    assert result.field("count").type == pa.int64()


def test_upsert_fields_in_schema_multiple_updates():
    """Add and update multiple fields."""
    schema = pa.schema(
        [
            pa.field("id", pa.string()),
        ]
    )
    updates = {
        "name": pa.string(),
        "count": pa.int64(),
    }

    result = upsert_fields_in_schema(schema=schema, updates=updates)

    assert "name" in result.names
    assert "count" in result.names


def test_upsert_fields_in_schema_preserves_order():
    """Existing fields maintain order, new fields appended."""
    schema = pa.schema(
        [
            pa.field("a", pa.string()),
            pa.field("b", pa.string()),
        ]
    )
    updates = {"c": pa.string()}

    result = upsert_fields_in_schema(schema=schema, updates=updates)

    assert result.names[:2] == ["a", "b"]
    assert "c" in result.names


# ---------------------------------------------------------------------------
# 9. remove_internal_metrics_from_metadata tests
# ---------------------------------------------------------------------------


def test_remove_internal_metrics_from_metadata_basic():
    """Remove internal metrics from metadata dict."""
    metadata = {
        "user_metric": "value1",
        "another_metric": "value2",
    }
    # Add some internal metrics
    for metric in list(internal_metrics)[:2]:
        metadata[metric] = "internal_value"

    result = remove_internal_metrics_from_metadata(metadata)

    assert "user_metric" in metadata
    assert "another_metric" in metadata
    assert len(result) > 0  # Internal metrics were removed


def test_remove_internal_metrics_from_metadata_empty():
    """Handle empty metadata dict."""
    metadata = {}
    result = remove_internal_metrics_from_metadata(metadata)

    assert result == {}


def test_remove_internal_metrics_from_metadata_no_internal():
    """Handle metadata with no internal metrics."""
    metadata = {"user_metric": "value"}
    result = remove_internal_metrics_from_metadata(metadata)

    assert result == {}
    assert "user_metric" in metadata


# ---------------------------------------------------------------------------
# 10. drop_features_from_table tests
# ---------------------------------------------------------------------------


def test_drop_features_from_table_basic():
    """Drop specified columns from table."""
    table = pa.table(
        {
            "id": ["1", "2"],
            "name": ["a", "b"],
            "content": ["x", "y"],
        }
    )
    result = drop_features_from_table(["content"], table)

    assert "content" not in result.column_names
    assert "id" in result.column_names
    assert "name" in result.column_names


def test_drop_features_from_table_multiple():
    """Drop multiple columns."""
    table = pa.table(
        {
            "id": ["1"],
            "a": ["x"],
            "b": ["y"],
            "c": ["z"],
        }
    )
    result = drop_features_from_table(["a", "c"], table)

    assert result.column_names == ["id", "b"]


def test_drop_features_from_table_nonexistent():
    """Dropping nonexistent column doesn't error."""
    table = pa.table(
        {
            "id": ["1"],
            "name": ["a"],
        }
    )
    result = drop_features_from_table(["nonexistent"], table)

    assert result.column_names == table.column_names


def test_drop_features_from_table_empty_list():
    """Empty drop list returns original table."""
    table = pa.table(
        {
            "id": ["1"],
            "name": ["a"],
        }
    )
    result = drop_features_from_table([], table)

    assert result.column_names == table.column_names


# ---------------------------------------------------------------------------
# 11. get_mandatory_features tests
# ---------------------------------------------------------------------------


def test_get_mandatory_features_basic():
    """Identify mandatory features."""
    input_features = {
        "field1": {OperatorConstants.Misc.TAGS: [OperatorConstants.Misc.MANDATORY]},
        "field2": {OperatorConstants.Misc.TAGS: []},
        "field3": {OperatorConstants.Misc.TAGS: [OperatorConstants.Misc.MANDATORY]},
    }
    check_features = ["field1", "field2", "field3"]

    result = get_mandatory_features(
        check_features=check_features, input_features=input_features
    )

    assert set(result) == {"field1", "field3"}


def test_get_mandatory_features_none():
    """No mandatory features returns empty list."""
    input_features = {
        "field1": {OperatorConstants.Misc.TAGS: []},
        "field2": {OperatorConstants.Misc.TAGS: []},
    }
    check_features = ["field1", "field2"]

    result = get_mandatory_features(
        check_features=check_features, input_features=input_features
    )

    assert result == []


def test_get_mandatory_features_empty_check_list():
    """Empty check list returns empty result."""
    input_features = {
        "field1": {OperatorConstants.Misc.TAGS: [OperatorConstants.Misc.MANDATORY]},
    }

    result = get_mandatory_features(check_features=[], input_features=input_features)

    assert result == []


def test_get_mandatory_features_no_tags():
    """Features without tags are not mandatory."""
    input_features = {
        "field1": {},
        "field2": {OperatorConstants.Misc.TAGS: [OperatorConstants.Misc.MANDATORY]},
    }
    check_features = ["field1", "field2"]

    result = get_mandatory_features(
        check_features=check_features, input_features=input_features
    )

    assert result == ["field2"]


# ---------------------------------------------------------------------------
# 12. validate_filter_criteria tests
# ---------------------------------------------------------------------------


def test_validate_filter_criteria_valid_list():
    """Valid criteria_list returns True."""
    criteria_list = ["age > 18", "status = 'active'"]
    criteria_json = None

    criteria_valid, json_valid = validate_filter_criteria(
        criteria_list=criteria_list, criteria_json=criteria_json
    )

    assert criteria_valid is True
    assert json_valid is False


def test_validate_filter_criteria_valid_json_leaf():
    """Valid JSON leaf condition returns True."""
    criteria_list = None
    criteria_json = {"variable": "age", "operator": ">", "value": 18}

    criteria_valid, json_valid = validate_filter_criteria(
        criteria_list=criteria_list, criteria_json=criteria_json
    )

    assert criteria_valid is False
    assert json_valid is True


def test_validate_filter_criteria_valid_json_group():
    """Valid JSON group with criteria returns True."""
    criteria_list = None
    criteria_json = {
        "logical_operator": "AND",
        "criteria_list": [
            {"variable": "age", "operator": ">", "value": 18},
            {"variable": "status", "operator": "=", "value": "active"},
        ],
    }

    criteria_valid, json_valid = validate_filter_criteria(
        criteria_list=criteria_list, criteria_json=criteria_json
    )

    assert criteria_valid is False
    assert json_valid is True


def test_validate_filter_criteria_empty_list():
    """Empty criteria_list returns False."""
    criteria_list = []
    criteria_json = None

    criteria_valid, json_valid = validate_filter_criteria(
        criteria_list=criteria_list, criteria_json=criteria_json
    )

    assert criteria_valid is False


def test_validate_filter_criteria_list_with_empty_strings():
    """List with only empty strings returns False."""
    criteria_list = ["", "  ", ""]
    criteria_json = None

    criteria_valid, json_valid = validate_filter_criteria(
        criteria_list=criteria_list, criteria_json=criteria_json
    )

    assert criteria_valid is False


def test_validate_filter_criteria_invalid_json_empty_group():
    """JSON group with empty criteria_list returns False."""
    criteria_list = None
    criteria_json = {"logical_operator": "AND", "criteria_list": []}

    criteria_valid, json_valid = validate_filter_criteria(
        criteria_list=criteria_list, criteria_json=criteria_json
    )

    assert json_valid is False


def test_validate_filter_criteria_nested_json():
    """Nested JSON groups validate correctly."""
    criteria_json = {
        "logical_operator": "OR",
        "criteria_list": [
            {"variable": "age", "operator": ">", "value": 18},
            {
                "logical_operator": "AND",
                "criteria_list": [
                    {"variable": "status", "operator": "=", "value": "active"},
                    {"variable": "verified", "operator": "=", "value": True},
                ],
            },
        ],
    }

    criteria_valid, json_valid = validate_filter_criteria(
        criteria_list=None, criteria_json=criteria_json
    )

    assert json_valid is True


# ---------------------------------------------------------------------------
# 13. _validate_criteria_json tests
# ---------------------------------------------------------------------------


def test_validate_criteria_json_leaf_condition():
    """Leaf condition with variable and operator is valid."""
    criteria = {"variable": "age", "operator": ">"}

    assert _validate_criteria_json(criteria_json=criteria) is True


def test_validate_criteria_json_group_with_valid_items():
    """Group with all valid items is valid."""
    criteria = {
        "criteria_list": [
            {"variable": "age", "operator": ">"},
            {"variable": "name", "operator": "="},
        ]
    }

    assert _validate_criteria_json(criteria_json=criteria) is True


def test_validate_criteria_json_empty_dict():
    """Empty dict is invalid."""
    assert _validate_criteria_json(criteria_json={}) is False


def test_validate_criteria_json_none():
    """None is invalid."""
    assert _validate_criteria_json(criteria_json=None) is False


def test_validate_criteria_json_group_with_invalid_item():
    """Group with any invalid item is invalid."""
    criteria = {
        "criteria_list": [
            {"variable": "age", "operator": ">"},
            {"invalid": "item"},  # Missing variable and operator
        ]
    }

    assert _validate_criteria_json(criteria_json=criteria) is False


def test_validate_criteria_json_group_empty_list():
    """Group with empty criteria_list is invalid."""
    criteria = {"criteria_list": []}

    assert _validate_criteria_json(criteria_json=criteria) is False


# ---------------------------------------------------------------------------
# 14. rename_features_and_save_original tests (Table)
# ---------------------------------------------------------------------------


def test_rename_features_table_basic():
    """Rename columns in PyArrow table."""
    table = pa.table(
        {
            "old_name": ["a", "b"],
            "keep_name": ["x", "y"],
        }
    )
    updated_features = [
        {
            OperatorConstants.Misc.OLD_FEATURE: "old_name",
            OperatorConstants.Misc.NEW_FEATURE: "new_name",
        }
    ]

    result = rename_features_and_save_original(
        updated_features=updated_features, input_features=table
    )

    assert "new_name" in result.column_names
    assert "old_name" not in result.column_names
    assert "keep_name" in result.column_names


def test_rename_features_table_multiple():
    """Rename multiple columns."""
    table = pa.table(
        {
            "a": [1],
            "b": [2],
            "c": [3],
        }
    )
    updated_features = [
        {
            OperatorConstants.Misc.OLD_FEATURE: "a",
            OperatorConstants.Misc.NEW_FEATURE: "x",
        },
        {
            OperatorConstants.Misc.OLD_FEATURE: "b",
            OperatorConstants.Misc.NEW_FEATURE: "y",
        },
    ]

    result = rename_features_and_save_original(
        updated_features=updated_features, input_features=table
    )

    assert set(result.column_names) == {"x", "y", "c"}


def test_rename_features_table_nonexistent_column():
    """Renaming nonexistent column raises KeyError."""
    table = pa.table({"a": [1]})
    updated_features = [
        {
            OperatorConstants.Misc.OLD_FEATURE: "nonexistent",
            OperatorConstants.Misc.NEW_FEATURE: "new",
        }
    ]

    with pytest.raises(KeyError):
        rename_features_and_save_original(
            updated_features=updated_features, input_features=table
        )


def test_rename_features_table_duplicate_new_name():
    """Duplicate new name raises ValueError."""
    table = pa.table({"a": [1], "b": [2]})
    updated_features = [
        {
            OperatorConstants.Misc.OLD_FEATURE: "a",
            OperatorConstants.Misc.NEW_FEATURE: "same",
        },
        {
            OperatorConstants.Misc.OLD_FEATURE: "b",
            OperatorConstants.Misc.NEW_FEATURE: "same",
        },
    ]

    with pytest.raises(ValueError, match="Duplicate name"):
        rename_features_and_save_original(
            updated_features=updated_features, input_features=table
        )


# ---------------------------------------------------------------------------
# 15. rename_features_and_save_original tests (Dict)
# ---------------------------------------------------------------------------


def test_rename_features_dict_basic():
    """Rename features in dict and save original name."""
    input_features = {
        "old_name": {"type": "string"},
        "keep_name": {"type": "int"},
    }
    updated_features = [
        {
            OperatorConstants.Misc.OLD_FEATURE: "old_name",
            OperatorConstants.Misc.NEW_FEATURE: "new_name",
        }
    ]

    rename_features_and_save_original(
        updated_features=updated_features, input_features=input_features
    )

    assert "new_name" in input_features
    assert "old_name" not in input_features
    assert (
        input_features["new_name"][OperatorConstants.Misc.ORIGINAL_FEATURE]
        == "old_name"
    )


def test_rename_features_dict_mandatory_raises():
    """Renaming mandatory feature raises FlowValidationException."""
    input_features = {
        "mandatory_field": {
            "type": "string",
            OperatorConstants.Misc.TAGS: [OperatorConstants.Misc.MANDATORY],
        },
    }
    updated_features = [
        {
            OperatorConstants.Misc.OLD_FEATURE: "mandatory_field",
            OperatorConstants.Misc.NEW_FEATURE: "new_name",
        }
    ]

    with pytest.raises(FlowValidationException):
        rename_features_and_save_original(
            updated_features=updated_features, input_features=input_features
        )


def test_rename_features_dict_preserves_original():
    """Original feature name is preserved in metadata."""
    input_features = {
        "field1": {"type": "string"},
    }
    updated_features = [
        {
            OperatorConstants.Misc.OLD_FEATURE: "field1",
            OperatorConstants.Misc.NEW_FEATURE: "field2",
        }
    ]

    rename_features_and_save_original(
        updated_features=updated_features, input_features=input_features
    )

    # Rename again
    updated_features2 = [
        {
            OperatorConstants.Misc.OLD_FEATURE: "field2",
            OperatorConstants.Misc.NEW_FEATURE: "field3",
        }
    ]
    rename_features_and_save_original(
        updated_features=updated_features2, input_features=input_features
    )

    # Original should still be field1
    assert input_features["field3"][OperatorConstants.Misc.ORIGINAL_FEATURE] == "field1"


def test_rename_features_none_inputs():
    """None inputs return None."""
    result = rename_features_and_save_original(
        updated_features=None, input_features=None
    )

    assert result is None


def test_rename_features_empty_updated_features():
    """Empty updated_features returns None."""
    input_features = {"field": {"type": "string"}}
    result = rename_features_and_save_original(
        updated_features=[], input_features=input_features
    )

    assert result is None


# ---------------------------------------------------------------------------
# 16. Edge cases and error handling
# ---------------------------------------------------------------------------


def test_rename_features_invalid_mapping_format():
    """Invalid mapping format raises ValueError."""
    table = pa.table({"a": [1]})
    updated_features = [
        "not_a_dict"  # Should be dict
    ]

    with pytest.raises(ValueError, match="must be a dict"):
        rename_features_and_save_original(
            updated_features=updated_features, input_features=table
        )


def test_rename_features_missing_keys():
    """Missing old_feature or new_feature raises ValueError."""
    table = pa.table({"a": [1]})
    updated_features = [
        {"old_feature": "a"}  # Missing new_feature
    ]

    with pytest.raises(ValueError, match="must contain"):
        rename_features_and_save_original(
            updated_features=updated_features, input_features=table
        )


def test_rename_features_duplicate_old_feature():
    """Duplicate old_feature in mappings raises ValueError."""
    table = pa.table({"a": [1], "b": [2]})
    updated_features = [
        {
            OperatorConstants.Misc.OLD_FEATURE: "a",
            OperatorConstants.Misc.NEW_FEATURE: "x",
        },
        {
            OperatorConstants.Misc.OLD_FEATURE: "a",
            OperatorConstants.Misc.NEW_FEATURE: "y",
        },
    ]

    with pytest.raises(ValueError, match="Duplicate mapping"):
        rename_features_and_save_original(
            updated_features=updated_features, input_features=table
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

# Made with Bob
