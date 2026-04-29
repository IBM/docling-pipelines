"""PII and HAP detection adapters.

This module imports all adapters to trigger their registration with the factory.
"""

# Import adapters to trigger registration
from .litellm_adapter import LiteLLMAdapter
from .ollama_adapter import OllamaAdapter
from .watsonx_adapter import WatsonXAdapter

__all__ = [
    "LiteLLMAdapter",
    "OllamaAdapter",
    "WatsonXAdapter",
]
