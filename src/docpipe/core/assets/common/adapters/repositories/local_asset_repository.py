"""Generic LocalAssetRepository for filesystem-based asset storage.

This implementation provides a unified AssetRepository[T] interface for
storing assets as JSON files in the local filesystem.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, TypeVar

from docpipe.core.assets.common.domain.models.asset import Asset
from docpipe.core.assets.common.domain.ports.asset_repository import AssetRepository
from docpipe.exceptions.docpipe_exceptions import (
    AssetAlreadyExistsException,
    AssetInvalidDataException,
    AssetNotFoundException,
)

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=Asset)


class LocalAssetRepository(AssetRepository[T]):
    """Generic filesystem-based repository for all asset types.

    Stores assets as JSON files in configured directories.

    Usage:
        flow_repo = LocalAssetRepository[Flow](asset_type=Flow, storage_path="/path/to/flows")
        flow = Flow(name="my_flow", definition={...})
        saved_flow = flow_repo.save(asset=flow)
    """

    @classmethod
    def from_config(cls, *, asset_type: type[T], config: dict) -> "LocalAssetRepository[T]":
        """Create a LocalAssetRepository from a config dict.

        Args:
            asset_type: The asset model class (Flow, etc.)
            config: May contain ``base_dir`` for the storage path.

        Returns:
            Configured LocalAssetRepository instance
        """
        storage_path = config.get("base_dir")
        return cls(asset_type=asset_type, storage_path=storage_path)

    def __init__(self, *, asset_type: type[T], storage_path: str | None = None):
        """Initialize repository with explicit asset type.

        Args:
            asset_type: The asset type class (Flow, DocumentSet, etc.)
            storage_path: Optional custom storage path (defaults to ~/Documents/pipeline/assets)
        """
        self._asset_type = asset_type

        # Determine storage path
        if storage_path:
            self._storage_path = Path(storage_path)
        else:
            # Default path for flows
            self._storage_path = Path.home() / "Documents" / "pipeline" / "assets"

        self._storage_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Initialized LocalAssetRepository for {asset_type.__name__} at {self._storage_path}")

    def _get_file_path(self, *, asset_id: str) -> Path:
        """Get file path for an asset.

        Args:
            asset_id: Asset ID

        Returns:
            Path to asset file
        """
        return self._storage_path / f"{asset_id}.json"

    def save(self, *, asset: T) -> T:
        """Save an asset.

        Args:
            asset: Asset to save

        Returns:
            Saved asset with generated ID and timestamps
        """
        asset.update_timestamp()

        # Check for duplicate name
        if self.exists_by_name(name=asset.name):
            raise AssetAlreadyExistsException(f"Asset with name '{asset.name}' already exists")

        # Save to file
        file_path = self._get_file_path(asset_id=asset.asset_id)
        with Path(file_path).open("w") as f:
            json.dump(asset.to_dict(), f, indent=2)

        logger.info(f"Saved {self._asset_type.__name__} {asset.asset_id}")
        return asset

    def find_by_id(self, *, asset_id: str) -> T | None:
        """Find asset by ID.

        Args:
            asset_id: Asset ID

        Returns:
            Asset if found, None otherwise
        """
        file_path = self._get_file_path(asset_id=asset_id)
        if not file_path.exists():
            return None

        with Path(file_path).open() as f:
            data = json.load(f)

        return self._asset_type.from_dict(data=data)  # type: ignore

    def find_by_name(self, *, name: str) -> T | None:
        """Find asset by name.

        Args:
            name: Asset name

        Returns:
            Asset if found, None otherwise
        """
        for asset in self.find_all():
            if asset.name == name:
                return asset
        return None

    def find_all(self) -> list[T]:
        """Find all assets.

        Returns:
            List of all assets
        """
        assets = []
        for file_path in self._storage_path.glob("*.json"):
            try:
                with Path(file_path).open() as f:
                    data = json.load(f)
                asset = self._asset_type.from_dict(data=data)  # type: ignore
                assets.append(asset)
            except Exception as e:
                logger.warning(f"Failed to load asset from {file_path}: {e}")
        return assets

    def list_all(self, *, limit: int | None = None, offset: int | None = None) -> list[T]:
        """List all assets with optional pagination, sorted newest-first.

        Args:
            limit: Maximum number of assets to return (None for all)
            offset: Number of assets to skip (None / 0 for none)

        Returns:
            List of assets sorted by creation date newest-first
        """
        assets = self.find_all()

        # Sort newest-first using the canonical get_updated_at() method on Asset base class
        def _sort_key(a: T) -> str:
            updated = a.get_updated_at()
            if updated is not None:
                return updated.isoformat()
            return a.name

        assets.sort(key=_sort_key, reverse=True)

        start = offset or 0
        return assets[start : start + limit] if limit is not None else assets[start:]

    def update(self, *, asset: T) -> T:
        """Update an asset.

        Args:
            asset: Asset to update

        Returns:
            Updated asset
        """
        if not asset.asset_id:
            raise AssetInvalidDataException("Asset ID is required for update")

        if not self.exists(asset_id=asset.asset_id):
            raise AssetNotFoundException(f"Asset {asset.asset_id} not found")

        asset.update_timestamp()

        # Save to file
        file_path = self._get_file_path(asset_id=asset.asset_id)
        with Path(file_path).open("w") as f:
            json.dump(asset.to_dict(), f, indent=2)

        logger.info(f"Updated {self._asset_type.__name__} {asset.asset_id}")
        return asset

    def partial_update(self, asset: T, updates: dict[str, Any]) -> T:
        """Apply partial updates to an existing asset and persist changes.

        This method applies the provided field updates to the asset,
        validates the result, and persists using the existing update() method.

        Args:
            asset: Asset entity to update
            updates: Dictionary of field updates to apply

        Returns:
            Updated asset with refreshed timestamp

        Raises:
            ValueError: If validation fails after applying updates
            PermissionError: If write permission denied
            OSError: If file system operation fails
            TimeoutError: If lock cannot be acquired
        """
        # Apply updates using setattr
        for field, value in updates.items():
            if hasattr(asset, field):
                setattr(asset, field, value)
                logger.debug("Applied update to field '%s' for flow %s", field, asset.asset_id)

        # Validate after updates
        try:
            asset.validate()
            asset.update_timestamp()
        except ValueError as exc:
            logger.error("Flow validation failed after partial update: %s", exc)
            raise ValueError(f"Invalid flow data after update: {exc!s}") from exc

        # Persist using existing update method (handles locking and atomicity)
        updated_asset = self.update(asset=asset)

        logger.info("Partial update completed for flow %s", asset.asset_id)
        return updated_asset

    def delete(self, *, asset_id: str) -> bool:
        """Delete an asset.

        Args:
            asset_id: Asset ID

        Returns:
            True if deleted, False if not found
        """
        file_path = self._get_file_path(asset_id=asset_id)
        if not file_path.exists():
            return False

        file_path.unlink()
        logger.info(f"Deleted {self._asset_type.__name__} {asset_id}")
        return True

    def bulk_delete(self, *, asset_ids: list[str]) -> dict[str, Any]:
        """Delete multiple assets in a batch operation.

        Args:
            asset_ids: List of asset IDs to delete

        Returns:
            Dictionary with deletion results
        """
        deleted = []
        failed = []

        for asset_id in asset_ids:
            try:
                if self.delete(asset_id=asset_id):
                    deleted.append(asset_id)
                else:
                    failed.append({"asset_id": asset_id, "error": "Asset not found"})
            except Exception as e:
                failed.append({"asset_id": asset_id, "error": str(e)})
                logger.warning(f"Failed to delete {self._asset_type.__name__} {asset_id}: {e}")

        result = {
            "total_requested": len(asset_ids),
            "total_deleted": len(deleted),
            "total_failed": len(failed),
            "deleted": deleted,
            "failed": failed,
        }

        logger.info(
            f"Bulk delete completed for {self._asset_type.__name__}: "
            f"{result['total_deleted']} deleted, {result['total_failed']} failed"
        )

        return result

    def exists(self, *, asset_id: str) -> bool:
        """Check if asset exists.

        Args:
            asset_id: Asset ID

        Returns:
            True if exists
        """
        file_path = self._get_file_path(asset_id=asset_id)
        return file_path.exists()

    def exists_by_name(self, *, name: str) -> bool:
        """Check if asset exists by name.

        Args:
            name: Asset name

        Returns:
            True if exists
        """
        return self.find_by_name(name=name) is not None

    def health_check(self) -> dict[str, Any]:
        """Check repository health.

        Returns:
            Health status dictionary
        """
        return {
            "status": "healthy",
            "storage_path": str(self._storage_path),
            "storage_exists": self._storage_path.exists(),
            "storage_writable": os.access(self._storage_path, os.W_OK),
            "asset_count": len(list(self._storage_path.glob("*.json"))),
        }
