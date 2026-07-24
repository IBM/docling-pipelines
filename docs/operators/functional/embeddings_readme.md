# EmbeddingsOperator

Generates dense vector embeddings from document text using a configurable AI provider.

- **Short Name:** `embeddings`
- **Category:** Functional

---

## Overview

`EmbeddingsOperator` converts document text (or pre-chunked content) into float vector
embeddings suitable for similarity search and RAG pipelines. It supports HuggingFace (local
and API), LiteLLM (100+ providers including Ollama, OpenAI, Azure, Cohere, AWS), and WatsonX
through a unified adapter architecture. Long text is automatically split and averaged when it
exceeds the model token limit.

---

## Key Features

- Three provider backends: HuggingFace, LiteLLM, WatsonX
- Local inference (HuggingFace) — no API key, no cost, offline capable, tested to 600+ parallel processes
- Automatic chunking of text that exceeds `token_limit`
- Per-document error handling — failed documents are logged and skipped
- Configurable output column name (`embeddings_column`)
- Works with both `content` (full text) and `chunked_content` (pre-chunked) inputs

---

## Operator Configuration

```json
{
  "type": "embeddings",
  "name": "generate_embeddings",
  "config": {
    "provider": "litellm",
    "provider_config": {
      "model_id": "openai/nomic-embed-text",
      "api_base": "http://localhost:11434"
    },
    "embeddings_column": "embeddings",
    "doc_column": "content"
  },
  "depends_on": ["chunk_documents"]
}
```

---

## Parameters

### Common parameters

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `provider` | string | **Yes** | `"litellm"` | Provider: `huggingface`, `litellm`, `watsonx` |
| `provider_config` | object | Varies | — | Provider-specific config including `model_id` (see below) |
| `embeddings_column` | string | No | `"embeddings"` | Output column name for generated embeddings |
| `doc_column` | string | No | `"content"` | Input column containing text to embed |
| `overlap_ratio` | float | No | `0.2` | Overlap ratio when auto-chunking long text (0.0–0.5) |
| `token_limit` | integer | No | `8192` | Max token limit; text beyond this is auto-chunked and averaged |

### HuggingFace `provider_config`

| Field | Type | Default | Description |
|---|---|---|---|
| `model_id` | string | Required | HuggingFace model name (e.g. `sentence-transformers/all-MiniLM-L6-v2`) |
| `use_local` | boolean | `true` | Use local inference vs HuggingFace Inference API |
| `device` | string | `"cpu"` | Device for local inference: `cpu`, `cuda`, `mps` |
| `api_token` | string | — | HuggingFace API token (required when `use_local: false`) |
| `batch_size` | integer | `32` | Texts per batch |

### LiteLLM `provider_config`

| Field | Type | Default | Description |
|---|---|---|---|
| `model_id` | string | Required | Model with provider prefix (e.g. `openai/nomic-embed-text` for Ollama) |
| `api_key` | string | — | Provider API key (or set env var) |
| `api_base` | string | — | Custom endpoint URL (e.g. `http://localhost:11434` for Ollama) |
| `batch_size` | integer | `32` | Texts per batch |
| `timeout` | integer | `120` | Request timeout in seconds |

### WatsonX `provider_config`

| Field | Type | Default | Description |
|---|---|---|---|
| `model_id` | string | Required | WatsonX model (e.g. `ibm/slate-125m-english-rtrvr`) |
| `api_key` | string | Required | IBM Cloud API key |
| `api_base` | string | Required | WatsonX endpoint URL |
| `container_kind` | string | `"project"` | `"project"` or `"space"` |
| `container_id` | string | Required | Project or space UUID |
| `batch_size` | integer | `800` | Texts per batch |
| `enable_rate_limiting` | boolean | `false` | Enable 7 req/s rate limiting |

---

## Output Columns

All input columns are preserved. The operator appends:

| Column | PyArrow Type | Description |
|---|---|---|
| `embeddings` (or `embeddings_column`) | `list<float32>` | Dense embedding vector. For chunked input, a list of vectors (one per chunk). |

---

## Examples

### Example 1 — Ollama via LiteLLM (local)

```json
{
  "type": "embeddings",
  "name": "embed",
  "config": {
    "provider": "litellm",
    "provider_config": {
      "model_id": "openai/nomic-embed-text",
      "api_base": "http://localhost:11434"
    }
  },
  "depends_on": ["chunk"]
}
```

