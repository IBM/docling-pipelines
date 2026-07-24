# ChunkerOperator

Splits document text into overlapping chunks for embedding generation and vector storage.

- **Short Name:** `chunker`
- **Category:** Functional

---

## Overview

`ChunkerOperator` breaks extracted document text into smaller, contextually coherent pieces
(chunks) that fit within embedding model token limits. It supports three strategies — simple
fixed-size, semantic content-aware, and hybrid Docling-based — and can optionally summarise
each chunk using an LLM.

Chunking can run locally (default) or be offloaded to a remote `docling-serve` instance for
distributed workloads.

---

## Key Features

- Three chunking strategies: `simple`, `semantic`, `hybrid`
- Optional LLM-based chunk summarisation (LiteLLM or WatsonX)
- Remote chunking via `docling-serve` API
- Configurable chunk size and overlap
- Optionally retains the original content column alongside chunks
- Outputs `chunk_sequence_number` and `start_index` for precise retrieval

---

## Operator Configuration

```json
{
  "type": "chunker",
  "name": "chunk_documents",
  "config": {
    "chunk_type": "hybrid",
    "chunk_size": 512,
    "chunk_overlap": 128,
    "provider": "docling_library",
    "doc_column": "content",
    "retain_original_content": false
  },
  "depends_on": ["extract_documents"]
}
```

---

## Parameters

### Common parameters

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `chunk_type` | string | No | `"simple"` | Chunking strategy: `simple`, `semantic`, or `hybrid` |
| `chunk_size` | integer | No | `2048` | Max chunk size — characters for `simple`, tokens for `hybrid`; ignored by `semantic` |
| `chunk_overlap` | integer | No | `200` | Overlap between consecutive chunks (characters or tokens). Max `512`. |
| `doc_column` | string | No | `"content"` | Input column containing text to chunk |
| `retain_original_content` | boolean | No | `false` | Keep the original content column in the output table |
| `docling_tokenizer` | string | No | `"sentence-transformers/all-MiniLM-L6-v2"` | HuggingFace tokenizer for `hybrid` chunking only |

### Semantic chunking parameters

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `semantic_embeddings_model` | string | Yes (semantic) | — | Ollama model for semantic boundary detection (e.g. `nomic-embed-text`) |
| `breakpoint_threshold_type` | string | No | `"percentile"` | Split heuristic: `percentile`, `standard_deviation`, `interquartile`, `gradient` |
| `breakpoint_threshold_amount` | float | No | null | Threshold value for the chosen heuristic (e.g. `95.0` for percentile) |

### Remote (docling-serve) chunking parameters

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `provider` | string | No | null | `"docling_library"` (local) or `"docling_serve"` (remote) |
| `provider_config.api_base` | string | Yes (remote) | — | Base URL of docling-serve instance |
| `provider_config.api_key` | string | No | — | API key for docling-serve |
| `provider_config.timeout` | integer | No | `300` | Request timeout in seconds |
| `provider_config.poll_interval` | integer | No | `2` | Polling interval for async requests |
| `provider_config.max_retries` | integer | No | `3` | Maximum retry attempts |
| `provider_config.verify_ssl` | boolean | No | `true` | Set `false` for self-signed certificates |

### Summarisation parameters (`summarization` object)

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `summarization.provider` | string | No | `"litellm"` | LLM provider: `litellm` or `watsonx` |
| `summarization.provider_config` | object | Yes (if summarization) | — | Provider-specific config including `model_id` |
| `summarization.summary_sentences` | integer | No | `2` | Target sentences per summary (1–5) |
| `summarization.summary_max_words` | integer | No | `20` | Max words per summary (10–100) |
| `summarization.max_input_tokens` | integer | No | `8000` | Max tokens per LLM request (1000–32000) |

---

## Output Columns

All original columns (except `content` when `retain_original_content: false`) are preserved.

| Column | PyArrow Type | Description |
|---|---|---|
| `chunked_content` | `list<struct<chunk: string, start_index: int64, summary: string?>>` | Array of chunk objects |
| `chunk_sequence_number` | `int64` | Sequential chunk index within the source document |
| `start_index` | `int64` | Token/character position of the chunk in the source document |

