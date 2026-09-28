"""Factory for creating data store adapters with decorator-based registration.

This factory enables automatic registration of data store adapters through decorators,
following the same pattern as VectorStoreFactory.

Note: Adapter construction details (e.g. storage dependencies, constructor arguments)
are encapsulated in each adapter's from_config() classmethod. The factory only handles
registration, config validation, and delegation.
"""

from typing import Any, ClassVar, cast

from docpipe.core.assets.document_sets.domain.ports.data_store import (
    DocumentSetStorage,
)
from docpipe.core.assets.document_sets.domain.types import DataStoreConfig
from docpipe.exceptions.docpipe_exceptions import DocpipeException
from docpipe.exceptions.error_codes import ErrorCode
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger(__name__)


class DataStoreFactory:
    """Factory for creating data store adapters.

    This factory maintains a registry of available data store adapters and
    provides methods to create instances based on adapter names.

    Usage:
        # Register an adapter
        @DataStoreFactory.register(name="duckdb", display_name="DuckDB")
        class DuckDBDocumentSetDataStore(DocumentSetDataStore):
            ...

        # Create an adapter instance
        config: DataStoreConfig = {"storage_path": "/path/to/storage"}
        adapter = DataStoreFactory.create(adapter_name="duckdb", config=config)

        # List all registered adapters
        adapters = DataStoreFactory.list_adapters()

        # Get adapter information
        info = DataStoreFactory.get_adapter_info(adapter_name="duckdb")
    """

    _adapters: ClassVar[dict[str, type[DocumentSetStorage]]] = {}
    _adapter_metadata: ClassVar[dict[str, dict[str, str]]] = {}

    @classmethod
    def register(cls, *, name: str, display_name: str):
        """Decorator to register a data store adapter class.

        Args:
            name: Unique identifier for the adapter (e.g., "duckdb", "parquet")
            display_name: Human-readable name for the adapter (e.g., "DuckDB", "Parquet Files")

        Returns:
            The decorator function that registers the adapter class

        Raises:
            DocpipeException: If an adapter with the same name is already registered

        Example:
            @DataStoreFactory.register(name="duckdb", display_name="DuckDB")
            class DuckDBDocumentSetStorage(DocumentSetStorage):
                pass
        """

        def decorator(
            adapter_class: type[DocumentSetStorage],
        ) -> type[DocumentSetStorage]:
            """Register the adapter class and return it unchanged."""
            if name in cls._adapters:
                logger.warning("Adapter '%s' is already registered. Overwriting.", name)

            cls._adapters[name] = adapter_class
            cls._adapter_metadata[name] = {
                "name": name,
                "display_name": display_name,
                "class": adapter_class.__name__,
            }
            logger.debug("Registered data store adapter: %s", name)

            return adapter_class

        return decorator

    @classmethod
    def create(cls, *, adapter_name: str, config: DataStoreConfig) -> DocumentSetStorage:
        """Create a data store adapter instance.

        Validates the config and delegates construction to the adapter's
        ``from_config()`` classmethod.

        Args:
            adapter_name: Name of the adapter to create (e.g., "duckdb")
            config: Configuration parameters passed through to the adapter's from_config()

        Returns:
            Initialized adapter instance

        Raises:
            DocpipeException: If adapter_name is not registered or configuration is invalid
        """
        if adapter_name not in cls._adapters:
            available = ", ".join(cls._adapters.keys()) if cls._adapters else "none"
            raise DocpipeException(
                message=f"Unknown data store adapter: '{adapter_name}'. Available adapters: {available}",
                status_code=400,
                error_code=ErrorCode.OPERATOR_CONFIGURATION_INVALID,
            )

        adapter_class = cls._adapters[adapter_name]
        logger.debug("Creating data store adapter: %s", adapter_name)

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
            return adapter_class.from_config(config=config_dict)
        except DocpipeException:
            raise
        except Exception as e:
            raise DocpipeException(
                message=f"Failed to create data store adapter '{adapter_name}': {e!s}",
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
                message=f"Unknown data store adapter: '{adapter_name}'. Available adapters: {available}",
                status_code=400,
                error_code=ErrorCode.OPERATOR_CONFIGURATION_INVALID,
            )

        return cls._adapter_metadata[adapter_name].copy()