### Example 2 — HuggingFace local inference

```json
{
  "type": "embeddings",
  "name": "embed",
  "config": {
    "provider": "huggingface",
    "provider_config": {
      "model_id": "sentence-transformers/all-MiniLM-L6-v2",
      "use_local": true,
      "device": "cpu",
      "batch_size": 16
    }
  },
  "depends_on": ["chunk"]
}
```

### Example 3 — WatsonX native

```json
{
  "type": "embeddings",
  "name": "embed",
  "config": {
    "provider": "watsonx",
    "provider_config": {
      "model_id": "ibm/slate-125m-english-rtrvr",
      "api_key": "${WATSONX_API_KEY}",
      "api_base": "${WATSONX_API_BASE}",
      "container_id": "${WATSONX_PROJECT_ID}",
      "container_kind": "project",
      "batch_size": 800,
      "enable_rate_limiting": true
    }
  },
  "depends_on": ["chunk"]
}
```

### Example 4 — OpenAI via LiteLLM

```json
{
  "type": "embeddings",
  "name": "embed",
  "config": {
    "provider": "litellm",
    "provider_config": {
      "model_id": "openai/text-embedding-3-small",
      "api_key": "${OPENAI_API_KEY}"
    }
  },
  "depends_on": ["chunk"]
}
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ConfigurationError: Unknown provider 'invalid'` | Typo in `provider` | Use one of: `huggingface`, `litellm`, `watsonx` |
| `ExternalServiceError: Model '…' not found` | Wrong `model_id` | Check model name against provider docs |
| `The api_key client option must be set` | Missing API key | Set `OPENAI_API_KEY`, `HUGGINGFACE_API_KEY`, etc. as env vars |
| Ollama connection refused | Ollama not running | Run `ollama serve && ollama pull <model>` |
| `chunked_content` column not found | Chunker was skipped | Add `ChunkerOperator` before this step; a validation warning is also emitted |
| Slow throughput with HuggingFace API | Rate limits | Switch to `use_local: true` for local inference |

### API key best practice

Store keys as environment variables — never in flow files committed to git:

```bash
export OPENAI_API_KEY=sk-...
export WATSONX_API_KEY=...
export HUGGINGFACE_API_KEY=hf_...
```

---

## Architecture

### Provider selection guide

| Use case | Recommended provider | Example model |
|---|---|---|
| Local / offline / high-concurrency | HuggingFace (local) | `sentence-transformers/all-MiniLM-L6-v2` |
| Privacy-sensitive workloads | HuggingFace (local) | `sentence-transformers/all-MiniLM-L6-v2` |
| Ollama (local LLM server) | LiteLLM | `openai/nomic-embed-text` |
| Production quality | LiteLLM (OpenAI) | `openai/text-embedding-3-large` |
| Multilingual | LiteLLM (Cohere) | `cohere/embed-multilingual-v3.0` |
| IBM enterprise | WatsonX native | `ibm/slate-125m-english-rtrvr` |

### LiteLLM model prefix reference

| Provider | Prefix | Example |
|---|---|---|
| Ollama | `openai/` | `openai/nomic-embed-text` |
| OpenAI | `openai/` | `openai/text-embedding-3-small` |
| Azure OpenAI | `azure/` | `azure/text-embedding-ada-002` |
| Cohere | `cohere/` | `cohere/embed-english-v3.0` |
| AWS Bedrock | `bedrock/` | `bedrock/amazon.titan-embed-text-v1` |
| HuggingFace API | `huggingface/` | `huggingface/sentence-transformers/all-MiniLM-L6-v2` |
| WatsonX via LiteLLM | `watsonx/` | `watsonx/ibm/slate-125m-english-rtrvr` |

### Typical pipeline position

```
Ingest → Extract → Chunker → EmbeddingsOperator → VectorDB
```

### Sample flow

See [`sample_flows/use_cases/invoice_processing.json`](../../../sample_flows/use_cases/invoice_processing.json).

## References

- [Operator Reference](../../reference/OPERATORS.md#embeddingsoperator)
- [Architecture Guide](../../../ARCHITECTURE.md)
- [HuggingFace Sentence Transformers](https://www.sbert.net/)
- [IBM watsonx.ai Documentation](https://www.ibm.com/watsonx/developer/)
- [OpenAI Embeddings Guide](https://platform.openai.com/docs/guides/embeddings)
- [LiteLLM Documentation](https://docs.litellm.ai/)
