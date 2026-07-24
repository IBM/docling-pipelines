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
        op = AuthoringOperator(type="ingest_local", name="ingest_docs", config={"paths": "./data"}, depends_on=[])

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
        op = AuthoringOperator(type="ingest_local", name="test op", config={}, depends_on=[])

        errors = op.validate(all_operator_names={"test op"}, operator_map={"test op": op})

        assert len(errors) == 1
        assert "cannot contain spaces" in errors[0]

    def test_operator_name_with_branch_separator(self):
        """Test validation fails for operator name with branch separator."""
        op = AuthoringOperator(type="ingest_local", name="test.op", config={}, depends_on=[])

        errors = op.validate(all_operator_names={"test.op"}, operator_map={"test.op": op})

        assert len(errors) == 1
        assert "cannot contain '.'" in errors[0]

    def test_invalid_config_type(self):
        """Test validation fails for non-dict config."""
        op = AuthoringOperator(
            type="ingest_local",
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
                AuthoringOperator(type="ingest_local", name="ingest", config={"paths": "./data"}, depends_on=[]),
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
            flow=[AuthoringOperator(type="ingest_local", name="ingest", config={}, depends_on=[])],
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
                AuthoringOperator(type="ingest_local", name="duplicate", config={}, depends_on=[]),
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
                    type="ingest_local",
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


# ---------------------------------------------------------------------------
# Additional tests for missing coverage lines
# ---------------------------------------------------------------------------


class TestAuthoringOperatorEdgeCases:
    """Test edge cases in AuthoringOperator.validate()."""

    def test_operator_name_empty_whitespace(self):
        """Operator name that is only whitespace triggers error."""
        op = AuthoringOperator(type="ingest_local", name="   ", config={}, depends_on=[])
        errors = op.validate(all_operator_names={"   "}, operator_map={})
        assert any("cannot be empty" in e for e in errors)

    def test_empty_dependency_string(self):
        """Empty string in depends_on triggers error."""
        op = AuthoringOperator(type="ingest_local", name="op1", config={}, depends_on=[""])
        errors = op.validate(all_operator_names={"op1"}, operator_map={"op1": op})
        assert any("Empty dependency" in e for e in errors)

    def test_branch_reference_invalid_format(self):
        """Branch reference with multiple separators raises error."""
        op = AuthoringOperator(type="extract", name="op2", config={}, depends_on=["branch_op.branch_a"])
        # operator_name not in all_operator_names
        errors = op.validate(all_operator_names={"op2"}, operator_map={"op2": op})
        assert any("not found in flow" in e for e in errors)

    def test_branch_reference_empty_branch_name(self):
        """Branch reference with empty branch name (op.) triggers error."""
        from docpipe.core.constants.operator_constants import OperatorConstants

        op = AuthoringOperator(type="extract", name="op2", config={}, depends_on=["branch_op."])
        branch_op = AuthoringOperator(
            type=OperatorConstants.Operators.BRANCHING,
            name="branch_op",
            config={"branches": {"branch_a": {}}},
            depends_on=[],
        )
        errors = op.validate(
            all_operator_names={"op2", "branch_op"},
            operator_map={"op2": op, "branch_op": branch_op},
        )
        assert any("empty" in e.lower() for e in errors)

    def test_branch_reference_op_is_not_branching(self):
        """Referencing a non-branching operator as branch triggers error."""
        not_branch_op = AuthoringOperator(type="ingest_local", name="ingest", config={}, depends_on=[])
        op = AuthoringOperator(type="extract", name="op2", config={}, depends_on=["ingest.branch_a"])
        errors = op.validate(
            all_operator_names={"op2", "ingest"},
            operator_map={"op2": op, "ingest": not_branch_op},
        )
        assert any("not a branching operator" in e for e in errors)

    def test_branch_not_in_branching_op(self):
        """Referencing non-existent branch in branching operator triggers error."""
        from docpipe.core.constants.operator_constants import OperatorConstants

        branch_op = AuthoringOperator(
            type=OperatorConstants.Operators.BRANCHING,
            name="branch_op",
            config={"branches": {"branch_a": {}}},
            depends_on=[],
        )
        op = AuthoringOperator(type="extract", name="op2", config={}, depends_on=["branch_op.nonexistent_branch"])
        errors = op.validate(
            all_operator_names={"op2", "branch_op"},
            operator_map={"op2": op, "branch_op": branch_op},
        )
        assert any("not found in branching operator" in e for e in errors)

    def test_branching_operator_with_invalid_branches_type(self):
        """Branching operator with non-dict 'branches' config triggers error."""
        from docpipe.core.constants.operator_constants import OperatorConstants

        op = AuthoringOperator(
            type=OperatorConstants.Operators.BRANCHING,
            name="branch_op",
            config={"branches": "invalid"},
            depends_on=[],
        )
        errors = op.validate(all_operator_names={"branch_op"}, operator_map={"branch_op": op})
        assert any("must have" in e and "dictionary" in e for e in errors)

    def test_branching_operator_with_empty_branches(self):
        """Branching operator with empty 'branches' dict triggers error."""
        from docpipe.core.constants.operator_constants import OperatorConstants

        op = AuthoringOperator(
            type=OperatorConstants.Operators.BRANCHING,
            name="branch_op",
            config={"branches": {}},
            depends_on=[],
        )
        errors = op.validate(all_operator_names={"branch_op"}, operator_map={"branch_op": op})
        assert any("at least one branch" in e for e in errors)

    def test_branch_name_with_spaces(self):
        """Branch name with spaces triggers error."""
        from docpipe.core.constants.operator_constants import OperatorConstants

        op = AuthoringOperator(
            type=OperatorConstants.Operators.BRANCHING,
            name="branch_op",
            config={"branches": {"bad branch": {}}},
            depends_on=[],
        )
        errors = op.validate(all_operator_names={"branch_op"}, operator_map={"branch_op": op})
        assert any("cannot contain spaces" in e for e in errors)

    def test_branch_name_empty(self):
        """Branch name that is whitespace triggers error."""
        from docpipe.core.constants.operator_constants import OperatorConstants

        op = AuthoringOperator(
            type=OperatorConstants.Operators.BRANCHING,
            name="branch_op",
            config={"branches": {"  ": {}}},
            depends_on=[],
        )
        errors = op.validate(all_operator_names={"branch_op"}, operator_map={"branch_op": op})
        assert any("cannot be empty" in e for e in errors)

    def test_branch_name_with_separator(self):
        """Branch name with dot separator triggers error."""
        from docpipe.core.constants.operator_constants import OperatorConstants

        op = AuthoringOperator(
            type=OperatorConstants.Operators.BRANCHING,
            name="branch_op",
            config={"branches": {"bad.branch": {}}},
            depends_on=[],
        )
        errors = op.validate(all_operator_names={"branch_op"}, operator_map={"branch_op": op})
        assert any("cannot contain" in e for e in errors)

    def test_merge_operator_single_input_fails(self):
        """Merge operator with only 1 depends_on triggers error."""
        from docpipe.core.constants.operator_constants import OperatorConstants

        op = AuthoringOperator(
            type=OperatorConstants.Operators.MERGE,
            name="merge_op",
            config={},
            depends_on=["op1"],
        )
        errors = op.validate(all_operator_names={"merge_op", "op1"}, operator_map={})
        assert any("at least 2 inputs" in e for e in errors)


class TestAuthoringFlowEdgeCases:
    """Test edge cases in AuthoringFlow.validate()."""

    def test_flow_name_too_long_raises(self):
        """Flow name > 255 characters raises FlowInvalidDataException."""
        flow = AuthoringFlow(
            flow_name="a" * 256,
            flow=[AuthoringOperator(type="noop", name="op1", config={}, depends_on=[])],
            flow_source=FlowSource.CLI,
        )
        with pytest.raises(FlowInvalidDataException) as exc_info:
            flow.validate()
        assert "255" in str(exc_info.value)

    def test_description_too_long_raises(self):
        """Description > 2000 characters raises FlowInvalidDataException."""
        flow = AuthoringFlow(
            flow_name="test",
            description="a" * 2001,
            flow=[AuthoringOperator(type="noop", name="op1", config={}, depends_on=[])],
            flow_source=FlowSource.CLI,
        )
        with pytest.raises(FlowInvalidDataException) as exc_info:
            flow.validate()
        assert "2000" in str(exc_info.value)

    def test_non_bool_disable_validation_raises(self):
        """Non-bool disable_validation in global_config raises FlowInvalidDataException."""
        from docpipe.core.constants.operator_constants import OperatorConstants

        flow = AuthoringFlow(
            flow_name="test",
            global_config={OperatorConstants.Config.DISABLE_VALIDATION: "yes"},
            flow=[AuthoringOperator(type="noop", name="op1", config={}, depends_on=[])],
            flow_source=FlowSource.CLI,
        )
        with pytest.raises(FlowInvalidDataException) as exc_info:
            flow.validate()
        assert "disable_validation" in str(exc_info.value)

    def test_self_dependency_raises(self):
        """Operator depending on itself raises FlowInvalidDataException."""
        op = AuthoringOperator(type="extract", name="op1", config={}, depends_on=["op1"])
        flow = AuthoringFlow(
            flow_name="test",
            flow=[op],
            flow_source=FlowSource.CLI,
        )
        with pytest.raises(FlowInvalidDataException) as exc_info:
            flow.validate()
        assert "itself" in str(exc_info.value)

    def test_get_operator_by_name_found(self):
        """get_operator_by_name returns the operator when found."""
        op = AuthoringOperator(type="noop", name="my_op", config={}, depends_on=[])
        flow = AuthoringFlow(flow_name="test", flow=[op], flow_source=FlowSource.CLI)
        result = flow.get_operator_by_name(name="my_op")
        assert result is op

    def test_get_operator_by_name_not_found_returns_none(self):
        """get_operator_by_name returns None when operator not found."""
        op = AuthoringOperator(type="noop", name="my_op", config={}, depends_on=[])
        flow = AuthoringFlow(flow_name="test", flow=[op], flow_source=FlowSource.CLI)
        result = flow.get_operator_by_name(name="nonexistent")
        assert result is None

    def test_to_dict(self):
        """to_dict returns a dict representation."""
        op = AuthoringOperator(type="noop", name="op1", config={}, depends_on=[])
        flow = AuthoringFlow(
            flow_name="My Flow",
            description="desc",
            flow=[op],
            flow_source=FlowSource.CLI,
        )
        d = flow.to_dict()
        assert isinstance(d, dict)
        assert "My Flow" in str(d)
