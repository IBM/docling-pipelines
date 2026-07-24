"""Common interface for LLM inference operations.

This port defines the contract for all LLM inference adapters, enabling
pluggable LLM providers across the docpipe framework.
"""

from abc import ABC, abstractmethod
from typing import Any

from docpipe.core.constants.constants import LLMConstants


class LLMInferencePort(ABC):
    """Common interface for LLM inference operations.

    This port is implemented by provider-specific adapters (WatsonX, LiteLLM, etc.)
    to provide a unified interface for text generation across all operators.
    """

    @abstractmethod
    def chat(self, *, messages: list[dict[str, str]], **kwargs: Any) -> str:
        """Multi-turn chat completion.

        Args:
            messages: List of message dicts with 'role' and 'content' keys
            **kwargs: Provider-specific parameters (temperature, max_tokens, etc.)

        Returns:
            Generated text response

        Raises:
            Exception: Provider-specific errors
        """
        pass

    @abstractmethod
    def generate(self, *, prompt: str, **kwargs: Any) -> str:
        """Single-turn text generation.

        Args:
            prompt: Input prompt text
            **kwargs: Provider-specific parameters (temperature, max_tokens, etc.)

        Returns:
            Generated text response

        Raises:
            Exception: Provider-specific errors
        """
        pass

    def validate(self) -> dict[str, Any]:
        """Template method for validation.

        This method defines the validation algorithm structure by calling
        the hook method validate_inference(). Subclasses override the hook
        method to provide specific validation logic.

        Returns:
            Validation result dictionary from validate_inference()
        """
        return self.validate_inference()

    def validate_inference(self) -> dict[str, Any]:
        """Hook method for inference validation.

        Default implementation returns a valid result. Subclasses should
        override this method to provide specific validation logic.

        Returns:
            Dictionary with validation result:
                - valid: bool indicating if validation passed
                - context: str indicating validation context ("inference")
                - message: Optional str with additional information
        """
        return {
            LLMConstants.ValidationKeys.VALID: True,
            LLMConstants.ValidationKeys.CONTEXT: LLMConstants.ValidationContexts.INFERENCE,
        }
