"""Base Asset model for all asset types in the unified architecture.

This module defines the minimal abstract base class for all assets (Flow, DocumentSet, DocumentLibrary).
Only truly common attributes are included here. Asset-specific attributes are defined in subclasses.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import uuid4

from docpipe.core.constants.asset_constants import AssetType
from docpipe.exceptions.docpipe_exceptions import AssetInvalidDataException


@dataclass
class Asset(ABC):
    """Abstract base class for all asset types.

    This class defines the common attributes shared by ALL assets
    in the system (Flow, DocumentSet, DocumentLibrary).

    Common Attributes:
        asset_id: Unique identifier for the asset
        name: Human-readable name of the asset (required)
        description: Optional description of the asset's purpose

    Note:
        Subclasses must implement:
        - get_asset_type(): Return asset type string
        - from_dict(): Deserialize from dictionary
        - Optionally override validate() and to_dict() for asset-specific logic
    """

    # Core identification - truly common across ALL assets
    asset_id: str | None = None
    name: str = ""
    description: str | None = None

    @abstractmethod
    def get_asset_type(self) -> AssetType:
        """Return the asset type identifier.

        Returns:
            AssetType: Asset type enum value (AssetType.FLOW, AssetType.DOCUMENT_SET, etc.)
        """
        ...

    @staticmethod
    @abstractmethod
    def get_config_key() -> str:
        """Return the YAML config key used to look up this asset's repository config.

        Example: "flow", "documentset", "documentlibrary"

        Returns:
            str: Key used under assets_management.<key>_repository in YAML config
        """
        ...

    @staticmethod
    @abstractmethod
    def get_collection_name() -> str:
        """Return the DuckDB collection (table) name for this asset type.

        Example: "document_sets", "document_libraries"

        Returns:
            str: Collection name used by DuckDBAssetRepository
        """
        ...

    def validate(self) -> None:
        """Validate the asset's data.

        Base validation checks common to all assets. Subclasses should call
        super().validate() first, then add their own validation logic.

        Raises:
            AssetInvalidDataException: If validation fails
        """
        if not self.name or not self.name.strip():
            raise AssetInvalidDataException(f"{self.get_asset_type()} name cannot be empty")

        if len(self.name) > 255:
            raise AssetInvalidDataException(f"{self.get_asset_type()} name cannot exceed 255 characters")

        if self.description and len(self.description) > 2000:
            raise AssetInvalidDataException(f"{self.get_asset_type()} description cannot exceed 2000 characters")

    def __post_init__(self) -> None:
        """Generate asset_id if not provided."""
        if self.asset_id is None:
            self.asset_id = str(uuid4())

    @abstractmethod
    def update_timestamp(self) -> None:
        """Update the asset's last-modified timestamp.

        Subclasses must implement this to refresh whatever timestamp field
        they expose (e.g. ``modified_on`` on Flow, ``updated_at`` on DocumentSet).
        """
        ...

    def get_created_at(self) -> datetime | None:
        """Return the creation timestamp for this asset, if available.

        Default implementation returns None (e.g. DocumentLibrary has no
        creation timestamp). Subclasses that track creation time override this:
        - DocumentSet overrides to return self.created_at
        - Flow overrides to return self.created_on

        The generic repository uses this method for sorting, so it never
        needs to know the concrete timestamp field name.
        """
        return None

    def get_updated_at(self) -> datetime | None:
        """Return the last-modified timestamp for this asset, if available.

        Default implementation returns None (e.g. DocumentLibrary has no
        update timestamp). Subclasses that track modification time override this:
        - DocumentSet overrides to return self.updated_at
        - Flow overrides to return self.modified_on

        The generic repository uses this method for sorting, so it never
        needs to know the concrete timestamp field name.
        """
        return None

    def to_dict(self) -> dict[str, Any]:
        """Serialize asset to dictionary.

        Base implementation includes only common fields. Subclasses should
        override this method to include their specific fields.

        Returns:
            dict: Dictionary representation of the asset
        """
        return {
            "asset_id": self.asset_id,
            "asset_type": self.get_asset_type(),
            "name": self.name,
            "description": self.description,
        }

    @classmethod
    @abstractmethod
    def from_dict(cls, *, data: dict[str, Any]) -> "Asset":
        """Deserialize asset from dictionary.

        Args:
            data: Dictionary representation of the asset

        Returns:
            Asset instance

        Note:
            Each concrete asset class must implement this method to handle
            both common Asset fields and their specific fields.
        """
        ...

    def __str__(self) -> str:
        """String representation of the asset."""
        return f"{self.get_asset_type()}(id={self.asset_id}, name={self.name})"

    def __repr__(self) -> str:
        """Developer-friendly representation of the asset."""
        return f"{self.__class__.__name__}(asset_id={self.asset_id!r}, name={self.name!r})"
