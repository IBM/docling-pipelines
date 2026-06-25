"""Outbound adapters for vector database operations.

Adapters are registered lazily to avoid importing optional dependencies
(like pymilvus) until they are actually needed.

Usage:
    Do not import adapters directly from this module. Instead, use the
    VectorStoreFactory to create adapter instances:

    from docpipe.core.operators.vectordb.adapters.outbound.factories.vector_store_factory import VectorStoreFactory

    # Create an adapter instance (triggers lazy loading if needed)
    adapter = VectorStoreFactory.create("opensearch", host="localhost", port=9200)

    # List available adapters
    adapters = VectorStoreFactory.list_adapters()  # ['opensearch', 'milvus']

Note:
    Lazy adapter registration is handled in vectordb_operator.py.
    This module intentionally does not export adapter classes to prevent
    eager loading of optional dependencies.
"""

# Intentionally empty - adapters should be accessed via VectorStoreFactory
__all__: list[str] = []
