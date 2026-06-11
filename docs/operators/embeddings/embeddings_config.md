# Embeddings Operator - Configuration Reference

## Overview

The Embeddings Operator generates vector embeddings for text content using HuggingFace, LiteLLM, and Watsonx providers. It leverages the unified adapter architecture for consistent integration and handles chunking of long text, batch processing, and error handling per document.

**Supported Providers:**
- **HuggingFace**: Native local or API-based inference with sentence-transformers models
- **LiteLLM**: Access to 100+ providers including OpenAI, Azure, Anthropic, Cohere, AWS Bedrock, Ollama, HuggingFace API, and more
- **Watsonx**: Native IBM watsonx.ai integration for enterprise deployments

**Note:** For Ollama models, use LiteLLM with `openai/` prefix (e.g., `openai/nomic-embed-text`). For HuggingFace, you can use either native provider (`provider: "huggingface"`) for local inference or LiteLLM (`provider: "litellm"` with `huggingface/` prefix) for API access.

- **Operator Name:** `embeddings`
- **Category**: Functional
- **Short Name**: `embeddings`

## Configuration Parameters

**Configuration Structure:**
The EmbeddingsOperator uses a nested configuration structure where provider-specific parameters (like `model_id`, `api_key`, `api_base`, etc.) are grouped under the `provider_config` object. This ensures clean separation between operator-level parameters and provider-specific settings.

### 1. `provider` (String)
**Type:** String
**Required:** Yes
**Default:** `"litellm"`
**Description:** Embedding provider type. Uses unified adapter architecture.

**Valid Values:**
- `"huggingface"` - Native HuggingFace local or API embeddings
- `"litellm"` - 100+ providers via LiteLLM (OpenAI, Azure, Anthropic, Cohere, Ollama, HuggingFace API, etc.)
- `"watsonx"` - Native IBM watsonx.ai integration

**Examples:**
```json
"provider": "huggingface"
"provider": "litellm"
"provider": "watsonx"
```

### 2. `provider_config` (Object)
**Type:** JSON Object
**Required:** Varies by provider
**Description:** Provider-specific configuration parameters including model_id.

**For LiteLLM:**
- `model_id` (String, Required): Model identifier with provider prefix
  - Ollama: `"openai/nomic-embed-text"`, `"openai/granite4"`, `"openai/llama3.2"`
  - HuggingFace: `"huggingface/sentence-transformers/all-MiniLM-L6-v2"`
  - OpenAI: `"text-embedding-3-small"`, `"text-embedding-3-large"`
  - Cohere: `"embed-english-v3.0"`, `"embed-multilingual-v3.0"`
  - AWS Bedrock: `"bedrock/amazon.titan-embed-text-v1"`
  - Azure: `"azure/text-embedding-ada-002"`
- `api_key` (String, Optional): API key for authentication
- `api_base` (String, Optional): Custom API endpoint (e.g., `"http://localhost:11434"` for Ollama)
- `batch_size` (Integer, Optional): Batch size for processing (default: 32)
- `timeout` (Integer, Optional): Request timeout in seconds (default: 120)

**Valid Values:**

**Note:** All model IDs listed below are values for `provider_config.model_id`, not standalone parameters.

**LiteLLM Models (100+ providers):**
- **Ollama** (prefix: `openai/`):
  - `"openai/nomic-embed-text"` - Nomic Embed Text (recommended)
  - `"openai/granite4"` - IBM Granite 4
  - `"openai/llama3.2"` - Meta Llama 3.2
  - Any Ollama-compatible model with `openai/` prefix

- **HuggingFace API via LiteLLM** (prefix: `huggingface/`):
  - `"huggingface/sentence-transformers/all-MiniLM-L6-v2"` - Fast, 384-dim
  - `"huggingface/sentence-transformers/all-mpnet-base-v2"` - High quality, 768-dim
  - `"huggingface/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"` - Multilingual
  - Any HuggingFace embedding model with `huggingface/` prefix (requires API token)

- **OpenAI**:
  - `"openai/text-embedding-3-small"` - OpenAI (1536-dim)
  - `"openai/text-embedding-3-large"` - OpenAI (3072-dim)
  - `"openai/text-embedding-ada-002"` - OpenAI (1536-dim)

- **Cohere**:
  - `"cohere/embed-english-v3.0"` - Cohere English
  - `"cohere/embed-multilingual-v3.0"` - Cohere Multilingual

