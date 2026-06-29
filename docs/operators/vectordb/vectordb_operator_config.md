# Vector Database Operator - Configuration Reference

## Overview

The Vector Database Operator provides a unified interface for storing documents and embeddings in vector databases for similarity search. It uses hexagonal architecture to support multiple vector database providers through adapters.

- **Operator Name:** `vectordb`
- **Category**: VectorDB
- **Short Name**: `vectordb`

## Supported Providers

- **opensearch**: OpenSearch with multiple KNN engines (NMSLIB, Faiss, Lucene)
- **pinecone**: Pinecone vector database (via adapter)
- **weaviate**: Weaviate vector database (via adapter)

## Configuration Parameters

### Core Parameters

#### 1. `provider` (String)
**Type:** String  
**Required:** No  
**Default:** `"opensearch"`  
**Description:** Type of vector database provider to use.  

**Valid Values:** `opensearch`, `pinecone`, `weaviate`

**Examples:**
```json
"provider": "opensearch"
```

#### 2. `index_name` (String)
**Type:** String  
**Required:** Yes  
**Description:** Name of the vector database index/collection where documents will be stored.  

**Examples:**
```json
"index_name": "documents"
```

#### 3. `doc_id_column` (String)
**Type:** String  
**Required:** No  
**Default:** `"doc_id_hash"`  
**Description:** Column containing document IDs. Used as primary key in the vector database.  

**Examples:**
```json
"doc_id_column": "doc_id_hash"
```

```json
"doc_id_column": "document_id"
```

#### 4. `embeddings_column` (String)
**Type:** String  
**Required:** No  
**Default:** `"embeddings"`  
**Description:** Column containing dense vector embeddings for similarity search.  

**Examples:**
```json
"embeddings_column": "embeddings"
```

```json
"embeddings_column": "vector_embeddings"
```

#### 5. `sparse_embeddings_column` (String)
**Type:** String  
**Required:** No  
**Description:** Column containing sparse vector embeddings for hybrid search (dense + sparse).  

**Examples:**
```json
"sparse_embeddings_column": "sparse_embeddings"
```

#### 6. `create_index` (Boolean)
**Type:** Boolean  
**Required:** No  
**Default:** `true`  
**Description:** Create index if it doesn't exist. When false, expects index to already exist.  

**Examples:**
```json
"create_index": true
```

#### 7. `vector_dimension` (Integer)
**Type:** Integer  
**Required:** No  
**Default:** `384`  
**Description:** Dimension of dense vector embeddings. Auto-detected from data if not specified.  

**Examples:**
```json
"vector_dimension": 768
```

#### 8. `batch_size` (Integer)
**Type:** Integer  
**Required:** No  
**Default:** `100`  
**Description:** Number of documents to index in each batch. Larger batches improve throughput but use more memory.  

**Examples:**
```json
"batch_size": 500
```

### Provider-Specific Configuration

#### 9. `provider_config` (JSON)
**Type:** JSON Object  
**Required:** Yes  
**Description:** Provider-specific configuration parameters including connection settings. **All connection parameters (host, port, username, password, use_ssl, etc.) must be inside this object.**  

**OpenSearch Example:**
```json
"provider_config": {
  "engine": "nmslib",
  "algorithm": "hnsw",
  "space_type": "l2",
  "engine_parameters": {
    "ef_construction": 512,
    "m": 16
  },
  "index_settings": {
    "number_of_shards": 2,
    "number_of_replicas": 1
  }
}
```

**AWS OpenSearch Example:**
```json
"provider_config": {
  "aws_auth": true,
  "aws_region": "us-east-1",
  "engine": "faiss",
  "algorithm": "hnsw"
}
```

## Output Features

### `doc_id_hash` (String)
**Type:** String  
**Description:** Unique identifier for the document  
**Available for Vector DB:** Yes  
**Mandatory for Vector DB:** Yes  
**Is Primary:** Yes  
**Tags:** `mandatory`, `primary`  

