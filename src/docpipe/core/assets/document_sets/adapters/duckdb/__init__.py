"""DuckDB adapters for document sets."""

from docpipe.core.assets.document_sets.adapters.duckdb.data_store import DuckDBDocumentSetStorage
from docpipe.core.assets.document_sets.adapters.duckdb.metadata_repository import DuckDBDocumentSetMetadataRepository

__all__ = [
    "DuckDBDocumentSetMetadataRepository",
    "DuckDBDocumentSetStorage",
]
