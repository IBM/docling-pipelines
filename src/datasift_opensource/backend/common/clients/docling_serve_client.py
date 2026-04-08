# Copyright IBM Corp. 2025
# SPDX-License-Identifier: Apache-2.0

"""
Docling Serve Client for document processing via REST API.

Provides async API support with submit → poll → retrieve pattern for
processing documents through docling-serve service.
"""

import base64
from pathlib import Path
from typing import Any

from common.clients.rest_client import RestClient, RestClientConfig, RestMethod
from common.exceptions.datasift_exceptions import DatasiftException
from common.exceptions.error_codes import ErrorCode
from common.util.infrastructure.logging import get_logger
from common.util.infrastructure.retry import retry_with_exponential_backoff

logger = get_logger(__name__)


def _should_retry_poll(result, exception):
    """
    Retry logic for docling serve status polling.

    Retries on DatasiftException with CONNECTION_ERROR or when task is still in progress.
    Does not retry on SUCCESS or FAILURE states.

    Args:
        result: The status response dictionary or None if exception occurred
        exception: Any exception that occurred during polling

    Returns:
        Tuple of (should_retry: bool, error_message: str)
    """
    # Retry on network errors (RestClient wraps these as DatasiftException with CONNECTION_ERROR)
    if exception:
        if isinstance(exception, DatasiftException) and exception.error_code == ErrorCode.CONNECTION_ERROR:
            return True, f"Network error during polling: {exception}"
        # Don't retry on other exceptions (HTTP errors, DatasiftException for FAILURE state, etc.)
        return False, ""

    # Check task state if we have a result
    if result:
        state = result.get("state", "unknown")
        if state in ["PENDING", "STARTED", "unknown"]:
            # Task still in progress or unknown state, continue polling
            return True, f"Task still in progress (state={state})"
        # For SUCCESS state, don't retry - result will be returned
        return False, ""

    # No result and no exception - shouldn't happen, but don't retry
    return False, "No result or exception"


