"""
Incremental metadata module for tracking document processing state.

This module provides a complete hexagonal architecture implementation for
managing incremental processing metadata, decoupled from job management.

Supports multiple storage backends:
- Filesystem: Efficient columnar storage (default)
- PostgreSQL: Production-grade database storage
"""

from .adapters import (
    FilesystemIncrementalMetadataStore,
    IncrementalMetadataFactory,
    IncrementalStorageBackend,
    PostgresIncrementalMetadataStore,
    get_default_incremental_factory,
    reset_default_incremental_factory,
)
from .application import IncrementalUpdateService
from .domain import IncrementalMetadataRecord, IncrementalMetadataStore

__all__ = [
    "FilesystemIncrementalMetadataStore",
    "IncrementalMetadataFactory",
    "IncrementalMetadataRecord",
    "IncrementalMetadataStore",
    "IncrementalStorageBackend",
    "IncrementalUpdateService",
    "PostgresIncrementalMetadataStore",
    "get_default_incremental_factory",
    "reset_default_incremental_factory",
]
