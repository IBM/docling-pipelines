# Sample Flows

This directory contains ready-to-run sample flows for first-time users of datasift-opensource.

## Complete Pipeline Flow

**File:** `complete_pipeline_flow.json`

### Flow Structure

Each flow consists of:

- **flow_id**: UUID identifying the flow (format: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`)
- **dag**: Array of operator nodes, each with:
  - **id**: UUID for the node (must be unique within the flow)
  - **name**: Descriptive name for the operator instance
  - **operator**: Operator type (e.g., `ingest_local`, `extract_docling`)
  - **config**: Operator-specific parameters
  - **input_edges/output_edges**: References to connected nodes using their UUIDs

### What It Does

This flow demonstrates a complete document processing pipeline that:

1. **Ingests** documents from a local folder
2. **Extracts** structured content using Docling (supports PDFs, DOCX, TXT)
3. **Chunks** documents using semantic chunking strategy
4. **Generates embeddings** using Ollama's nomic-embed-text model
5. **Stores** vectors and metadata in OpenSearch for retrieval

This is a typical RAG (Retrieval-Augmented Generation) preparation pipeline.

### Prerequisites

Before running this flow, ensure you have:

1. **Ollama Running**

   ```bash
   # Start Ollama server
   ollama serve

   # Pull the embedding model
   ollama pull nomic-embed-text
   ```

   Verify: `curl http://localhost:11434/api/tags`

2. **OpenSearch Running**

   ```bash
   # Using the provided docker-compose file
   docker-compose -f docker-compose.opensearch.yml up -d
   ```

   Verify: `curl -u admin:MyStrongPass123! http://localhost:9200`

3. **Python Environment Setup**
   ```bash
   cd src/datasift_opensource/backend
   uv sync --extra dev
   ```

### How to Customize

#### 1. Change Input Documents Path

Edit the `input_folder` in the `ingest-local-documents` node:

```json
"config": {
  "input_folder": "./your/documents/path",
  "include_filter": "pdf,txt,docx",
  ...
}
```

#### 2. Modify Chunking Strategy

Change the chunking approach in the `chunk-documents` node:

```json
"config": {
  "chunk_type": "simple",     // Options: "simple", "semantic", "hybrid"
  "chunk_size": 1024,         // Adjust chunk size
  "chunk_overlap": 100,       // Adjust overlap
  ...
}
```

#### 3. Use Different Embedding Model

Update the model in the `generate-embeddings` node:

```json
"config": {
  "embeddings_model_id": "llama3.2",  // Any Ollama model
  ...
}
```

#### 4. Change OpenSearch Configuration

Modify connection settings and index name in the `store-in-opensearch` node:

```json
"config": {
  "vector_db_type": "opensearch",
  "index_name": "my-custom-index",
  "vectordb_parameters": {
    "host": "localhost",
    "port": 9200,
    ...
  },
  ...
}
```

### Feature Mappings Explained

The `feature_mappings` in the OpenSearch operator maps PyArrow table columns to OpenSearch fields:

```json
"feature_mappings": {
  "content": "content",           // Document text content
  "doc_name": "doc_name",         // Original filename
  "file_path": "file_path",       // Full file path
  "doc_id_hash": "doc_id_hash",   // Unique document identifier
  "chunk_id": "chunk_id",         // Unique chunk identifier
  "chunk_index": "chunk_index"    // Chunk position in document
}
```

**Key:** PyArrow column name → **Value:** OpenSearch field name

### Available Features Configuration

**IMPORTANT:** The `available_features` parameter is **required** to store embeddings and other fields in OpenSearch. This configuration defines which columns should be indexed and their data types.

```json
"available_features": {
  "embeddings": {
    "type": "vector",
    "available_for_vector_db": true
  },
  "content": {
    "type": "string",
    "available_for_vector_db": true
  },
  "doc_name": {
    "type": "string",
    "available_for_vector_db": true
  },
  "file_path": {
    "type": "string",
    "available_for_vector_db": true
  },
  "doc_id_hash": {
    "type": "string",
    "available_for_vector_db": true
  },
  "chunk_id": {
    "type": "string",
    "available_for_vector_db": true
  },
  "chunk_index": {
    "type": "integer",
    "available_for_vector_db": true
  }
}
```

**Key Points:**

- **Embeddings must be explicitly configured:** Even though `embeddings_column` specifies which column contains vectors, the embeddings will NOT be stored unless explicitly listed in `available_features` with `"type": "vector"`
- **Type specification:** Each field must have a type (`vector`, `string`, `integer`, `float`, `boolean`)
- **Storage control:** `"available_for_vector_db": true` enables storage in OpenSearch
- **All mapped features should be included:** Any field in `feature_mappings` should also appear in `available_features`

**Supported Types:**

- `vector` - For embedding vectors (requires KNN configuration)
- `string` - For text fields
- `integer` - For whole numbers
- `float` - For decimal numbers
- `boolean` - For true/false values

### How to Run

1. **Prepare your documents:**

   ```bash
   mkdir -p sample_documents
   # Copy your PDF, TXT, or DOCX files to sample_documents/
   ```

2. **Execute the flow:**

   ```bash
   datasift-orchestrator --flow-file sample_flows/complete_pipeline_flow.json
   ```

3. **Monitor progress:**
   The orchestrator will show progress for each operator and any errors.

4. **Verify results:**

   ```bash
   # Check if index was created
   curl -u admin:MyStrongPass123! "http://localhost:9200/sample-documents-index/_count"

   # Search for documents
   curl -u admin:MyStrongPass123! -X POST "http://localhost:9200/sample-documents-index/_search" \
     -H "Content-Type: application/json" \
     -d '{"query": {"match_all": {}}, "size": 5}'
   ```

### Troubleshooting

**Common Issues:**

1. **Ollama not running:** Ensure `ollama serve` is active and model is pulled
2. **OpenSearch connection failed:** Check if OpenSearch container is running
3. **No documents found:** Verify the `input_folder` path and file extensions
4. **Import errors:** Ensure PYTHONPATH is set correctly when running tests

**Debug Mode:**

Add logging to see detailed execution:

```json
"global_config": {
  "doc_column": "content",
  "disable_validation": "false",  // Enable validation
  "force_ingest": true,
  "log_level": "DEBUG"            // Add debug logging
}
```

### Next Steps

After running this sample:

1. **Query your data:** Use OpenSearch queries to search your indexed documents
2. **Build a chat interface:** Connect to a chat UI for RAG conversations
3. **Add quality operators:** Include document classification, PII redaction, etc.
4. **Scale up:** Process larger document collections with batch processing

For more advanced flows, see the `tests/` directory for additional examples.
