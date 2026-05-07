"""Document classification adapters.

This module imports all adapters to trigger their registration with the factory.
"""

from datasift.core.operators.quality.classification.adapters.outbound.litellm_adapter import (
    LiteLLMClassificationAdapter,
)
from datasift.core.operators.quality.classification.adapters.outbound.ollama_adapter import (
    OllamaClassificationAdapter,
)
from datasift.core.operators.quality.classification.adapters.outbound.watsonx_adapter import (
    WatsonxClassificationAdapter,
)

__all__ = [
    "LiteLLMClassificationAdapter",
    "OllamaClassificationAdapter",
    "WatsonxClassificationAdapter",
]
