import gc
import os

import psutil
import pyarrow as pa

from common.constants.constants import DatasiftConstants
from common.models.session_info import get_session_info
from common.util.core.datetime import get_current_timestamp
from common.util.infrastructure.logging import get_logger

logger = get_logger()


def log_elapsed_time(*, start_time, operator: str | None = None, actions: list | None = None):
    if get_session_info().track_perf:
        elapsed_time = get_current_timestamp() - start_time
        log_message = operator if operator else ""
        log_message = log_message + ":" + ("-".join(actions) if actions else "")
        log_message = log_message + ":" + str(elapsed_time)

        logger.info(log_message, extra={DatasiftConstants.TRACK_PERF: "true"})


def get_pyarrow_table_size_mb(table: pa.Table) -> float:  # pragma: no cover # NOSONAR
    """
    Returns the approximate size of the pyarrow Table in MiB.
    Uses table.nbytes (total bytes of buffers)
    """
    if table is None:
        return 0.0
    spark_runtime: str = os.environ.get("IS_SPARK_RUNTIME", "FALSE").upper()
    try:
        if spark_runtime == "TRUE":
            return 1 / (1024 * 1024)
        return table.nbytes / (1024 * 1024)
    except Exception:
        # Fallback in case nbytes isn't available
        if spark_runtime == "TRUE":
            return sum(1 for _ in table.columns) / (1024 * 1024)
        return sum(c.nbytes for c in table.columns) / (1024 * 1024)


def get_process_memory_mb() -> dict[str, float]:  # pragma: no cover # NOSONAR
    """
    Returns current process memory metrics in MiB: rss and vms.
    """
    proc = psutil.Process(os.getpid())
    vm = psutil.virtual_memory()
    mem_info = proc.memory_info()
    rss = mem_info.rss / (1024 * 1024)
    vms = mem_info.vms / (1024 * 1024)
    available_mb = vm.available / (1024 * 1024)
    total_mb = vm.total / (1024 * 1024)
    used_percent = vm.percent

    return {
        "rss_mb": round(rss, 2),
        "vms_mb": round(vms, 2),
        "available_mb": available_mb,
        "total_mb": total_mb,
        "used_percent": used_percent,
    }


def log_memory_usage(
    *,
    operator_name: str,
    phase: str,
    table: pa.Table | list[pa.Table] | None = None,
    extra: dict | None = None,
    logger=None,
):  # pragma: no cover # NOSONAR
    """
    Logs current memory utilization and PyArrow table size for a given operator and phase.
    Only logs if get_session_info().track_perf is enabled.

    Parameters
    ----------
    operator_name : str
        Name of the operator
    phase : str
        Current phase of operation
    table : pa.Table | list[pa.Table] | None
        PyArrow table(s) to measure
    extra : dict | None
        Extra logging context
    logger : Logger | None
        Logger instance to use
    """
    if not get_session_info().track_perf:
        return

    if not table:
        return

    process_memory = get_process_memory_mb()
    table_size = 0
    no_of_tables = 0
    if isinstance(table, list):
        no_of_tables = len(table)
        for t in table:
            table_size += get_pyarrow_table_size_mb(t)
    else:
        no_of_tables = 1
        table_size = get_pyarrow_table_size_mb(table)

    log_fields_str = (
        f"Memory Stats: [{operator_name}] {phase} | RSS: {process_memory['rss_mb']} MiB | VMS: {process_memory['vms_mb']} MiB | PyArrow table(s) {no_of_tables} of size: {round(table_size, 2)} MiB "
        f"| Available Memory: {process_memory['available_mb']} | Total Memory: {process_memory['total_mb']} | Used Percentage: {process_memory['used_percent']}"
    )
    if logger:
        logger.info(log_fields_str, extra=extra)
    else:
        from common.util.infrastructure.logging import get_logger

        logger = get_logger()
        logger.info(log_fields_str, extra=extra)


def cleanup_pyarrow_buffers(operator_name, phase, table, extra, logger):  # pragma: no cover # NOSONAR
    """
    Cleanup PyArrow buffers and log memory usage.
    Only performs cleanup if get_session_info().track_perf is enabled.

    Parameters
    ----------
    operator_name : str
        Name of the operator
    phase : str
        Current phase of operation
    table : pa.Table | list[pa.Table] | None
        PyArrow table(s) to measure
    extra : dict | None
        Extra logging context
    logger : Logger | None
        Logger instance to use
    """
    if not get_session_info().track_perf:
        return

    log_memory_usage(
        operator_name=operator_name,
        phase=phase,
        table=table,
        extra=extra,
        logger=logger,
    )
    pool = pa.default_memory_pool()
    pool.release_unused()  # free up unused buffer memory
    gc.collect()
