# Embeddings Operator

## Overview

The Embeddings Operator generates vector embeddings from text using various AI providers. It supports multiple embedding models through a hexagonal architecture with pluggable adapters.

## Supported Providers

| Provider        | Description                    | Best For                             |
| --------------- | ------------------------------ | ------------------------------------ |
| **Ollama**      | Local LLM server               | Privacy, offline usage, no API costs |
| **HuggingFace** | Local or API models            | Open-source models, customization    |
| **LiteLLM**     | Unified API for 100+ providers | OpenAI, Azure, Cohere, AWS, GCP      |
| **Watsonx**     | IBM watsonx.ai cloud service   | Enterprise AI, IBM Cloud integration |

## Quick Start

### Basic Configuration

```json
{
  "operator_type": "EmbeddingsOperator",
  "operator_params": {
    "provider": "ollama",
    "model_name": "nomic-embed-text"
  }
}
```

### Complete Pipeline Example

```json
{
  "nodes": [
    {
      "id": "ingest",
      "operator_type": "IngestLocalFolder",
      "operator_params": {
        "folder_path": "data/documents"
      }
    },
    {
      "id": "extract",
      "operator_type": "ExtractOperator",
      "operator_params": {}
    },
    {
      "id": "chunk",
      "operator_type": "DoclingChunker",
      "operator_params": {
        "chunk_size": 512
      }
    },
    {
      "id": "embed",
      "operator_type": "EmbeddingsOperator",
      "operator_params": {
        "provider": "ollama",
        "model_name": "nomic-embed-text"
      }
    },
    {
      "id": "store",
      "operator_type": "VectorDBOperator",
      "operator_params": {
        "provider": "opensearch",
        "index_name": "documents",
        "dimension": 768
      }
    }
  ],
  "edges": [
    { "from": "ingest", "to": "extract" },
    { "from": "extract", "to": "chunk" },
    { "from": "chunk", "to": "embed" },
    { "from": "embed", "to": "store" }
  ]
}
```

## Provider-Specific Guides

### Ollama (Local)

**Requirements**: Ollama server running on `http://localhost:11434`

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull embedding model
ollama pull nomic-embed-text

# Verify server is running
curl http://localhost:11434/api/tags
```

**Configuration**:

```json
{
  "operator_params": {
    "provider": "ollama",
    "model_name": "nomic-embed-text"
  }
}
```

**Popular Models**:

- `nomic-embed-text` (768 dimensions) - Recommended for general use
- `mxbai-embed-large` (1024 dimensions) - Higher quality
- `all-minilm` (384 dimensions) - Faster, smaller

**Pros**:

- ✅ Free, no API costs
- ✅ Privacy (data stays local)
- ✅ Works offline
- ✅ Fast for local processing

**Cons**:

- ❌ Requires local setup
- ❌ Limited to available models
- ❌ Requires GPU for best performance

### HuggingFace (Local or API)

**Local Mode** (Recommended for development):

```json
{
  "operator_params": {
    "provider": "huggingface",
    "model_name": "sentence-transformers/all-MiniLM-L6-v2",
    "use_local": true,
    "device": "cpu"
  }
}
```

**API Mode** (Requires HuggingFace token):

```bash
export HUGGINGFACE_API_KEY=hf_...
```

```json
{
  "operator_params": {
    "provider": "huggingface",
    "model_name": "sentence-transformers/all-MiniLM-L6-v2",
    "use_local": false,
    "api_token": "${HUGGINGFACE_API_KEY}"
  }
}
```

**Popular Models**:

- `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions) - Fast, efficient
- `sentence-transformers/all-mpnet-base-v2` (768 dimensions) - Higher quality
- `BAAI/bge-small-en-v1.5` (384 dimensions) - Good for English

**Pros**:

- ✅ Large model selection
- ✅ Open-source models
- ✅ Local or API options
- ✅ Active community

**Cons**:

- ❌ Local mode requires dependencies
- ❌ API mode has rate limits
- ❌ Model downloads can be large

### LiteLLM (Multi-Provider API)

**For detailed LiteLLM documentation, see [README_LITELLM.md](adapters/outbound/README_LITELLM.md)**

**Quick Start with OpenAI**:

```bash
export OPENAI_API_KEY=sk-proj-...
```

```json
{
  "operator_params": {
    "provider": "litellm",
    "model_name": "text-embedding-3-small"
  }
}
```

**Supported Providers**:

