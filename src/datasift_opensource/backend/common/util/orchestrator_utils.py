import os
import json
import shutil
import tempfile
from queue import Queue
from typing import Optional

import pyarrow as pa
import pyarrow.compute as pc

from common.util.constants import DatasiftConstants, OperatorConstants
from common.util.iceberg_util import get_warehouse_path
from common.util.log import get_logger

PREFECT_HOME_PREFIX = "prefect_"
PREFECT_HOME = "PREFECT_HOME"
PREFECT_API_DATABASE_CONNECTION_URL = "PREFECT_API_DATABASE_CONNECTION_URL"
PREFECT_API_SERVICES_FLOW_RUN_NOTIFICATIONS_ENABLED = (
    "PREFECT_API_SERVICES_FLOW_RUN_NOTIFICATIONS_ENABLED"
)
PREFECT_CLOUD_ENABLE_ORCHESTRATION_TELEMETRY = (
    "PREFECT_CLOUD_ENABLE_ORCHESTRATION_TELEMETRY"
)
PREFECT_SERVER_EPHEMERAL_STARTUP_TIMEOUT_SECONDS = (
    "PREFECT_SERVER_EPHEMERAL_STARTUP_TIMEOUT_SECONDS"
)
# Set to "true" to use SQLite with persistent storage and the default Prefect home directory.
# Allows accessing Prefect dashboard for flows review.
PREFECT_DEBUG = "PREFECT_DEBUG"


def create_node_id_to_index_map(*, flow_def: dict) -> dict:
    """
    Return a mapping between each node ID and its corresponding index,
    representing the position where it
    appears in the original JSON node sequence.

    Args:
        flow_def: a dict holding a flow.

    Returns:
        dict: A mapping between node id and its index in the input flow.
    """
    node_id_to_index_map = {}
    index = 0
    for node in flow_def:
        node_id_to_index_map[node["id"]] = index
        index = index + 1
    return node_id_to_index_map


def create_log_folders(job_id, job_run_id, type):
    """
    Created 3 folders, UDP_logs/jobId/JobrunID. The log for that job will be stored there
    """
    # PLACEHOLDER log TILL LOG LOCATION IS DECIDED
    log_location_path = get_warehouse_path(path="")

    log_app_location = DatasiftConstants.UDP_LOGS

    log_job_folder_name = job_id
    log_job_location = os.path.join(
        log_location_path, log_app_location, log_job_folder_name, str(job_run_id)
    )
    os.makedirs(log_job_location, exist_ok=True)
    if type == "job":
        log_job_run_file_name = "job_stats.json"
    elif type == "agg_logs":
        log_job_run_file_name = "flow_execute_aggregated.json"

    log_final_path = os.path.join(log_job_location, log_job_run_file_name)
    return log_final_path


def write_job_logs(job_stats, job_log_final_path):
    with open(job_log_final_path, "w") as file:
        json.dump(job_stats.__dict__, file, indent=4)


# should be called before loading Prefect libraries
def set_prefect_env_variables() -> None:
    os.environ[PREFECT_CLOUD_ENABLE_ORCHESTRATION_TELEMETRY] = "false"
    os.environ[PREFECT_SERVER_EPHEMERAL_STARTUP_TIMEOUT_SECONDS] = "120"
    if not os.getenv(PREFECT_DEBUG):
        # See https://github.com/PrefectHQ/prefect/issues/10188
        os.environ[PREFECT_API_SERVICES_FLOW_RUN_NOTIFICATIONS_ENABLED] = "False"
        # Create a temporary directory for Prefect Home
        os.environ[PREFECT_HOME] = tempfile.mkdtemp(prefix=PREFECT_HOME_PREFIX)
        # force Prefect to use an in-memory SQLite DB
        os.environ[PREFECT_API_DATABASE_CONNECTION_URL] = "sqlite+aiosqlite:///:memory:"


def clean_up_prefect_home() -> None:
    prefect_home = os.getenv(PREFECT_HOME)
    if prefect_home and not os.getenv(PREFECT_DEBUG):
        _safe_rmtree(path=prefect_home, prefix=PREFECT_HOME_PREFIX)


