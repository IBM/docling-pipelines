"""Embeddings module with Hexagonal Architecture.

This module provides embedding generation capabilities using a hexagonal architecture
pattern with ports and adapters for clean separation of concerns.

Architecture:
- Domain: Core business models (EmbeddingRequest, EmbeddingResponse, ModelInfo)
- Ports: Interface definitions (LLMServicePort)
- Adapters: Concrete implementations (OllamaLLMAdapter, HuggingFaceLLMAdapter, LiteLLMLLMAdapter)
- Application: Operator that orchestrates the workflow (EmbeddingsOperator)
"""

from .adapters.outbound import HuggingFaceLLMAdapter, LiteLLMLLMAdapter, OllamaLLMAdapter
from .adapters.outbound.factories.llm_adapter_factory import LLMAdapterFactory
from .domain import EmbeddingRequest, EmbeddingResponse, ModelInfo
from .embeddings_operator import EmbeddingsOperator
from .ports.outbound.llm_service import LLMServicePort

__all__ = [
    # Domain Models
    "EmbeddingRequest",
    "EmbeddingResponse",
    # Operator
    "EmbeddingsOperator",
    # Adapters
    "HuggingFaceLLMAdapter",
    # Factory
    "LLMAdapterFactory",
    # Port
    "LLMServicePort",
    # Adapters
    "LiteLLMLLMAdapter",
    # Domain Models
    "ModelInfo",
    # Adapters
    "OllamaLLMAdapter",
]
