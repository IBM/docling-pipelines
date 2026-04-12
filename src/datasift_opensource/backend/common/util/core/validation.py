"""Validation utility functions."""

from datetime import datetime
from typing import Any
from uuid import UUID


def to_bool(value: Any) -> bool:
    """
    Return True only for the boolean True or for strings equal to 'true' after trimming surrounding whitespace and lowercasing.
    Returns False for all other inputs (including 'false', '1', 1, objects, None, etc.).

    Args:
        value: Value to convert to boolean

    Returns:
        True if value is boolean True or string "true" (case-insensitive), False otherwise
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() == "true":
        return True
    return False


def is_value_in_range(*, value: int | float, min_value: int | float, max_value: int | float) -> bool:
    """
    Check if a value is within the specified range (inclusive).

    Args:
        value: The value to check.
        min_value: The minimum value of the range (inclusive).
        max_value: The maximum value of the range (inclusive).

    Returns:
        bool: True if value is within [min_value, max_value], False otherwise.
    """
    return min_value <= value <= max_value


def is_date_time_as_per_format(date_time_str: str, date_time_format: str):
    """
    Check if a date string matches the specified format.

    Args:
        date_time_str: Input date in string format.
        date_time_format: date_time format which the input date_time string should follow.

    Returns:
        True - If the input date is a valid date and is as per the date_time_format
        False - If the input date is not a valid date or is not as per the date_time_format
    """
    try:
        datetime.strptime(date_time_str, date_time_format)
        return True
    except ValueError:
        return False


def validate_uuid_format(value: str | None, field_name: str) -> str | None:
    """Validate that a string is in valid UUID format.

    Used across the application to validate UUID fields like flow_id, container_id,
    and other identifier fields that must conform to UUID standards.

    Args:
        value: The string value to validate (can be None for optional fields)
        field_name: Name of the field being validated (used in error messages)

    Returns:
        The validated UUID string unchanged, or None if input was None

    Raises:
        ValueError: If the value is not a valid UUID format, with a descriptive
            error message including the field name and an example UUID

    Examples:
        >>> validate_uuid_format("550e8400-e29b-41d4-a716-446655440000", "flow_id")
        '550e8400-e29b-41d4-a716-446655440000'
        >>> validate_uuid_format(None, "flow_id")
        None
        >>> validate_uuid_format("invalid", "flow_id")
        ValueError: flow_id must be a valid UUID format, got 'invalid'...
    """
    if value is None:
        return None
    try:
        UUID(value)
        return value
    except (ValueError, AttributeError, TypeError) as e:
        raise ValueError(
            f"{field_name} must be a valid UUID format, got '{value}'. Example: '550e8400-e29b-41d4-a716-446655440000'"
        ) from e


def validate_container_kind(value: str | None) -> str | None:
    """Validate that container_kind is either 'project' or 'space'.

    Used to validate IBM Cloud container type fields. Ensures only valid
    container types are accepted for flow metadata.

    Args:
        value: The container kind value to validate (can be None for optional fields)

    Returns:
        The validated container kind unchanged, or None if input was None

    Raises:
        ValueError: If the value is not 'project' or 'space', with a descriptive
            error message explaining valid options

    Examples:
        >>> validate_container_kind("project")
        'project'
        >>> validate_container_kind("space")
        'space'
        >>> validate_container_kind(None)
        None
        >>> validate_container_kind("invalid")
        ValueError: container_kind must be 'project' or 'space', got 'invalid'...
    """
    if value is None:
        return None
    if value not in ["project", "space"]:
        raise ValueError(
            f"container_kind must be 'project' or 'space', got '{value}'. "
            "Provide a valid container type or omit this field."
        )
    return value


def _validate_operator_type_format(operator_type: str) -> None:
    """Validate operator_type is a valid Python class path format.

    Args:
        operator_type: The operator type string to validate

    Raises:
        ValueError: If operator_type format is invalid
    """
    if not operator_type or not isinstance(operator_type, str):
        raise ValueError("operator_type must be a non-empty string")

    # Check for valid Python identifier format (module.path.ClassName or simple_name)
    parts = operator_type.split(".")
    for part in parts:
        if not part or not (part[0].isalpha() or part[0] == "_"):
            raise ValueError(
                f"operator_type '{operator_type}' contains invalid identifier '{part}'. "
                "Must be valid Python class path (e.g., 'ingest_local' or 'core.operators.IngestLocal')"
            )


def _validate_dag_nodes(nodes: list[dict[str, Any]]) -> None:
    """Validate DAG nodes structure.

    Args:
        nodes: List of node dictionaries to validate

    Raises:
        ValueError: If nodes structure is invalid
    """
    if not isinstance(nodes, list):
        raise ValueError(f"nodes must be a list, got {type(nodes).__name__}")

    if not nodes:
        raise ValueError("nodes list cannot be empty - at least one node is required")

    node_ids = set()
    for idx, node in enumerate(nodes):
        if not isinstance(node, dict):
            raise ValueError(f"node at index {idx} must be a dictionary, got {type(node).__name__}")

        # Validate required fields
        if "id" not in node:
            raise ValueError(f"node at index {idx} is missing required field 'id'")

        node_id = node["id"]
        if not isinstance(node_id, str) or not node_id:
            raise ValueError(f"node at index {idx} has invalid 'id': must be a non-empty string")

        # Check for duplicate IDs
        if node_id in node_ids:
            raise ValueError(f"duplicate node id '{node_id}' found at index {idx}")
        node_ids.add(node_id)

        # Validate operator field (can be 'operator' or 'operator_type')
        operator_field = node.get("operator") or node.get("operator_type")
        if not operator_field:
            raise ValueError(f"node '{node_id}' at index {idx} is missing required field 'operator' or 'operator_type'")

        _validate_operator_type_format(operator_field)

        # Validate operator_params/config if present
        params = node.get("operator_params") or node.get("config")
        if params is not None and not isinstance(params, dict):
            raise ValueError(f"node '{node_id}' has invalid 'operator_params'/'config': must be a dictionary")


def _validate_dag_edges(edges: list[dict[str, Any]], node_ids: set[str]) -> None:
    """Validate DAG edges structure and references.

    Args:
        edges: List of edge dictionaries to validate
        node_ids: Set of valid node IDs for reference checking

    Raises:
        ValueError: If edges structure is invalid or references non-existent nodes
    """
    if not isinstance(edges, list):
        raise ValueError(f"edges must be a list, got {type(edges).__name__}")

    for idx, edge in enumerate(edges):
        if not isinstance(edge, dict):
            raise ValueError(f"edge at index {idx} must be a dictionary, got {type(edge).__name__}")

        # Validate required fields
        if "source" not in edge:
            raise ValueError(f"edge at index {idx} is missing required field 'source'")
        if "target" not in edge:
            raise ValueError(f"edge at index {idx} is missing required field 'target'")

        source = edge["source"]
        target = edge["target"]

        if not isinstance(source, str) or not source:
            raise ValueError(f"edge at index {idx} has invalid 'source': must be a non-empty string")
        if not isinstance(target, str) or not target:
            raise ValueError(f"edge at index {idx} has invalid 'target': must be a non-empty string")

        # Validate references
        if source not in node_ids:
            raise ValueError(f"edge at index {idx} references non-existent source node '{source}'")
        if target not in node_ids:
            raise ValueError(f"edge at index {idx} references non-existent target node '{target}'")

        # Check for self-referencing edges
        if source == target:
            raise ValueError(f"edge at index {idx} is self-referencing (source == target == '{source}')")


def _detect_cycles_in_dag(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> None:
    """Detect cycles in the DAG using depth-first search.

    Args:
        nodes: List of node dictionaries
        edges: List of edge dictionaries

    Raises:
        ValueError: If a cycle is detected in the DAG
    """
    # Build adjacency list
    graph: dict[str, list[str]] = {node["id"]: [] for node in nodes}
    for edge in edges:
        graph[edge["source"]].append(edge["target"])

    # DFS-based cycle detection
    white, gray, black = 0, 1, 2
    color = dict.fromkeys(graph, white)

    def dfs(node_id: str, path: list[str]) -> bool:
        """DFS helper that returns True if cycle detected."""
        if color[node_id] == gray:
            # Found a back edge - cycle detected
            cycle_start = path.index(node_id)
            cycle_path = " -> ".join([*path[cycle_start:], node_id])
            raise ValueError(f"cycle detected in DAG: {cycle_path}")

        if color[node_id] == black:
            return False

        color[node_id] = gray
        path.append(node_id)

        for neighbor in graph[node_id]:
            dfs(neighbor, path)

        path.pop()
        color[node_id] = black
        return False

    for node_id in graph:
        if color[node_id] == white:
            dfs(node_id, [])


def _validate_dag_format(value: dict[str, Any]) -> None:
    """Validate modern DAG format structure.

    Args:
        value: The flow definition dictionary to validate

    Raises:
        ValueError: If DAG format is invalid
    """
    # Validate nodes
    if "nodes" not in value:
        raise ValueError("DAG format definition must contain 'nodes' key. Example: {'nodes': [...], 'edges': [...]}")

    nodes = value["nodes"]
    _validate_dag_nodes(nodes)

    # Collect node IDs for edge validation
    node_ids = {node["id"] for node in nodes}

    # Validate edges if present
    edges = value.get("edges", [])
    _validate_dag_edges(edges, node_ids)

    # Detect cycles
    if edges:
        _detect_cycles_in_dag(nodes, edges)


def _validate_elyra_format(value: dict[str, Any]) -> None:
    """Validate legacy Elyra pipeline format structure.

    Args:
        value: The flow definition dictionary to validate

    Raises:
        ValueError: If Elyra format is invalid
    """
    # Validate required Elyra fields
    if "pipelines" not in value:
        raise ValueError(
            "Elyra format definition must contain 'pipelines' key. "
            "Example: {'doc_type': 'pipeline', 'pipelines': [...], 'primary_pipeline': '...'}"
        )

    pipelines = value["pipelines"]
    if not isinstance(pipelines, list):
        raise ValueError(f"pipelines must be a list, got {type(pipelines).__name__}")

    if not pipelines:
        raise ValueError("pipelines list cannot be empty")

    # Validate primary_pipeline if present
    if "primary_pipeline" in value:
        primary = value["primary_pipeline"]
        if not isinstance(primary, str) or not primary:
            raise ValueError("primary_pipeline must be a non-empty string")


def validate_flow_definition(value: dict[str, Any] | None) -> dict[str, Any] | None:
    """Validate flow definition structure with comprehensive structural validation.

    Performs deep validation of flow definitions used throughout the datasift-opensource
    framework. This is a shared validator used by Flow domain models, DTOs, and API
    endpoints to ensure consistent validation across all layers.

    Validation includes:
    - Required top-level keys (nodes/edges for DAG, doc_type/pipelines for Elyra)
    - Node structure validation (id, operator/operator_type, operator_params/config)
    - Edge structure validation (source, target) with reference checking
    - Cycle detection in DAG using depth-first search
    - Operator type format validation (Python class path format)
    - Duplicate node ID detection

    Supported Formats:
    - Modern DAG format: {"nodes": [...], "edges": [...]}
    - Legacy Elyra format: {"doc_type": "pipeline", "pipelines": [...], "primary_pipeline": "..."}

    Args:
        value: The flow definition dictionary to validate (can be None for optional fields)

    Returns:
        The validated definition dictionary unchanged, or None if input was None

    Raises:
        ValueError: If the definition structure is invalid, with specific error messages for:
            - Missing required keys (nodes, edges, doc_type, pipelines)
            - Invalid node structure (missing id, operator, invalid types)
            - Invalid edge references (non-existent nodes, self-references)
            - Circular dependencies in the DAG
            - Invalid operator type format
            - Duplicate node IDs

    Examples:
        >>> validate_flow_definition({"nodes": [{"id": "n1", "operator": "ingest"}], "edges": []})
        {'nodes': [{'id': 'n1', 'operator': 'ingest'}], 'edges': []}
        >>> validate_flow_definition({"doc_type": "pipeline", "pipelines": [...]})
        {'doc_type': 'pipeline', 'pipelines': [...]}
        >>> validate_flow_definition(None)
        None
        >>> validate_flow_definition({})
        ValueError: definition must contain either 'doc_type' (Elyra format) or 'nodes' (DAG format)
    """
    if value is None:
        return None

    if not isinstance(value, dict):
        raise ValueError(f"definition must be a dictionary, got {type(value).__name__}")

    # Determine format and validate accordingly
    has_nodes = "nodes" in value
    has_doc_type = "doc_type" in value

    if not has_nodes and not has_doc_type:
        raise ValueError(
            "definition must contain either 'doc_type' (Elyra format) or 'nodes' (DAG format). "
            "Examples:\n"
            "  DAG: {'nodes': [...], 'edges': [...]}\n"
            "  Elyra: {'doc_type': 'pipeline', 'pipelines': [...]}"
        )

    if has_nodes:
        _validate_dag_format(value)
    elif has_doc_type:
        _validate_elyra_format(value)

    return value


def deduplicate_tags(value: list[str] | None, allow_none: bool = False) -> list[str] | None:
    """Remove duplicate tags while preserving insertion order.

    Used across the application to normalize tag lists in flow metadata and other
    tagged resources. Ensures tag uniqueness while maintaining the order in which
    tags were first encountered.

    Args:
        value: List of tags to deduplicate (can be None for optional fields)
        allow_none: If True, returns None when input is None. If False, returns empty list.
            Default is False for backward compatibility.

    Returns:
        Deduplicated list of tags preserving first occurrence order, or None/empty list
        based on allow_none parameter

    Raises:
        ValueError: If value is not a list or contains non-string elements, with
            descriptive error messages

    Examples:
        >>> deduplicate_tags(["a", "b", "a", "c"])
        ['a', 'b', 'c']
        >>> deduplicate_tags(None, allow_none=False)
        []
        >>> deduplicate_tags(None, allow_none=True)
        None
        >>> deduplicate_tags(["tag1", 123])
        ValueError: all tags must be strings, got int
    """
    if value is None:
        return None if allow_none else []

    if not isinstance(value, list):
        raise ValueError(f"tags must be a list, got {type(value).__name__}")

    seen = set()
    result = []
    for tag in value:
        if not isinstance(tag, str):
            raise ValueError(f"all tags must be strings, got {type(tag).__name__}")
        if tag not in seen:
            seen.add(tag)
            result.append(tag)
    return result
