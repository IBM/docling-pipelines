#!/usr/bin/env python3
"""
Extract Docling Operator
Implements document extraction using Docling's DocumentConverter and DocumentExtractor.
Follows the structure of IngestLocalOperator with AbstractOperator as parent class.
"""

import json
import logging
import os
import tempfile
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import pyarrow as pa
from docling.datamodel.base_models import InputFormat
from docling.document_converter import DocumentConverter

from common.clients.vlm_pipeline_options_provider import VlmPipelineOptionsProviderFactory
from common.constants.constants import (
    AttributeDataTypes,
    DatasiftConstants,
    ExecutionStatus,
    Metrics,
)
from common.constants.operator_constants import OperatorConstants
from common.exceptions.datasift_exceptions import FlowExecutionFailedException

# Import TransformUtils from centralized location
from common.util.data.transform import TransformUtils
from common.util.document_class_utils import DocumentClassUtils
from common.util.infrastructure.logging import get_logger
from core.operators.abstract_operator import AbstractOperator, OperatorCategory
from core.operators.functional.doc_id_hash import DocIdHashOperator
from core.operators.operator_utils import OperatorUtils

logger: logging.Logger = get_logger()

# Docling-serve supported file extensions (as of v1 API)
# Based on: docx, pptx, html, image, pdf, asciidoc, md, csv, xlsx, xml_*, audio, vtt, latex
DOCLING_SERVE_SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".pptx",
    ".html",
    ".htm",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".asciidoc",
    ".adoc",
    ".md",
    ".csv",
    ".xlsx",
    ".xls",
    ".xml",
    ".json",
    ".mp3",
    ".wav",
    ".vtt",
    ".tex",
    ".latex",
}


def _extract_with_template_worker(file_path: str, binary_content: bytes, template: dict | None) -> dict[str, Any]:
    """
    Worker function for template-based extraction - designed to run in parallel.

    Args:
        file_path: Path to the document file
        binary_content: Binary content of the document
        template: Template dictionary for structured extraction (None falls back to basic extraction)

    Returns:
        Dictionary containing extracted structured data
    """
    logger.info("Processing file with template: %s", file_path)

    try:
        from docling.document_extractor import DocumentExtractor

        # Save binary content to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file_path).suffix) as tmp_file:
            tmp_file.write(binary_content)
            tmp_path = tmp_file.name

        try:
            # Initialize extractor (each worker gets its own instance)
            extractor = DocumentExtractor(allowed_formats=[InputFormat.IMAGE, InputFormat.PDF])

            # Extract with template if provided
            if template:
                result = extractor.extract(source=tmp_path, template=template)
            else:
                # Fall back to basic extraction if no template
                logger.warning("No template provided for %s, using basic extraction", file_path)
                return OperatorUtils.extract_basic_worker(
                    file_path, binary_content, extract_tables=True, extract_images=True
                )

            # Convert pages to proper dict format
            pages_data = []
            for page in result.pages:
                page_dict = {
                    OperatorConstants.Extraction.PAGE_NO: page.page_no,
                    OperatorConstants.Columns.EXTRACTED_DATA: page.extracted_data,
                    OperatorConstants.Columns.RAW_TEXT: page.raw_text,
                    OperatorConstants.Extraction.ERRORS: page.errors,
                }
                pages_data.append(page_dict)

            logger.info("Saved structured results for %s", file_path)

            return {
                OperatorConstants.Extraction.SUCCESS: True,
                OperatorConstants.Columns.DOC_COLUMN_DEFAULT: json.dumps(pages_data, indent=2),
                OperatorConstants.Columns.STRUCTURED_DATA: pages_data,
                OperatorConstants.Metadata.METADATA: {"page_count": len(pages_data)},
            }
        finally:
            # Clean up temporary file
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    except ImportError as e:
        logger.error("DocumentExtractor not available. Install with: pip install docling[vlm]")
        logger.error(f"Error: {e!s}")
        return {
            OperatorConstants.Extraction.SUCCESS: False,
            OperatorConstants.Extraction.ERROR: "DocumentExtractor not available",
            OperatorConstants.Columns.DOC_COLUMN_DEFAULT: None,
        }
    except Exception as e:
        logger.error(f"Error extracting with template: {e!s}")
        return {
            OperatorConstants.Extraction.SUCCESS: False,
            OperatorConstants.Extraction.ERROR: str(e),
            OperatorConstants.Columns.DOC_COLUMN_DEFAULT: None,
        }


def _ensure_markdown_format_for_api_engines(vlm_options: Any, preset: str) -> None:
    """
    Ensure MARKDOWN format for API-based VLM engines.

    DOCTAGS format is specific to IBM Granite models, while MARKDOWN is universally
    supported by all VLM models (including Granite). This function converts DOCTAGS
    to MARKDOWN for maximum compatibility across all API-based engines.

    Args:
        vlm_options: VLM options from preset
        preset: Preset name for logging
    """
    from docling.datamodel.pipeline_options_vlm_model import ResponseFormat

    if vlm_options.model_spec.response_format == ResponseFormat.DOCTAGS:
        logger.info(f"Preset '{preset}' uses DOCTAGS format. Converting to MARKDOWN for universal API compatibility.")
        vlm_options.model_spec.response_format = ResponseFormat.MARKDOWN
        vlm_options.model_spec.prompt = (
            "Convert this document page to markdown format. Include all text, tables, and structure."
        )
        vlm_options.model_spec.stop_strings = []


def _configure_vlm_engine(
    *, vlm_engine_type: str | None, vlm_preset: str, vlm_provider_config: dict[str, Any] | None = None
):
    """
    Configure VLM pipeline options based on engine type.

    Args:
        vlm_engine_type: Engine type ("transformers", "mlx", or "api" variants).
                        If None, returns None to let Docling use its defaults.
        vlm_preset: VLM preset name (e.g., "granite_docling")
        vlm_provider_config: Provider-specific configuration dictionary

    Returns:
        VlmPipelineOptions configured for the engine, or None to use Docling defaults

    Raises:
        ValueError: If required parameters are missing for the selected engine
    """
    # If no engine type and no provider config, return None to use Docling's defaults
    # This supports the simplest case: just set use_vlm_pipeline=True
    if not vlm_engine_type and not vlm_provider_config:
        logger.info("No VLM engine configuration provided - using Docling defaults")
        return None

    # Get pipeline options provider for the specified engine type
    provider = VlmPipelineOptionsProviderFactory.get_provider(engine_type=vlm_engine_type)

    # Create complete pipeline options using the provider
    provider_config = vlm_provider_config or {}
    pipeline_options = provider.create_pipeline_options(preset=vlm_preset, config=provider_config)

    return pipeline_options