def _safe_rmtree(path: str, prefix: str = None) -> bool:
    """
    Safely remove a directory if it's inside the system temp directory
    and optionally matches a given prefix.

    Args:
        path (str): Directory to remove.
        prefix (str, optional): Require the basename of the directory
                                to start with this prefix (e.g., "prefect_").

    Returns:
        bool: True if the directory was removed, False otherwise.
    """
    logger = get_logger()
    path = os.path.abspath(path)
    temp_root = os.path.abspath(tempfile.gettempdir())

    # Check: must be under system temp directory
    if os.path.commonpath([path, temp_root]) != temp_root:
        logger.warning(f"Refusing to delete {path}: not inside {temp_root}")
        return False

    # Check: prefix (if given)
    if prefix and not os.path.basename(path).startswith(prefix):
        logger.warning(f"Refusing to delete {path}: does not start with '{prefix}'")
        return False

    # Perform safe removal
    if os.path.exists(path):
        shutil.rmtree(path, ignore_errors=True)
        logger.info(f"Deleted tempdir: {path}")
        return True
    else:
        logger.info(f"Path does not exist: {path}")
        return False


# Helper: Ensure schema alignment across tables
def align_table_schema(table: pa.Table, all_cols: dict) -> pa.Table:
    logger = get_logger()
    try:
        for col in all_cols.keys():
            if col not in table.column_names:
                values = pa.array(pa.nulls(table.num_rows), type=all_cols[col])
                table = table.append_column(col, values)
        # Keep consistent column order
        table = table.select(sorted(all_cols))
    except Exception as e:
        logger.warning(f"[WARN] Failed to align schema: {e}")
    return table


# Helper: Combine and align cumulative deleted rows
def combine_cumulative_deleted_rows(deleted_rows: Queue[pa.Table]) -> pa.Table:
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
        combined = pa.concat_tables(aligned_tables, promote=True)
        logger.info(
            f"Combined cumulative deleted rows: {combined.num_rows} rows, {len(all_cols)} columns."
        )
        return combined

    except Exception as e:
        logger.warning(f"[WARN] Failed to combine cumulative deleted rows: {e}")
        return pa.table({})


# Helper: Combine multiple tables safely
def _combine_tables(tables: list[pa.Table], table_type: str) -> Optional[pa.Table]:
    logger = get_logger()
    if not tables:
        return None
    try:
        combined = pa.concat_tables(tables, promote=True)
        # Warn if duplicate IDs
        if OperatorConstants.ID in combined.column_names:
            unique_ids = pc.count_distinct(combined[OperatorConstants.ID]).as_py()
            total_rows = combined.num_rows
            if unique_ids < total_rows:
                logger.warning(
                    f"{table_type} contains {total_rows - unique_ids} duplicate IDs."
                )
        return combined
    except Exception as e:
        logger.warning(f"[WARN] Failed to combine {table_type}: {e}")
        return None


def _total_rows(
    tables: Optional[pa.Table | dict[str, pa.Table] | list[pa.Table]],
) -> int:
    """Returns total rows from pa.Table, list, or dict of pa.Table."""
    if isinstance(tables, pa.Table):
        return tables.num_rows
    if isinstance(tables, dict):
        return sum(tbl.num_rows for tbl in tables.values())
    if isinstance(tables, list):
        return sum(tbl.num_rows for tbl in tables)
    return 0


def update_deleted_rows(
    prev_tables: Optional[pa.Table | dict[str, pa.Table] | list[pa.Table]],
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
        previous_combined = _combine_tables(
            list(prev_tables.values()), "previous tables"
        )
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
        deleted_mask = pc.invert(
            pc.is_in(
                previous_combined[OperatorConstants.ID],
                value_set=current_combined[OperatorConstants.ID],
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


def construct_deleted_rows_table_path(*, job_id: str, job_run_id):
    # table_name = "deleted_rows_table"
    metadata_path = "/unprocessed_docs"
    parquet_file_name = "unprocessed_docs.parquet"
    return os.path.join(
        get_warehouse_path(path=metadata_path), job_id, job_run_id, parquet_file_name
    )
