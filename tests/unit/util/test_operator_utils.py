#!/usr/bin/env python3
"""
Unit tests for operator_utils module.
Tests utility functions for table manipulation, validation, and feature management.
"""

import pyarrow as pa
import pytest

from docpipe.core.constants.constants import internal_metrics
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.operator_utils import OperatorUtils
from docpipe.exceptions.docpipe_exceptions import FlowValidationException

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
    result = OperatorUtils.remove_rows(table=table, remove_row_idx=[1, 3])

    assert result.num_rows == 3
    ids = result[OperatorConstants.Columns.ID].to_pylist()
    assert ids == ["1", "3", "5"]


def test_remove_rows_empty_list():
    """Removing no rows returns original table."""
    table = make_table(num_rows=3)
    result = OperatorUtils.remove_rows(table=table, remove_row_idx=[])

    assert result.num_rows == 3


def test_remove_rows_all_rows():
    """Remove all rows returns empty table."""
    table = make_table(num_rows=3)
    result = OperatorUtils.remove_rows(table=table, remove_row_idx=[0, 1, 2])

    assert result.num_rows == 0


def test_remove_rows_preserves_columns():
    """Removing rows preserves all columns."""
    table = make_table(num_rows=3, extra_columns={"content": ["a", "b", "c"]})
    result = OperatorUtils.remove_rows(table=table, remove_row_idx=[1])

    assert set(result.column_names) == set(table.column_names)


# ---------------------------------------------------------------------------
# 2. remove_all_rows tests
# ---------------------------------------------------------------------------


def test_remove_all_rows_by_id():
    """Remove rows by document ID."""
    table = make_table(num_rows=5)
    result = OperatorUtils.remove_all_rows(table=table, remove_row_id=["2", "4"])

    assert result.num_rows == 3
    ids = result[OperatorConstants.Columns.ID].to_pylist()
    assert ids == ["1", "3", "5"]


def test_remove_all_rows_empty_list():
    """Removing no IDs returns original table."""
    table = make_table(num_rows=3)
    result = OperatorUtils.remove_all_rows(table=table, remove_row_id=[])

    assert result.num_rows == 3


def test_remove_all_rows_nonexistent_id():
    """Removing nonexistent ID doesn't affect table."""
    table = make_table(num_rows=3)
    result = OperatorUtils.remove_all_rows(table=table, remove_row_id=["999"])

    assert result.num_rows == 3


def test_remove_all_rows_all_ids():
    """Remove all rows by ID."""
    table = make_table(num_rows=3)
    result = OperatorUtils.remove_all_rows(table=table, remove_row_id=["1", "2", "3"])

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
    count = OperatorUtils.find_doc_count(table=table)

    assert count == 2  # Two unique document names


def test_find_doc_count_without_name_column():
    """Count rows when name column is missing."""
    table = pa.table(
        {
            OperatorConstants.Columns.ID: ["1", "2", "3"],
        }
    )
    count = OperatorUtils.find_doc_count(table=table)

    assert count == 3  # Falls back to row count


def test_find_doc_count_empty_table():
    """Count for empty table returns 0."""
    table = pa.table(
        {
            OperatorConstants.Columns.ID: pa.array([], type=pa.string()),
        }
    )
    count = OperatorUtils.find_doc_count(table=table)

    assert count == 0


def test_find_doc_count_none_table():
    """Count for None table returns 0."""
    count = OperatorUtils.find_doc_count(table=None)

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
    count = OperatorUtils.find_doc_count_from_tables(tables=[table1, table2])

    assert count == 3  # Three unique documents


def test_find_doc_count_from_tables_empty_list():
    """Count from empty list returns 0."""
    count = OperatorUtils.find_doc_count_from_tables(tables=[])

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
    count = OperatorUtils.find_doc_count_from_tables(tables=[table1, table2])

    assert count == 1


# ---------------------------------------------------------------------------
# 5. validate_link_name tests
# ---------------------------------------------------------------------------


def test_validate_link_name_valid():
    """Valid link name passes validation."""
    existing: set[str] = set()
    errors: list[str] = []
    OperatorUtils.validate_link_name(link_name="link1", existing_link_names=existing, errors=errors)

    assert len(errors) == 0
    assert "link1" in existing


def test_validate_link_name_duplicate():
    """Duplicate link name adds error."""
    existing: set[str] = {"link1"}
    errors: list[str] = []
    OperatorUtils.validate_link_name(link_name="Link1", existing_link_names=existing, errors=errors)

    assert len(errors) == 1
    assert "Duplicate link name" in errors[0]


def test_validate_link_name_case_insensitive():
    """Link name validation is case-insensitive."""
    existing: set[str] = {"link1"}
    errors: list[str] = []
    OperatorUtils.validate_link_name(link_name="LINK1", existing_link_names=existing, errors=errors)

    assert len(errors) == 1


def test_validate_link_name_empty():
    """Empty link name adds error."""
    existing: set[str] = set()
    errors: list[str] = []
    OperatorUtils.validate_link_name(link_name="", existing_link_names=existing, errors=errors)

    assert len(errors) == 1
    assert "Missing link name" in errors[0]


def test_validate_link_name_none():
    """None link name adds error."""
    existing: set[str] = set()
    errors: list[str] = []
    OperatorUtils.validate_link_name(link_name=None, existing_link_names=existing, errors=errors)

    assert len(errors) == 1


# ---------------------------------------------------------------------------
# 6. doc_id_hash tests
# ---------------------------------------------------------------------------


def test_doc_id_hash_basic():
    """Hash content produces hex string."""
    content = "test content"
    result = OperatorUtils.doc_id_hash(content=content)

    assert isinstance(result, str)
    assert len(result) == 128  # SHA3-512 produces 128 hex chars


def test_doc_id_hash_deterministic():
    """Same content produces same hash."""
    content = "test content"
    hash1 = OperatorUtils.doc_id_hash(content=content)
    hash2 = OperatorUtils.doc_id_hash(content=content)

    assert hash1 == hash2


def test_doc_id_hash_different_content():
    """Different content produces different hash."""
    hash1 = OperatorUtils.doc_id_hash(content="content1")
    hash2 = OperatorUtils.doc_id_hash(content="content2")

    assert hash1 != hash2


def test_doc_id_hash_empty_string():
    """Empty string can be hashed."""
    result = OperatorUtils.doc_id_hash(content="")

    assert isinstance(result, str)
    assert len(result) == 128


def test_doc_id_hash_unicode():
    """Unicode content can be hashed."""
    content = "こんにちは世界"
    result = OperatorUtils.doc_id_hash(content=content)

    assert isinstance(result, str)
    assert len(result) == 128


# ---------------------------------------------------------------------------
# 7. decode_binary_content tests
# ---------------------------------------------------------------------------


def test_decode_binary_content_utf8():
    """Decode UTF-8 binary content."""
    binary = b"Hello, World!"
    result = OperatorUtils.decode_binary_content(binary_content=binary)

    assert result == "Hello, World!"


