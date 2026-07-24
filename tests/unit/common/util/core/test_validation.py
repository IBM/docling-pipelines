"""Unit tests for validation utility functions."""

import pytest

from docpipe.utils.core.validation import (
    _validate_authoring_format,
    _validate_dag_nodes,
    _validate_operator_type_format,
    deduplicate_tags,
    is_date_time_as_per_format,
    is_value_in_range,
    to_bool,
    validate_container_kind,
    validate_database_path,
    validate_flow_definition,
    validate_uuid_format,
)


class TestValidateUuidFormat:
    """Tests for validate_uuid_format function."""

    def test_valid_uuid(self):
        """Test validation passes for valid UUID."""
        uuid_str = "550e8400-e29b-41d4-a716-446655440000"
        result = validate_uuid_format(uuid_str, "test_field")
        assert result == uuid_str

    def test_none_value(self):
        """Test None value returns None."""
        result = validate_uuid_format(None, "test_field")
        assert result is None

    def test_invalid_uuid_format(self):
        """Test invalid UUID format raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_uuid_format("invalid-uuid", "test_field")
        assert "test_field must be a valid UUID format" in str(exc_info.value)
        assert "550e8400-e29b-41d4-a716-446655440000" in str(exc_info.value)

    def test_empty_string(self):
        """Test empty string raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_uuid_format("", "test_field")
        assert "test_field must be a valid UUID format" in str(exc_info.value)

    def test_partial_uuid(self):
        """Test partial UUID raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_uuid_format("550e8400-e29b", "test_field")
        assert "test_field must be a valid UUID format" in str(exc_info.value)

    def test_uuid_with_extra_characters(self):
        """Test UUID with extra characters raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_uuid_format("550e8400-e29b-41d4-a716-446655440000-extra", "test_field")
        assert "test_field must be a valid UUID format" in str(exc_info.value)

    def test_different_field_names(self):
        """Test error message includes correct field name."""
        with pytest.raises(ValueError) as exc_info:
            validate_uuid_format("invalid", "container_id")
        assert "container_id must be a valid UUID format" in str(exc_info.value)

        with pytest.raises(ValueError) as exc_info:
            validate_uuid_format("invalid", "job_id")
        assert "job_id must be a valid UUID format" in str(exc_info.value)


class TestValidateContainerKind:
    """Tests for validate_container_kind function."""

    def test_valid_project(self):
        """Test 'project' is valid."""
        result = validate_container_kind("project")
        assert result == "project"

    def test_valid_space(self):
        """Test 'space' is valid."""
        result = validate_container_kind("space")
        assert result == "space"

    def test_none_value(self):
        """Test None value returns None."""
        result = validate_container_kind(None)
        assert result is None

    def test_invalid_value(self):
        """Test invalid container kind raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_container_kind("invalid")
        assert "container_kind must be 'project' or 'space'" in str(exc_info.value)
        assert "got 'invalid'" in str(exc_info.value)

    def test_case_sensitive(self):
        """Test validation is case-sensitive."""
        with pytest.raises(ValueError):
            validate_container_kind("Project")
        with pytest.raises(ValueError):
            validate_container_kind("SPACE")

    def test_empty_string(self):
        """Test empty string raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_container_kind("")
        assert "container_kind must be 'project' or 'space'" in str(exc_info.value)


