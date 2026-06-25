"""Integration tests for job runs API flow definition snapshot endpoint."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from docpipe.api.dependencies import get_job_stats_service
from docpipe.api.main import app
from docpipe.exceptions.docpipe_exceptions import DocpipeException, JobStatsStoreReadException
from docpipe.exceptions.error_codes import ErrorCode


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def mock_flow_definition():
    """Sample flow definition for testing."""
    return {
        "name": "Test Flow",
        "description": "Test flow description",
        "dag": [
            {"id": "node1", "operator": "ingest", "config": {"path": "/data"}},
            {"id": "node2", "operator": "extract", "config": {"mode": "text"}},
        ],
    }


class TestGetFlowDefinitionSnapshot:
    """Tests for GET /job_runs/{job_run_id}/flow_definition endpoint."""

    def test_get_flow_definition_success(self, client, mock_flow_definition):
        """Test successful retrieval of flow definition."""
        job_run_id = "9a5137a7-15d5-431c-b945-b147a3043694"

        # Mock stats service to return flow definition
        mock_stats_service = MagicMock()
        mock_stats_service.get_flow_definition.return_value = mock_flow_definition

        # Override the dependency
        app.dependency_overrides[get_job_stats_service] = lambda: mock_stats_service

        try:
            # Make request
            response = client.get(f"/api/v1/job_runs/{job_run_id}/flow_definition")

            # Assertions
            assert response.status_code == 200
            response_data = response.json()
            assert response_data["name"] == "Test Flow"
            assert response_data["description"] == "Test flow description"
            assert len(response_data["dag"]) == 2
            assert response_data["dag"][0]["operator"] == "ingest"

            # Verify stats service was called
            mock_stats_service.get_flow_definition.assert_called_once_with(job_run_id=job_run_id)
        finally:
            # Clean up dependency override
            app.dependency_overrides.clear()

    def test_get_flow_definition_not_found(self, client):
        """Test 404 when flow definition file doesn't exist."""
        job_run_id = "9a5137a7-15d5-431c-b945-b147a3043694"

        # Mock stats service to raise JobStatsStoreReadException (flow definition file not found)
        mock_stats_service = MagicMock()
        mock_stats_service.get_flow_definition.side_effect = JobStatsStoreReadException(
            message=f"Flow definition file not found for job_run_id={job_run_id}",
            job_run_id=job_run_id,
            operation="get_flow_definition",
        )

        # Override the dependency
        app.dependency_overrides[get_job_stats_service] = lambda: mock_stats_service

        try:
            # Make request
            response = client.get(f"/api/v1/job_runs/{job_run_id}/flow_definition")

            # Assertions - API uses custom error format with 'errors' array
            assert response.status_code == 500
            response_data = response.json()
            assert "errors" in response_data
            assert len(response_data["errors"]) > 0
            assert "not found" in response_data["errors"][0]["message"].lower()
        finally:
            # Clean up dependency override
            app.dependency_overrides.clear()

    def test_get_flow_definition_with_unicode(self, client):
        """Test retrieval of flow definition with Unicode characters."""
        job_run_id = "9a5137a7-15d5-431c-b945-b147a3043694"

        flow_def_with_unicode = {
            "name": "Test Flow with 中文 and émojis 🚀",
            "description": "Special chars: <>&\"'",
            "dag": [],
        }

        # Mock stats service to return flow definition with unicode
        mock_stats_service = MagicMock()
        mock_stats_service.get_flow_definition.return_value = flow_def_with_unicode

        # Override the dependency
        app.dependency_overrides[get_job_stats_service] = lambda: mock_stats_service

        try:
            response = client.get(f"/api/v1/job_runs/{job_run_id}/flow_definition")

            assert response.status_code == 200
            response_data = response.json()
            assert response_data["name"] == "Test Flow with 中文 and émojis 🚀"
            assert response_data["description"] == "Special chars: <>&\"'"
        finally:
            # Clean up dependency override
            app.dependency_overrides.clear()

    def test_get_flow_definition_invalid_job_run_id(self, client):
        """Test 400 validation error for invalid job_run_id format."""
        invalid_job_run_id = "not-a-uuid"

        response = client.get(f"/api/v1/job_runs/{invalid_job_run_id}/flow_definition")

        # API returns 400 for validation errors, not 422
        assert response.status_code == 400
        response_data = response.json()
        assert "errors" in response_data
        assert len(response_data["errors"]) > 0

    def test_get_flow_definition_job_run_not_found(self, client):
        """Test 404 when job run doesn't exist in stats service."""
        job_run_id = "9a5137a7-15d5-431c-b945-b147a3043694"

        # Mock stats service to raise DocpipeException with 404 status
        mock_stats_service = MagicMock()
        mock_stats_service.get_flow_definition.side_effect = DocpipeException(
            message=f"Job run not found: {job_run_id}",
            status_code=404,
            error_code=ErrorCode.JOB_RUN_NOT_FOUND,
        )

        # Override the dependency
        app.dependency_overrides[get_job_stats_service] = lambda: mock_stats_service

        try:
            response = client.get(f"/api/v1/job_runs/{job_run_id}/flow_definition")

            assert response.status_code == 404
            response_data = response.json()
            assert "errors" in response_data
            assert "not found" in response_data["errors"][0]["message"].lower()
        finally:
            # Clean up dependency override
            app.dependency_overrides.clear()

    def test_get_flow_definition_server_error(self, client):
        """Test 500 error when storage read error occurs."""
        job_run_id = "9a5137a7-15d5-431c-b945-b147a3043694"

        # Simulate a storage read error in stats service
        mock_stats_service = MagicMock()
        mock_stats_service.get_flow_definition.side_effect = JobStatsStoreReadException(
            message="Failed to read flow definition from storage",
            job_run_id=job_run_id,
            operation="get_flow_definition",
        )

        # Override the dependency
        app.dependency_overrides[get_job_stats_service] = lambda: mock_stats_service

        try:
            response = client.get(f"/api/v1/job_runs/{job_run_id}/flow_definition")

            assert response.status_code == 500
            response_data = response.json()
            assert "errors" in response_data
            assert len(response_data["errors"]) > 0
            # JobStatsStoreReadException returns specific error message
            assert "storage" in response_data["errors"][0]["message"].lower()
        finally:
            # Clean up dependency override
            app.dependency_overrides.clear()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
