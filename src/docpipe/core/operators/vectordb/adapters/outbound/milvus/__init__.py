"""Milvus vector database adapter components.

Components are loaded lazily to avoid importing pymilvus until actually needed.

Usage:
    Do not import components directly from this module. Instead, use the
    VectorStoreFactory to create Milvus adapter instances:

    from docpipe.core.operators.vectordb.adapters.outbound.factories.vector_store_factory import VectorStoreFactory

    # Create Milvus adapter (triggers lazy loading)
    adapter = VectorStoreFactory.create("milvus", host="localhost", port=19530)

Note:
    This module intentionally does not export any classes to prevent eager
    loading of pymilvus. All Milvus components are loaded on-demand when the
    adapter is first instantiated through the factory.
"""

# Intentionally empty - components should be accessed via VectorStoreFactory
__all__: list[str] = []
