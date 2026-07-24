"""
Adapters layer for incremental metadata.

Contains storage adapters and configuration factory.
"""

from .config import (
    IncrementalMetadataFactory,
    IncrementalStorageBackend,
    get_default_incremental_factory,
    reset_default_incremental_factory,
)
from .stores import (
    FilesystemIncrementalMetadataStore,
    PostgresIncrementalMetadataStore,
)

__all__ = [
    "FilesystemIncrementalMetadataStore",
    "IncrementalMetadataFactory",
    "IncrementalStorageBackend",
    "PostgresIncrementalMetadataStore",
    "get_default_incremental_factory",
    "reset_default_incremental_factory",
]
