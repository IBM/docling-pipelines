"""Common interface for LLM embedding generation.

This port defines the contract for all embedding adapters, enabling
pluggable embedding providers across the datasift framework.
"""

from abc import ABC, abstractmethod


class LLMEmbeddingPort(ABC):
    """Common interface for embedding generation.

    This port is implemented by provider-specific adapters (WatsonX, LiteLLM, HuggingFace, etc.)
    to provide a unified interface for generating embeddings across all operators.
    """

    @abstractmethod
    def generate_embeddings(self, *, text: str) -> list[float]:
        """Generate embeddings for single text.

        Args:
            text: Input text to embed

        Returns:
            List of embedding values (floats)

        Raises:
            Exception: Provider-specific errors
        """
        pass

    @abstractmethod
    def generate_embeddings_batch(self, *, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of input texts to embed

        Returns:
            List of embedding lists, one per input text

        Raises:
            Exception: Provider-specific errors
        """
        pass

    @abstractmethod
    def get_embedding_dimension(self) -> int:
        """Get embedding dimension for this model.

        Returns:
            Dimension of embedding vectors

        Raises:
            Exception: Provider-specific errors
        """
        pass
