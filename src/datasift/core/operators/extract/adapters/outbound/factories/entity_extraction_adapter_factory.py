"""Factory for creating entity extraction adapters.

This factory creates appropriate entity extraction adapter instances based on the
extraction mode and configuration. It supports multiple extraction strategies:
- LLM: Unified LLM-based entity extraction using shared infrastructure (watsonx, litellm)
- DOCLING: Template-based entity extraction using Docling templates
"""

import logging
from typing import Any

from datasift.core.constants.constants import DoclingClientConfigConstants
from datasift.core.constants.operator_constants import OperatorConstants
from datasift.core.operators.extract.adapters.outbound.entity_extraction.docling_entity_adapter import (
    DoclingEntityAdapter,
)
from datasift.core.operators.extract.adapters.outbound.entity_extraction.llm_entity_adapter import (
    LLMEntityAdapter,
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
        - "litellm": LLM-based extraction using LiteLLM (supports multiple providers)
        - "watsonx": LLM-based extraction using IBM watsonx
        - "docling": Template-based extraction using Docling templates
        - "none": No entity extraction

    Example Usage:
        # Create LiteLLM adapter
        config = {
            OperatorConstants.Config.MODEL_NAME: "openai/granite4:latest",
            OperatorConstants.LLM.TEMPERATURE: 0.0,
            OperatorConstants.LLM.MAX_TOKENS: 4096,
            OperatorConstants.LLM.MAX_DOC_CHARS: 8000,
            "entity_provider_config": {
                "api_base": "http://localhost:11434/v1",
                "api_key": "<ollama_key>"
            },
            "doc_column": "doc_content",
            "output_column": "entities",
            "expand_extracted_data": False
        }
        adapter = EntityExtractionAdapterFactory.create_adapter(
            mode="litellm",
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
            mode: Entity extraction mode (LITELLM, WATSONX, DOCLING, NONE)
            operator_config: Full operator configuration dictionary

        Returns:
            Adapter-specific configuration dictionary

        Raises:
            ValueError: If mode is unsupported or configuration is invalid
        """
        # Common configuration for all entity modes
        from datasift.core.constants.constants import DatasiftConstants

        adapter_config = {
            "doc_column": operator_config.get("doc_column", OperatorConstants.Columns.DOC_COLUMN_DEFAULT),
            OperatorConstants.Columns.OUTPUT_COLUMN: operator_config.get(
                OperatorConstants.Columns.OUTPUT_COLUMN, OperatorConstants.Misc.ENTITIES
            ),
            "expand_extracted_data": operator_config.get(OperatorConstants.Config.EXPAND_EXTRACTED_DATA, False),
            "custom_schema": operator_config.get(OperatorConstants.Config.CUSTOM_SCHEMA, {}),
            "common_log_arguments": operator_config.get("common_log_arguments", {}),
            # Job tracking context for progress updates
            DatasiftConstants.JOB_RUN_ID: operator_config.get(DatasiftConstants.JOB_RUN_ID),
            DatasiftConstants.NODE_ID: operator_config.get(DatasiftConstants.NODE_ID),
            DatasiftConstants.NODE_NAME: operator_config.get(DatasiftConstants.NODE_NAME),
            DatasiftConstants.BATCH_ID: operator_config.get(DatasiftConstants.BATCH_ID),
        }

        # Add mode-specific configuration
        if mode in (EntityExtractionMode.LITELLM, EntityExtractionMode.WATSONX):
            # Both LITELLM and WATSONX modes use LLM adapter with provider-specific config
            entity_provider_config = operator_config.get("entity_provider_config", {})

            # Set provider based on mode (use entity mode constants as provider names)
            provider = (
                OperatorConstants.ExtractionModes.ENTITY_MODE_LITELLM
                if mode == EntityExtractionMode.LITELLM
                else OperatorConstants.ExtractionModes.ENTITY_MODE_WATSONX
            )

            adapter_config.update(
                {
                    OperatorConstants.Config.PROVIDER: provider,
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
                    "entity_provider_config": entity_provider_config,
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
                f"Unsupported entity extraction mode: {mode}. Supported modes: litellm, watsonx, docling, none"
            )

        return adapter_config

    @staticmethod
    def create_adapter(
        *, mode: EntityExtractionMode, operator_config: dict[str, Any], max_workers: int = 4
    ) -> EntityExtractionPort | None:
        """Create appropriate entity extraction adapter based on mode.

        Args:
            mode: Extraction mode ("litellm", "watsonx", "docling", or "none")
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
        # IMPORTANT: Merge operator_config first to preserve global_config keys like ingest_source
        full_config = {**operator_config, **adapter_config, "max_workers": max_workers}

        # LITELLM and WATSONX modes use LLM adapter
        if mode in (EntityExtractionMode.LITELLM, EntityExtractionMode.WATSONX):
            provider = adapter_config.get(OperatorConstants.Config.PROVIDER)
            logger.info(
                "Creating LLMEntityAdapter with provider=%s, model=%s, and %s workers",
                provider,
                adapter_config.get(OperatorConstants.Config.MODEL_NAME),
                max_workers,
            )
            return LLMEntityAdapter(config=full_config)

        elif mode == EntityExtractionMode.DOCLING:
            logger.info("Creating DoclingEntityAdapter with %s workers", max_workers)
            return DoclingEntityAdapter(config=full_config)

        elif mode == EntityExtractionMode.NONE:
            logger.info("Entity extraction disabled (mode='none')")
            return None

        else:
            raise ValueError(
                f"Unsupported entity extraction mode: {mode}. Supported modes: litellm, watsonx, docling, none"
            )

    @staticmethod
    def get_supported_modes() -> list[str]:
        """Get list of supported extraction modes.

        Returns:
            List of supported extraction mode values
        """
        return [
            EntityExtractionMode.LITELLM,
            EntityExtractionMode.WATSONX,
            EntityExtractionMode.DOCLING,
            EntityExtractionMode.NONE,
        ]