def _extract_vlm_worker(
    file_path: str,
    binary_content: bytes,
    vlm_preset: str,
    vlm_engine_type: str | None = None,
    vlm_provider_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Worker function for VLM-based extraction using presets - designed to run in parallel.

    Args:
        file_path: Path to the document file
        binary_content: Binary content of the document
        vlm_preset: VLM preset name (e.g., "granite_docling")
        vlm_engine_type: Engine type ("transformers", "mlx", or "api" variants)
        vlm_provider_config: Provider-specific configuration dictionary

    Returns:
        Dictionary containing extracted markdown content
    """
    logger.info(f"Processing file with VLM pipeline (preset: {vlm_preset}, engine: {vlm_engine_type}): {file_path}")

    try:
        # Import VLM-specific classes
        from docling.document_converter import ImageFormatOption, PdfFormatOption
        from docling.pipeline.vlm_pipeline import VlmPipeline
        from docling_core.types.doc.document import PictureItem, TableItem
    except ImportError as e:
        logger.error("VLM pipeline dependencies not available. Install with: pip install docling[vlm]")
        logger.error(f"Error: {e!s}")
        return {
            OperatorConstants.Extraction.SUCCESS: False,
            OperatorConstants.Extraction.ERROR: "VLM pipeline dependencies not available. Install docling[vlm]",
            OperatorConstants.Columns.DOC_COLUMN_DEFAULT: None,
        }

    # Determine the effective file extension
    file_suffix = Path(file_path).suffix.lower()
    if not file_suffix:
        file_suffix = OperatorUtils.detect_extension_from_bytes(binary_content)

    # Save binary content to temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=file_suffix) as tmp_file:
        tmp_file.write(binary_content)
        tmp_path = tmp_file.name

    try:
        # Configure VLM pipeline options (includes remote services configuration)
        pipeline_options = _configure_vlm_engine(
            vlm_engine_type=vlm_engine_type,
            vlm_preset=vlm_preset,
            vlm_provider_config=vlm_provider_config,
        )

        # Set up converter with VLM pipeline
        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_cls=VlmPipeline,
                    pipeline_options=pipeline_options,
                ),
                InputFormat.IMAGE: ImageFormatOption(
                    pipeline_cls=VlmPipeline,
                    pipeline_options=pipeline_options,
                ),
            }
        )

        # Convert document
        result = converter.convert(tmp_path)

        # Export to markdown
        markdown_text = result.document.export_to_markdown()

        # Extract tables
        tables = []
        for item, _ in result.document.iterate_items():
            if isinstance(item, TableItem):
                table_df = item.export_to_dataframe()
                tables.append({"ref": item.self_ref, "data": table_df.to_dict() if table_df is not None else None})

        # Extract images
        images = []
        for item, _ in result.document.iterate_items():
            if isinstance(item, PictureItem):
                images.append({"ref": item.self_ref, "caption": getattr(item, "caption", None)})

        logger.info(f"Completed VLM extraction for {file_path}")

        return {
            OperatorConstants.Extraction.SUCCESS: True,
            OperatorConstants.Columns.DOC_COLUMN_DEFAULT: markdown_text,
            OperatorConstants.Columns.TABLES: tables,
            OperatorConstants.Columns.IMAGES: images,
            OperatorConstants.Metadata.METADATA: {
                "table_count": len(tables),
                "image_count": len(images),
                "char_count": len(markdown_text),
                "vlm_preset": vlm_preset,
                "vlm_engine_type": vlm_engine_type or OperatorConstants.Config.VLM_ENGINE_TRANSFORMERS,
            },
        }
    except Exception as e:
        logger.error(f"Error extracting content with VLM pipeline from {file_path}: {e!s}")
        return {
            OperatorConstants.Extraction.SUCCESS: False,
            OperatorConstants.Extraction.ERROR: str(e),
            OperatorConstants.Columns.DOC_COLUMN_DEFAULT: None,
        }
    finally:
        # Clean up temporary file
        try:
            os.unlink(tmp_path)
        except OSError as e:
            logger.warning(f"Failed to cleanup temporary file {tmp_path}: {e}")


def _extract_with_docling_serve_worker(
    file_path: str, binary_content: bytes, docling_serve_config: dict[str, Any]
) -> dict[str, Any]:
    """
    Worker function for docling-serve extraction - designed to run in parallel.

    Args:
        file_path: Path to the document file
        binary_content: Binary content of the document
        docling_serve_config: Configuration dict with base_url, api_key, timeout, etc.

    Returns:
        Dictionary containing extracted markdown content and metadata
    """
    logger.info(f"Processing file with docling-serve: {file_path}")

    # Check if file extension is supported by docling-serve BEFORE making API call
    file_extension = file_path.lower().split(".")[-1] if "." in file_path else ""
    file_ext_with_dot = f".{file_extension}"

    if file_ext_with_dot not in DOCLING_SERVE_SUPPORTED_EXTENSIONS:
        # For unsupported formats (e.g., .txt), decode binary content directly
        logger.info(
            f"File extension '{file_ext_with_dot}' not supported by docling-serve. Using direct text extraction for: {file_path}"
        )
        try:
            text_content = binary_content.decode("utf-8", errors="ignore").strip()
            if text_content:
                return {
                    OperatorConstants.Extraction.SUCCESS: True,
                    OperatorConstants.Columns.DOC_COLUMN_DEFAULT: text_content,
                    OperatorConstants.Metadata.METADATA: {"extraction_method": "direct_decode"},
                }
            else:
                return {
                    OperatorConstants.Extraction.SUCCESS: False,
                    OperatorConstants.Extraction.ERROR: "Empty content after decoding",
                    OperatorConstants.Columns.DOC_COLUMN_DEFAULT: None,
                }
        except Exception as decode_error:
            logger.error(f"Failed to decode unsupported file {file_path}: {decode_error}")
            return {
                OperatorConstants.Extraction.SUCCESS: False,
                OperatorConstants.Extraction.ERROR: f"Decode error: {decode_error!s}",
                OperatorConstants.Columns.DOC_COLUMN_DEFAULT: None,
            }

    try:
        from common.clients.docling_serve_client import DoclingServeClient

        # Extract config parameters
        base_url = docling_serve_config.get("base_url", "http://0.0.0.0:5001")
        api_key = docling_serve_config.get("api_key")
        timeout = docling_serve_config.get("timeout", 300)
        poll_interval = docling_serve_config.get("poll_interval", 2)
        max_retries = docling_serve_config.get("max_retries", 3)

        # Build processing options
        options = {
            "do_ocr": docling_serve_config.get("do_ocr", True),
            "pdf_backend": docling_serve_config.get("pdf_backend", "dlparse_v2"),
        }
        if "ocr_engine" in docling_serve_config:
            options["ocr_engine"] = docling_serve_config["ocr_engine"]
        if "ocr_languages" in docling_serve_config:
            options["ocr_languages"] = docling_serve_config["ocr_languages"]
        if "table_mode" in docling_serve_config:
            options["table_mode"] = docling_serve_config["table_mode"]
        if "image_export_mode" in docling_serve_config:
            options["image_export_mode"] = docling_serve_config["image_export_mode"]

        # Initialize client and process document
        client = DoclingServeClient(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            poll_interval=poll_interval,
            max_retries=max_retries,
        )
        result = client.process_document(binary_content=binary_content, options=options)

        # Debug: Log the full result structure
        logger.debug(f"Docling-serve result structure for {file_path}: {result}")
        logger.debug(f"Docling-serve result keys: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}")

        # Extract markdown and metadata from v1 API response format
        # v1 API returns: {"document": {"md_content": "...", ...}, "processing_time": ..., ...}
        document = result.get("document", {})
        logger.info(f"Document object keys: {list(document.keys()) if isinstance(document, dict) else 'Not a dict'}")

        # Fallback strategy for content extraction: try md_content first, then text_content, then html_content
        # Text files typically populate text_content instead of md_content in docling-serve responses
        markdown_text = (
            (document.get("md_content") or "").strip()
            or (document.get("text_content") or "").strip()
            or (document.get("html_content") or "").strip()
            or ""
        )
        logger.info(f"Extracted content length: {len(markdown_text) if markdown_text else 0}")

        metadata = {"processing_time": result.get("processing_time", 0)}
        if "page_count" in result:
            metadata["page_count"] = result["page_count"]

        logger.info(f"Completed docling-serve extraction for {file_path}")
        return {
            OperatorConstants.Extraction.SUCCESS: True,
            OperatorConstants.Columns.DOC_COLUMN_DEFAULT: markdown_text,
            OperatorConstants.Metadata.METADATA: metadata,
        }
    except Exception as e:
        logger.error(f"Error extracting with docling-serve from {file_path}: {e!s}")
        return {
            OperatorConstants.Extraction.SUCCESS: False,
            OperatorConstants.Extraction.ERROR: str(e),
            OperatorConstants.Columns.DOC_COLUMN_DEFAULT: None,
        }


class ExtractDoclingOperator(AbstractOperator):
    """
    Operator for extracting content from documents using Docling.
    Follows the structure of IngestLocalOperator with AbstractOperator as parent class.

    This operator extracts content from documents using Docling's DocumentConverter
    and optionally DocumentExtractor for template-based extraction.
    """

    short_name: str = OperatorConstants.Operators.EXTRACT_DOCLING
    category: OperatorCategory = OperatorCategory.Extract

    def __init__(self, config: dict[str, Any]) -> None:
        """
        Initialize the operator with configuration.

        Args:
            config: Configuration dictionary containing:
                - doc_column: Name of the column to store document content (default: "content")
                - doc_id_hash: Name of the column to store document hash (default: "doc_id_hash")
                - extract_tables: Whether to extract tables (default: True)
                - extract_images: Whether to extract images (default: True)
                - use_template: Whether to use template-based extraction (default: False)
                - template: Template dictionary for structured extraction (optional)
                - expand_extracted_data: Whether to expand extracted_data into individual columns (default: False)
                - use_vlm_pipeline: Whether to use VLM pipeline for enhanced extraction (default: False)
                - vlm_preset: VLM preset name (default: "granite_docling")
                - vlm_engine_type: VLM engine type - "transformers" or "mlx" (default: None/auto)
                - use_docling_serve: Whether to use docling-serve for remote extraction (default: False)
                - docling_serve_base_url: Base URL for docling-serve service
                - docling_serve_api_key: API key for docling-serve authentication (optional)
                - docling_serve_timeout: Request timeout for docling-serve in seconds
                - docling_serve_poll_interval: Poll interval for docling-serve task status in seconds
                - docling_serve_max_retries: Maximum retries for docling-serve polling
                - docling_serve_ocr_preset: OCR preset for docling-serve (e.g., "auto", "tesseract", "easyocr")
                - docling_serve_ocr_lang: OCR languages for docling-serve (list of language codes)
                - docling_serve_pdf_backend: PDF backend for docling-serve
                - docling_serve_table_mode: Table extraction mode for docling-serve
                - docling_serve_image_export_mode: Image export mode for docling-serve
                - max_workers: Maximum number of parallel workers (default: auto-detect)
                - use_processes: Use ProcessPoolExecutor instead of ThreadPoolExecutor (default: False)
        """
        super().__init__(config)
        self.doc_column: str = config.get(
            OperatorConstants.Columns.DOC_COLUMN, OperatorConstants.Columns.DOC_COLUMN_DEFAULT
        )
        self.doc_id_hash: str = config.get(
            OperatorConstants.Columns.DOC_ID_HASH, OperatorConstants.Columns.DOC_ID_HASH_DEFAULT
        )
        self.extract_tables: bool = config.get(OperatorConstants.Config.EXTRACT_TABLES, True)
        self.extract_images: bool = config.get(OperatorConstants.Config.EXTRACT_IMAGES, True)
        self.use_template: bool = config.get(OperatorConstants.Config.USE_TEMPLATE, False)
        self.template: dict[str, Any] | None = config.get(OperatorConstants.Config.TEMPLATE)
        self.expand_extracted_data: bool = config.get(OperatorConstants.Config.EXPAND_EXTRACTED_DATA, False)

        # VLM Pipeline configuration
        self.use_vlm_pipeline: bool = config.get(OperatorConstants.Config.USE_VLM_PIPELINE, False)
        self.vlm_preset: str = config.get(
            OperatorConstants.Config.VLM_PRESET, OperatorConstants.Config.VLM_PRESET_DEFAULT
        )
        self.vlm_engine_type: str | None = config.get(
            OperatorConstants.Config.VLM_ENGINE_TYPE, OperatorConstants.Config.VLM_ENGINE_TRANSFORMERS
        )
        self.vlm_provider_config: dict[str, Any] | None = config.get(OperatorConstants.Config.VLM_PROVIDER_CONFIG)

        # Validate VLM preset if VLM pipeline is enabled
        if self.use_vlm_pipeline and self.vlm_preset:
            try:
                from docling.datamodel.pipeline_options import VlmConvertOptions

                # Test if preset is valid by attempting to load it
                VlmConvertOptions.from_preset(self.vlm_preset)
            except Exception as e:
                raise ValueError(
                    f"Invalid vlm_preset: '{self.vlm_preset}'. "
                    f"Error: {e!s}. "
                    f"Please verify the preset name is correct (e.g., 'granite_docling')."
                ) from e

        # Validate VLM engine type
        valid_engines = [
            OperatorConstants.Config.VLM_ENGINE_TRANSFORMERS,
            OperatorConstants.Config.VLM_ENGINE_MLX,
            OperatorConstants.Config.VLM_ENGINE_API,
            OperatorConstants.Config.VLM_ENGINE_API_LMSTUDIO,
            OperatorConstants.Config.VLM_ENGINE_API_OLLAMA,
            OperatorConstants.Config.VLM_ENGINE_API_OPENAI,
            OperatorConstants.Config.VLM_ENGINE_API_WATSONX,
        ]
        if self.vlm_engine_type and self.vlm_engine_type not in valid_engines:
            raise ValueError(f"Invalid vlm_engine_type: {self.vlm_engine_type}. Must be one of {valid_engines}")

        # Validate provider configuration for API-based engines
        if self.use_vlm_pipeline and self.vlm_engine_type:
            provider = VlmPipelineOptionsProviderFactory.get_provider(engine_type=self.vlm_engine_type)
            if provider and self.vlm_provider_config:
                # Validate provider-specific configuration
                try:
                    provider.validate_config(config=self.vlm_provider_config)
                except ValueError as e:
                    raise ValueError(f"Invalid vlm_provider_config for {self.vlm_engine_type}: {e}") from e

        # Validate mutually exclusive modes
        if self.use_vlm_pipeline and self.use_template:
            raise ValueError("Cannot use both VLM pipeline and template extraction simultaneously")

        # Docling-serve configuration
        self.use_docling_serve: bool = config.get(OperatorConstants.Config.USE_DOCLING_SERVE, False)

        # Only read docling-serve config if use_docling_serve is True
        if self.use_docling_serve:
            self.docling_serve_base_url: str = config.get(OperatorConstants.Config.DOCLING_SERVE_BASE_URL, "")
            self.docling_serve_api_key: str | None = config.get(OperatorConstants.Config.DOCLING_SERVE_API_KEY)
            self.docling_serve_timeout: int = config.get(OperatorConstants.Config.DOCLING_SERVE_TIMEOUT, 300)
            self.docling_serve_poll_interval: int = config.get(OperatorConstants.Config.DOCLING_SERVE_POLL_INTERVAL, 2)
            self.docling_serve_max_retries: int = config.get(OperatorConstants.Config.DOCLING_SERVE_MAX_RETRIES, 3)

            # Support both old and new parameter names for backward compatibility
            # New parameters take precedence
            self.docling_serve_do_ocr: bool = config.get(OperatorConstants.Config.DOCLING_SERVE_DO_OCR, True)
            self.docling_serve_ocr_preset: str = config.get(
                OperatorConstants.Config.DOCLING_SERVE_OCR_PRESET,
                config.get(OperatorConstants.Config.DOCLING_SERVE_OCR_ENGINE, "easyocr"),
            )
            self.docling_serve_ocr_lang: list[str] | None = config.get(
                OperatorConstants.Config.DOCLING_SERVE_OCR_LANG,
                config.get(OperatorConstants.Config.DOCLING_SERVE_OCR_LANGUAGES, []),
            )

            self.docling_serve_pdf_backend: str = config.get(
                OperatorConstants.Config.DOCLING_SERVE_PDF_BACKEND, "dlparse_v2"
            )
            self.docling_serve_table_mode: str = config.get(OperatorConstants.Config.DOCLING_SERVE_TABLE_MODE, "fast")
            self.docling_serve_image_export_mode: str = config.get(
                OperatorConstants.Config.DOCLING_SERVE_IMAGE_EXPORT_MODE, "placeholder"
            )
        else:
            # Set defaults when not using docling-serve
            self.docling_serve_base_url = ""
            self.docling_serve_api_key = None
            self.docling_serve_timeout = 300
            self.docling_serve_poll_interval = 2
            self.docling_serve_max_retries = 3
            self.docling_serve_ocr_preset = "easyocr"
            self.docling_serve_ocr_lang = None
            self.docling_serve_pdf_backend = "dlparse_v2"
            self.docling_serve_table_mode = "fast"
            self.docling_serve_image_export_mode = "placeholder"

        self._validate_extraction_modes()
        self._validate_vlm_config()
        self._validate_docling_serve_config()

        # Parallel processing configuration
        self.max_workers: int = config.get(
            OperatorConstants.Config.MAX_WORKERS, OperatorUtils.get_optimal_workers(is_cpu_intensive=self.use_template)
        )
        self.use_processes: bool = config.get(OperatorConstants.Config.USE_PROCESSES, False)

        self.common_log_arguments: dict[str, Any] = {
            DatasiftConstants.JOB_ID: self.job_id,
            DatasiftConstants.JOB_RUN_ID: self.job_run_id,
        }

        # Initialize Docling converter
        self.converter: DocumentConverter = DocumentConverter()

        # Initialize DocumentExtractor if template extraction is enabled
        self.extractor: Any | None = None
        if self.use_template and self.template:
            try:
                from docling.document_extractor import DocumentExtractor

                self.extractor = DocumentExtractor(allowed_formats=[InputFormat.IMAGE, InputFormat.PDF])
            except ImportError:
                logger.warning("DocumentExtractor not available. Install with: pip install docling[vlm]")
                self.use_template = False

        logger.info(
            "Initialized ExtractDoclingOperator with %s workers using %s (template=%s, vlm=%s, docling_serve=%s)",
            self.max_workers,
            "ProcessPoolExecutor" if self.use_processes else "ThreadPoolExecutor",
            self.use_template,
            self.use_vlm_pipeline,
            self.use_docling_serve,
        )

    def _validate_extraction_modes(self) -> None:
        enabled_modes = [self.use_template, self.use_vlm_pipeline, self.use_docling_serve]
        if sum(enabled_modes) > 1:
            raise FlowExecutionFailedException(
                "use_docling_serve, use_vlm_pipeline, and use_template are mutually exclusive"
            )

    def _validate_vlm_config(self) -> None:
        if self.use_vlm_pipeline and self.vlm_preset:
            try:
                from docling.datamodel.pipeline_options import VlmConvertOptions

                VlmConvertOptions.from_preset(self.vlm_preset)
            except Exception as e:
                raise FlowExecutionFailedException(
                    f"Invalid vlm_preset: '{self.vlm_preset}'. "
                    f"Error: {e!s}. "
                    f"Please verify the preset name is correct (e.g., 'granite_docling')."
                ) from e

        valid_engines = [
            OperatorConstants.Config.VLM_ENGINE_TRANSFORMERS,
            OperatorConstants.Config.VLM_ENGINE_MLX,
            OperatorConstants.Config.VLM_ENGINE_API,
            OperatorConstants.Config.VLM_ENGINE_API_LMSTUDIO,
            OperatorConstants.Config.VLM_ENGINE_API_OLLAMA,
            OperatorConstants.Config.VLM_ENGINE_API_OPENAI,
            OperatorConstants.Config.VLM_ENGINE_API_WATSONX,
        ]
        if self.vlm_engine_type and self.vlm_engine_type not in valid_engines:
            raise FlowExecutionFailedException(
                f"Invalid vlm_engine_type: {self.vlm_engine_type}. Must be one of {valid_engines}"
            )
        # Validate provider config for API-based engines
        if self.vlm_engine_type == OperatorConstants.Config.VLM_ENGINE_API:
            if not self.vlm_provider_config or not self.vlm_provider_config.get(
                OperatorConstants.Config.VLM_API_BASE_URL
            ):
                raise FlowExecutionFailedException(
                    "vlm_api_base_url is required in vlm_provider_config when vlm_engine_type='api'. "
                    "Provide the API endpoint (e.g., 'https://us-south.ml.cloud.ibm.com/ml/v1/text/chat?version=2023-05-29' for watsonx.ai)"
                )

        if self.vlm_engine_type == OperatorConstants.Config.VLM_ENGINE_API_WATSONX:
            if not self.vlm_provider_config or not self.vlm_provider_config.get(OperatorConstants.Config.VLM_API_KEY):
                raise FlowExecutionFailedException(
                    "vlm_api_key is required in vlm_provider_config when vlm_engine_type='api_watsonx'. "
                    "Provide the IBM Cloud API key for watsonx.ai authentication."
                )

    def _validate_docling_serve_config(self) -> None:
        if self.use_docling_serve and not self.docling_serve_base_url:
            raise FlowExecutionFailedException("docling_serve_base_url is required when use_docling_serve=True")

    def _get_docling_serve_config(self) -> dict[str, Any]:
        return {
            "base_url": self.docling_serve_base_url,
            "api_key": self.docling_serve_api_key,
            "timeout": self.docling_serve_timeout,
            "poll_interval": self.docling_serve_poll_interval,
            "max_retries": self.docling_serve_max_retries,
            "do_ocr": self.docling_serve_do_ocr,
            "ocr_preset": self.docling_serve_ocr_preset,
            "ocr_lang": self.docling_serve_ocr_lang,
            "pdf_backend": self.docling_serve_pdf_backend,
            "table_mode": self.docling_serve_table_mode,
            "image_export_mode": self.docling_serve_image_export_mode,
        }

    def _submit_extraction_task(
        self,
        executor: ProcessPoolExecutor | ThreadPoolExecutor,
        task: dict[str, Any],
        document_types: list[str],
        template_cache: dict[str, dict],
    ):
        # Determine which template to use for this document
        template_to_use = self.template
        if self.use_template and document_types and template_cache:
            row_doc_type = document_types[task["idx"]]
            if row_doc_type and row_doc_type in template_cache:
                template_to_use = template_cache[row_doc_type]
                logger.debug("Using template for document type '%s' for %s", row_doc_type, task["doc_name"])

        if self.use_template:
            return executor.submit(
                _extract_with_template_worker, task["doc_name"], task["binary_content"], template_to_use
            )
        if self.use_vlm_pipeline:
            return executor.submit(
                _extract_vlm_worker,
                task["doc_name"],
                task["binary_content"],
                self.vlm_preset,
                self.vlm_engine_type,
                self.vlm_provider_config,
            )
        if self.use_docling_serve:
            return executor.submit(
                _extract_with_docling_serve_worker,
                task["doc_name"],
                task["binary_content"],
                self._get_docling_serve_config(),
            )
        return executor.submit(
            OperatorUtils.extract_basic_worker,
            task["doc_name"],
            task["binary_content"],
            self.extract_tables,
            self.extract_images,
        )

    @staticmethod
    def _expand_extracted_data_columns(table: pa.Table, extracted_data_list: list[Any | None]) -> pa.Table:
        """
        Expand the extracted_data column into individual columns based on the template structure.
        Each key in the extracted_data becomes a separate column in the PyArrow table.

        Args:
            table: PyArrow table to add columns to
            extracted_data_list: List of extracted data dictionaries (one per document)

        Returns:
            PyArrow table with expanded columns
        """
        if not extracted_data_list or not any(extracted_data_list):
            logger.warning("No extracted data to expand")
            return table

        # Collect all unique keys from all documents' extracted data
        all_keys: set[str] = set()
        for data in extracted_data_list:
            if data and isinstance(data, list):
                # Handle list of pages - collect keys from first page's extracted_data
                for page in data:
                    if isinstance(page, dict) and OperatorConstants.Columns.EXTRACTED_DATA in page:
                        page_data = page[OperatorConstants.Columns.EXTRACTED_DATA]
                        if isinstance(page_data, dict):
                            all_keys.update(page_data.keys())
                        break  # Only use first page to determine schema
            elif data and isinstance(data, dict):
                all_keys.update(data.keys())

        if not all_keys:
            logger.warning("No keys found in extracted data to expand")
            return table

        logger.info(f"Expanding extracted_data into {len(all_keys)} columns: {sorted(all_keys)}")

        # Create columns for each key
        for key in sorted(all_keys):
            column_values: list[Any] = []

            for data in extracted_data_list:
                value = None

                if data and isinstance(data, list):
                    # Handle list of pages - extract from first page
                    for page in data:
                        if isinstance(page, dict) and OperatorConstants.Columns.EXTRACTED_DATA in page:
                            page_data = page[OperatorConstants.Columns.EXTRACTED_DATA]
                            if isinstance(page_data, dict):
                                value = page_data.get(key)
                            break
                elif data and isinstance(data, dict):
                    value = data.get(key)

                # Convert value to string for PyArrow compatibility
                if value is not None:
                    column_values.append(str(value))
                else:
                    column_values.append(None)

            # Add column to table
            table = TransformUtils.add_column(table=table, name=f"extracted_{key}", content=column_values)

        return table

    def _check_existing_features(self, table: pa.Table) -> bool:
        if self.doc_column not in table.column_names:
            return False
        if self.use_template:
            if self.expand_extracted_data and not any(col.startswith("extracted_") for col in table.column_names):
                return False
            elif OperatorConstants.Columns.EXTRACTED_DATA not in table.column_names:
                return False
        return True

    def transform(self, table: pa.Table, file_name: str | None = None) -> tuple[list[pa.Table], dict[str, Any]]:
        """
        Transform the input table by extracting content from documents.

        Args:
            table: PyArrow table containing document information with columns:
                - id: Document ID
                - name: Document name/filename
                - path: Document path (optional)
                - binary_content: Binary content of the document (optional)
            file_name: File name (optional)
        Returns:
            Tuple of (list of transformed tables, metadata dictionary)
        """
        metadata = self.create_base_metadata(total_docs_count=table.num_rows)
        if table.num_rows == 0:
            return [table], metadata
        if self._check_existing_features(table=table):
            metadata[OperatorConstants.Extraction.MESSAGE] = (
                "All requested features already present. Moving to next operator"
            )
            return [table], metadata

        document_types: list[str] = []
        template_cache: dict[str, dict] = {}
        if self.use_template and OperatorConstants.Columns.DOCUMENT_TYPE in table.column_names:
            document_types = table.column(OperatorConstants.Columns.DOCUMENT_TYPE).to_pylist()
            DocumentClassUtils.generate_docling_templates_for_types(
                document_types=document_types, template_cache=template_cache, include_nested=True
            )
            if not template_cache:
                logger.warning("No templates could be loaded from document_type column, using default template")

        doc_tasks: list[Any] = OperatorUtils.prepare_document_content_fetch(table=table)
        doc_contents = [None] * table.num_rows
        doc_metadata_list: list[dict[str, Any]] = [{}] * table.num_rows
        extracted_data_list = [None] * table.num_rows
        remove_row_idx: list[int] = []
        executor_class = ProcessPoolExecutor if self.use_processes else ThreadPoolExecutor

        logger.info("Processing %s documents in parallel with %s workers", len(doc_tasks), self.max_workers)
        with executor_class(max_workers=self.max_workers) as executor:
            future_to_task = {}
            for task in doc_tasks:
                if "error" in task:
                    self.record_failed_document(
                        metadata=metadata, doc_id=str(task["doc_id"]), doc_name=task["doc_name"], reason=task["error"]
                    )
                    continue

                future = self._submit_extraction_task(executor, task, document_types, template_cache)
                future_to_task[future] = task

            for future in as_completed(future_to_task):
                task = future_to_task[future]
                idx = task["idx"]
                try:
                    result = future.result()
                    if result[OperatorConstants.Extraction.SUCCESS]:
                        extracted_content = result.get(OperatorConstants.Columns.DOC_COLUMN_DEFAULT)
                        if not extracted_content or (
                            isinstance(extracted_content, str) and not extracted_content.strip()
                        ):
                            self.record_skipped_document(
                                metadata=metadata,
                                doc_id=str(task["doc_id"]),
                                doc_name=task["doc_name"],
                                reason="Empty extracted content",
                            )
                            remove_row_idx.append(idx)
                            logger.warning(
                                "Skipping document %s due to empty extracted content",
                                task["doc_name"],
                                extra=self.common_log_arguments,
                            )
                            continue

                        doc_contents[idx] = extracted_content
                        doc_metadata_list[idx] = result.get(OperatorConstants.Metadata.METADATA, {})
                        if self.use_template and OperatorConstants.Columns.STRUCTURED_DATA in result:
                            extracted_data_list[idx] = result[OperatorConstants.Columns.STRUCTURED_DATA]
                        metadata[Metrics.External.PROCESSED_DOCS] += 1
                        continue

                    self.record_failed_document(
                        metadata=metadata,
                        doc_id=str(task["doc_id"]),
                        doc_name=task["doc_name"],
                        reason=result.get(OperatorConstants.Extraction.ERROR, "Unknown error"),
                    )
                    logger.error(
                        "Failed to extract content from %s: %s",
                        task["doc_name"],
                        result.get(OperatorConstants.Extraction.ERROR),
                        extra=self.common_log_arguments,
                    )
                except Exception as e:
                    logger.error("Error processing document at index %s: %s", idx, e)
                    self.record_failed_document(
                        metadata=metadata, doc_id=str(task["doc_id"]), doc_name=task["doc_name"], reason=str(e)
                    )

        if remove_row_idx:
            table = OperatorUtils.remove_rows(table=table, remove_row_idx=remove_row_idx)
            doc_contents = [content for idx, content in enumerate(doc_contents) if idx not in remove_row_idx]
            extracted_data_list = [data for idx, data in enumerate(extracted_data_list) if idx not in remove_row_idx]

        if doc_contents:
            table = TransformUtils.add_column(table=table, name=self.doc_column, content=doc_contents)
        if self.use_template and extracted_data_list:
            if self.expand_extracted_data:
                logger.info("Expanding extracted_data into individual columns")
                table = self._expand_extracted_data_columns(table, extracted_data_list)
            else:
                extracted_data_json = [json.dumps(data) if data is not None else None for data in extracted_data_list]
                table = TransformUtils.add_column(
                    table=table, name=OperatorConstants.Columns.EXTRACTED_DATA, content=extracted_data_json
                )
                logger.info("Added extracted_data column with structured template extraction results")

        logger.info("Generating hash id and adding it to table")
        hash_operator = DocIdHashOperator({OperatorConstants.Columns.DOC_COLUMN: self.doc_column})
        table_list, _ = hash_operator.transform(table)
        table = table_list[0]

        metadata[Metrics.External.NODE_STATUS] = (
            ExecutionStatus.COMPLETED_WITH_ERRORS.value
            if metadata[Metrics.External.FAILED_DOCS_COUNT] > 0
            else ExecutionStatus.COMPLETED.value
        )
        return [table], metadata

    def get_metadata(self) -> dict[str, Any]:
        """
        Get metadata about the operator including features and attributes.
        Follows the structure of IngestLocalOperator.get_metadata()

        Returns:
            Dictionary containing operator metadata
        """
        metadata_features = {
            OperatorConstants.Columns.DOC_COLUMN_DEFAULT: {
                OperatorConstants.Misc.NAME: "Document Content",
                OperatorConstants.Config.DESCRIPTION: "The markdown content extracted from the document",
                OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: True,
                OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_STRING,
                OperatorConstants.Misc.TAGS: [OperatorConstants.Misc.MANDATORY],
            },
            OperatorConstants.Columns.DOC_ID_HASH_DEFAULT: {
                OperatorConstants.Misc.NAME: "Hash ID",
                OperatorConstants.Config.DESCRIPTION: "Hash ID of the document row",
                OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: True,
                OperatorConstants.Config.MANDATORY_FOR_VECTOR_DB: True,
                OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_STRING,
                OperatorConstants.Misc.IS_PRIMARY: True,
                OperatorConstants.Misc.TAGS: [OperatorConstants.Misc.MANDATORY, OperatorConstants.Misc.PRIMARY],
            },
            OperatorConstants.Columns.EXTRACTED_DATA: {
                OperatorConstants.Misc.NAME: "Extracted Data",
                OperatorConstants.Config.DESCRIPTION: "Structured data extracted using template-based extraction",
                OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: True,
                OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_STRING,
                OperatorConstants.Misc.TAGS: [],
            },
            self.doc_id_hash: {
                OperatorConstants.Misc.NAME: "Hash ID",
                OperatorConstants.Config.DESCRIPTION: "Hash ID of the document row",
                OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: True,
                OperatorConstants.Config.MANDATORY_FOR_VECTOR_DB: True,
                OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_STRING,
                OperatorConstants.Misc.IS_PRIMARY: True,
                OperatorConstants.Misc.TAGS: [OperatorConstants.Misc.MANDATORY, OperatorConstants.Misc.PRIMARY],
            },
        }

        return {
            OperatorConstants.Misc.CATEGORY: self.category.value,
            OperatorConstants.Config.FEATURES: metadata_features,
            OperatorConstants.Misc.IS_OPERATOR_AVAILABLE: self.is_available(),
            OperatorConstants.Config.ATTRIBUTES: {
                OperatorConstants.Columns.DOC_COLUMN: {
                    OperatorConstants.Misc.NAME: "Document Column",
                    OperatorConstants.Config.DESCRIPTION: "Name of the column to store document content",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: OperatorConstants.Columns.DOC_COLUMN_DEFAULT,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                OperatorConstants.Columns.DOC_ID_HASH: {
                    OperatorConstants.Misc.NAME: "Document ID Hash Column",
                    OperatorConstants.Config.DESCRIPTION: "Name of the column to store document hash",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: OperatorConstants.Columns.DOC_ID_HASH_DEFAULT,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                OperatorConstants.Config.EXTRACT_TABLES: {
                    OperatorConstants.Misc.NAME: "Extract Tables",
                    OperatorConstants.Config.DESCRIPTION: "Whether to extract tables from documents",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.BOOLEAN,
                },
                OperatorConstants.Config.EXTRACT_IMAGES: {
                    OperatorConstants.Misc.NAME: "Extract Images",
                    OperatorConstants.Config.DESCRIPTION: "Whether to extract images from documents",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.BOOLEAN,
                },
                OperatorConstants.Config.USE_TEMPLATE: {
                    OperatorConstants.Misc.NAME: "Use Template",
                    OperatorConstants.Config.DESCRIPTION: "Whether to use template-based extraction for structured data",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: False,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.BOOLEAN,
                },
                OperatorConstants.Config.TEMPLATE: {
                    OperatorConstants.Misc.NAME: "Extraction Template",
                    OperatorConstants.Config.DESCRIPTION: "Template dictionary for structured extraction (required if use_template is True)",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: None,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.JSON,
                },
                OperatorConstants.Config.EXPAND_EXTRACTED_DATA: {
                    OperatorConstants.Misc.NAME: "Expand Extracted Data",
                    OperatorConstants.Config.DESCRIPTION: "Whether to expand extracted_data JSON into individual columns",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: False,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.BOOLEAN,
                },
                OperatorConstants.Config.USE_VLM_PIPELINE: {
                    OperatorConstants.Misc.NAME: "Use VLM Pipeline",
                    OperatorConstants.Config.DESCRIPTION: "Enable Vision Language Model pipeline for enhanced document understanding (requires docling[vlm])",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: False,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.BOOLEAN,
                },
                OperatorConstants.Config.VLM_PRESET: {
                    OperatorConstants.Misc.NAME: "VLM Preset",
                    OperatorConstants.Config.DESCRIPTION: "VLM preset name for document processing (e.g., 'granite_docling')",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: OperatorConstants.Config.VLM_PRESET_DEFAULT,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                OperatorConstants.Config.VLM_ENGINE_TYPE: {
                    OperatorConstants.Misc.NAME: "VLM Engine Type",
                    OperatorConstants.Config.DESCRIPTION: "VLM engine: 'transformers' (local, default), 'mlx' (macOS optimized), or 'api' (remote API)",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: OperatorConstants.Config.VLM_ENGINE_TRANSFORMERS,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                OperatorConstants.Config.VLM_PROVIDER_CONFIG: {
                    OperatorConstants.Misc.NAME: "VLM Provider Configuration",
                    OperatorConstants.Config.DESCRIPTION: "Provider-specific configuration dict. Required keys vary by engine type. Watsonx: {'api_key', 'container_id', 'model_id', 'api_base_url'}. Ollama/LMStudio: {'api_base_url'}. OpenAI: {'api_key', 'api_base_url'}",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: None,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.JSON,
                },
                OperatorConstants.Config.USE_DOCLING_SERVE: {
                    OperatorConstants.Misc.NAME: "Use Docling Serve",
                    OperatorConstants.Config.DESCRIPTION: "Enable docling-serve based remote extraction. Mutually exclusive with template and VLM modes.",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: False,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.BOOLEAN,
                },
                OperatorConstants.Config.DOCLING_SERVE_BASE_URL: {
                    OperatorConstants.Misc.NAME: "Docling Serve Base URL",
                    OperatorConstants.Config.DESCRIPTION: "Base URL for the docling-serve service (required when use_docling_serve is True)",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: "http://0.0.0.0:5001",
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                OperatorConstants.Config.DOCLING_SERVE_API_KEY: {
                    OperatorConstants.Misc.NAME: "Docling Serve API Key",
                    OperatorConstants.Config.DESCRIPTION: "Optional API key sent as X-API-KEY when calling docling-serve",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: None,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                OperatorConstants.Config.DOCLING_SERVE_TIMEOUT: {
                    OperatorConstants.Misc.NAME: "Docling Serve Timeout",
                    OperatorConstants.Config.DESCRIPTION: "Request timeout in seconds for docling-serve operations",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: 300,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.INTEGER,
                },
                OperatorConstants.Config.DOCLING_SERVE_POLL_INTERVAL: {
                    OperatorConstants.Misc.NAME: "Docling Serve Poll Interval",
                    OperatorConstants.Config.DESCRIPTION: "Polling interval in seconds when waiting for docling-serve task completion",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: 2,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.INTEGER,
                },
                OperatorConstants.Config.DOCLING_SERVE_MAX_RETRIES: {
                    OperatorConstants.Misc.NAME: "Docling Serve Max Retries",
                    OperatorConstants.Config.DESCRIPTION: "Maximum retry attempts for docling-serve status polling",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: 3,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.INTEGER,
                },
                OperatorConstants.Config.DOCLING_SERVE_DO_OCR: {
                    OperatorConstants.Misc.NAME: "Docling Serve OCR Enabled (Deprecated)",
                    OperatorConstants.Config.DESCRIPTION: "DEPRECATED: Use docling_serve_ocr_preset instead. Whether OCR should be enabled when processing documents with docling-serve",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.BOOLEAN,
                },
                OperatorConstants.Config.DOCLING_SERVE_OCR_ENGINE: {
                    OperatorConstants.Misc.NAME: "Docling Serve OCR Engine (Deprecated)",
                    OperatorConstants.Config.DESCRIPTION: "DEPRECATED: Use docling_serve_ocr_preset instead. OCR engine name passed to docling-serve",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: "easyocr",
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                OperatorConstants.Config.DOCLING_SERVE_OCR_LANGUAGES: {
                    OperatorConstants.Misc.NAME: "Docling Serve OCR Languages (Deprecated)",
                    OperatorConstants.Config.DESCRIPTION: "DEPRECATED: Use docling_serve_ocr_lang instead. List of OCR languages passed to docling-serve",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: [],
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.JSON,
                },
                OperatorConstants.Config.DOCLING_SERVE_OCR_PRESET: {
                    OperatorConstants.Misc.NAME: "Docling Serve OCR Preset",
                    OperatorConstants.Config.DESCRIPTION: "OCR preset for docling-serve (e.g., 'auto', 'tesseract', 'easyocr')",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: "auto",
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                OperatorConstants.Config.DOCLING_SERVE_OCR_LANG: {
                    OperatorConstants.Misc.NAME: "Docling Serve OCR Languages",
                    OperatorConstants.Config.DESCRIPTION: "List of OCR language codes for docling-serve (e.g., ['eng', 'fra'])",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: None,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.JSON,
                },
                OperatorConstants.Config.DOCLING_SERVE_PDF_BACKEND: {
                    OperatorConstants.Misc.NAME: "Docling Serve PDF Backend",
                    OperatorConstants.Config.DESCRIPTION: "PDF backend to use in docling-serve",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: "dlparse_v2",
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                OperatorConstants.Config.DOCLING_SERVE_TABLE_MODE: {
                    OperatorConstants.Misc.NAME: "Docling Serve Table Mode",
                    OperatorConstants.Config.DESCRIPTION: "Table structure extraction mode for docling-serve",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: "fast",
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                OperatorConstants.Config.DOCLING_SERVE_IMAGE_EXPORT_MODE: {
                    OperatorConstants.Misc.NAME: "Docling Serve Image Export Mode",
                    OperatorConstants.Config.DESCRIPTION: "Image export mode passed to docling-serve",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: "placeholder",
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                OperatorConstants.Config.MAX_WORKERS: {
                    OperatorConstants.Misc.NAME: "Max Workers",
                    OperatorConstants.Config.DESCRIPTION: "Maximum number of parallel workers (auto-detect if not specified)",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: None,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.INTEGER,
                },
                OperatorConstants.Config.USE_PROCESSES: {
                    OperatorConstants.Misc.NAME: "Use Processes",
                    OperatorConstants.Config.DESCRIPTION: "Use ProcessPoolExecutor instead of ThreadPoolExecutor for CPU-intensive tasks",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: False,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.BOOLEAN,
                },
            },
        }
