"""
Domain models for job management.

Exports domain models for job and node statistics.
"""

from .job_stats import JobStats
from .node_stats import NodeMetadataItem, NodeStats, NodeStatsFields

# Rebuild JobStats to resolve forward references to NodeStats
JobStats.model_rebuild()

__all__ = [
    "JobStats",
    "NodeMetadataItem",
    "NodeStats",
    "NodeStatsFields",
]
