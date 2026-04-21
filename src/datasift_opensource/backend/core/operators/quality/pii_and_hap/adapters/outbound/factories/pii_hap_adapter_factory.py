"""Factory for creating PII and HAP detection adapters"""

from typing import Any, ClassVar

from core.operators.quality.pii_and_hap.ports.outbound.pii_hap_service import PIIHAPServicePort


class PIIHAPAdapterFactory:
    """Factory for creating PII and HAP detection adapters.

    This factory maintains a registry of available adapters and provides
    methods to create adapter instances and list available adapters.

    Adapters self-register using the @register_pii_hap_adapter decorator.

    Example:
        @register_pii_hap_adapter
        class OllamaAdapter(PIIHAPServicePort):
            ADAPTER_NAME = "ollama"
            ...
    """

    _registry: ClassVar[dict[str, type[PIIHAPServicePort]]] = {}

    @classmethod
    def register(cls, adapter_class: type[PIIHAPServicePort]) -> type[PIIHAPServicePort]:
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
    def create(cls, adapter_name: str, **adapter_config: Any) -> PIIHAPServicePort:
        """Create an adapter instance.

        Args:
            adapter_name: Name of the adapter to create (e.g., 'ollama', 'watsonx', 'dpk')
            **adapter_config: Additional adapter-specific configuration

        Returns:
            Initialized adapter instance

        Raises:
            ValueError: If adapter name is unknown
        """
        adapter_class = cls._registry.get(adapter_name.lower())
        if not adapter_class:
            available = ", ".join(cls._registry.keys())
            raise ValueError(f"Unknown PII/HAP detection adapter: '{adapter_name}'. Available adapters: {available}")

        return adapter_class(**adapter_config)

    @classmethod
    def list_adapters(cls) -> list[str]:
        """List all registered adapter names.

        Returns:
            List of registered adapter names
        """
        return list(cls._registry.keys())


def register_pii_hap_adapter(adapter_class: type[PIIHAPServicePort]) -> type[PIIHAPServicePort]:
    """Decorator to register a PII/HAP detection adapter.

    This decorator automatically registers the adapter class with the factory
    when the module is imported.

    Args:
        adapter_class: Adapter class to register

    Returns:
        The adapter class (unchanged)

    Example:
        @register_pii_hap_adapter
        class OllamaAdapter(PIIHAPServicePort):
            ADAPTER_NAME = "ollama"
            ADAPTER_DISPLAY_NAME = "Ollama LLM"
            ...
    """
    return PIIHAPAdapterFactory.register(adapter_class)
