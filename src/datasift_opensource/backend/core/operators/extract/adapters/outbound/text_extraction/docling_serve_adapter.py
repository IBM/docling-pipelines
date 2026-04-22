"""Docling Serve remote extraction adapter.

This adapter implements remote document extraction using the Docling Serve API.
It delegates extraction to a remote Docling Serve instance, enabling distributed
processing and reducing local resource requirements.
"""

import logging
from typing import Any

from common.clients.docling_serve_client import DoclingServeClient
from common.constants.operator_constants import OperatorConstants
from common.util.infrastructure.logging import get_logger
from core.operators.extract.ports.outbound.text_extraction import TextExtractionPort

logger: logging.Logger = get_logger()


class DoclingServeAdapter(TextExtractionPort):
    """Adapter for remote Docling Serve document extraction.

    This adapter connects to a remote Docling Serve API for document extraction.
    It supports:
    - Remote API-based extraction
    - Configurable OCR settings
    - Multiple PDF backends
    - Table and image extraction modes
    - Polling-based result retrieval
    - Automatic retry on failures

    Configuration:
        docling_serve_config: Dictionary containing:
            - base_url: Docling Serve API endpoint (default: "http://0.0.0.0:5001")
            - api_key: Optional API key for authentication
            - timeout: Request timeout in seconds (default: 300)
            - poll_interval: Polling interval in seconds (default: 2)
            - max_retries: Maximum retry attempts (default: 3)
            - do_ocr: Enable OCR processing (default: True)
            - ocr_engine: OCR engine to use (optional)
            - ocr_languages: List of OCR languages (optional)
            - pdf_backend: PDF backend to use (default: "dlparse_v2")
            - table_mode: Table extraction mode (optional)
            - image_export_mode: Image export mode (optional)

    Attributes:
        ADAPTER_NAME: Short identifier "docling_serve"
        ADAPTER_DISPLAY_NAME: Human-readable name "Docling Serve"
    """

    ADAPTER_NAME = "docling_serve"
    ADAPTER_DISPLAY_NAME = "Docling Serve Extractor"

    def __init__(self, *, config: dict[str, Any]) -> None:
        """Initialize the adapter with configuration.

        Args:
            config: Configuration dictionary
        """
        super().__init__(config=config)

    def _init_adapter_config(self, *, config: dict[str, Any]) -> None:
        """Initialize Docling Serve-specific configuration.

        Args:
            config: Configuration dictionary containing docling_serve_config

        Raises:
            ValueError: If docling_serve_config is missing or invalid
        """
        docling_serve_config = config.get("docling_serve_config")
        if not docling_serve_config:
            raise ValueError("docling_serve_config is required for DoclingServeAdapter")

        # Extract connection parameters
        self.base_url = docling_serve_config.get("base_url", "http://0.0.0.0:5001")
        self.api_key = docling_serve_config.get("api_key")
        self.timeout = docling_serve_config.get("timeout", 300)
        self.poll_interval = docling_serve_config.get("poll_interval", 2)
        self.max_retries = docling_serve_config.get("max_retries", 3)

        # Build processing options
        self.processing_options = {
            "do_ocr": docling_serve_config.get("do_ocr", True),
            "pdf_backend": docling_serve_config.get("pdf_backend", "dlparse_v2"),
        }

        # Add optional parameters if present
        if "ocr_engine" in docling_serve_config:
            self.processing_options["ocr_engine"] = docling_serve_config["ocr_engine"]
        if "ocr_languages" in docling_serve_config:
            self.processing_options["ocr_languages"] = docling_serve_config["ocr_languages"]
        if "table_mode" in docling_serve_config:
            self.processing_options["table_mode"] = docling_serve_config["table_mode"]
        if "image_export_mode" in docling_serve_config:
            self.processing_options["image_export_mode"] = docling_serve_config["image_export_mode"]

        logger.info("Initialized DoclingServeAdapter with base_url: %s, timeout: %s", self.base_url, self.timeout)

    def extract_single_document(self, *, file_path: str, binary_content: bytes, **kwargs: Any) -> dict[str, Any]:
        """Extract content from a single document using Docling Serve API.

        Sends the document to a remote Docling Serve instance for extraction.
        Polls for results and returns the extracted markdown content.

        Args:
            file_path: Path to the document file (used for logging)
            binary_content: Binary content of the document
            **kwargs: Additional parameters (currently unused)

        Returns:
            Dictionary containing:
                - success: True if extraction succeeded
                - doc_content: Extracted content as markdown
                - metadata: Extraction metadata (processing_time, page_count, etc.)
                - error: Error message if extraction failed
        """
        logger.info("Processing file with docling-serve: %s", file_path)

        try:
            # Initialize client and process document
            client = DoclingServeClient(
                base_url=self.base_url,
                api_key=self.api_key,
                timeout=self.timeout,
                poll_interval=self.poll_interval,
                max_retries=self.max_retries,
            )
            result = client.process_document(binary_content=binary_content, options=self.processing_options)
            # Debug: Log the full result structure
            logger.debug(f"Docling-serve result structure for {file_path}: {result}")
            logger.debug(
                f"Docling-serve result keys: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}"
            )
            # Extract markdown and metadata from v1 API response format
            # v1 API returns: {"document": {"md_content": "...", ...}, "processing_time": ..., ...}
            document = result.get("document", {})
            logger.info(
                f"Document object keys: {list(document.keys()) if isinstance(document, dict) else 'Not a dict'}"
            )
            markdown_text = document.get("md_content", "")
            logger.info(f"Extracted markdown length: {len(markdown_text) if markdown_text else 0}")
            metadata = {"processing_time": result.get("processing_time", 0)}
            if "page_count" in result:
                metadata["page_count"] = result["page_count"]

            logger.info("Completed docling-serve extraction for %s", file_path)
            return {
                OperatorConstants.Extraction.SUCCESS: True,
                OperatorConstants.Columns.DOC_COLUMN_DEFAULT: markdown_text,
                OperatorConstants.Metadata.METADATA: metadata,
            }
        except Exception as e:
            logger.error("Error extracting with docling-serve from %s: %s", file_path, str(e))
            return {
                OperatorConstants.Extraction.SUCCESS: False,
                OperatorConstants.Extraction.ERROR: str(e),
                OperatorConstants.Columns.DOC_COLUMN_DEFAULT: None,
            }
