"""Unified LiteLLM adapter for inference and embeddings.

This adapter consolidates all LiteLLM capabilities into a single class,
providing a unified interface for:
- LLM inference (chat and text generation)
- Embedding generation

Supports 100+ providers including OpenAI, Anthropic, Cohere, and Ollama.
"""

from typing import Any

from datasift.core.ports.llm_embedding_port import LLMEmbeddingPort
from datasift.core.ports.llm_inference_port import LLMInferencePort
from datasift.integrations.litellm.client import LiteLLMLLMClient


class LiteLLMAdapter(LLMInferencePort, LLMEmbeddingPort):
    """Unified LiteLLM adapter for all LLM capabilities.

    This adapter provides a single interface for LiteLLM operations including
    inference and embeddings across 100+ providers.

    Supports multiple providers:
    - Native LiteLLM providers (OpenAI, Anthropic, Cohere, etc.)
    - Ollama via OpenAI-compatible API (api_base: http://localhost:11434/v1)
    - HuggingFace models via LiteLLM integration

    Attributes:
        client: LiteLLM client instance
        model_name: Default model name (can be overridden per method call)
    """

    def __init__(
        self,
        *,
        model_name: str,
        api_key: str | None = None,
        api_base: str | None = None,
        **kwargs: Any,
    ):
        """Initialize unified LiteLLM adapter.

        Args:
            model_name: Model identifier with optional provider prefix
                - OpenAI: "gpt-4", "text-embedding-ada-002"
                - Ollama: "openai/llama2", "openai/nomic-embed-text"
                - HuggingFace: "huggingface/sentence-transformers/all-MiniLM-L6-v2"
            api_key: API key for the provider (use "ollama" for Ollama)
            api_base: API base URL (e.g., "http://localhost:11434/v1" for Ollama)
            **kwargs: Additional LiteLLM client parameters

        Examples:
            # OpenAI
            adapter = LiteLLMAdapter(
                model_name="gpt-4",
                api_key="sk-..."  # pragma: allowlist secret
            )

            # Ollama
            adapter = LiteLLMAdapter(
                model_name="openai/llama2",
                api_key="ollama",  # pragma: allowlist secret
                api_base="http://localhost:11434/v1"
            )

            # HuggingFace
            adapter = LiteLLMAdapter(
                model_name="huggingface/sentence-transformers/all-MiniLM-L6-v2",
                api_key="your-hf-api-key"  # pragma: allowlist secret
            )
        """
        self.client = LiteLLMLLMClient(
            model_name=model_name,
            api_key=api_key,
            api_base=api_base,
        )
        self.model_name = model_name
        self._dimension: int | None = None

    # ==================== Inference Methods ====================

    def chat(
        self,
        *,
        model_name: str | None = None,
        messages: list[dict[str, str]],
        response_format: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> str:
        """Multi-turn chat completion using LiteLLM.

        Args:
            model_name: Model identifier (uses default if not provided)
            messages: List of message dicts with 'role' and 'content' keys
            response_format: Optional response format specification (e.g., {"type": "json_object"})
            **kwargs: LiteLLM-specific parameters (temperature, max_tokens, etc.)

        Returns:
            Generated text response

        Raises:
            Exception: LiteLLM client errors

        Examples:
            # Regular chat
            response = adapter.chat(messages=[
                {"role": "user", "content": "Hello"}
            ])

            # JSON response format
            response = adapter.chat(
                messages=[{"role": "user", "content": "List 3 colors"}],
                response_format={"type": "json_object"}
            )
        """
        # Add response_format to kwargs if provided
        if response_format:
            kwargs["response_format"] = response_format

        # Use provided model_name or fall back to default
        effective_model = model_name or self.model_name
        if effective_model and effective_model != self.client.model_name:
            self.client.model_name = effective_model

        return self.client.chat(messages=messages, **kwargs)

    def generate(
        self,
        *,
        model_name: str | None = None,
        prompt: str,
        response_format: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> str:
        """Single-turn text generation using LiteLLM.

        Args:
            model_name: Model identifier (uses default if not provided)
            prompt: Input prompt text
            response_format: Optional response format specification (e.g., {"type": "json_object"})
            **kwargs: LiteLLM-specific parameters (temperature, max_tokens, etc.)

        Returns:
            Generated text response

        Raises:
            Exception: LiteLLM client errors

        Examples:
            # Regular generation
            response = adapter.generate(prompt="Write a haiku")

            # JSON response format
            response = adapter.generate(
                prompt="List 3 colors in JSON",
                response_format={"type": "json_object"}
            )
        """
        # Add response_format to kwargs if provided
        if response_format:
            kwargs["response_format"] = response_format

        # Use provided model_name or fall back to default
        effective_model = model_name or self.model_name
        if effective_model and effective_model != self.client.model_name:
            self.client.model_name = effective_model

        return self.client.generate(prompt=prompt, **kwargs)

    # ==================== Embedding Methods ====================

    def generate_embeddings(
        self,
        *,
        model_name: str | None = None,
        text: str,
        **kwargs: Any,
    ) -> list[float]:
        """Generate embeddings for single text using LiteLLM.

        Args:
            model_name: Embedding model identifier (uses default if not provided)
            text: Input text to embed
            **kwargs: Additional LiteLLM parameters

        Returns:
            List of embedding values (floats)

        Raises:
            Exception: LiteLLM client errors

        Examples:
            # OpenAI embeddings
            embeddings = adapter.generate_embeddings(
                model_name="text-embedding-ada-002",
                text="Hello world"
            )

            # Ollama embeddings
            embeddings = adapter.generate_embeddings(
                model_name="openai/nomic-embed-text",
                text="Hello world"
            )
        """
        # Use provided model_name or fall back to default
        effective_model = model_name or self.model_name
        if effective_model and effective_model != self.client.model_name:
            self.client.model_name = effective_model

        return self.client.generate_embeddings(text=text)

    def generate_embeddings_batch(
        self,
        *,
        model_name: str | None = None,
        texts: list[str],
        **kwargs: Any,
    ) -> list[list[float]]:
        """Generate embeddings for multiple texts using LiteLLM.

        Args:
            model_name: Embedding model identifier (uses default if not provided)
            texts: List of input texts to embed
            **kwargs: Additional LiteLLM parameters

        Returns:
            List of embedding lists, one per input text

        Raises:
            Exception: LiteLLM client errors

        Examples:
            embeddings = adapter.generate_embeddings_batch(
                model_name="text-embedding-ada-002",
                texts=["Hello", "World"]
            )
        """
        # Use provided model_name or fall back to default
        effective_model = model_name or self.model_name
        if effective_model and effective_model != self.client.model_name:
            self.client.model_name = effective_model

        return self.client.generate_embeddings_batch(texts=texts)

    def get_embedding_dimension(self, *, model_name: str | None = None) -> int:
        """Get embedding dimension for LiteLLM model.

        Detects dimension by generating a sample embedding if not cached.

        Args:
            model_name: Embedding model identifier (uses default if not provided)

        Returns:
            Dimension of embedding vectors

        Raises:
            Exception: LiteLLM client errors
        """
        if self._dimension is None:
            # Detect dimension by generating sample embedding
            sample = self.generate_embeddings(model_name=model_name, text="test")
            self._dimension = len(sample)
        return self._dimension
