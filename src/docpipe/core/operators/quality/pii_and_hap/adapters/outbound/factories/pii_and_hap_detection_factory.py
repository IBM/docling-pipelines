# Copyright IBM Corp. 2026
# SPDX-License-Identifier: Apache-2.0

"""Factory for creating PII and HAP detection adapters.

Implements the registry pattern with decorator-based auto-registration.
"""

from typing import ClassVar

from docpipe.core.operators.quality.pii_and_hap.ports.outbound.pii_and_hap_detection_port import (
    PIIAndHAPDetectionPort,
)
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger(__name__)


class PIIAndHAPDetectionFactory:
    """Factory for creating PII/HAP detection adapters.

    Maintains a registry of available adapters keyed by ``ADAPTER_NAME``.
    Adapters self-register at import time via the
    ``@register_pii_and_hap_detection_adapter`` decorator.

    Example::

        @register_pii_and_hap_detection_adapter
        class MyAdapter(PIIAndHAPDetectionPort):
            ADAPTER_NAME = "myprovider"
            ...

        adapter = PIIAndHAPDetectionFactory.create("myprovider", model_id="...", provider_config={})
    """

    _registry: ClassVar[dict[str, type[PIIAndHAPDetectionPort]]] = {}

    @classmethod
    def register(cls, adapter_class: type[PIIAndHAPDetectionPort]) -> type[PIIAndHAPDetectionPort]:
        """Register an adapter class.

        Args:
            adapter_class: Adapter class to register.  Must define ``ADAPTER_NAME``.

        Returns:
            The adapter class unchanged (allows use as a decorator).

        Raises:
            ValueError: If the adapter class does not define ``ADAPTER_NAME``.
        """
        if not hasattr(adapter_class, "ADAPTER_NAME") or not adapter_class.ADAPTER_NAME:
            raise ValueError(f"Adapter {adapter_class.__name__} must define ADAPTER_NAME")

        name = adapter_class.ADAPTER_NAME.lower()
        cls._registry[name] = adapter_class
        logger.debug("Registered PII/HAP detection adapter: %s", name)
        return adapter_class

    @classmethod
    def create(cls, provider: str, *, model_id: str, provider_config: dict) -> PIIAndHAPDetectionPort:
        """Create a PII/HAP detection adapter instance.

        Args:
            provider: Provider name — must match an adapter's ``ADAPTER_NAME``.
            model_id: Model identifier forwarded to the adapter.
            provider_config: Provider-specific configuration dict.

        Returns:
            Initialised adapter implementing ``PIIAndHAPDetectionPort``.

        Raises:
            ValueError: If ``provider`` is not registered.  The error message
                lists all currently registered provider names.
        """
        key = provider.lower()
        adapter_class = cls._registry.get(key)
        if not adapter_class:
            available = ", ".join(sorted(cls._registry.keys()))
            raise ValueError(f"Unknown PII/HAP detection provider: '{provider}'. Registered providers: {available}")

        logger.debug("Creating PII/HAP detection adapter: %s", key)
        return adapter_class(model_id=model_id, provider_config=provider_config)

    @classmethod
    def list_adapters(cls) -> list[str]:
        """Return sorted list of all registered provider names."""
        return sorted(cls._registry.keys())


def register_pii_and_hap_detection_adapter(
    adapter_class: type[PIIAndHAPDetectionPort],
) -> type[PIIAndHAPDetectionPort]:
    """Decorator that registers a PII/HAP detection adapter with the factory.

    Usage::

        @register_pii_and_hap_detection_adapter
        class WatsonxPIIAndHAPAdapter(PIIAndHAPDetectionPort):
            ADAPTER_NAME = "watsonx"
            ...

    Args:
        adapter_class: The adapter class to register.

    Returns:
        The adapter class unchanged (allows decorator chaining).
    """
    return PIIAndHAPDetectionFactory.register(adapter_class)
