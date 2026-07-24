"""Entity extraction adapters."""

from .docling_entity_adapter import DoclingEntityAdapter
from .llm_entity_adapter import LLMEntityAdapter

__all__ = ["DoclingEntityAdapter", "LLMEntityAdapter"]
