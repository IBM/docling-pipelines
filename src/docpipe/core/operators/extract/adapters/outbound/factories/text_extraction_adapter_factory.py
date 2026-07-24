"""Factory for creating text extraction adapters.

This factory creates appropriate text extraction adapter instances based on the
extraction provider and configuration. It supports multiple extraction strategies:
- DOCLING_LIBRARY: Local Docling extraction with optional VLM support
- DOCLING_SERVE: Remote extraction via Docling Serve API
"""

import logging
from typing import Any

from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.extract.adapters.outbound.text_extraction.docling_adapter import DoclingAdapter
from docpipe.core.operators.extract.adapters.outbound.text_extraction.docling_serve_adapter import DoclingServeAdapter
from docpipe.core.operators.extract.domain.models import DoclingServeConfig, TextExtractionMode
from docpipe.core.operators.extract.ports.outbound.text_extraction import TextExtractionPort
from docpipe.utils.infrastructure.logging import get_logger

logger: logging.Logger = get_logger()


class TextExtractionAdapterFactory:
    """Factory for creating text extraction adapters.

    This factory creates appropriate adapter instances based on extraction provider
    and validates configuration requirements for each adapter type.

    Supported Providers:
        - TextExtractionMode.DOCLING_LIBRARY: Local Docling extraction with optional VLM
        - TextExtractionMode.DOCLING_SERVE: Remote Docling Serve API extraction

    Example Usage:
        # Create Docling adapter (standard extraction)
        config = {
            "doc_column": "document"
        }
        adapter = TextExtractionAdapterFactory.create_adapter(
            mode=TextExtractionMode.DOCLING_LIBRARY,
            config=config,
            max_workers=4
        )

        # Create Docling adapter with VLM enabled
        vlm_config = {
            "doc_column": "document",
            "provider_config": {
                "vlm_pipeline": {
                    "preset": "granite_docling",
                    "engine": "api_ollama",
                    "engine_options": {
                        "api_base": "http://localhost:11434",
                        "model_id": "ibm/granite-docling:258m"
                    }
                }
            }
        }
        vlm_adapter = TextExtractionAdapterFactory.create_adapter(
            mode=TextExtractionMode.DOCLING_LIBRARY,
            text_extraction_config=vlm_config,
            global_config={},
            max_workers=2
        )

        # Create Docling Serve adapter
        serve_config = {
            "docling_serve_config": {
                "base_url": "http://localhost:5001",
                "timeout": 300,
                "do_ocr": True
            },
            "doc_column": "document"
        }
        serve_adapter = TextExtractionAdapterFactory.create_adapter(
            mode=TextExtractionMode.DOCLING_SERVE,
            config=serve_config
        )
    """

    @staticmethod
    def build_adapter_config(*, mode: TextExtractionMode, text_extraction_config: dict[str, Any]) -> dict[str, Any]:
        """Build adapter-specific configuration from nested text_extraction config.

        This method extracts and transforms the nested text_extraction configuration into
        adapter-specific configuration, handling provider-specific requirements.

        Args:
            mode: Text extraction provider (DOCLING_LIBRARY, DOCLING_SERVE)
            text_extraction_config: Nested text_extraction configuration dictionary

        Returns:
            Adapter-specific configuration dictionary

        Raises:
            ValueError: If provider is unsupported or configuration is invalid
        """
        # Extract provider_config from nested structure
        provider_config = text_extraction_config.get(OperatorConstants.Config.PROVIDER_CONFIG, {})

        # Common configuration for all text providers
        adapter_config: dict[str, Any] = {
            OperatorConstants.Config.DOC_COLUMN: text_extraction_config.get(
                OperatorConstants.Config.DOC_COLUMN, OperatorConstants.Columns.DOC_COLUMN_DEFAULT
            ),
            OperatorConstants.Extraction.ADDITIONAL_FORMATS: provider_config.get(
                OperatorConstants.Extraction.ADDITIONAL_FORMATS, []
            ),
            OperatorConstants.Config.COMMON_LOG_ARGUMENTS: text_extraction_config.get(
                OperatorConstants.Config.COMMON_LOG_ARGUMENTS, {}
            ),
        }

        # Add mode-specific configuration from provider_config
        if mode == TextExtractionMode.DOCLING_LIBRARY:
            # VLM configuration comes from provider_config.vlm_pipeline
            vlm_pipeline = provider_config.get(OperatorConstants.Config.VLM_PIPELINE, {})

            adapter_config.update(
                {
                    OperatorConstants.Config.USE_VLM_PIPELINE: bool(vlm_pipeline),
                    OperatorConstants.Config.VLM_PRESET: vlm_pipeline.get(
                        OperatorConstants.Config.PRESET, OperatorConstants.Config.DEFAULT
                    ),
                    OperatorConstants.Config.VLM_ENGINE_TYPE: vlm_pipeline.get(
                        OperatorConstants.Config.ENGINE, OperatorConstants.Config.VLM_ENGINE_TRANSFORMERS
                    ),
                    OperatorConstants.Config.VLM_PROVIDER_CONFIG: vlm_pipeline.get(
                        OperatorConstants.Config.ENGINE_OPTIONS
                    ),
                }
            )

            # ASR configuration comes from provider_config.asr_pipeline
            asr_pipeline = provider_config.get(OperatorConstants.Config.ASR_PIPELINE, {})

            adapter_config.update(
                {
                    OperatorConstants.Config.USE_ASR_PIPELINE: bool(asr_pipeline),
                    OperatorConstants.Config.ASR_MODEL_NAME: asr_pipeline.get(
                        OperatorConstants.Config.MODEL_ID, OperatorConstants.Config.ASR_MODEL_DEFAULT
                    ),
                }
            )

        elif mode == TextExtractionMode.DOCLING_SERVE:
            # Build docling_serve_config dictionary from provider_config
            docling_serve_config = {
                OperatorConstants.Config.BASE_URL: provider_config.get(
                    OperatorConstants.Config.BASE_URL, "http://localhost:5001"
                ),
                OperatorConstants.Processing.TIMEOUT: provider_config.get(OperatorConstants.Processing.TIMEOUT, 300),
                OperatorConstants.Processing.POLL_INTERVAL: provider_config.get(
                    OperatorConstants.Processing.POLL_INTERVAL, 2
                ),
                OperatorConstants.Processing.MAX_RETRIES: provider_config.get(
                    OperatorConstants.Processing.MAX_RETRIES, 3
                ),
                OperatorConstants.Processing.VERIFY_SSL: provider_config.get(
                    OperatorConstants.Processing.VERIFY_SSL, True
                ),
                OperatorConstants.Config.DO_OCR: provider_config.get(OperatorConstants.Config.DO_OCR, True),
                OperatorConstants.Config.OCR_ENGINE: provider_config.get(
                    OperatorConstants.Config.OCR_ENGINE, "easyocr"
                ),
                OperatorConstants.Config.PDF_BACKEND: provider_config.get(
                    OperatorConstants.Config.PDF_BACKEND, "dlparse_v2"
                ),
                OperatorConstants.Config.TABLE_MODE: provider_config.get(OperatorConstants.Config.TABLE_MODE, "fast"),
                OperatorConstants.Config.IMAGE_EXPORT_MODE: provider_config.get(
                    OperatorConstants.Config.IMAGE_EXPORT_MODE, "placeholder"
                ),
            }

            # Add optional parameters if provided
            if provider_config.get(OperatorConstants.Config.API_KEY):
                docling_serve_config[OperatorConstants.Config.API_KEY] = provider_config[
                    OperatorConstants.Config.API_KEY
                ]

            if provider_config.get(OperatorConstants.Config.OCR_LANGUAGES):
                docling_serve_config[OperatorConstants.Config.OCR_LANGUAGES] = provider_config[
                    OperatorConstants.Config.OCR_LANGUAGES
                ]

            adapter_config[OperatorConstants.Config.DOCLING_SERVE_CONFIG] = docling_serve_config

        else:
            raise ValueError(
                f"Unsupported extraction provider: {mode}. Supported providers: {[m.value for m in TextExtractionMode]}"
            )

        return adapter_config

    @staticmethod
    def create_adapter(
        *,
        mode: TextExtractionMode,
        text_extraction_config: dict[str, Any],
        global_config: dict[str, Any],
        max_workers: int = 4,
        use_processes: bool = False,
    ) -> TextExtractionPort:
        """Create appropriate text extraction adapter based on provider.

        Args:
            mode: Extraction provider (DOCLING_LIBRARY, DOCLING_SERVE)
            text_extraction_config: Nested text_extraction configuration dictionary
            global_config: Global operator configuration (for job tracking, etc.)
            max_workers: Number of parallel workers (default: 4)
            use_processes: Use ProcessPoolExecutor instead of ThreadPoolExecutor (default: False)

        Returns:
            Configured TextExtractionPort adapter instance

        Raises:
            ValueError: If provider is unsupported or config is invalid
        """
        # Build adapter-specific configuration from nested text_extraction config
        adapter_config = TextExtractionAdapterFactory.build_adapter_config(
            mode=mode, text_extraction_config=text_extraction_config
        )

        # Merge with global config for job tracking and other global settings
        # IMPORTANT: Merge global_config first to preserve keys like ingest_source
        full_config = {**global_config, **adapter_config, "max_workers": max_workers, "use_processes": use_processes}

        if mode == TextExtractionMode.DOCLING_LIBRARY:
            # Check if VLM is enabled
            use_vlm = adapter_config.get(OperatorConstants.Config.USE_VLM_PIPELINE, False)

            if use_vlm:
                TextExtractionAdapterFactory._validate_vlm_config(adapter_config)
                logger.info(
                    "Creating DoclingAdapter with VLM enabled (preset: %s) and %s workers",
                    adapter_config.get(
                        OperatorConstants.Config.VLM_PRESET, OperatorConstants.Config.VLM_PRESET_DEFAULT
                    ),
                    max_workers,
                )
            else:
                TextExtractionAdapterFactory._validate_docling_config(adapter_config)
                logger.info("Creating DoclingAdapter for provider: %s with %s workers", mode.value, max_workers)

            return DoclingAdapter(config=full_config)

        elif mode == TextExtractionMode.DOCLING_SERVE:
            TextExtractionAdapterFactory._validate_docling_serve_config(adapter_config)
            logger.info(
                "Creating DoclingServeAdapter with URL: %s",
                adapter_config.get(OperatorConstants.Config.DOCLING_SERVE_CONFIG, {}).get(
                    OperatorConstants.Config.BASE_URL, "http://localhost:5001"
                ),
            )
            return DoclingServeAdapter(config=full_config)

        else:
            raise ValueError(
                f"Unsupported extraction provider: {mode}. Supported providers: {[m.value for m in TextExtractionMode]}"
            )

    @staticmethod
    def _validate_docling_config(config: dict[str, Any]) -> None:
        """Validate configuration for DoclingAdapter.

        Args:
            config: Configuration dictionary to validate

        Raises:
            ValueError: If required configuration is missing or invalid
        """
        # Optional parameters - no strict validation needed
        # DoclingAdapter handles defaults internally
        use_template = config.get(OperatorConstants.Config.USE_TEMPLATE, False)

        if use_template:
            template = config.get(OperatorConstants.Config.TEMPLATE)
            if template is not None and not isinstance(template, dict):
                raise ValueError("DoclingAdapter 'template' must be a dictionary when provided")

        # Validate boolean flags if present
        for flag in [
            OperatorConstants.Config.EXPAND_EXTRACTED_DATA,
        ]:
            if flag in config and not isinstance(config[flag], bool):
                raise ValueError(f"DoclingAdapter '{flag}' must be a boolean")

    @staticmethod
    def _validate_vlm_config(config: dict[str, Any]) -> None:
        """Validate configuration for DoclingAdapter with VLM enabled.

        Args:
            config: Configuration dictionary to validate

        Raises:
            ValueError: If required configuration is missing or invalid
        """
        # VLM preset is optional (defaults to "granite_docling")
        vlm_preset = config.get(OperatorConstants.Config.VLM_PRESET)
        if vlm_preset is not None and not isinstance(vlm_preset, str):
            raise ValueError("DoclingAdapter 'vlm_preset' must be a string")

        # VLM engine type is optional
        vlm_engine_type = config.get(OperatorConstants.Config.VLM_ENGINE_TYPE)
        if vlm_engine_type is not None and not isinstance(vlm_engine_type, str):
            raise ValueError("DoclingAdapter 'vlm_engine_type' must be a string")

        # VLM provider config is optional
        vlm_provider_config = config.get(OperatorConstants.Config.VLM_PROVIDER_CONFIG)
        if vlm_provider_config is not None and not isinstance(vlm_provider_config, dict):
            raise ValueError("DoclingAdapter 'vlm_provider_config' must be a dictionary")

        # No additional validation needed for VLM config
        pass

    @staticmethod
    def _validate_docling_serve_config(config: dict[str, Any]) -> None:
        """Validate configuration for DoclingServeAdapter.

        Args:
            config: Configuration dictionary to validate

        Raises:
            ValueError: If required configuration is missing or invalid
        """
        docling_serve_config = config.get(OperatorConstants.Config.DOCLING_SERVE_CONFIG)

        if not docling_serve_config:
            raise ValueError("DoclingServeAdapter requires 'docling_serve_config' dictionary")

        if not isinstance(docling_serve_config, dict):
            raise ValueError("DoclingServeAdapter 'docling_serve_config' must be a dictionary")

        # Validate base_url if present
        base_url = docling_serve_config.get(OperatorConstants.Config.BASE_URL)
        if base_url is not None and not isinstance(base_url, str):
            raise ValueError("docling_serve_config 'base_url' must be a string")

        # Validate numeric parameters if present
        for param in [
            OperatorConstants.Processing.TIMEOUT,
            OperatorConstants.Processing.POLL_INTERVAL,
            OperatorConstants.Processing.MAX_RETRIES,
        ]:
            value = docling_serve_config.get(param)
            if value is not None and not isinstance(value, (int, float)):
                raise ValueError(f"docling_serve_config '{param}' must be a number")

        # Validate boolean flags if present
        do_ocr = docling_serve_config.get(OperatorConstants.Config.DO_OCR)
        if do_ocr is not None and not isinstance(do_ocr, bool):
            raise ValueError("docling_serve_config 'do_ocr' must be a boolean")

    @staticmethod
    def _build_docling_serve_config(config: dict[str, Any]) -> DoclingServeConfig:
        """Build DoclingServeConfig from configuration dictionary.

        This helper method constructs a DoclingServeConfig dataclass instance
        from the configuration dictionary, applying defaults where needed.

        Args:
            config: Configuration dictionary containing docling_serve_config

        Returns:
            DoclingServeConfig instance

        Raises:
            ValueError: If required configuration is missing
        """
        docling_serve_config = config.get(OperatorConstants.Config.DOCLING_SERVE_CONFIG, {})

        return DoclingServeConfig(
            url=docling_serve_config.get(OperatorConstants.Config.BASE_URL, "http://localhost:8080"),
            timeout=docling_serve_config.get(OperatorConstants.Processing.TIMEOUT, 300),
            max_retries=docling_serve_config.get(OperatorConstants.Processing.MAX_RETRIES, 3),
            additional_params=docling_serve_config.get("additional_params", {}),
        )

    @staticmethod
    def get_supported_modes() -> list[str]:
        """Get list of supported extraction providers.

        Returns:
            List of supported extraction provider values
        """
        return [mode.value for mode in TextExtractionMode]
