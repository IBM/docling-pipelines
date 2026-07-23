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
    create_incremental_metadata_store,
    create_store_from_config_file,
    register_incremental_update_store,
    reset_default_incremental_store,
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
    "create_incremental_metadata_store",
    "create_store_from_config_file",
    "register_incremental_update_store",
    "reset_default_incremental_store",
]
