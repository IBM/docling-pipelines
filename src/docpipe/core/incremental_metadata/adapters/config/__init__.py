"""
Configuration and factory for incremental metadata.
"""

from .incremental_metadata_factory import (
    IncrementalMetadataFactory,
    get_default_factory,
    get_incremental_update_service,
    register_incremental_update_store,
    set_default_factory,
)

__all__ = [
    "IncrementalMetadataFactory",
    "get_default_factory",
    "get_incremental_update_service",
    "register_incremental_update_store",
    "set_default_factory",
]
