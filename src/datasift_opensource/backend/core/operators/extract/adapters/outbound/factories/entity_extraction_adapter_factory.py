"""Factory for creating entity extraction adapters.

This factory creates appropriate entity extraction adapter instances based on the
extraction mode and configuration. It supports multiple extraction strategies:
- OLLAMA: LLM-based entity extraction using Ollama models
- DOCLING: Template-based entity extraction using Docling templates
"""

import logging
from typing import Any

from common.constants.operator_constants import OperatorConstants
from common.util.infrastructure.logging import get_logger
from core.operators.extract.adapters.outbound.entity_extraction.docling_entity_adapter import DoclingEntityAdapter
from core.operators.extract.adapters.outbound.entity_extraction.litellm_entity_adapter import LiteLLMEntityAdapter
from core.operators.extract.adapters.outbound.entity_extraction.ollama_entity_adapter import OllamaEntityAdapter
from core.operators.extract.domain import EntityExtractionMode
from core.operators.extract.ports.outbound.entity_extraction import EntityExtractionPort

logger: logging.Logger = get_logger()


class EntityExtractionAdapterFactory:
    """Factory for creating entity extraction adapters.

    This factory creates appropriate adapter instances based on extraction mode
    and validates configuration requirements for each adapter type.

    Supported Modes:
        - "ollama": LLM-based extraction using Ollama models
        - "docling": Template-based extraction using Docling templates
        - "litellm": Multi-provider LLM extraction using LiteLLM
        - "none": No entity extraction

    Example Usage:
        # Create Ollama adapter
        config = {
            "model_name": "llama3.2",
            "temperature": 0.0,
            "max_tokens": 4096,
            "max_doc_chars": 8000,
            "doc_column": "doc_content",
            "output_column": "entities",
            "expand_extracted_data": False
        }
        adapter = EntityExtractionAdapterFactory.create_adapter(
            mode="ollama",
            config=config,
            max_workers=4
        )

        # Create Docling adapter
        docling_config = {
            "doc_column": "doc_content",
            "output_column": "entities"
        }
        docling_adapter = EntityExtractionAdapterFactory.create_adapter(
            mode="docling",
            config=docling_config,
            max_workers=4
        )
    """

    @staticmethod
    def build_adapter_config(*, mode: EntityExtractionMode, operator_config: dict[str, Any]) -> dict[str, Any]:
        """Build adapter-specific configuration from operator config.

        This method extracts and transforms operator-level configuration into
        adapter-specific configuration, handling mode-specific requirements.

        Args:
            mode: Entity extraction mode (OLLAMA, DOCLING, LITELLM, NONE)
            operator_config: Full operator configuration dictionary

        Returns:
            Adapter-specific configuration dictionary

        Raises:
            ValueError: If mode is unsupported or configuration is invalid
        """
        # Common configuration for all entity modes
        adapter_config = {
            "doc_column": operator_config.get("doc_column", OperatorConstants.Columns.DOC_COLUMN_DEFAULT),
            OperatorConstants.Columns.OUTPUT_COLUMN: operator_config.get(
                OperatorConstants.Columns.OUTPUT_COLUMN, OperatorConstants.Misc.ENTITIES
            ),
            "expand_extracted_data": operator_config.get(
                OperatorConstants.ExtractionModes.EXPAND_EXTRACTED_DATA, False
            ),
            "custom_schema": operator_config.get(OperatorConstants.Config.CUSTOM_SCHEMA, {}),
            "common_log_arguments": operator_config.get("common_log_arguments", {}),
        }

        # Add mode-specific configuration
        if mode == EntityExtractionMode.OLLAMA:
            adapter_config.update(
                {
                    "model_name": operator_config.get(OperatorConstants.ExtractionModes.ENTITY_MODEL_NAME, "llama3.2"),
                    "temperature": operator_config.get(OperatorConstants.ExtractionModes.ENTITY_TEMPERATURE, 0.0),
                    "max_tokens": operator_config.get(OperatorConstants.ExtractionModes.ENTITY_MAX_TOKENS, 4096),
                    "max_doc_chars": operator_config.get("max_doc_chars", 8000),
                }
            )

        elif mode == EntityExtractionMode.LITELLM:
            adapter_config.update(
                {
                    "model_name": operator_config.get(
                        OperatorConstants.ExtractionModes.ENTITY_MODEL_NAME, "gpt-3.5-turbo"
                    ),
                    "temperature": operator_config.get(OperatorConstants.ExtractionModes.ENTITY_TEMPERATURE, 0.0),
                    "max_tokens": operator_config.get(OperatorConstants.ExtractionModes.ENTITY_MAX_TOKENS, 2000),
                }
            )

        elif mode == EntityExtractionMode.DOCLING:
            # Docling mode uses default configuration
            pass

        elif mode == EntityExtractionMode.NONE:
            # No configuration needed for NONE mode
            pass

        else:
            raise ValueError(
                f"Unsupported entity extraction mode: {mode}. Supported modes: ollama, docling, litellm, none"
            )

        return adapter_config

    @staticmethod
    def create_adapter(
        *, mode: EntityExtractionMode, operator_config: dict[str, Any], max_workers: int = 4
    ) -> EntityExtractionPort | None:
        """Create appropriate entity extraction adapter based on mode.

        Args:
            mode: Extraction mode ("ollama", "docling", "litellm", or "none")
            operator_config: Full operator configuration dictionary
            max_workers: Number of parallel workers (default: 4)

        Returns:
            Configured EntityExtractionPort adapter instance, or None if mode is "none"

        Raises:
            ValueError: If mode is unsupported or config is invalid
        """
        # Build adapter-specific configuration
        adapter_config = EntityExtractionAdapterFactory.build_adapter_config(mode=mode, operator_config=operator_config)

        # Add common configuration
        full_config = {**adapter_config, "max_workers": max_workers}

        if mode == OperatorConstants.ExtractionModes.ENTITY_MODE_OLLAMA:
            EntityExtractionAdapterFactory._validate_ollama_config(adapter_config)
            logger.info(
                "Creating OllamaEntityAdapter with model: %s and %s workers",
                adapter_config.get("model_name", "llama3.2"),
                max_workers,
            )
            return OllamaEntityAdapter(config=full_config)

        elif mode == OperatorConstants.ExtractionModes.ENTITY_MODE_DOCLING:
            EntityExtractionAdapterFactory._validate_docling_config(adapter_config)
            logger.info("Creating DoclingEntityAdapter with %s workers", max_workers)
            return DoclingEntityAdapter(config=full_config)

        elif mode == OperatorConstants.ExtractionModes.ENTITY_MODE_LITELLM:
            EntityExtractionAdapterFactory._validate_litellm_config(adapter_config)
            logger.info(
                "Creating LiteLLMEntityAdapter with model: %s and %s workers",
                adapter_config.get("model_name", "gpt-3.5-turbo"),
                max_workers,
            )
            return LiteLLMEntityAdapter(config=full_config)

        elif mode == OperatorConstants.ExtractionModes.ENTITY_MODE_NONE:
            logger.info("Entity extraction disabled (mode='none')")
            return None

        else:
            raise ValueError(
                f"Unsupported entity extraction mode: {mode}. Supported modes: ollama, docling, litellm, none"
            )

    @staticmethod
    def _validate_ollama_config(config: dict[str, Any]) -> None:
        """Validate configuration for OllamaEntityAdapter.

        Args:
            config: Configuration dictionary to validate

        Raises:
            ValueError: If required configuration is missing or invalid
        """
        # Model name is optional (defaults to "llama3.2")
        model_name = config.get(OperatorConstants.Config.MODEL_NAME)
        if model_name is not None and not isinstance(model_name, str):
            raise ValueError("OllamaEntityAdapter 'model_name' must be a string")

        # Validate numeric parameters if present
        for param in [
            OperatorConstants.ExtractionModes.ENTITY_TEMPERATURE,
            OperatorConstants.ExtractionModes.ENTITY_MAX_TOKENS,
            "max_doc_chars",
        ]:
            value = config.get(param)
            if value is not None and not isinstance(value, (int, float)):
                raise ValueError(f"OllamaEntityAdapter '{param}' must be a number")

        # Validate boolean flags if present
        expand_extracted_data = config.get(OperatorConstants.ExtractionModes.EXPAND_EXTRACTED_DATA)
        if expand_extracted_data is not None and not isinstance(expand_extracted_data, bool):
            raise ValueError("OllamaEntityAdapter 'expand_extracted_data' must be a boolean")

    @staticmethod
    def _validate_docling_config(config: dict[str, Any]) -> None:
        """Validate configuration for DoclingEntityAdapter.

        Args:
            config: Configuration dictionary to validate

        Raises:
            ValueError: If required configuration is missing or invalid
        """
        # Docling adapter has minimal configuration requirements
        # Most configuration is handled by the base EntityExtractionPort

        # Validate string parameters if present
        for param in ["doc_column", "output_column"]:
            value = config.get(param)
            if value is not None and not isinstance(value, str):
                raise ValueError(f"DoclingEntityAdapter '{param}' must be a string")

    @staticmethod
    def _validate_litellm_config(config: dict[str, Any]) -> None:
        """Validate configuration for LiteLLMEntityAdapter.

        Args:
            config: Configuration dictionary to validate

        Raises:
            ValueError: If required configuration is missing or invalid
        """
        # Model name is optional (defaults to "gpt-3.5-turbo")
        model_name = config.get(OperatorConstants.Config.MODEL_NAME)
        if model_name is not None and not isinstance(model_name, str):
            raise ValueError("LiteLLMEntityAdapter 'model_name' must be a string")

        # Validate numeric parameters if present
        for param in [
            OperatorConstants.ExtractionModes.ENTITY_TEMPERATURE,
            OperatorConstants.ExtractionModes.ENTITY_MAX_TOKENS,
        ]:
            value = config.get(param)
            if value is not None and not isinstance(value, (int, float)):
                raise ValueError(f"LiteLLMEntityAdapter '{param}' must be a number")

    @staticmethod
    def get_supported_modes() -> list[str]:
        """Get list of supported extraction modes.

        Returns:
            List of supported extraction mode values
        """
        return [
            OperatorConstants.ExtractionModes.ENTITY_MODE_OLLAMA,
            OperatorConstants.ExtractionModes.ENTITY_MODE_DOCLING,
            OperatorConstants.ExtractionModes.ENTITY_MODE_LITELLM,
            OperatorConstants.ExtractionModes.ENTITY_MODE_NONE,
        ]
