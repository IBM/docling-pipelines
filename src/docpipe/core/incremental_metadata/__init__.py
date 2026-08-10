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
    PostgresIncrementalMetadataStore,
    get_default_factory,
    get_incremental_update_service,
    register_incremental_update_store,
    set_default_factory,
)
from .application import IncrementalUpdateService
from .domain import IncrementalMetadataRecord, IncrementalMetadataStore

__all__ = [
    "FilesystemIncrementalMetadataStore",
    "IncrementalMetadataFactory",
    "IncrementalMetadataRecord",
    "IncrementalMetadataStore",
    "IncrementalUpdateService",
    "PostgresIncrementalMetadataStore",
    "get_default_factory",
    "get_incremental_update_service",
    "register_incremental_update_store",
    "set_default_factory",
]
