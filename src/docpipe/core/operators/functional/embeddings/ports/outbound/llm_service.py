"""Port interface for LLM embedding services.

This port defines the contract that all embedding service adapters must implement.
It follows the hexagonal architecture pattern, keeping the interface minimal and
focused on business logic only.
"""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class LLMServicePort(ABC):
    """Port interface for LLM embedding services.

    This interface defines the contract for embedding generation services.
    Adapters implementing this port handle provider-specific details while
    the operator depends only on this abstraction.

    Attributes:
        ADAPTER_NAME: Unique identifier for the adapter (e.g., 'ollama')
        ADAPTER_DISPLAY_NAME: Human-readable name for UI display
    """

    ADAPTER_NAME: str
    ADAPTER_DISPLAY_NAME: str

    def __init__(self, model_name: str, **kwargs: Any) -> None:
        """Initialize the LLM service adapter.

        Args:
            model_name: Name of the model to use
            **kwargs: Additional adapter-specific configuration
        """
        self.model_name = model_name

    @staticmethod
    @abstractmethod
    def get_config_schema() -> type[BaseModel]:
        """Return the Pydantic config model class for this adapter."""
        ...

    @abstractmethod
    def generate_embeddings(self, text: str) -> list[float]:
        """Generate embedding vector for text.

        Args:
            text: Input text to generate embeddings for

        Returns:
            List of floats representing the embedding vector

        Raises:
            Exception: If embedding generation fails
        """
        ...

    @abstractmethod
    def generate_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embedding vectors for multiple texts with provider-optimized processing.

        This method enables efficient processing of multiple texts using provider-specific
        optimization strategies (30-50% faster depending on provider).

        Batch size and concurrency settings are configured per-provider through
        adapter initialization (via provider_config), not as method parameters.

        Args:
            texts: List of input texts to generate embeddings for

        Returns:
            List of embedding vectors, one per input text

        Raises:
            Exception: If embedding generation fails
        """
        ...

    @abstractmethod
    def get_model_token_limit(self) -> int:
        """Get maximum token limit for the model.

        Returns:
            Maximum number of tokens the model can process
        """
        ...

    def get_embedding_dimension(self) -> int | None:
        """Get embedding vector dimension.

        This is optional and may return None if the dimension is unknown
        or cannot be determined without making an API call.

        Returns:
            Dimension of embedding vectors, or None if unknown
        """
        return None
