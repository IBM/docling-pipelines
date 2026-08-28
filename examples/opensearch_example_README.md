# OpenSearch Integration Example

This example demonstrates how to use the OpenSearch operator for vector similarity search in the Docling Pipelines pipeline.

## Prerequisites

1. **Install Dependencies**
   ```bash
   # From project root
   uv sync --extra dev
   ```

2. **Configure Environment Variables**

   Create a `.env` file in the project root with your OpenSearch configuration:
   ```bash
   cp .env.example .env
   ```

   Edit `.env` and set your OpenSearch connection details:
   ```bash
   # OpenSearch Connection
   OPENSEARCH_HOST=your-opensearch-host
   OPENSEARCH_PORT=9200
   OPENSEARCH_USE_SSL=true
   OPENSEARCH_VERIFY_CERTS=true
   OPENSEARCH_USERNAME=your-username
   OPENSEARCH_PASSWORD=${OPENSEARCH_PASSWORD}

   # Index Configuration
   OPENSEARCH_INDEX_NAME=docpipe_vectors
   OPENSEARCH_VECTOR_DIMENSION=384

   # Engine Configuration
   OPENSEARCH_ENGINE=faiss
   OPENSEARCH_ALGORITHM=hnsw
   OPENSEARCH_SPACE_TYPE=l2
   ```

   See [Environment Setup Guide](../docs/integrations/opensearch/ENVIRONMENT_SETUP.md) for complete configuration details.

## Running the Example

```bash
python examples/opensearch_integration_example.py
```

## What the Example Demonstrates

### Example 1: Basic Document Indexing
- Creates sample documents with embeddings
- Uses FAISS engine with HNSW algorithm
- Indexes documents in batches
- Verifies document count

### Example 2: Lucene Engine with Cosine Similarity
- Demonstrates using Lucene engine instead of FAISS
- Uses cosine similarity metric
- Shows custom engine parameters (ef_construction, m)

### Example 3: Query and Delete Operations
- Queries documents by document names
- Retrieves specific fields
- Deletes documents by IDs
- Verifies deletion

### Example 4: Large Batch Processing
- Processes 150 documents in batches of 50
- Demonstrates automatic batch size management
- Shows batch processing statistics

### Example 5: Error Handling
- Handles missing document IDs
- Tracks skipped and failed documents
- Shows error reporting

## Expected Output

```
================================================================================
OpenSearch Operator Integration Examples
================================================================================

These examples demonstrate the OpenSearch operator capabilities:
1. Basic document indexing
2. Different engines and algorithms
3. Query and delete operations
4. Batch processing
5. Error handling

================================================================================
Example 1: Basic Document Indexing
================================================================================

1. Creating sample documents...
   Created 10 documents

2. Initializing OpenSearch operator...
   Connected to OpenSearch 2.x.x
   Engine: faiss, Algorithm: hnsw

3. Indexing documents...

4. Indexing Results:
   Total documents: 10
   Processed: 10
   Failed: 0
   Skipped: 0
   Batches: 1

5. Verifying index...
   Total documents in index: 10

...
```

## Configuration Options

The example shows various configuration options:

### Engine Options
- `faiss` - Facebook AI Similarity Search (fastest)
- `lucene` - Apache Lucene (most compatible)
- `nmslib` - Non-Metric Space Library
- `jvector` - Java-based vector search (OpenSearch 2.16+)

### Algorithm Options
- `hnsw` - Hierarchical Navigable Small World (recommended)
- `ivf` - Inverted File Index (for large datasets)

### Similarity Metrics
- `l2` - Euclidean distance
- `cosine` - Cosine similarity
- `innerproduct` - Inner product

### Engine Parameters
```python
"engine_parameters": {
    "ef_construction": 256,  # HNSW: higher = better recall, slower indexing
    "m": 32,                 # HNSW: higher = better recall, more memory
    "nlist": 100,            # IVF: number of clusters
    "nprobes": 10            # IVF: number of clusters to search
}
```

