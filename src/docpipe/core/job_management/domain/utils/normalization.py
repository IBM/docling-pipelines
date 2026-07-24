"""
Normalization utilities for job management domain models.

This module contains functions for normalizing and transforming data
to ensure compatibility across different storage formats and versions.
"""

from docpipe.core.constants import DocpipeConstants, OperatorConstants


def normalize_node_stats_for_dto(*, job_stats_data: dict) -> dict:  # NOSONAR python:S3516
    """
    Normalize node_stats data by ensuring each node has 'node_id' field.
    This is needed for backward compatibility with old logs that use 'id' instead of 'node_id'.
    New job runs already write the correct format, so this only processes old data.

    Args:
        job_stats_data: Dictionary containing job stats with node_stats

    Returns:
        The same dictionary with normalized node_stats (Pydantic handles conversion to NodeStats)
    """
    if DocpipeConstants.NODE_STATS in job_stats_data and isinstance(job_stats_data[DocpipeConstants.NODE_STATS], dict):
        node_stats = job_stats_data[DocpipeConstants.NODE_STATS]
        # Quick check: if first node already has 'node_id', assume all nodes are in new format
        if node_stats:
            first_node = next(iter(node_stats.values()), None)
            if isinstance(first_node, dict) and DocpipeConstants.NODE_ID in first_node:
                # Already in new format, no normalization needed
                return job_stats_data

        # Old format detected, normalize all nodes
        for node_data in node_stats.values():
            if (
                isinstance(node_data, dict)
                and OperatorConstants.Misc.ID in node_data
                and DocpipeConstants.NODE_ID not in node_data
            ):
                node_data[DocpipeConstants.NODE_ID] = node_data[OperatorConstants.Misc.ID]
    return job_stats_data
