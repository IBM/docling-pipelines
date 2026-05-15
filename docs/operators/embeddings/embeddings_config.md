# Embeddings Operator - Configuration Reference

## Overview

The Embeddings Operator generates vector embeddings for text content using various embedding providers. It supports multiple providers (Ollama, HuggingFace, LiteLLM, and Watsonx) and handles chunking of long text, batch processing, and error handling per document.

- **Operator Name:** `embeddings`
- **Category**: Functional
- **Short Name**: `embeddings`

## Configuration Parameters

### 1. `embeddings_type` (String)
**Type:** String
**Required:** Yes
**Default:** `"ollama"`
**Description:** Embedding provider type.

**Valid Values:**
- `"ollama"` - Local Ollama models (nomic-embed-text, llama2, etc.)
- `"huggingface"` - HuggingFace models (all-MiniLM-L6-v2, mpnet-base-v2, etc.)
- `"litellm"` - 100+ providers via LiteLLM (OpenAI, Azure, Anthropic, Cohere, etc.)
- `"watsonx"` - Native IBM watsonx.ai integration

**Examples:**
```json
"embeddings_type": "ollama"
"embeddings_type": "huggingface"
"embeddings_type": "litellm"
"embeddings_type": "watsonx"
```

### 2. `embeddings_model_id` (String)
**Type:** String
**Required:** Yes
**Default:** `"llama2"`
**Description:** Model name for the selected provider.

**Valid Values:**

**Ollama Models:**
- `"nomic-embed-text"` - Nomic Embed Text (recommended for embeddings)
- `"granite4"` - IBM Granite 4
- `"llama3.2"` - Meta Llama 3.2
- `"llama2"` - Meta Llama 2
- Any Ollama-compatible model

**HuggingFace Models:**
- `"sentence-transformers/all-MiniLM-L6-v2"` - Fast, 384-dim
- `"sentence-transformers/all-mpnet-base-v2"` - High quality, 768-dim
- `"sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"` - Multilingual
- Any HuggingFace embedding model

**LiteLLM Models:**
- `"watsonx/ibm/slate-125m-english-rtrvr"` - IBM watsonx.ai (via LiteLLM)
- `"watsonx/ibm/slate-30m-english-rtrvr"` - IBM watsonx.ai (via LiteLLM)
- `"text-embedding-3-small"` - OpenAI (1536-dim)
- `"text-embedding-ada-002"` - OpenAI (1536-dim)
- `"embed-english-v3.0"` - Cohere
- `"amazon.titan-embed-text-v1"` - AWS Bedrock
- 100+ more providers

**Watsonx Models:**
- `"ibm/slate-125m-english-rtrvr"` - IBM watsonx.ai
- `"ibm/slate-30m-english-rtrvr"` - IBM watsonx.ai
- Any watsonx.ai embedding model

**Examples:**
```json
"embeddings_model_id": "watsonx/ibm/slate-125m-english-rtrvr"
"embeddings_model_id": "nomic-embed-text"
"embeddings_model_id": "sentence-transformers/all-MiniLM-L6-v2"
"embeddings_model_id": "text-embedding-3-small"
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

### 5. `provider_config` (JSON)
**Type:** JSON Object
**Required:** No
**Description:** Additional configuration parameters for the embedding provider.

**For Ollama:**
- No additional configuration required (uses defaults)

**For HuggingFace:**
- `device` (String, Optional): Device to use ("cpu", "cuda", "mps")
- `normalize_embeddings` (Boolean, Optional): Normalize embeddings (default: true)

**For LiteLLM:**
- `api_key` (String, Required): API key for the provider
- `api_base` (String, Optional): Custom API endpoint
- `api_version` (String, Optional): API version (for Azure)
- Additional provider-specific parameters

**For Watsonx:**
- `api_key` (String, Required): IBM Cloud API key
- `api_base` (String, Required): watsonx.ai service URL
- `container_id` (String, Required): Project or space ID
- `container_kind` (String, Optional): "project" or "space" (default: "project")
- `enable_rate_limiting` (Boolean, Optional): Enable rate limiting (7 req/s) for WatsonX API calls (default: false)

**Examples:**

LiteLLM (IBM watsonx.ai):
```json
"provider_config": {
  "api_key": "${WATSONX_API_KEY}", # pragma: allowlist secret
  "api_base": "https://us-south.ml.cloud.ibm.com",
  "project_id": "${WATSONX_PROJECT_ID}"
}
```

Watsonx:
```json
"provider_config": {
  "api_key": "${WATSONX_API_KEY}", # pragma: allowlist secret
  "api_base": "${WATSONX_API_BASE}",
  "container_id": "${WATSONX_CONTAINER_ID}",
  "container_kind": "project",
  "enable_rate_limiting": true
}
```

HuggingFace:
```json
"provider_config": {
  "device": "cuda",
  "normalize_embeddings": true
}
```

LiteLLM (OpenAI):
```json
"provider_config": {
  "api_key": "${OPENAI_API_KEY}", # pragma: allowlist secret
  "api_base": "https://api.openai.com/v1"
}
```

LiteLLM (Azure):
```json
"provider_config": {
  "api_key": "${AZURE_API_KEY}", # pragma: allowlist secret
  "api_base": "https://your-resource.openai.azure.com",
  "api_version": "2023-05-15"
}
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

