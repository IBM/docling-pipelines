# Chunker Operator

## Overview

The Chunker operator splits documents into smaller, manageable chunks for downstream processing such as embedding generation and vector storage. It supports multiple chunking strategies to accommodate different use cases and performance requirements.

## Chunking Strategies

### 1. Simple Chunking
Basic text splitting with configurable chunk size and overlap. Best for straightforward text processing where semantic boundaries are not critical.

**Use Cases:**
- Quick prototyping
- Simple text processing pipelines
- When semantic boundaries are not important

### 2. Semantic Chunking
Sentence-based chunking using NLTK for natural language processing. Respects sentence boundaries to maintain semantic coherence.

**Use Cases:**
- Natural language text processing
- When maintaining sentence integrity is important
- Content that benefits from semantic boundaries

### 3. Hybrid Chunking
Advanced chunking using the Docling library. Provides sophisticated document structure awareness and semantic chunking.

**Execution Providers:**
- **Local (`docling_library`)**: Runs chunking locally using the Docling library
- **Remote (`docling_serve`)**: Offloads chunking to docling-serve API for distributed processing

**Use Cases:**
- Complex document structures requiring sophisticated chunking
- High-quality semantic chunking requirements
- **Local provider**: When local processing is preferred or docling-serve is unavailable
- **Remote provider**: Distributed architectures, scaling operations across workers, offloading computation

## Configuration Parameters

### Common Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `chunk_type` | string | No | `simple` | Chunking strategy: `simple`, `semantic`, or `hybrid` |
| `chunk_size` | integer | No | 1000 | Maximum chunk size in characters (simple: 500-5000) or tokens (hybrid: 100-2048) |
| `chunk_overlap` | integer | No | 200 | Number of overlapping characters/tokens between chunks |
| `doc_column` | string | No | `content` | Name of the column containing text to chunk |

### Provider-Based Configuration

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `provider` | string | No | - | Chunking provider: `docling_library` (local), `docling_serve` (remote), `simple`, or `semantic` |
| `provider_config` | object | No | {} | Provider-specific configuration options (nested object) |

#### Provider Options for `docling_serve`

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `api_base` | string | Yes | - | Base URL of docling-serve instance (e.g., `https://docling-serve.example.com`) |
| `api_key` | string | No | - | API key for authentication (if required) |
| `timeout` | integer | No | 300 | Request timeout in seconds |
| `poll_interval` | integer | No | 2 | Polling interval for async operations (seconds) |
| `max_retries` | integer | No | 3 | Maximum number of retry attempts |
| `verify_ssl` | boolean | No | true | Enable/disable SSL certificate verification. Set to `false` for self-signed certificates |

### Hybrid/Docling Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `docling_tokenizer` | string | No | `sentence-transformers/all-MiniLM-L6-v2` | HuggingFace tokenizer model for hybrid (Docling) chunking. Only used when chunk_type is "hybrid" |

## Configuration Examples

### Simple Chunking

```json
{
  "id": "chunker-node",
  "name": "simple_chunker",
  "operator": "chunker",
  "config": {
    "chunk_type": "simple",
    "chunk_size": 512,
    "chunk_overlap": 128,
    "doc_column": "content"
  }
}
```

### Semantic Chunking

```json
{
  "id": "chunker-node",
  "name": "semantic_chunker",
  "operator": "chunker",
  "config": {
    "chunk_type": "semantic",
    "chunk_size": 512,
    "chunk_overlap": 50,
    "doc_column": "content"
  }
}
```

### Hybrid Chunking (Local)

```json
{
  "id": "chunker-node",
  "name": "docling_chunker",
  "operator": "chunker",
  "config": {
    "chunk_type": "hybrid",
    "provider": "docling_library",
    "chunk_size": 512,
    "chunk_overlap": 128,
    "docling_tokenizer": "sentence-transformers/all-MiniLM-L6-v2",
    "doc_column": "content"
  }
}
```

### Docling-serve Chunking (Remote)

```json
{
  "id": "chunker-node",
  "name": "docling_serve_chunker",
  "operator": "chunker",
  "config": {
    "chunk_type": "hybrid",
    "chunk_size": 512,
    "chunk_overlap": 128,
    "provider": "docling_serve",
    "provider_config": {
      "api_base": "https://docling-serve.example.com",
      "timeout": 60,
      "max_retries": 3
    },
    "doc_column": "content"
  }
}
```

## Input Schema

The Chunker operator expects a PyArrow table with at least:

| Column | Type | Description |
|--------|------|-------------|
| `content` (or custom name) | string | Text content to be chunked |
| `doc_id_hash` | string | Document identifier |

Additional columns are preserved in the output.

## Output Schema

The operator produces a PyArrow table with:

| Column | Type | Description |
|--------|------|-------------|
| `chunked_content` | list<struct<chunk: string, start_index: int64>> | Array of chunks with metadata |
| All original columns except `content` | - | Preserved from input |

Each chunk in `chunked_content` contains:
- `chunk`: The text content of the chunk
- `start_index`: Starting position in the original text

## Docling-serve Integration

### Architecture

