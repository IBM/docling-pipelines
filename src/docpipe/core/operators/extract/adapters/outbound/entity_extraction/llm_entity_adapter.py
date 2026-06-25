"""Unified LLM entity extraction adapter using shared infrastructure.

This adapter implements entity extraction using the shared LLM infrastructure,
supporting both watsonx and litellm providers through a unified interface.
It replaces the provider-specific adapters (OllamaEntityAdapter, LiteLLMEntityAdapter,
WatsonXEntityAdapter) with a single implementation.
"""

from typing import Any

import pyarrow as pa

from docpipe.core.adapters.llm_adapter_factory import LLMAdapterFactory
from docpipe.core.constants import OperatorConstants
from docpipe.core.operators.extract.ports.outbound.entity_extraction import EntityExtractionPort
from docpipe.core.operators.extract.services.entity_extraction_service import EntityExtractionService
from docpipe.core.ports.llm_inference_port import LLMInferencePort
from docpipe.utils.infrastructure.logging import get_logger
from docpipe.utils.llm import parse_llm_json_response

logger = get_logger(__name__)


class LLMEntityAdapter(EntityExtractionPort):
    """Unified LLM-based entity extraction adapter.

    This adapter uses the shared LLM infrastructure to extract structured entities
    from document text across multiple LLM providers (watsonx, litellm). It supports
    both schema-based extraction (with a predefined schema) and schema-free
    extraction (discovering entities automatically).

    Supported Providers:
        - watsonx: IBM watsonx.ai models
        - litellm: Unified interface for 100+ providers including:
          * Ollama (via OpenAI-compatible API with model prefix 'openai/')
          * OpenAI, Anthropic, Cohere, HuggingFace, and 90+ more

    Attributes:
        ADAPTER_NAME: Short identifier "llm"
        ADAPTER_DISPLAY_NAME: Display name "LLM"
        provider_name: LLM provider name (watsonx or litellm)
        model_name: LLM model identifier
        temperature: LLM sampling temperature (0.0 = deterministic)
        max_tokens: Maximum tokens for LLM response
        max_doc_chars: Maximum document characters to send to LLM
        llm_adapter: LLMInferencePort instance for LLM communication
    """

    ADAPTER_NAME = "llm"
    ADAPTER_DISPLAY_NAME = "LLM"

    def __init__(self, *, config: dict[str, Any]) -> None:
        """Initialize the adapter with configuration.

        Args:
            config: Configuration dictionary
        """
        super().__init__(config=config)

    def validate(self, *, config: dict[str, Any]) -> None:
        """Validate LLM-specific configuration.

        Args:
            config: Configuration dictionary to validate

        Raises:
            ValueError: If required configuration is missing or invalid
        """
        # Validate provider
        provider = config.get(OperatorConstants.Config.PROVIDER)
        if not isinstance(provider, str) or not provider.strip():
            raise ValueError("'provider' is required for LLM entity extraction")

        provider = provider.lower()

        # Reject direct ollama provider
        if provider == "ollama":
            raise ValueError(
                "Direct 'ollama' provider is deprecated for entity extraction. "
                "Use 'litellm' provider with model_id format 'openai/<model_name>' "
                "and configure api_base='http://localhost:11434/v1' in entity_provider_config. "
                "Example: provider='litellm', entity_model_id='openai/granite4:latest'"
            )

        # Validate provider is supported
        supported_providers = LLMAdapterFactory.get_supported_providers(capability="inference")
        if provider not in supported_providers:
            raise ValueError(
                f"Unsupported provider '{provider}' for entity extraction. Supported providers: {supported_providers}"
            )

        # Validate model_name
        model_name = config.get(OperatorConstants.Config.MODEL_NAME)
        if not isinstance(model_name, str) or not model_name.strip():
            raise ValueError(f"'{OperatorConstants.Config.MODEL_NAME}' is required for LLM entity extraction")

        # Validate numeric parameters if present
        for param in [
            OperatorConstants.LLM.TEMPERATURE,
            OperatorConstants.LLM.MAX_TOKENS,
            OperatorConstants.LLM.MAX_DOC_CHARS,
        ]:
            value = config.get(param)
            if value is not None and not isinstance(value, (int, float)):
                raise ValueError(f"LLMEntityAdapter '{param}' must be a number")

        super().validate(config=config)

    def _init_adapter_config(self, *, config: dict[str, Any]) -> None:
        """Initialize LLM-specific configuration.

        Args:
            config: Configuration dictionary containing:
                - provider: LLM provider (watsonx or litellm)
                - model_name: LLM model identifier
                - temperature: Sampling temperature (default: 0.0)
                - max_tokens: Maximum response tokens (default: 2000)
                - max_doc_chars: Maximum document characters (default: 8000)
                - entity_provider_config: Provider-specific configuration
        """
        self.provider: str = str(config.get(OperatorConstants.Config.PROVIDER)).lower()
        self.model_name: str = str(config.get(OperatorConstants.Config.MODEL_NAME))

        # Handle None values for numeric parameters
        temperature = config.get(OperatorConstants.LLM.TEMPERATURE, 0.0)
        self.temperature = float(temperature) if temperature is not None else 0.0

        max_tokens = config.get(OperatorConstants.LLM.MAX_TOKENS, 2000)
        self.max_tokens = int(max_tokens) if max_tokens is not None else 2000

        max_doc_chars = config.get(OperatorConstants.LLM.MAX_DOC_CHARS, 8000)
        self.max_doc_chars = int(max_doc_chars) if max_doc_chars is not None else 8000

        # Get provider-specific configuration
        provider_config = config.get("entity_provider_config", {})

        # Create LLM adapter using shared infrastructure
        self.llm_adapter: LLMInferencePort = LLMAdapterFactory.create_inference_adapter(
            provider=self.provider,
            model_id=self.model_name,
            provider_config=provider_config,
        )

        # Validate adapter configuration
        self._validate_adapter()

        logger.info(
            "Initialized LLMEntityAdapter with provider=%s, model=%s, temperature=%s, max_tokens=%s",
            self.provider,
            self.model_name,
            self.temperature,
            self.max_tokens,
        )

    def _validate_adapter(self) -> None:
        """Validate LLM adapter configuration on initialization.

        Raises:
            DocpipeException: If adapter validation fails
        """
        from docpipe.exceptions.docpipe_exceptions import DocpipeException

        result = self.llm_adapter.validate()

        # Log warnings
        if result.get("warnings"):
            for warning in result["warnings"]:
                logger.warning(f"LLM adapter validation warning: {warning}")

        # Raise error if validation failed
        if not result.get("valid", True):
            errors = result.get("errors", ["Unknown validation error"])
            raise DocpipeException(
                message=f"LLM adapter validation failed: {'; '.join(errors)}",
                status_code=400,
            )

    def transform(self, *, table: pa.Table, metadata: dict[str, Any]) -> tuple[list[pa.Table], dict[str, Any]]:
        """Transform documents by extracting entities using LLM.

        This method delegates orchestration to EntityExtractionService while
        maintaining backward compatibility with the adapter interface.

        Args:
            table: PyArrow table with document information containing columns:
                - id: Document ID
                - name: Document name/filename
                - doc_content: Document text content
                - document_type: Document type for schema selection (optional)
            metadata: Metadata dictionary to update

        Returns:
            Tuple of (list of transformed tables, metadata dictionary)
        """
        # Create service instance with adapter and configuration
        service = EntityExtractionService(
            adapter=self,
            config={
                OperatorConstants.Columns.DOC_COLUMN: self.doc_column,
                OperatorConstants.Columns.OUTPUT_COLUMN: self.output_column,
                OperatorConstants.Config.EXPAND_EXTRACTED_DATA: self.expand_extracted_data,
                OperatorConstants.Columns.DOC_ID_HASH: self.doc_id_hash_column,
                OperatorConstants.Config.CUSTOM_SCHEMA: self.custom_schema,
                "common_log_arguments": self.common_log_arguments,
            },
            max_workers=self.max_workers,
            job_run_id=self.job_run_id,
            node_id=self.node_id,
            node_name=self.node_name,
            batch_id=self.batch_id,
        )

        # Delegate to service for orchestration
        return service.transform(table=table, metadata=metadata)

    def extract_entities_single(
        self, *, doc_id: str, doc_name: str, content: str | bytes, schema: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Extract entities from a single document using LLM.

        Args:
            doc_id: Document identifier
            doc_name: Document name
            content: Document content (text or bytes)
            schema: Optional schema dictionary for structured extraction

        Returns:
            Dictionary with extraction results:
            {
                "success": bool,              # Extraction success indicator
                "entities": dict,             # Extracted entities as dictionary
                "error": str | None           # Error message if failed
            }
        """
        # Convert bytes to string if needed
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="ignore")

        # Truncate content if too long
        if len(content) > self.max_doc_chars:
            logger.warning(
                "Document %s content truncated from %d to %d characters",
                doc_id,
                len(content),
                self.max_doc_chars,
            )
            content = content[: self.max_doc_chars]

        # Build prompt based on whether schema is provided
        if schema:
            system_prompt = OperatorConstants.ExtractionModes.ENTITY_EXTRACTION_SYSTEM_PROMPT
            user_prompt = f"""Document Content:
{content}

Schema Template:
{schema}

Extract entities matching the schema template above."""
        else:
            system_prompt = OperatorConstants.ExtractionModes.ENTITY_EXTRACTION_SCHEMA_FREE_SYSTEM_PROMPT
            user_prompt = f"""Document Content:
{content}

Extract all named entities and structured information from the document."""

        # Call LLM using chat interface for better provider compatibility
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            response = self.llm_adapter.chat(
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )

            # Parse JSON response
            entities = self._parse_json_response(response)
            logger.debug("Extracted %d entities from document %s", len(entities), doc_id)

            return {
                OperatorConstants.Extraction.SUCCESS: True,
                OperatorConstants.Misc.ENTITIES: entities,
                OperatorConstants.Extraction.ERROR: None,
            }

        except Exception as e:
            error_msg = f"Error extracting entities from document {doc_id}: {e}"
            logger.error(error_msg)
            return {
                OperatorConstants.Extraction.SUCCESS: False,
                OperatorConstants.Misc.ENTITIES: {},
                OperatorConstants.Extraction.ERROR: error_msg,
            }

    def _parse_json_response(self, response: str) -> dict[str, Any]:
        """Parse JSON response from LLM, handling markdown fences and errors.

        Args:
            response: Raw LLM response string

        Returns:
            Parsed JSON dictionary, or empty dict if parsing fails
        """
        from docpipe.exceptions.docpipe_exceptions import DocpipeException

        try:
            return parse_llm_json_response(
                response,
                log_on_error=True,
                log_level="warning",
            )
        except DocpipeException:
            # Return empty dict on parsing failure (maintains backward compatibility)
            return {}
