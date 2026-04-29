# Copyright IBM Corp. 2025
# SPDX-License-Identifier: Apache-2.0

"""
Unit tests for DoclingServeClient.
"""

from unittest.mock import MagicMock, patch

import pytest

from datasift.exceptions.datasift_exceptions import DatasiftException
from datasift.integrations.docling.client import DoclingServeClient


class TestDoclingServeClient:
    """Test suite for DoclingServeClient."""

    def test_init_default_values(self):
        """Test client initialization with default values."""
        client = DoclingServeClient()
        assert client.base_url == "http://0.0.0.0:5001"
        assert client.api_key is None
        assert client.timeout == 300
        assert client.poll_interval == 2
        # max_retries is passed to RestClient but not stored as instance attribute

    def test_init_custom_values(self):
        """Test client initialization with custom values."""
        client = DoclingServeClient(
            base_url="http://localhost:8000",
            api_key="test-key",  # pragma: allowlist secret
            timeout=600,
            poll_interval=5,
            max_retries=5,
        )
        assert client.base_url == "http://localhost:8000"
        assert client.api_key == "test-key"  # pragma: allowlist secret
        assert client.timeout == 600
        assert client.poll_interval == 5
        # max_retries is passed to RestClient but not stored as instance attribute
        assert client.custom_headers["X-API-KEY"] == "test-key"

    def test_build_options_defaults(self):
        """Test default options building."""
        client = DoclingServeClient()
        options = client._build_options()

        assert options["do_ocr"] is True
        assert options["do_table_structure"] is True
        assert options["pdf_backend"] == "dlparse_v2"
        assert options["images_scale"] == 2.0

    def test_build_options_override(self):
        """Test options override."""
        client = DoclingServeClient()
        custom_options = {"do_ocr": False, "custom_param": "value"}
        options = client._build_options(custom_options)

        assert options["do_ocr"] is False
        assert options["custom_param"] == "value"
        assert options["do_table_structure"] is True  # Default preserved

    def test_submit_document_validation_error(self):
        """Test submit_document raises error when both params provided."""
        client = DoclingServeClient()

        with pytest.raises(ValueError, match="Provide exactly one"):
            client.submit_document(file_path="test.pdf", binary_content=b"data")

    def test_submit_document_validation_error_neither(self):
        """Test submit_document raises error when neither param provided."""
        client = DoclingServeClient()

        with pytest.raises(ValueError, match="Provide exactly one"):
            client.submit_document()

    @patch("datasift.integrations.docling.client.Path")
    @patch("datasift.integrations.docling.client.RestClient")
    def test_submit_document_with_file_path(self, mock_rest_client_class, mock_path):
        """Test submit_document with file path."""
        # Setup mocks
        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = True
        mock_path_instance.read_bytes.return_value = b"test content"
        mock_path_instance.name = "test.pdf"
        mock_path.return_value = mock_path_instance

        mock_rest_client_instance = MagicMock()
        mock_rest_client_instance.call_rest_multipart.return_value = {"task_id": "test-task-123"}
        mock_rest_client_class.return_value = mock_rest_client_instance

        # Execute
        client = DoclingServeClient()
        task_id = client.submit_document(file_path="test.pdf")

        # Verify
        assert task_id == "test-task-123"
        mock_rest_client_instance.call_rest_multipart.assert_called_once()
        call_args = mock_rest_client_instance.call_rest_multipart.call_args
        assert "files" in call_args.kwargs
        assert "data" in call_args.kwargs

    @patch("datasift.integrations.docling.client.RestClient")
    def test_submit_document_with_binary_content(self, mock_rest_client_class):
        """Test submit_document with binary content."""
        # Setup mock
        mock_rest_client_instance = MagicMock()
        mock_rest_client_instance.call_rest_multipart.return_value = {"task_id": "test-task-456"}
        mock_rest_client_class.return_value = mock_rest_client_instance

        # Execute
        client = DoclingServeClient()
        binary_data = b"test binary content"
        task_id = client.submit_document(binary_content=binary_data)

        # Verify
        assert task_id == "test-task-456"
        call_args = mock_rest_client_instance.call_rest_multipart.call_args
        assert "files" in call_args.kwargs
        files = call_args.kwargs["files"]
        # Verify the file content is passed correctly
        assert "files" in files
        filename, content, mime_type = files["files"]
        assert content == binary_data

    @patch("datasift.integrations.docling.client.RestClient.call_rest_multipart")
    def test_submit_document_http_error(self, mock_call_rest_multipart):
        """Test submit_document handles HTTP errors."""
        mock_call_rest_multipart.side_effect = DatasiftException(
            message="Connection failed",
            status_code=503,
            error_code="CONNECTION_ERROR",
        )

        client = DoclingServeClient()
        with pytest.raises(DatasiftException, match="Connection failed"):
            client.submit_document(binary_content=b"data")

    @patch("datasift.integrations.docling.client.RestClient.call_rest_json")
    @patch("datasift.integrations.docling.client.time.sleep")
    def test_poll_status_success(self, mock_sleep, mock_call_rest_json):
        """Test poll_status with successful completion."""
        # Setup mock responses
        mock_call_rest_json.return_value = {"task_status": "SUCCESS", "progress": 100}

        # Execute
        client = DoclingServeClient()
        status = client.poll_status(task_id="test-task-123")

        # Verify
        assert status["task_status"] == "SUCCESS"
        mock_call_rest_json.assert_called_once()

    @patch("datasift.integrations.docling.client.RestClient.call_rest_json")
    @patch("datasift.integrations.docling.client.time.sleep")
    def test_poll_status_pending_then_success(self, mock_sleep, mock_call_rest_json):
        """Test poll_status with pending then success."""
        # Setup mock responses
        responses = [
            {"task_status": "PENDING"},
            {"task_status": "STARTED"},
            {"task_status": "SUCCESS"},
        ]
        mock_call_rest_json.side_effect = responses

        # Execute
        client = DoclingServeClient()
        status = client.poll_status(task_id="test-task-123")

        # Verify
        assert status["task_status"] == "SUCCESS"
        assert mock_call_rest_json.call_count == 3

    @patch("datasift.integrations.docling.client.RestClient.call_rest_json")
    def test_poll_status_failure(self, mock_call_rest_json):
        """Test poll_status with task failure."""
        mock_call_rest_json.return_value = {
            "task_status": "FAILURE",
            "error": "Processing failed",
        }

        client = DoclingServeClient()
        with pytest.raises(DatasiftException, match="Task test-task-123 failed"):
            client.poll_status(task_id="test-task-123")

    @patch("datasift.integrations.docling.client.RestClient.call_rest_json")
    def test_get_result_success(self, mock_call_rest_json):
        """Test get_result retrieves document data."""
        mock_call_rest_json.return_value = {"document": "data", "metadata": {}}

        client = DoclingServeClient()
        result = client.get_result(task_id="test-task-123")

        assert "document" in result
        assert result["document"] == "data"

    @patch("datasift.integrations.docling.client.RestClient.call_rest_json")
    def test_get_result_http_error(self, mock_call_rest_json):
        """Test get_result handles HTTP errors."""
        mock_call_rest_json.side_effect = DatasiftException(
            message="Network error",
            status_code=503,
            error_code="CONNECTION_ERROR",
        )

        client = DoclingServeClient()
        with pytest.raises(DatasiftException, match="Network error"):
            client.get_result(task_id="test-task-123")

    @patch.object(DoclingServeClient, "submit_document")
    @patch.object(DoclingServeClient, "_poll_for_completion")
    @patch.object(DoclingServeClient, "get_result")
    def test_process_document_integration(self, mock_get_result, mock_poll_for_completion, mock_submit):
        """Test process_document integrates all steps."""
        # Setup mocks
        mock_submit.return_value = "test-task-123"
        # Mock _poll_for_completion to return a status dict with lowercase "success"
        mock_poll_for_completion.return_value = {
            "task_status": "success",
            "result": {"document": "processed"},
        }
        mock_get_result.return_value = {"document": "processed"}

        # Execute
        client = DoclingServeClient()
        result = client.process_document(binary_content=b"data")

        # Verify all methods called
        mock_submit.assert_called_once()
        mock_poll_for_completion.assert_called_once_with(task_id="test-task-123", poll_interval=None, timeout=7200)
        mock_get_result.assert_called_once_with(task_id="test-task-123")
        assert result["document"] == "processed"