### 2. `doc_id_hash` (String)
**Description:** Unique hash identifier for the document (auto-generated if not present).
**Type:** String
**Available for Vector DB:** Yes
**Tags:** `mandatory`, `internal_feature`

## Configuration Examples

### Example 1: IBM watsonx.ai Embeddings via LiteLLM
```json
{
  "id": "30953cfb-a3a2-4688-9aea-ff9fff10f7bd",
  "operator": "embeddings",
  "config": {
    "embeddings_type": "litellm",
    "embeddings_model_id": "watsonx/ibm/slate-125m-english-rtrvr",
    "embeddings_column": "embeddings",
    "batch_size": 64,
    "provider_config": {
      "api_key": "${WATSONX_API_KEY}", # pragma: allowlist secret
      "api_base": "https://us-south.ml.cloud.ibm.com",
      "project_id": "${WATSONX_PROJECT_ID}"
    }
  }
}
```

### Example 2: Watsonx.ai Embeddings
```json
{
  "id": "30953cfb-a3a2-4688-9aea-ff9fff10f7bd",
  "operator": "embeddings",
  "config": {
    "embeddings_type": "watsonx",
    "embeddings_model_id": "ibm/slate-125m-english-rtrvr",
    "embeddings_column": "embeddings",
    "batch_size": 64,
    "provider_config": {
      "api_key": "${WATSONX_API_KEY}", # pragma: allowlist secret
      "api_base": "${WATSONX_API_BASE}",
      "container_id": "${WATSONX_CONTAINER_ID}",
      "container_kind": "project",
      "enable_rate_limiting": true
    }
  }
}
```

### Example 3: Ollama Embeddings (Local)
```json
{
  "id": "30953cfb-a3a2-4688-9aea-ff9fff10f7bd",
  "operator": "embeddings",
  "config": {
    "embeddings_type": "ollama",
    "embeddings_model_id": "nomic-embed-text",
    "embeddings_column": "embeddings",
    "overlap_ratio": 0.2,
    "batch_size": 32
  }
}
```

### Example 4: HuggingFace Embeddings (GPU)
```json
{
  "id": "30953cfb-a3a2-4688-9aea-ff9fff10f7bd",
  "operator": "embeddings",
  "config": {
    "embeddings_type": "huggingface",
    "embeddings_model_id": "sentence-transformers/all-mpnet-base-v2",
    "embeddings_column": "embeddings",
    "batch_size": 64,
    "provider_config": {
      "device": "cuda",
      "normalize_embeddings": true
    }
  }
}
```

### Example 5: OpenAI Embeddings via LiteLLM
```json
{
  "id": "30953cfb-a3a2-4688-9aea-ff9fff10f7bd",
  "operator": "embeddings",
  "config": {
    "embeddings_type": "litellm",
    "embeddings_model_id": "text-embedding-3-small",
    "embeddings_column": "embeddings",
    "batch_size": 100,
    "provider_config": {
      "api_key": "${OPENAI_API_KEY}" # pragma: allowlist secret
    }
  }
}
```

### Example 6: Cohere Embeddings via LiteLLM
```json
{
  "id": "30953cfb-a3a2-4688-9aea-ff9fff10f7bd",
  "operator": "embeddings",
  "config": {
    "embeddings_type": "litellm",
    "embeddings_model_id": "embed-english-v3.0",
    "embeddings_column": "embeddings",
    "batch_size": 96,
    "provider_config": {
      "api_key": "${COHERE_API_KEY}" # pragma: allowlist secret
    }
  }
}
```

## Best Practices

1. **Provider Selection**:
   - Use **Ollama** for development and privacy-sensitive applications
   - Use **HuggingFace** for local deployment with GPU acceleration
   - Use **LiteLLM** for production with managed services (100+ providers)
   - Use **Watsonx** for IBM Cloud enterprise deployments

2. **Model Selection**:
   - Choose models with appropriate dimensions for your use case
   - Smaller models generally mean faster inference and less vector storage
   - Larger models generally mean higher quality and more vector storage

3. **Batch Size**:
   - Increase for better throughput (32-128)
   - Decrease if running out of memory (8-16)
   - Test with your hardware configuration

4. **Chunking**:
   - Use Chunker operator before Embeddings for better control
   - Embeddings operator auto-chunks long text if needed
   - Adjust `overlap_ratio` for context preservation

5. **Performance**:
   - Ollama: ~1000 docs/min (local)
   - HuggingFace: ~2000 docs/min (GPU)
   - LiteLLM: ~500 docs/min (API rate limits)

6. **Error Handling**:
   - Operator handles per-document errors gracefully
   - Failed documents are logged and skipped
   - Check metadata for failed_docs_count

## Validation Rules

- `embeddings_type` must be one of: ollama, huggingface, litellm, watsonx
- `embeddings_model_id` must be a non-empty string
- `overlap_ratio` must be between 0.0 and 0.5
- `batch_size` must be between 1 and 128
- Input data must have `content` column or `chunked_content` column
- For LiteLLM, `provider_config` with `api_key` is required
- For Watsonx, `provider_config.api_key`, `provider_config.api_base`, and `provider_config.container_id` are required

## Complete Flow Example

- [Sample Flow](tests/sample_test_flows/invoice_processing/flow_invoice_process.json)