class DoclingServeClient:
    """
    Client for interacting with docling-serve REST API.

    Supports async document processing with submit → poll → retrieve pattern.
    Handles file submission, status polling with retry logic, and result retrieval.
    """

    def __init__(
        self,
        base_url: str = "http://0.0.0.0:5001",
        api_key: str | None = None,
        timeout: int = 300,
        poll_interval: int = 2,
        max_retries: int = 3,
    ):
        """
        Initialize the Docling Serve client.

        Args:
            base_url: Base URL of docling-serve service (default: http://0.0.0.0:5001)
            api_key: Optional API key for authentication via X-API-KEY header
            timeout: Request timeout in seconds (default: 300)
            poll_interval: Polling interval in seconds (default: 2)
            max_retries: Maximum retry attempts for polling (default: 3)
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.max_retries = max_retries

        # Initialize RestClient
        rest_config = RestClientConfig(timeout=self.timeout, max_retries=self.max_retries)
        self.rest_client = RestClient(config=rest_config, base_url=self.base_url)

        # Setup custom headers for API key
        self.custom_headers = {}
        if self.api_key:
            self.custom_headers["X-API-KEY"] = self.api_key

        logger.info(f"Initialized DoclingServeClient with base_url={self.base_url}")

    def _build_options(self, options: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        Build options dictionary with defaults for v1 API.

        Args:
            options: User-provided options to override defaults

        Returns:
            Complete options dictionary with defaults applied
        """
        default_options = {
            "do_ocr": True,
            "ocr_engine": "easyocr",
            "pdf_backend": "dlparse_v2",
            "table_mode": "accurate",
            "do_table_structure": True,
            "table_cell_matching": True,
            "include_images": True,
            "images_scale": 2.0,
            "image_export_mode": "embedded",
            "to_formats": ["md"],
        }

        if options:
            default_options.update(options)

        return default_options

    def submit_document(
        self,
        file_path: str | None = None,
        binary_content: bytes | None = None,
        options: dict[str, Any] | None = None,
    ) -> str:
        """
        Submit a document for processing.

        Args:
            file_path: Path to file to process (mutually exclusive with binary_content)
            binary_content: Binary content of file (mutually exclusive with file_path)
            options: Processing options (OCR, tables, images, PDF backend, etc.)

        Returns:
            Task ID for tracking the processing job

        Raises:
            ValueError: If neither or both file_path and binary_content provided
            FileNotFoundError: If file_path does not exist
            DatasiftException: For HTTP or network errors
        """
        if (file_path is None) == (binary_content is None):
            raise ValueError("Provide exactly one of file_path or binary_content")

        # Read file if path provided
        content: bytes
        if file_path:
            path = Path(file_path)
            if not path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            content = path.read_bytes()
            logger.info(f"Submitting document: {file_path}")
        else:
            # binary_content is guaranteed to be bytes here due to validation above
            content = binary_content  # type: ignore[assignment]
            logger.info("Submitting document from binary content")

        # Encode content as base64
        file_bytes = base64.b64encode(content).decode("utf-8")

        # Build JSON payload
        payload = {
            "file_bytes": file_bytes,
            "options": self._build_options(options),
        }

        # Submit request
        endpoint = "/v1/convert/file/async"
        return self._submit_request_json(endpoint, payload)

    def _submit_request_json(self, endpoint: str, payload: dict[str, Any]) -> str:
        """
        Submit HTTP JSON request and extract task ID.

        Args:
            endpoint: API endpoint path
            payload: JSON payload dictionary

        Returns:
            Task ID from response

        Raises:
            DatasiftException: For HTTP or network errors
        """
        result = self.rest_client.call_rest_json(
            method=RestMethod.POST,
            endpoint=endpoint,
            json_data=payload,
            headers=self.custom_headers,
        )

        task_id = result.get("task_id")
        if not task_id:
            raise DatasiftException(
                message="No task_id in response",
                status_code=500,
                error_code=ErrorCode.EXTERNAL_SERVICE_ERROR,
            )

        logger.info(f"Document submitted successfully, task_id={task_id}")
        return task_id

    def poll_status(
        self,
        task_id: str,
        poll_interval: int | None = None,
        max_retries: int | None = None,
    ) -> dict[str, Any]:
        """
        Poll task status until completion with retry logic.

        Args:
            task_id: Task ID to poll
            poll_interval: Override default polling interval in seconds
            max_retries: Override default max retry attempts

        Returns:
            Status response with state and progress information

        Raises:
            DatasiftException: For HTTP errors or max retries exceeded
        """
        interval = poll_interval if poll_interval is not None else self.poll_interval
        retries = max_retries if max_retries is not None else self.max_retries

        logger.info(f"Polling status for task_id={task_id}")

        # Use retry decorator with custom retry logic
        @retry_with_exponential_backoff(
            max_retries=retries,
            initial_delay=interval,
            max_delay=interval,  # Keep constant delay for polling
            retry_logic=_should_retry_poll,
        )
        def _poll_once() -> dict[str, Any]:
            """Single polling attempt that checks task status."""
            endpoint = f"/v1/status/poll/{task_id}"
            status = self._check_status(endpoint)
            state = status.get("state", "unknown")

            if state == "SUCCESS":
                logger.info(f"Task {task_id} completed successfully")
                return status
            elif state == "FAILURE":
                error_msg = status.get("error", "Unknown error")
                raise DatasiftException(
                    message=f"Task failed: {error_msg}",
                    status_code=500,
                    error_code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                )
            elif state in ["PENDING", "STARTED"]:
                logger.debug(f"Task {task_id} status={state}, polling...")
                # Return status dict to trigger retry via retry_logic
                return status
            else:
                logger.warning(f"Unknown task status: {state}")
                # Return status dict to trigger retry via retry_logic
                return status

        result = _poll_once()
        # Ensure we return a valid status dict
        if result is None:
            raise DatasiftException(
                message=f"Polling failed for task {task_id}: no valid status returned",
                status_code=500,
                error_code=ErrorCode.EXTERNAL_SERVICE_ERROR,
            )
        return result

    def _check_status(self, endpoint: str) -> dict[str, Any]:
        """
        Check task status via HTTP request.

        Args:
            endpoint: Status endpoint path

        Returns:
            Status response dictionary

        Raises:
            DatasiftException: For HTTP errors
        """
        return self.rest_client.call_rest_json(
            method=RestMethod.GET,
            endpoint=endpoint,
            headers=self.custom_headers,
        )

    def get_result(self, task_id: str) -> dict[str, Any]:
        """
        Retrieve processed document result.

        Args:
            task_id: Task ID to retrieve result for

        Returns:
            Processed document data as dictionary

        Raises:
            DatasiftException: For HTTP or network errors
        """
        endpoint = f"/v1/result/{task_id}"
        logger.info(f"Retrieving result for task_id={task_id}")

        result = self.rest_client.call_rest_json(
            method=RestMethod.GET,
            endpoint=endpoint,
            headers=self.custom_headers,
        )

        logger.info(f"Result retrieved successfully for task_id={task_id}")
        return result

    def process_document(
        self,
        file_path: str | None = None,
        binary_content: bytes | None = None,
        options: dict[str, Any] | None = None,
        poll_interval: int | None = None,
        max_retries: int | None = None,
    ) -> dict[str, Any]:
        """
        Convenience method combining submit → poll → retrieve.

        Args:
            file_path: Path to file to process
            binary_content: Binary content of file
            options: Processing options
            poll_interval: Override default polling interval
            max_retries: Override default max retry attempts

        Returns:
            Processed document data as dictionary

        Raises:
            ValueError: If neither or both file_path and binary_content provided
            FileNotFoundError: If file_path does not exist
            DatasiftException: For HTTP, network, or processing errors
        """
        # Submit document
        task_id = self.submit_document(file_path=file_path, binary_content=binary_content, options=options)

        # Poll until completion
        self.poll_status(task_id=task_id, poll_interval=poll_interval, max_retries=max_retries)

        # Retrieve result
        return self.get_result(task_id=task_id)
