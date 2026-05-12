"""Storage layer for datasift.

This module provides storage interfaces and implementations following
a clean architecture pattern.

Structure:
- interfaces/: Storage interface definitions (KeyValueStorage, TableStorage)
- file_system/: Filesystem-based key-value storage implementation
- duck_db/: DuckDB-based storage implementations (key-value and table)
- factory.py: Factory for creating storage instances
- exceptions.py: Storage-specific exceptions
"""

from datasift.storage.duck_db import DuckDBKeyValueStorage, DuckDBTableStorage
from datasift.storage.exceptions import (
    StorageConnectionError,
    StorageException,
    StorageNotFoundError,
    StorageValidationError,
)
from datasift.storage.factory import StorageFactory
from datasift.storage.file_system import FileSystemStorage
from datasift.storage.interfaces import KeyValueStorage, TableStorage

__all__ = [
    "DuckDBKeyValueStorage",
    "DuckDBTableStorage",
    "FileSystemStorage",
    "KeyValueStorage",
    "StorageConnectionError",
    "StorageException",
    "StorageFactory",
    "StorageNotFoundError",
    "StorageValidationError",
    "TableStorage",
]
