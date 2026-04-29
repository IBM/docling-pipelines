"""Storage backends and abstractions."""

from datasift.storage.base_storage import BaseStorage
from datasift.storage.duckdb_storage import DuckDBStorage

__all__ = ["BaseStorage", "DuckDBStorage"]