class TestValidateFlowDefinition:
    """Tests for validate_flow_definition function."""

    # Basic format tests
    def test_none_value(self):
        """Test None value returns None."""
        result = validate_flow_definition(None)
        assert result is None

    def test_invalid_not_dict(self):
        """Test non-dict value raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_flow_definition("not a dict")
        assert "definition must be a dictionary" in str(exc_info.value)
        assert "got str" in str(exc_info.value)

    def test_invalid_list(self):
        """Test list value raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_flow_definition([])
        assert "definition must be a dictionary" in str(exc_info.value)
        assert "got list" in str(exc_info.value)

    def test_empty_dict(self):
        """Test empty dict raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_flow_definition({})
        assert "definition must contain either 'doc_type'" in str(exc_info.value)
        assert "or 'flow_name'" in str(exc_info.value)

    def test_missing_required_keys(self):
        """Test dict without required keys raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_flow_definition({"other_key": "value"})
        assert "definition must contain either 'doc_type'" in str(exc_info.value)

    # Elyra format tests
    def test_valid_elyra_format_minimal(self):
        """Test valid minimal Elyra format."""
        definition = {"doc_type": "pipeline", "pipelines": [{"id": "pipeline1"}]}
        result = validate_flow_definition(definition)
        assert result == definition

    def test_valid_elyra_format_with_primary(self):
        """Test valid Elyra format with primary_pipeline."""
        definition = {
            "doc_type": "pipeline",
            "version": "3.0",
            "pipelines": [{"id": "pipeline1"}],
            "primary_pipeline": "pipeline1",
        }
        result = validate_flow_definition(definition)
        assert result == definition

    def test_elyra_missing_pipelines(self):
        """Test Elyra format missing pipelines raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_flow_definition({"doc_type": "pipeline"})
        assert "must contain 'pipelines' key" in str(exc_info.value)

    def test_elyra_pipelines_not_list(self):
        """Test Elyra pipelines not being a list raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_flow_definition({"doc_type": "pipeline", "pipelines": "not a list"})
        assert "pipelines must be a list" in str(exc_info.value)

    def test_elyra_empty_pipelines(self):
        """Test Elyra empty pipelines raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_flow_definition({"doc_type": "pipeline", "pipelines": []})
        assert "pipelines list cannot be empty" in str(exc_info.value)

    def test_elyra_invalid_primary_pipeline(self):
        """Test Elyra invalid primary_pipeline raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_flow_definition(
                {
                    "doc_type": "pipeline",
                    "pipelines": [{"id": "pipeline1"}],
                    "primary_pipeline": "",
                }
            )
        assert "primary_pipeline must be a non-empty string" in str(exc_info.value)


class TestDeduplicateTags:
    """Tests for deduplicate_tags function."""

    def test_no_duplicates(self):
        """Test list with no duplicates remains unchanged."""
        tags = ["tag1", "tag2", "tag3"]
        result = deduplicate_tags(tags)
        assert result == tags

    def test_with_duplicates(self):
        """Test duplicates are removed while preserving order."""
        tags = ["tag1", "tag2", "tag1", "tag3", "tag2"]
        result = deduplicate_tags(tags)
        assert result == ["tag1", "tag2", "tag3"]

    def test_empty_list(self):
        """Test empty list returns empty list."""
        result = deduplicate_tags([])
        assert result == []

    def test_single_tag(self):
        """Test single tag list."""
        result = deduplicate_tags(["tag1"])
        assert result == ["tag1"]

    def test_all_duplicates(self):
        """Test list with all duplicates."""
        tags = ["tag1", "tag1", "tag1"]
        result = deduplicate_tags(tags)
        assert result == ["tag1"]

    def test_none_with_allow_none_false(self):
        """Test None returns empty list when allow_none=False."""
        result = deduplicate_tags(None, allow_none=False)
        assert result == []

    def test_none_with_allow_none_true(self):
        """Test None returns None when allow_none=True."""
        result = deduplicate_tags(None, allow_none=True)
        assert result is None

    def test_invalid_not_list(self):
        """Test non-list value raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            deduplicate_tags("not a list")
        assert "tags must be a list" in str(exc_info.value)
        assert "got str" in str(exc_info.value)

    def test_invalid_dict(self):
        """Test dict value raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            deduplicate_tags({"key": "value"})
        assert "tags must be a list" in str(exc_info.value)
        assert "got dict" in str(exc_info.value)

    def test_non_string_element(self):
        """Test list with non-string element raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            deduplicate_tags(["tag1", 123, "tag2"])
        assert "all tags must be strings" in str(exc_info.value)
        assert "got int" in str(exc_info.value)

    def test_mixed_non_string_elements(self):
        """Test list with various non-string elements raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            deduplicate_tags(["tag1", None])
        assert "all tags must be strings" in str(exc_info.value)

        with pytest.raises(ValueError) as exc_info:
            deduplicate_tags(["tag1", ["nested"]])
        assert "all tags must be strings" in str(exc_info.value)

    def test_preserves_order(self):
        """Test that order is preserved when deduplicating."""
        tags = ["z", "a", "m", "a", "z", "b"]
        result = deduplicate_tags(tags)
        assert result == ["z", "a", "m", "b"]

    def test_case_sensitive(self):
        """Test deduplication is case-sensitive."""
        tags = ["Tag", "tag", "TAG"]
        result = deduplicate_tags(tags)
        assert result == ["Tag", "tag", "TAG"]

    def test_whitespace_preserved(self):
        """Test tags with whitespace are treated as distinct."""
        tags = ["tag", " tag", "tag ", " tag "]
        result = deduplicate_tags(tags)
        assert result == ["tag", " tag", "tag ", " tag "]


