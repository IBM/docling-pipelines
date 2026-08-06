"""
Shared thread pool executor for background tasks.

This module owns the single module-level ThreadPoolExecutor used for
background work (e.g. report generation) that must survive beyond the
lifetime of any individual thread or request. Centralising it here avoids
circular imports between abstract_orchestrator and flow_execution_event_handler.
"""

import os
from concurrent.futures import ThreadPoolExecutor

# Default max_workers for background task executor.
# 20 workers matches the previous value in abstract_orchestrator and provides
# sufficient capacity for concurrent report generation tasks. Adjust via the
# DOCPIPE_REPORT_WORKERS environment variable if needed for your deployment.
DEFAULT_REPORT_WORKERS = 20

_max_workers = int(os.getenv("DOCPIPE_REPORT_WORKERS", str(DEFAULT_REPORT_WORKERS)))

thread_pool_executor = ThreadPoolExecutor(max_workers=_max_workers)
