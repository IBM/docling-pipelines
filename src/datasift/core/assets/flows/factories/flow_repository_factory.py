"""Factory for creating flow repository instances."""

from typing import Any

from datasift.core.assets.flows.adapters.repositories.storage_flow_repository import (
    StorageFlowRepository,
)
from datasift.core.assets.flows.domain.ports.flow_repository import FlowRepository
from datasift.core.constants.constants import DatasiftConstants
from datasift.storage import StorageFactory
from datasift.utils.infrastructure.logging import get_logger

logger = get_logger(__name__)


class FlowRepositoryFactory:
    """Factory for creating flow repository instances.

    This factory creates flow repositories with the appropriate storage backend
    based on the storage type configuration.
    """

    @staticmethod
    def create(*, storage_type: str = DatasiftConstants.DEFAULT_STORAGE_TYPE, **config: Any) -> FlowRepository:
        """Create a flow repository instance.

        Args:
            storage_type: Type of storage backend ("duckdb", "filesystem")
            **config: Storage-specific configuration (e.g., database_path, base_dir)

        Returns:
            FlowRepository instance with configured storage

        Raises:
            ValueError: If storage_type is not supported

        Example:
            # DuckDB backend
            repository = FlowRepositoryFactory.create(
                storage_type="duckdb",
                database_path="data/flows.db"
            )

            # Filesystem backend
            repository = FlowRepositoryFactory.create(
                storage_type="filesystem",
                base_dir="data/flows"
            )
        """
        logger.info(f"Creating flow repository with storage type: {storage_type}")

        # Validate storage type
        if storage_type not in DatasiftConstants.SUPPORTED_STORAGE_TYPES:
            raise ValueError(
                f"Unsupported storage type: '{storage_type}'. "
                f"Supported types: {', '.join(DatasiftConstants.SUPPORTED_STORAGE_TYPES)}"
            )

        # Create storage instance
        key_value_storage = StorageFactory.create_key_value_storage(storage_type=storage_type, **config)

        # Create and return repository
        return StorageFlowRepository(storage=key_value_storage)

    @staticmethod
    def list_available() -> list[str]:
        """List available storage types for flow repositories."""
        return DatasiftConstants.SUPPORTED_STORAGE_TYPES
