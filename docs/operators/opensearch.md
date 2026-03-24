# OpenSearch Operator

## Overview

The OpenSearch operator stores documents and embeddings in OpenSearch for vector similarity search. It supports multiple KNN engines, algorithms, incremental updates, and query capabilities.

## Features

### Core Capabilities
- **Multiple KNN Engines**: FAISS, Lucene, nmslib, jVector
- **Multiple Algorithms**: HNSW, IVF
- **Vector Similarity Metrics**: L2, Cosine, Inner Product
- **Batch Processing**: Size-aware batching with configurable limits
- **Incremental Updates**: Query and delete capabilities
- **Error Handling**: Detailed failure tracking and retry logic
- **Version Compatibility**: Automatic version detection and validation

### Supported Engines

| Engine | Algorithms | Best For | Notes |
|--------|-----------|----------|-------|
| FAISS | HNSW, IVF | Large-scale similarity search | Recommended for production |
| Lucene | HNSW | Native OpenSearch integration | Good balance of speed and accuracy |
| nmslib | HNSW | Legacy support | Deprecated in OpenSearch 2.13+ |
| jVector | HNSW | Java-based implementation | Requires k-NN plugin |

### Algorithm Comparison

| Algorithm | Speed | Accuracy | Memory | Use Case |
|-----------|-------|----------|--------|----------|
| HNSW | Fast | High | Medium | General purpose, recommended |
| IVF | Very Fast | Medium | Low | Large datasets, speed priority |

## Configuration Parameters

### Connection Settings

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `opensearch_host` | string | Yes | - | OpenSearch server host |
| `opensearch_port` | integer | No | 9200 | OpenSearch server port |
| `opensearch_username` | string | No | - | Username for authentication |
| `opensearch_password` | string | No | - | Password for authentication |
| `opensearch_use_ssl` | boolean | No | false | Use SSL connection |
| `opensearch_verify_certs` | boolean | No | false | Verify SSL certificates |
| `opensearch_aws_auth` | boolean | No | false | Use AWS IAM authentication |
| `opensearch_aws_region` | string | No | - | AWS region for authentication |

### Index Settings

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `index_name` | string | Yes | - | Name of the OpenSearch index |
| `doc_id_column` | string | No | "doc_id_hash" | Column containing document IDs |
| `embeddings_column` | string | No | "embeddings" | Column containing embeddings |
| `vector_dimension` | integer | No | 384 | Dimension of vector embeddings |
| `create_index` | boolean | No | true | Create index if it doesn't exist |
| `batch_size` | integer | No | 100 | Documents per batch |

### Engine Configuration

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `engine` | string | No | "faiss" | KNN engine (faiss, lucene, nmslib, jvector) |
| `algorithm` | string | No | "hnsw" | KNN algorithm (hnsw, ivf) |
| `space_type` | string | No | "l2" | Similarity metric (l2, cosine, inner_product) |
| `engine_parameters` | object | No | {} | Custom engine-specific parameters |

### Engine Parameters

#### FAISS + HNSW
```json
{
  "ef_construction": 128,
  "m": 24
}
```

#### FAISS + IVF
```json
{
  "nlist": 128,
  "nprobe": 8
}
```

#### Lucene + HNSW
```json
{
  "ef_construction": 128,
  "m": 16
}
```

## Usage Examples

### Example 1: Basic Usage with FAISS

```python
from core.operators.universal.vectordb.opensearch_operator import OpenSearchOperator
import pyarrow as pa
import numpy as np

config = {
    "opensearch_host": "localhost",
    "opensearch_port": 9200,
    "opensearch_username": "admin",
    "opensearch_password": "admin",
    "opensearch_use_ssl": False,
    "index_name": "my_documents",
    "engine": "faiss",
    "algorithm": "hnsw",
    "space_type": "l2",
    "vector_dimension": 384,
    "available_features": {
        "doc_id_hash": {
            "available_for_vector_db": True,
            "mandatory_for_vector_db": True,
            "type": "string",
            "is_primary": True
        },
        "content": {
            "available_for_vector_db": True,
            "type": "string"
        },
        "embeddings": {
            "available_for_vector_db": True,
            "mandatory_for_vector_db": True,
            "type": "vector"
        }
    },
    "feature_mappings": {
        "doc_id_hash": "id",
        "content": "text",
        "embeddings": "vector"
    }
}

# Create sample data
data = {
    "doc_id_hash": ["doc1", "doc2"],
    "content": ["First document", "Second document"],
    "embeddings": [np.random.rand(384).tolist(), np.random.rand(384).tolist()]
}

table = pa.table(data)

# Index documents
operator = OpenSearchOperator(config)
result_tables, metadata = operator.transform(table)

print(f"Indexed {metadata['processed_docs']} documents")
```

### Example 2: Lucene Engine with Cosine Similarity

```python
config = {
    "opensearch_host": "localhost",
    "opensearch_port": 9200,
    "index_name": "semantic_search",
    "engine": "lucene",
    "algorithm": "hnsw",
    "space_type": "cosine",
    "vector_dimension": 768,
    "engine_parameters": {
        "ef_construction": 256,
        "m": 32
    }
}
```

