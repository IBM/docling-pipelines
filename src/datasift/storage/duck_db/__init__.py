"""DuckDB storage implementation."""

from datasift.storage.duck_db.key_value_storage import DuckDBKeyValueStorage
from datasift.storage.duck_db.table_storage import DuckDBTableStorage

__all__ = [
    "DuckDBKeyValueStorage",
    "DuckDBTableStorage",
]
