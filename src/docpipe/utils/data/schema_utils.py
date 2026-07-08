"""Schema alignment and table combination utilities for PyArrow tables."""

import pyarrow as pa
import pyarrow.compute as pc

from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.utils.infrastructure.logging import get_logger


def align_table_schema(table: pa.Table, all_cols: dict) -> pa.Table:
    """
    Ensure schema alignment across tables by adding missing columns with null values.

    Args:
        table: PyArrow table to align
        all_cols: Dictionary mapping column names to their PyArrow types

    Returns:
        Aligned PyArrow table with all columns from all_cols
    """
    logger = get_logger()
    try:
        for col in all_cols:
            if col not in table.column_names:
                values = pa.array(pa.nulls(table.num_rows), type=all_cols[col])
                table = table.append_column(col, values)
        # Keep consistent column order
        table = table.select(sorted(all_cols))
    except Exception as e:
        logger.warning(f"[WARN] Failed to align schema: {e}")
    return table


def _combine_tables(tables: list[pa.Table], table_type: str) -> pa.Table | None:
    """
    Combine multiple PyArrow tables safely with duplicate ID detection.

    Args:
        tables: List of PyArrow tables to combine
        table_type: Description of table type for logging

    Returns:
        Combined PyArrow table or None if combination fails
    """
    logger = get_logger()
    if not tables:
        return None

    # Filter out None values from the list
    valid_tables = [t for t in tables if t is not None]
    if not valid_tables:
        return None

    try:
        combined = pa.concat_tables(valid_tables, promote_options="default")
        # Warn if duplicate IDs
        if OperatorConstants.Columns.ID in combined.column_names:
            unique_ids = pc.count_distinct(combined[OperatorConstants.Columns.ID]).as_py()  # type: ignore[attr-defined]
            total_rows = combined.num_rows
            if unique_ids < total_rows:
                logger.warning(f"{table_type} contains {total_rows - unique_ids} duplicate IDs.")
        return combined
    except Exception as e:
        logger.warning(f"[WARN] Failed to combine {table_type}: {e}")
        return None


def _total_rows(
    tables: pa.Table | dict[str, pa.Table] | list[pa.Table] | None,
) -> int:
    """
    Returns total rows from pa.Table, list, or dict of pa.Table.

    Args:
        tables: Single table, list of tables, dict of tables, or None

    Returns:
        Total number of rows across all tables
    """
    if isinstance(tables, pa.Table):
        return tables.num_rows
    if isinstance(tables, dict):
        return sum(tbl.num_rows for tbl in tables.values())
    if isinstance(tables, list):
        return sum(tbl.num_rows for tbl in tables)
    return 0


__all__ = [
    "_combine_tables",
    "_total_rows",
    "align_table_schema",
]
