"""Factory for creating and discovering source adapters."""

from typing import Any, ClassVar

from docpipe.core.operators.ingest.ports.outbound.document_source import DocumentSourcePort


class SourceAdapterFactory:
    """
    Factory for discovering and creating document source adapters.

    This factory implements the Registry pattern combined with Factory pattern:
    - Adapters self-register using the @register_source_adapter decorator
    - The factory maintains a registry of all available adapters
    - Adapters can be created by name
    - Metadata about all adapters can be queried for UI/discovery purposes

    This follows the Open/Closed Principle:
    - Open for extension: New adapters can be added without modifying this code
    - Closed for modification: The factory logic doesn't change when adding adapters
    """

    _adapters: ClassVar[dict[str, type[DocumentSourcePort]]] = {}

    @classmethod
    def register(cls, adapter_class: type[DocumentSourcePort]) -> None:
        """
        Register a source adapter.

        Args:
            adapter_class: The adapter class to register

        Raises:
            ValueError: If adapter doesn't have SOURCE_NAME
        """
        source_name = getattr(adapter_class, "SOURCE_NAME", None)

        if not source_name:
            raise ValueError(f"Adapter {adapter_class.__name__} must define SOURCE_NAME class attribute")

        cls._adapters[source_name] = adapter_class

    @classmethod
    def create(cls, source_name: str) -> DocumentSourcePort:
        """
        Create a source adapter instance by name.

        Args:
            source_name: The unique name of the source adapter

        Returns:
            DocumentSourcePort: Instance of the requested adapter

        Raises:
            ValueError: If source name is not registered
        """
        adapter_class = cls._adapters.get(source_name)

        if not adapter_class:
            available = ", ".join(cls._adapters.keys())
            raise ValueError(f"Unknown source adapter: '{source_name}'. Available adapters: {available}")

        return adapter_class()

    @classmethod
    def get_adapter_class(cls, source_name: str) -> type[DocumentSourcePort] | None:
        """
        Get the adapter class by name without instantiating.

        Args:
            source_name: The unique name of the source adapter

        Returns:
            Optional[Type[DocumentSourcePort]]: The adapter class or None
        """
        return cls._adapters.get(source_name)

    @classmethod
    def list_sources(cls) -> list[dict[str, Any]]:
        """
        List all available source adapters with their metadata.

        Returns:
            List[Dict]: List of adapter metadata dictionaries
        """
        sources = []

        for _source_name, adapter_class in cls._adapters.items():
            # Create temporary instance to get metadata
            adapter = adapter_class()
            metadata = adapter.get_metadata()
            sources.append(metadata)

        return sources

    @classmethod
    def is_registered(cls, source_name: str) -> bool:
        """
        Check if a source adapter is registered.

        Args:
            source_name: The unique name of the source adapter

        Returns:
            bool: True if registered, False otherwise
        """
        return source_name in cls._adapters

    @classmethod
    def get_registered_names(cls) -> list[str]:
        """
        Get list of all registered source adapter names.

        Returns:
            List[str]: List of registered source names
        """
        return list(cls._adapters.keys())

    @classmethod
    def clear_registry(cls) -> None:
        """
        Clear all registered adapters.

        This is primarily useful for testing.
        """
        cls._adapters.clear()


def register_source_adapter(adapter_class: type[DocumentSourcePort]) -> type[DocumentSourcePort]:
    """
    Decorator to auto-register source adapters.

    Usage:
        @register_source_adapter
        class MySourceAdapter(DocumentSourcePort):
            SOURCE_NAME = "my_source"
            ...

    Args:
        adapter_class: The adapter class to register

    Returns:
        Type[DocumentSourcePort]: The same adapter class (for chaining)
    """
    SourceAdapterFactory.register(adapter_class)
    return adapter_class