Each item in `chunked_content`:
- `chunk` — text content of the chunk
- `start_index` — position in the original text
- `summary` — present only when summarisation is enabled

---

## Examples

### Example 1 — Simple chunking

```json
{
  "type": "chunker",
  "name": "simple_chunker",
  "config": {
    "chunk_type": "simple",
    "chunk_size": 1000,
    "chunk_overlap": 200,
    "doc_column": "content"
  },
  "depends_on": ["extract"]
}
```

### Example 2 — Semantic chunking

```json
{
  "type": "chunker",
  "name": "semantic_chunker",
  "config": {
    "chunk_type": "semantic",
    "semantic_embeddings_model": "nomic-embed-text",
    "breakpoint_threshold_type": "percentile",
    "breakpoint_threshold_amount": 95.0,
    "doc_column": "content"
  },
  "depends_on": ["extract"]
}
```

### Example 3 — Hybrid chunking with summarisation

```json
{
  "type": "chunker",
  "name": "hybrid_chunker",
  "config": {
    "chunk_type": "hybrid",
    "provider": "docling_library",
    "chunk_size": 512,
    "chunk_overlap": 50,
    "docling_tokenizer": "sentence-transformers/all-MiniLM-L6-v2",
    "summarization": {
      "provider": "litellm",
      "provider_config": {
        "model_id": "llama3.2",
        "api_base": "http://localhost:11434/v1",
        "api_key": "<ollama>"
      },
      "summary_sentences": 2,
      "summary_max_words": 30
    }
  },
  "depends_on": ["extract"]
}
```

### Example 4 — Remote chunking via docling-serve

```json
{
  "type": "chunker",
  "name": "remote_chunker",
  "config": {
    "chunk_type": "hybrid",
    "chunk_size": 512,
    "chunk_overlap": 128,
    "provider": "docling_serve",
    "provider_config": {
      "api_base": "https://docling-serve.example.com",
      "timeout": 120,
      "max_retries": 3
    }
  },
  "depends_on": ["extract"]
}
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Connection to docling-serve timed out` | Remote service unreachable | Verify `api_base` is correct and the service is running; increase `timeout` |
| `Docling-serve returned no chunks` | Empty or non-markdown input | Verify the `doc_column` column contains non-empty markdown text |
| SSL verification errors | Self-signed certificate on docling-serve | Set `provider_config.verify_ssl: false` for testing; use a valid cert in production |
| Semantic chunking hangs | Ollama not running | Start Ollama: `ollama serve && ollama pull <model>` |
| Very large number of tiny chunks | `chunk_size` is too small | Increase `chunk_size`; recommend 512–1024 tokens for hybrid |
| Downstream embeddings fail | Input column name mismatch | Ensure the `doc_column` matches what `ExtractOperator` writes (default: `content`) |

---

## Architecture

### Strategy selection guide

| Strategy | Best for | Dependencies |
|---|---|---|
| `simple` | Quick prototyping, plain text | None |
| `semantic` | Narrative text where sentence boundaries matter | Ollama |
| `hybrid` | Structured documents (PDFs with sections, tables) | Docling library or docling-serve |

### Chunk size guidance

- **512–1024 tokens**: Better for precise retrieval
- **1024–2048 tokens**: Better for preserving context
- **Overlap**: Recommend 10–25% of chunk size (e.g. 128 for 512)

### Typical pipeline position

```
Ingest → Extract → Chunker → Embeddings → VectorDB
```

### Sample flow

See [`sample_flows/use_cases/invoice_processing.json`](../../../sample_flows/use_cases/invoice_processing.json).

- **ExtractOperator**: Extracts text content for chunking
- **EmbeddingsOperator**: Generates embeddings from chunks
- **VectorDBOperator**: Stores chunked and embedded content
- **BranchingOperator**: Enables conditional chunking strategies

## References

- [Docling Documentation](https://github.com/DS4SD/docling)
- [Docling-serve API](https://github.com/DS4SD/docling-serve)
- [ARCHITECTURE.md](../../../ARCHITECTURE.md) - System architecture overview