## Integration with Full Pipeline

To use OpenSearch in a complete pipeline:

```python
# 1. Ingest documents
from docpipe.core.operators.ingest.ingest_source import IngestSourceOperator

ingest_config = {
    "provider": "filesystem",
    "connection_params": {"paths": ["/path/to/documents"]},
    "include_filter": "pdf,docx,txt"
}
ingest_op = IngestSourceOperator(ingest_config)
table = ingest_op.transform()

# 2. Extract content
from docpipe.core.operators.extract.extract_operator import ExtractOperator

extract_config = {}
extract_op = ExtractOperator(extract_config)
table, _ = extract_op.transform(table)

# 3. Chunk documents
from docpipe.core.operators.functional.chunker import ChunkerOperator

chunk_config = {
    "chunk_size": 512,
    "chunk_overlap": 50
}
chunk_op = ChunkerOperator(chunk_config)
table, _ = chunk_op.transform(table)

# 4. Generate embeddings (you would use your embedding operator here)
# table = add_embeddings(table)

# 5. Index in OpenSearch
from docpipe.utils.infrastructure.config import get_opensearch_config
from docpipe.core.operators.vectordb import VectorDBOperator

# Load configuration from environment variables
opensearch_config = get_opensearch_config()

# Override specific settings if needed
opensearch_config.update({
    "index_name": "my_documents",
    "available_features": {...},
    "feature_mappings": {...}
})

opensearch_op = VectorDBOperator(opensearch_config)
result_tables, metadata = opensearch_op.transform(table)
```

## Troubleshooting

### Missing .env File
```bash
# The example will exit gracefully if .env is not found
⚠️  .env file not found!
This example requires OpenSearch configuration in a .env file.
Please create .env based on .env.example

# Create .env from template
cp .env.example .env
# Edit .env with your configuration
```

### Connection Issues
```bash
# Check if OpenSearch is accessible (replace with your host)
curl https://your-opensearch-host:9200

# Verify credentials
curl -u username:password https://your-opensearch-host:9200
```

### Import Errors
```bash
# Make sure dependencies are installed from project root
uv sync --extra dev
```

### Index Already Exists
```python
# Set create_index to False to use existing index
config["create_index"] = False

# Or delete the index first
operator.client.indices.delete(index="index_name")
```

## Performance Tuning

### For Large Datasets (>1M documents)
```python
config = {
    "batch_size": 1000,
    "provider_config": {
        "engine": "faiss",
        "algorithm": "ivf",
        "engine_parameters": {
            "nlist": 1000,
            "nprobes": 50
        }
    }
}
```

### For High Recall Requirements
```python
config = {
    "provider_config": {
        "engine": "lucene",
        "algorithm": "hnsw",
        "engine_parameters": {
            "ef_construction": 512,
            "m": 64
        }
    }
}
```

### For Fast Indexing
```python
config = {
    "batch_size": 500,
    "provider_config": {
        "engine": "faiss",
        "algorithm": "hnsw",
        "engine_parameters": {
            "ef_construction": 128,
            "m": 16
        }
    }
}
```

## Next Steps

1. Configure your `.env` file with OpenSearch connection details
2. Run the example: `python examples/opensearch_integration_example.py`
3. Integrate with your embedding model
4. Adjust batch sizes and engine parameters for your use case
5. Add custom metadata fields to feature_mappings
6. Implement similarity search queries

## Additional Resources

- [Environment Setup Guide](../docs/integrations/opensearch/ENVIRONMENT_SETUP.md) - Complete configuration guide
- [OpenSearch Quick Start](../docs/integrations/opensearch/OPENSEARCH_QUICKSTART.md) - Quick start guide
- [Operator Documentation](../docs/operators/vectordb/opensearch.md) - Full operator reference
- [OpenSearch Documentation](https://opensearch.org/docs/latest/) - Official OpenSearch docs
- [OpenSearch k-NN Plugin](https://opensearch.org/docs/latest/search-plugins/knn/index/) - Vector search plugin
