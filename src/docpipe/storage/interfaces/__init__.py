"""Storage interfaces for docpipe."""

from docpipe.storage.interfaces.key_value_storage import KeyValueStorage
from docpipe.storage.interfaces.table_storage import TableStorage

__all__ = [
    "KeyValueStorage",
    "TableStorage",
]