### Example 3: AWS OpenSearch with IAM Authentication

```python
config = {
    "opensearch_host": "search-mydomain.us-east-1.es.amazonaws.com",
    "opensearch_port": 443,
    "opensearch_use_ssl": True,
    "opensearch_aws_auth": True,
    "opensearch_aws_region": "us-east-1",
    "index_name": "production_docs",
    "engine": "faiss",
    "algorithm": "hnsw"
}
```

### Example 4: Query Documents

```python
# Query documents by name
docs = operator.query_by_doc_names(["doc1", "doc2"], fields=["content", "embeddings"])
print(f"Found {len(docs)} documents")

# Get document count
count = operator.get_document_count()
print(f"Total documents: {count}")

# Delete documents
success, failed = operator.delete_documents_by_ids(["doc1", "doc2"])
print(f"Deleted {success} documents, {failed} failed")
```

## Flow Configuration

### Complete Flow Example

```json
{
  "id": "opensearch-node",
  "name": "Store in OpenSearch",
  "operator": "opensearch",
  "config": {
    "opensearch_host": "localhost",
    "opensearch_port": 9200,
    "opensearch_username": "admin",
    "opensearch_password": "admin",
    "opensearch_use_ssl": false,
    "index_name": "datasift_documents",
    "doc_id_column": "doc_id_hash",
    "embeddings_column": "embeddings",
    "engine": "faiss",
    "algorithm": "hnsw",
    "space_type": "l2",
    "vector_dimension": 384,
    "batch_size": 100,
    "create_index": true,
    "available_features": {
      "doc_id_hash": {
        "name": "Document ID",
        "available_for_vector_db": true,
        "mandatory_for_vector_db": true,
        "type": "string",
        "is_primary": true
      },
      "content": {
        "name": "Content",
        "available_for_vector_db": true,
        "type": "string"
      },
      "embeddings": {
        "name": "Embeddings",
        "available_for_vector_db": true,
        "mandatory_for_vector_db": true,
        "type": "vector"
      }
    },
    "feature_mappings": {
      "doc_id_hash": "pk",
      "content": "text",
      "embeddings": "vector_embeddings"
    }
  }
}
```

## Performance Tuning

### Batch Size Optimization

The operator uses size-aware batching with a default limit of 3MB per batch:

```python
config = {
    "batch_size": 500,  # Maximum documents per batch
    # Actual batch size may be smaller if 3MB limit is reached
}
```

### Engine-Specific Tuning

#### FAISS + HNSW (Balanced)
```python
"engine_parameters": {
    "ef_construction": 128,  # Higher = better accuracy, slower indexing
    "m": 24                  # Higher = better accuracy, more memory
}
```

#### FAISS + IVF (Speed Priority)
```python
"engine_parameters": {
    "nlist": 128,  # Number of clusters
    "nprobe": 8    # Clusters to search (higher = more accurate, slower)
}
```

#### Lucene + HNSW (Native)
```python
"engine_parameters": {
    "ef_construction": 128,
    "m": 16  # Lucene typically uses lower m values
}
```

## Error Handling

The operator provides detailed error tracking:

```python
result_tables, metadata = operator.transform(table)

print(f"Total documents: {metadata['total_docs']}")
print(f"Processed: {metadata['processed_docs']}")
print(f"Failed: {metadata['failed_docs_count']}")
print(f"Skipped: {metadata['skipped_docs_count']}")
print(f"Batches: {metadata['number_of_batches']}")

# Check failed documents
for failed_doc in metadata['failed_docs']:
    print(f"Failed: {failed_doc['name']} - {failed_doc['reason']}")
```

## Best Practices

### 1. Engine Selection
- **FAISS**: Best for production, supports both HNSW and IVF
- **Lucene**: Good for native OpenSearch integration
- **Avoid nmslib**: Deprecated in OpenSearch 2.13+

### 2. Algorithm Selection
- **HNSW**: Recommended for most use cases (high accuracy)
- **IVF**: Use for very large datasets where speed is critical

### 3. Similarity Metrics
- **L2**: Euclidean distance (default, works well for most embeddings)
- **Cosine**: Normalized similarity (good for text embeddings)
- **Inner Product**: For pre-normalized vectors

### 4. Index Management
- Always set `create_index: true` for first run
- Validate existing index configuration matches your settings
- Use consistent engine/algorithm across index lifecycle

### 5. Batch Processing
- Default batch size (100) works well for most cases
- Increase for smaller documents, decrease for large documents
- Monitor memory usage with large batches

## Troubleshooting

See [`docs/opensearch/DOCKER_SETUP.md`](../opensearch/DOCKER_SETUP.md) for troubleshooting.

## Related Operators

- **IngestLocalOperator**: Ingest documents from local filesystem
- **ExtractDoclingOperator**: Extract content from documents
- **DoclingChunkerOperator**: Chunk documents for vector storage
- **EmbeddingsOperator**: Generate embeddings from text

## References

- [OpenSearch k-NN Plugin Documentation](https://opensearch.org/docs/latest/search-plugins/knn/index/)
- [FAISS Documentation](https://github.com/facebookresearch/faiss)
- [OpenSearch Python Client](https://opensearch.org/docs/latest/clients/python/)