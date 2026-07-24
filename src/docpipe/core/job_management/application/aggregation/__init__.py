"""
Core job management aggregation primitives.

This package owns batch/node aggregation behavior for the
hexagonal job statistics architecture.
"""

from .aggregator import MetadataAggregator
from .batch_aggregator import aggregate_batch_node_stats
from .strategies import AggregationStrategy

__all__ = [
    "AggregationStrategy",
    "MetadataAggregator",
    "aggregate_batch_node_stats",
]
