"""Entity extraction adapters.

Importing this package triggers the ``@register_entity_extraction_adapter`` decorators
on all adapter modules, populating ``EntityExtractionAdapterFactory._registry``.
"""

from .docling_entity_adapter import DoclingEntityAdapter
from .litellm_entity_adapter import LiteLLMEntityAdapter
from .llm_entity_adapter import LLMEntityAdapter
from .watsonx_entity_adapter import WatsonxEntityAdapter

__all__ = ["DoclingEntityAdapter", "LLMEntityAdapter", "LiteLLMEntityAdapter", "WatsonxEntityAdapter"]
