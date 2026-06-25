# VectorDB Operator - Hexagonal Architecture

## Overview

The VectorDB operator implements a hexagonal architecture (ports and adapters pattern) to provide a clean separation between domain logic and infrastructure concerns. This design allows easy integration of multiple vector database providers without modifying the core operator logic.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     VectorDBOperator                         │
│                   (Application Layer)                        │
│  - Orchestrates vector database operations                   │
│  - Depends on VectorStorePort interface                      │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ uses
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                   VectorStorePort                            │
│                  (Port Interface)                            │
│  - index_documents()                                         │
│  - query_by_doc_names()                                      │
│  - delete_documents_by_ids()                                 │
│  - create_index()                                            │
│  - refresh_index()                                           │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ implemented by
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              OpenSearchAdapter                               │
│           (Outbound Adapter)                                 │
│  - Wraps OpenSearchClient                                    │
│  - Wraps OpenSearchIndexManager                              │
│  - Wraps OpenSearchBatchProcessor                            │
└─────────────────────────────────────────────────────────────┘
```

## Components

### Domain Layer (`domain/models.py`)

Defines pure business models without infrastructure dependencies:

- `IndexRequest` - Request to index documents
- `IndexResult` - Result of indexing operation
- `QueryRequest` - Request to query documents
- `QueryResult` - Result of query operation
- `DeleteRequest` - Request to delete documents
- `DeleteResult` - Result of delete operation
- `IndexInfo` - Information about an index

### Port Layer (`ports/outbound/vector_store.py`)

Defines the interface contract that all vector database adapters must implement:

```python
class VectorStorePort(ABC):
    @abstractmethod
    def index_documents(self, request: IndexRequest) -> IndexResult:
        """Index documents into the vector store"""
        
    @abstractmethod
    def query_by_doc_names(self, request: QueryRequest) -> QueryResult:
        """Query documents by their names/IDs"""
        
    @abstractmethod
    def delete_documents_by_ids(self, request: DeleteRequest) -> DeleteResult:
        """Delete documents by their IDs"""
```

### Adapter Layer (`adapters/outbound/`)

Concrete implementations of the port interface for specific vector databases:

- **OpenSearchAdapter** - Implements VectorStorePort for OpenSearch
- **Factory** - Creates adapters using decorator-based registration

### Application Layer (`vectordb_operator.py`)

The main operator that:
1. Accepts configuration with `provider` parameter
2. Uses VectorStoreFactory to create the appropriate adapter
3. Delegates all vector database operations to the adapter
4. Transforms PyArrow tables to/from domain models

## Usage

### Basic Configuration

```python
from docpipe.core.operators.vectordb import VectorDBOperator

config = {
    "provider": "opensearch",  # Selects OpenSearch adapter
    "index_name": "my_index",
    "vector_dimension": 384,
    "provider_config": {
        "host": "localhost",
        "port": 9200,
        "engine": "faiss",
        "algorithm": "hnsw",
        "space_type": "l2",
        # ... other OpenSearch-specific config
    }
}

operator = VectorDBOperator(config)
```

### Indexing Documents

```python
import pyarrow as pa

table = pa.table({
    "doc_id_hash": ["doc1", "doc2"],
    "content": ["Document 1", "Document 2"],
    "embeddings": [[0.1, 0.2, ...], [0.3, 0.4, ...]]
})

result_tables, metadata = operator.transform(table)
print(f"Indexed {metadata['processed_docs']} documents")
```

### Querying Documents

```python
docs = operator.query_by_doc_names(["doc1", "doc2"])
for doc in docs:
    print(doc["content"])
```

### Deleting Documents

```python
success_count, failed_count = operator.delete_documents_by_ids(["doc1", "doc2"])
print(f"Deleted {success_count} documents")
```

## Adding a New Vector Database

To add support for a new vector database (e.g., Pinecone, Weaviate):

### 1. Create an Adapter

```python
# adapters/outbound/pinecone/adapter.py
from docpipe.core.operators.vectordb.ports.outbound.vector_store import VectorStorePort
from docpipe.core.operators.vectordb.domain.models import IndexRequest, IndexResult
from docpipe.core.operators.vectordb.adapters.outbound.factories.vector_store_factory import register_vector_store

@register_vector_store("pinecone")
class PineconeAdapter(VectorStorePort):
    def __init__(self, **config):
        # Initialize Pinecone client
        self.api_key = config.get("pinecone_api_key")
        self.environment = config.get("pinecone_environment")
        # ... setup Pinecone client
        
    def index_documents(self, request: IndexRequest) -> IndexResult:
        # Implement indexing using Pinecone API
        pass
        
    def query_by_doc_names(self, request: QueryRequest) -> QueryResult:
        # Implement querying using Pinecone API
        pass
        
    # ... implement other methods
```

### 2. Register the Adapter

The `@register_vector_store("pinecone")` decorator automatically registers the adapter with the factory.

### 3. Use the New Adapter

```python
config = {
    "provider": "pinecone",  # Now uses Pinecone adapter
    "pinecone_api_key": "your-api-key",  # pragma: allowlist secret
    "pinecone_environment": "us-west1-gcp",
    "index_name": "my_index",
    # ... other Pinecone-specific config
}

operator = VectorDBOperator(config)
# Same interface, different implementation!
```

## Benefits

### 1. Separation of Concerns
- Domain logic (VectorDBOperator) is independent of infrastructure (OpenSearch, Pinecone, etc.)
- Easy to test domain logic without database dependencies

### 2. Dependency Inversion
- High-level operator depends on abstraction (VectorStorePort), not concrete implementations
- Follows SOLID principles

### 3. Open/Closed Principle
- Open for extension (add new adapters)
- Closed for modification (operator code unchanged)

### 4. Easy Testing
- Mock VectorStorePort for unit tests
- Test adapters independently

### 5. Flexibility
- Switch vector databases by changing configuration
- Support multiple databases simultaneously
- Gradual migration between databases

## Design Patterns Used

1. **Hexagonal Architecture (Ports & Adapters)**
   - Clear separation between domain and infrastructure
   - Testable and maintainable

2. **Dependency Injection**
   - Adapter injected via factory based on configuration
   - Loose coupling between components

3. **Factory Pattern**
   - VectorStoreFactory creates appropriate adapter
   - Decorator-based registration for extensibility

4. **Strategy Pattern**
   - Different vector database strategies (adapters)
   - Same interface, different implementations

## File Structure

```
vectordb/
├── README.md                          # This file
├── MILVUS_README.md                   # Milvus-specific documentation
├── __init__.py                        # Public API exports
├── vectordb_operator.py               # Main operator
├── domain/
│   ├── __init__.py
│   └── models.py                      # Domain models
├── ports/
│   └── outbound/
│       ├── __init__.py
│       └── vector_store.py            # Port interface
└── adapters/
    └── outbound/
        ├── __init__.py
        ├── opensearch/                # OpenSearch provider
        │   ├── __init__.py
        │   ├── adapter.py             # OpenSearch adapter
        │   ├── client.py              # OpenSearch connection
        │   ├── index_manager.py       # OpenSearch index ops
        │   └── batch_processor.py     # OpenSearch bulk ops
        ├── milvus/                    # Milvus provider
        │   ├── __init__.py
        │   ├── adapter.py             # Milvus adapter
        │   ├── client.py              # Milvus connection
        │   ├── index_manager.py       # Milvus collection ops
        │   └── batch_processor.py     # Milvus bulk ops
        └── factories/
            ├── __init__.py
            └── vector_store_factory.py # Factory with registration
```
