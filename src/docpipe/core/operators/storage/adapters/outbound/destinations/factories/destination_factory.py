"""Factory for creating and discovering destination adapters."""

from typing import ClassVar

from docpipe.core.operators.storage.ports.outbound.destination_adapter import DestinationAdapterPort


class DestinationAdapterFactory:
    """
    Registry + factory for destination adapters.
    Mirrors SourceAdapterFactory from the ingest side.

    Adapters self-register via @register_destination_adapter decorator.
    """

    _adapters: ClassVar[dict[str, type[DestinationAdapterPort]]] = {}

    # Alias provider names that map to an existing canonical adapter.
    # ibm_cos uses the S3 adapter with a custom endpoint_url — no separate adapter needed.
    # onedrive uses the SharePoint adapter — identical Graph API drive endpoints, same config shape.
    _ALIASES: ClassVar[dict[str, str]] = {
        "ibm_cos": "s3",
        "onedrive": "sharepoint",
    }

    @classmethod
    def register(cls, adapter_class: type[DestinationAdapterPort]) -> None:
        """Register."""
        dest_name = getattr(adapter_class, "DEST_NAME", None)
        if not dest_name:
            raise ValueError(f"Adapter {adapter_class.__name__} must define DEST_NAME class attribute")
        cls._adapters[dest_name] = adapter_class

    @classmethod
    def create(cls, dest_name: str) -> DestinationAdapterPort:
        """Create."""
        resolved = cls._ALIASES.get(dest_name, dest_name)
        adapter_class = cls._adapters.get(resolved)
        if not adapter_class:
            available = ", ".join(list(cls._adapters.keys()) + list(cls._ALIASES.keys()))
            raise ValueError(f"Unknown destination adapter: '{dest_name}'. Available: {available}")
        return adapter_class()

    @classmethod
    def is_registered(cls, dest_name: str) -> bool:
        """Is registered."""
        return dest_name in cls._adapters or dest_name in cls._ALIASES

    @classmethod
    def get_registered_names(cls) -> list[str]:
        """Get registered names."""
        return list(cls._adapters.keys()) + list(cls._ALIASES.keys())


def register_destination_adapter(
    adapter_class: type[DestinationAdapterPort],
) -> type[DestinationAdapterPort]:
    """
    Decorator to auto-register destination adapters.

    Usage:
        @register_destination_adapter
        class MyAdapter(DestinationAdapterPort):
            DEST_NAME = "my_dest"
    """
    DestinationAdapterFactory.register(adapter_class)
    return adapter_class
