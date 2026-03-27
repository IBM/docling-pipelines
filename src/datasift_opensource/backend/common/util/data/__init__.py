"""Data utilities for PyArrow table operations, schema management, and incremental updates."""

from .incremental_update import IncrementalUpdateUtil
from .pyarrow_handler import (
    BaseParquetTableHandler,
    CpdParquetTableHandler,
    get_parquet_table_handler,
)
from .schema_utils import _combine_tables, _total_rows, align_table_schema
from .transform import HAS_TRANSFORM_UTILS, TransformUtils

__all__ = [
    # PyArrow Handler
    "BaseParquetTableHandler",
    "CpdParquetTableHandler",
    "get_parquet_table_handler",
    # Transform Utils
    "TransformUtils",
    "HAS_TRANSFORM_UTILS",
    # Schema Utils
    "align_table_schema",
    "_combine_tables",
    "_total_rows",
    # Incremental Update
    "IncrementalUpdateUtil",
]

# Made with Bob
