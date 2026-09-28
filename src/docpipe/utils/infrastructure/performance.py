"""Performance measurement and memory management utilities."""

import ctypes
import gc
import os
import sys

import psutil
import pyarrow as pa

from docpipe.core.constants.constants import DocpipeConstants
from docpipe.utils.core.datetime import get_current_timestamp
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger()


def log_elapsed_time(*, start_time, operator: str | None = None, actions: list | None = None):
    """Log elapsed time."""
    elapsed_time = get_current_timestamp() - start_time
    log_message = operator if operator else ""
    log_message = log_message + ":" + ("-".join(actions) if actions else "")
    log_message = log_message + ":" + str(elapsed_time)

    logger.info(log_message, extra={DocpipeConstants.TRACK_PERF: "true"})


def get_pyarrow_table_size_mb(table: pa.Table) -> float:
    """
    Returns the approximate size of the pyarrow Table in MiB.
    Uses table.nbytes (total bytes of buffers)
    """
    if table is None:
        return 0.0

    try:
        return table.nbytes / (1024 * 1024)
    except Exception:
        # Fallback in case nbytes isn't available
        return sum(c.nbytes for c in table.columns) / (1024 * 1024)


def get_process_memory_mb() -> dict[str, float]:
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


def reclaim_memory(*, context: str) -> None:
    """Return freed memory to the operating system, then log what came back.

    Python frees objects, but the allocator keeps the pages for reuse.  Nothing
    in a flow asks for them back, so resident memory ratchets up across flows
    and only drops when the process restarts.

    release_unused covers the PyArrow pool.  malloc_trim covers glibc and is
    Linux-only — there is no libc.so.6 on macOS, which returns pages anyway.
    Both are best-effort; failures are logged, never raised.

    Parameters
    ----------
    context : str
        Short label naming the call site, so the log lines can be told apart
        when this runs more than once per flow.
    """

    def _rss() -> float | None:
        """Return current RSS in MiB, or None if unavailable."""
        try:
            return get_process_memory_mb()["rss_mb"]
        except Exception:
            return None

    rss_before = _rss()
    gc.collect()

    released, trimmed = False, False
    try:
        pa.default_memory_pool().release_unused()
        released = True
    except Exception:
        logger.warning("PyArrow release_unused failed (%s)", context, exc_info=True)

    # glibc only.  macOS and musl have no libc.so.6, and macOS returns freed pages
    # on its own, so skipping there is correct rather than a failure worth warning
    # about.  A real failure on Linux still warns.
    if sys.platform.startswith("linux"):
        try:
            ctypes.CDLL("libc.so.6").malloc_trim(ctypes.c_size_t(0))
            trimmed = True
        except Exception:
            logger.warning("malloc_trim failed (%s)", context, exc_info=True)
    else:
        logger.debug("malloc_trim skipped on %s (%s)", sys.platform, context)

    rss_after = _rss()
    if rss_before is not None and rss_after is not None:
        logger.info(
            "Memory reclaim [%s]: RSS %.1f -> %.1f MiB (recovered %.1f MiB), release_unused=%s malloc_trim=%s",
            context,
            rss_before,
            rss_after,
            rss_before - rss_after,
            released,
            trimmed,
            extra={DocpipeConstants.TRACK_PERF: "true"},
        )
    else:
        logger.info(
            "Memory reclaim [%s]: release_unused=%s malloc_trim=%s (RSS unavailable)",
            context,
            released,
            trimmed,
            extra={DocpipeConstants.TRACK_PERF: "true"},
        )


def log_memory_usage(
    *,
    operator_name: str,
    phase: str,
    table: pa.Table | list[pa.Table] | None = None,
    extra: dict | None = None,
    logger=None,
):
    """
    Logs current memory utilization and PyArrow table size for a given operator and phase.

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
    if table is None:
        return

    process_memory = get_process_memory_mb()
    table_size: float = 0.0
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
        from docpipe.utils.infrastructure.logging import get_logger

        logger = get_logger()
        logger.info(log_fields_str, extra=extra)


def cleanup_pyarrow_buffers(operator_name, phase, table, extra, logger):
    """
    Cleanup PyArrow buffers and log memory usage.

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
