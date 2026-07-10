# Embeddings Operator

## Overview

The Embeddings Operator generates vector embeddings from text using various AI providers through a unified adapter architecture. It uses the centralized `LLMAdapterFactory` for consistent provider integration across the Docpipe framework.

## Supported Providers

| Provider        | Description                           | Best For                             |
| --------------- | ------------------------------------- | ------------------------------------ |
| **HuggingFace** | Native local or API models            | Open-source models, high-concurrency local inference, offline usage |
| **LiteLLM**     | Unified API for 100+ providers        | OpenAI, Azure, Cohere, AWS, GCP, Ollama |
| **Watsonx**     | IBM watsonx.ai cloud service          | Enterprise AI, IBM Cloud integration |

## Architecture

The operator uses the centralized `LLMAdapterFactory` from `src/docpipe/core/adapters/llm_adapter_factory.py`:

```
┌─────────────────────────────────────────┐
│     EmbeddingsOperator (Core Logic)     │
│                                         │
│  - Batch processing                     │
│  - Error handling                       │
│  - PyArrow table management             │
│  - Automatic chunking for long text     │
└──────────────┬──────────────────────────┘
               │
               │ Uses
               ▼
┌─────────────────────────────────────────┐
│      LLMAdapterFactory (Centralized)    │
│                                         │
│  - create_embedding_adapter()           │
│  - Provider validation                  │
│  - Unified configuration                │
└──────────────┬──────────────────────────┘
               │
               │ Creates
               ▼
┌─────────────────────────────────────────┐
│      LLMEmbeddingPort (Interface)       │
│                                         │
│  - generate_embeddings()                │
│  - generate_embeddings_batch()          │
│  - get_embedding_dimension()            │
│  - validate_embedding()                 │
└──────────────┬──────────────────────────┘
               │
               │ Implemented by
               ▼
┌─────────────────────────────────────────┐
│           Adapters                      │
│                                         │
│  - HuggingFaceAdapter                   │
│  - LiteLLMAdapter                       │
│  - WatsonXAdapter                       │
└──────────────┬──────────────────────────┘
               │
               │ Uses
               ▼
┌─────────────────────────────────────────┐
│         LLM Clients                     │
│                                         │
│  - HuggingFaceLLMClient                 │
│  - LiteLLMLLMClient                     │
│  - WatsonxRestEmbeddingClient           │
└─────────────────────────────────────────┘
```

## Quick Start

### Basic Configuration

```json
{
  "type": "embeddings",
  "name": "embed",
  "config": {
    "provider": "litellm",
    "model_id": "openai/nomic-embed-text",
    "provider_config": {
      "api_base": "http://localhost:11434"
    }
  }
}
```

## Provider-Specific Guides

### HuggingFace (Native Local or API)

**Local Mode** (Recommended for production and high-concurrency):

```json
{
  "type": "embeddings",
  "name": "embed",
  "config": {
    "provider": "huggingface",
    "model_id": "sentence-transformers/all-MiniLM-L6-v2",
    "provider_config": {
      "use_local": true,
      "device": "cpu",
      "batch_size": 16
    }
  }
}
```

**API Mode** (Requires HuggingFace token):

```bash
export HUGGINGFACE_API_KEY=hf_...
```

```json
{
  "type": "embeddings",
  "name": "embed",
  "config": {
    "provider": "huggingface",
    "model_id": "sentence-transformers/all-MiniLM-L6-v2",
    "provider_config": {
      "use_local": false,
      "api_token": "${HUGGINGFACE_API_KEY}"
    }
  }
}
```

**Popular Models**:

- `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions) - Fast, efficient
- `sentence-transformers/all-mpnet-base-v2` (768 dimensions) - Higher quality
- `BAAI/bge-small-en-v1.5` (384 dimensions) - Good for English

**Pros**:

- ✅ Large model selection (1000+ models)
- ✅ Open-source models
- ✅ Native local inference (no API costs)
- ✅ High-concurrency support (600+ parallel processes tested)
- ✅ Offline capable with pre-downloaded models
- ✅ Active community

**Cons**:

- ❌ Local mode requires dependencies (sentence-transformers, torch)
- ❌ API mode has rate limits (use native provider for local)
- ❌ Model downloads can be large (cache in `/models` volume)

### LiteLLM (Multi-Provider API)

**Quick Start with Ollama**:

```bash
# Start Ollama
ollama serve