class TestToBool:
    """Tests for to_bool function."""

    def test_bool_true(self):
        """Test boolean True returns True."""
        assert to_bool(True) is True

    def test_bool_false(self):
        """Test boolean False returns False."""
        assert to_bool(False) is False

    def test_string_true_lowercase(self):
        """Test string 'true' returns True."""
        assert to_bool("true") is True

    def test_string_true_uppercase(self):
        """Test string 'TRUE' returns True."""
        assert to_bool("TRUE") is True

    def test_string_true_mixed_case(self):
        """Test string 'TrUe' returns True."""
        assert to_bool("TrUe") is True

    def test_string_true_with_whitespace(self):
        """Test string ' true ' returns True."""
        assert to_bool(" true ") is True

    def test_string_false(self):
        """Test string 'false' returns False."""
        assert to_bool("false") is False

    def test_string_one(self):
        """Test string '1' returns False."""
        assert to_bool("1") is False

    def test_integer_one(self):
        """Test integer 1 returns False."""
        assert to_bool(1) is False

    def test_integer_zero(self):
        """Test integer 0 returns False."""
        assert to_bool(0) is False

    def test_none(self):
        """Test None returns False."""
        assert to_bool(None) is False

    def test_empty_string(self):
        """Test empty string returns False."""
        assert to_bool("") is False

    def test_list(self):
        """Test list returns False."""
        assert to_bool([]) is False

    def test_dict(self):
        """Test dict returns False."""
        assert to_bool({}) is False


class TestIsValueInRange:
    """Tests for is_value_in_range function."""

    def test_value_in_range(self):
        """Test value within range returns True."""
        assert is_value_in_range(value=5, min_value=1, max_value=10) is True

    def test_value_at_min(self):
        """Test value at minimum returns True."""
        assert is_value_in_range(value=1, min_value=1, max_value=10) is True

    def test_value_at_max(self):
        """Test value at maximum returns True."""
        assert is_value_in_range(value=10, min_value=1, max_value=10) is True

    def test_value_below_range(self):
        """Test value below range returns False."""
        assert is_value_in_range(value=0, min_value=1, max_value=10) is False

    def test_value_above_range(self):
        """Test value above range returns False."""
        assert is_value_in_range(value=11, min_value=1, max_value=10) is False

    def test_float_values(self):
        """Test with float values."""
        assert is_value_in_range(value=5.5, min_value=1.0, max_value=10.0) is True
        assert is_value_in_range(value=0.5, min_value=1.0, max_value=10.0) is False

    def test_negative_range(self):
        """Test with negative range."""
        assert is_value_in_range(value=-5, min_value=-10, max_value=-1) is True
        assert is_value_in_range(value=0, min_value=-10, max_value=-1) is False


class TestIsDateTimeAsPerFormat:
    """Tests for is_date_time_as_per_format function."""

    def test_valid_date_format(self):
        """Test valid date with correct format returns True."""
        assert is_date_time_as_per_format("2024-01-15", "%Y-%m-%d") is True

    def test_valid_datetime_format(self):
        """Test valid datetime with correct format returns True."""
        assert is_date_time_as_per_format("2024-01-15 14:30:00", "%Y-%m-%d %H:%M:%S") is True

    def test_invalid_date_format(self):
        """Test invalid date format returns False."""
        assert is_date_time_as_per_format("2024-01-15", "%d/%m/%Y") is False

    def test_invalid_date_value(self):
        """Test invalid date value returns False."""
        assert is_date_time_as_per_format("2024-13-45", "%Y-%m-%d") is False

    def test_empty_string(self):
        """Test empty string returns False."""
        assert is_date_time_as_per_format("", "%Y-%m-%d") is False

    def test_partial_date(self):
        """Test partial date returns False."""
        assert is_date_time_as_per_format("2024-01", "%Y-%m-%d") is False


