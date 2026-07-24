# VectorDBOperator

Indexes document embeddings into a vector database for similarity search.

- **Short Name:** `vectordb`
- **Category:** VectorDB

---

## Overview

`VectorDBOperator` takes a PyArrow table containing document embeddings and indexes it into a
vector database. It uses a hexagonal architecture (ports and adapters) so that the core operator
logic is independent of the underlying database; switching providers only requires a config change.

OpenSearch is the primary supported provider; Pinecone and Weaviate are available via adapters.

---

## Key Features

- Multi-provider support via adapter pattern (OpenSearch, Pinecone, Weaviate)
- Automatic index creation on first run (`create_index: true`)
- Configurable KNN engine and algorithm (NMSLIB, Faiss, Lucene for OpenSearch)
- Hybrid search support (dense + sparse embeddings)
- Batch-based indexing for throughput control
- Auto-detection of vector dimension from input data

---

## Operator Configuration

```json
{
  "type": "vectordb",
  "name": "index_documents",
  "config": {
    "provider": "opensearch",
    "host": "localhost",
    "port": 9200,
    "index_name": "my_documents",
    "vector_dimension": 384,
    "use_ssl": false,
    "verify_certs": false,
    "provider_config": {
      "engine": "nmslib",
      "algorithm": "hnsw",
      "space_type": "l2"
    }
  },
  "depends_on": ["generate_embeddings"]
}
```

---

## Parameters

### Core parameters

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `provider` | string | No | `"opensearch"` | Vector DB provider: `opensearch`, `pinecone`, `weaviate` |
| `index_name` | string | **Yes** | — | Index/collection name |
| `host` | string | No | `"localhost"` | Database host |
| `port` | integer | No | `9200` | Database port |
| `username` | string | No | — | Authentication username |
| `password` | string | No | — | Authentication password |
| `use_ssl` | boolean | No | `false` | Enable SSL/TLS |
| `verify_certs` | boolean | No | `false` | Verify SSL certificates |
| `doc_id_column` | string | No | `"doc_id_hash"` | Column used as primary key |
| `embeddings_column` | string | No | `"embeddings"` | Column containing dense embeddings |
| `sparse_embeddings_column` | string | No | — | Column containing sparse embeddings for hybrid search |
| `create_index` | boolean | No | `true` | Create index if it does not exist |
| `vector_dimension` | integer | No | `384` | Embedding dimension (auto-detected from data if omitted) |
| `batch_size` | integer | No | `100` | Documents indexed per batch |
| `provider_config` | object | No | `{}` | Provider-specific settings (engine, algorithm, AWS auth, etc.) |

### OpenSearch `provider_config` fields

| Field | Type | Default | Description |
|---|---|---|---|
| `engine` | string | `"nmslib"` | KNN engine: `nmslib`, `faiss`, `lucene` |
| `algorithm` | string | `"hnsw"` | Index algorithm |
| `space_type` | string | `"l2"` | Distance metric: `l2`, `cosinesimil`, `innerproduct` |
| `engine_parameters.ef_construction` | integer | `512` | Accuracy/speed tradeoff during indexing |
| `engine_parameters.m` | integer | `16` | Number of bi-directional links per node |
| `index_settings.number_of_shards` | integer | `1` | OpenSearch shards |
| `index_settings.number_of_replicas` | integer | `0` | OpenSearch replicas |
| `aws_auth` | boolean | `false` | Use AWS SigV4 auth (for AWS OpenSearch Service) |
| `aws_region` | string | — | AWS region (required when `aws_auth: true`) |

---

## Output Columns

The operator does not add or remove columns. The input table is returned unchanged to allow
chaining with downstream operators.

**Required input columns:**

| Column | Description |
|---|---|
| `doc_id_hash` (or `doc_id_column`) | Unique document ID — used as the primary key |
| `embeddings` (or `embeddings_column`) | Dense vector embeddings |

---

## Examples

### Example 1 — Basic OpenSearch (local, no auth)

