"""Storage layer for docpipe.

This module provides storage interfaces (ports) and implementations following
a clean architecture pattern.

Structure:
- interfaces/: Storage port definitions (KeyValueStoragePort, TableStoragePort, ContentStoragePort)
- file_system/: Filesystem-based storage implementations
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
from docpipe.storage.file_system import ContentFileSystemStorage, KeyValueFileSystemStorage
from docpipe.storage.interfaces import ContentStoragePort, KeyValueStoragePort, TableStoragePort

__all__ = [
    "ContentFileSystemStorage",
    "ContentStoragePort",
    "DuckDBKeyValueStorage",
    "DuckDBTableStorage",
    "KeyValueFileSystemStorage",
    "KeyValueStoragePort",
    "StorageConnectionError",
    "StorageException",
    "StorageFactory",
    "StorageNotFoundError",
    "StorageValidationError",
    "TableStoragePort",
]
