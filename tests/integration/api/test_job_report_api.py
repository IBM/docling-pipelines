"""Integration tests for job report download API endpoint."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from docpipe.api.dependencies import get_job_stats_service
from docpipe.api.main import app
from docpipe.core.constants.constants import ExecutionStatus
from docpipe.core.job_management.domain.models import JobStats


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def mock_job_stats_completed():
    """Sample completed job stats for testing."""
    return JobStats(
        job_id="test-job-123",
        job_run_id="9a5137a7-15d5-431c-b945-b147a3043694",
        status=ExecutionStatus.COMPLETED,
        node_stats={},
    )


@pytest.fixture
def mock_job_stats_running():
    """Sample running job stats for testing."""
    return JobStats(
        job_id="test-job-123",
        job_run_id="9a5137a7-15d5-431c-b945-b147a3043694",
        status=ExecutionStatus.RUNNING,
        node_stats={},
    )


@pytest.fixture
def mock_csv_content():
    """Sample CSV report content."""
    return """GUID,File name,Status,Status reason,Time stamp,Pages,Processing time (in seconds)
doc1,test.pdf,Ingested,,2024-01-01T00:00:00Z,10,45
doc2,sample.docx,Failed,File not found,2024-01-01T00:01:00Z,0,0
"""


class TestDownloadJobReport:
    """Tests for GET /job_runs/{job_run_id}/report endpoint."""

    @patch("docpipe.core.job_management.application.services.report_utils.read_report_from_storage")
    def test_download_report_success_existing_report(
        self, mock_read_report, client, mock_job_stats_completed, mock_csv_content
    ):
        """Test successful download of existing report."""
        job_run_id = mock_job_stats_completed.job_run_id

        # Mock report exists in storage
        mock_read_report.return_value = mock_csv_content

        # Mock stats service
        mock_stats_service = MagicMock()
        mock_stats_service.get_job.return_value = mock_job_stats_completed
        app.dependency_overrides[get_job_stats_service] = lambda: mock_stats_service

        try:
            response = client.get(f"/api/v1/job_runs/{job_run_id}/report")

            assert response.status_code == 200
            assert response.headers["content-type"] == "text/csv; charset=utf-8"
            assert "attachment" in response.headers["content-disposition"]
            assert f"job_report_{job_run_id}.csv" in response.headers["content-disposition"]
            assert "GUID,File name,Status" in response.text
            assert "doc1,test.pdf,Ingested" in response.text
        finally:
            app.dependency_overrides.clear()

    @patch("docpipe.core.job_management.application.services.report_generator.JobReportGenerator.save_report_to_file")
    @patch("docpipe.core.job_management.application.services.report_generator.JobReportGenerator.generate_csv_content")
    @patch("docpipe.core.job_management.application.services.report_utils.check_parquet_availability")
    @patch("docpipe.core.job_management.application.services.report_utils.read_report_from_storage")
    def test_download_report_on_demand_generation(
        self,
        mock_read_report,
        mock_parquet,
        mock_generate_csv,
        mock_save,
        client,
        mock_job_stats_completed,
        mock_csv_content,
    ):
        """Test on-demand report generation when report doesn't exist."""
        job_run_id = mock_job_stats_completed.job_run_id

        # Mock report doesn't exist initially
        mock_read_report.return_value = ""
        # Mock parquet availability check
        mock_parquet.return_value = (True, "")
        # Mock on-demand CSV generation and save
        mock_generate_csv.return_value = mock_csv_content
        mock_save.return_value = "/data/test-job/report.csv"

        # Mock stats service — second get_job call (with node_stats) returns completed job
        mock_stats_service = MagicMock()
        mock_stats_service.get_job.return_value = mock_job_stats_completed
        mock_stats_service.get_flow_definition.return_value = {"dag": []}
        app.dependency_overrides[get_job_stats_service] = lambda: mock_stats_service

        try:
            response = client.get(f"/api/v1/job_runs/{job_run_id}/report")

            assert response.status_code == 200
            assert response.headers["content-type"] == "text/csv; charset=utf-8"
            assert "doc1,test.pdf,Ingested" in response.text

            # Verify on-demand generation was called
            mock_generate_csv.assert_called_once()
        finally:
            app.dependency_overrides.clear()

    def test_download_report_job_not_completed(self, client, mock_job_stats_running):
        """Test 425 error when job is not yet completed."""
        job_run_id = mock_job_stats_running.job_run_id

        # Mock stats service to return running job
        mock_stats_service = MagicMock()
        mock_stats_service.get_job.return_value = mock_job_stats_running
        app.dependency_overrides[get_job_stats_service] = lambda: mock_stats_service

        try:
            response = client.get(f"/api/v1/job_runs/{job_run_id}/report")

            assert response.status_code == 425
            response_data = response.json()
            assert "errors" in response_data
            assert "not yet completed" in response_data["errors"][0]["message"].lower()
        finally:
            app.dependency_overrides.clear()

    def test_download_report_job_not_found(self, client):
        """Test 404 when job run doesn't exist."""
        job_run_id = "9a5137a7-15d5-431c-b945-b147a3043694"

        # Mock stats service to return None (job not found)
        mock_stats_service = MagicMock()
        mock_stats_service.get_job.return_value = None
        app.dependency_overrides[get_job_stats_service] = lambda: mock_stats_service

        try:
            response = client.get(f"/api/v1/job_runs/{job_run_id}/report")

            assert response.status_code == 404
            response_data = response.json()
            assert "errors" in response_data
            assert "not found" in response_data["errors"][0]["message"].lower()
        finally:
            app.dependency_overrides.clear()

    def test_download_report_invalid_job_run_id(self, client):
        """Test 400 validation error for invalid job_run_id format."""
        invalid_job_run_id = "not-a-uuid"

        response = client.get(f"/api/v1/job_runs/{invalid_job_run_id}/report")

        assert response.status_code == 400
        response_data = response.json()
        assert "errors" in response_data

    @patch("docpipe.core.job_management.application.services.report_generator.JobReportGenerator.generate_csv_content")
    @patch("docpipe.core.job_management.application.services.report_utils.check_parquet_availability")
    @patch("docpipe.core.job_management.application.services.report_utils.read_report_from_storage")
    def test_download_report_generation_failure(
        self, mock_read_report, mock_parquet, mock_generate_csv, client, mock_job_stats_completed
    ):
        """Test 500 error when report generation fails."""
        job_run_id = mock_job_stats_completed.job_run_id

        # Mock report doesn't exist
        mock_read_report.return_value = ""
        # Mock parquet availability check
        mock_parquet.return_value = (True, "")
        # Mock CSV generation failure
        mock_generate_csv.side_effect = Exception("Report generation failed")

        # Mock stats service
        mock_stats_service = MagicMock()
        mock_stats_service.get_job.return_value = mock_job_stats_completed
        mock_stats_service.get_flow_definition.return_value = {"dag": []}
        app.dependency_overrides[get_job_stats_service] = lambda: mock_stats_service

        try:
            response = client.get(f"/api/v1/job_runs/{job_run_id}/report")

            assert response.status_code == 500
            response_data = response.json()
            assert "errors" in response_data
        finally:
            app.dependency_overrides.clear()

    @patch("docpipe.core.job_management.application.services.report_utils.read_report_from_storage")
    def test_download_report_with_unicode_content(self, mock_read_report, client, mock_job_stats_completed):
        """Test report download with Unicode characters."""
        job_run_id = mock_job_stats_completed.job_run_id

        # CSV with Unicode characters
        unicode_csv = """GUID,File name,Status
doc1,测试文档.pdf,Ingested
doc2,émoji🚀.docx,Failed
"""
        mock_read_report.return_value = unicode_csv

        # Mock stats service
        mock_stats_service = MagicMock()
        mock_stats_service.get_job.return_value = mock_job_stats_completed
        app.dependency_overrides[get_job_stats_service] = lambda: mock_stats_service

        try:
            response = client.get(f"/api/v1/job_runs/{job_run_id}/report")

            assert response.status_code == 200
            assert "测试文档.pdf" in response.text
            assert "émoji🚀.docx" in response.text
        finally:
            app.dependency_overrides.clear()

    def test_download_report_completed_with_errors(self, client):
        """Test report download for job completed with errors."""
        job_stats = JobStats(
            job_id="test-job-123",
            job_run_id="9a5137a7-15d5-431c-b945-b147a3043694",
            status=ExecutionStatus.COMPLETED_WITH_ERRORS,
            node_stats={},
        )

        csv_content = "GUID,File name,Status\ndoc1,test.pdf,Failed\n"

        # Mock stats service and report storage
        mock_stats_service = MagicMock()
        mock_stats_service.get_job.return_value = job_stats
        app.dependency_overrides[get_job_stats_service] = lambda: mock_stats_service

        with patch(
            "docpipe.core.job_management.application.services.report_utils.read_report_from_storage"
        ) as mock_read:
            mock_read.return_value = csv_content

            try:
                response = client.get(f"/api/v1/job_runs/{job_stats.job_run_id}/report")

                # Should succeed for COMPLETED_WITH_ERRORS status
                assert response.status_code == 200
                assert "doc1,test.pdf,Failed" in response.text
            finally:
                app.dependency_overrides.clear()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
