"""Factory for creating language detection adapters.

This factory implements the registry pattern with decorator-based auto-registration,
following the same pattern as the embeddings operators' LLM adapter factory.
"""

from typing import ClassVar

from docpipe.core.operators.quality.language_detection.ports.outbound.language_service import LanguageServicePort


class LanguageAdapterFactory:
    """Factory for creating language detection adapters.

    This factory maintains a registry of available adapters and provides
    methods to create adapter instances and list available adapters.

    Adapters self-register using the @register_language_adapter decorator.

    Example:
        @register_language_adapter
        class LangdetectAdapter(LanguageServicePort):
            ADAPTER_NAME = "langdetect"
            ...
    """

    _registry: ClassVar[dict[str, type[LanguageServicePort]]] = {}

    @classmethod
    def register(cls, adapter_class: type[LanguageServicePort]) -> type[LanguageServicePort]:
        """Register an adapter class.

        Args:
            adapter_class: Adapter class to register

        Returns:
            The adapter class (for decorator chaining)

        Raises:
            ValueError: If adapter doesn't define ADAPTER_NAME
        """
        if not hasattr(adapter_class, "ADAPTER_NAME") or not adapter_class.ADAPTER_NAME:
            raise ValueError(f"Adapter {adapter_class.__name__} must define ADAPTER_NAME")

        name = adapter_class.ADAPTER_NAME.lower()
        cls._registry[name] = adapter_class
        return adapter_class

    @classmethod
    def create(cls, adapter_name: str, **adapter_config) -> LanguageServicePort:
        """Create an adapter instance.

        Args:
            adapter_name: Name of the adapter to create (e.g., 'langdetect', 'fasttext')
            **adapter_config: Additional adapter-specific configuration

        Returns:
            Initialized adapter instance

        Raises:
            ValueError: If adapter name is unknown
        """
        adapter_class = cls._registry.get(adapter_name.lower())
        if not adapter_class:
            available = ", ".join(cls._registry.keys())
            raise ValueError(f"Unknown language detection adapter: '{adapter_name}'. Available adapters: {available}")

        return adapter_class(**adapter_config)

    @classmethod
    def list_adapters(cls) -> list[str]:
        """List all registered adapter names.

        Returns:
            List of registered adapter names
        """
        return list(cls._registry.keys())


def register_language_adapter(adapter_class: type[LanguageServicePort]) -> type[LanguageServicePort]:
    """Decorator to register a language detection adapter.

    This decorator automatically registers the adapter class with the factory
    when the module is imported.

    Args:
        adapter_class: Adapter class to register

    Returns:
        The adapter class (unchanged)

    Example:
        @register_language_adapter
        class LangdetectAdapter(LanguageServicePort):
            ADAPTER_NAME = "langdetect"
            ADAPTER_DISPLAY_NAME = "langdetect"
            ...
    """
    return LanguageAdapterFactory.register(adapter_class)
