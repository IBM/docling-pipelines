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
        assert "or 'nodes'" in str(exc_info.value)

    def test_missing_required_keys(self):
        """Test dict without required keys raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_flow_definition({"other_key": "value"})
        assert "definition must contain either 'doc_type'" in str(exc_info.value)

    # DAG format tests
    def test_valid_dag_format_minimal(self):
        """Test valid minimal DAG format."""
        definition = {
            "nodes": [{"id": "node1", "operator": "ingest_local"}],
            "edges": [],
        }
        result = validate_flow_definition(definition)
        assert result == definition

    def test_valid_dag_format_with_edges(self):
        """Test valid DAG format with edges."""
        definition = {
            "nodes": [
                {"id": "node1", "operator": "ingest_local"},
                {"id": "node2", "operator": "extract_operator"},
            ],
            "edges": [{"source": "node1", "target": "node2"}],
        }
        result = validate_flow_definition(definition)
        assert result == definition

    def test_valid_dag_with_operator_type(self):
        """Test DAG with operator_type instead of operator."""
        definition = {
            "nodes": [{"id": "node1", "operator_type": "datasift.core.operators.IngestLocal"}],
            "edges": [],
        }
        result = validate_flow_definition(definition)
        assert result == definition

    def test_valid_dag_with_operator_params(self):
        """Test DAG with operator_params."""
        definition = {
            "nodes": [
                {
                    "id": "node1",
                    "operator": "ingest_local",
                    "operator_params": {"input_folder": "/path"},
                }
            ],
            "edges": [],
        }
        result = validate_flow_definition(definition)
        assert result == definition

    def test_valid_dag_with_config(self):
        """Test DAG with config instead of operator_params."""
        definition = {
            "nodes": [
                {
                    "id": "node1",
                    "operator": "ingest_local",
                    "config": {"input_folder": "/path"},
                }
            ],
            "edges": [],
        }
        result = validate_flow_definition(definition)
        assert result == definition

    def test_dag_missing_nodes_key(self):
        """Test DAG format missing nodes key raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_flow_definition({"edges": []})
        assert "definition must contain either 'doc_type'" in str(exc_info.value)
        assert "or 'nodes'" in str(exc_info.value)

    def test_dag_nodes_not_list(self):
        """Test nodes not being a list raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_flow_definition({"nodes": "not a list"})
        assert "nodes must be a list" in str(exc_info.value)

    def test_dag_empty_nodes(self):
        """Test empty nodes list raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_flow_definition({"nodes": []})
        assert "nodes list cannot be empty" in str(exc_info.value)

    def test_dag_node_not_dict(self):
        """Test node not being a dict raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_flow_definition({"nodes": ["not a dict"]})
        assert "node at index 0 must be a dictionary" in str(exc_info.value)

    def test_dag_node_missing_id(self):
        """Test node missing id raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_flow_definition({"nodes": [{"operator": "ingest"}]})
        assert "node at index 0 is missing required field 'id'" in str(exc_info.value)

    def test_dag_node_invalid_id(self):
        """Test node with invalid id raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_flow_definition({"nodes": [{"id": "", "operator": "ingest"}]})
        assert "node at index 0 has invalid 'id'" in str(exc_info.value)

    def test_dag_node_duplicate_id(self):
        """Test duplicate node IDs raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_flow_definition(
                {
                    "nodes": [
                        {"id": "node1", "operator": "ingest"},
                        {"id": "node1", "operator": "extract"},
                    ]
                }
            )
        assert "duplicate node id 'node1'" in str(exc_info.value)

    def test_dag_node_missing_operator(self):
        """Test node missing operator field raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_flow_definition({"nodes": [{"id": "node1"}]})
        assert "is missing required field 'operator' or 'operator_type'" in str(exc_info.value)

    def test_dag_node_invalid_operator_params(self):
        """Test node with invalid operator_params raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_flow_definition(
                {
                    "nodes": [
                        {
                            "id": "node1",
                            "operator": "ingest",
                            "operator_params": "not a dict",
                        }
                    ]
                }
            )
        assert "has invalid 'operator_params'/'config'" in str(exc_info.value)

    def test_dag_edges_not_list(self):
        """Test edges not being a list raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_flow_definition(
                {
                    "nodes": [{"id": "node1", "operator": "ingest"}],
                    "edges": "not a list",
                }
            )
        assert "edges must be a list" in str(exc_info.value)

    def test_dag_edge_not_dict(self):
        """Test edge not being a dict raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_flow_definition(
                {
                    "nodes": [{"id": "node1", "operator": "ingest"}],
                    "edges": ["not a dict"],
                }
            )
        assert "edge at index 0 must be a dictionary" in str(exc_info.value)

    def test_dag_edge_missing_source(self):
        """Test edge missing source raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_flow_definition(
                {
                    "nodes": [
                        {"id": "node1", "operator": "ingest"},
                        {"id": "node2", "operator": "extract"},
                    ],
                    "edges": [{"target": "node2"}],
                }
            )
        assert "edge at index 0 is missing required field 'source'" in str(exc_info.value)

    def test_dag_edge_missing_target(self):
        """Test edge missing target raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_flow_definition(
                {
                    "nodes": [
                        {"id": "node1", "operator": "ingest"},
                        {"id": "node2", "operator": "extract"},
                    ],
                    "edges": [{"source": "node1"}],
                }
            )
        assert "edge at index 0 is missing required field 'target'" in str(exc_info.value)

    def test_dag_edge_invalid_source(self):
        """Test edge with invalid source raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_flow_definition(
                {
                    "nodes": [{"id": "node1", "operator": "ingest"}],
                    "edges": [{"source": "", "target": "node1"}],
                }
            )
        assert "edge at index 0 has invalid 'source'" in str(exc_info.value)

    def test_dag_edge_nonexistent_source(self):
        """Test edge referencing non-existent source raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_flow_definition(
                {
                    "nodes": [{"id": "node1", "operator": "ingest"}],
                    "edges": [{"source": "nonexistent", "target": "node1"}],
                }
            )
        assert "references non-existent source node 'nonexistent'" in str(exc_info.value)

    def test_dag_edge_nonexistent_target(self):
        """Test edge referencing non-existent target raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_flow_definition(
                {
                    "nodes": [{"id": "node1", "operator": "ingest"}],
                    "edges": [{"source": "node1", "target": "nonexistent"}],
                }
            )
        assert "references non-existent target node 'nonexistent'" in str(exc_info.value)

    def test_dag_edge_self_referencing(self):
        """Test self-referencing edge raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_flow_definition(
                {
                    "nodes": [{"id": "node1", "operator": "ingest"}],
                    "edges": [{"source": "node1", "target": "node1"}],
                }
            )
        assert "is self-referencing" in str(exc_info.value)

    def test_dag_cycle_detection_simple(self):
        """Test simple cycle detection."""
        with pytest.raises(ValueError) as exc_info:
            validate_flow_definition(
                {
                    "nodes": [
                        {"id": "node1", "operator": "ingest"},
                        {"id": "node2", "operator": "extract"},
                    ],
                    "edges": [
                        {"source": "node1", "target": "node2"},
                        {"source": "node2", "target": "node1"},
                    ],
                }
            )
        assert "cycle detected in DAG" in str(exc_info.value)

    def test_dag_cycle_detection_complex(self):
        """Test complex cycle detection."""
        with pytest.raises(ValueError) as exc_info:
            validate_flow_definition(
                {
                    "nodes": [
                        {"id": "node1", "operator": "ingest"},
                        {"id": "node2", "operator": "extract"},
                        {"id": "node3", "operator": "chunk"},
                    ],
                    "edges": [
                        {"source": "node1", "target": "node2"},
                        {"source": "node2", "target": "node3"},
                        {"source": "node3", "target": "node1"},
                    ],
                }
            )
        assert "cycle detected in DAG" in str(exc_info.value)

    def test_dag_no_cycle_linear(self):
        """Test linear DAG has no cycle."""
        definition = {
            "nodes": [
                {"id": "node1", "operator": "ingest"},
                {"id": "node2", "operator": "extract"},
                {"id": "node3", "operator": "chunk"},
            ],
            "edges": [
                {"source": "node1", "target": "node2"},
                {"source": "node2", "target": "node3"},
            ],
        }
        result = validate_flow_definition(definition)
        assert result == definition

    def test_dag_no_cycle_branching(self):
        """Test branching DAG has no cycle."""
        definition = {
            "nodes": [
                {"id": "node1", "operator": "ingest"},
                {"id": "node2", "operator": "extract"},
                {"id": "node3", "operator": "chunk"},
            ],
            "edges": [
                {"source": "node1", "target": "node2"},
                {"source": "node1", "target": "node3"},
            ],
        }
        result = validate_flow_definition(definition)
        assert result == definition

    # Operator type validation tests
    def test_operator_type_valid_simple(self):
        """Test valid simple operator type."""
        definition = {
            "nodes": [{"id": "node1", "operator": "ingest_local"}],
            "edges": [],
        }
        result = validate_flow_definition(definition)
        assert result == definition

    def test_operator_type_valid_dotted(self):
        """Test valid dotted operator type."""
        definition = {
            "nodes": [{"id": "node1", "operator": "datasift.core.operators.IngestLocal"}],
            "edges": [],
        }
        result = validate_flow_definition(definition)
        assert result == definition

    def test_operator_type_invalid_empty(self):
        """Test empty operator type raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_flow_definition({"nodes": [{"id": "node1", "operator": ""}]})
        assert "is missing required field 'operator' or 'operator_type'" in str(exc_info.value)

    def test_operator_type_invalid_format(self):
        """Test invalid operator type format raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_flow_definition({"nodes": [{"id": "node1", "operator": "123invalid"}]})
        assert "contains invalid identifier" in str(exc_info.value)

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
