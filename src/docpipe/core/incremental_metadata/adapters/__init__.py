"""
Adapters layer for incremental metadata.

Contains storage adapters and configuration factory.
"""

from .config import (
    IncrementalMetadataFactory,
    create_incremental_metadata_store,
    create_store_from_config_file,
    register_incremental_update_store,
    reset_default_incremental_store,
)
from .stores import (
    FilesystemIncrementalMetadataStore,
    PostgresIncrementalMetadataStore,
)

__all__ = [
    "FilesystemIncrementalMetadataStore",
    "IncrementalMetadataFactory",
    "PostgresIncrementalMetadataStore",
    "create_incremental_metadata_store",
    "create_store_from_config_file",
    "register_incremental_update_store",
    "reset_default_incremental_store",
]