- **AWS Bedrock**:
  - `"bedrock/amazon.titan-embed-text-v1"` - AWS Bedrock
  - `"bedrock/cohere.embed-english-v3"` - Cohere on Bedrock

- **Azure OpenAI** (prefix: `azure/`):
  - `"azure/text-embedding-ada-002"` - Azure OpenAI

- **Watsonx via LiteLLM** (prefix: `watsonx/`):
  - `"watsonx/ibm/slate-125m-english-rtrvr"` - IBM watsonx.ai
  - `"watsonx/ibm/slate-30m-english-rtrvr"` - IBM watsonx.ai

**Watsonx Models (Native):**
- `"ibm/slate-125m-english-rtrvr"` - IBM watsonx.ai (768-dim)
- `"ibm/slate-30m-english-rtrvr"` - IBM watsonx.ai (384-dim)
- Any watsonx.ai embedding model

**HuggingFace Models (Native Provider):**
- `"sentence-transformers/all-MiniLM-L6-v2"` - Fast, 384-dim (recommended for high-concurrency)
- `"sentence-transformers/all-mpnet-base-v2"` - High quality, 768-dim
- `"sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"` - Multilingual
- `"BAAI/bge-small-en-v1.5"` - Good for English, 384-dim
- Any sentence-transformers compatible model (no prefix needed)

**Examples:**

LiteLLM with various providers:
```json
"provider_config": {
  "model_id": "openai/nomic-embed-text"                              // Ollama via LiteLLM
}
"provider_config": {
  "model_id": "huggingface/sentence-transformers/all-MiniLM-L6-v2"   // HuggingFace API via LiteLLM
}
"provider_config": {
  "model_id": "sentence-transformers/all-MiniLM-L6-v2"               // Native HuggingFace local
}
"provider_config": {
  "model_id": "openai/text-embedding-3-small"                        // OpenAI via LiteLLM
}
"provider_config": {
  "model_id": "watsonx/ibm/slate-125m-english-rtrvr"                 // Watsonx via LiteLLM
}
```

LiteLLM with OpenAI:
```json
"provider_config": {
  "model_id": "openai/text-embedding-3-small",
  "api_key": "${OPENAI_API_KEY}"
}
```

Watsonx:
```json
"provider_config": {
  "model_id": "ibm/slate-125m-english-rtrvr",
  "api_key": "${WATSONX_API_KEY}",
  "api_base": "https://us-south.ml.cloud.ibm.com",
  "container_id": "${WATSONX_PROJECT_ID}",
  "container_kind": "project",
  "batch_size": 800,
  "enable_rate_limiting": true
}
```

### 3. `embeddings_column` (String)
**Type:** String
**Required:** No
**Default:** `"embeddings"`
**Description:** Name of the output column for embeddings.

**Examples:**
```json
"embeddings_column": "embeddings"
```

### 4. `overlap_ratio` (Float)
**Type:** Float
**Required:** No
**Default:** `0.2`
**Description:** Overlap ratio for chunking long text that exceeds model token limits.

**Valid Values:**
- Minimum: `0.0` (no overlap)
- Maximum: `0.5` (50% overlap)
- Recommended: `0.2` (20% overlap)

**Examples:**
```json
"overlap_ratio": 0.2
"overlap_ratio": 0.3
```

## Output Features

### 1. `embeddings` (Vector)
**Description:** Dense vector embeddings for similarity search.
**Type:** List of floats (vector)
**Available for Vector DB:** Yes (Mandatory)

**For Chunked Content:**
- Returns list of vectors (one per chunk)
- Each chunk gets its own embedding

**For Full Documents:**
- Returns single vector for entire document
- Long documents are automatically chunked and averaged


## Configuration Examples

### Example 1: IBM watsonx.ai Embeddings via LiteLLM
```json
{
  "operator": "embeddings",
  "config": {
    "provider": "litellm",
    "provider_config": {
      "model_id": "watsonx/ibm/slate-125m-english-rtrvr",
      "api_base": "https://us-south.ml.cloud.ibm.com",
      "api_key": "${WATSONX_API_KEY}", # pragma: allowlist secret
      "container_id": "${WATSONX_PROJECT_ID}",
      "container_kind": "project"
    },
    "embeddings_column": "embeddings"
  }
}
```

