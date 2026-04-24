"""Ollama entity extraction adapter.

This adapter implements entity extraction using a locally running Ollama LLM.
It supports both schema-based and schema-free extraction modes.
"""

import json
from typing import Any

from common.constants import OperatorConstants
from common.util.infrastructure.logging import get_logger
from core.operators.extract.ports.outbound.entity_extraction import EntityExtractionPort

logger = get_logger(__name__)


class OllamaEntityAdapter(EntityExtractionPort):
    """Ollama-based entity extraction adapter.

    This adapter uses a locally running Ollama LLM to extract structured entities
    from document text. It supports both schema-based extraction (with a predefined
    schema) and schema-free extraction (discovering entities automatically).

    Attributes:
        ADAPTER_NAME: Short identifier "ollama"
        ADAPTER_DISPLAY_NAME: Display name "Ollama"
        model_name: Ollama model to use (e.g., "llama3.2", "granite4")
        temperature: LLM sampling temperature (0.0 = deterministic)
        max_tokens: Maximum tokens for LLM response
        max_doc_chars: Maximum document characters to send to LLM
        ollama_client: OllamaClient instance for LLM communication
    """

    ADAPTER_NAME = "ollama"
    ADAPTER_DISPLAY_NAME = "Ollama"

    def __init__(self, *, config: dict[str, Any]) -> None:
        """Initialize the adapter with configuration.

        Args:
            config: Configuration dictionary
        """
        super().__init__(config=config)

    def validate(self, *, config: dict[str, Any]) -> None:
        """Validate Ollama-specific configuration.

        Args:
            config: Configuration dictionary to validate

        Raises:
            ValueError: If required model_name is missing or blank
        """
        model_name = config.get(OperatorConstants.Config.MODEL_NAME)
        if not isinstance(model_name, str) or not model_name.strip():
            raise ValueError(
                f"'{OperatorConstants.ExtractionModes.ENTITY_MODEL_NAME}' is required when "
                f"entity extraction mode is '{OperatorConstants.ExtractionModes.ENTITY_MODE_OLLAMA}'"
            )
        # Validate numeric parameters if present
        for param in [
            OperatorConstants.LLM.TEMPERATURE,
            OperatorConstants.LLM.MAX_TOKENS,
            OperatorConstants.LLM.MAX_DOC_CHARS,
        ]:
            value = config.get(param)
            if value is not None and not isinstance(value, (int, float)):
                raise ValueError(f"OllamaEntityAdapter '{param}' must be a number")
        super().validate(config=config)

    def _init_adapter_config(self, *, config: dict[str, Any]) -> None:
        """Initialize Ollama-specific configuration.

        Args:
            config: Configuration dictionary containing:
                - model_name: Ollama model name (default: "llama3.2")
                - temperature: Sampling temperature (default: 0.0)
                - max_tokens: Maximum response tokens (default: 4096)
                - max_doc_chars: Maximum document characters (default: 8000)
        """
        self.model_name: str = str(config.get(OperatorConstants.Config.MODEL_NAME))
        self.temperature = float(config.get(OperatorConstants.LLM.TEMPERATURE, 0.0))
        self.max_tokens = int(config.get(OperatorConstants.LLM.MAX_TOKENS, 4096))
        self.max_doc_chars = int(config.get(OperatorConstants.LLM.MAX_DOC_CHARS, 8000))

        # Initialize Ollama client (lazy import to avoid breaking ollama due to import chain issues)
        from common.clients.ollama_client import OllamaClient

        self.ollama_client = OllamaClient(
            model_name=self.model_name,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            max_doc_chars=self.max_doc_chars,
        )

        logger.info(
            "Initialized OllamaEntityAdapter with model=%s, temperature=%s, max_tokens=%s",
            self.model_name,
            self.temperature,
            self.max_tokens,
        )

    def extract_entities_single(
        self, *, doc_id: str, doc_name: str, content: str | bytes, schema: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Extract entities from a single document using Ollama.

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

            response = self.ollama_client.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )

            # Parse response - handle both dict and ChatResponse object
            if isinstance(response, dict):
                raw_response = response.get("message", {}).get("content", "")
            elif hasattr(response, "message"):
                message = response.message
                if isinstance(message, dict):
                    raw_response = message.get("content", "")
                elif hasattr(message, "content"):
                    raw_response = message.content or ""
                else:
                    raw_response = ""
            else:
                raw_response = ""
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
