"""Docling library text extraction adapter.

This adapter implements the unified docling_library provider for document extraction.
It handles both standard Docling extraction and VLM (Vision Language Model) extraction
when use_vlm_pipeline is enabled. The adapter uses Docling's DocumentExtractor for
extraction and supports template-based structured extraction.
"""

import logging
from typing import Any

from docling.datamodel.base_models import InputFormat
from docling.document_converter import ImageFormatOption, PdfFormatOption
from docling.pipeline.vlm_pipeline import VlmPipeline

from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.extract.ports.outbound.text_extraction import TextExtractionPort
from docpipe.core.operators.operator_utils import OperatorUtils, is_asr_available
from docpipe.integrations.docling.vlm_pipeline_options_provider import VlmPipelineOptionsProviderFactory
from docpipe.utils.infrastructure.logging import get_logger

logger: logging.Logger = get_logger()

# Check if ASR dependencies are available using utility function
_ASR_AVAILABLE = is_asr_available()
if not _ASR_AVAILABLE:
    logger.debug("ASR dependencies not available. Install with: uv pip install -e '.[asr]'")


class DoclingAdapter(TextExtractionPort):
    """Adapter for unified Docling library document extraction.

    This adapter implements the docling_library provider, which handles both standard
    Docling extraction and VLM (Vision Language Model) extraction. When use_vlm_pipeline
    is enabled, it uses Docling's VLM pipeline for enhanced extraction.

    The adapter provides:
    - Standard Docling extraction using DocumentExtractor
    - VLM pipeline support for advanced document understanding
    - Template-based structured extraction for structured data
    - Page-level extraction results

    Configuration:
        use_vlm_pipeline: Enable VLM extraction (default: False)
        vlm_preset: VLM preset name when VLM is enabled (default: "granite_docling")
        vlm_engine_type: VLM engine type (optional, uses Docling defaults if not set)
        vlm_provider_config: Provider-specific configuration (optional)

    Attributes:
        ADAPTER_NAME: Short identifier "docling_library"
        ADAPTER_DISPLAY_NAME: Human-readable name "Docling Library Extractor"
    """

    ADAPTER_NAME = "docling_library"
    ADAPTER_DISPLAY_NAME = "Docling Library Extractor"

    def __init__(self, *, config: dict[str, Any]) -> None:
        """Initialize the adapter with configuration.

        Args:
            config: Configuration dictionary
        """
        super().__init__(config=config)

    def _init_adapter_config(self, *, config: dict[str, Any]) -> None:
        """Initialize Docling-specific configuration.

        Args:
            config: Configuration dictionary containing:
                - use_vlm_pipeline: Enable VLM extraction (default: False)
                - vlm_preset: VLM preset name (default: "granite_docling")
                - vlm_engine_type: Engine type (optional)
                - vlm_provider_config: Provider-specific configuration (optional)
                - additional_formats: List of additional output formats beyond markdown (default: [])
                - use_asr_pipeline: Enable ASR extraction for audio/video (default: False)
                - asr_model_name: ASR model name (optional)
        """
        self.use_vlm_pipeline = config.get(OperatorConstants.Config.USE_VLM_PIPELINE, False)
        self.vlm_preset = config.get(OperatorConstants.Config.VLM_PRESET, OperatorConstants.Config.VLM_PRESET_DEFAULT)
        self.vlm_engine_type = config.get(OperatorConstants.Config.VLM_ENGINE_TYPE)
        self.vlm_provider_config = config.get(OperatorConstants.Config.VLM_PROVIDER_CONFIG)
        self.additional_formats = config.get(OperatorConstants.Extraction.ADDITIONAL_FORMATS, [])
        self.use_asr_pipeline = config.get(OperatorConstants.Config.USE_ASR_PIPELINE, False) and _ASR_AVAILABLE
        # Always use string default for ASR model name
        self.asr_model_name = config.get(
            OperatorConstants.Config.ASR_MODEL_NAME, OperatorConstants.Config.ASR_MODEL_DEFAULT
        )

        if self.use_vlm_pipeline:
            logger.info(
                "Initialized DoclingAdapter with VLM enabled - preset: %s, engine: %s, additional formats: %s",
                self.vlm_preset,
                self.vlm_engine_type or "default",
                self.additional_formats,
            )
        if self.use_asr_pipeline:
            logger.info(
                "Initialized DoclingAdapter with ASR enabled - model: %s",
                self.asr_model_name or "default",
            )
        elif config.get(OperatorConstants.Config.USE_ASR_PIPELINE, False) and not _ASR_AVAILABLE:
            logger.warning(
                "ASR pipeline requested but dependencies not available. Install with: uv pip install -e '.[asr]'"
            )
        if not self.use_vlm_pipeline and not self.use_asr_pipeline:
            logger.info(
                "Initialized DoclingAdapter with standard extraction, additional formats: %s", self.additional_formats
            )

    def _configure_vlm_engine(self) -> Any:
        """Configure VLM pipeline options based on engine type.

        Returns:
            VlmPipelineOptions configured for the engine, or None to use Docling defaults

        Raises:
            ValueError: If required parameters are missing for the selected engine
        """
        # If no engine type and no provider config, return None to use Docling's defaults
        if not self.vlm_engine_type and not self.vlm_provider_config:
            logger.info("No VLM engine configuration provided - using Docling defaults")
            return None

        # Get pipeline options provider for the specified engine type
        provider = VlmPipelineOptionsProviderFactory.get_provider(engine_type=self.vlm_engine_type)

        # Create complete pipeline options using the provider
        provider_config = self.vlm_provider_config or {}
        pipeline_options = provider.create_pipeline_options(preset=self.vlm_preset, config=provider_config)

        return pipeline_options

    def _configure_asr_engine(self) -> Any:
        """Configure ASR pipeline options based on model configuration.
        Returns:
            AsrPipelineOptions configured for the model, or None to use Docling defaults
        Raises:
            ValueError: If required parameters are missing for ASR
        """
        # If no model name specified, return None to use Docling's defaults
        if not self.asr_model_name:
            logger.info("No ASR model specified - using Docling defaults (whisper_turbo)")
            return None

        try:
            # Import the asr_model_specs module to access pre-configured model specs
            from docling.datamodel import asr_model_specs
            from docling.datamodel.pipeline_options import AsrPipelineOptions

            # Convert model name to uppercase constant name (e.g., "whisper_turbo" -> "WHISPER_TURBO")
            model_constant_name = self.asr_model_name.upper()

            # Get the pre-configured model spec from the module
            if hasattr(asr_model_specs, model_constant_name):
                asr_options = getattr(asr_model_specs, model_constant_name)
                logger.info("Using ASR model: %s (repo_id: %s)", self.asr_model_name, asr_options.repo_id)
            else:
                logger.warning(
                    "Invalid ASR model name: %s. Using default WHISPER_TURBO. "
                    "Valid options: whisper_tiny, whisper_small, whisper_medium, whisper_base, "
                    "whisper_large, whisper_turbo, and their _mlx/_native variants",
                    self.asr_model_name,
                )
                asr_options = asr_model_specs.WHISPER_TURBO

            return AsrPipelineOptions(asr_options=asr_options)

        except ImportError as e:
            logger.warning("ASR pipeline dependencies not available: %s", str(e))
            return None

    def extract_single_document(
        self, *, file_path: str, binary_content: bytes, **kwargs: Any
    ) -> dict[str, Any]:  # NOSONAR python:S3776
        """Extract content from a single document using Docling.

        Performs template-based extraction if a template is provided, otherwise
        falls back to basic extraction. Extracts structured data, tables, and
        images based on configuration. Uses VLM pipeline if enabled.

        Args:
            file_path: Path to the document file (used for logging and temp file)
            binary_content: Binary content of the document
            **kwargs: Additional parameters:
                - template: Optional template dictionary for structured extraction

        Returns:
            Dictionary containing:
                - success: True if extraction succeeded
                - doc_content: Extracted content as JSON string (template mode) or markdown
                - structured_data: List of page-level structured data (template mode)
                - metadata: Extraction metadata (page_count, etc.)
                - error: Error message if extraction failed
        """
        if self.use_vlm_pipeline:
            logger.info(
                "Processing file with VLM pipeline (preset: %s, engine: %s): %s",
                self.vlm_preset,
                self.vlm_engine_type or "default",
                file_path,
            )
        else:
            logger.info("Processing file with standard extraction: %s", file_path)

        try:
            # Prepare converter configuration
            converter_config = None
            format_options: dict[InputFormat, Any] = {}

            if self.use_vlm_pipeline:
                # Configure VLM pipeline options
                pipeline_options = self._configure_vlm_engine()

                # Set up VLM pipeline for PDF and image formats
                format_options[InputFormat.PDF] = PdfFormatOption(
                    pipeline_cls=VlmPipeline,
                    pipeline_options=pipeline_options,
                )
                format_options[InputFormat.IMAGE] = ImageFormatOption(
                    pipeline_cls=VlmPipeline,
                    pipeline_options=pipeline_options,
                )

            if self.use_asr_pipeline and _ASR_AVAILABLE:
                # Import ASR classes only when needed
                from docling.document_converter import AudioFormatOption
                from docling.pipeline.asr_pipeline import AsrPipeline

                # Configure ASR pipeline options
                asr_options = self._configure_asr_engine()

                # Set up ASR pipeline for audio and video formats
                # Note: Docling does not have a separate VIDEO InputFormat or VideoFormatOption
                # Video files are handled through AUDIO format with ASR pipeline
                format_options[InputFormat.AUDIO] = AudioFormatOption(
                    pipeline_cls=AsrPipeline,
                    pipeline_options=asr_options,
                )

            # Only set converter_config if we have format options
            if format_options:
                converter_config = {OperatorConstants.Config.FORMAT_OPTIONS: format_options}

            # Use common extraction method with output_formats
            result = OperatorUtils.extract_content(
                file_path=file_path,
                binary_content=binary_content,
                converter_config=converter_config,
                additional_formats=self.additional_formats,
            )

            # Add VLM-specific metadata if extraction succeeded and VLM was used
            if self.use_vlm_pipeline and result.get(OperatorConstants.Extraction.SUCCESS):
                result[OperatorConstants.Metadata.METADATA][OperatorConstants.Config.VLM_PRESET] = self.vlm_preset
                result[OperatorConstants.Metadata.METADATA][OperatorConstants.Config.VLM_ENGINE_TYPE] = (
                    self.vlm_engine_type or OperatorConstants.Config.VLM_ENGINE_TRANSFORMERS
                )
            # Add ASR-specific metadata if extraction succeeded and ASR was used
            if self.use_asr_pipeline and result.get(OperatorConstants.Extraction.SUCCESS):
                result[OperatorConstants.Metadata.METADATA][OperatorConstants.Config.ASR_MODEL_NAME] = (
                    self.asr_model_name or OperatorConstants.Config.ASR_MODEL_DEFAULT
                )
            return result

        except ImportError as e:
            if self.use_vlm_pipeline:
                logger.error("VLM pipeline dependencies not available. Install with: pip install docling[vlm]")
                logger.error("Error: %s", str(e))
                return {
                    OperatorConstants.Extraction.SUCCESS: False,
                    OperatorConstants.Extraction.ERROR: "VLM pipeline dependencies not available. Install docling[vlm]",
                    OperatorConstants.Columns.DOC_COLUMN_DEFAULT: None,
                }
            raise
        except Exception as e:
            logger.error("Error during text extraction: %s", str(e))
            return {
                OperatorConstants.Extraction.SUCCESS: False,
                OperatorConstants.Extraction.ERROR: str(e),
                OperatorConstants.Columns.DOC_COLUMN_DEFAULT: None,
            }
