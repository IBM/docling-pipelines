"""Storage port interfaces for docpipe."""

from docpipe.storage.interfaces.content_storage_port import ContentStoragePort
from docpipe.storage.interfaces.key_value_storage_port import KeyValueStoragePort
from docpipe.storage.interfaces.table_storage_port import TableStoragePort

__all__ = [
    "ContentStoragePort",
    "KeyValueStoragePort",
    "TableStoragePort",
]
