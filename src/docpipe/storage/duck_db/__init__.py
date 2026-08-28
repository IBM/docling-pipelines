"""DuckDB storage implementation."""

from docpipe.storage.duck_db.duckdb_key_value_storage import DuckDBKeyValueStorage
from docpipe.storage.duck_db.duckdb_table_storage import DuckDBTableStorage

__all__ = [
    "DuckDBKeyValueStorage",
    "DuckDBTableStorage",
]
