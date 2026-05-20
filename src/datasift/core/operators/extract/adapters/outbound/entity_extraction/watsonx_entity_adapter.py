"""WatsonX entity extraction adapter.

This adapter implements entity extraction using IBM watsonx.ai LLM.
It supports both schema-based and schema-free extraction modes.
"""

from typing import Any

from datasift.core.constants import OperatorConstants
from datasift.core.operators.extract.ports.outbound.entity_extraction import EntityExtractionPort
from datasift.integrations.watsonx.client import WatsonXClient
from datasift.utils.infrastructure.logging import get_logger

logger = get_logger(__name__)


class WatsonXEntityAdapter(EntityExtractionPort):
    """WatsonX-based entity extraction adapter.

    This adapter uses IBM watsonx.ai LLM to extract structured entities
    from document text. It supports both schema-based extraction (with a predefined
    schema) and schema-free extraction (discovering entities automatically).

    Attributes:
        ADAPTER_NAME: Short identifier "watsonx"
        ADAPTER_DISPLAY_NAME: Display name "IBM watsonx"
        model_name: WatsonX model to use (e.g., "ibm/granite-13b-chat-v2")
        api_base: WatsonX API base URL
        container_kind: Container type ("project" or "space")
        temperature: LLM sampling temperature (0.0 = deterministic)
        max_tokens: Maximum tokens for LLM response
        max_doc_chars: Maximum document characters to send to LLM
        timeout: Request timeout in seconds
        watsonx_client: WatsonXClient instance for LLM communication

    Security Note:
        api_key and container_id MUST be set via environment variables:
        - WATSONX_API_KEY: IBM Cloud API key
        - WATSONX_CONTAINER_ID: Project or space ID
    """

    ADAPTER_NAME = "watsonx"
    ADAPTER_DISPLAY_NAME = "IBM watsonx"

    def __init__(self, *, config: dict[str, Any]) -> None:
        """Initialize the adapter with configuration.

        Args:
            config: Configuration dictionary
        """
        super().__init__(config=config)

    def validate(self, *, config: dict[str, Any]) -> None:
        """Validate WatsonX-specific configuration.

        Args:
            config: Configuration dictionary to validate

        Raises:
            ValueError: If required model_name is missing or blank
        """
        model_name = config.get(OperatorConstants.Config.MODEL_NAME)
        if not isinstance(model_name, str) or not model_name.strip():
            raise ValueError(
                f"'{OperatorConstants.ExtractionModes.ENTITY_MODEL_NAME}' is required when "
                f"entity extraction mode is '{OperatorConstants.ExtractionModes.ENTITY_MODE_WATSONX}'"
            )

        # Validate api_base if provided
        api_base = config.get(OperatorConstants.Config.API_BASE)
        if api_base and not isinstance(api_base, str):
            raise ValueError("WatsonXEntityAdapter 'api_base' must be a string")

        # Validate container_kind if provided
        container_kind = config.get(OperatorConstants.Config.CONTAINER_KIND)
        if container_kind and container_kind not in ("project", "space"):
            raise ValueError("WatsonXEntityAdapter 'container_kind' must be 'project' or 'space'")

        # Validate numeric parameters if present
        for param in [
            OperatorConstants.LLM.TEMPERATURE,
            OperatorConstants.LLM.MAX_TOKENS,
            OperatorConstants.LLM.MAX_DOC_CHARS,
            OperatorConstants.Config.REQUEST_TIMEOUT,
        ]:
            value = config.get(param)
            if value is not None and not isinstance(value, (int, float)):
                raise ValueError(f"WatsonXEntityAdapter '{param}' must be a number")

        super().validate(config=config)

    def _init_adapter_config(self, *, config: dict[str, Any]) -> None:
        """Initialize WatsonX-specific configuration.

        Args:
            config: Configuration dictionary containing:
                - model_name: WatsonX model name (required)
                - api_key: IBM Cloud API key (optional, falls back to env var)
                - container_id: Project or space ID (optional, falls back to env var)
                - api_base: API base URL (optional, falls back to env var)
                - container_kind: Container type (optional, falls back to env var)
                - temperature: Sampling temperature (default: 0.0)
                - max_tokens: Maximum response tokens (default: 4096)
                - max_doc_chars: Maximum document characters (default: 8000)
                - request_timeout: Request timeout in seconds (default: 120)
        """
        self.model_name: str = str(config.get(OperatorConstants.Config.MODEL_NAME))
        self.api_key: str | None = config.get(OperatorConstants.Config.API_KEY)
        self.container_id: str | None = config.get(OperatorConstants.Config.CONTAINER_ID)
        self.api_base: str | None = config.get(OperatorConstants.Config.API_BASE)
        self.container_kind: str | None = config.get(OperatorConstants.Config.CONTAINER_KIND)
        self.temperature = float(config.get(OperatorConstants.LLM.TEMPERATURE, 0.0))
        self.max_tokens = int(config.get(OperatorConstants.LLM.MAX_TOKENS, 4096))
        self.max_doc_chars = int(config.get(OperatorConstants.LLM.MAX_DOC_CHARS, 8000))
        self.timeout = int(config.get(OperatorConstants.Config.REQUEST_TIMEOUT, 120))

        # Initialize WatsonX client
        self.watsonx_client = WatsonXClient(
            model_name=self.model_name,
            api_key=self.api_key,
            container_id=self.container_id,
            api_base=self.api_base,
            container_kind=self.container_kind,
            timeout=self.timeout,
        )

        logger.info(
            "Initialized WatsonXEntityAdapter with model=%s, temperature=%s, max_tokens=%s",
            self.model_name,
            self.temperature,
            self.max_tokens,
        )

    def extract_entities_single(
        self, *, doc_id: str, doc_name: str, content: str | bytes, schema: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Extract entities from a single document using WatsonX.

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

            # Call WatsonX client
            response = self.watsonx_client.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )

            # Parse JSON response
            entities = self._parse_llm_json(raw_response=response)

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
