"""Factory for creating document classification adapters.

This factory implements the registry pattern with decorator-based auto-registration.
"""

from typing import Any, ClassVar

from datasift.core.operators.quality.classification.ports.outbound.classification_service import (
    ClassificationServicePort,
)


class ClassificationAdapterFactory:
    """Factory for creating document classification adapters."""

    _registry: ClassVar[dict[str, type[ClassificationServicePort]]] = {}

    @classmethod
    def register(cls, *, adapter_class: type[ClassificationServicePort]) -> type[ClassificationServicePort]:
        """Register an adapter class."""
        if not hasattr(adapter_class, "ADAPTER_NAME") or not adapter_class.ADAPTER_NAME:
            raise ValueError(f"Adapter {adapter_class.__name__} must define ADAPTER_NAME")

        name = adapter_class.ADAPTER_NAME.lower()
        cls._registry[name] = adapter_class
        return adapter_class

    @classmethod
    def create(
        cls,
        *,
        adapter_name: str,
        model_id: str | None = None,
        **adapter_config: Any,
    ) -> ClassificationServicePort:
        """Create an adapter instance."""
        adapter_class = cls._registry.get(adapter_name.lower())
        if not adapter_class:
            available = ", ".join(cls._registry.keys())
            raise ValueError(f"Unknown classification adapter: '{adapter_name}'. Available adapters: {available}")

        return adapter_class(model_id=model_id, **adapter_config)

    @classmethod
    def list_adapters(cls) -> list[str]:
        """List all registered adapter names."""
        return list(cls._registry.keys())


def register_classification_adapter(
    adapter_class: type[ClassificationServicePort],
) -> type[ClassificationServicePort]:
    """Decorator to register a classification adapter."""
    return ClassificationAdapterFactory.register(adapter_class=adapter_class)
