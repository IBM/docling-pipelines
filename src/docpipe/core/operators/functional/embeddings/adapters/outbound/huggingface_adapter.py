"""HuggingFace LLM adapter for embedding generation."""

from docpipe.core.constants.constants import ServiceConstants
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.functional.embeddings.adapters.outbound.factories.llm_adapter_factory import (
    register_llm_adapter,
)
from docpipe.core.operators.functional.embeddings.ports.outbound.llm_service import LLMServicePort
from docpipe.integrations.huggingface.client import HuggingFaceLLMClient


@register_llm_adapter
class HuggingFaceLLMAdapter(LLMServicePort):
    """Adapter for HuggingFace LLM embedding service.

    This adapter provides embeddings using HuggingFace models, supporting both
    local inference and API-based inference.
    """

    ADAPTER_NAME = "huggingface"
    ADAPTER_DISPLAY_NAME = "HuggingFace"

    def __init__(self, model_name: str, **adapter_config):
        """Initialize HuggingFace adapter.

        Args:
            model_name: HuggingFace model name (e.g., 'sentence-transformers/all-MiniLM-L6-v2')
            **adapter_config: Additional configuration:
                - use_local: Whether to use local inference (default: True)
                - api_token: HuggingFace API token for API inference
                - device: Device for local inference ('cpu', 'cuda', etc.)
                - batch_size: Number of texts to process in each batch (default: 32)
        """
        self.model_name = model_name

        # Extract parameters to avoid duplication when passing **adapter_config
        use_local = adapter_config.pop("use_local", True)
        api_token = adapter_config.pop("api_token", None)
        device = adapter_config.pop("device", None)
        batch_size = adapter_config.pop(
            OperatorConstants.Config.BATCH_SIZE, ServiceConstants.DEFAULT_EMBEDDINGS_BATCH_SIZE
        )

        self.client = HuggingFaceLLMClient(
            model_name=model_name,
            use_local=use_local,
            api_token=api_token,
            device=device,
            batch_size=batch_size,
            **adapter_config,
        )

    def generate_embeddings(self, text: str) -> list[float]:
        """Generate embeddings using HuggingFace.

        Args:
            text: Input text to embed

        Returns:
            List of floats representing the embedding vector
        """
        return self.client.generate_embeddings(text)

    def generate_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts in batches.

        Args:
            texts: List of input texts to embed

        Returns:
            List of embedding vectors, one per input text
        """
        return self.client.generate_embeddings_batch(texts)

    def get_model_token_limit(self) -> int:
        """Get token limit for HuggingFace model.

        Returns:
            Maximum token limit for the model
        """
        return HuggingFaceLLMClient.get_model_token_limit(self.model_name)

    def get_embedding_dimension(self) -> int | None:
        """Get embedding dimension for HuggingFace model.

        Returns:
            Embedding dimension if known, None otherwise
        """
        try:
            return HuggingFaceLLMClient.get_embedding_dimension(self.model_name)
        except Exception:
            return None
