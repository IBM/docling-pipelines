"""Data utilities for PyArrow table operations, schema management, and incremental updates."""

from .incremental_update import IncrementalUpdateUtil
from .pyarrow_handler import (
    BaseParquetTableHandler,
    CpdParquetTableHandler,
    get_parquet_table_handler,
)
from .schema_utils import _combine_tables, _total_rows, align_table_schema
from .transform import TransformUtils

__all__ = [
    # PyArrow Handler
    "BaseParquetTableHandler",
    "CpdParquetTableHandler",
    # Incremental Update
    "IncrementalUpdateUtil",
    # Transform Utils
    "TransformUtils",
    "_combine_tables",
    "_total_rows",
    # Schema Utils
    "align_table_schema",
    "get_parquet_table_handler",
]

# Made with Bob
