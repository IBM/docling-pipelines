"""Utility functions for DuckDB storage."""

import pyarrow as pa

from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger(__name__)


def pyarrow_to_duckdb_type(pa_type: pa.DataType) -> str:  # NOSONAR python:S3776
    """
    Convert PyArrow type to DuckDB type.

    Args:
        pa_type: PyArrow data type

    Returns:
        DuckDB type string
    """
    if pa.types.is_string(pa_type) or pa.types.is_large_string(pa_type):
        return "VARCHAR"
    elif pa.types.is_int64(pa_type):
        return "BIGINT"
    elif pa.types.is_int32(pa_type):
        return "INTEGER"
    elif pa.types.is_int16(pa_type):
        return "SMALLINT"
    elif pa.types.is_int8(pa_type):
        return "TINYINT"
    elif pa.types.is_float64(pa_type):
        return "DOUBLE"
    elif pa.types.is_float32(pa_type):
        return "FLOAT"
    elif pa.types.is_boolean(pa_type):
        return "BOOLEAN"
    elif pa.types.is_binary(pa_type) or pa.types.is_large_binary(pa_type):
        return "BLOB"
    elif pa.types.is_timestamp(pa_type):
        return "TIMESTAMP"
    elif pa.types.is_date(pa_type):
        return "DATE"
    elif pa.types.is_time(pa_type):
        return "TIME"
    elif pa.types.is_list(pa_type) or pa.types.is_large_list(pa_type):
        return "JSON"
    elif pa.types.is_struct(pa_type):
        return "JSON"
    elif pa.types.is_map(pa_type):
        return "JSON"
    else:
        logger.warning(f"Unknown PyArrow type {pa_type}, defaulting to VARCHAR")
        return "VARCHAR"
