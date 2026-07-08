"""
Report Utility Functions

Helper functions for job report generation, storage, and retrieval.
Adapted for docling-pipelines - uses local filesystem only, no CP4D/CAMS dependencies.
"""

import os

from fastapi.responses import StreamingResponse

from docpipe.utils.infrastructure.filesystem import get_data_path
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger()


def get_report_path(*, job_run_id: str, job_id: str) -> str:
    """
    Get the file path for a job run report.

    The report is saved in the same directory as job logs:
    data/{job_id}/{job_run_id}/job_report_{job_run_id}.csv

    Args:
        job_run_id: Job run ID
        job_id: Job ID (required)

    Returns:
        Full path to the report CSV file
    """
    filename = f"job_report_{job_run_id}.csv"
    job_dir = os.path.join(get_data_path(), job_id, job_run_id)
    return os.path.join(job_dir, filename)


def read_report_from_storage(report_path: str) -> tuple[str, bool]:
    """
    Read report content from file storage.

    Args:
        report_path: Path to the report file

    Returns:
        Tuple of (report_content, exists)
        - report_content: CSV content as string (empty if not found)
        - exists: True if file exists, False otherwise
    """
    try:
        if not os.path.exists(report_path):
            logger.debug(f"Report file not found: {report_path}")
            return "", False

        with open(report_path, encoding="utf-8") as f:
            content = f.read()

        logger.debug(f"Successfully read report from: {report_path}")
        return content, True

    except Exception as e:
        logger.error(f"Error reading report from {report_path}: {e}")
        return "", False


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

    # Create streaming response
    response = StreamingResponse(
        io.StringIO(content),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="job_report_{job_run_id}.csv"'},
    )

    return response


def check_parquet_availability(*, job_run_id: str, job_id: str) -> tuple[bool, str]:
    """
    Check if parquet files are available for report generation.

    This is a lightweight check that verifies the ingest parquet file exists
    before doing expensive operations like fetching full job_stats.

    Args:
        job_run_id: Job run ID
        job_id: Job ID

    Returns:
        Tuple of (is_available: bool, error_message: str)
    """
    from pathlib import Path

    # Construct expected data directory path
    # Pattern: data/{job_id}/{job_run_id}/data/
    data_dir = Path("data") / job_id / job_run_id / "data"

    # Check if the data directory exists
    if not data_dir.exists():
        return False, f"Data directory not found: {data_dir}"

    # Look for ingest operator parquet file (could be ingest_0, ingest_local_0, etc.)
    ingest_dirs = list(data_dir.glob("ingest*_0"))
    if not ingest_dirs:
        return False, f"No ingest operator directory found in {data_dir}"

    # Check if parquet file exists in any ingest directory
    for ingest_dir in ingest_dirs:
        parquet_file = ingest_dir / "output.parquet"
        if parquet_file.exists():
            logger.info(f"Found ingest parquet file: {parquet_file}")
            return True, ""

    return False, f"No ingest parquet file found in {data_dir}"


def generate_report_on_demand(*, job_run_id: str, job_stats, job_stats_service) -> str:
    """
    Generate a report on-demand for a completed job run.

    This function encapsulates all business logic for report generation including:
    - Fetching flow definition
    - Extracting DAG nodes
    - Generating the report
    - Saving to storage

    Args:
        job_run_id: Job run ID
        job_stats: JobStats object (must include node_stats)
        job_stats_service: Service for fetching flow definition

    Returns:
        CSV content as string

    Raises:
        Exception: If report generation fails
    """
    from docpipe.core.job_management.application.services.report_generator import JobReportGenerator

    logger.info(f"Generating report on-demand for job run {job_run_id}")

    try:
        # Fetch flow definition to extract DAG nodes
        flow_definition = job_stats_service.get_flow_definition(job_run_id=job_run_id)
        dag_nodes = flow_definition.get("dag", []) if flow_definition else None

        # Generate report
        generator = JobReportGenerator(job_stats=job_stats, dag_nodes=dag_nodes)
        csv_content = generator.generate_csv_content()

        # Save to file for future requests
        report_path = get_report_path(job_run_id=job_run_id, job_id=job_stats.job_id)
        generator.save_report_to_file(report_path)

        logger.info(f"On-demand report generated and saved: {report_path}")
        return csv_content

    except Exception as e:
        logger.error(f"Failed to generate on-demand report for {job_run_id}: {e}", exc_info=True)
        raise
