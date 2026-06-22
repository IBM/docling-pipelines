"""VectorDB module with Hexagonal Architecture.

This module provides vector database operations using a hexagonal architecture
pattern with ports and adapters for clean separation of concerns.

Architecture:
- Domain: Core business models (IndexRequest, IndexResult, QueryRequest, etc.)
- Ports: Interface definitions (VectorStorePort)
- Adapters: Concrete implementations (OpenSearchAdapter, MilvusAdapter)
- Application: Operator that orchestrates the workflow (VectorDBOperator)

Adapters are registered lazily to avoid importing optional dependencies
until they are actually needed.
"""

from .adapters.outbound.factories.vector_store_factory import VectorStoreFactory, register_vector_store
from .domain import DeleteRequest, DeleteResult, IndexInfo, IndexRequest, IndexResult, QueryRequest, QueryResult
from .ports.outbound.vector_store import VectorStorePort
from .vectordb_operator import VectorDBOperator

__all__ = [
    "DeleteRequest",
    "DeleteResult",
    "IndexInfo",
    "IndexRequest",
    "IndexResult",
    "QueryRequest",
    "QueryResult",
    "VectorDBOperator",
    "VectorStoreFactory",
    "VectorStorePort",
    "register_vector_store",
]
