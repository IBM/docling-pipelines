"""Ollama entity extraction adapter.

This adapter implements entity extraction using a locally running Ollama LLM.
It supports both schema-based and schema-free extraction modes.
"""

import json
import re
from typing import Any

from common.constants import OperatorConstants
from common.util.infrastructure.logging import get_logger
from core.operators.extract.ports.outbound.entity_extraction import EntityExtractionPort

logger = get_logger(__name__)

# System prompts
_SYSTEM_PROMPT = """\
You are a precise document entity extraction assistant.
Your task is to extract structured information from document text and return it \
as valid JSON that exactly matches the provided schema template.

Rules:
1. Return ONLY a valid JSON object — no markdown fences, no explanation text.
2. Use null for any field that cannot be found in the document.
3. For NESTED fields, return a list of objects.
4. Do not add extra fields not in the template.
5. Preserve original values (dates, amounts, names) exactly as they appear.
"""

_SCHEMA_FREE_SYSTEM_PROMPT = """\
You are a precise document entity extraction assistant.
Your task is to identify and extract ALL named entities and key structured information
from the document text and return them as a valid JSON object.

Rules:
1. Return ONLY a valid JSON object — no markdown fences, no explanation text.
2. Use meaningful key names that describe the entity type (e.g. "invoice_number", "vendor_name", "total_amount").
3. Group related entities under nested objects where appropriate (e.g. "vendor": {"name": ..., "address": ...}).
4. Use null for any field that cannot be determined.
5. Preserve original values (dates, amounts, names) exactly as they appear.
6. Include all significant entities: people, organizations, dates, amounts, locations, identifiers, etc.
"""


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

    def _init_adapter_config(self, *, config: dict[str, Any]) -> None:
        """Initialize Ollama-specific configuration.

        Args:
            config: Configuration dictionary containing:
                - model_name: Ollama model name (default: "llama3.2")
                - temperature: Sampling temperature (default: 0.0)
                - max_tokens: Maximum response tokens (default: 4096)
                - max_doc_chars: Maximum document characters (default: 8000)
        """
        self.model_name = config.get(OperatorConstants.Config.MODEL_NAME, "llama3.2")
        self.temperature = float(config.get(OperatorConstants.ExtractionModes.ENTITY_TEMPERATURE, 0.0))
        self.max_tokens = int(config.get(OperatorConstants.ExtractionModes.ENTITY_MAX_TOKENS, 4096))
        self.max_doc_chars = int(config.get("max_doc_chars", 8000))

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
        self, doc_id: str, doc_name: str, content: str | bytes, schema: dict[str, Any] | None = None, **kwargs: Any
    ) -> dict[str, Any]:
        """Extract entities from a single document using Ollama.

        Args:
            doc_id: Document identifier
            doc_name: Document name for logging
            content: Document text content (str) or binary content (bytes)
            schema: Optional schema dictionary for structured extraction
            **kwargs: Additional parameters (unused)

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
            has_schema = bool(schema and (schema.get("fields") or schema.get("columns")))

            if has_schema and schema is not None:
                # Schema-based extraction
                system_prompt = _SYSTEM_PROMPT
                user_prompt = self._build_schema_prompt(content=truncated_content, schema=schema)
            else:
                # Schema-free extraction
                system_prompt = _SCHEMA_FREE_SYSTEM_PROMPT
                user_prompt = self._build_schema_free_prompt(content=truncated_content)

            # Log prompts for debugging
            logger.debug("=" * 80)
            logger.debug("LLM PROMPT for document '%s' (ID: %s)", doc_name, doc_id)
            logger.debug("-" * 80)
            logger.debug("SYSTEM PROMPT:\n%s", system_prompt)
            logger.debug("-" * 80)
            logger.debug("USER PROMPT:\n%s", user_prompt)
            logger.debug("=" * 80)

            response = self.ollama_client.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                options={"temperature": self.temperature},
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

            # Log extracted entities
            logger.info("=" * 80)
            logger.info("EXTRACTED ENTITIES for document '%s' (ID: %s)", doc_name, doc_id)
            logger.info("-" * 80)
            logger.info("%s", json.dumps(entities, indent=2, ensure_ascii=False))
            logger.info("=" * 80)

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

    def _build_schema_prompt(self, *, content: str, schema: dict[str, Any]) -> str:
        """Build prompt for schema-based extraction.

        Args:
            content: Document text content
            schema: Schema dictionary with fields/columns

        Returns:
            Formatted user prompt string
        """
        # Extract schema metadata
        schema_name = schema.get("document_type", "") or schema.get("table", "")
        schema_desc_text = schema.get("document_description", "") or schema.get("description", "")

        # Build schema description using helper functions
        schema_desc = self._build_schema_description(schema=schema)

        # Build JSON template
        json_template = self._build_json_template(schema=schema)

        return (
            f"Extract entities from the following document text.\n\n"
            f"Document Type: {schema_name}\n"
            f"Description: {schema_desc_text}\n\n"
            f"Schema fields to extract:\n{schema_desc}\n\n"
            f"Return your answer as a JSON object matching this template exactly:\n"
            f"{json.dumps(json_template, indent=2)}\n\n"
            f"Document text:\n{content}"
        )

    def _build_schema_description(self, *, schema: dict[str, Any]) -> str:
        """Build human-readable schema description.

        Args:
            schema: Schema dictionary

        Returns:
            Formatted schema description
        """
        from common.util.document_class_utils import DocumentClassUtils

        # Check for new 'fields' format first
        if "fields" in schema:
            return DocumentClassUtils.build_schema_description_from_fields(schema["fields"])

        # Fall back to old 'columns' format
        columns = schema.get("columns", {})
        if not columns:
            return ""

        lines: list[str] = []
        for col_name, col_type in columns.items():
            lines.append(f"  - {col_name} ({col_type})")

        return "\n".join(lines)

    def _build_json_template(self, *, schema: dict[str, Any]) -> dict[str, Any]:
        """Build JSON template from schema.

        Args:
            schema: Schema dictionary

        Returns:
            JSON template dictionary
        """
        from common.util.document_class_utils import DocumentClassUtils

        # Check for new 'fields' format first
        if "fields" in schema:
            return DocumentClassUtils.build_json_template_from_fields(schema["fields"])

        # Fall back to old 'columns' format
        columns = schema.get("columns", {})
        if not columns:
            return {}

        template: dict[str, Any] = {}
        for col_name in columns.keys():
            if "." in col_name:
                # Build nested structure
                parts = col_name.split(".")
                current = template
                for part in parts[:-1]:
                    if part not in current:
                        current[part] = {}
                    current = current[part]
                current[parts[-1]] = None
            else:
                template[col_name] = None

        return template

    def _build_schema_free_prompt(self, *, content: str) -> str:
        """Build prompt for schema-free extraction.

        Args:
            content: Document text content

        Returns:
            Formatted user prompt string
        """
        return (
            f"Extract all named entities and key information from the following document text.\n\n"
            f"Document text:\n{content}"
        )

    def _parse_llm_json(self, *, raw_response: str) -> dict[str, Any]:
        """Parse JSON from LLM response with repair logic.

        Args:
            raw_response: Raw LLM response text

        Returns:
            Parsed JSON dictionary (empty dict if parsing fails)
        """
        text = raw_response.strip()

        # Strip markdown fences
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:]).strip()

        # Direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Regex extraction of first {...} block
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                repaired = self._try_repair_truncated_json(raw=match.group())
                if repaired is not None:
                    return repaired

        # Last-resort repair
        repaired = self._try_repair_truncated_json(raw=text)
        if repaired is not None:
            return repaired

        logger.warning("Failed to parse LLM response as JSON, returning empty dict")
        return {}

    def _try_repair_truncated_json(self, *, raw: str) -> dict[str, Any] | None:
        """Try to repair truncated JSON by closing unclosed braces/brackets.

        Args:
            raw: Raw JSON string (potentially truncated)

        Returns:
            Parsed JSON dictionary or None if repair fails
        """
        stack: list[str] = []
        in_string = False
        escape_next = False

        for char in raw:
            if escape_next:
                escape_next = False
                continue
            if char == "\\" and in_string:
                escape_next = True
                continue
            if char == '"':
                in_string = not in_string
                continue
            if not in_string:
                if char in "{[":
                    stack.append("}" if char == "{" else "]")
                elif char in "}]":
                    if stack and stack[-1] == char:
                        stack.pop()

        closing = "".join(reversed(stack))
        repaired = raw.rstrip() + closing

        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            return None
