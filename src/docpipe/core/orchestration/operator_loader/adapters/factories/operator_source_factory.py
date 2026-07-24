"""Factory for creating operator source adapters with decorator-based registration.

This factory enables automatic registration of operator source adapters through decorators.
"""

from typing import Any, ClassVar

from docpipe.core.orchestration.operator_loader.ports.operator_source import OperatorSourcePort
from docpipe.exceptions.docpipe_exceptions import DocpipeException
from docpipe.exceptions.error_codes import ErrorCode
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger(__name__)


class OperatorSourceFactory:
    """Factory for creating operator source adapters.

    This factory maintains a registry of available operator source adapters and
    provides methods to create instances based on adapter names.

    Usage:
        # Register an adapter
        @register_operator_source
        class FilesystemAdapter(OperatorSourcePort):
            ADAPTER_NAME = "filesystem"
            ...

        # Create an adapter instance
        adapter = OperatorSourceFactory.create("filesystem", path="/path/to/operators")
    """

    _adapters: ClassVar[dict[str, type[OperatorSourcePort]]] = {}

    @classmethod
    def register(cls, adapter_class: type[OperatorSourcePort]) -> type[OperatorSourcePort]:
        """Register an operator source adapter class.

        Args:
            adapter_class: The adapter class to register

        Returns:
            The adapter class (for decorator chaining)

        Raises:
            DocpipeException: If adapter_class doesn't have ADAPTER_NAME or is already registered
        """
        if not hasattr(adapter_class, "ADAPTER_NAME"):
            raise DocpipeException(
                message=f"Adapter class {adapter_class.__name__} must define ADAPTER_NAME",
                status_code=500,
                error_code=ErrorCode.OPERATOR_CONFIGURATION_INVALID,
            )

        adapter_name = adapter_class.ADAPTER_NAME

        if adapter_name in cls._adapters:
            logger.warning(f"Adapter '{adapter_name}' is already registered. Overwriting.")

        cls._adapters[adapter_name] = adapter_class
        logger.debug(f"Registered operator source adapter: {adapter_name}")

        return adapter_class

    @classmethod
    def create(cls, adapter_name: str, **config: Any) -> OperatorSourcePort:
        """Create an operator source adapter instance.

        Args:
            adapter_name: Name of the adapter to create
            **config: Configuration parameters for the adapter

        Returns:
            Initialized adapter instance

        Raises:
            DocpipeException: If adapter_name is not registered
        """
        if adapter_name not in cls._adapters:
            available = ", ".join(cls._adapters.keys()) if cls._adapters else "none"
            raise DocpipeException(
                message=f"Unknown operator source adapter: '{adapter_name}'. Available adapters: {available}",
                status_code=400,
                error_code=ErrorCode.OPERATOR_CONFIGURATION_INVALID,
            )

        adapter_class = cls._adapters[adapter_name]
        logger.debug(f"Creating operator source adapter: {adapter_name}")

        try:
            return adapter_class(**config)
        except Exception as e:
            raise DocpipeException(
                message=f"Failed to create operator source adapter '{adapter_name}': {e!s}",
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
            DocpipeException: If adapter_name is not registered
        """
        if adapter_name not in cls._adapters:
            raise DocpipeException(
                message=f"Unknown operator source adapter: '{adapter_name}'",
                status_code=400,
                error_code=ErrorCode.OPERATOR_CONFIGURATION_INVALID,
            )

        adapter_class = cls._adapters[adapter_name]
        return {
            "name": adapter_class.ADAPTER_NAME,
            "display_name": adapter_class.ADAPTER_DISPLAY_NAME,
            "class": adapter_class.__name__,
        }


def register_operator_source(adapter_class: type[OperatorSourcePort]) -> type[OperatorSourcePort]:
    """Decorator to register an operator source adapter.

    Usage:
        @register_operator_source
        class FilesystemAdapter(OperatorSourcePort):
            ADAPTER_NAME = "filesystem"
            ADAPTER_DISPLAY_NAME = "Local Filesystem"
            ...

    Args:
        adapter_class: The adapter class to register

    Returns:
        The adapter class (for decorator chaining)
    """
    return OperatorSourceFactory.register(adapter_class)
