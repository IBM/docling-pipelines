"""Factory for creating AttachmentRepository adapters with decorator-based registration.

Adapters self-wire their own dependencies via a ``create(*, config)`` classmethod.
"""

from typing import Any, ClassVar

from docpipe.core.assets.common.domain.ports.attachment_repository import AttachmentRepository
from docpipe.exceptions.docpipe_exceptions import DocpipeException
from docpipe.exceptions.error_codes import ErrorCode
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger(__name__)


class AttachmentRepositoryFactory:
    """Factory for creating AttachmentRepository adapters.

    Maintains a registry of available adapters and delegates instantiation to
    each adapter's own ``create(*, config)`` classmethod.

    Usage:
        # Register an adapter
        @AttachmentRepositoryFactory.register(name="duckdb", display_name="DuckDB")
        class DuckDBAttachmentRepository(AttachmentRepository):
            ...

        # Create an adapter instance
        adapter = AttachmentRepositoryFactory.create(
            adapter_name="duckdb", config={"database_path": "/path/to/db"}
        )
    """

    _adapters: ClassVar[dict[str, type[AttachmentRepository]]] = {}
    _adapter_metadata: ClassVar[dict[str, dict[str, str]]] = {}

    @classmethod
    def register(cls, *, name: str, display_name: str):
        """Decorator to register an AttachmentRepository adapter class.

        Args:
            name: Unique identifier for the adapter (e.g., "duckdb").
            display_name: Human-readable name (e.g., "DuckDB").

        Returns:
            The decorator function that registers the adapter class.
        """

        def decorator(adapter_class: type[AttachmentRepository]) -> type[AttachmentRepository]:
            if name in cls._adapters:
                logger.warning("Attachment repository adapter '%s' is already registered. Overwriting.", name)

            cls._adapters[name] = adapter_class
            cls._adapter_metadata[name] = {
                "name": name,
                "display_name": display_name,
                "class": adapter_class.__name__,
            }
            logger.debug("Registered attachment repository adapter: %s", name)
            return adapter_class

        return decorator

    @classmethod
    def create(cls, *, adapter_name: str, config: dict[str, Any]) -> AttachmentRepository:
        """Create an AttachmentRepository adapter instance.

        Validates the config then delegates to the adapter's own
        ``create(*, config)`` classmethod, which is responsible for wiring
        its own dependencies.

        Args:
            adapter_name: Name of the adapter to create (e.g., "duckdb").
            config: Configuration dictionary passed as-is to the adapter.

        Returns:
            Initialized adapter instance.

        Raises:
            DocpipeException: If adapter_name is not registered, configuration
                is invalid, or instantiation fails.
        """
        if adapter_name not in cls._adapters:
            available = ", ".join(cls._adapters.keys()) if cls._adapters else "none"
            raise DocpipeException(
                message=f"Unknown attachment repository adapter: '{adapter_name}'. Available adapters: {available}",
                status_code=400,
                error_code=ErrorCode.OPERATOR_CONFIGURATION_INVALID,
            )

        adapter_class = cls._adapters[adapter_name]
        logger.debug("Creating attachment repository adapter: %s", adapter_name)

        validation_errors = adapter_class.validate_config(config=config)
        if validation_errors:
            error_msg = "; ".join(validation_errors)
            raise DocpipeException(
                message=f"Invalid configuration for adapter '{adapter_name}': {error_msg}",
                status_code=400,
                error_code=ErrorCode.OPERATOR_CONFIGURATION_INVALID,
            )

        try:
            return adapter_class.create(config=config)
        except DocpipeException:
            raise
        except Exception as e:
            raise DocpipeException(
                message=f"Failed to create attachment repository adapter '{adapter_name}': {e!s}",
                status_code=500,
                error_code=ErrorCode.OPERATOR_CONFIGURATION_INVALID,
            ) from e

    @classmethod
    def list_adapters(cls) -> list[dict[str, str]]:
        """List all registered adapter names with their metadata.

        Returns:
            List of dictionaries with keys: name, display_name, class.
        """
        return list(cls._adapter_metadata.values())

    @classmethod
    def get_adapter_info(cls, *, adapter_name: str) -> dict[str, str]:
        """Get information about a registered adapter.

        Args:
            adapter_name: Name of the adapter.

        Returns:
            Dictionary with keys: name, display_name, class.

        Raises:
            DocpipeException: If adapter_name is not registered.
        """
        if adapter_name not in cls._adapters:
            available = ", ".join(cls._adapters.keys()) if cls._adapters else "none"
            raise DocpipeException(
                message=f"Unknown attachment repository adapter: '{adapter_name}'. Available adapters: {available}",
                status_code=400,
                error_code=ErrorCode.OPERATOR_CONFIGURATION_INVALID,
            )
        return cls._adapter_metadata[adapter_name].copy()
