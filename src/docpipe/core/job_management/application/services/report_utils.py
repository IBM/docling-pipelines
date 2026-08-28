"""
Report Utility Functions

Helper functions for job report generation, storage, and retrieval.
Report read/write and data-availability checks are delegated to the
ContentStoragePort resolved via ContentStorageFactory so that storage backends
(filesystem, COS, etc.) can be swapped without modifying this module.

All functions read job_id and job_run_id from SessionInfo so callers
do not need to pass them explicitly.
"""

from __future__ import annotations

from fastapi.responses import StreamingResponse

from docpipe.core.models.session_info import get_session_info
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger()

_REPORT_FILENAME_TEMPLATE = "job_report_{job_run_id}.csv"


def _report_collection(*, job_id: str, job_run_id: str) -> str:
    """
    Return the sub-path (relative to base_dir) where reports are stored.

    Resolves to: {base_dir}/{job_id}/{job_run_id}/
    """
    return f"{job_id}/{job_run_id}"


def _report_file_name(*, job_run_id: str) -> str:
    """Return the file name for a job run report."""
    return _REPORT_FILENAME_TEMPLATE.format(job_run_id=job_run_id)


def read_report_from_storage() -> str:
    """
    Read report content via the configured storage adapter.

    Reads job_id and job_run_id from SessionInfo.

    Returns:
        CSV content as string, or empty string if not found.
    """
    from docpipe.core.job_management.adapters.config.report_storage_factory import get_report_storage

    session = get_session_info()
    return get_report_storage().read_text(
        collection=_report_collection(job_id=session.job_id, job_run_id=session.job_run_id),
        file_name=_report_file_name(job_run_id=session.job_run_id),
    )


def create_csv_streaming_response(*, content: str, job_run_id: str) -> StreamingResponse:
    """
    Create a FastAPI StreamingResponse for CSV download.

    Args:
        content: CSV content as string
        job_run_id: Job run ID (used for filename)

    Returns:
        StreamingResponse configured for CSV download
    """
    import io

    return StreamingResponse(
        io.StringIO(content),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="job_report_{job_run_id}.csv"'},
    )


def check_parquet_availability() -> tuple[bool, str]:
    """
    Check if data is available for report generation.

    Delegates to ``ContentStoragePort.check_data_availability()`` so each
    backend (filesystem, COS, S3, etc.) applies its own check without
    any changes to this module.

    Reads job_id and job_run_id from SessionInfo.

    Returns:
        Tuple of (is_available: bool, error_message: str)
    """
    from docpipe.core.job_management.adapters.config.report_storage_factory import get_report_storage

    session = get_session_info()
    collection = _report_collection(job_id=session.job_id, job_run_id=session.job_run_id)
    return get_report_storage().check_data_availability(collection=collection)