# Pull model
ollama pull nomic-embed-text
```

```json
{
  "type": "embeddings",
  "name": "embed",
  "config": {
    "provider": "litellm",
    "model_id": "openai/nomic-embed-text",
    "provider_config": {
      "api_base": "http://localhost:11434"
    }
  }
}
```

**Quick Start with OpenAI**:

```bash
export OPENAI_API_KEY=sk-proj-...
```

```json
{
  "type": "embeddings",
  "name": "embed",
  "config": {
    "provider": "litellm",
    "model_id": "openai/text-embedding-3-small"
  }
}
```

**Supported Providers**:

- OpenAI (`text-embedding-3-small`, `text-embedding-3-large`)
- Azure OpenAI (`azure/deployment-name`)
- Cohere (`embed-english-v3.0`, `embed-multilingual-v3.0`)
- AWS Bedrock (`bedrock/amazon.titan-embed-text-v1`)
- Google Vertex AI (`vertex_ai/textembedding-gecko@001`)
- Ollama (via OpenAI-compatible API with `openai/` prefix)
- HuggingFace API (with `huggingface/` prefix)
- And 90+ more...

For detailed provider-specific configuration examples and advanced usage, see the [LiteLLM Embeddings Documentation](https://docs.litellm.ai/docs/embedding/supported_embedding).

**Pros**:

- ✅ Unified interface for all providers
- ✅ Production-grade APIs
- ✅ High-quality embeddings
- ✅ Automatic provider detection

**Cons**:

- ❌ Requires API keys (except Ollama)
- ❌ API costs
- ❌ Network dependency
- ❌ Rate limits

### Watsonx.ai (IBM Cloud)

**Requirements**: IBM watsonx.ai account with API key and project/space ID

```bash
export WATSONX_API_KEY=your-api-key
export WATSONX_API_BASE=https://us-south.ml.cloud.ibm.com
export WATSONX_CONTAINER_ID=your-project-or-space-id
```

**Configuration**:

```json
{
  "type": "embeddings",
  "name": "embed",
  "config": {
    "provider": "watsonx",
    "model_id": "ibm/slate-125m-english-rtrvr",
    "provider_config": {
      "api_key": "${WATSONX_API_KEY}",
      "api_base": "${WATSONX_API_BASE}",
      "container_id": "${WATSONX_CONTAINER_ID}"
    }
  }
}
```

**Popular Models**:

- `ibm/slate-125m-english-rtrvr` - Recommended for general use
- `ibm/slate-30m-english-rtrvr` - Faster, smaller model

**Pros**:

- ✅ Enterprise-grade IBM Cloud service
- ✅ High-quality foundation models
- ✅ Automatic IAM authentication
- ✅ Batch processing support

**Cons**:

- ❌ Requires IBM Cloud account
- ❌ API costs
- ❌ Network dependency

## Configuration Reference

### Common Parameters

| Parameter          | Type   | Required | Default      | Description                                                  |
| ------------------ | ------ | -------- | ------------ | ------------------------------------------------------------ |
| `provider`         | string | Yes      | `litellm`    | Provider name: `huggingface`, `litellm`, `watsonx`           |
| `model_id`         | string | Yes      | -            | Model identifier                                             |
| `embeddings_column`| string | No       | `embeddings` | Output column name                                           |
| `doc_column`       | string | No       | `content`    | Input content column                                         |
| `overlap_ratio`    | float  | No       | `0.2`        | Overlap ratio for chunking long text (0.0-0.5)               |
| `token_limit`      | integer| No       | `8192`       | Maximum token limit for chunking                             |

### Provider-Specific Parameters

#### HuggingFace

| Parameter    | Type    | Default | Description                                      |
| ------------ | ------- | ------- | ------------------------------------------------ |
| `use_local`  | boolean | `true`  | Use local model inference vs HuggingFace API     |
| `device`     | string  | `cpu`   | Device for local inference: `cpu`, `cuda`, `mps` |
| `api_token`  | string  | None    | HuggingFace API token (required for API mode)    |
| `batch_size` | int     | `32`    | Number of texts to process in each batch         |

#### LiteLLM

| Parameter  | Type   | Default | Description                       |
| ---------- | ------ | ------- | --------------------------------- |
| `api_key`  | string | None    | Provider API key (or use env var) |
| `api_base` | string | None    | Custom API endpoint               |

#### Watsonx

| Parameter              | Type    | Default   | Description                                                  |
| ---------------------- | ------- | --------- | ------------------------------------------------------------ |
| `api_key`              | string  | None      | Watsonx.ai API key (required)                                |
| `api_base`             | string  | None      | Watsonx.ai API endpoint URL (required)                       |
| `container_kind`       | string  | `project` | Container type: `project` or `space`                         |
| `container_id`         | string  | None      | Project ID or Space ID (required)                            |
| `batch_size`           | int     | `800`     | Number of texts to process per batch                         |
| `enable_rate_limiting` | boolean | False     | Enable rate limiting (7 req/s) for WatsonX API calls         |

## Performance Optimization

### Choosing the Right Provider

| Use Case                  | Recommended Provider | Model                   |
| ------------------------- | -------------------- | ----------------------- |
| Development/Testing       | HuggingFace (local)  | all-MiniLM-L6-v2        |
| Privacy-Sensitive         | HuggingFace (local)  | all-MiniLM-L6-v2        |
| High-Concurrency (600+)   | HuggingFace (local)  | all-MiniLM-L6-v2        |
| Production (Quality)      | LiteLLM (OpenAI)     | text-embedding-3-large  |
| Production (Cost)         | LiteLLM (OpenAI)     | text-embedding-3-small  |
| Multilingual              | LiteLLM (Cohere)     | embed-multilingual-v3.0 |

### Performance Tips

1. **Batch Processing**: Operator handles batching automatically
2. **Model Selection**: Smaller models = faster processing
3. **Local vs API**: Local is faster for small datasets, API scales better
4. **Caching**: Cache embeddings for frequently accessed documents
5. **GPU Acceleration**: Use GPU for local models (HuggingFace with `device: "cuda"`)

## Error Handling

### Common Errors

#### Provider Not Available

```
ConfigurationError: Unknown provider 'invalid'
Available providers: huggingface, litellm, watsonx
```

**Solution**: Check provider name spelling.

#### Model Not Found

```
ExternalServiceError: Model 'invalid-model' not found
```

**Solution**: Verify model name with provider documentation

#### Missing API Key (LiteLLM/HuggingFace API)

```
ExternalServiceError: The api_key client option must be set
```

**Solution**: Set environment variable: `export OPENAI_API_KEY=sk-...` or `export HUGGINGFACE_API_KEY=hf_...`

### Retry Logic

All adapters include automatic retry logic:

- **Retries**: 3 attempts
- **Backoff**: Exponential (1s, 2s, 4s)
- **Errors**: Network, rate limiting, temporary failures

## Security Best Practices

### API Key Management

**✅ Recommended: Environment Variables**

```bash
export OPENAI_API_KEY=your-key-here
export COHERE_API_KEY=your-key-here
export WATSONX_API_KEY=your-key-here
export HUGGINGFACE_API_KEY=your-key-here
```

**⚠️ Not Recommended: Configuration Files**

```json
{
  "config": {
    "provider": "litellm",
    "model_id": "openai/text-embedding-3-small",
    "provider_config": {
      "api_key": "sk-proj-..." // pragma: allowlist secret
    }
  }
}
```

### Why Environment Variables?

1. **Not Version Controlled**: Environment variables aren't committed to Git
2. **Per-Environment**: Different keys for dev/staging/prod
3. **Standard Practice**: Industry-standard approach
4. **Audit Trail**: Easier to track and rotate keys

### When Configuration-Based Keys Are Acceptable

- **Local development/testing only**
- **Temporary test keys**
- **Keys that will be immediately rotated**
- **Never in production**

### Provider-Specific Environment Variables

| Provider     | Environment Variable             |
| ------------ | -------------------------------- |
| OpenAI       | `OPENAI_API_KEY`                 |
| Azure OpenAI | `AZURE_API_KEY`                  |
| Cohere       | `COHERE_API_KEY`                 |
| Anthropic    | `ANTHROPIC_API_KEY`              |
| Vertex AI    | `GOOGLE_APPLICATION_CREDENTIALS` |
| Bedrock      | `AWS_ACCESS_KEY_ID`              |
| watsonx      | `WATSONX_API_KEY`                |
| Hugging Face | `HUGGINGFACE_API_KEY`            |

### Security Checklist

1. **Never commit API keys**: Use environment variables or secret management
2. **Rotate keys regularly**: Change API keys periodically
3. **Use least privilege**: Grant minimum required permissions
4. **Monitor usage**: Track API calls for anomalies
5. **Secure storage**: Store keys in secure vaults (AWS Secrets Manager, Azure Key Vault, etc.)

## Testing

### Unit Tests

```bash
# From project root
source .venv/bin/activate
uv run pytest tests/unit/operators/embeddings/ -v
```

### Integration Tests

```bash
# From project root
# Requires Ollama server running
source .venv/bin/activate
uv run pytest tests/integration/test_embeddings_ollama_integration.py -v
```

## Troubleshooting

### Enable Debug Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Verify Provider Setup

**HuggingFace (Local)**:

```python
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('all-MiniLM-L6-v2')
print(model.encode(["test"]))
```

**LiteLLM (OpenAI)**:

```bash
curl https://api.openai.com/v1/embeddings \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"input": "test", "model": "text-embedding-3-small"}'
```

## Additional Resources

- [Operator Reference](../../reference/OPERATORS.md#embeddingsoperator)
- [Architecture Guide](../../../ARCHITECTURE.md)
- [HuggingFace Sentence Transformers](https://www.sbert.net/)
- [IBM watsonx.ai Documentation](https://www.ibm.com/watsonx/developer/)
- [OpenAI Embeddings Guide](https://platform.openai.com/docs/guides/embeddings)
- [LiteLLM Documentation](https://docs.litellm.ai/)

## Support

For issues or questions:

1. Check this documentation
2. Review provider-specific documentation
3. Open an issue in the docling-pipelines repository