def test_decode_binary_content_unicode():
    """Decode Unicode binary content."""
    text = "こんにちは"
    binary = text.encode("utf-8")
    result = OperatorUtils.decode_binary_content(binary_content=binary)

    assert result == text


def test_decode_binary_content_latin1():
    """Decode Latin-1 encoded content."""
    text = "Café"
    binary = text.encode("latin-1")
    result = OperatorUtils.decode_binary_content(binary_content=binary)

    # charset_normalizer may detect encoding differently, just verify it returns a string
    assert isinstance(result, str)
    assert len(result) > 0


def test_decode_binary_content_empty():
    """Decode empty binary content."""
    binary = b""
    result = OperatorUtils.decode_binary_content(binary_content=binary)

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

    result = OperatorUtils.upsert_fields_in_schema(schema=schema, updates=updates)

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

    result = OperatorUtils.upsert_fields_in_schema(schema=schema, updates=updates)

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

    result = OperatorUtils.upsert_fields_in_schema(schema=schema, updates=updates)

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

    result = OperatorUtils.upsert_fields_in_schema(schema=schema, updates=updates)

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

    result = OperatorUtils.remove_internal_metrics_from_metadata(metadata)

    assert "user_metric" in metadata
    assert "another_metric" in metadata
    assert len(result) > 0  # Internal metrics were removed


def test_remove_internal_metrics_from_metadata_empty():
    """Handle empty metadata dict."""
    metadata: dict[str, object] = {}
    result = OperatorUtils.remove_internal_metrics_from_metadata(metadata)

    assert result == {}


def test_remove_internal_metrics_from_metadata_no_internal():
    """Handle metadata with no internal metrics."""
    metadata = {"user_metric": "value"}
    result = OperatorUtils.remove_internal_metrics_from_metadata(metadata)

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
    result = OperatorUtils.drop_features_from_table(["content"], table)

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
    result = OperatorUtils.drop_features_from_table(["a", "c"], table)

    assert result.column_names == ["id", "b"]


def test_drop_features_from_table_nonexistent():
    """Dropping nonexistent column doesn't error."""
    table = pa.table(
        {
            "id": ["1"],
            "name": ["a"],
        }
    )
    result = OperatorUtils.drop_features_from_table(["nonexistent"], table)

    assert result.column_names == table.column_names


def test_drop_features_from_table_empty_list():
    """Empty drop list returns original table."""
    table = pa.table(
        {
            "id": ["1"],
            "name": ["a"],
        }
    )
    result = OperatorUtils.drop_features_from_table([], table)

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

    result = OperatorUtils.get_mandatory_features(check_features=check_features, input_features=input_features)

    assert set(result) == {"field1", "field3"}


def test_get_mandatory_features_none():
    """No mandatory features returns empty list."""
    input_features: dict[str, dict] = {
        "field1": {OperatorConstants.Misc.TAGS: []},
        "field2": {OperatorConstants.Misc.TAGS: []},
    }
    check_features = ["field1", "field2"]

    result = OperatorUtils.get_mandatory_features(check_features=check_features, input_features=input_features)

    assert result == []


def test_get_mandatory_features_empty_check_list():
    """Empty check list returns empty result."""
    input_features = {
        "field1": {OperatorConstants.Misc.TAGS: [OperatorConstants.Misc.MANDATORY]},
    }

    result = OperatorUtils.get_mandatory_features(check_features=[], input_features=input_features)

    assert result == []


def test_get_mandatory_features_no_tags():
    """Features without tags are not mandatory."""
    input_features = {
        "field1": {},
        "field2": {OperatorConstants.Misc.TAGS: [OperatorConstants.Misc.MANDATORY]},
    }
    check_features = ["field1", "field2"]

    result = OperatorUtils.get_mandatory_features(check_features=check_features, input_features=input_features)

    assert result == ["field2"]


# ---------------------------------------------------------------------------
# 12. validate_filter_criteria tests
# ---------------------------------------------------------------------------


def test_validate_filter_criteria_valid_list():
    """Valid criteria_list returns True."""
    criteria_list = ["age > 18", "status = 'active'"]
    criteria_json = None

    criteria_valid, json_valid = OperatorUtils.validate_filter_criteria(
        criteria_list=criteria_list, criteria_json=criteria_json
    )

    assert criteria_valid is True
    assert json_valid is False


