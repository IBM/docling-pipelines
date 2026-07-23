"""Generic service layer for all asset types.

This module defines the generic service class that provides common operations
for all asset types. Model-specific operations (create/update with timestamps) are
implemented in subclasses (FlowService, DocumentSetService, DocumentLibraryService).

"""

import logging
from typing import Any

from docpipe.core.assets.common.domain.models.asset import Asset
from docpipe.core.assets.common.domain.ports.asset_repository import AssetRepository
from docpipe.exceptions.docpipe_exceptions import DocpipeException

logger = logging.getLogger(__name__)


class AssetService[T: Asset]:
    """Generic service for all asset types - provides ONLY truly common operations.

    This service provides operations that work identically for ALL assets:
    - get_by_id / get_by_name (retrieval)
    - delete (deletion)
    - exists / exists_by_name (existence checks)
    - list_all / count_all (listing and counting)
    - health_check (repository health)

    Model-specific operations are implemented in subclasses:
    - FlowService: create_flow(), update_flow() (handles created_on/modified_on)
    - DocumentSetService: create(), update() (handles created_at/updated_at)
    - DocumentLibraryService: create(), update() (no timestamps)

    Type Parameters:
        T: Asset type (Flow, DocumentSet, DocumentLibrary, etc.)
    """

    def __init__(self, *, repository: AssetRepository[T]):
        """Initialize the service with a repository.

        Args:
            repository: Repository implementation for asset storage
        """
        self._repository = repository
        logger.debug("AssetService initialized with repository: %s", type(repository).__name__)

    def get_by_id(self, *, asset_id: str) -> T:
        """Get an asset by ID with validation and not-found handling.

        Args:
            asset_id: Unique identifier of the asset

        Returns:
            Asset instance

        Raises:
            DocpipeException: If asset_id is empty or asset doesn't exist
        """
        if not asset_id or not asset_id.strip():
            raise DocpipeException("asset_id cannot be empty", status_code=400)

        asset = self._repository.find_by_id(asset_id=asset_id)
        if asset is None:
            raise DocpipeException(f"Asset with ID '{asset_id}' not found", status_code=404)

        logger.info("Successfully retrieved asset %s", asset_id)
        return asset

    def get_by_name(self, *, name: str) -> T:
        """Get an asset by name with not-found handling.

        Args:
            name: Name of the asset

        Returns:
            Asset instance

        Raises:
            DocpipeException: If asset doesn't exist
        """
        asset = self._repository.find_by_name(name=name)
        if asset is None:
            raise DocpipeException(f"Asset with name '{name}' not found", status_code=404)

        logger.info("Successfully retrieved asset by name: %s", name)
        return asset

    def delete(self, *, asset_id: str) -> bool:
        """Delete an asset with validation and not-found handling.

        Args:
            asset_id: Unique identifier of the asset to delete

        Returns:
            True if asset was deleted

        Raises:
            DocpipeException: If asset_id is empty or asset doesn't exist
        """
        if not asset_id or not asset_id.strip():
            raise DocpipeException("asset_id cannot be empty", status_code=400)

        deleted = self._repository.delete(asset_id=asset_id)

        if deleted:
            logger.info("Successfully deleted asset %s", asset_id)
            return deleted
        logger.error("Asset %s not found for deletion", asset_id)
        raise DocpipeException(f"Asset with ID '{asset_id}' not found", status_code=404)

    def exists(self, *, asset_id: str) -> bool:
        """Check if an asset exists by ID.

        Args:
            asset_id: Unique identifier of the asset

        Returns:
            True if asset exists, False otherwise

        Raises:
            DocpipeException: If asset_id is empty
        """
        if not asset_id or not asset_id.strip():
            raise DocpipeException("asset_id cannot be empty", status_code=400)

        result = self._repository.exists(asset_id=asset_id)
        logger.debug("Asset existence check for %s: %s", asset_id, result)
        return result

    def exists_by_name(self, *, name: str) -> bool:
        """Check if an asset with the given name exists.

        Args:
            name: Name of the asset

        Returns:
            True if asset with this name exists, False otherwise
        """
        return self._repository.exists_by_name(name=name)

    def list_all(self, *, skip: int = 0, limit: int = 100) -> list[T]:
        """List all assets with pagination.

        Args:
            skip: Number of items to skip (for pagination)
            limit: Maximum number of items to return

        Returns:
            List of assets

        Raises:
            DocpipeException: If pagination parameters are invalid
        """
        if skip < 0:
            raise DocpipeException("skip must be >= 0", status_code=400)
        if limit <= 0:
            raise DocpipeException("limit must be > 0", status_code=400)

        all_assets = self._repository.find_all()
        paginated = all_assets[skip : skip + limit]

        logger.info("Listed %d assets (paginated from %d)", len(paginated), len(all_assets))
        return paginated

    def count_all(self) -> int:
        """Count all assets.

        Returns:
            Number of assets
        """
        count = len(self._repository.find_all())
        logger.info("Counted %d assets", count)
        return count

    def health_check(self) -> dict[str, Any]:
        """Check the health of the underlying repository.

        Returns:
            Dictionary with health status information
        """
        return self._repository.health_check()
