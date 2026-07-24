"""
Domain utilities for job management.

This module contains utility functions that operate on domain models
but don't belong to any specific model class.
"""

from .normalization import normalize_node_stats_for_dto

__all__ = ["normalize_node_stats_for_dto"]
