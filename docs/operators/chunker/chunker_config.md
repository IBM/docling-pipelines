# Chunker Operator - Configuration Reference

## Overview

The Chunker Operator provides intelligent text chunking with support for three strategies: simple (fixed-size), semantic (content-aware), and hybrid (Docling-based hierarchical). It's essential for preparing documents for embedding generation and vector storage.

- **Operator Name:** `chunker`
- **Category**: Functional
- **Short Name**: `chunker`

## Configuration Parameters

### 1. `chunk_type` (String)
**Type:** String
**Required:** No
**Default:** `"simple"`
**Description:** Chunking strategy to use.

**Valid Values:**
- `"simple"` - Fixed-size chunking with overlap (traditional approach)
- `"semantic"` - Content-aware chunking based on semantic similarity (LangChain)
- `"hybrid"` - Hierarchical + semantic chunking using Docling's HybridChunker

**Examples:**
```json
"chunk_type": "simple"
"chunk_type": "semantic"
"chunk_type": "hybrid"
```

### 2. `chunk_size` (Integer)
**Type:** Integer
**Required:** No
**Default:** `2048`
**Description:** Size of each chunk. Units depend on chunk_type:
- Simple: characters (500-5000)
- Hybrid: tokens (100-2048)
- Semantic: not used

**Valid Values:**
- Minimum: `100` (for hybrid) or `500` (for simple)
- Maximum: `5000` (for simple) or `2048` (for hybrid)

**Examples:**
```json
"chunk_size": 1000
"chunk_size": 512
```

### 3. `chunk_overlap` (Integer)
**Type:** Integer
**Required:** No
**Default:** `200`
**Description:** Number of characters/tokens that consecutive chunks share to retain context across boundaries.

**Valid Values:**
- Minimum: `0`
- Maximum: `512`

**Examples:**
```json
"chunk_overlap": 200
"chunk_overlap": 50
```

### 4. `semantic_embeddings_model` (String)
**Type:** String
**Required:** No (Yes for semantic chunking)
**Default:** None
**Description:** Ollama model name for generating embeddings in semantic chunking. Must be explicitly provided when using semantic chunking.

**Recommended Models:**
- `"nomic-embed-text"` - General purpose embedding model (recommended for most use cases)
- `"mxbai-embed-large"` - Higher quality embeddings with larger model
- `"granite4"` - IBM Granite 4
- Any other Ollama-compatible embedding model suitable for your domain and language

**Examples:**
```json
"semantic_embeddings_model": "nomic-embed-text"
"semantic_embeddings_model": "mxbai-embed-large"
```

### 5. `breakpoint_threshold_type` (String)
**Type:** String
**Required:** No (for semantic chunking)
**Default:** `"percentile"`
**Description:** Method for determining semantic chunk boundaries.

**Valid Values:**
- `"percentile"` - Split at percentile threshold of dissimilarity scores (e.g: 95th percentile = split at top 5% most dissimilar points)
- `"standard_deviation"` - Split when dissimilarity exceeds N standard deviations (e.g: 2.0 = split at 2 std devs above mean)
- `"interquartile"` - Split based on interquartile range (IQR)
- `"gradient"` - Split at points with steepest changes in similarity

**Examples:**
```json
"breakpoint_threshold_type": "percentile"
"breakpoint_threshold_type": "standard_deviation"
```

### 6. `breakpoint_threshold_amount` (Float)
**Type:** Float
**Required:** No
**Default:** `None` (uses LangChain defaults)
**Description:** Threshold value for the selected breakpoint type.

**Valid Values:**
- For percentile: `0-100` (e.g., 95.0 for 95th percentile)
- For standard_deviation: positive number (e.g., 2.0 for 2 std devs)
- `null`: Use LangChain defaults

**Examples:**
```json
"breakpoint_threshold_amount": 95.0
"breakpoint_threshold_amount": 2.0
"breakpoint_threshold_amount": None
```

### 7. `docling_tokenizer` (String)
**Type:** String
**Required:** No (only used for hybrid chunking)
**Default:** `"sentence-transformers/all-MiniLM-L6-v2"`
**Description:** HuggingFace tokenizer model for hybrid (Docling) chunking. This parameter is only used when `chunk_type` is set to `"hybrid"`. If not specified, the default tokenizer will be used.

**Valid Values:**
- `"sentence-transformers/all-MiniLM-L6-v2"` (default)
- `"sentence-transformers/all-mpnet-base-v2"`
- Any HuggingFace tokenizer model

**Examples:**
```json
"docling_tokenizer": "sentence-transformers/all-MiniLM-L6-v2"
"docling_tokenizer": "sentence-transformers/all-mpnet-base-v2"
```

