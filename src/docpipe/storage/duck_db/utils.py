"""Utility functions for DuckDB storage."""

import pyarrow as pa

from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger(__name__)


def pyarrow_to_duckdb_type(pa_type: pa.DataType) -> str:
    """
    Convert PyArrow type to DuckDB type.

    Args:
        pa_type: PyArrow data type

    Returns:
        DuckDB type string
    """
    if pa.types.is_string(pa_type) or pa.types.is_large_string(pa_type):
        return "VARCHAR"
    if pa.types.is_int64(pa_type):
        return "BIGINT"
    if pa.types.is_int32(pa_type):
        return "INTEGER"
    if pa.types.is_int16(pa_type):
        return "SMALLINT"
    if pa.types.is_int8(pa_type):
        return "TINYINT"
    if pa.types.is_float64(pa_type):
        return "DOUBLE"
    if pa.types.is_float32(pa_type):
        return "FLOAT"
    if pa.types.is_boolean(pa_type):
        return "BOOLEAN"
    if pa.types.is_binary(pa_type) or pa.types.is_large_binary(pa_type):
        return "BLOB"
    if pa.types.is_timestamp(pa_type):
        return "TIMESTAMP"
    if pa.types.is_date(pa_type):
        return "DATE"
    if pa.types.is_time(pa_type):
        return "TIME"
    if pa.types.is_list(pa_type) or pa.types.is_large_list(pa_type):
        return "JSON"
    if pa.types.is_struct(pa_type):
        return "JSON"
    if pa.types.is_map(pa_type):
        return "JSON"
    logger.warning(f"Unknown PyArrow type {pa_type}, defaulting to VARCHAR")
    return "VARCHAR"
