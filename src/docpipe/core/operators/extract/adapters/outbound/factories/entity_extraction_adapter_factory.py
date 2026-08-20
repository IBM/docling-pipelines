"""Factory for creating entity extraction adapters.

This factory creates appropriate entity extraction adapter instances based on the
extraction mode and configuration. It supports multiple extraction strategies:
- LLM: Unified LLM-based entity extraction using shared infrastructure (watsonx, litellm)
- DOCLING: Template-based entity extraction using Docling templates
"""

import logging
from typing import Any, ClassVar

from docpipe.core.constants.constants import DoclingClientConfigConstants
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.extract.domain import EntityExtractionMode
from docpipe.core.operators.extract.ports.outbound.entity_extraction import EntityExtractionPort
from docpipe.utils.infrastructure.logging import get_logger

logger: logging.Logger = get_logger()


class EntityExtractionAdapterFactory:
    """Factory for creating entity extraction adapters.

    This factory creates appropriate adapter instances based on extraction mode
    and validates configuration requirements for each adapter type.

    It also maintains a class registry so that third-party adapters can
    self-register via ``@register_entity_extraction_adapter``.

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

    # Registry of adapter classes keyed by ADAPTER_NAME (populated via @register_entity_extraction_adapter).
    _registry: ClassVar[dict[str, type[EntityExtractionPort]]] = {}

    @classmethod
    def register(cls, adapter_class: type[EntityExtractionPort]) -> type[EntityExtractionPort]:
        """Register an adapter class in the schema-discovery registry.

        Called automatically by the ``@register_entity_extraction_adapter`` decorator.

        Args:
            adapter_class: Concrete subclass of ``EntityExtractionPort``.

        Returns:
            The adapter class (for decorator chaining).

        Raises:
            ValueError: If the class does not define ``ADAPTER_NAME``.
        """
        if not hasattr(adapter_class, "ADAPTER_NAME") or not adapter_class.ADAPTER_NAME:
            raise ValueError(f"Adapter {adapter_class.__name__} must define ADAPTER_NAME")

        name = adapter_class.ADAPTER_NAME.lower()
        cls._registry[name] = adapter_class
        return adapter_class

    @classmethod
    def list_adapters(cls) -> list[str]:
        """Return names of all registered adapters.

        Returns:
            List of registered adapter names.
        """
        return list(cls._registry.keys())

    @staticmethod
    def build_adapter_config(
        *, mode: EntityExtractionMode, entity_extraction_config: dict[str, Any], doc_column: str
    ) -> dict[str, Any]:
        """Build adapter-specific configuration from nested entity_extraction config.

        This method extracts and transforms the nested entity_extraction configuration into
        adapter-specific configuration, handling mode-specific requirements.

        Args:
            mode: Entity extraction mode (LITELLM, WATSONX, DOCLING, NONE)
            entity_extraction_config: Nested entity_extraction configuration dictionary
            doc_column: Document column name from text_extraction config

        Returns:
            Adapter-specific configuration dictionary

        Raises:
            ValueError: If mode is unsupported or configuration is invalid
        """
        # Extract provider_config from nested structure
        provider_config = entity_extraction_config.get(OperatorConstants.Config.PROVIDER_CONFIG, {})

        adapter_config = {
            "doc_column": doc_column,  # Use doc_column from text_extraction
            OperatorConstants.Columns.OUTPUT_COLUMN: entity_extraction_config.get(
                OperatorConstants.Columns.OUTPUT_COLUMN, OperatorConstants.Misc.ENTITIES
            ),
            "expand_extracted_data": entity_extraction_config.get(
                OperatorConstants.Config.EXPAND_EXTRACTED_DATA, False
            ),
            "custom_schema": entity_extraction_config.get(OperatorConstants.Config.CUSTOM_SCHEMA, {}),
            "common_log_arguments": entity_extraction_config.get("common_log_arguments", {}),
            # Job-tracking fields (job_run_id, node_id, node_name, batch_id) are NOT read
            # from entity_extraction_config — they are never present there (they come from
            # the orchestrator via global_config).  Reading them here produces None values
            # that would overwrite the real values already in global_config at line 184.
        }

        # Add mode-specific configuration from provider_config
        if mode in (EntityExtractionMode.LITELLM, EntityExtractionMode.WATSONX):
            # Both LITELLM and WATSONX modes use LLM adapter with provider-specific config
            # Set provider based on mode (use entity mode constants as provider names)
            provider = (
                OperatorConstants.ExtractionModes.ENTITY_MODE_LITELLM
                if mode == EntityExtractionMode.LITELLM
                else OperatorConstants.ExtractionModes.ENTITY_MODE_WATSONX
            )

            adapter_config.update(
                {
                    OperatorConstants.Config.PROVIDER: provider,
                    OperatorConstants.Config.MODEL_NAME: provider_config.get(OperatorConstants.Config.MODEL_ID),
                    OperatorConstants.LLM.TEMPERATURE: provider_config.get(OperatorConstants.LLM.TEMPERATURE, 0.0),
                    OperatorConstants.LLM.MAX_TOKENS: provider_config.get("max_tokens", 4096),
                    OperatorConstants.LLM.MAX_DOC_CHARS: entity_extraction_config.get("max_doc_chars", 8000),
                    "entity_provider_config": provider_config,
                }
            )

        elif mode == EntityExtractionMode.DOCLING:
            # Pass through vlm_pipeline from provider_config for custom model configuration
            vlm_pipeline = provider_config.get(DoclingClientConfigConstants.VLM_PIPELINE)
            if vlm_pipeline:
                adapter_config[DoclingClientConfigConstants.VLM_PIPELINE] = vlm_pipeline

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
        *,
        mode: EntityExtractionMode,
        entity_extraction_config: dict[str, Any],
        global_config: dict[str, Any],
        doc_column: str,
        max_workers: int = 4,
    ) -> EntityExtractionPort | None:
        """Create appropriate entity extraction adapter based on mode.

        Args:
            mode: Extraction mode ("litellm", "watsonx", "docling", or "none")
            entity_extraction_config: Nested entity_extraction configuration dictionary
            global_config: Global operator configuration (for job tracking, etc.)
            doc_column: Document column name from text_extraction config
            max_workers: Number of parallel workers (default: 4)

        Returns:
            Configured EntityExtractionPort adapter instance, or None if mode is "none"

        Raises:
            ValueError: If mode is unsupported or config is invalid
        """
        # Build adapter-specific configuration from nested entity_extraction config
        adapter_config = EntityExtractionAdapterFactory.build_adapter_config(
            mode=mode, entity_extraction_config=entity_extraction_config, doc_column=doc_column
        )

        # Merge with global config for job tracking and other global settings
        # IMPORTANT: Merge global_config first to preserve keys like ingest_source
        full_config = {**global_config, **adapter_config, "max_workers": max_workers}

        # LITELLM and WATSONX modes use LLM adapter
        if mode in (EntityExtractionMode.LITELLM, EntityExtractionMode.WATSONX):
            from docpipe.core.operators.extract.adapters.outbound.entity_extraction.llm_entity_adapter import (
                LLMEntityAdapter,
            )

            provider = adapter_config.get(OperatorConstants.Config.PROVIDER)
            logger.info(
                "Creating LLMEntityAdapter with provider=%s, model=%s, and %s workers",
                provider,
                adapter_config.get(OperatorConstants.Config.MODEL_NAME),
                max_workers,
            )
            return LLMEntityAdapter(config=full_config)

        if mode == EntityExtractionMode.DOCLING:
            from docpipe.core.operators.extract.adapters.outbound.entity_extraction.docling_entity_adapter import (
                DoclingEntityAdapter,
            )

            logger.info("Creating DoclingEntityAdapter with %s workers", max_workers)
            return DoclingEntityAdapter(config=full_config)

        if mode == EntityExtractionMode.NONE:
            logger.info("Entity extraction disabled (mode='none')")
            return None

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


def register_entity_extraction_adapter(adapter_class: type[EntityExtractionPort]) -> type[EntityExtractionPort]:
    """Decorator to register an entity extraction adapter for schema discovery.

    This decorator automatically registers the adapter class with
    ``EntityExtractionAdapterFactory``.

    Args:
        adapter_class: Concrete subclass of ``EntityExtractionPort``.

    Returns:
        The adapter class (unchanged).

    Example::

        @register_entity_extraction_adapter
        class LLMEntityAdapter(EntityExtractionPort):
            ADAPTER_NAME = "litellm"
            ADAPTER_DISPLAY_NAME = "LiteLLM"
            ...
    """
    return EntityExtractionAdapterFactory.register(adapter_class)
