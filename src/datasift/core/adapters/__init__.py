"""Core adapters module for LLM operations.

This module provides unified adapters for LLM operations across multiple providers:
- WatsonX: IBM watsonx.ai models
- LiteLLM: Unified interface for 100+ LLM providers

Each provider has a consolidated adapter implementing multiple port interfaces:
- LLMInferencePort (chat, generate)
- LLMEmbeddingPort (generate_embeddings)
- TextDetectionPort (detect) - WatsonX only
"""

from datasift.core.adapters.litellm import LiteLLMAdapter
from datasift.core.adapters.llm_adapter_factory import LLMAdapterFactory
from datasift.core.adapters.watsonx import WatsonXAdapter

__all__ = [
    "LLMAdapterFactory",
    "LiteLLMAdapter",
    "WatsonXAdapter",
]