### 8. `retain_original_content` (Boolean)
**Type:** Boolean
**Required:** No
**Default:** `false`
**Description:** Whether to keep the original content column after chunking.

**Valid Values:**
- `true` - Keep original content alongside chunks
- `false` - Remove original content column

**Examples:**
```json
"retain_original_content": false
```

### 9. `summarization` (Object)
**Type:** JSON Object
**Required:** No
**Default:** `{}`
**Description:** Nested configuration object for all summarization-related settings. When present with a provider specified, summarization is enabled.

**Sub-parameters:**
- `provider` (String): LLM provider (`litellm` or `watsonx`)
- `provider_config` (Object): Provider-specific configuration
- `max_input_tokens` (Integer): Maximum tokens per LLM request
- `overlap_ratio` (Float): Overlap ratio for sliding window
- `summary_sentences` (Integer): Target sentences per summary
- `summary_max_words` (Integer): Maximum words per summary

**Structure:**
```json
"summarization": {
  "provider": "litellm",
  "provider_config": {
    "model_id": "openai/granite4",
    "api_base": "http://localhost:11434/v1",
    "api_key": "<ollama>"
  },
  "summary_sentences": 3,
  "summary_max_words": 50,
  "max_input_tokens": 8000
}
```

**Sub-parameters:**

#### 10.1 `provider` (String)
**Type:** String
**Required:** No
**Default:** `"litellm"`
**Description:** LLM provider for summarization.

**Valid Values:**
- `"litellm"` - LiteLLM (supports 100+ providers including Ollama, OpenAI, Anthropic, HuggingFace)
- `"watsonx"` - IBM WatsonX

#### 10.2 `provider_config` (Object)
**Type:** JSON Object
**Required:** Yes (when summarization is enabled)
**Description:** Provider-specific configuration including model_id.

**For LiteLLM:**
- `model_id` (String, Required): Model identifier (auto-prefixed with `openai/` for Ollama models)
- `api_base` (String, Optional): API endpoint URL (default: `http://localhost:11434/v1` for Ollama)
- `api_key` (String, Optional): API key for authentication

**For Watsonx:**
- `model_id` (String, Required): WatsonX model identifier
- `api_key` (String, Required): IBM Cloud API key
- `api_base` (String, Required): WatsonX API URL (default: `https://us-south.ml.cloud.ibm.com`)
- `container_id` (String, Required): WatsonX project/space ID
- `container_kind` (String, Required): Container type (`"project"` or `"space"`)

#### 10.3 `summary_sentences` (Integer)
**Type:** Integer
**Required:** No
**Default:** `2`
**Description:** Number of sentences in each summary.

**Valid Values:**
- Minimum: `1`
- Maximum: `5`

#### 10.4 `summary_max_words` (Integer)
**Type:** Integer
**Required:** No
**Default:** `20`
**Description:** Maximum words per summary.

**Valid Values:**
- Minimum: `10`
- Maximum: `100`

#### 10.5 `max_input_tokens` (Integer)
**Type:** Integer
**Required:** No
**Default:** `8000`
**Description:** Maximum input tokens per summarization request.

**Valid Values:**
- Minimum: `1000`
- Maximum: `32000`

**Complete Examples:**

**LiteLLM with Ollama:**
```json
"summarization": {
  "provider": "litellm",
  "provider_config": {
    "model_id": "openai/granite4",
    "api_base": "http://localhost:11434/v1",
    "api_key": "<ollama>"
  },
  "summary_sentences": 3,
  "summary_max_words": 50
}
```

**WatsonX:**
```json
"summarization": {
  "provider": "watsonx",
  "provider_config": {
    "model_id": "ibm/granite-13b-chat-v2",
    "api_key": "${WATSONX_API_KEY}",
    "api_base": "${WATSONX_API_BASE}",
    "container_id": "${WATSONX_PROJECT_ID}",
    "container_kind": "project"
  },
  "summary_sentences": 2,
  "summary_max_words": 30
}
```

**Backward Compatibility Note:** The flat configuration structure (using `summarization_provider`, `summarization_provider_config`, `summary_sentences`, etc. at the top level) is still supported but deprecated. The nested `summarization` object is the recommended approach.

### 11. `provider` (String)
**Type:** String
**Required:** No
**Default:** `None`
**Description:** Chunking provider for remote/distributed chunking. When not specified, uses local chunking based on `chunk_type`.

**Valid Values:**
- `"docling_library"` - Local Docling library (same as not specifying provider)
- `"docling_serve"` - Remote chunking via docling-serve API
- `None` - Use local chunking based on `chunk_type` (default)

**Examples:**
```json
"provider": "docling_serve"
"provider": null
```

