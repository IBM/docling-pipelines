"""Factory for creating entity extraction adapters.

This factory creates appropriate entity extraction adapter instances based on the
extraction mode and configuration. It supports multiple extraction strategies:
- OLLAMA: LLM-based entity extraction using Ollama models
- DOCLING: Template-based entity extraction using Docling templates
"""

import logging
from typing import Any

from datasift.core.constants.constants import DoclingClientConfigConstants
from datasift.core.constants.operator_constants import OperatorConstants
from datasift.core.operators.extract.adapters.outbound.entity_extraction.docling_entity_adapter import (
    DoclingEntityAdapter,
)
from datasift.core.operators.extract.adapters.outbound.entity_extraction.litellm_entity_adapter import (
    LiteLLMEntityAdapter,
)
from datasift.core.operators.extract.adapters.outbound.entity_extraction.ollama_entity_adapter import (
    OllamaEntityAdapter,
)
from datasift.core.operators.extract.adapters.outbound.entity_extraction.watsonx_entity_adapter import (
    WatsonXEntityAdapter,
)
from datasift.core.operators.extract.domain import EntityExtractionMode
from datasift.core.operators.extract.ports.outbound.entity_extraction import EntityExtractionPort
from datasift.utils.infrastructure.logging import get_logger

logger: logging.Logger = get_logger()


