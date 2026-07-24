"""
Domain ports (interfaces) for incremental metadata.

Exports port interfaces following hexagonal architecture pattern.
"""

from .incremental_metadata_store import IncrementalMetadataStore

__all__ = [
    "IncrementalMetadataStore",
]
