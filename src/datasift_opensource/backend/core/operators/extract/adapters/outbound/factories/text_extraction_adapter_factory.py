"""Factory for creating text extraction adapters.

This factory creates appropriate text extraction adapter instances based on the
extraction mode and configuration. It supports multiple extraction strategies:
- DOCLING_LIBRARY: Local Docling extraction with optional VLM support
- DOCLING_SERVE: Remote extraction via Docling Serve API
"""

import logging
from typing import Any

from common.constants.operator_constants import OperatorConstants
from common.util.infrastructure.logging import get_logger
from core.operators.extract.adapters.outbound.text_extraction.docling_adapter import DoclingAdapter
from core.operators.extract.adapters.outbound.text_extraction.docling_serve_adapter import DoclingServeAdapter
from core.operators.extract.domain.models import DoclingServeConfig, TextExtractionMode
from core.operators.extract.ports.outbound.text_extraction import TextExtractionPort

logger: logging.Logger = get_logger()


class TextExtractionAdapterFactory:
    """Factory for creating text extraction adapters.

    This factory creates appropriate adapter instances based on extraction mode
    and validates configuration requirements for each adapter type.

    Supported Modes:
        - TextExtractionMode.DOCLING_LIBRARY: Local Docling extraction with optional VLM
        - TextExtractionMode.DOCLING_SERVE: Remote Docling Serve API extraction

    Example Usage:
        # Create Docling adapter (standard extraction)
        config = {
            "extract_tables": True,
            "extract_images": False,
            "doc_column": "document"
        }
        adapter = TextExtractionAdapterFactory.create_adapter(
            mode=TextExtractionMode.DOCLING_LIBRARY,
            config=config,
            max_workers=4
        )

        # Create Docling adapter with VLM enabled
        vlm_config = {
            "use_vlm_pipeline": True,
            "vlm_preset": "granite_docling",
            "vlm_engine_type": "transformers",
            "extract_tables": True,
            "extract_images": True,
            "doc_column": "document"
        }
        vlm_adapter = TextExtractionAdapterFactory.create_adapter(
            mode=TextExtractionMode.DOCLING_LIBRARY,
            config=vlm_config,
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
    def build_adapter_config(*, mode: TextExtractionMode, operator_config: dict[str, Any]) -> dict[str, Any]:
        """Build adapter-specific configuration from operator config.

        This method extracts and transforms operator-level configuration into
        adapter-specific configuration, handling mode-specific requirements.

        Args:
            mode: Text extraction mode (DOCLING_LIBRARY, DOCLING_SERVE)
            operator_config: Full operator configuration dictionary

        Returns:
            Adapter-specific configuration dictionary

        Raises:
            ValueError: If mode is unsupported or configuration is invalid
        """
        # Common configuration for all text modes
        adapter_config: dict[str, Any] = {
            "doc_column": operator_config.get("doc_column", OperatorConstants.Columns.DOC_COLUMN_DEFAULT),
            OperatorConstants.Config.EXTRACT_TABLES: operator_config.get(
                OperatorConstants.Config.EXTRACT_TABLES, True
            ),
            OperatorConstants.Config.EXTRACT_IMAGES: operator_config.get(
                OperatorConstants.Config.EXTRACT_IMAGES, True
            ),
            "common_log_arguments": operator_config.get("common_log_arguments", {}),
        }

        # Add mode-specific configuration
        if mode == TextExtractionMode.DOCLING_LIBRARY:
            # VLM configuration is now part of docling_library mode
            adapter_config.update(
                {
                    OperatorConstants.Config.USE_VLM_PIPELINE: operator_config.get(
                        OperatorConstants.Config.USE_VLM_PIPELINE, False
                    ),
                    OperatorConstants.Config.VLM_PRESET: operator_config.get(
                        OperatorConstants.Config.VLM_PRESET, OperatorConstants.Config.VLM_PRESET_DEFAULT
                    ),
                    OperatorConstants.Config.VLM_ENGINE_TYPE: operator_config.get(
                        OperatorConstants.Config.VLM_ENGINE_TYPE
                    ),
                    OperatorConstants.Config.VLM_PROVIDER_CONFIG: operator_config.get(
                        OperatorConstants.Config.VLM_PROVIDER_CONFIG
                    ),
                }
            )

        elif mode == TextExtractionMode.DOCLING_SERVE:
            # Build docling_serve_config dictionary
            docling_serve_config = {
                "base_url": operator_config.get(OperatorConstants.Config.DOCLING_SERVE_BASE_URL, "http://localhost:5001"),
                "timeout": operator_config.get(OperatorConstants.Config.DOCLING_SERVE_TIMEOUT, 300),
                "poll_interval": operator_config.get(OperatorConstants.Config.DOCLING_SERVE_POLL_INTERVAL, 2),
                "max_retries": operator_config.get(OperatorConstants.Config.DOCLING_SERVE_MAX_RETRIES, 3),
                "do_ocr": operator_config.get(OperatorConstants.Config.DOCLING_SERVE_DO_OCR, True),
                "ocr_engine": operator_config.get(OperatorConstants.Config.DOCLING_SERVE_OCR_ENGINE, "easyocr"),
                "pdf_backend": operator_config.get(OperatorConstants.Config.DOCLING_SERVE_PDF_BACKEND, "dlparse_v2"),
                "table_mode": operator_config.get(OperatorConstants.Config.DOCLING_SERVE_TABLE_MODE, "fast"),
                "image_export_mode": operator_config.get(
                    OperatorConstants.Config.DOCLING_SERVE_IMAGE_EXPORT_MODE, "placeholder"
                ),
            }

            # Add optional parameters if provided
            if operator_config.get(OperatorConstants.Config.DOCLING_SERVE_API_KEY):
                docling_serve_config[OperatorConstants.Config.API_KEY] = operator_config[
                    OperatorConstants.Config.DOCLING_SERVE_API_KEY
                ]

            if operator_config.get(OperatorConstants.Config.DOCLING_SERVE_OCR_LANGUAGES):
                docling_serve_config["ocr_languages"] = operator_config[
                    OperatorConstants.Config.DOCLING_SERVE_OCR_LANGUAGES
                ]

            adapter_config["docling_serve_config"] = docling_serve_config

        else:
            raise ValueError(
                f"Unsupported extraction mode: {mode}. Supported modes: {[m.value for m in TextExtractionMode]}"
            )

        return adapter_config

    @staticmethod
    def create_adapter(
        *, mode: TextExtractionMode, operator_config: dict[str, Any], max_workers: int = 4, use_processes: bool = False
    ) -> TextExtractionPort:
        """Create appropriate text extraction adapter based on mode.

        Args:
            mode: Extraction mode (DOCLING_LIBRARY, DOCLING_SERVE)
            operator_config: Full operator configuration dictionary
            max_workers: Number of parallel workers (default: 4)
            use_processes: Use ProcessPoolExecutor instead of ThreadPoolExecutor (default: False)

        Returns:
            Configured TextExtractionPort adapter instance

        Raises:
            ValueError: If mode is unsupported or config is invalid
        """
        # Build adapter-specific configuration
        adapter_config = TextExtractionAdapterFactory.build_adapter_config(mode=mode, operator_config=operator_config)

        # Add common configuration
        full_config = {**adapter_config, "max_workers": max_workers, "use_processes": use_processes}

        if mode == TextExtractionMode.DOCLING_LIBRARY:
            # Check if VLM is enabled
            use_vlm = adapter_config.get("use_vlm_pipeline", False)

            if use_vlm:
                TextExtractionAdapterFactory._validate_vlm_config(adapter_config)
                logger.info(
                    "Creating DoclingAdapter with VLM enabled (preset: %s) and %s workers",
                    adapter_config.get("vlm_preset", OperatorConstants.Config.VLM_PRESET_DEFAULT),
                    max_workers,
                )
            else:
                TextExtractionAdapterFactory._validate_docling_config(adapter_config)
                logger.info("Creating DoclingAdapter for mode: %s with %s workers", mode.value, max_workers)

            return DoclingAdapter(config=full_config)

        elif mode == TextExtractionMode.DOCLING_SERVE:
            TextExtractionAdapterFactory._validate_docling_serve_config(adapter_config)
            logger.info(
                "Creating DoclingServeAdapter with URL: %s",
                adapter_config.get("docling_serve_config", {}).get("base_url", "http://0.0.0.0:5001"),
            )
            return DoclingServeAdapter(config=full_config)

        else:
            raise ValueError(
                f"Unsupported extraction mode: {mode}. Supported modes: {[m.value for m in TextExtractionMode]}"
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
            OperatorConstants.Config.EXTRACT_TABLES,
            OperatorConstants.Config.EXTRACT_IMAGES,
            OperatorConstants.ExtractionModes.EXPAND_EXTRACTED_DATA,
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

        # Validate boolean flags if present
        for flag in [OperatorConstants.Config.EXTRACT_TABLES, OperatorConstants.Config.EXTRACT_IMAGES]:
            if flag in config and not isinstance(config[flag], bool):
                raise ValueError(f"DoclingAdapter '{flag}' must be a boolean")

    @staticmethod
    def _validate_docling_serve_config(config: dict[str, Any]) -> None:
        """Validate configuration for DoclingServeAdapter.

        Args:
            config: Configuration dictionary to validate

        Raises:
            ValueError: If required configuration is missing or invalid
        """
        docling_serve_config = config.get("docling_serve_config")

        if not docling_serve_config:
            raise ValueError("DoclingServeAdapter requires 'docling_serve_config' dictionary")

        if not isinstance(docling_serve_config, dict):
            raise ValueError("DoclingServeAdapter 'docling_serve_config' must be a dictionary")

        # Validate base_url if present
        base_url = docling_serve_config.get("base_url")
        if base_url is not None and not isinstance(base_url, str):
            raise ValueError("docling_serve_config 'base_url' must be a string")

        # Validate numeric parameters if present
        for param in ["timeout", "poll_interval", "max_retries"]:
            value = docling_serve_config.get(param)
            if value is not None and not isinstance(value, (int, float)):
                raise ValueError(f"docling_serve_config '{param}' must be a number")

        # Validate boolean flags if present
        do_ocr = docling_serve_config.get("do_ocr")
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
        docling_serve_config = config.get("docling_serve_config", {})

        return DoclingServeConfig(
            url=docling_serve_config.get("base_url", "http://localhost:8080"),
            timeout=docling_serve_config.get("timeout", 300),
            max_retries=docling_serve_config.get("max_retries", 3),
            additional_params=docling_serve_config.get("additional_params", {}),
        )

    @staticmethod
    def get_supported_modes() -> list[str]:
        """Get list of supported extraction modes.

        Returns:
            List of supported extraction mode values
        """
        return [mode.value for mode in TextExtractionMode]
