"""Document set adapters for various storage backends.

This module imports all adapter implementations to trigger their registration
with the factory classes.
"""

# Import DuckDB adapters to trigger registration
from docpipe.core.assets.document_sets.adapters.duckdb import (
    DuckDBDocumentSetDataStore,
    DuckDBDocumentSetMetadataRepository,
)

__all__ = [
    "DuckDBDocumentSetDataStore",
    "DuckDBDocumentSetMetadataRepository",
]
