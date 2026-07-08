"""
DAG Utility Functions

Shared utilities for working with DAG (Directed Acyclic Graph) nodes.
"""

from typing import Any

from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger()


def identify_ingest_and_destination_nodes(dag_nodes: list[dict[str, Any]]) -> tuple[str | None, list[str]]:
    """
    Identify ingest node (no input edges) and destination nodes (no output edges).

    This is a shared utility used by both JobTrackerService and JobReportGenerator
    to consistently identify special nodes in the DAG.

    Args:
        dag_nodes: List of DAG node dictionaries

    Returns:
        Tuple of (ingest_node_id, destination_node_ids)
    """
    ingest_node_id = None
    destination_node_ids = []

    for node in dag_nodes:
        node_id = node.get(OperatorConstants.Misc.ID)
        if not node_id:
            continue

        # Ingest node: has no input edges
        if not node.get("input_edges"):
            ingest_node_id = node_id
            logger.debug(f"Identified ingest node: {node_id}")

        # Destination nodes: have no output edges
        if not node.get("output_edges"):
            destination_node_ids.append(node_id)

    if destination_node_ids:
        logger.debug(f"Identified {len(destination_node_ids)} destination nodes: {destination_node_ids}")
    else:
        logger.warning("No destination nodes found in DAG")

    return ingest_node_id, destination_node_ids
