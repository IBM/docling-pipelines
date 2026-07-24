"""Docling Serve remote extraction adapter.

This adapter implements remote document extraction using the Docling Serve API.
It delegates extraction to a remote Docling Serve instance, enabling distributed
processing and reducing local resource requirements.
"""

import json
import logging
from pathlib import Path
from typing import Any, ClassVar

from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.extract.ports.outbound.text_extraction import TextExtractionPort
from docpipe.core.operators.operator_utils import OperatorUtils
from docpipe.integrations.docling.client import DoclingServeClient
from docpipe.utils.infrastructure.logging import get_logger

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
            - base_url: Docling Serve API endpoint (default: "http://localhost:5001")
            - api_key: Optional API key for authentication
            - timeout: Request timeout in seconds (default: 300)
            - poll_interval: Polling interval in seconds (default: 2)
            - max_retries: Maximum retry attempts (default: 3)
            - verify_ssl: Enable SSL certificate verification (default: True)
                         Set to False only for internal testing with self-signed certificates
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

    # Maps format name -> docling-serve API response field name.
    FORMAT_API_FIELD_MAPPING: ClassVar[dict[str, str]] = {
        OperatorConstants.Extraction.OUTPUT_FORMAT_HTML: "html_content",
        OperatorConstants.Extraction.OUTPUT_FORMAT_JSON: "json_content",
        OperatorConstants.Extraction.OUTPUT_FORMAT_TEXT: "text_content",
        OperatorConstants.Extraction.OUTPUT_FORMAT_DOCTAGS: "doctags_content",
        OperatorConstants.Extraction.OUTPUT_FORMAT_DOCLANG: "doclang_content",
    }

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
        self.base_url = docling_serve_config.get("base_url", "http://localhost:5001")
        self.api_key = docling_serve_config.get(OperatorConstants.Config.API_KEY)
        self.timeout = docling_serve_config.get("timeout", 300)
        self.poll_interval = docling_serve_config.get("poll_interval", 2)
        self.max_retries = docling_serve_config.get("max_retries", 3)
        self.verify_ssl = docling_serve_config.get("verify_ssl", True)

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
            file_path: Path to the document file (used for logging and filename preservation)
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
            file_suffix = Path(file_path).suffix.lower()
            if not file_suffix:
                file_suffix = OperatorUtils.detect_extension_from_bytes(binary_content)

            # Handle .txt specially (Docling cannot process them)
            if file_suffix in [OperatorConstants.Extraction.TEXT_EXTENSION]:
                return OperatorUtils.extract_text_file(
                    file_path=file_path,
                    binary_content=binary_content,
                    additional_formats=self.additional_formats,
                )

            # Extract filename from path to preserve extension for remote processing
            filename = Path(file_path).name

            # Initialize client and process document
            client = DoclingServeClient(
                base_url=self.base_url,
                api_key=self.api_key,
                timeout=self.timeout,
                poll_interval=self.poll_interval,
                max_retries=self.max_retries,
                verify_ssl=self.verify_ssl,
            )
            result = client.process_document(
                binary_content=binary_content,
                filename=filename,
                options=self.processing_options,
            )
            # Debug: Log the full result structure
            logger.debug(
                f"Docling-serve result keys: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}"
            )
            # Extract content from v1 API response format
            # v1 API returns: {"document": {"md_content": "...", ...}, "processing_time": ..., ...}
            document = result.get("document", {})
            logger.info(
                f"Document object keys: {list(document.keys()) if isinstance(document, dict) else 'Not a dict'}"
            )
            markdown_text = document.get("md_content", "")
            logger.info(f"Extracted markdown length: {len(markdown_text) if markdown_text else 0} for file {file_path}")

            # Build result dictionary starting with mandatory markdown
            result_dict: dict[str, Any] = {
                OperatorConstants.Extraction.SUCCESS: True,
                OperatorConstants.Columns.DOC_COLUMN_DEFAULT: markdown_text,
            }

            # Add additional formats if they were requested and are present in response
            formats_generated = [OperatorConstants.Extraction.OUTPUT_FORMAT_MARKDOWN]

            for fmt in self.additional_formats:
                if fmt in self.FORMAT_API_FIELD_MAPPING and fmt in OperatorConstants.Extraction.FORMAT_COLUMN_MAPPING:
                    api_field = self.FORMAT_API_FIELD_MAPPING[fmt]
                    output_column = OperatorConstants.Extraction.FORMAT_COLUMN_MAPPING[fmt]
                    if api_field in document:
                        content = document.get(api_field, "")
                        # Special handling for JSON format: serialise the dict response to a string
                        if fmt == OperatorConstants.Extraction.OUTPUT_FORMAT_JSON and content:
                            content = json.dumps(content, indent=2) if content else ""
                        result_dict[output_column] = content
                        formats_generated.append(fmt)
                        logger.info(f"Generated {fmt} format for {file_path}")

            # Build metadata
            metadata = {
                "processing_time": result.get("processing_time", 0),
                "char_count": len(markdown_text) if markdown_text else 0,
                "formats": formats_generated,
            }

            # Add page count if available from json_content
            json_content = document.get("json_content", {})
            if json_content and isinstance(json_content, dict):
                pages = json_content.get("pages", {})
                if pages:
                    metadata[OperatorConstants.Metadata.PAGE_COUNT] = len(pages)

            result_dict[OperatorConstants.Metadata.METADATA] = metadata

            logger.info(f"Completed docling-serve extraction for {file_path} (formats: {formats_generated})")
            return result_dict

        except Exception as e:
            logger.error("Error extracting with docling-serve from %s: %s", file_path, str(e))
            return {
                OperatorConstants.Extraction.SUCCESS: False,
                OperatorConstants.Extraction.ERROR: str(e),
                OperatorConstants.Columns.DOC_COLUMN_DEFAULT: None,
            }
