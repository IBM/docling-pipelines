# Copyright IBM Corp. 2025
# -License-Identifier: Apache-2.0

"""
Docling Serve Client for document processing via REST API.

Provides async API support with submit → poll → retrieve pattern for
processing documents through docling-serve service.
"""

import time
from pathlib import Path
from typing import Any

from docpipe.core.constants.constants import DoclingClientConstants
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.exceptions.docpipe_exceptions import DocpipeException
from docpipe.exceptions.error_codes import ErrorCode
from docpipe.integrations.base_llm_client import retry_with_backoff
from docpipe.integrations.rest_client import RestClient, RestClientConfig, RestMethod
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger(__name__)


class DoclingServeClient:
    """
    Client for interacting with docling-serve REST API.

    Supports async document processing with submit → poll → retrieve pattern.
    Handles file submission, status polling with retry logic, and result retrieval.
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None = None,
        timeout: int = 300,
        poll_interval: int = 2,
        max_retries: int = 3,
        verify_ssl: bool = True,
    ):
        """
        Initialize the Docling Serve client.

        Args:
            base_url: Base URL of docling-serve service (required, must not be empty)
            api_key: Optional API key for authentication via X-API-KEY header
            timeout: Request timeout in seconds (default: 300)
            poll_interval: Polling interval in seconds (default: 2)
            max_retries: Maximum retry attempts for API call failures (default: 3)
            verify_ssl: Enable SSL certificate verification (default: True).
                       Set to False only for internal testing with self-signed certificates.

        Raises:
            ValueError: If base_url is empty or whitespace-only
        """
        if not base_url or not base_url.strip():
            raise ValueError("base_url must not be empty")

        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.poll_interval = poll_interval

        # Initialize RestClient with max_retries for actual API call failures
        rest_config = RestClientConfig(timeout=self.timeout, max_retries=max_retries, verify_ssl=verify_ssl)
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
            "ocr_preset": "auto",
            "ocr_lang": None,
            "pdf_backend": "dlparse_v2",
            "table_mode": "accurate",
            "do_table_structure": True,
            "table_cell_matching": True,
            "include_images": True,
            "images_scale": 2.0,
            "image_export_mode": "embedded",
            "to_formats": ["json", "md", "text", "doclang"],
        }

        if options:
            default_options.update(options)

        return default_options

    def submit_document(
        self,
        *,
        file_path: str | None = None,
        binary_content: bytes | None = None,
        filename: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> str:
        """
        Submit a document for processing.

        Args:
            file_path: Path to file to process (mutually exclusive with binary_content)
            binary_content: Binary content of file (mutually exclusive with file_path)
            filename: Filename to use when binary_content is provided. Preserves file extension
                     for proper MIME type detection. If not provided, uses default fallback filename.
            options: Processing options (OCR, tables, images, PDF backend, etc.)

        Returns:
            Task ID for tracking the processing job

        Raises:
            ValueError: If neither or both file_path and binary_content provided
            FileNotFoundError: If file_path does not exist
            DocpipeException: For HTTP or network errors
        """
        if (file_path is None) == (binary_content is None):
            raise ValueError("Provide exactly one of file_path or binary_content")

        # Read file if path provided
        content: bytes
        actual_filename: str
        if file_path:
            path = Path(file_path)
            if not path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            content = path.read_bytes()
            actual_filename = path.name
            logger.info(f"Submitting document: {file_path}")
        else:
            # binary_content is guaranteed to be bytes here due to validation above
            content = binary_content  # type: ignore[assignment]
            actual_filename = filename if filename else OperatorConstants.Extraction.DEFAULT_FALLBACK_FILENAME
            logger.info(f"Submitting document from binary content with filename: {actual_filename}")

        # Submit request using multipart/form-data
        endpoint = "/v1/convert/file/async"
        return self._submit_request_multipart(
            endpoint=endpoint,
            file_content=content,
            filename=actual_filename,
            options=options,
        )

    def _submit_request_multipart(
        self,
        *,
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
            DocpipeException: For HTTP or network errors
        """
        # Determine MIME type based on file extension
        mime_type = "application/octet-stream"
        if filename:
            ext = Path(filename).suffix.lower()
            mime_map = {
                ".html": "text/html",
                ".htm": "text/html",
                ".md": "text/markdown",
                ".txt": "text/plain",
                ".pdf": "application/pdf",
                ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ".doc": "application/msword",
                ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ".xls": "application/vnd.ms-excel",
                ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                ".ppt": "application/vnd.ms-powerpoint",
            }
            mime_type = mime_map.get(ext, "application/octet-stream")

        # Build multipart form data
        files = {"files": (filename, file_content, mime_type)}

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
            raise DocpipeException(
                message="No task_id in response",
                status_code=500,
                error_code=ErrorCode.EXTERNAL_SERVICE_ERROR,
            )

        logger.info(f"Document submitted successfully, task_id={task_id}")
        return task_id

    def _poll_for_completion(
        self,
        *,
        task_id: str,
        poll_interval: int | None = None,
        timeout: int = 7200,
        filename: str | None = None,
    ) -> dict[str, Any]:
        """
        Poll task status until a terminal status is reached.

        Args:
            task_id: Task ID to poll
            poll_interval: Override default polling interval in seconds
            timeout: Maximum time to wait in seconds (default: 7200 = 2 hours)
            filename: Optional filename associated with the task for logging

        Returns:
            Final status response dictionary

        Raises:
            DocpipeException: For failure status, HTTP errors, or timeout exceeded
        """
        interval = poll_interval if poll_interval is not None else self.poll_interval
        start_time = time.time()

        logger.info(f"Polling status for task_id={task_id} with timeout={timeout}s")

        while True:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                raise DocpipeException(
                    message=f"Polling timeout after {timeout} seconds for task {task_id}",
                    status_code=500,
                    error_code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                )

            try:
                endpoint = f"/v1/status/poll/{task_id}"
                result = self._check_status(endpoint=endpoint)
                task_status = result.get("task_status", "unknown").upper()
                file_label = filename if filename is not None else "unknown"

                logger.info(f"Polling task {task_id} for file '{file_label}': status={task_status}")

                if task_status == "SUCCESS":
                    logger.info(f"Task {task_id} completed successfully")
                    return result

                if task_status == "FAILURE":
                    error_msg = result.get("error_message", "Unknown error")
                    logger.error(
                        f"Task {task_id} failed with error: {error_msg}",
                        extra={"task_id": task_id, "full_response": result},
                    )
                    raise DocpipeException(
                        message=f"Task {task_id} failed: {error_msg}",
                        status_code=500,
                        error_code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                    )

                # Continue polling for PENDING/STARTED/unknown statuses
                logger.debug(f"Task {task_id} status: {task_status}, continuing to poll...")
                time.sleep(interval)

            except DocpipeException as e:
                # Re-raise DocpipeException (including FAILURE status)
                if e.error_code != ErrorCode.CONNECTION_ERROR:
                    raise
                # For connection errors, log and retry
                logger.warning(f"Connection error during polling: {e}, retrying...")
                time.sleep(interval)

    def poll_status(
        self,
        *,
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
            DocpipeException: For failure status, HTTP errors, or timeout exceeded
        """
        return self._poll_for_completion(
            task_id=task_id,
            poll_interval=poll_interval,
            timeout=timeout,
        )

    @retry_with_backoff(
        max_retries=DoclingClientConstants.STATUS_404_MAX_RETRIES,
        initial_delay=DoclingClientConstants.STATUS_404_BACKOFF_BASE,
        backoff_factor=2.0,
        exceptions=(DocpipeException,),
    )
    def _check_status(self, *, endpoint: str) -> dict[str, Any]:
        """
        Check task status via HTTP request with retry logic for 404 errors.

        Retries on 404 errors to handle:
        - Pod restarts/terminations during HPA scaling
        - Load balancer routing issues during pod lifecycle events
        - Transient network issues

        Args:
            endpoint: Status endpoint path

        Returns:
            Status response dictionary

        Raises:
            DocpipeException: For HTTP errors (after retries for 404)
        """
        try:
            return self.rest_client.call_rest_json(
                method=RestMethod.GET,
                endpoint=endpoint,
                headers=self.custom_headers,
            )
        except DocpipeException as e:
            # Only retry on 404 errors (task not found during pod transitions)
            if e.status_code == 404:
                logger.warning(
                    f"Task not found (404) at {endpoint}. "
                    f"This may occur during pod restarts or HPA scaling. Retrying..."
                )
                raise  # Let decorator handle retry
            # For other errors, raise immediately without retry
            raise

    def get_result(self, *, task_id: str) -> dict[str, Any]:
        """
        Retrieve processed document result.

        Args:
            task_id: Task ID to retrieve result for

        Returns:
            Processed document data as dictionary

        Raises:
            DocpipeException: For HTTP or network errors
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
        *,
        file_path: str | None = None,
        binary_content: bytes | None = None,
        filename: str | None = None,
        options: dict[str, Any] | None = None,
        poll_interval: int | None = None,
        timeout: int = 7200,
    ) -> dict[str, Any]:
        """
        Convenience method combining submit → poll → retrieve.

        Args:
            file_path: Path to file to process
            binary_content: Binary content of file
            filename: Filename to use when binary_content is provided. Preserves file extension
                     for proper MIME type detection. If not provided, defaults to "document.pdf".
            options: Processing options
            poll_interval: Override default polling interval
            timeout: Maximum time to wait in seconds (default: 7200 = 2 hours)

        Returns:
            Processed document data as dictionary

        Raises:
            ValueError: If neither or both file_path and binary_content provided
            FileNotFoundError: If file_path does not exist
            DocpipeException: For HTTP, network, or processing errors
        """
        # Submit document
        task_id = self.submit_document(
            file_path=file_path,
            binary_content=binary_content,
            filename=filename,
            options=options,
        )

        # Poll until completion and only retrieve result after SUCCESS
        final_response = self._poll_for_completion(
            task_id=task_id,
            poll_interval=poll_interval,
            timeout=timeout,
            filename=filename,
        )
        logger.info(f"Final Status before: {task_id}, {final_response}")
        final_status = str(final_response.get("task_status", "")).upper()
        logger.info(f"Final Status: {task_id}, {final_status}")
        if final_status != "SUCCESS":
            error_message = final_response.get("error_message", "Unknown Error")
            raise DocpipeException(
                message=f"Task {task_id} did not complete successfully with error message: {error_message}",
                status_code=500,
                error_code=ErrorCode.EXTERNAL_SERVICE_ERROR,
            )

        return self.get_result(task_id=task_id)
