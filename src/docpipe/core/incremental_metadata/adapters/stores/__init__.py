"""
Storage adapters for incremental metadata.

Importing these modules triggers their @register_incremental_update_store
decorator, which populates IncrementalMetadataFactory._stores.

External backends (e.g. COS in EE) must be imported before
get_incremental_update_service() or get_default_factory() is called so
their decorator fires.  This is the same contract as OperatorSourceFactory.
"""

# Import adapters to trigger decorator registration
from .filesystem import FilesystemIncrementalMetadataStore
from .postgres import PostgresIncrementalMetadataStore

__all__ = [
    "FilesystemIncrementalMetadataStore",
    "PostgresIncrementalMetadataStore",
]