```json
{
  "type": "vectordb",
  "name": "index_documents",
  "config": {
    "provider": "opensearch",
    "host": "localhost",
    "port": 9200,
    "index_name": "documents",
    "vector_dimension": 384,
    "use_ssl": false,
    "verify_certs": false
  },
  "depends_on": ["embeddings"]
}
```

### Example 2 — OpenSearch with Faiss and custom settings

```json
{
  "type": "vectordb",
  "name": "index_documents",
  "config": {
    "provider": "opensearch",
    "host": "opensearch.example.com",
    "port": 9200,
    "username": "admin",
    "password": "${OPENSEARCH_PASSWORD}",
    "index_name": "research_papers",
    "vector_dimension": 1536,
    "batch_size": 500,
    "provider_config": {
      "engine": "faiss",
      "algorithm": "hnsw",
      "space_type": "l2",
      "engine_parameters": {
        "ef_construction": 512,
        "m": 16
      }
    }
  },
  "depends_on": ["embeddings"]
}
```

### Example 3 — AWS OpenSearch Service

```json
{
  "type": "vectordb",
  "name": "index_documents",
  "config": {
    "provider": "opensearch",
    "host": "search-domain.us-east-1.es.amazonaws.com",
    "port": 443,
    "index_name": "documents",
    "vector_dimension": 1536,
    "use_ssl": true,
    "verify_certs": true,
    "provider_config": {
      "aws_auth": true,
      "aws_region": "us-east-1",
      "engine": "faiss",
      "algorithm": "hnsw"
    }
  },
  "depends_on": ["embeddings"]
}
```

### Example 4 — Hybrid search (dense + sparse)

```json
{
  "type": "vectordb",
  "name": "index_hybrid",
  "config": {
    "provider": "opensearch",
    "host": "localhost",
    "port": 9200,
    "index_name": "hybrid_search",
    "embeddings_column": "dense_embeddings",
    "sparse_embeddings_column": "sparse_embeddings",
    "vector_dimension": 768,
    "provider_config": {
      "engine": "nmslib",
      "algorithm": "hnsw"
    }
  },
  "depends_on": ["embeddings"]
}
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ConnectionError` to OpenSearch | Service not running or wrong host/port | Start OpenSearch; verify `host` and `port` |
| `Index already exists` on re-run | `create_index: true` but index was already created | This is safe — the operator skips creation if the index exists |
| `KeyError: doc_id_hash` | Input table missing the ID column | Ensure `DocIdHashOperator` runs before `VectorDBOperator` |
| `KeyError: embeddings` | Input table missing the embeddings column | Ensure `EmbeddingsOperator` runs before `VectorDBOperator` |
| Vector dimension mismatch | `vector_dimension` does not match embedding model output | Set `vector_dimension` to match your model (e.g. 384, 768, 1536) or omit it for auto-detection |
| Slow indexing | `batch_size` too small | Increase `batch_size` to 500–1000 |

---

## Architecture

### Hexagonal design

```
VectorDBOperator (application layer)
    └── VectorStorePort (interface)
            └── OpenSearchAdapter (outbound adapter)
                    ├── OpenSearchClient         (connection)
                    ├── OpenSearchIndexManager   (index ops)
                    └── OpenSearchBatchProcessor (bulk indexing)
```

Adding a new provider requires only a new adapter class decorated with `@register_vector_store("provider_name")`.

### Engine selection guide (OpenSearch)

| Engine | Best for |
|---|---|
| `nmslib` | General use, balanced accuracy/speed |
| `faiss` | Large-scale datasets (millions of docs) |
| `lucene` | Smaller datasets, no native dependency |

### Typical pipeline position

```
Ingest → Extract → Chunker → Embeddings → VectorDBOperator
```

### Sample flows

- [`sample_flows/vectordb/opensearch_integration.json`](../../../sample_flows/vectordb/opensearch_integration.json)
- [`sample_flows/vectordb/milvus_integration.json`](../../../sample_flows/vectordb/milvus_integration.json)
- [`sample_flows/operators/entity_extraction_litellm.json`](../../../sample_flows/operators/entity_extraction_litellm.json)
