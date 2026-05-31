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

**Migration Note:** The old `embeddings_type` parameter is deprecated. Use `provider` instead.

### 2. `model_id` (String)
**Type:** String
**Required:** Yes
**Description:** Model identifier for the selected provider.

**Valid Values:**

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
```json
"model_id": "openai/nomic-embed-text"                              // Ollama via LiteLLM
"model_id": "huggingface/sentence-transformers/all-MiniLM-L6-v2"   // HuggingFace API via LiteLLM
"model_id": "sentence-transformers/all-MiniLM-L6-v2"               // Native HuggingFace local
"model_id": "text-embedding-3-small"                               // OpenAI via LiteLLM
"model_id": "ibm/slate-125m-english-rtrvr"                         // Native Watsonx
```

**Migration Note:** The old `embeddings_model_id` parameter is deprecated. Use `model_id` instead.

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
**Required:** Varies by provider
**Description:** Provider-specific configuration parameters for the embedding provider.

**For LiteLLM:**
- `api_key` (String, Required for most providers): API key for the provider
- `api_base` (String, Optional): Custom API endpoint
- `api_version` (String, Optional): API version (for Azure)
- `project_id` (String, Optional): Project ID (for watsonx via LiteLLM)
- `timeout` (Float, Optional): Timeout in seconds for API calls
- Additional provider-specific parameters as needed

**For Watsonx (Native):**
- `api_base` (String, Required): watsonx.ai service URL
- `api_key` (String, Required): IBM Cloud API key
- `container_id` (String, Required): Project or space ID
- `container_kind` (String, Optional): "project" or "space" (default: "project")
- `enable_rate_limiting` (Boolean, Optional): Enable rate limiting (7 req/s) for WatsonX API calls (default: false)

**For Ollama via LiteLLM:**
- `api_base` (String, Optional): Ollama server URL (default: "http://localhost:11434")
- No API key required for local Ollama

**For HuggingFace via LiteLLM:**
- `api_key` (String, Optional): HuggingFace API token (or use HF_TOKEN env var)
- `api_base` (String, Optional): Custom HuggingFace endpoint

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
    "provider": "litellm",
    "model_id": "watsonx/ibm/slate-125m-english-rtrvr",
    "embeddings_column": "embeddings",
    "provider_config": {
      "api_base": "https://us-south.ml.cloud.ibm.com",
      "api_key": "${WATSONX_API_KEY}", # pragma: allowlist secret
      "project_id": "${WATSONX_PROJECT_ID}"
    }
  }
}
```

### Example 2: Watsonx.ai Embeddings (Native)
```json
{
  "id": "30953cfb-a3a2-4688-9aea-ff9fff10f7bd",
  "operator": "embeddings",
  "config": {
    "provider": "watsonx",
    "model_id": "ibm/slate-125m-english-rtrvr",
    "embeddings_column": "embeddings",
    "provider_config": {
      "api_base": "${WATSONX_API_BASE}",
      "api_key": "${WATSONX_API_KEY}", # pragma: allowlist secret
      "container_id": "${WATSONX_CONTAINER_ID}",
      "container_kind": "project",
      "enable_rate_limiting": true
    }
  }
}
```

### Example 3: Ollama Embeddings via LiteLLM (Local)
```json
{
  "id": "30953cfb-a3a2-4688-9aea-ff9fff10f7bd",
  "operator": "embeddings",
  "config": {
    "provider": "litellm",
    "model_id": "openai/nomic-embed-text",
    "embeddings_column": "embeddings",
    "overlap_ratio": 0.2,
    "provider_config": {
      "api_base": "http://localhost:11434"
    }
  }
}
```

### Example 4: HuggingFace Embeddings via LiteLLM
```json
{
  "id": "30953cfb-a3a2-4688-9aea-ff9fff10f7bd",
  "operator": "embeddings",
  "config": {
    "provider": "litellm",
    "model_id": "huggingface/sentence-transformers/all-mpnet-base-v2",
    "embeddings_column": "embeddings",
    "provider_config": {
      "api_key": "${HUGGINGFACE_API_KEY}" # pragma: allowlist secret
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
    "provider": "litellm",
    "model_id": "text-embedding-3-small",
    "embeddings_column": "embeddings",
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
    "provider": "litellm",
    "model_id": "embed-english-v3.0",
    "embeddings_column": "embeddings",
    "provider_config": {
      "api_key": "${COHERE_API_KEY}" # pragma: allowlist secret
    }
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

- `provider` must be one of: litellm, watsonx
- `model_id` must be a non-empty string
- `overlap_ratio` must be between 0.0 and 0.5
- Input data must have `content` column or `chunked_content` column
- For LiteLLM, `provider_config.api_key` is required
- For Watsonx, `provider_config.api_key`, `provider_config.api_base`, and `provider_config.container_id` are required

## Complete Flow Example

- [Sample Flow](../../../tests/sample_test_flows/invoice_processing/flow_invoice_process.json)