- OpenAI (`text-embedding-3-small`, `text-embedding-3-large`)
- Azure OpenAI (`azure/deployment-name`)
- Cohere (`embed-english-v3.0`, `embed-multilingual-v3.0`)
- IBM watsonx.ai (`watsonx/ibm/slate-30m-english-rtrvr`, `watsonx/ibm/slate-125m-english-rtrvr`)
- AWS Bedrock (`bedrock/amazon.titan-embed-text-v1`)
- Google Vertex AI (`vertex_ai/textembedding-gecko@001`)
- And 100+ more...

**Pros**:

- ✅ Unified interface for all providers
- ✅ Production-grade APIs
- ✅ High-quality embeddings
- ✅ Automatic provider detection

**Cons**:

- ❌ Requires API keys
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
  "operator_params": {
    "provider": "watsonx",
    "model_name": "ibm/slate-125m-english-rtrvr",
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

**Note**: Embedding dimensions are retrieved dynamically. For troubleshooting, see [TROUBLESHOOTING.md](../../../../../TROUBLESHOOTING.md#watsonx-troubleshooting).

## Architecture

### Hexagonal Architecture

The embeddings operator follows hexagonal architecture (ports and adapters pattern):

```
┌─────────────────────────────────────────┐
│     EmbeddingsOperator (Core Logic)     │
│                                         │
│  - Batch processing                     │
│  - Error handling                       │
│  - PyArrow table management             │
└──────────────┬──────────────────────────┘
               │
               │ Uses
               ▼
┌─────────────────────────────────────────┐
│      LLMServicePort (Interface)         │
│                                         │
│  - generate_embeddings()                │
│  - get_model_token_limit()              │
│  - get_embedding_dimension()            │
└──────────────┬──────────────────────────┘
               │
               │ Implemented by
               ▼
┌─────────────────────────────────────────┐
│           Adapters                      │
│                                         │
│  - OllamaLLMAdapter                     │
│  - HuggingFaceLLMAdapter                │
│  - LiteLLMLLMAdapter                    │
│  - WatsonxLLMAdapter                    │
└──────────────┬──────────────────────────┘
               │
               │ Uses
               ▼
┌─────────────────────────────────────────┐
│         LLM Clients                     │
│                                         │
│  - OllamaClient                         │
│  - HuggingFaceLLMClient                 │
│  - LiteLLMLLMClient                     │
│  - WatsonxRestEmbeddingClient           │
└─────────────────────────────────────────┘
```

### Adding a New Provider

1. **Create Client** (in `common/clients/`):

```python
from common.clients.base_llm_client import BaseLLMClient

class MyProviderClient(BaseLLMClient):
    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        # Implementation
        pass
```

2. **Create Adapter** (in `adapters/outbound/`):

```python
from ports.outbound.llm_service import LLMServicePort
from adapters.outbound.factories.llm_adapter_factory import register_llm_adapter

@register_llm_adapter
class MyProviderAdapter(LLMServicePort):
    ADAPTER_NAME = "myprovider"
    ADAPTER_DISPLAY_NAME = "My Provider"

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        return self.client.generate_embeddings(texts)
```

3. **Use in Flow**:

```json
{
  "operator_params": {
    "provider": "myprovider",
    "model_name": "my-model"
  }
}
```

## Configuration Reference

### Common Parameters

| Parameter          | Type   | Required | Description                                                  |
| ------------------ | ------ | -------- | ------------------------------------------------------------ |
| `provider`         | string | Yes      | Provider name: `ollama`, `huggingface`, `litellm`, `watsonx` |
| `model_name`       | string | Yes      | Model identifier                                             |
| `text_column`      | string | No       | Column containing text (default: `text`)                     |
| `embedding_column` | string | No       | Output column name (default: `embeddings`)                   |

### Provider-Specific Parameters

#### Ollama

| Parameter  | Type   | Default                  | Description       |
| ---------- | ------ | ------------------------ | ----------------- |
| `base_url` | string | `http://localhost:11434` | Ollama server URL |

#### HuggingFace

| Parameter   | Type    | Default | Description                  |
| ----------- | ------- | ------- | ---------------------------- |
| `use_local` | boolean | `true`  | Use local model vs API       |
| `device`    | string  | `cpu`   | Device: `cpu`, `cuda`, `mps` |
| `api_token` | string  | None    | HuggingFace API token        |

#### LiteLLM

| Parameter  | Type   | Default | Description                       |
| ---------- | ------ | ------- | --------------------------------- |
| `api_key`  | string | None    | Provider API key (or use env var) |
| `api_base` | string | None    | Custom API endpoint               |

#### Watsonx

| Parameter              | Type    | Default   | Description                                                  |
| ---------------------- | ------- | --------- | ------------------------------------------------------------ |
| `api_key`              | string  | None      | Watsonx.ai API key (required)                                |
| `api_base`             | string  | None      | Watsonx.ai API endpoint URL for the native adapter (required) |
| `container_kind`       | string  | `project` | Container type: `project` or `space`                         |
| `container_id`         | string  | None      | Project ID or Space ID for the native adapter (required)     |
| `batch_size`           | int     | 800       | Number of texts to process per batch                         |
| `enable_rate_limiting` | boolean | False     | Enable rate limiting (7 req/s) for WatsonX API calls         |

## Performance Optimization

### Choosing the Right Provider

| Use Case             | Recommended Provider | Model                   |
| -------------------- | -------------------- | ----------------------- |
| Development/Testing  | HuggingFace (local)  | all-MiniLM-L6-v2        |
| Privacy-Sensitive    | Ollama               | nomic-embed-text        |
| Production (Quality) | LiteLLM (OpenAI)     | text-embedding-3-large  |
| Production (Cost)    | LiteLLM (OpenAI)     | text-embedding-3-small  |
| Multilingual         | LiteLLM (Cohere)     | embed-multilingual-v3.0 |

### Performance Tips

1. **Batch Processing**: Process documents in batches (coming soon)
2. **Model Selection**: Smaller models = faster processing
3. **Local vs API**: Local is faster for small datasets, API scales better
4. **Caching**: Cache embeddings for frequently accessed documents
5. **GPU Acceleration**: Use GPU for local models (HuggingFace, Ollama)

### Benchmark Results

Based on 24 chunks from 3 PDF documents:

| Provider    | Model                  | Time    | Dimension | Throughput    |
| ----------- | ---------------------- | ------- | --------- | ------------- |
| Ollama      | nomic-embed-text       | 1.35s   | 768       | 17.8 chunks/s |
| HuggingFace | all-MiniLM-L6-v2       | 1.70s   | 384       | 14.1 chunks/s |
| LiteLLM     | text-embedding-3-small | ~2.0s\* | 1536      | ~12 chunks/s  |

\*Estimated based on network latency

## Error Handling

### Common Errors

#### Provider Not Available

```
ConfigurationError: Unknown provider 'invalid'
Available providers: ollama, huggingface, litellm
```

**Solution**: Check provider name spelling

#### Model Not Found

```
ExternalServiceError: Model 'invalid-model' not found
```

**Solution**: Verify model name with provider documentation

#### Server Not Running (Ollama)

```
ExternalServiceError: Failed to connect to Ollama server at http://localhost:11434
```

**Solution**: Start Ollama server: `ollama serve`

#### Missing API Key (LiteLLM)

```
ExternalServiceError: The api_key client option must be set
```

**Solution**: Set environment variable: `export OPENAI_API_KEY=sk-...`

### Retry Logic

All adapters include automatic retry logic:

- **Retries**: 3 attempts
- **Backoff**: Exponential (1s, 2s, 4s)
- **Errors**: Network, rate limiting, temporary failures

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

### Flow Testing

```bash
# From project root
datasift-orchestrator --flow-file tests/sample_test_flows/basic/opensearch_integration.json
```

## Troubleshooting

### Enable Debug Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Verify Provider Setup

**Ollama**:

```bash
curl http://localhost:11434/api/tags
```

**HuggingFace**:

```python
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('all-MiniLM-L6-v2')
print(model.encode(["test"]))
```

**LiteLLM**:

```bash
curl https://api.openai.com/v1/embeddings \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"input": "test", "model": "text-embedding-3-small"}'
```

## Additional Resources

- [LiteLLM Detailed Documentation](adapters/outbound/README_LITELLM.md)
- [Ollama Documentation](https://ollama.com/docs)
- [HuggingFace Sentence Transformers](https://www.sbert.net/)
- [IBM watsonx.ai Documentation](https://www.ibm.com/watsonx/developer/)
- [OpenAI Embeddings Guide](https://platform.openai.com/docs/guides/embeddings)

## Support

For issues or questions:

1. Check this documentation
2. Review provider-specific documentation
3. Open an issue in the datasift-opensource repository
