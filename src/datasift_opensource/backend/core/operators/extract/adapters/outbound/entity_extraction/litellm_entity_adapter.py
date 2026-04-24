"""LiteLLM entity extraction adapter.

This adapter implements entity extraction using LiteLLM for multi-provider LLM support.
It supports both schema-based and schema-free extraction modes across multiple providers
(OpenAI, Anthropic, Cohere, etc.).
"""

import json
from typing import Any

from common.constants import OperatorConstants
from common.util.infrastructure.logging import get_logger
from core.operators.extract.ports.outbound.entity_extraction import EntityExtractionPort

logger = get_logger(__name__)


class LiteLLMEntityAdapter(EntityExtractionPort):
    """LiteLLM-based entity extraction adapter.

    This adapter uses LiteLLM to extract structured entities from document text
    across multiple LLM providers (OpenAI, Anthropic, Cohere, etc.). It supports
    both schema-based extraction (with a predefined schema) and schema-free
    extraction (discovering entities automatically).

    Attributes:
        ADAPTER_NAME: Short identifier "litellm"
        ADAPTER_DISPLAY_NAME: Display name "LiteLLM"
        model_name: LLM model identifier (e.g., "gpt-3.5-turbo", "claude-3-sonnet")
        temperature: LLM sampling temperature (0.0 = deterministic)
        max_tokens: Maximum tokens for LLM response
        max_doc_chars: Maximum document characters to send to LLM
        api_key: Optional API key for the provider
        api_base: Optional custom API base URL
        litellm_client: LiteLLMLLMClient instance for LLM communication
    """

    ADAPTER_NAME = OperatorConstants.ExtractionModes.ENTITY_MODE_LITELLM
    ADAPTER_DISPLAY_NAME = "LiteLLM"

    def __init__(self, *, config: dict[str, Any]) -> None:
        """Initialize the adapter with configuration.

        Args:
            config: Configuration dictionary
        """
        super().__init__(config=config)

    def validate(self, *, config: dict[str, Any]) -> None:
        """Validate LiteLLM-specific configuration.

        Args:
            config: Configuration dictionary to validate

        Raises:
            ValueError: If required model_name is missing or blank
        """
        model_name = config.get(OperatorConstants.Config.MODEL_NAME)
        if not isinstance(model_name, str) or not model_name.strip():
            raise ValueError(
                f"'{OperatorConstants.ExtractionModes.ENTITY_MODEL_NAME}' is required when "
                f"entity extraction mode is '{OperatorConstants.ExtractionModes.ENTITY_MODE_LITELLM}'"
            )
        # Validate numeric parameters if present
        for param in [
            OperatorConstants.LLM.TEMPERATURE,
            OperatorConstants.LLM.MAX_TOKENS,
            OperatorConstants.LLM.MAX_DOC_CHARS,
        ]:
            value = config.get(param)
            if value is not None and not isinstance(value, (int, float)):
                raise ValueError(f"LiteLLMEntityAdapter '{param}' must be a number")

        # Validate provider-specific configuration if present
        api_key = config.get(OperatorConstants.Config.API_KEY)
        if api_key is not None and not isinstance(api_key, str):
            raise ValueError("LiteLLMEntityAdapter 'api_key' must be a string")

        api_base = config.get(OperatorConstants.LLM.API_BASE)
        if api_base is not None and not isinstance(api_base, str):
            raise ValueError("LiteLLMEntityAdapter 'api_base' must be provided and as a string")
        super().validate(config=config)

    def _init_adapter_config(self, *, config: dict[str, Any]) -> None:
        """Initialize LiteLLM-specific configuration.

        Args:
            config: Configuration dictionary containing:
                - model_name: LLM model identifier
                - temperature: Sampling temperature (default: 0.0)
                - max_tokens: Maximum response tokens (default: 4096)
                - max_doc_chars: Maximum document characters (default: 8000)
                - api_key: Optional API key for the provider
                - api_base: Optional custom API base URL
        """
        self.model_name: str = str(config.get(OperatorConstants.Config.MODEL_NAME))
        self.temperature = float(config.get(OperatorConstants.LLM.TEMPERATURE, 0.0))
        self.max_tokens = int(config.get(OperatorConstants.LLM.MAX_TOKENS, 4096))
        self.max_doc_chars = int(config.get(OperatorConstants.LLM.MAX_DOC_CHARS, 8000))
        self.api_key = config.get(OperatorConstants.Config.API_KEY)
        self.api_base = config.get(OperatorConstants.LLM.API_BASE)

        # Initialize LiteLLM client (lazy import to avoid breaking due to import chain issues)
        from common.clients.litellm_llm_client import LiteLLMLLMClient

        self.litellm_client = LiteLLMLLMClient(
            model_name=self.model_name,
            api_key=self.api_key,
            api_base=self.api_base,
        )

        logger.info(
            "Initialized LiteLLMEntityAdapter with model=%s, temperature=%s, max_tokens=%s",
            self.model_name,
            self.temperature,
            self.max_tokens,
        )

    def extract_entities_single(
        self, *, doc_id: str, doc_name: str, content: str | bytes, schema: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Extract entities from a single document using LiteLLM.

        Args:
            doc_id: Document identifier
            doc_name: Document name for logging
            content: Document text content (str) or binary content (bytes)
            schema: Optional schema dictionary for structured extraction

        Returns:
            Dictionary with extraction results:
            {
                "success": bool,
                "entities": dict,
                "error": str | None
            }
        """
        # Convert bytes to string if needed
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="ignore")
        try:
            # Truncate content if needed
            truncated_content = content[: self.max_doc_chars] if len(content) > self.max_doc_chars else content

            # Check if schema is provided
            if schema and (schema.get("fields") or schema.get("columns")):
                # Schema-based extraction
                system_prompt = OperatorConstants.ExtractionModes.ENTITY_EXTRACTION_SYSTEM_PROMPT
                user_prompt = self._build_schema_prompt(content=truncated_content, schema=schema)
            else:
                # Schema-free extraction
                system_prompt = OperatorConstants.ExtractionModes.ENTITY_EXTRACTION_SCHEMA_FREE_SYSTEM_PROMPT
                user_prompt = self._build_schema_free_prompt(content=truncated_content)

            raw_response = self.litellm_client.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )

            entities = self._parse_llm_json(raw_response=raw_response)

            return {
                OperatorConstants.Extraction.SUCCESS: True,
                OperatorConstants.Misc.ENTITIES: entities,
                OperatorConstants.Extraction.ERROR: None,
            }

        except Exception as exc:
            logger.error("Entity extraction failed for doc '%s' (%s): %s", doc_name, doc_id, exc)
            return {
                OperatorConstants.Extraction.SUCCESS: False,
                OperatorConstants.Misc.ENTITIES: {},
                OperatorConstants.Extraction.ERROR: str(exc),
            }
