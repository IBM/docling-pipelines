"""DuckDB adapters for document sets."""

from datasift.core.assets.document_sets.adapters.duckdb.data_store import (
    DuckDBDataStore,
    DuckDBDocumentSetDataStore,
)
from datasift.core.assets.document_sets.adapters.duckdb.metadata_repository import (
    DuckDBDocumentSetMetadataRepository,
    DuckDBMetadataRepository,
)

__all__ = [
    "DuckDBDataStore",
    "DuckDBDocumentSetDataStore",
    "DuckDBDocumentSetMetadataRepository",
    "DuckDBMetadataRepository",
]
