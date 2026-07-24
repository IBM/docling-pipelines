"""Factory for creating document library repository adapters with decorator-based registration.

This factory enables automatic registration of repository adapters through decorators,
following the same pattern as Document Sets MetadataRepositoryFactory.

Note: Repository adapters use KeyValueStorage from the storage layer for metadata operations.
The factory creates storage instances via StorageFactory and injects them into adapters.
Junction table operations remain in the repository layer using direct SQL.
"""

from typing import Any, ClassVar, cast

from docpipe.core.assets.document_libraries.domain.ports.document_library_repository import (
    DocumentLibraryRepository,
)
from docpipe.core.assets.document_libraries.domain.types import RepositoryConfig
from docpipe.exceptions.docpipe_exceptions import DocpipeException
from docpipe.exceptions.error_codes import ErrorCode
from docpipe.storage import StorageFactory
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger(__name__)


class DocumentLibraryRepositoryFactory:
    """Factory for creating document library repository adapters.

    This factory maintains a registry of available repository adapters and
    provides methods to create instances based on adapter names.

    Usage:
        # Register an adapter
        @DocumentLibraryRepositoryFactory.register(name="duckdb", display_name="DuckDB")
        class DuckDBDocumentLibraryMetadataRepository(DocumentLibraryRepository):
            ...

        # Create an adapter instance
        config: RepositoryConfig = {"database_path": "/path/to/db"}
        adapter = DocumentLibraryRepositoryFactory.create(adapter_name="duckdb", config=config)

        # List all registered adapters
        adapters = DocumentLibraryRepositoryFactory.list_adapters()

        # Get adapter information
        info = DocumentLibraryRepositoryFactory.get_adapter_info(adapter_name="duckdb")
    """

    _adapters: ClassVar[dict[str, type[DocumentLibraryRepository]]] = {}
    _adapter_metadata: ClassVar[dict[str, dict[str, str]]] = {}

    @classmethod
    def register(cls, *, name: str, display_name: str):
        """Decorator to register a document library repository adapter class.

        Args:
            name: Unique identifier for the adapter (e.g., "duckdb", "postgres")
            display_name: Human-readable name for the adapter (e.g., "DuckDB", "PostgreSQL")

        Returns:
            The decorator function that registers the adapter class

        Raises:
            DocpipeException: If an adapter with the same name is already registered

        Example:
            @DocumentLibraryRepositoryFactory.register(name="duckdb", display_name="DuckDB")
            class DuckDBDocumentLibraryMetadataRepository(DocumentLibraryRepository):
                pass
        """

        def decorator(
            adapter_class: type[DocumentLibraryRepository],
        ) -> type[DocumentLibraryRepository]:
            if name in cls._adapters:
                logger.warning(f"Adapter '{name}' is already registered. Overwriting.")

            cls._adapters[name] = adapter_class
            cls._adapter_metadata[name] = {
                "name": name,
                "display_name": display_name,
                "class": adapter_class.__name__,
            }
            logger.debug(f"Registered document library repository adapter: {name}")

            return adapter_class

        return decorator

    @classmethod
    def create(cls, *, adapter_name: str, config: RepositoryConfig) -> DocumentLibraryRepository:
        """Create a document library repository adapter instance with dependency injection.

        This method creates the appropriate storage instance via StorageFactory
        and injects it into the adapter, following the dependency injection pattern.

        Args:
            adapter_name: Name of the adapter to create (e.g., "duckdb")
            config: Configuration parameters including database_path

        Returns:
            Initialized adapter instance with injected storage

        Raises:
            DocpipeException: If adapter_name is not registered or configuration is invalid
        """
        if adapter_name not in cls._adapters:
            available = ", ".join(cls._adapters.keys()) if cls._adapters else "none"
            raise DocpipeException(
                message=f"Unknown document library repository adapter: '{adapter_name}'. Available adapters: {available}",
                status_code=400,
                error_code=ErrorCode.OPERATOR_CONFIGURATION_INVALID,
            )

        adapter_class = cls._adapters[adapter_name]
        logger.debug(f"Creating document library repository adapter: {adapter_name}")

        # Validate configuration before instantiation
        config_dict = cast(dict[str, Any], config)
        validation_errors = adapter_class.validate_config(config=config_dict)
        if validation_errors:
            error_msg = "; ".join(validation_errors)
            raise DocpipeException(
                message=f"Invalid configuration for adapter '{adapter_name}': {error_msg}",
                status_code=400,
                error_code=ErrorCode.OPERATOR_CONFIGURATION_INVALID,
            )

        try:
            # Create storage instance via StorageFactory (dependency injection)
            # The adapter_name determines which storage type to use
            storage_type = adapter_name  # e.g., "duckdb" -> DuckDB storage
            key_value_storage = StorageFactory.create_key_value_storage(storage_type=storage_type, **config_dict)

            # Extract database_path for health check reporting
            database_path = config_dict.get("database_path", "unknown")

            # Inject storage into adapter
            return adapter_class(key_value_storage=key_value_storage, database_path=database_path)
        except Exception as e:
            raise DocpipeException(
                message=f"Failed to create document library repository adapter '{adapter_name}': {e!s}",
                status_code=500,
                error_code=ErrorCode.OPERATOR_CONFIGURATION_INVALID,
            ) from e

    @classmethod
    def list_adapters(cls) -> list[dict[str, str]]:
        """List all registered adapter names with their metadata.

        Returns:
            List of dictionaries containing adapter information with keys:
            - name: Adapter identifier
            - display_name: Human-readable name
            - class: Adapter class name
        """
        return list(cls._adapter_metadata.values())

    @classmethod
    def get_adapter_info(cls, *, adapter_name: str) -> dict[str, str]:
        """Get information about a registered adapter.

        Args:
            adapter_name: Name of the adapter

        Returns:
            Dictionary with adapter information containing:
            - name: Adapter identifier
            - display_name: Human-readable name
            - class: Adapter class name

        Raises:
            DocpipeException: If adapter_name is not registered
        """
        if adapter_name not in cls._adapters:
            available = ", ".join(cls._adapters.keys()) if cls._adapters else "none"
            raise DocpipeException(
                message=f"Unknown document library repository adapter: '{adapter_name}'. Available adapters: {available}",
                status_code=400,
                error_code=ErrorCode.OPERATOR_CONFIGURATION_INVALID,
            )

        return cls._adapter_metadata[adapter_name].copy()
