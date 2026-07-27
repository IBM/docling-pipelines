"""
Adapters layer for incremental metadata.

Contains storage adapters and configuration factory.
"""

from .config import (
    IncrementalMetadataFactory,
    get_default_factory,
    get_incremental_update_service,
    register_incremental_update_store,
)
from .stores import (
    FilesystemIncrementalMetadataStore,
    PostgresIncrementalMetadataStore,
)

__all__ = [
    "FilesystemIncrementalMetadataStore",
    "IncrementalMetadataFactory",
    "PostgresIncrementalMetadataStore",
    "get_default_factory",
    "get_incremental_update_service",
    "register_incremental_update_store",
]
