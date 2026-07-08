"""
Unit tests for report utility functions

Tests cover:
- Report path generation
- Report reading from storage
- Report existence checking
- CSV streaming response creation
- On-demand report generation
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from docpipe.core.constants.constants import ExecutionStatus
from docpipe.core.job_management.application.services.report_utils import (
    create_csv_streaming_response,
    generate_report_on_demand,
    get_report_path,
    read_report_from_storage,
)
from docpipe.core.job_management.domain.models import JobStats

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


class TestGenerateReportOnDemand:
    """Test on-demand report generation."""

    @patch("docpipe.core.job_management.application.services.report_generator.JobReportGenerator")
    def test_generate_report_on_demand_success(self, mock_generator_class):
        """Generate report on demand successfully."""
        # Setup mocks
        mock_generator = Mock()
        mock_generator.generate_csv_content.return_value = "GUID,File name\ndoc1,test.pdf\n"
        mock_generator.save_report_to_file.return_value = "saved_path"
        mock_generator_class.return_value = mock_generator

        mock_job_stats_service = Mock()
        mock_job_stats_service.get_flow_definition.return_value = {"dag": []}

        job_stats = JobStats(
            job_id=JOB_ID,
            job_run_id=JOB_RUN_ID,
            status=ExecutionStatus.COMPLETED,
            node_stats={},
        )

        # Execute
        csv_content = generate_report_on_demand(
            job_run_id=JOB_RUN_ID,
            job_stats=job_stats,
            job_stats_service=mock_job_stats_service,
        )

        # Verify
        assert csv_content == "GUID,File name\ndoc1,test.pdf\n"
        mock_job_stats_service.get_flow_definition.assert_called_once_with(job_run_id=JOB_RUN_ID)
        mock_generator_class.assert_called_once_with(
            job_stats=job_stats,
            dag_nodes=[],
        )
        mock_generator.generate_csv_content.assert_called_once()
        mock_generator.save_report_to_file.assert_called_once()

    @patch("docpipe.core.job_management.application.services.report_generator.JobReportGenerator")
    def test_generate_report_on_demand_with_dag_nodes(self, mock_generator_class):
        """Generate report with DAG nodes."""
        mock_generator = Mock()
        mock_generator.generate_csv_content.return_value = "CSV content"
        mock_generator.save_report_to_file.return_value = "saved_path"
        mock_generator_class.return_value = mock_generator

        mock_job_stats_service = Mock()
        dag_nodes = [{"id": "node1", "name": "Ingest"}]
        mock_job_stats_service.get_flow_definition.return_value = {"dag": dag_nodes}

        job_stats = JobStats(
            job_id=JOB_ID,
            job_run_id=JOB_RUN_ID,
            status=ExecutionStatus.COMPLETED,
            node_stats={},
        )

        generate_report_on_demand(
            job_run_id=JOB_RUN_ID,
            job_stats=job_stats,
            job_stats_service=mock_job_stats_service,
        )

        mock_job_stats_service.get_flow_definition.assert_called_once_with(job_run_id=JOB_RUN_ID)
        mock_generator_class.assert_called_once_with(
            job_stats=job_stats,
            dag_nodes=dag_nodes,
        )

    @patch("docpipe.core.job_management.application.services.report_generator.JobReportGenerator")
    def test_generate_report_on_demand_handles_errors(self, mock_generator_class):
        """Generate report handles errors gracefully."""
        mock_generator = Mock()
        mock_generator.generate_csv_content.side_effect = Exception("Generation failed")
        mock_generator_class.return_value = mock_generator

        mock_job_stats_service = Mock()
        mock_job_stats_service.get_flow_definition.return_value = {"dag": []}

        job_stats = JobStats(
            job_id=JOB_ID,
            job_run_id=JOB_RUN_ID,
            status=ExecutionStatus.COMPLETED,
            node_stats={},
        )

        with pytest.raises(Exception, match="Generation failed"):
            generate_report_on_demand(
                job_run_id=JOB_RUN_ID,
                job_stats=job_stats,
                job_stats_service=mock_job_stats_service,
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
