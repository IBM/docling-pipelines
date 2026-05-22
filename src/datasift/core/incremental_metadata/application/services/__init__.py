"""
Application services for incremental metadata management.

This module provides high-level business logic for managing incremental
processing metadata, coordinating between domain models and storage adapters.
"""

from .incremental_update_service import IncrementalUpdateService

__all__ = [
    "IncrementalUpdateService",
]
