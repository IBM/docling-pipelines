"""Ollama LLM adapter for embedding generation."""

from common.clients.ollama_client import OLLAMA_MODEL_TOKEN_LIMITS, InteractionMode, OllamaClient
from common.exceptions.datasift_exceptions import ExternalServiceError
from common.util.infrastructure.logging import get_logger
from core.operators.functional.embeddings.adapters.outbound.factories.llm_adapter_factory import (
    register_llm_adapter,
)
from core.operators.functional.embeddings.ports.outbound.llm_service import LLMServicePort

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
            **adapter_config: Additional configuration (currently unused for Ollama)
        """
        self.model_name = model_name
        self.client = OllamaClient(model=model_name, mode=InteractionMode.EMBEDDINGS)
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

    def generate_embeddings_batch(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        """Generate embeddings for multiple texts using concurrent requests.

        Args:
            texts: List of input texts to embed
            batch_size: Number of concurrent requests (default: 32)

        Returns:
            List of embedding vectors, one per input text

        Raises:
            ValueError: If embeddings are invalid or empty
        """
        embeddings_list = self.client.generate_embeddings_batch(texts, batch_size)

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
                    f"Check server status: curl http://localhost:11434/api/tags"
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


# Made with Bob
