"""Storage backends and abstractions."""

from storage.base_storage import BaseStorage
from storage.duckdb_storage import DuckDBStorage

__all__ = ["BaseStorage", "DuckDBStorage"]