### 12. `provider_config` (Object)
**Type:** Object (JSON)
**Required:** No (Yes if provider is "docling_serve")
**Default:** `{}`
**Description:** Provider-specific configuration options for remote chunking.

**For `docling_serve` provider:**
- `api_base` (string, required): Base URL of docling-serve instance
- `api_key` (string, optional): API key for authentication
- `timeout` (integer, optional, default: 300): Request timeout in seconds
- `poll_interval` (integer, optional, default: 2): Polling interval for async operations
- `max_retries` (integer, optional, default: 3): Maximum retry attempts

**Examples:**
```json
"provider_config": {
  "api_base": "https://docling-serve.example.com",
  "timeout": 120,
  "max_retries": 3
}
```

## Output Features

### 1. `chunk_sequence_number` (Integer)
**Description:** Sequential chunk number for each text chunk, representing its position within a larger document.
**Type:** Integer (int64)
**Available for Vector DB:** Yes
**Tags:** `mandatory`, `internal_feature`

### 2. `start_index` (Integer)
**Description:** Chunk starting token position in the source document.
**Type:** Integer (int64)
**Available for Vector DB:** Yes
**Tags:** `mandatory`, `internal_feature`

### 3. `chunked_content` (List)
**Description:** Content containing segmented portions of larger text data.
**Type:** List of dictionaries
**Available for Filter:** No
**Tags:** `mandatory`

**Chunk Object Structure:**
```json
{
  "chunk": "Text content of the chunk",
  "start_index": 0,
  "summary": "Optional summary if summarization enabled"
}
```

## Configuration Examples

### Example 1: Simple Chunking
```json
{
  "operator": "chunker",
  "config": {
    "chunk_type": "simple",
    "chunk_size": 1000,
    "chunk_overlap": 200,
    "retain_original_content": false
  }
}
```

### Example 2: Semantic Chunking
```json
{
  "operator": "chunker",
  "config": {
    "chunk_type": "semantic",
    "semantic_embeddings_model": "nomic-embed-text",
    "breakpoint_threshold_type": "percentile",
    "breakpoint_threshold_amount": 95.0,
    "retain_original_content": false
  }
}
```

### Example 3: Hybrid Chunking with Summarization (Nested Structure)
```json
{
  "operator": "chunker",
  "config": {
    "chunk_type": "hybrid",
    "chunk_size": 512,
    "chunk_overlap": 50,
    "docling_tokenizer": "sentence-transformers/all-MiniLM-L6-v2",
    "summarization": {
      "provider": "litellm",
      "provider_config": {
        "model_id": "openai/granite4",
        "api_base": "http://localhost:11434/v1",
        "api_key": "<ollama>"
      },
      "summary_sentences": 2,
      "summary_max_words": 30
    },
    "retain_original_content": false
  }
}
```

### Example 4: Remote Chunking with Docling-Serve
```json
{
  "operator": "chunker",
  "config": {
    "chunk_type": "hybrid",
    "chunk_size": 512,
    "chunk_overlap": 128,
    "provider": "docling_serve",
    "provider_config": {
      "api_base": "https://docling-serve.example.com",
      "timeout": 120,
      "poll_interval": 2,
      "max_retries": 3
    },
    "retain_original_content": false
  }
}
```

## Best Practices

1. **Strategy Selection**:
   - Use **simple** for general text and fast processing
   - Use **semantic** for maintaining semantic coherence in narratives
   - Use **hybrid** for structured documents (PDFs with sections, tables)

2. **Chunk Size**:
   - Smaller chunks (500-1000): Better for precise retrieval
   - Larger chunks (1500-3000): Better for context preservation
   - Balance based on your embedding model's token limit

3. **Overlap**:
   - 10-20% overlap recommended for context continuity
   - Higher overlap for technical documents
   - Lower overlap for simple text

4. **Semantic Chunking**:
   - Use percentile threshold (95.0) for most cases
   - Adjust threshold based on document type
   - Test with sample documents first

5. **Summarization**:
   - Enable for long chunks (>1000 tokens)
   - Useful for improving retrieval relevance
   - Adds processing time and cost

6. **Remote Chunking**:
   - Use `provider: "docling_serve"` for distributed architectures
   - Offloads computation to remote service
   - Requires network access to docling-serve instance
   - Configure appropriate timeout based on document size
   - Local chunking preferred for small-scale operations

## Validation Rules

- `chunk_type` must be one of: simple, semantic, hybrid
- `chunk_size` must be within valid range for the selected chunk_type
- `chunk_overlap` must be less than `chunk_size`
- Semantic chunking requires Ollama server running
- Hybrid chunking requires Docling library
- Summarization requires `summarization` object with `provider` and valid model configuration

## Complete Flow Example

- [Sample Flow](../../../tests/sample_test_flows/invoice_processing/flow_invoice.json)
