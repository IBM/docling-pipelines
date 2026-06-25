"""Ollama LLM adapter for embedding generation."""

from docpipe.core.constants.constants import ServiceConstants
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.functional.embeddings.adapters.outbound.factories.llm_adapter_factory import (
    register_llm_adapter,
)
from docpipe.core.operators.functional.embeddings.ports.outbound.llm_service import LLMServicePort
from docpipe.exceptions.docpipe_exceptions import ExternalServiceError
from docpipe.integrations.ollama.client import OLLAMA_MODEL_TOKEN_LIMITS, InteractionMode, OllamaClient
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger(__name__)


@register_llm_adapter
class OllamaLLMAdapter(LLMServicePort):
    """Adapter for Ollama LLM embedding service.

    This adapter provides embeddings using locally-hosted Ollama models.
    Ollama supports various open-source models like llama2, mistral, granite, etc.

    Features:
        - Automatic dimension detection on first use
        - Dimension caching for performance
        - Comprehensive error handling
    """

    ADAPTER_NAME = "ollama"
    ADAPTER_DISPLAY_NAME = "Ollama"

    def __init__(self, model_name: str, **adapter_config):
        """Initialize Ollama adapter.

        Args:
            model_name: Ollama model name (e.g., 'granite4', 'llama3.2', 'nomic-embed-text')
            **adapter_config: Additional configuration:
                - host: Ollama server URL (optional, defaults to OLLAMA_HOST env var or http://localhost:11434)
                - max_concurrent_requests: Maximum concurrent requests for batch embeddings (default: 8)
                - timeout: Timeout in seconds for API calls (optional)
                - validate_model: Whether to validate model availability on initialization (default: true)
        """
        self.model_name = model_name

        # Extract parameters from adapter_config
        host = adapter_config.get("host")
        max_concurrent_requests = adapter_config.get(
            OperatorConstants.Config.MAX_CONCURRENT_REQUESTS, ServiceConstants.DEFAULT_OLLAMA_MAX_CONCURRENT_REQUESTS
        )
        timeout = adapter_config.get("timeout")
        validate_model = adapter_config.get("validate_model", True)

        self.client = OllamaClient(
            model_name=model_name,
            host=host,
            mode=InteractionMode.EMBEDDINGS,
            max_concurrent_requests=max_concurrent_requests,
            timeout=timeout,
            validate_model=validate_model,
        )
        self._cached_dimension: int | None = None

    def generate_embeddings(self, text: str) -> list[float]:
        """Generate embeddings using Ollama.

        Args:
            text: Input text to embed

        Returns:
            List of floats representing the embedding vector

        Raises:
            ValueError: If embeddings are invalid or empty
        """
        embeddings = self.client.generate_embeddings(text)

        if not embeddings or not isinstance(embeddings, list):
            raise ValueError(f"Invalid embeddings from Ollama model '{self.model_name}': {embeddings}")

        return embeddings

    def generate_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts using concurrent requests.

        Args:
            texts: List of input texts to embed

        Returns:
            List of embedding vectors, one per input text

        Raises:
            ValueError: If embeddings are invalid or empty
        """
        embeddings_list = self.client.generate_embeddings_batch(texts)

        # Validate all embeddings
        for i, embeddings in enumerate(embeddings_list):
            if not embeddings or not isinstance(embeddings, list):
                raise ValueError(f"Invalid embeddings from Ollama model '{self.model_name}' at index {i}: {embeddings}")

        return embeddings_list

    def get_model_token_limit(self) -> int:
        """Get token limit for Ollama model.

        Returns:
            Maximum token limit for the model (default: 4096)
        """
        return OLLAMA_MODEL_TOKEN_LIMITS.get(self.model_name, 4096)

    def _detect_dimension(self) -> int:
        """Detect embedding dimension by generating a test embedding.

        This method generates a single test embedding to determine the
        dimension of the model's output vectors. The result is cached
        for subsequent calls.

        Returns:
            Embedding dimension (number of values in embedding vector)

        Raises:
            ExternalServiceError: If Ollama server is not available or
                model is not found
            RuntimeError: If dimension detection fails
        """
        test_text = "dimension detection"

        try:
            logger.debug(f"Detecting embedding dimension for Ollama model '{self.model_name}'")

            # Generate test embedding
            result = self.client.generate_embeddings(test_text)

            if not result or not isinstance(result, list):
                raise RuntimeError(f"Invalid embedding result from Ollama model '{self.model_name}': {result}")

            dimension = len(result)
            logger.info(f"Detected embedding dimension for Ollama model '{self.model_name}': {dimension}")

            return dimension

        except Exception as e:
            error_msg = f"Failed to detect embedding dimension for Ollama model '{self.model_name}': {e}"
            logger.error(error_msg)

            # Provide helpful error messages
            if "connection" in str(e).lower():
                raise ExternalServiceError(
                    f"{error_msg}\n"
                    f"Ensure Ollama server is running: ollama serve\n"
                    f"Check server status: curl {ServiceConstants.DEFAULT_OLLAMA_HOST}/api/tags"
                ) from e
            elif "not found" in str(e).lower():
                raise ExternalServiceError(
                    f"{error_msg}\nModel may not be available. Pull it with: ollama pull {self.model_name}"
                ) from e
            else:
                raise RuntimeError(error_msg) from e

    def get_embedding_dimension(self) -> int | None:
        """Get embedding dimension for Ollama model.

        Automatically detects dimension on first call by generating a test
        embedding. The result is cached for subsequent calls to avoid
        repeated API calls.

        Returns:
            Embedding dimension if successfully detected, None if detection fails

        Note:
            First call incurs a one-time cost of ~100-200ms for test embedding.
            Subsequent calls return the cached value instantly.
        """
        if self._cached_dimension is None:
            try:
                self._cached_dimension = self._detect_dimension()
            except Exception as e:
                logger.warning(
                    f"Could not detect embedding dimension for Ollama model '{self.model_name}': {e}. Returning None."
                )
                return None

        return self._cached_dimension
