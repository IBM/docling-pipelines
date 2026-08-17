"""Tests for authoring flow domain models and validation."""

import pytest

from docpipe.core.assets.flows.domain.models.authoring_flow import (
    AuthoringFlow,
    AuthoringOperator,
    FlowSource,
)
from docpipe.exceptions.docpipe_exceptions import FlowInvalidDataException


class TestAuthoringOperator:
    """Tests for AuthoringOperator validation."""

    def test_valid_operator(self):
        """Test creating a valid operator."""
        op = AuthoringOperator(type="ingest_source", name="ingest_docs", config={"paths": "./data"}, depends_on=[])

        errors = op.validate(all_operator_names={"ingest_docs"}, operator_map={"ingest_docs": op})

        assert len(errors) == 0

    def test_empty_operator_type(self):
        """Test validation fails for empty operator type."""
        op = AuthoringOperator(type="", name="test_op", config={}, depends_on=[])

        errors = op.validate(all_operator_names={"test_op"}, operator_map={"test_op": op})

        assert len(errors) == 1
        assert "type cannot be empty" in errors[0]

    def test_operator_name_with_spaces(self):
        """Test validation fails for operator name with spaces."""
        op = AuthoringOperator(type="ingest_source", name="test op", config={}, depends_on=[])

        errors = op.validate(all_operator_names={"test op"}, operator_map={"test op": op})

        assert len(errors) == 1
        assert "cannot contain spaces" in errors[0]

    def test_operator_name_with_branch_separator(self):
        """Test validation fails for operator name with branch separator."""
        op = AuthoringOperator(type="ingest_source", name="test.op", config={}, depends_on=[])

        errors = op.validate(all_operator_names={"test.op"}, operator_map={"test.op": op})

        assert len(errors) == 1
        assert "cannot contain '.'" in errors[0]

    def test_invalid_config_type(self):
        """Test validation fails for non-dict config."""
        op = AuthoringOperator(
            type="ingest_source",
            name="test_op",
            config="invalid",  # type: ignore
            depends_on=[],
        )

        errors = op.validate(all_operator_names={"test_op"}, operator_map={"test_op": op})

        assert len(errors) == 1
        assert "config must be a dictionary" in errors[0]

    def test_nonexistent_dependency(self):
        """Test validation fails for nonexistent dependency."""
        op = AuthoringOperator(type="extract_operator", name="extract", config={}, depends_on=["nonexistent"])

        errors = op.validate(all_operator_names={"extract"}, operator_map={"extract": op})

        assert len(errors) == 1
        assert "not found in flow" in errors[0]

    def test_circular_dependency(self):
        """Test that circular dependencies are detected at flow level."""
        # Create operators with circular dependency: op1 -> op2 -> op1
        op1 = AuthoringOperator(type="test_op", name="op1", depends_on=["op2"])
        op2 = AuthoringOperator(type="test_op", name="op2", depends_on=["op1"])

        # Circular dependency is detected at flow level, not operator level
        flow = AuthoringFlow(flow_name="test_flow", flow=[op1, op2], flow_source=FlowSource.CLI)

        # Flow validation should detect circular dependency
        with pytest.raises(FlowInvalidDataException) as exc_info:
            flow.validate()

        assert "Circular dependency" in str(exc_info.value)


class TestAuthoringFlow:
    """Tests for AuthoringFlow validation."""

    def test_valid_flow(self):
        """Test creating a valid flow."""
        flow = AuthoringFlow(
            flow_name="test-flow",
            description="Test flow",
            global_config={},
            flow=[
                AuthoringOperator(type="ingest_source", name="ingest", config={"paths": "./data"}, depends_on=[]),
                AuthoringOperator(type="extract_operator", name="extract", config={}, depends_on=["ingest"]),
            ],
            flow_source=FlowSource.CLI,
        )

        flow.validate()  # Should not raise

    def test_empty_flow_name(self):
        """Test validation fails for empty flow name."""
        flow = AuthoringFlow(
            flow_name="",
            description="Test",
            global_config={},
            flow=[AuthoringOperator(type="ingest_source", name="ingest", config={}, depends_on=[])],
            flow_source=FlowSource.CLI,
        )

        with pytest.raises(FlowInvalidDataException) as exc_info:
            flow.validate()

        assert "Flow name cannot be empty" in str(exc_info.value)

    def test_empty_flow_array(self):
        """Test validation fails for empty flow array."""
        flow = AuthoringFlow(
            flow_name="test-flow", description="Test", global_config={}, flow=[], flow_source=FlowSource.CLI
        )

        with pytest.raises(FlowInvalidDataException) as exc_info:
            flow.validate()

        assert "must contain at least one operator" in str(exc_info.value)

    def test_duplicate_operator_names(self):
        """Test validation fails for duplicate operator names."""
        flow = AuthoringFlow(
            flow_name="test-flow",
            description="Test",
            global_config={},
            flow=[
                AuthoringOperator(type="ingest_source", name="duplicate", config={}, depends_on=[]),
                AuthoringOperator(type="extract_operator", name="duplicate", config={}, depends_on=[]),
            ],
            flow_source=FlowSource.CLI,
        )

        with pytest.raises(FlowInvalidDataException) as exc_info:
            flow.validate()

        assert "Duplicate operator name" in str(exc_info.value)

    def test_operator_without_name(self):
        """Test validation fails for operator without name."""
        flow = AuthoringFlow(
            flow_name="test-flow",
            description="Test",
            global_config={},
            flow=[
                AuthoringOperator(
                    type="ingest_source",
                    name=None,  # type: ignore
                    config={},
                    depends_on=[],
                )
            ],
            flow_source=FlowSource.CLI,
        )

        with pytest.raises(FlowInvalidDataException) as exc_info:
            flow.validate()

        assert "must have a name" in str(exc_info.value)

    def test_multiple_validation_errors(self):
        """Test that all validation errors are collected."""
        flow = AuthoringFlow(
            flow_name="test-flow",  # Valid name
            description="Test",
            global_config={},
            flow=[
                AuthoringOperator(
                    type="",  # Invalid: empty type
                    name="op1",
                    config={},
                    depends_on=[],
                ),
                AuthoringOperator(
                    type="extract_operator",
                    name="op2",
                    config={},
                    depends_on=["nonexistent"],  # Invalid: nonexistent dependency
                ),
            ],
            flow_source=FlowSource.CLI,
        )

        with pytest.raises(FlowInvalidDataException) as exc_info:
            flow.validate()

        error_msg = str(exc_info.value)
        # Should contain multiple errors
        assert "type cannot be empty" in error_msg
        assert "not found in flow" in error_msg

    def test_flow_source_enum(self):
        """Test FlowSource enum values."""
        assert FlowSource.API == "api"
        assert FlowSource.CLI == "cli"
        assert FlowSource.PROGRAMMATIC == "programmatic"
        assert FlowSource.UI == "ui"

    def test_valid_branch_dependency(self):
        """Test validation passes for valid branch dependency."""
        flow = AuthoringFlow(
            flow_name="test-flow",
            description="Test",
            global_config={},
            flow=[
                AuthoringOperator(
                    type="branching",
                    name="branch_op",
                    config={"branches": {"branch_a": {}, "branch_b": {}}},
                    depends_on=[],
                ),
                AuthoringOperator(
                    type="extract_operator",
                    name="extract",
                    config={},
                    depends_on=["branch_op.branch_a"],  # Branch reference
                ),
            ],
            flow_source=FlowSource.CLI,
        )

        flow.validate()  # Should not raise
