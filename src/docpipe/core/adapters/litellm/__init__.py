"""LiteLLM adapter module.

This module provides the unified LiteLLM adapter for inference and embeddings
across 100+ providers including OpenAI, Anthropic, Cohere, and Ollama.
"""

from docpipe.core.adapters.litellm.litellm_adapter import LiteLLMAdapter

__all__ = ["LiteLLMAdapter"]