class EntityExtractionAdapterFactory:
    """Factory for creating entity extraction adapters.

    This factory creates appropriate adapter instances based on extraction mode
    and validates configuration requirements for each adapter type.

    Supported Modes:
        - "ollama": LLM-based extraction using Ollama models
        - "docling": Template-based extraction using Docling templates
        - "litellm": Multi-provider LLM extraction using LiteLLM
        - "watsonx": IBM watsonx.ai LLM extraction
        - "none": No entity extraction

    Example Usage:
        # Create Ollama adapter
        config = {
            OperatorConstants.Config.MODEL_NAME: "llama3.2",
            OperatorConstants.LLM.TEMPERATURE: 0.0,
            OperatorConstants.LLM.MAX_TOKENS: 4096,
            OperatorConstants.LLM.MAX_DOC_CHARS: 8000,
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
            "expand_extracted_data": operator_config.get(OperatorConstants.Config.EXPAND_EXTRACTED_DATA, False),
            "custom_schema": operator_config.get(OperatorConstants.Config.CUSTOM_SCHEMA, {}),
            "common_log_arguments": operator_config.get("common_log_arguments", {}),
        }

        # Add mode-specific configuration
        if mode == EntityExtractionMode.OLLAMA:
            adapter_config.update(
                {
                    OperatorConstants.Config.MODEL_NAME: operator_config.get(
                        OperatorConstants.ExtractionModes.ENTITY_MODEL_NAME
                    ),
                    OperatorConstants.LLM.TEMPERATURE: operator_config.get(
                        OperatorConstants.ExtractionModes.ENTITY_TEMPERATURE, 0.0
                    ),
                    OperatorConstants.LLM.MAX_TOKENS: operator_config.get(
                        OperatorConstants.ExtractionModes.ENTITY_MAX_TOKENS, 4096
                    ),
                    OperatorConstants.LLM.MAX_DOC_CHARS: operator_config.get(
                        OperatorConstants.ExtractionModes.ENTITY_MAX_DOC_CHARS, 8000
                    ),
                }
            )

        elif mode == EntityExtractionMode.LITELLM:
            # Extract provider-specific configuration
            entity_provider_config = operator_config.get("entity_provider_config", {})
            adapter_config.update(
                {
                    OperatorConstants.Config.MODEL_NAME: operator_config.get(
                        OperatorConstants.ExtractionModes.ENTITY_MODEL_NAME
                    ),
                    OperatorConstants.LLM.TEMPERATURE: operator_config.get(
                        OperatorConstants.ExtractionModes.ENTITY_TEMPERATURE, 0.0
                    ),
                    OperatorConstants.LLM.MAX_TOKENS: operator_config.get(
                        OperatorConstants.ExtractionModes.ENTITY_MAX_TOKENS, 2000
                    ),
                    OperatorConstants.LLM.MAX_DOC_CHARS: operator_config.get(
                        OperatorConstants.ExtractionModes.ENTITY_MAX_DOC_CHARS, 8000
                    ),
                    OperatorConstants.Config.API_KEY: entity_provider_config.get(OperatorConstants.Config.API_KEY, ""),
                    OperatorConstants.LLM.API_BASE: entity_provider_config.get(OperatorConstants.LLM.API_BASE),
                }
            )

        elif mode == EntityExtractionMode.WATSONX:
            # Extract provider-specific configuration
            entity_provider_config = operator_config.get("entity_provider_config", {})
            adapter_config.update(
                {
                    OperatorConstants.Config.MODEL_NAME: operator_config.get(
                        OperatorConstants.ExtractionModes.ENTITY_MODEL_NAME
                    ),
                    OperatorConstants.LLM.TEMPERATURE: operator_config.get(
                        OperatorConstants.ExtractionModes.ENTITY_TEMPERATURE, 0.0
                    ),
                    OperatorConstants.LLM.MAX_TOKENS: operator_config.get(
                        OperatorConstants.ExtractionModes.ENTITY_MAX_TOKENS, 4096
                    ),
                    OperatorConstants.LLM.MAX_DOC_CHARS: operator_config.get(
                        OperatorConstants.ExtractionModes.ENTITY_MAX_DOC_CHARS, 8000
                    ),
                    OperatorConstants.Config.API_BASE: entity_provider_config.get(OperatorConstants.Config.API_BASE),
                    OperatorConstants.Config.CONTAINER_KIND: entity_provider_config.get(
                        OperatorConstants.Config.CONTAINER_KIND
                    ),
                    OperatorConstants.Config.REQUEST_TIMEOUT: entity_provider_config.get(
                        OperatorConstants.Config.REQUEST_TIMEOUT, 120
                    ),
                }
            )

        elif mode == EntityExtractionMode.DOCLING:
            # Pass through entity_config for custom model configuration
            entity_config = operator_config.get(DoclingClientConfigConstants.ENTITY_CONFIG)
            if entity_config:
                adapter_config[DoclingClientConfigConstants.ENTITY_CONFIG] = entity_config

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
            logger.info(
                "Creating OllamaEntityAdapter with model: %s and %s workers",
                adapter_config.get(OperatorConstants.Config.MODEL_NAME),
                max_workers,
            )
            return OllamaEntityAdapter(config=full_config)

        elif mode == OperatorConstants.ExtractionModes.ENTITY_MODE_DOCLING:
            logger.info("Creating DoclingEntityAdapter with %s workers", max_workers)
            return DoclingEntityAdapter(config=full_config)

        elif mode == OperatorConstants.ExtractionModes.ENTITY_MODE_LITELLM:
            logger.info(
                "Creating LiteLLMEntityAdapter with model: %s and %s workers",
                adapter_config.get(OperatorConstants.Config.MODEL_NAME),
                max_workers,
            )
            return LiteLLMEntityAdapter(config=full_config)

        elif mode == OperatorConstants.ExtractionModes.ENTITY_MODE_WATSONX:
            logger.info(
                "Creating WatsonXEntityAdapter with model: %s and %s workers",
                adapter_config.get(OperatorConstants.Config.MODEL_NAME),
                max_workers,
            )
            return WatsonXEntityAdapter(config=full_config)

        elif mode == OperatorConstants.ExtractionModes.ENTITY_MODE_NONE:
            logger.info("Entity extraction disabled (mode='none')")
            return None

        else:
            raise ValueError(
                f"Unsupported entity extraction mode: {mode}. Supported modes: ollama, docling, litellm, none"
            )

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
            OperatorConstants.ExtractionModes.ENTITY_MODE_WATSONX,
            OperatorConstants.ExtractionModes.ENTITY_MODE_NONE,
        ]