### `embeddings` (Vector)
**Type:** Vector (Dense)  
**Description:** Dense vector embeddings for similarity search  
**Available for Vector DB:** Yes  
**Mandatory for Vector DB:** Yes  
**Tags:** `mandatory`  

### `sparse_embeddings` (Vector)
**Type:** Vector (Sparse)  
**Description:** Sparse vector embeddings for hybrid search  
**Available for Vector DB:** Yes  

### `content` (String)
**Type:** String  
**Description:** The text content of the document  
**Available for Filter:** Yes  
**Available for Vector DB:** Yes  

## Configuration Examples

### Example 1: Basic OpenSearch Configuration
```json
{
  "operator": "vectordb",
  "config": {
    "provider": "opensearch",
    "host": "localhost",
    "port": 9200,
    "index_name": "documents",
    "vector_dimension": 768,
    "create_index": true,
    "use_ssl": false,
    "verify_certs": false
  }
}
```

### Example 2: OpenSearch with NMSLIB Engine
```json
{
  "operator": "vectordb",
  "config": {
    "provider": "opensearch",
    "host": "opensearch.example.com",
    "port": 9200,
    "username": "admin",
    "password": "admin", # pragma: allowlist secret
    "index_name": "research_papers",
    "vector_dimension": 1536,
    "batch_size": 500,
    "provider_config": {
      "engine": "nmslib",
      "algorithm": "hnsw",
      "space_type": "l2",
      "engine_parameters": {
        "ef_construction": 512,
        "m": 16
      }
    }
  }
}
```

### Example 3: OpenSearch with Faiss Engine
```json
{
  "operator": "vectordb",
  "config": {
    "provider": "opensearch",
    "host": "localhost",
    "port": 9200,
    "index_name": "embeddings",
    "vector_dimension": 768,
    "use_ssl": false,
    "provider_config": {
      "engine": "faiss",
      "algorithm": "hnsw",
      "space_type": "l2",
      "engine_parameters": {
        "ef_search": 512,
        "ef_construction": 512,
        "m": 16
      }
    }
  }
}
```

### Example 4: OpenSearch with Lucene Engine
```json
{
  "operator": "vectordb",
  "config": {
    "provider": "opensearch",
    "host": "localhost",
    "port": 9200,
    "index_name": "documents",
    "vector_dimension": 384,
    "provider_config": {
      "engine": "lucene",
      "algorithm": "hnsw",
      "space_type": "cosinesimil",
      "engine_parameters": {
        "ef_construction": 128,
        "m": 16
      }
    }
  }
}
```

### Example 5: AWS OpenSearch with Authentication
```json
{
  "operator": "vectordb",
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
  }
}
```

### Example 6: Hybrid Search with Sparse Embeddings
```json
{
  "operator": "vectordb",
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
  }
}
```

## Best Practices

1. **Index Creation**: Let the operator create the index on first run (`create_index: true`)
2. **Vector Dimension**: Match the dimension to your embedding model output
3. **Batch Size**: Use larger batches (500-1000) for better throughput
4. **Engine Selection**: 
   - Use NMSLIB for general use
   - Use Faiss for large datasets
   - Use Lucene for smaller datasets
5. **Connection Security**: Always use SSL in production (`use_ssl: true`)
6. **Engine Parameters**: Tune `ef_construction` and `m` for accuracy/speed tradeoff
7. **Chunked Documents**: The operator automatically handles chunked embeddings

## Validation Rules

- `index_name` is required
- `provider_config` is required and must not be empty
- `vector_dimension` must match embedding model output
- `batch_size` must be greater than 0
- `doc_id_column` must exist in input data
- `embeddings_column` must exist in input data

## Complete Flow Example

- [Sample Flow](../../../sample_flows/complete_pipeline_flow.json)
- [Sample Flow](../../../tests/sample_test_flows/specialized/flow_purchase_orders_with_schema.json)
