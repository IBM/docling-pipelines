"""Factory classes for document set adapters.

This module provides lazy exports for factory classes to avoid import-time
cycles during adapter registration.
"""

__all__ = ["DataStoreFactory", "MetadataRepositoryFactory"]


def __getattr__(name: str):
    if name == "MetadataRepositoryFactory":
        from docpipe.core.assets.document_sets.factories.metadata_repository_factory import (
            MetadataRepositoryFactory,
        )

        return MetadataRepositoryFactory
    if name == "DataStoreFactory":
        from docpipe.core.assets.document_sets.factories.data_store_factory import (
            DataStoreFactory,
        )

        return DataStoreFactory
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
