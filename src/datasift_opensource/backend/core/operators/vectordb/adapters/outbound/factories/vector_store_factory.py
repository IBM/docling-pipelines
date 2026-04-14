"""Factory for creating vector store adapters with decorator-based registration.

This factory enables automatic registration of vector store adapters through decorators.
"""

from typing import Any, ClassVar

from common.exceptions.datasift_exceptions import DatasiftException
from common.exceptions.error_codes import ErrorCode
from common.util.infrastructure.logging import get_logger
from core.operators.vectordb.ports.outbound.vector_store import VectorStorePort

logger = get_logger(__name__)


class VectorStoreFactory:
    """Factory for creating vector store adapters.

    This factory maintains a registry of available vector store adapters and
    provides methods to create instances based on adapter names.

    Usage:
        # Register an adapter
        @register_vector_store
        class OpenSearchAdapter(VectorStorePort):
            ADAPTER_NAME = "opensearch"
            ...

        # Create an adapter instance
        adapter = VectorStoreFactory.create("opensearch", config=config)
    """

    _adapters: ClassVar[dict[str, type[VectorStorePort]]] = {}

    @classmethod
    def register(cls, adapter_class: type[VectorStorePort]) -> type[VectorStorePort]:
        """Register a vector store adapter class.

        Args:
            adapter_class: The adapter class to register

        Returns:
            The adapter class (for decorator chaining)

        Raises:
            DatasiftException: If adapter_class doesn't have ADAPTER_NAME or is already registered
        """
        if not hasattr(adapter_class, "ADAPTER_NAME"):
            raise DatasiftException(
                message=f"Adapter class {adapter_class.__name__} must define ADAPTER_NAME",
                status_code=500,
                error_code=ErrorCode.OPERATOR_CONFIGURATION_INVALID,
            )

        adapter_name = adapter_class.ADAPTER_NAME

        if adapter_name in cls._adapters:
            logger.warning(f"Adapter '{adapter_name}' is already registered. Overwriting.")

        cls._adapters[adapter_name] = adapter_class
        logger.debug(f"Registered vector store adapter: {adapter_name}")

        return adapter_class

    @classmethod
    def create(cls, adapter_name: str, **config: Any) -> VectorStorePort:
        """Create a vector store adapter instance.

        Args:
            adapter_name: Name of the adapter to create
            **config: Configuration parameters for the adapter

        Returns:
            Initialized adapter instance

        Raises:
            DatasiftException: If adapter_name is not registered
        """
        if adapter_name not in cls._adapters:
            available = ", ".join(cls._adapters.keys()) if cls._adapters else "none"
            raise DatasiftException(
                message=f"Unknown vector store adapter: '{adapter_name}'. Available adapters: {available}",
                status_code=400,
                error_code=ErrorCode.OPERATOR_CONFIGURATION_INVALID,
            )

        adapter_class = cls._adapters[adapter_name]
        logger.debug(f"Creating vector store adapter: {adapter_name}")

        try:
            return adapter_class(**config)
        except Exception as e:
            raise DatasiftException(
                message=f"Failed to create vector store adapter '{adapter_name}': {e!s}",
                status_code=500,
                error_code=ErrorCode.OPERATOR_CONFIGURATION_INVALID,
            ) from e

    @classmethod
    def list_adapters(cls) -> list[str]:
        """List all registered adapter names.

        Returns:
            List of registered adapter names
        """
        return list(cls._adapters.keys())

    @classmethod
    def get_adapter_info(cls, adapter_name: str) -> dict[str, str]:
        """Get information about a registered adapter.

        Args:
            adapter_name: Name of the adapter

        Returns:
            Dictionary with adapter information

        Raises:
            DatasiftException: If adapter_name is not registered
        """
        if adapter_name not in cls._adapters:
            raise DatasiftException(
                message=f"Unknown vector store adapter: '{adapter_name}'",
                status_code=400,
                error_code=ErrorCode.OPERATOR_CONFIGURATION_INVALID,
            )

        adapter_class = cls._adapters[adapter_name]
        return {
            "name": adapter_class.ADAPTER_NAME,
            "display_name": adapter_class.ADAPTER_DISPLAY_NAME,
            "class": adapter_class.__name__,
        }


def register_vector_store(adapter_class: type[VectorStorePort]) -> type[VectorStorePort]:
    """Decorator to register a vector store adapter.

    Usage:
        @register_vector_store
        class OpenSearchAdapter(VectorStorePort):
            ADAPTER_NAME = "opensearch"
            ADAPTER_DISPLAY_NAME = "OpenSearch"
            ...

    Args:
        adapter_class: The adapter class to register

    Returns:
        The adapter class (for decorator chaining)
    """
    return VectorStoreFactory.register(adapter_class)
