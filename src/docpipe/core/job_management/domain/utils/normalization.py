"""
Normalization utilities for job management domain models.

This module contains functions for normalizing and transforming data
to ensure compatibility across different storage formats and versions.
"""

from docpipe.core.constants import DocpipeConstants, OperatorConstants


def normalize_node_stats_for_dto(*, job_stats_data: dict) -> dict:
    """
    Normalize node_stats data by ensuring each node has 'node_id' field.
    This is needed for backward compatibility with old logs that use 'id' instead of 'node_id'.
    New job runs already write the correct format, so this only processes old data.

    Modifies the dictionary in-place and returns it.

    Args:
        job_stats_data: Dictionary containing job stats with node_stats to be normalized in-place

    Returns:
        The same job_stats_data dict (modified in-place)
    """
    # Early return if node_stats is missing or not a dict
    if DocpipeConstants.NODE_STATS not in job_stats_data:
        return job_stats_data

    node_stats = job_stats_data[DocpipeConstants.NODE_STATS]
    if not isinstance(node_stats, dict):
        return job_stats_data

    # Early return if already in new format
    if node_stats:
        first_node = next(iter(node_stats.values()), None)
        if isinstance(first_node, dict) and DocpipeConstants.NODE_ID in first_node:
            return job_stats_data

    # Normalize old format: add 'node_id' field from 'id' field
    for node_data in node_stats.values():
        if (
            isinstance(node_data, dict)
            and OperatorConstants.Misc.ID in node_data
            and DocpipeConstants.NODE_ID not in node_data
        ):
            node_data[DocpipeConstants.NODE_ID] = node_data[OperatorConstants.Misc.ID]

    return job_stats_data
