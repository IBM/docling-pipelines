"""Shared fixtures and helpers for flow_validator tests."""

from unittest.mock import Mock

import pytest

from docpipe.core.constants.constants import DocpipeConstants
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.orchestration.flow_validator import FlowValidator


@pytest.fixture
def validator():
    """Return a FlowValidator with a fully mocked orchestrator."""
    mock_orchestrator = Mock()
    mock_orchestrator.common_log_arguments = {}
    mock_orchestrator.flow_engine = Mock()
    mock_orchestrator.custom_operator_packages = None
    mock_orchestrator.enable_custom_operators = False
    return FlowValidator(orchestrator=mock_orchestrator)


def make_validator():
    """Factory function (kept for backwards compat with existing tests that call it directly)."""
    mock_orchestrator = Mock()
    mock_orchestrator.common_log_arguments = {}
    mock_orchestrator.flow_engine = Mock()
    mock_orchestrator.custom_operator_packages = None
    mock_orchestrator.enable_custom_operators = False
    return FlowValidator(orchestrator=mock_orchestrator)


def make_node(node_id, operator, name=None, config=None, output_edges=None):
    """Build a minimal DAG node dictionary."""
    node = {
        "id": node_id,
        OperatorConstants.Misc.OPERATOR: operator,
        OperatorConstants.Misc.NAME: name or f"Node {node_id}",
        "config": config or {},
    }
    if output_edges is not None:
        node[DocpipeConstants.OUTPUT_EDGES] = output_edges
    return node
