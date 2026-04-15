# Copyright IBM Corp. 2025
# SPDX-License-Identifier: Apache-2.0

"""
Docling Serve Client for document processing via REST API.

Provides async API support with submit → poll → retrieve pattern for
processing documents through docling-serve service.
"""

import time
from pathlib import Path
from typing import Any

from common.clients.rest_client import RestClient, RestClientConfig, RestMethod
from common.exceptions.datasift_exceptions import DatasiftException
from common.exceptions.error_codes import ErrorCode
from common.util.infrastructure.logging import get_logger

logger = get_logger(__name__)


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
            max_retries: Maximum retry attempts for API call failures (default: 3)
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.poll_interval = poll_interval

        # Initialize RestClient with max_retries for actual API call failures
        rest_config = RestClientConfig(timeout=self.timeout, max_retries=max_retries)
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
        filename: str
        if file_path:
            path = Path(file_path)
            if not path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            content = path.read_bytes()
            filename = path.name
            logger.info(f"Submitting document: {file_path}")
        else:
            # binary_content is guaranteed to be bytes here due to validation above
            content = binary_content  # type: ignore[assignment]
            filename = "document.pdf"  # Default filename for binary content
            logger.info("Submitting document from binary content")

        # Submit request using multipart/form-data
        endpoint = "/v1/convert/file/async"
        return self._submit_request_multipart(endpoint, content, filename, options)

    def _submit_request_multipart(
        self,
        endpoint: str,
        file_content: bytes,
        filename: str,
        options: dict[str, Any] | None = None,
    ) -> str:
        """
        Submit HTTP multipart/form-data request and extract task ID.

        Args:
            endpoint: API endpoint path
            file_content: Binary file content
            filename: Name of the file
            options: Processing options dictionary

        Returns:
            Task ID from response

        Raises:
            DatasiftException: For HTTP or network errors
        """
        # Build multipart form data
        files = {"files": (filename, file_content, "application/octet-stream")}

        # Build form data with options as individual fields
        data = self._build_options(options)

        result = self.rest_client.call_rest_multipart(
            method=RestMethod.POST,
            endpoint=endpoint,
            files=files,
            data=data,
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

    def _poll_for_completion(
        self,
        task_id: str,
        poll_interval: int | None = None,
        timeout: int = 7200,
    ) -> dict[str, Any]:
        """
        Poll task status until a terminal status is reached.

        Args:
            task_id: Task ID to poll
            poll_interval: Override default polling interval in seconds
            timeout: Maximum time to wait in seconds (default: 7200 = 2 hours)

        Returns:
            Final status response dictionary

        Raises:
            DatasiftException: For failure status, HTTP errors, or timeout exceeded
        """
        interval = poll_interval if poll_interval is not None else self.poll_interval
        start_time = time.time()

        logger.info(f"Polling status for task_id={task_id} with timeout={timeout}s")

        while True:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                raise DatasiftException(
                    message=f"Polling timeout after {timeout} seconds for task {task_id}",
                    status_code=500,
                    error_code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                )

            try:
                endpoint = f"/v1/status/poll/{task_id}"
                result = self._check_status(endpoint)
                task_status = result.get("task_status", "unknown").upper()

                logger.info(f"Polling task {task_id}: status={task_status}")

                if task_status == "SUCCESS":
                    logger.info(f"Task {task_id} completed successfully")
                    return result

                if task_status == "FAILURE":
                    error_msg = result.get("error_message", "Unknown error")
                    logger.error(
                        f"Task {task_id} failed with error: {error_msg}",
                        extra={"task_id": task_id, "full_response": result},
                    )
                    raise DatasiftException(
                        message=f"Task {task_id} failed: {error_msg}",
                        status_code=500,
                        error_code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                    )

                # Continue polling for PENDING/STARTED/unknown statuses
                logger.debug(f"Task {task_id} status: {task_status}, continuing to poll...")
                time.sleep(interval)

            except DatasiftException as e:
                # Re-raise DatasiftException (including FAILURE status)
                if e.error_code != ErrorCode.CONNECTION_ERROR:
                    raise
                # For connection errors, log and retry
                logger.warning(f"Connection error during polling: {e}, retrying...")
                time.sleep(interval)

    def poll_status(
        self,
        task_id: str,
        poll_interval: int | None = None,
        timeout: int = 7200,
    ) -> dict[str, Any]:
        """
        Poll task status until completion with timeout.

        Args:
            task_id: Task ID to poll
            poll_interval: Override default polling interval in seconds
            timeout: Maximum time to wait in seconds (default: 7200 = 2 hours)

        Returns:
            Final status response with terminal state information

        Raises:
            DatasiftException: For failure status, HTTP errors, or timeout exceeded
        """
        return self._poll_for_completion(
            task_id=task_id,
            poll_interval=poll_interval,
            timeout=timeout,
        )

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
        timeout: int = 7200,
    ) -> dict[str, Any]:
        """
        Convenience method combining submit → poll → retrieve.

        Args:
            file_path: Path to file to process
            binary_content: Binary content of file
            options: Processing options
            poll_interval: Override default polling interval
            timeout: Maximum time to wait in seconds (default: 7200 = 2 hours)

        Returns:
            Processed document data as dictionary

        Raises:
            ValueError: If neither or both file_path and binary_content provided
            FileNotFoundError: If file_path does not exist
            DatasiftException: For HTTP, network, or processing errors
        """
        # Submit document
        task_id = self.submit_document(file_path=file_path, binary_content=binary_content, options=options)

        # Poll until completion and only retrieve result after SUCCESS
        final_response = self._poll_for_completion(
            task_id=task_id,
            poll_interval=poll_interval,
            timeout=timeout,
        )
        logger.info(f"Final Status before: {task_id}, {final_response}")
        final_status = final_response.get("task_status")
        logger.info(f"Final Status: {task_id}, {final_status}")
        if final_status != "success":
            error_message = final_response.get("error_message", "Unknown Error")
            raise DatasiftException(
                message=f"Task {task_id} did not complete successfully with error message: {error_message}",
                status_code=500,
                error_code=ErrorCode.EXTERNAL_SERVICE_ERROR,
            )

        return self.get_result(task_id=task_id)
