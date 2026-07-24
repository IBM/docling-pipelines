"""Outbound adapters for embeddings.

This module imports all adapters to trigger their auto-registration
with the LLMAdapterFactory via the @register_llm_adapter decorator.
"""

# Import adapters to trigger registration
from .huggingface_adapter import HuggingFaceLLMAdapter
from .litellm_adapter import LiteLLMLLMAdapter
from .ollama_adapter import OllamaLLMAdapter
from .watsonx_adapter import WatsonxLLMAdapter

__all__ = [
    "HuggingFaceLLMAdapter",
    "LiteLLMLLMAdapter",
    "OllamaLLMAdapter",
    "WatsonxLLMAdapter",
]
