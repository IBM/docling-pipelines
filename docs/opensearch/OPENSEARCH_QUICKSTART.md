# OpenSearch Operator - Quick Start Guide

This guide will help you quickly test the new OpenSearch operator implementation.

## 1. Install Dependencies

```bash
cd src/datasift_opensource/backend
uv sync --extra dev
```

This will install:
- `opensearch-py==2.7.1` - OpenSearch Python client
- All other required dependencies

## 2. Verify Installation

```bash
# Activate the virtual environment
source .venv/bin/activate

# Check if opensearch-py is installed
python -c "import opensearchpy; print(f'OpenSearch client version: {opensearchpy.__version__}')"
```

Expected output:
```
OpenSearch client version: 2.7.1
```

## 3. Run Unit Tests

```bash
# From the backend directory
cd src/datasift_opensource/backend

# Set PYTHONPATH
export PYTHONPATH="$(cd ../../.. && pwd)/src:${PYTHONPATH}"

# Run OpenSearch operator tests
uv run pytest ../../../tests/unit/operators/vectordb/test_opensearch_operator.py -v

# Run all tests
uv run pytest ../../../tests/ -v
```

Expected output:
```
tests/unit/operators/vectordb/test_opensearch_operator.py::TestOpenSearchOperator::test_initialization PASSED
tests/unit/operators/vectordb/test_opensearch_operator.py::TestOpenSearchOperator::test_engine_algorithm_compatibility PASSED
...
```

## 4. Run Integration Example

The integration example connects to a real OpenSearch instance and demonstrates all operator capabilities.

```bash
# From project root
python examples/opensearch_integration_example.py
```

This will:
1. Create sample documents with embeddings
2. Index them in OpenSearch using different engines (FAISS, Lucene)
3. Query documents by name
4. Delete documents
5. Demonstrate batch processing
6. Show error handling

Expected output:
```
================================================================================
OpenSearch Operator Integration Examples
================================================================================

Example 1: Basic Document Indexing
...
Connected to OpenSearch 2.x.x
Engine: faiss, Algorithm: hnsw
...
Total documents in index: 10
```

## 5. Test with Your Own Data

Create a simple test script:

```python
import pyarrow as pa
import numpy as np
from datasift_opensource.backend.core.operators.universal.vectordb.opensearch_operator import OpenSearchOperator

# Configuration
config = {
    "opensearch_host": "9.30.97.49",
    "opensearch_port": 9200,
    "opensearch_username": "admin",
    "opensearch_password": "8P@ssw0rd12@",
    "opensearch_use_ssl": False,
    "opensearch_verify_certs": False,
    "index_name": "my_test_index",
    "doc_id_column": "doc_id_hash",
    "embeddings_column": "embeddings",
    "vector_dimension": 384,
    "engine": "faiss",
    "algorithm": "hnsw",
    "space_type": "l2",
    "create_index": True,
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
table = pa.table({
    "doc_id_hash": ["doc1", "doc2", "doc3"],
    "content": ["First document", "Second document", "Third document"],
    "embeddings": [np.random.rand(384).tolist() for _ in range(3)]
})

# Initialize and run operator
operator = OpenSearchOperator(config)
result_tables, metadata = operator.transform(table)

print(f"Indexed {metadata['processed_docs']} documents")
print(f"Total in index: {operator.get_document_count()}")
```

## 6. Verify in OpenSearch

Check the index directly:

```bash
# List all indices
curl -u admin:8P@ssw0rd12@ http://9.30.97.49:9200/_cat/indices?v

# Get index mapping
curl -u admin:8P@ssw0rd12@ http://9.30.97.49:9200/my_test_index/_mapping?pretty

# Search documents
curl -u admin:8P@ssw0rd12@ http://9.30.97.49:9200/my_test_index/_search?pretty

# Get document count
curl -u admin:8P@ssw0rd12@ http://9.30.97.49:9200/my_test_index/_count?pretty
```

## 7. Integration with Full Pipeline

Example flow configuration (`flow_opensearch.json`):

```json
{
  "name": "Document Processing with OpenSearch",
  "operators": [
    {
      "type": "ingest_local_folder",
      "config": {
        "input_folder": "./tests/fixtures/invoices",
        "file_extensions": [".pdf"]
      }
    },
    {
      "type": "extract_docling",
      "config": {}
    },
    {
      "type": "docling_chunker",
      "config": {
        "chunk_size": 512,
        "chunk_overlap": 50
      }
    },
    {
      "type": "opensearch",
      "config": {
        "opensearch_host": "9.30.97.49",
        "opensearch_port": 9200,
        "opensearch_username": "admin",
        "opensearch_password": "8P@ssw0rd12@",
        "opensearch_use_ssl": false,
        "index_name": "invoice_documents",
        "doc_id_column": "doc_id_hash",
        "embeddings_column": "embeddings",
        "vector_dimension": 384,
        "engine": "faiss",
        "algorithm": "hnsw",
        "create_index": true
      }
    }
  ]
}
```

Run the flow:

```bash
datasift-orchestrator run --flow flow_opensearch.json
```

## Troubleshooting

### Issue: Import errors
**Solution**: Make sure dependencies are installed
```bash
cd src/datasift_opensource/backend
uv sync --extra dev
```

### Issue: Connection refused
**Solution**: Verify OpenSearch is accessible
```bash
curl http://9.30.97.49:9200
```

### Issue: Authentication failed
**Solution**: Check credentials
```bash
curl -u admin:8P@ssw0rd12@ http://9.30.97.49:9200
```

### Issue: Index already exists
**Solution**: Either delete the index or set `create_index: false`
```bash
curl -X DELETE -u admin:8P@ssw0rd12@ http://9.30.97.49:9200/my_test_index
```

### Issue: Version compatibility
**Solution**: Check OpenSearch version
```bash
curl -u admin:8P@ssw0rd12@ http://9.30.97.49:9200
```

The operator supports OpenSearch 2.x and later.

## Next Steps

1. ✅ Run unit tests to verify implementation
2. ✅ Run integration example with test OpenSearch instance
3. ✅ Test with your own data
4. ✅ Integrate into your pipeline
5. ✅ Tune performance parameters for your use case

## Performance Tuning Tips

### For Large Datasets (>1M documents)
- Use `engine: "faiss"` with `algorithm: "ivf"`
- Increase `batch_size` to 1000-5000
- Set `nlist: 1000` in engine_parameters

### For High Recall
- Use `engine: "lucene"` with `algorithm: "hnsw"`
- Increase `ef_construction` to 512
- Increase `m` to 64

### For Fast Indexing
- Use `engine: "faiss"` with `algorithm: "hnsw"`
- Decrease `ef_construction` to 128
- Decrease `m` to 16
- Increase `batch_size`

## Additional Resources

- [OpenSearch Operator Documentation](docs/operators/opensearch.md)
- [Integration Example README](examples/opensearch_example_README.md)
- [OpenSearch k-NN Documentation](https://opensearch.org/docs/latest/search-plugins/knn/index/)
- [Unit Tests](tests/unit/operators/vectordb/test_opensearch_operator.py)

## Support

For issues or questions:
1. Check the [operator documentation](docs/operators/opensearch.md)
2. Review the [integration example](examples/opensearch_integration_example.py)
3. Check OpenSearch logs for detailed error messages