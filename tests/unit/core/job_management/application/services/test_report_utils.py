"""
Unit tests for report utility functions

Tests cover:
- Report path generation
- Report reading from storage
- Report existence checking
- CSV streaming response creation
"""

from unittest.mock import Mock, patch

import pytest

from docpipe.core.job_management.application.services.report_utils import (
    create_csv_streaming_response,
    read_report_from_storage,
)
from docpipe.core.models.session_info import create_session_info

# Test constants
JOB_ID = "test-job-123"
JOB_RUN_ID = "test-run-456"

_STORAGE_FACTORY = "docpipe.core.job_management.adapters.config.report_storage_factory.get_report_storage"


class TestReadReportFromStorage:
    """Test reading report from storage via the adapter."""

    def test_read_report_delegates_to_adapter(self):
        """read_report_from_storage delegates to the ContentStoragePort adapter."""
        create_session_info(job_id=JOB_ID, job_run_id=JOB_RUN_ID)
        csv_content = "GUID,File name,Status\ndoc1,test.pdf,Ingested\n"
        mock_adapter = Mock()
        mock_adapter.read_text.return_value = csv_content

        with patch(_STORAGE_FACTORY, return_value=mock_adapter):
            content = read_report_from_storage()

        assert content == csv_content
        mock_adapter.read_text.assert_called_once_with(
            collection=f"{JOB_ID}/{JOB_RUN_ID}", file_name=f"job_report_{JOB_RUN_ID}.csv"
        )

    def test_read_report_not_found(self):
        """Returns empty string when report does not exist."""
        create_session_info(job_id=JOB_ID, job_run_id=JOB_RUN_ID)
        mock_adapter = Mock()
        mock_adapter.read_text.return_value = ""

        with patch(_STORAGE_FACTORY, return_value=mock_adapter):
            content = read_report_from_storage()

        assert content == ""


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
