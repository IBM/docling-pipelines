"""
Unit tests for report utility functions

Tests cover:
- Report path generation
- Report reading from storage
- Report existence checking
- CSV streaming response creation
"""

from pathlib import Path

import pytest

from docpipe.core.job_management.application.services.report_utils import (
    create_csv_streaming_response,
    get_report_path,
    read_report_from_storage,
)

# Test constants
JOB_ID = "test-job-123"
JOB_RUN_ID = "test-run-456"


class TestGetReportPath:
    """Test report path generation."""

    def test_get_report_path_with_job_id(self):
        """Report path includes job_id when provided."""
        path = get_report_path(job_run_id=JOB_RUN_ID, job_id=JOB_ID)

        assert JOB_ID in path
        assert JOB_RUN_ID in path
        assert path.endswith(".csv")
        assert f"job_report_{JOB_RUN_ID}.csv" in path

    def test_get_report_path_structure(self):
        """Report path has correct directory structure."""
        path = get_report_path(job_run_id=JOB_RUN_ID, job_id=JOB_ID)

        # Should be: data/{job_id}/{job_run_id}/job_report_{job_run_id}.csv
        path_parts = Path(path).parts
        assert JOB_ID in path_parts
        assert JOB_RUN_ID in path_parts
        assert f"job_report_{JOB_RUN_ID}.csv" in path_parts


class TestReadReportFromStorage:
    """Test reading report from storage."""

    def test_read_report_success(self, tmp_path):
        """Successfully read report content from file."""
        report_path = tmp_path / "test_report.csv"
        csv_content = "GUID,File name,Status\ndoc1,test.pdf,Ingested\n"
        report_path.write_text(csv_content)

        content, exists = read_report_from_storage(str(report_path))

        assert exists is True
        assert content == csv_content

    def test_read_report_not_found(self, tmp_path):
        """Returns empty content when file not found."""
        report_path = tmp_path / "nonexistent.csv"

        content, exists = read_report_from_storage(str(report_path))

        assert exists is False
        assert content == ""

    def test_read_report_handles_errors(self, tmp_path):
        """Handles read errors gracefully."""
        report_path = tmp_path / "test_report.csv"
        report_path.write_text("content")
        report_path.chmod(0o000)  # Remove read permissions

        try:
            content, exists = read_report_from_storage(str(report_path))
            assert exists is False
            assert content == ""
        finally:
            report_path.chmod(0o644)  # Restore permissions


class TestCreateCSVStreamingResponse:
    """Test CSV streaming response creation."""

    def test_create_streaming_response(self):
        """Creates streaming response with correct headers."""
        csv_content = "GUID,File name\ndoc1,test.pdf\n"

        response = create_csv_streaming_response(content=csv_content, job_run_id=JOB_RUN_ID)

        assert response.media_type == "text/csv"
        assert "Content-Disposition" in response.headers
        assert f"job_report_{JOB_RUN_ID}.csv" in response.headers["Content-Disposition"]
        assert "attachment" in response.headers["Content-Disposition"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
