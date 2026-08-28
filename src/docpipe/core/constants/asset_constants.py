"""Constants for asset management in the unified architecture.

This module defines enums and constants used across all asset types
(Flow, DocumentSet, DocumentLibrary) in the system.
"""

from enum import StrEnum


class AssetType(StrEnum):
    """Enum for asset types in the system.

    This enum defines all supported asset types in the unified architecture.
    Each asset type corresponds to a concrete Asset subclass:
    - FLOW: Flow assets (workflow definitions)
    - DOCUMENT_SET: DocumentSet assets (collections of documents)
    - DOCUMENT_LIBRARY: DocumentLibrary assets (curated document collections)
    """

    FLOW = "flow"
    DOCUMENT_SET = "document_set"
    DOCUMENT_LIBRARY = "document_library"
