"""
Domain layer for incremental metadata.

Contains domain models and port interfaces.
"""

from .models import IncrementalMetadataRecord
from .ports import IncrementalMetadataStore

__all__ = [
    "IncrementalMetadataRecord",
    "IncrementalMetadataStore",
]
