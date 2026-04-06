# Copyright IBM Corp. 2025
# SPDX-License-Identifier: Apache-2.0

"""
Unit tests for DoclingServeClient.
"""

import base64
from unittest.mock import MagicMock, patch

import pytest

from common.clients.docling_serve_client import DoclingServeClient
from common.exceptions.datasift_exceptions import DatasiftException


class TestDoclingServeClient:
    """Test suite for DoclingServeClient."""

    def test_init_default_values(self):
        """Test client initialization with default values."""
        client = DoclingServeClient()
        assert client.base_url == "http://0.0.0.0:5001"
        assert client.api_key is None
        assert client.timeout == 300
        assert client.poll_interval == 2
        assert client.max_retries == 3

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
        assert client.max_retries == 5
        assert client.headers["X-API-KEY"] == "test-key"

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

    @patch("common.clients.docling_serve_client.Path")
    @patch("common.clients.docling_serve_client.requests.post")
    def test_submit_document_with_file_path(self, mock_post, mock_path):
        """Test submit_document with file path."""
        # Setup mocks
        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = True
        mock_path_instance.read_bytes.return_value = b"test content"
        mock_path.return_value = mock_path_instance

        mock_response = MagicMock()
        mock_response.json.return_value = {"task_id": "test-task-123"}
        mock_post.return_value = mock_response

        # Execute
        client = DoclingServeClient()
        task_id = client.submit_document(file_path="test.pdf")

        # Verify
        assert task_id == "test-task-123"
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert "file_bytes" in call_args.kwargs["json"]
        assert "options" in call_args.kwargs["json"]

    @patch("common.clients.docling_serve_client.requests.post")
    def test_submit_document_with_binary_content(self, mock_post):
        """Test submit_document with binary content."""
        # Setup mock
        mock_response = MagicMock()
        mock_response.json.return_value = {"task_id": "test-task-456"}
        mock_post.return_value = mock_response

        # Execute
        client = DoclingServeClient()
        binary_data = b"test binary content"
        task_id = client.submit_document(binary_content=binary_data)

        # Verify
        assert task_id == "test-task-456"
        call_args = mock_post.call_args
        payload = call_args.kwargs["json"]

        # Verify base64 encoding
        decoded = base64.b64decode(payload["file_bytes"])
        assert decoded == binary_data

    @patch("common.clients.docling_serve_client.requests.post")
    def test_submit_document_http_error(self, mock_post):
        """Test submit_document handles HTTP errors."""
        mock_post.side_effect = Exception("Connection failed")

        client = DoclingServeClient()
        with pytest.raises(DatasiftException, match="Unexpected error"):
            client.submit_document(binary_content=b"data")

    @patch("common.clients.docling_serve_client.requests.get")
    @patch("common.util.infrastructure.retry.time.sleep")
    def test_poll_status_success(self, mock_sleep, mock_get):
        """Test poll_status with successful completion."""
        # Setup mock responses
        mock_response = MagicMock()
        mock_response.json.return_value = {"state": "SUCCESS", "progress": 100}
        mock_get.return_value = mock_response

        # Execute
        client = DoclingServeClient()
        status = client.poll_status("test-task-123")

        # Verify
        assert status["state"] == "SUCCESS"
        mock_get.assert_called_once()

    @patch("common.clients.docling_serve_client.requests.get")
    @patch("common.util.infrastructure.retry.time.sleep")
    def test_poll_status_pending_then_success(self, mock_sleep, mock_get):
        """Test poll_status with pending then success."""
        # Setup mock responses
        responses = [
            {"state": "PENDING"},
            {"state": "STARTED"},
            {"state": "SUCCESS"},
        ]
        mock_response = MagicMock()
        mock_response.json.side_effect = responses
        mock_get.return_value = mock_response

        # Execute
        client = DoclingServeClient()
        status = client.poll_status("test-task-123")

        # Verify
        assert status["state"] == "SUCCESS"
        assert mock_get.call_count == 3

    @patch("common.clients.docling_serve_client.requests.get")
    def test_poll_status_failure(self, mock_get):
        """Test poll_status with task failure."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "state": "FAILURE",
            "error": "Processing failed",
        }
        mock_get.return_value = mock_response

        client = DoclingServeClient()
        with pytest.raises(DatasiftException, match="Task failed"):
            client.poll_status("test-task-123")

    @patch("common.clients.docling_serve_client.requests.get")
    def test_get_result_success(self, mock_get):
        """Test get_result retrieves document data."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"document": "data", "metadata": {}}
        mock_get.return_value = mock_response

        client = DoclingServeClient()
        result = client.get_result("test-task-123")

        assert "document" in result
        assert result["document"] == "data"

    @patch("common.clients.docling_serve_client.requests.get")
    def test_get_result_http_error(self, mock_get):
        """Test get_result handles HTTP errors."""
        mock_get.side_effect = Exception("Network error")

        client = DoclingServeClient()
        with pytest.raises(DatasiftException, match="Unexpected error"):
            client.get_result("test-task-123")

    @patch.object(DoclingServeClient, "submit_document")
    @patch.object(DoclingServeClient, "poll_status")
    @patch.object(DoclingServeClient, "get_result")
    def test_process_document_integration(
        self, mock_get_result, mock_poll, mock_submit
    ):
        """Test process_document integrates all steps."""
        # Setup mocks
        mock_submit.return_value = "test-task-123"
        mock_poll.return_value = {"state": "SUCCESS"}
        mock_get_result.return_value = {"document": "processed"}

        # Execute
        client = DoclingServeClient()
        result = client.process_document(binary_content=b"data")

        # Verify all methods called
        mock_submit.assert_called_once()
        mock_poll.assert_called_once_with(
            task_id="test-task-123", poll_interval=None, max_retries=None
        )
        mock_get_result.assert_called_once_with(task_id="test-task-123")
        assert result["document"] == "processed"
