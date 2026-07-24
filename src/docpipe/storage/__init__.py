"""Storage layer for docpipe.

This module provides storage interfaces and implementations following
a clean architecture pattern.

Structure:
- interfaces/: Storage interface definitions (KeyValueStorage, TableStorage)
- file_system/: Filesystem-based key-value storage implementation
- duck_db/: DuckDB-based storage implementations (key-value and table)
- factory.py: Factory for creating storage instances
- exceptions.py: Storage-specific exceptions
"""

from docpipe.storage.duck_db import DuckDBKeyValueStorage, DuckDBTableStorage
from docpipe.storage.exceptions import (
    StorageConnectionError,
    StorageException,
    StorageNotFoundError,
    StorageValidationError,
)
from docpipe.storage.factory import StorageFactory
from docpipe.storage.file_system import FileSystemStorage
from docpipe.storage.interfaces import KeyValueStorage, TableStorage

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
