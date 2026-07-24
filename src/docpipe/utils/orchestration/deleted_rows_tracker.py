"""Utilities for tracking and managing deleted rows across pipeline steps."""

from queue import Queue

import pyarrow as pa
import pyarrow.compute as pc

from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.utils.data.schema_utils import _combine_tables, _total_rows, align_table_schema
from docpipe.utils.infrastructure.logging import get_logger


def combine_cumulative_deleted_rows(deleted_rows: Queue[pa.Table]) -> pa.Table:
    """
    Combine and align cumulative deleted rows from multiple steps.

    Args:
        deleted_rows: Queue containing PyArrow tables of deleted rows

    Returns:
        Combined PyArrow table with aligned schema
    """
    logger = get_logger()

    if not deleted_rows:
        return pa.table({})  # nothing to combine

    try:
        # Collect all column names across all tables
        all_cols = {}
        for tbl in list(deleted_rows.queue):
            for field in tbl.schema:
                all_cols[field.name] = field.type
        # Align schema for each table
        aligned_tables = []
        for tbl in list(deleted_rows.queue):
            aligned_tables.append(align_table_schema(tbl, all_cols))

        # Concatenate aligned tables
        combined = pa.concat_tables(aligned_tables, promote_options="default")
        logger.info(f"Combined cumulative deleted rows: {combined.num_rows} rows, {len(all_cols)} columns.")
        return combined

    except Exception as e:
        logger.warning(f"[WARN] Failed to combine cumulative deleted rows: {e}")
        return pa.table({})


def update_deleted_rows(
    prev_tables: pa.Table | dict[str, pa.Table] | list[pa.Table] | None,
    current_tables: list[pa.Table],
    skip_columns: list[str],
    op,
) -> pa.Table:
    """
    Compares previous and current PyArrow tables across steps to detect deleted rows
    and updates a cumulative deleted-rows table.

    ----------
    Parameters
    ----------
    prev_tables : Optional[pa.Table | dict[str, pa.Table] | list[pa.Table]]
        The tables from the previous step (can be a single table, dict of tables, or list of tables).

    current_tables : list[pa.Table]
        The list of PyArrow Tables for the current step.

    skip_columns : list[str]
        List of column names to exclude while saving deleted rows (for example,
        large data columns such as `"content"`, `"entity"`, etc.).

    op : AbstractOperator
        Current operator object providing config and metadata.

    -------
    Returns
    -------
    pa.Table
        return deleted_rows table (a single PyArrow Table).
    """

    logger = get_logger()
    if _total_rows(prev_tables) == _total_rows(current_tables):
        logger.info("No deleted rows detected.")
        return pa.table({})

    # ---- Combine previous + current ----
    if isinstance(prev_tables, dict):
        previous_combined = _combine_tables(list(prev_tables.values()), "previous tables")
    elif isinstance(prev_tables, list):
        previous_combined = _combine_tables(prev_tables, "previous tables")
    else:
        previous_combined = prev_tables

    current_combined = _combine_tables(current_tables, "current tables")

    if (
        previous_combined is None
        or current_combined is None
        or previous_combined.num_rows == 0
        or current_combined.num_rows == 0
    ):
        return pa.table({})

    # ---- Detect deleted rows ----
    try:
        deleted_mask = pc.invert(  # type: ignore[attr-defined]
            pc.is_in(  # type: ignore[attr-defined]
                previous_combined[OperatorConstants.Columns.ID],
                value_set=current_combined[OperatorConstants.Columns.ID],
            )
        )
        deleted_rows = previous_combined.filter(deleted_mask)
    except Exception as e:
        logger.warning(f"[WARN] Error detecting deleted rows: {e}")
        return pa.table({})

    if deleted_rows.num_rows == 0:
        return pa.table({})

    # ---- Align schema and drop heavy columns ----
    try:
        all_cols = {}
        for tbl in [current_combined, previous_combined]:
            for field in tbl.schema:
                all_cols[field.name] = field.type
        deleted_rows = align_table_schema(deleted_rows, all_cols)

        op_config = getattr(op, "config", {})
        skip_column_names = [op_config.get(name, name) for name in skip_columns]
        keep_cols = [c for c in deleted_rows.column_names if c not in skip_column_names]
        deleted_rows = deleted_rows.select(keep_cols)
    except Exception as e:
        logger.warning(f"[WARN] Schema alignment or column filter failed: {e}")

    # ---- Add deleted step tag ----
    try:
        step_tag = f"{op.id}_{op.name}"
        step_tag_col = pa.array([step_tag] * deleted_rows.num_rows)
        return deleted_rows.append_column("deleted_at_step", step_tag_col)
    except Exception as e:
        logger.warning(f"[WARN] Failed to tag deleted rows: {e}")

    return pa.table({})


__all__ = [
    "combine_cumulative_deleted_rows",
    "update_deleted_rows",
]
