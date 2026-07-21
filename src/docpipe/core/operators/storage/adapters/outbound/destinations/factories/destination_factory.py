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

    @classmethod
    def register(cls, adapter_class: type[DestinationAdapterPort]) -> None:
        dest_name = getattr(adapter_class, "DEST_NAME", None)
        if not dest_name:
            raise ValueError(f"Adapter {adapter_class.__name__} must define DEST_NAME class attribute")
        cls._adapters[dest_name] = adapter_class

    @classmethod
    def create(cls, dest_name: str) -> DestinationAdapterPort:
        adapter_class = cls._adapters.get(dest_name)
        if not adapter_class:
            available = ", ".join(cls._adapters.keys())
            raise ValueError(f"Unknown destination adapter: '{dest_name}'. Available: {available}")
        return adapter_class()

    @classmethod
    def is_registered(cls, dest_name: str) -> bool:
        return dest_name in cls._adapters

    @classmethod
    def get_registered_names(cls) -> list[str]:
        return list(cls._adapters.keys())


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
