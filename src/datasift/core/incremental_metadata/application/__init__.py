"""
Application layer for incremental metadata management.

This layer contains services that coordinate business logic between
the domain layer and external adapters.
"""

from .services import IncrementalUpdateService

__all__ = [
    "IncrementalUpdateService",
]
