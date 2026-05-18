"""Unit tests for validation utility functions."""

import pytest

from datasift.utils.core.validation import (
    deduplicate_tags,
    validate_container_kind,
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
