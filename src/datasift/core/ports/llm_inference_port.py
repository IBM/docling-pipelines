"""Common interface for LLM inference operations.

This port defines the contract for all LLM inference adapters, enabling
pluggable LLM providers across the datasift framework.
"""

from abc import ABC, abstractmethod
from typing import Any


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
