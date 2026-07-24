"""Common interface for LLM embedding generation.

This port defines the contract for all embedding adapters, enabling
pluggable embedding providers across the docpipe framework.
"""

from abc import ABC, abstractmethod
from typing import Any

from docpipe.core.constants.constants import LLMConstants


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

    def validate(self) -> dict[str, Any]:
        """Template method for validation.

        This method defines the validation algorithm structure by calling
        the hook method validate_embedding(). Subclasses override the hook
        method to provide specific validation logic.

        Returns:
            Validation result dictionary from validate_embedding()
        """
        return self.validate_embedding()

    def validate_embedding(self) -> dict[str, Any]:
        """Hook method for embedding validation.

        Default implementation returns a valid result. Subclasses should
        override this method to provide specific validation logic.

        Returns:
            Dictionary with validation result:
                - valid: bool indicating if validation passed
                - context: str indicating validation context ("embedding")
                - message: Optional str with additional information
        """
        return {
            LLMConstants.ValidationKeys.VALID: True,
            LLMConstants.ValidationKeys.CONTEXT: LLMConstants.ValidationContexts.EMBEDDING,
        }