class TestValidateOperatorTypeFormat:
    """Tests for _validate_operator_type_format function."""

    def test_valid_simple_name(self):
        """Test valid simple operator name."""
        _validate_operator_type_format("ingest_local")

    def test_valid_class_path(self):
        """Test valid class path."""
        _validate_operator_type_format("core.operators.IngestLocal")

    def test_valid_nested_path(self):
        """Test valid nested class path."""
        _validate_operator_type_format("docpipe.core.operators.extract.ExtractOperator")

    def test_empty_string(self):
        """Test empty string raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            _validate_operator_type_format("")
        assert "operator_type must be a non-empty string" in str(exc_info.value)

    def test_none_value(self):
        """Test None raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            _validate_operator_type_format(None)  # type: ignore
        assert "operator_type must be a non-empty string" in str(exc_info.value)

    def test_invalid_starting_with_number(self):
        """Test operator type starting with number raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            _validate_operator_type_format("123operator")
        assert "contains invalid identifier" in str(exc_info.value)

    def test_invalid_special_characters(self):
        """Test operator type with special characters raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            _validate_operator_type_format("operator.123name")
        assert "contains invalid identifier" in str(exc_info.value)


class TestValidateDagNodes:
    """Tests for _validate_dag_nodes function."""

    def test_valid_nodes(self):
        """Test valid nodes list."""
        nodes = [
            {"id": "node1", "operator": "ingest_local", "operator_params": {}},
            {"id": "node2", "operator_type": "extract", "config": {}},
        ]
        _validate_dag_nodes(nodes)

    def test_not_list(self):
        """Test non-list raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            _validate_dag_nodes("not a list")  # type: ignore
        assert "nodes must be a list" in str(exc_info.value)

    def test_empty_list(self):
        """Test empty list raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            _validate_dag_nodes([])
        assert "nodes list cannot be empty" in str(exc_info.value)

    def test_node_not_dict(self):
        """Test node that is not a dict raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            _validate_dag_nodes(["not a dict"])  # type: ignore
        assert "node at index 0 must be a dictionary" in str(exc_info.value)

    def test_missing_id(self):
        """Test node missing id raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            _validate_dag_nodes([{"operator": "ingest_local"}])
        assert "node at index 0 is missing required field 'id'" in str(exc_info.value)

    def test_invalid_id_type(self):
        """Test node with invalid id type raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            _validate_dag_nodes([{"id": 123, "operator": "ingest_local"}])  # type: ignore
        assert "node at index 0 has invalid 'id'" in str(exc_info.value)

    def test_empty_id(self):
        """Test node with empty id raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            _validate_dag_nodes([{"id": "", "operator": "ingest_local"}])
        assert "node at index 0 has invalid 'id'" in str(exc_info.value)

    def test_duplicate_ids(self):
        """Test duplicate node ids raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            _validate_dag_nodes(
                [
                    {"id": "node1", "operator": "ingest_local"},
                    {"id": "node1", "operator": "extract"},
                ]
            )
        assert "duplicate node id 'node1'" in str(exc_info.value)

    def test_missing_operator(self):
        """Test node missing operator raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            _validate_dag_nodes([{"id": "node1"}])
        assert "is missing required field 'operator' or 'operator_type'" in str(exc_info.value)

    def test_invalid_operator_params(self):
        """Test node with invalid operator_params raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            _validate_dag_nodes([{"id": "node1", "operator": "ingest_local", "operator_params": "not a dict"}])  # type: ignore
        assert "has invalid 'operator_params'/'config'" in str(exc_info.value)


class TestValidateAuthoringFormat:
    """Tests for _validate_authoring_format function."""

    def test_valid_authoring_format(self):
        """Test valid authoring format."""
        definition = {
            "flow_name": "Test Flow",
            "flow": [{"type": "ingest_local", "name": "ingest", "config": {}}],
        }
        _validate_authoring_format(definition)

    def test_missing_flow_name(self):
        """Test missing flow_name raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            _validate_authoring_format({"flow": []})
        assert "must contain 'flow_name' key" in str(exc_info.value)

    def test_empty_flow_name(self):
        """Test empty flow_name raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            _validate_authoring_format({"flow_name": "", "flow": []})
        assert "flow_name must be a non-empty string" in str(exc_info.value)

    def test_whitespace_flow_name(self):
        """Test whitespace-only flow_name raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            _validate_authoring_format({"flow_name": "   ", "flow": []})
        assert "flow_name must be a non-empty string" in str(exc_info.value)

    def test_missing_flow(self):
        """Test missing flow raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            _validate_authoring_format({"flow_name": "Test"})
        assert "must contain 'flow' key" in str(exc_info.value)

    def test_flow_not_list(self):
        """Test flow not being a list raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            _validate_authoring_format({"flow_name": "Test", "flow": "not a list"})  # type: ignore
        assert "flow must be a list" in str(exc_info.value)

    def test_empty_flow(self):
        """Test empty flow raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            _validate_authoring_format({"flow_name": "Test", "flow": []})
        assert "flow list cannot be empty" in str(exc_info.value)

    def test_operator_not_dict(self):
        """Test operator not being a dict raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            _validate_authoring_format({"flow_name": "Test", "flow": ["not a dict"]})  # type: ignore
        assert "flow operator at index 0 must be a dictionary" in str(exc_info.value)

    def test_operator_missing_type(self):
        """Test operator missing type raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            _validate_authoring_format({"flow_name": "Test", "flow": [{"name": "op1", "config": {}}]})
        assert "flow operator at index 0 is missing required field 'type'" in str(exc_info.value)

    def test_operator_missing_name(self):
        """Test operator missing name raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            _validate_authoring_format({"flow_name": "Test", "flow": [{"type": "ingest", "config": {}}]})
        assert "flow operator at index 0 is missing required field 'name'" in str(exc_info.value)

    def test_operator_missing_config(self):
        """Test operator missing config raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            _validate_authoring_format({"flow_name": "Test", "flow": [{"type": "ingest", "name": "op1"}]})
        assert "flow operator at index 0 is missing required field 'config'" in str(exc_info.value)


class TestValidateDatabasePath:
    """Tests for validate_database_path function."""

    def test_memory_database(self):
        """Test :memory: database is allowed."""
        result = validate_database_path(":memory:")
        assert result == ":memory:"

    def test_valid_relative_path(self):
        """Test valid relative path is resolved to absolute."""
        result = validate_database_path("data/docs.db")
        assert result.endswith("data/docs.db")
        assert result.startswith("/")

    def test_empty_path(self):
        """Test empty path raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_database_path("")
        assert "Database path cannot be empty" in str(exc_info.value)

    def test_whitespace_path(self):
        """Test whitespace-only path raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_database_path("   ")
        assert "Database path cannot be empty" in str(exc_info.value)

    def test_none_path(self):
        """Test None path raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_database_path(None)  # type: ignore
        assert "Database path cannot be empty" in str(exc_info.value)

    def test_path_traversal(self):
        """Test path traversal is blocked."""
        with pytest.raises(ValueError) as exc_info:
            validate_database_path("../../../etc/passwd")
        assert "Path traversal patterns (..) are not allowed" in str(exc_info.value)

    def test_path_with_base_dir(self):
        """Test path validation with base directory."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            result = validate_database_path(f"{tmpdir}/test.db", base_dir=tmpdir)
            # Use Path.resolve() to handle symlinks like /var -> /private/var on macOS
            assert Path(result).resolve().is_relative_to(Path(tmpdir).resolve())

    def test_path_outside_base_dir(self):
        """Test path outside base directory raises ValueError."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(ValueError) as exc_info:
                validate_database_path("/tmp/other.db", base_dir=tmpdir)
            assert "must be within" in str(exc_info.value)
