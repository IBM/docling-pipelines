"""Port interfaces for document set domain.

This module exports the abstract port interfaces that define the contracts
for external adapters in the hexagonal architecture.
"""

from .data_store import DocumentSetDataStore
from .metadata_repository import DocumentSetMetadataRepository

__all__ = ["DocumentSetDataStore", "DocumentSetMetadataRepository"]
