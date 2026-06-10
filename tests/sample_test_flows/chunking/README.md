# Chunking Test Flows

This directory contains test flows demonstrating the Chunker operator with various configurations, including LLM-based summarization.

## Available Flows

### 1. Simple Chunking with Summarization
**File:** `simple_chunking_with_summarization.json`

**Description:** Basic pipeline demonstrating simple chunking with LLM-based summarization.

**Pipeline:** Ingest → Extract → Chunk (with summaries)

**Key Features:**
- Simple chunking strategy
- Chunk size: 500 tokens
- Chunk overlap: 50 tokens
- LLM summarization enabled (LiteLLM + Ollama)
- Summary configuration: 3 sentences, max 50 words

**Usage:**
```bash
datasift-orchestrator --flow-file tests/sample_test_flows/chunking/simple_chunking_with_summarization.json
```

### 2. Hybrid Chunking with Summarization
**File:** `hybrid_chunking_with_summarization.json`

**Description:** Advanced pipeline using Docling's hybrid chunking with LLM-based summarization.

**Pipeline:** Ingest → Extract → SQL Filter → Chunk (with summaries)

**Key Features:**
- Hybrid chunking strategy (Docling)
- Chunk size: 512 tokens
- Chunk overlap: 128 tokens
- LLM summarization enabled (LiteLLM + Ollama)
- Micro-batching enabled (batch size: 10)
- SQL filtering for data quality

**Usage:**
```bash
datasift-orchestrator --flow-file tests/sample_test_flows/chunking/hybrid_chunking_with_summarization.json
```

## Prerequisites

### Ollama Setup
Both flows require Ollama running locally with the `llama3.2` model:

```bash
# Install Ollama (if not already installed)
# Visit: https://ollama.ai

# Pull the model
ollama pull llama3.2

# Verify Ollama is running
curl http://localhost:11434/v1/models
```

### Test Data
- **Simple flow:** Uses documents from `./sample_documents`
- **Hybrid flow:** Uses test fixtures from `./tests/fixtures/customer_support_docs`

## Summarization Configuration

Both flows use the following summarization setup:

```json
{
  "summarization": {
    "provider": "litellm",
    "provider_config": {
      "model_id": "openai/llama3.2",
      "api_base": "http://localhost:11434/v1",
      "api_key": "<ollama>"
    }
  }
}
```

### Customization Options

You can customize summarization behavior by modifying:
- `summary_sentences`: Number of sentences in summary (default: 2)
- `summary_max_words`: Maximum words per summary (default: 100)
- `summarization_provider_config.model_id`: Different LLM model
- `summarization_provider`: Switch to `watsonx` or other providers

## Output Schema

When summarization is enabled, chunks include a `summary` field:

```
chunked_content: list<item: struct<chunk: string, start_index: int64, summary: string>>
  child 0, item: struct<chunk: string, start_index: int64, summary: string>
      child 0, chunk: string
      child 1, start_index: int64
      child 2, summary: string
```

## Troubleshooting

### Ollama Connection Issues
If you see connection errors:
1. Verify Ollama is running: `curl http://localhost:11434/v1/models`
2. Check the model is available: `ollama list`
3. Ensure port 11434 is not blocked

### Slow Summarization
Summarization adds processing time:
- Simple flow: ~3-5 seconds per document
- Hybrid flow: ~12-15 seconds for 11 documents (with batching)

Consider:
- Using a smaller/faster model
- Reducing `summary_sentences` or `summary_max_words`
- Disabling summarization for large datasets

## Related Documentation

- [Chunker Operator Reference](../../../docs/operators/chunker.md)
- [Summarization Service Architecture](../../../ARCHITECTURE.md#summarization-service)
- [LiteLLM Integration](../../../src/datasift/core/operators/functional/embeddings/adapters/outbound/README_LITELLM.md)