When `provider: "docling_serve"` is configured, the Chunker operator:

1. Encodes markdown content as base64
2. Sends POST request to `/v1/chunk/hybrid/source` endpoint
3. Receives chunked results from docling-serve
4. Processes and formats chunks into PyArrow table

### API Communication

**Endpoint:** `POST /v1/chunk/hybrid/source`

**Request Payload:**
```json
{
  "sources": [{
    "kind": "file",
    "base64_string": "<base64-encoded-markdown>",
    "filename": "document.md"
  }],
  "convert_options": {
    "from_formats": ["md"],
    "to_formats": ["md"]
  },
  "include_converted_doc": false,
  "target": {"kind": "inbody"},
  "chunking_options": {
    "chunker": "hybrid",
    "tokenizer": "nltk",
    "max_tokens": 512,
    "merge_peers": true,
    "use_markdown_tables": false,
    "include_raw_text": false
  }
}
```

**Response:**
```json
{
  "chunks": [
    {
      "text": "Chunk content...",
      "meta": {
        "headings": ["Section Title"],
        "doc_items": [...],
        "token_count": 245
      }
    }
  ]
}
```

### Error Handling

The operator handles various error scenarios:

- **Connection Timeout**: Retries with exponential backoff
- **Empty Response**: Logs warning and continues with next document
- **Invalid Response**: Raises exception with detailed error message
- **Network Errors**: Retries up to `docling_serve_chunking_max_retries`

### SSL Certificate Validation

For testing with self-signed certificates, SSL verification can be disabled in the RestClient configuration. For production deployments, proper SSL certificates should be used.

## Performance Considerations

### Local vs Remote Chunking

| Aspect | Local (Hybrid) | Remote (Docling-serve) |
|--------|----------------|------------------------|
| **Latency** | Low (in-process) | Higher (network overhead) |
| **Scalability** | Limited by local resources | Scales with docling-serve instances |
| **Resource Usage** | Uses local CPU/memory | Offloads to remote service |
| **Dependencies** | Requires Docling library | Requires network access |
| **Best For** | Small-scale, local processing | Large-scale, distributed processing |

### Optimization Tips

1. **Chunk Size**: Balance between semantic coherence and processing efficiency
   - Smaller chunks (256-512 tokens): Better for precise retrieval
   - Larger chunks (1024+ tokens): Better for context preservation

2. **Chunk Overlap**: Prevents information loss at chunk boundaries
   - Recommended: 10-25% of chunk size
   - Example: 128 tokens overlap for 512-token chunks

3. **Batch Processing**: Process multiple documents in parallel when using docling-serve

4. **Timeout Configuration**: Adjust based on document size and network latency
   - Small documents: 30-60 seconds
   - Large documents: 120+ seconds

## Common Workflows

### RAG Pipeline with Remote Chunking

```
IngestSource → ExtractOperator → Chunker (docling-serve) → EmbeddingsOperator → VectorDBOperator
```

### Quality-Enhanced Pipeline

```
IngestSource → ExtractOperator → LanguageDetection → Chunker → EmbeddingsOperator
```

### Multi-Strategy Pipeline

```
IngestSource → ExtractOperator → BranchingOperator
                                  ├─> Chunker (simple) → Path A
                                  └─> Chunker (hybrid) → Path B
```

## Troubleshooting

### Issue: Connection Timeout to Docling-serve

**Symptoms:** `Connection to docling-serve timed out` error

**Solutions:**
1. Verify docling-serve is running and accessible
2. Check network connectivity
3. Increase `docling_serve_chunking_timeout`
4. Verify firewall rules allow outbound HTTPS

### Issue: Empty Chunks Returned

**Symptoms:** `Docling-serve returned no chunks` warning

**Solutions:**
1. Verify input content is not empty
2. Check content format (should be markdown)
3. Verify docling-serve configuration
4. Review docling-serve logs for errors

### Issue: SSL Certificate Errors

**Symptoms:** SSL verification failures

**Solutions:**
1. Use proper SSL certificates in production
2. For testing, configure RestClient with `verify_ssl=False`
3. Add CA certificates to system trust store

### Issue: Slow Chunking Performance

**Symptoms:** High latency in chunking operations

**Solutions:**
1. Consider using local hybrid chunking for small-scale operations
2. Scale docling-serve horizontally
3. Optimize chunk size and overlap parameters
4. Enable batch processing

## Metadata

The operator provides metadata about chunking operations:

```python
{
  "total_chunks": 150,
  "processed_docs": 10,
  "failed_docs_count": 0,
  "skipped_docs_count": 0,
  "node_status": "Completed"
}
```

## Related Operators

- **ExtractOperator**: Extracts text content for chunking
- **EmbeddingsOperator**: Generates embeddings from chunks
- **VectorDBOperator**: Stores chunked and embedded content
- **BranchingOperator**: Enables conditional chunking strategies

## References

- [Docling Documentation](https://github.com/DS4SD/docling)
- [Docling-serve API](https://github.com/DS4SD/docling-serve)
- [ARCHITECTURE.md](../../ARCHITECTURE.md) - System architecture overview