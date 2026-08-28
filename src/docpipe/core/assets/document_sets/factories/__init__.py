"""Factory classes for document set adapters."""

__all__ = ["DataStoreFactory"]


def __getattr__(name: str):
    if name == "DataStoreFactory":
        from docpipe.core.assets.document_sets.factories.data_store_factory import (
            DataStoreFactory,
        )

        return DataStoreFactory
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