### Example 2: Watsonx.ai Embeddings (Native)
```json
{
  "operator": "embeddings",
  "config": {
    "provider": "watsonx",
    "provider_config": {
      "model_id": "ibm/slate-125m-english-rtrvr",
      "api_key": "${WATSONX_API_KEY}", # pragma: allowlist secret
      "api_base": "${WATSONX_API_BASE}",
      "container_id": "${WATSONX_PROJECT_ID}",
      "container_kind": "project",
      "batch_size": 800,
      "enable_rate_limiting": true
    },
    "embeddings_column": "embeddings"
  }
}
```

### Example 3: Ollama Embeddings via LiteLLM (Local)
```json
{
  "operator": "embeddings",
  "config": {
    "provider": "litellm",
    "provider_config": {
      "model_id": "openai/nomic-embed-text",
      "api_base": "http://localhost:11434",
      "batch_size": 32
    },
    "embeddings_column": "embeddings",
    "overlap_ratio": 0.2
  }
}
```

### Example 4: HuggingFace Embeddings via LiteLLM
```json
{
  "operator": "embeddings",
  "config": {
    "provider": "litellm",
    "provider_config": {
      "model_id": "huggingface/sentence-transformers/all-mpnet-base-v2",
      "api_key": "${HUGGINGFACE_API_KEY}" # pragma: allowlist secret
    },
    "embeddings_column": "embeddings"
  }
}
```

### Example 5: OpenAI Embeddings via LiteLLM
```json
{
  "operator": "embeddings",
  "config": {
    "provider": "litellm",
    "provider_config": {
      "model_id": "openai/text-embedding-3-small",
      "api_key": "${OPENAI_API_KEY}" # pragma: allowlist secret
    },
    "embeddings_column": "embeddings"
  }
}
```

### Example 6: Cohere Embeddings via LiteLLM
```json
{
  "operator": "embeddings",
  "config": {
    "provider": "litellm",
    "provider_config": {
      "model_id": "cohere/embed-english-v3.0",
      "api_key": "${COHERE_API_KEY}" # pragma: allowlist secret
    },
    "embeddings_column": "embeddings"
  }
}
```

## Best Practices

1. **Provider Selection**:
   - Use **LiteLLM** for maximum flexibility (100+ providers including Ollama, HuggingFace, OpenAI, etc.)
   - Use **Watsonx (Native)** for IBM Cloud enterprise deployments with advanced features
   - For Ollama: Use LiteLLM with `openai/` prefix for local development
   - For HuggingFace: Use LiteLLM with `huggingface/` prefix for model access

2. **Model Selection**:
   - Choose models with appropriate dimensions for your use case
   - Smaller models generally mean faster inference and less vector storage
   - Larger models generally mean higher quality and more vector storage

3. **Batch Processing**:
   - LiteLLM handles batching internally based on provider capabilities
   - Watsonx native adapter supports configurable batch sizes (default: 800)
   - Adjust based on your provider's rate limits and quotas

4. **Chunking**:
   - Use Chunker operator before Embeddings for better control
   - Embeddings operator auto-chunks long text if needed
   - Adjust `overlap_ratio` for context preservation

5. **Performance**:
   - Ollama via LiteLLM: ~1000 docs/min (local)
   - HuggingFace via LiteLLM: ~500-2000 docs/min (depends on API/local)
   - OpenAI via LiteLLM: ~500 docs/min (API rate limits)
   - Watsonx: ~800 docs/min (with rate limiting enabled)

6. **Error Handling**:
   - Operator handles per-document errors gracefully
   - Failed documents are logged and skipped
   - Check metadata for failed_docs_count

## Validation Rules

- `provider` must be one of: huggingface, litellm, watsonx
- `provider_config.model_id` must be a non-empty string
- `overlap_ratio` must be between 0.0 and 0.5
- Input data must have `content` column or `chunked_content` column
- For LiteLLM, `provider_config.model_id` is required; `provider_config.api_key` required for most providers
- For Watsonx, `provider_config.model_id`, `provider_config.api_key`, `provider_config.api_base`, `provider_config.container_id`, and `provider_config.container_kind` are required

### Validation Warnings

- **Missing Chunker Warning**: If the `chunked_content` feature is not available (i.e., no Chunker operator before Embeddings), a validation warning will be generated. Using a Chunker operator before Embeddings provides better control over chunk size and overlap, resulting in more optimal embeddings.

## Complete Flow Example

- [Sample Flow](../../../tests/sample_test_flows/invoice_processing/flow_invoice_process.json)