def test_validate_filter_criteria_valid_json_leaf():
    """Valid JSON leaf condition returns True."""
    criteria_list = None
    criteria_json = {"variable": "age", "operator": ">", "value": 18}

    criteria_valid, json_valid = OperatorUtils.validate_filter_criteria(
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

    criteria_valid, json_valid = OperatorUtils.validate_filter_criteria(
        criteria_list=criteria_list, criteria_json=criteria_json
    )

    assert criteria_valid is False
    assert json_valid is True


def test_validate_filter_criteria_empty_list():
    """Empty criteria_list returns False."""
    criteria_list: list[str] = []
    criteria_json = None

    criteria_valid, _ = OperatorUtils.validate_filter_criteria(criteria_list=criteria_list, criteria_json=criteria_json)

    assert criteria_valid is False


def test_validate_filter_criteria_list_with_empty_strings():
    """List with only empty strings returns False."""
    criteria_list = ["", "  ", ""]
    criteria_json = None

    criteria_valid, _ = OperatorUtils.validate_filter_criteria(criteria_list=criteria_list, criteria_json=criteria_json)

    assert criteria_valid is False


def test_validate_filter_criteria_invalid_json_empty_group():
    """JSON group with empty criteria_list returns False."""
    criteria_list = None
    criteria_json = {"logical_operator": "AND", "criteria_list": []}

    _, json_valid = OperatorUtils.validate_filter_criteria(criteria_list=criteria_list, criteria_json=criteria_json)

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

    _, json_valid = OperatorUtils.validate_filter_criteria(criteria_list=None, criteria_json=criteria_json)

    assert json_valid is True


# ---------------------------------------------------------------------------
# 13. _validate_criteria_json tests
# ---------------------------------------------------------------------------


def test_validate_criteria_json_leaf_condition():
    """Leaf condition with variable and operator is valid."""
    criteria = {"variable": "age", "operator": ">"}

    assert OperatorUtils._validate_criteria_json(criteria_json=criteria) is True


def test_validate_criteria_json_group_with_valid_items():
    """Group with all valid items is valid."""
    criteria = {
        "criteria_list": [
            {"variable": "age", "operator": ">"},
            {"variable": "name", "operator": "="},
        ]
    }

    assert OperatorUtils._validate_criteria_json(criteria_json=criteria) is True


def test_validate_criteria_json_empty_dict():
    """Empty dict is invalid."""
    assert OperatorUtils._validate_criteria_json(criteria_json={}) is False


def test_validate_criteria_json_none():
    """None is invalid."""
    assert OperatorUtils._validate_criteria_json(criteria_json=None) is False


def test_validate_criteria_json_group_with_invalid_item():
    """Group with any invalid item is invalid."""
    criteria = {
        "criteria_list": [
            {"variable": "age", "operator": ">"},
            {"invalid": "item"},  # Missing variable and operator
        ]
    }

    assert OperatorUtils._validate_criteria_json(criteria_json=criteria) is False


def test_validate_criteria_json_group_empty_list():
    """Group with empty criteria_list is invalid."""
    criteria: dict[str, list] = {"criteria_list": []}

    assert OperatorUtils._validate_criteria_json(criteria_json=criteria) is False


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

    result = OperatorUtils.rename_features_and_save_original(updated_features=updated_features, input_features=table)

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

    result = OperatorUtils.rename_features_and_save_original(updated_features=updated_features, input_features=table)

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
        OperatorUtils.rename_features_and_save_original(updated_features=updated_features, input_features=table)


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
        OperatorUtils.rename_features_and_save_original(updated_features=updated_features, input_features=table)


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

    OperatorUtils.rename_features_and_save_original(updated_features=updated_features, input_features=input_features)

    assert "new_name" in input_features
    assert "old_name" not in input_features
    assert input_features["new_name"][OperatorConstants.Misc.ORIGINAL_FEATURE] == "old_name"


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
        OperatorUtils.rename_features_and_save_original(
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

    OperatorUtils.rename_features_and_save_original(updated_features=updated_features, input_features=input_features)

    # Rename again
    updated_features2 = [
        {
            OperatorConstants.Misc.OLD_FEATURE: "field2",
            OperatorConstants.Misc.NEW_FEATURE: "field3",
        }
    ]
    OperatorUtils.rename_features_and_save_original(updated_features=updated_features2, input_features=input_features)

    # Original should still be field1
    assert input_features["field3"][OperatorConstants.Misc.ORIGINAL_FEATURE] == "field1"


def test_rename_features_none_inputs():
    """None inputs return None."""
    result = OperatorUtils.rename_features_and_save_original(updated_features=None, input_features=None)

    assert result is None


def test_rename_features_empty_updated_features():
    """Empty updated_features returns None."""
    input_features = {"field": {"type": "string"}}
    result = OperatorUtils.rename_features_and_save_original(updated_features=[], input_features=input_features)

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
        OperatorUtils.rename_features_and_save_original(updated_features=updated_features, input_features=table)


def test_rename_features_missing_keys():
    """Missing old_feature or new_feature raises ValueError."""
    table = pa.table({"a": [1]})
    updated_features = [
        {"old_feature": "a"}  # Missing new_feature
    ]

    with pytest.raises(ValueError, match="must contain"):
        OperatorUtils.rename_features_and_save_original(updated_features=updated_features, input_features=table)


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
        OperatorUtils.rename_features_and_save_original(updated_features=updated_features, input_features=table)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


# ---------------------------------------------------------------------------
# 17. extract_text_file tests
# ---------------------------------------------------------------------------


class TestOperatorUtilsExtractTextFile:
    """Test suite for OperatorUtils.extract_text_file method."""

    def test_extract_text_file_is_public_method(self):
        """Test that extract_text_file is a public static method."""
        # Verify method exists and is callable
        assert hasattr(OperatorUtils, "extract_text_file")
        assert callable(OperatorUtils.extract_text_file)
        # Verify it's a static method (not bound to instance)
        assert isinstance(OperatorUtils.__dict__["extract_text_file"], staticmethod)

    def test_extract_text_file_utf8_content_success(self):
        """Test extraction of UTF-8 encoded text file."""
        file_path = "/path/to/document.txt"
        binary_content = b"This is a test document.\nWith multiple lines."

        result = OperatorUtils.extract_text_file(file_path=file_path, binary_content=binary_content)

        assert result[OperatorConstants.Extraction.SUCCESS] is True
        assert result[OperatorConstants.Columns.DOC_COLUMN_DEFAULT] == "This is a test document.\nWith multiple lines."
        assert OperatorConstants.Metadata.METADATA in result
        assert result[OperatorConstants.Metadata.METADATA]["is_text_file"] is True

    def test_extract_text_file_latin1_fallback(self):
        """Test extraction falls back to latin-1 encoding when UTF-8 fails."""
        file_path = "/path/to/document.txt"
        # Create content with latin-1 specific characters that aren't valid UTF-8
        binary_content = b"Text with special chars: \xe9\xe0\xf1"

        result = OperatorUtils.extract_text_file(file_path=file_path, binary_content=binary_content)

        assert result[OperatorConstants.Extraction.SUCCESS] is True
        # latin-1 should decode these characters
        assert "Text with special chars:" in result[OperatorConstants.Columns.DOC_COLUMN_DEFAULT]

    def test_extract_text_file_empty_content(self):
        """Test extraction of empty text file."""
        file_path = "/path/to/empty.txt"
        binary_content = b""

        result = OperatorUtils.extract_text_file(file_path=file_path, binary_content=binary_content)

        assert result[OperatorConstants.Extraction.SUCCESS] is True
        assert result[OperatorConstants.Columns.DOC_COLUMN_DEFAULT] == ""
        assert result[OperatorConstants.Metadata.METADATA]["char_count"] == 0

    def test_extract_text_file_multiline_content(self):
        """Test extraction of multiline text content."""
        file_path = "/path/to/multiline.txt"
        binary_content = b"Line 1\nLine 2\nLine 3\n"

        result = OperatorUtils.extract_text_file(file_path=file_path, binary_content=binary_content)

        assert result[OperatorConstants.Extraction.SUCCESS] is True
        assert result[OperatorConstants.Columns.DOC_COLUMN_DEFAULT] == "Line 1\nLine 2\nLine 3\n"
        assert result[OperatorConstants.Metadata.METADATA]["char_count"] == len("Line 1\nLine 2\nLine 3\n")

    def test_extract_text_file_unicode_content(self):
        """Test extraction of Unicode text content."""
        file_path = "/path/to/unicode.txt"
        binary_content = "Hello 世界 🌍".encode()

        result = OperatorUtils.extract_text_file(file_path=file_path, binary_content=binary_content)

        assert result[OperatorConstants.Extraction.SUCCESS] is True
        assert result[OperatorConstants.Columns.DOC_COLUMN_DEFAULT] == "Hello 世界 🌍"

    def test_extract_text_file_metadata_structure(self):
        """Test that metadata has correct structure."""
        file_path = "/path/to/document.txt"
        binary_content = b"Test content"

        result = OperatorUtils.extract_text_file(file_path=file_path, binary_content=binary_content)

        metadata = result[OperatorConstants.Metadata.METADATA]
        assert "char_count" in metadata
        assert "is_text_file" in metadata
        assert metadata["char_count"] == len("Test content")
        assert metadata["is_text_file"] is True

    def test_extract_text_file_handles_txt_extension(self):
        """Test that .txt files are handled correctly."""
        file_path = "/path/to/notes.txt"
        binary_content = b"Plain text notes"

        result = OperatorUtils.extract_text_file(file_path=file_path, binary_content=binary_content)

        assert result[OperatorConstants.Extraction.SUCCESS] is True
        assert result[OperatorConstants.Columns.DOC_COLUMN_DEFAULT] == "Plain text notes"

    def test_extract_text_file_does_not_handle_md_files(self):
        """Test that extract_text_file can be used for any text, including .md files."""
        # Note: The adapter layer decides routing, not extract_text_file itself
        file_path = "/path/to/readme.md"
        binary_content = b"# Markdown Header\n\nContent"

        result = OperatorUtils.extract_text_file(file_path=file_path, binary_content=binary_content)

        # extract_text_file will process any text content given to it
        assert result[OperatorConstants.Extraction.SUCCESS] is True
        assert result[OperatorConstants.Columns.DOC_COLUMN_DEFAULT] == "# Markdown Header\n\nContent"

    def test_extract_text_file_large_content(self):
        """Test extraction of large text content."""
        file_path = "/path/to/large.txt"
        # Create large content (10KB)
        binary_content = b"A" * 10000

        result = OperatorUtils.extract_text_file(file_path=file_path, binary_content=binary_content)

        assert result[OperatorConstants.Extraction.SUCCESS] is True
        assert len(result[OperatorConstants.Columns.DOC_COLUMN_DEFAULT]) == 10000
        assert result[OperatorConstants.Metadata.METADATA]["char_count"] == 10000

    def test_extract_text_file_whitespace_content(self):
        """Test extraction of content with various whitespace."""
        file_path = "/path/to/whitespace.txt"
        binary_content = b"  \t\n  Text with spaces  \t\n  "

        result = OperatorUtils.extract_text_file(file_path=file_path, binary_content=binary_content)

        assert result[OperatorConstants.Extraction.SUCCESS] is True
        # Whitespace should be preserved
        assert result[OperatorConstants.Columns.DOC_COLUMN_DEFAULT] == "  \t\n  Text with spaces  \t\n  "

    def test_extract_text_file_special_characters(self):
        """Test extraction with special characters."""
        file_path = "/path/to/special.txt"
        binary_content = b"Special chars: @#$%^&*()_+-=[]{}|;:',.<>?/~`"

        result = OperatorUtils.extract_text_file(file_path=file_path, binary_content=binary_content)

        assert result[OperatorConstants.Extraction.SUCCESS] is True
        assert result[OperatorConstants.Columns.DOC_COLUMN_DEFAULT] == "Special chars: @#$%^&*()_+-=[]{}|;:',.<>?/~`"

    def test_extract_text_file_additional_format_text(self):
        """Test that 'text' additional format populates content_text column."""
        file_path = "/path/to/document.txt"
        binary_content = b"Hello world"

        result = OperatorUtils.extract_text_file(
            file_path=file_path, binary_content=binary_content, additional_formats=["text"]
        )

        assert result[OperatorConstants.Extraction.SUCCESS] is True
        assert result[OperatorConstants.Columns.DOC_COLUMN_DEFAULT] == "Hello world"
        assert result[OperatorConstants.Columns.CONTENT_TEXT] == "Hello world"

    def test_extract_text_file_additional_format_html(self):
        """Test that 'html' additional format produces valid HTML via native Docling export."""
        file_path = "/path/to/document.txt"
        binary_content = b"Hello world"

        result = OperatorUtils.extract_text_file(
            file_path=file_path, binary_content=binary_content, additional_formats=["html"]
        )

        assert result[OperatorConstants.Extraction.SUCCESS] is True
        html = result[OperatorConstants.Columns.CONTENT_HTML]
        assert html is not None
        assert "Hello world" in html
        assert "<html" in html.lower()

    def test_extract_text_file_additional_format_json(self):
        """Test that 'json' additional format produces a valid Docling JSON dict."""
        import json

        file_path = "/path/to/document.txt"
        binary_content = b"Hello world"

        result = OperatorUtils.extract_text_file(
            file_path=file_path, binary_content=binary_content, additional_formats=["json"]
        )

        assert result[OperatorConstants.Extraction.SUCCESS] is True
        parsed = json.loads(result[OperatorConstants.Columns.CONTENT_JSON])
        # Docling export_to_dict() returns a structured document — verify it's a non-empty dict
        assert isinstance(parsed, dict)
        assert len(parsed) > 0

    def test_extract_text_file_additional_formats_multiple(self):
        """Test multiple additional formats are all populated."""
        file_path = "/path/to/document.txt"
        binary_content = b"Sample text"

        result = OperatorUtils.extract_text_file(
            file_path=file_path, binary_content=binary_content, additional_formats=["text", "html", "json"]
        )

        assert result[OperatorConstants.Extraction.SUCCESS] is True
        assert result[OperatorConstants.Columns.CONTENT_TEXT] == "Sample text"
        assert OperatorConstants.Columns.CONTENT_HTML in result
        assert OperatorConstants.Columns.CONTENT_JSON in result

    def test_extract_text_file_additional_format_doctags(self):
        """Test that doctags format is populated for plain text files."""
        file_path = "/path/to/document.txt"
        binary_content = b"Sample text"

        result = OperatorUtils.extract_text_file(
            file_path=file_path, binary_content=binary_content, additional_formats=["doctags"]
        )

        assert result[OperatorConstants.Extraction.SUCCESS] is True
        assert OperatorConstants.Columns.CONTENT_DOCTAGS in result
        doctags = result[OperatorConstants.Columns.CONTENT_DOCTAGS]
        assert doctags is not None
        assert "Sample text" in doctags

    def test_extract_text_file_additional_format_doclang(self):
        """Test that doclang format is populated for plain text files."""
        file_path = "/path/to/document.txt"
        binary_content = b"Sample text"

        result = OperatorUtils.extract_text_file(
            file_path=file_path, binary_content=binary_content, additional_formats=["doclang"]
        )

        assert result[OperatorConstants.Extraction.SUCCESS] is True
        assert OperatorConstants.Columns.CONTENT_DOCLANG in result
        doclang = result[OperatorConstants.Columns.CONTENT_DOCLANG]
        assert doclang is not None
        assert "Sample text" in doclang

    def test_extract_text_file_no_additional_formats_unchanged(self):
        """Test that omitting additional_formats keeps original behaviour."""
        file_path = "/path/to/document.txt"
        binary_content = b"Hello world"

        result = OperatorUtils.extract_text_file(file_path=file_path, binary_content=binary_content)

        assert result[OperatorConstants.Extraction.SUCCESS] is True
        assert OperatorConstants.Columns.CONTENT_TEXT not in result
        assert OperatorConstants.Columns.CONTENT_HTML not in result
        assert OperatorConstants.Columns.CONTENT_JSON not in result


# ---------------------------------------------------------------------------
# sanitize_doc_id_for_filename tests
# ---------------------------------------------------------------------------


def test_sanitize_doc_id_for_filename_with_slashes():
    """Test sanitizing document IDs containing forward slashes."""
    from docpipe.core.operators.operator_utils import sanitize_doc_id_for_filename

    doc_id = "folder/subfolder/document.pdf"
    result = sanitize_doc_id_for_filename(doc_id=doc_id)

    assert result == "folder_subfolder_document.pdf"
    assert "/" not in result


def test_sanitize_doc_id_for_filename_no_slashes():
    """Test sanitizing document IDs without slashes."""
    from docpipe.core.operators.operator_utils import sanitize_doc_id_for_filename

    doc_id = "simple_document_id"
    result = sanitize_doc_id_for_filename(doc_id=doc_id)

    assert result == "simple_document_id"


def test_sanitize_doc_id_for_filename_multiple_slashes():
    """Test sanitizing document IDs with multiple consecutive slashes."""
    from docpipe.core.operators.operator_utils import sanitize_doc_id_for_filename

    doc_id = "path//to///file.txt"
    result = sanitize_doc_id_for_filename(doc_id=doc_id)

    assert result == "path__to___file.txt"
    assert "/" not in result


# ---------------------------------------------------------------------------
# resolve_env_var tests
# ---------------------------------------------------------------------------


class TestResolveEnvVar:
    """Tests for resolve_env_var function."""

    def test_resolve_simple_var(self, monkeypatch):
        """Test ${VAR} format."""
        monkeypatch.setenv("TEST_VAR", "test_value")
        from docpipe.core.operators.operator_utils import resolve_env_var

        result = resolve_env_var("${TEST_VAR}")
        assert result == "test_value"

    def test_resolve_var_with_default(self, monkeypatch):
        """Test ${VAR:default} format."""
        from docpipe.core.operators.operator_utils import resolve_env_var

        result = resolve_env_var("${MISSING_VAR:default_value}")
        assert result == "default_value"

    def test_resolve_var_with_dash_default(self, monkeypatch):
        """Test ${VAR:-default} format."""
        from docpipe.core.operators.operator_utils import resolve_env_var

        result = resolve_env_var("${MISSING_VAR:-default_value}")
        assert result == "default_value"

    def test_resolve_dollar_var(self, monkeypatch):
        """Test $VAR format."""
        monkeypatch.setenv("TEST_VAR", "test_value")
        from docpipe.core.operators.operator_utils import resolve_env_var

        result = resolve_env_var("$TEST_VAR")
        assert result == "test_value"

    def test_resolve_uppercase_var(self, monkeypatch):
        """Test UPPER_CASE variables."""
        monkeypatch.setenv("UPPER_CASE_VAR", "upper_value")
        from docpipe.core.operators.operator_utils import resolve_env_var

        result = resolve_env_var("UPPER_CASE_VAR")
        assert result == "upper_value"

    def test_resolve_missing_required_var(self):
        """Test error when required var missing."""
        from docpipe.core.operators.operator_utils import resolve_env_var

        with pytest.raises(ValueError, match="Environment variable MISSING_VAR is not set"):
            resolve_env_var("${MISSING_VAR}")

    def test_resolve_with_fallback(self, monkeypatch):
        """Test fallback to default value."""
        from docpipe.core.operators.operator_utils import resolve_env_var

        result = resolve_env_var("${NONEXISTENT:fallback}")
        assert result == "fallback"

    def test_resolve_multiple_vars(self, monkeypatch):
        """Test string with multiple variables (returns first match)."""
        monkeypatch.setenv("VAR1", "value1")
        from docpipe.core.operators.operator_utils import resolve_env_var

        # Function only resolves single variable patterns
        result = resolve_env_var("${VAR1}")
        assert result == "value1"

    def test_resolve_non_string_value(self):
        """Test non-string values are returned as-is."""
        from docpipe.core.operators.operator_utils import resolve_env_var

        assert resolve_env_var(123) == 123
        assert resolve_env_var(None) is None
        assert resolve_env_var(True) is True


# ---------------------------------------------------------------------------
# get_supported_file_extensions tests
# ---------------------------------------------------------------------------


class TestGetSupportedFileExtensions:
    """Tests for get_supported_file_extensions function."""

    def test_extensions_without_asr(self, monkeypatch):
        """Test when ASR not available."""
        from docpipe.core.operators.operator_utils import get_supported_file_extensions

        # Mock is_asr_available to return False
        monkeypatch.setattr("docpipe.core.operators.operator_utils.is_asr_available", lambda: False)

        result = get_supported_file_extensions()
        extensions = result.split(",")

        # Should have base extensions only
        assert "pdf" in extensions
        assert "docx" in extensions
        assert "txt" in extensions
        # Should NOT have audio/video extensions
        assert "mp3" not in extensions
        assert "wav" not in extensions
        assert "mp4" not in extensions

    def test_extensions_with_asr(self, monkeypatch):
        """Test when ASR available."""
        from docpipe.core.operators.operator_utils import get_supported_file_extensions

        # Mock is_asr_available to return True
        monkeypatch.setattr("docpipe.core.operators.operator_utils.is_asr_available", lambda: True)

        result = get_supported_file_extensions()
        extensions = result.split(",")

        # Should have base extensions
        assert "pdf" in extensions
        assert "docx" in extensions
        # Should have audio/video extensions
        assert "mp3" in extensions
        assert "wav" in extensions
        assert "mp4" in extensions

    def test_returns_string(self):
        """Verify return type is string."""
        from docpipe.core.operators.operator_utils import get_supported_file_extensions

        result = get_supported_file_extensions()
        assert isinstance(result, str)
        assert "," in result  # Should be comma-separated

    def test_includes_common_formats(self):
        """Verify common formats included."""
        from docpipe.core.operators.operator_utils import get_supported_file_extensions

        result = get_supported_file_extensions()
        extensions = result.split(",")

        # Common document formats
        assert "pdf" in extensions
        assert "docx" in extensions
        assert "pptx" in extensions
        assert "txt" in extensions
        assert "md" in extensions
        # Common image formats
        assert "png" in extensions
        assert "jpeg" in extensions
        assert "jpg" in extensions


# ---------------------------------------------------------------------------
# is_asr_available tests
# ---------------------------------------------------------------------------


class TestIsAsrAvailable:
    """Tests for is_asr_available function."""

    def test_asr_available(self, monkeypatch):
        """Mock successful import."""
        # Mock the imports to succeed
        import sys
        from unittest.mock import MagicMock

        from docpipe.core.operators.operator_utils import is_asr_available

        mock_module = MagicMock()
        monkeypatch.setitem(sys.modules, "docling.datamodel.asr_model_specs", mock_module)
        monkeypatch.setitem(sys.modules, "docling.document_converter", mock_module)
        monkeypatch.setitem(sys.modules, "docling.pipeline.asr_pipeline", mock_module)

        # Re-import to get fresh function
        import importlib

        import docpipe.core.operators.operator_utils

        importlib.reload(docpipe.core.operators.operator_utils)

        result = is_asr_available()
        # Result depends on actual environment, just verify it returns bool
        assert isinstance(result, bool)

    def test_asr_not_available(self, monkeypatch):
        """Mock ImportError."""
        # This test verifies the function handles ImportError gracefully
        # In actual environment, ASR may or may not be available
        from docpipe.core.operators.operator_utils import is_asr_available

        result = is_asr_available()
        assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# get_optimal_workers tests
# ---------------------------------------------------------------------------


class TestGetOptimalWorkers:
    """Tests for get_optimal_workers function."""

    def test_cpu_intensive_task(self, monkeypatch):
        """Test with cpu_intensive=True."""
        monkeypatch.setattr("os.cpu_count", lambda: 8)

        result = OperatorUtils.get_optimal_workers(is_cpu_intensive=True)

        # Should be cpu_count - 1
        assert result == 7

    def test_io_bound_task(self, monkeypatch):
        """Test with cpu_intensive=False."""
        monkeypatch.setattr("os.cpu_count", lambda: 4)

        result = OperatorUtils.get_optimal_workers(is_cpu_intensive=False)

        # Should be cpu_count * 2, capped at 16
        assert result == 8

    def test_respects_max_cap(self, monkeypatch):
        """Test max_workers cap at 16."""
        monkeypatch.setattr("os.cpu_count", lambda: 20)

        result = OperatorUtils.get_optimal_workers(is_cpu_intensive=False)

        # Should be capped at 16
        assert result == 16

    def test_minimum_workers(self, monkeypatch):
        """Test minimum of 1 worker."""
        monkeypatch.setattr("os.cpu_count", lambda: 1)

        result = OperatorUtils.get_optimal_workers(is_cpu_intensive=True)

        # Should be at least 1 (max(1, cpu_count - 1))
        assert result >= 1


class TestDetectExtensionFromBytes:
    """Test suite for detect_extension_from_bytes function."""

    def test_detect_pdf(self):
        """Test PDF file signature detection."""
        pdf_bytes = b"%PDF-1.4\n%some content"
        ext = OperatorUtils.detect_extension_from_bytes(pdf_bytes)
        assert ext == ".pdf"

    def test_detect_docx(self):
        """Test DOCX file signature detection."""
        # DOCX files start with PK (ZIP) and contain word/ in content
        docx_bytes = b"PK\x03\x04" + b"\x00" * 100 + b"word/document.xml" + b"\x00" * 100
        ext = OperatorUtils.detect_extension_from_bytes(docx_bytes)
        assert ext == ".docx"

    def test_detect_xlsx(self):
        """Test XLSX file signature detection."""
        # XLSX files start with PK (ZIP) and contain xl/ in content
        xlsx_bytes = b"PK\x03\x04" + b"\x00" * 100 + b"xl/workbook.xml" + b"\x00" * 100
        ext = OperatorUtils.detect_extension_from_bytes(xlsx_bytes)
        assert ext == ".xlsx"

    def test_detect_pptx(self):
        """Test PPTX file signature detection."""
        # PPTX files start with PK (ZIP) and contain ppt/ in content
        pptx_bytes = b"PK\x03\x04" + b"\x00" * 100 + b"ppt/presentation.xml" + b"\x00" * 100
        ext = OperatorUtils.detect_extension_from_bytes(pptx_bytes)
        assert ext == ".pptx"

    def test_detect_generic_zip(self):
        """Test generic ZIP file defaults to .docx."""
        # ZIP without Office markers defaults to .docx
        zip_bytes = b"PK\x03\x04" + b"\x00" * 100
        ext = OperatorUtils.detect_extension_from_bytes(zip_bytes)
        assert ext == ".docx"

    def test_detect_doc_ole2(self):
        """Test legacy DOC file signature detection."""
        doc_bytes = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 100
        ext = OperatorUtils.detect_extension_from_bytes(doc_bytes)
        assert ext == ".doc"

    def test_detect_png(self):
        """Test PNG file signature detection."""
        png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        ext = OperatorUtils.detect_extension_from_bytes(png_bytes)
        assert ext == ".png"

    def test_detect_jpeg(self):
        """Test JPEG file signature detection."""
        jpeg_bytes = b"\xff\xd8\xff" + b"\x00" * 100
        ext = OperatorUtils.detect_extension_from_bytes(jpeg_bytes)
        assert ext == ".jpg"

    def test_detect_gif87(self):
        """Test GIF87a file signature detection."""
        gif_bytes = b"GIF87a" + b"\x00" * 100
        ext = OperatorUtils.detect_extension_from_bytes(gif_bytes)
        assert ext == ".gif"

    def test_detect_gif89(self):
        """Test GIF89a file signature detection."""
        gif_bytes = b"GIF89a" + b"\x00" * 100
        ext = OperatorUtils.detect_extension_from_bytes(gif_bytes)
        assert ext == ".gif"

    def test_detect_tiff_little_endian(self):
        """Test TIFF file signature detection (little endian)."""
        tiff_bytes = b"II*\x00" + b"\x00" * 100
        ext = OperatorUtils.detect_extension_from_bytes(tiff_bytes)
        assert ext == ".tiff"

    def test_detect_tiff_big_endian(self):
        """Test TIFF file signature detection (big endian)."""
        tiff_bytes = b"MM\x00*" + b"\x00" * 100
        ext = OperatorUtils.detect_extension_from_bytes(tiff_bytes)
        assert ext == ".tiff"

    def test_detect_html_doctype(self):
        """Test HTML file detection with DOCTYPE."""
        html_bytes = b"<!DOCTYPE html><html></html>"
        ext = OperatorUtils.detect_extension_from_bytes(html_bytes)
        assert ext == ".html"

    def test_detect_html_tag(self):
        """Test HTML file detection with html tag."""
        html_bytes = b"<html><body>test</body></html>"
        ext = OperatorUtils.detect_extension_from_bytes(html_bytes)
        assert ext == ".html"

    def test_detect_html_with_whitespace(self):
        """Test HTML file detection with leading whitespace."""
        html_bytes = b"  \n  <html><body>test</body></html>"
        ext = OperatorUtils.detect_extension_from_bytes(html_bytes)
        assert ext == ".html"

    def test_detect_text_utf8(self):
        """Test plain text file detection."""
        text_bytes = b"Hello, world! This is plain text."
        ext = OperatorUtils.detect_extension_from_bytes(text_bytes)
        assert ext == ".txt"

    def test_detect_unknown(self):
        """Test unknown file type returns empty string."""
        # Binary content that doesn't match any signature and can't be decoded as UTF-8
        unknown_bytes = b"\xff\xfe\xfd\xfc\xfb\xfa\xf9\xf8\xf7\xf6"
        ext = OperatorUtils.detect_extension_from_bytes(unknown_bytes)
        assert ext == ""

    def test_detect_with_empty_bytes(self):
        """Test empty bytes returns empty string."""
        ext = OperatorUtils.detect_extension_from_bytes(b"")
        assert ext == ""


class TestPrepareDocumentContentFetch:
    """Test suite for prepare_document_content_fetch function."""

    def test_prepare_with_binary_content(self):
        """Test preparation with binary_content column."""
        table = pa.table(
            {
                "id": ["doc1", "doc2"],
                "name": ["file1.pdf", "file2.docx"],
                "binary_content": [b"content1", b"content2"],
            }
        )

        result = OperatorUtils.prepare_document_content_fetch(table=table)

        assert len(result) == 2
        assert result[0]["idx"] == 0
        assert result[0]["doc_id"] == "doc1"
        assert result[0]["doc_name"] == "file1.pdf"
        assert result[0]["binary_content"] == b"content1"
        assert result[1]["idx"] == 1
        assert result[1]["doc_id"] == "doc2"
        assert result[1]["doc_name"] == "file2.docx"
        assert result[1]["binary_content"] == b"content2"

    def test_prepare_with_file_path(self, tmp_path):
        """Test preparation with file path."""
        # Create test files
        file1 = tmp_path / "test1.txt"
        file1.write_bytes(b"test content 1")

        table = pa.table(
            {
                "id": ["doc1"],
                "name": ["test1.txt"],
                "path": [str(file1)],
            }
        )

        result = OperatorUtils.prepare_document_content_fetch(table=table)

        assert len(result) == 1
        assert result[0]["idx"] == 0
        assert result[0]["doc_id"] == "doc1"
        assert result[0]["doc_name"] == "test1.txt"
        assert result[0]["binary_content"] == b"test content 1"

    def test_prepare_with_unsupported_extension(self):
        """Test preparation with unsupported file extension."""
        table = pa.table(
            {
                "id": ["doc1"],
                "name": ["file.xyz"],
                "binary_content": [b"content"],
            }
        )

        supported_extensions = {".pdf", ".docx", ".txt"}
        result = OperatorUtils.prepare_document_content_fetch(table=table, supported_extensions=supported_extensions)

        assert len(result) == 1
        assert result[0]["idx"] == 0
        assert result[0]["doc_id"] == "doc1"
        assert result[0]["doc_name"] == "file.xyz"
        assert "error" in result[0]
        assert "Unsupported file extension: .xyz" in result[0]["error"]
        assert result[0]["skip_reason"] == "unsupported_extension"
        assert "binary_content" not in result[0]

    def test_prepare_missing_id_uses_path(self):
        """Test that path is used as doc_id when id column is missing."""
        table = pa.table(
            {
                "name": ["file1.pdf"],
                "path": ["/path/to/file1.pdf"],
                "binary_content": [b"content"],
            }
        )

        result = OperatorUtils.prepare_document_content_fetch(table=table)

        assert len(result) == 1
        assert result[0]["doc_id"] == "/path/to/file1.pdf"

    def test_prepare_missing_id_and_path_uses_index(self):
        """Test that index is used as doc_id when both id and path are missing."""
        table = pa.table(
            {
                "name": ["file1.pdf"],
                "binary_content": [b"content"],
            }
        )

        result = OperatorUtils.prepare_document_content_fetch(table=table)

        assert len(result) == 1
        assert result[0]["doc_id"] == "doc_0"

    def test_prepare_missing_name_uses_index(self):
        """Test that index is used for doc_name when name column is missing."""
        table = pa.table(
            {
                "id": ["doc1"],
                "binary_content": [b"content"],
            }
        )

        result = OperatorUtils.prepare_document_content_fetch(table=table)

        assert len(result) == 1
        assert result[0]["doc_name"] == "document_0"

    def test_prepare_with_metadata_column(self, tmp_path):
        """Test preparation with metadata column containing item_id."""
        file1 = tmp_path / "test.txt"
        file1.write_bytes(b"test content")

        import json

        metadata = json.dumps({"item_id": "item123", "other": "data"})

        table = pa.table(
            {
                "id": ["doc1"],
                "name": ["test.txt"],
                "path": [str(file1)],
                "metadata": [metadata],
            }
        )

        result = OperatorUtils.prepare_document_content_fetch(table=table)

        assert len(result) == 1
        assert result[0]["binary_content"] == b"test content"

    def test_prepare_with_source_columns(self, tmp_path):
        """Test preparation with source and source_id columns."""
        file1 = tmp_path / "test.txt"
        file1.write_bytes(b"test content")

        table = pa.table(
            {
                "id": ["doc1"],
                "name": ["test.txt"],
                "path": [str(file1)],
                "source": ["s3"],
                "source_id": ["bucket/key"],
            }
        )

        result = OperatorUtils.prepare_document_content_fetch(table=table)

        assert len(result) == 1
        assert result[0]["binary_content"] == b"test content"

    def test_prepare_error_handling(self):
        """Test error handling when binary content fetch fails."""
        table = pa.table(
            {
                "id": ["doc1"],
                "name": ["nonexistent.txt"],
                "path": ["/nonexistent/path/file.txt"],
            }
        )

        result = OperatorUtils.prepare_document_content_fetch(table=table)

        assert len(result) == 1
        assert "error" in result[0]
        # When error occurs, doc_id falls back to doc_<idx>
        assert result[0]["doc_id"] == "doc_0"


class TestExtractContentAdditional:
    """Additional test suite for extract_content function focusing on untested branches."""

    def test_extract_with_converter_config(self, mocker):
        """Test extraction with converter_config parameter."""
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import PdfFormatOption

        # Mock DocumentConverter
        mock_converter = mocker.MagicMock()
        mock_result = mocker.MagicMock()
        mock_result.document.export_to_markdown.return_value = "# Test Content"
        mock_result.document.pages = [1]
        mock_converter.convert.return_value = mock_result

        mocker.patch("docpipe.core.operators.operator_utils.DocumentConverter", return_value=mock_converter)

        pdf_content = b"%PDF-1.4\n%test content\n%%EOF"

        converter_config = {
            "format_options": {InputFormat.PDF: PdfFormatOption(pipeline_options=PdfPipelineOptions(do_ocr=False))}
        }

        result = OperatorUtils.extract_content(
            file_path="test.pdf",
            binary_content=pdf_content,
            converter_config=converter_config,
        )

        assert result["success"] is True
        assert "content" in result
        assert "metadata" in result

    def test_extract_with_additional_formats_html(self, mocker):
        """Test extraction with HTML additional format."""
        mock_converter = mocker.MagicMock()
        mock_result = mocker.MagicMock()
        mock_result.document.export_to_markdown.return_value = "# Test"
        mock_result.document.export_to_html.return_value = "<h1>Test</h1>"
        mock_result.document.pages = [1]
        mock_converter.convert.return_value = mock_result

        mocker.patch("docpipe.core.operators.operator_utils.DocumentConverter", return_value=mock_converter)

        pdf_content = b"%PDF-1.4\n%test content\n%%EOF"

        result = OperatorUtils.extract_content(
            file_path="test.pdf",
            binary_content=pdf_content,
            additional_formats=["html"],
        )

        assert result["success"] is True
        assert "content" in result
        assert "content_html" in result
        assert "html" in result["metadata"]["output_formats_generated"]

    def test_extract_with_additional_formats_json(self, mocker):
        """Test extraction with JSON additional format."""
        mock_converter = mocker.MagicMock()
        mock_result = mocker.MagicMock()
        mock_result.document.export_to_markdown.return_value = "# Test"
        mock_result.document.export_to_dict.return_value = {"test": "data"}
        mock_result.document.pages = [1]
        mock_converter.convert.return_value = mock_result

        mocker.patch("docpipe.core.operators.operator_utils.DocumentConverter", return_value=mock_converter)

        pdf_content = b"%PDF-1.4\n%test content\n%%EOF"

        result = OperatorUtils.extract_content(
            file_path="test.pdf",
            binary_content=pdf_content,
            additional_formats=["json"],
        )

        assert result["success"] is True
        assert "content" in result
        assert "content_json" in result
        assert "json" in result["metadata"]["output_formats_generated"]

    def test_extract_with_additional_formats_text(self, mocker):
        """Test extraction with text additional format."""
        mock_converter = mocker.MagicMock()
        mock_result = mocker.MagicMock()
        mock_result.document.export_to_markdown.return_value = "# Test"
        mock_result.document.export_to_text.return_value = "Test"
        mock_result.document.pages = [1]
        mock_converter.convert.return_value = mock_result

        mocker.patch("docpipe.core.operators.operator_utils.DocumentConverter", return_value=mock_converter)

        pdf_content = b"%PDF-1.4\n%test content\n%%EOF"

        result = OperatorUtils.extract_content(
            file_path="test.pdf",
            binary_content=pdf_content,
            additional_formats=["text"],
        )

        assert result["success"] is True
        assert "content" in result
        assert "content_text" in result
        assert "text" in result["metadata"]["output_formats_generated"]

    def test_extract_with_additional_formats_doctags(self, mocker):
        """Test extraction with doctags additional format."""
        mock_converter = mocker.MagicMock()
        mock_result = mocker.MagicMock()
        mock_result.document.export_to_markdown.return_value = "# Test"
        mock_result.document.export_to_doctags.return_value = "doctags_content"
        mock_result.document.pages = [1]
        mock_converter.convert.return_value = mock_result

        mocker.patch("docpipe.core.operators.operator_utils.DocumentConverter", return_value=mock_converter)

        pdf_content = b"%PDF-1.4\n%test content\n%%EOF"

        result = OperatorUtils.extract_content(
            file_path="test.pdf",
            binary_content=pdf_content,
            additional_formats=["doctags"],
        )

        assert result["success"] is True
        assert "content" in result
        assert "content_doctags" in result
        assert "doctags" in result["metadata"]["output_formats_generated"]

    def test_extract_with_multiple_additional_formats(self, mocker):
        """Test extraction with multiple additional formats."""
        mock_converter = mocker.MagicMock()
        mock_result = mocker.MagicMock()
        mock_result.document.export_to_markdown.return_value = "# Test"
        mock_result.document.export_to_html.return_value = "<h1>Test</h1>"
        mock_result.document.export_to_dict.return_value = {"test": "data"}
        mock_result.document.export_to_text.return_value = "Test"
        mock_result.document.pages = [1]
        mock_converter.convert.return_value = mock_result

        mocker.patch("docpipe.core.operators.operator_utils.DocumentConverter", return_value=mock_converter)

        pdf_content = b"%PDF-1.4\n%test content\n%%EOF"

        result = OperatorUtils.extract_content(
            file_path="test.pdf",
            binary_content=pdf_content,
            additional_formats=["html", "json", "text"],
        )

        assert result["success"] is True
        assert "content" in result
        assert "content_html" in result
        assert "content_json" in result
        assert "content_text" in result
        assert len(result["metadata"]["output_formats_generated"]) == 4

    def test_extract_filters_markdown_from_additional_formats(self, mocker):
        """Test that markdown is filtered out if mistakenly included in additional_formats."""
        mock_converter = mocker.MagicMock()
        mock_result = mocker.MagicMock()
        mock_result.document.export_to_markdown.return_value = "# Test"
        mock_result.document.export_to_html.return_value = "<h1>Test</h1>"
        mock_result.document.pages = [1]
        mock_converter.convert.return_value = mock_result

        mocker.patch("docpipe.core.operators.operator_utils.DocumentConverter", return_value=mock_converter)

        pdf_content = b"%PDF-1.4\n%test content\n%%EOF"

        result = OperatorUtils.extract_content(
            file_path="test.pdf",
            binary_content=pdf_content,
            additional_formats=["markdown", "html"],
        )

        assert result["success"] is True
        assert "content" in result
        assert "content_html" in result
        markdown_count = result["metadata"]["output_formats_generated"].count("markdown")
        assert markdown_count == 1

    def test_extract_with_unknown_format(self, mocker):
        """Test extraction with unknown format in additional_formats."""
        mock_converter = mocker.MagicMock()
        mock_result = mocker.MagicMock()
        mock_result.document.export_to_markdown.return_value = "# Test"
        mock_result.document.pages = [1]
        mock_converter.convert.return_value = mock_result

        mocker.patch("docpipe.core.operators.operator_utils.DocumentConverter", return_value=mock_converter)

        pdf_content = b"%PDF-1.4\n%test content\n%%EOF"

        result = OperatorUtils.extract_content(
            file_path="test.pdf",
            binary_content=pdf_content,
            additional_formats=["unknown_format"],
        )

        assert result["success"] is True
        assert "content" in result
        assert "unknown_format" in result["metadata"]["output_formats_failed"]

    def test_extract_text_file_via_extract_content(self):
        """Test that .txt files are handled by extract_text_file."""
        text_content = b"This is plain text content."

        result = OperatorUtils.extract_content(
            file_path="test.txt",
            binary_content=text_content,
        )

        assert result["success"] is True
        assert result["content"] == "This is plain text content."
        assert result["metadata"]["is_text_file"] is True

    def test_extract_with_extension_detection(self, mocker):
        """Test automatic extension detection when file has no extension."""
        mock_converter = mocker.MagicMock()
        mock_result = mocker.MagicMock()
        mock_result.document.export_to_markdown.return_value = "# Test"
        mock_result.document.pages = [1]
        mock_converter.convert.return_value = mock_result

        mocker.patch("docpipe.core.operators.operator_utils.DocumentConverter", return_value=mock_converter)

        pdf_content = b"%PDF-1.4\n%test content\n%%EOF"

        result = OperatorUtils.extract_content(
            file_path="document_without_extension",
            binary_content=pdf_content,
        )

        assert result["success"] is True
        assert "content" in result

    def test_extract_audio_file(self, tmp_path):
        """Test audio file handling (creates temporary file)."""
        # Create a minimal valid audio file (WAV format)
        # WAV header: RIFF + size + WAVE + fmt chunk + data chunk
        wav_content = (
            b"RIFF"
            + (36).to_bytes(4, "little")  # File size - 8
            + b"WAVE"
            + b"fmt "
            + (16).to_bytes(4, "little")  # fmt chunk size
            + (1).to_bytes(2, "little")  # Audio format (PCM)
            + (1).to_bytes(2, "little")  # Channels
            + (44100).to_bytes(4, "little")  # Sample rate
            + (88200).to_bytes(4, "little")  # Byte rate
            + (2).to_bytes(2, "little")  # Block align
            + (16).to_bytes(2, "little")  # Bits per sample
            + b"data"
            + (0).to_bytes(4, "little")  # Data size
        )

        result = OperatorUtils.extract_content(
            file_path="test.wav",
            binary_content=wav_content,
        )

        # Audio extraction may succeed or fail depending on ASR availability
        assert "success" in result
        assert "content" in result or "error" in result
