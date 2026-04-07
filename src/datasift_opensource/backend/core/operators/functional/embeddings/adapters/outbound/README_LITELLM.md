# LiteLLM Adapter Documentation

## Overview

The LiteLLM adapter provides a unified interface for generating embeddings across multiple AI providers including OpenAI, Anthropic, Cohere, Azure, and many others. It leverages the [LiteLLM](https://github.com/BerriAI/litellm) library to abstract provider-specific implementations.

## Supported Providers

LiteLLM supports 100+ embedding models from various providers:

### Major Providers

- **OpenAI**: `text-embedding-3-small`, `text-embedding-3-large`, `text-embedding-ada-002`
- **Azure OpenAI**: Azure-hosted OpenAI models
- **Cohere**: `embed-english-v3.0`, `embed-multilingual-v3.0`
- **Anthropic**: Claude models (via embeddings API)
- **Vertex AI**: Google Cloud AI models
- **Bedrock**: AWS Bedrock models
- **Hugging Face**: API-hosted models

For a complete list, see [LiteLLM Supported Models](https://docs.litellm.ai/docs/embedding/supported_embedding).

## Configuration

### Basic Configuration

```python
{
    "operator_type": "datasift_opensource.backend.core.operators.functional.embeddings.embeddings_operator.EmbeddingsOperator",
    "operator_params": {
        "provider": "litellm",
        "model_name": "text-embedding-3-small",
        "api_key": "your-api-key-here"  # pragma: allowlist secret  # Optional if using env var
    }
}
```

### Environment Variables

LiteLLM automatically detects API keys from environment variables based on the provider:

| Provider     | Environment Variable                         | Example                          |
| ------------ | -------------------------------------------- | -------------------------------- |
| OpenAI       | `OPENAI_API_KEY`                             | `export OPENAI_API_KEY=sk-...`   |
| Azure OpenAI | `AZURE_API_KEY`                              | `export AZURE_API_KEY=...`       |
| Cohere       | `COHERE_API_KEY`                             | `export COHERE_API_KEY=...`      |
| Anthropic    | `ANTHROPIC_API_KEY`                          | `export ANTHROPIC_API_KEY=...`   |
| Vertex AI    | `VERTEXAI_PROJECT`, `VERTEXAI_LOCATION`      | See Vertex AI docs               |
| Bedrock      | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | See AWS docs                     |
| Hugging Face | `HUGGINGFACE_API_KEY`                        | `export HUGGINGFACE_API_KEY=...` |

**Recommendation**: Use environment variables instead of hardcoding API keys in configuration files.

### Advanced Configuration

```python
{
    "operator_type": "datasift_opensource.backend.core.operators.functional.embeddings.embeddings_operator.EmbeddingsOperator",
    "operator_params": {
        "provider": "litellm",
        "model_name": "text-embedding-3-small",
        "api_key": "your-api-key-here",  # pragma: allowlist secret  # Optional
        "api_base": "https://custom-endpoint.com/v1"  # Optional: custom API endpoint
    }
}
```

## Provider-Specific Examples

### OpenAI

```python
# Using environment variable (recommended)
export OPENAI_API_KEY=sk-proj-...

# Flow configuration
{
    "operator_params": {
        "provider": "litellm",
        "model_name": "text-embedding-3-small"
    }
}
```

**Available Models**:

- `text-embedding-3-small` (1536 dimensions, $0.02/1M tokens)
- `text-embedding-3-large` (3072 dimensions, $0.13/1M tokens)
- `text-embedding-ada-002` (1536 dimensions, legacy)

### Azure OpenAI

```bash
# Set environment variables
export AZURE_API_KEY=your-azure-key
export AZURE_API_BASE=https://your-resource.openai.azure.com
export AZURE_API_VERSION=2023-05-15
```

```python
{
    "operator_params": {
        "provider": "litellm",
        "model_name": "azure/your-deployment-name"
    }
}
```

### Cohere

```bash
export COHERE_API_KEY=your-cohere-key
```

```python
{
    "operator_params": {
        "provider": "litellm",
        "model_name": "embed-english-v3.0"
    }
}
```

**Available Models**:

- `embed-english-v3.0` (1024 dimensions, English only)
- `embed-multilingual-v3.0` (1024 dimensions, 100+ languages)
- `embed-english-light-v3.0` (384 dimensions, faster)

### Vertex AI (Google Cloud)

```bash
export VERTEXAI_PROJECT=your-project-id
export VERTEXAI_LOCATION=us-central1
```

```python
{
    "operator_params": {
        "provider": "litellm",
        "model_name": "vertex_ai/textembedding-gecko@001"
    }
}
```

### AWS Bedrock

```bash
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key
export AWS_REGION_NAME=us-east-1
```

````python
{
    "operator_params": {
        "provider": "litellm",
        "model_name": "bedrock/amazon.titan-embed-text-v1"
    }
}

### IBM watsonx.ai

IBM watsonx.ai provides enterprise-grade embedding models optimized for retrieval tasks.

**Environment Variables**:
```bash
export WATSONX_URL=https://us-south.ml.cloud.ibm.com  # Your watsonx instance URL
export WATSONX_APIKEY=your-api-key                     # pragma: allowlist secret  # IBM Cloud API key
export WATSONX_PROJECT_ID=your-project-id              # Project ID (optional if passed as param)
````

**Authentication Options**:

- `WATSONX_APIKEY`: IBM Cloud API key (recommended)
- `WATSONX_TOKEN`: IAM auth token (short-lived)
- `WATSONX_ZENAPIKEY`: Zen API key (long-term authentication)

**Flow Configuration**:

```json
{
  "operator_type": "datasift_opensource.backend.core.operators.functional.embeddings.embeddings_operator.EmbeddingsOperator",
  "operator_params": {
    "provider": "litellm",
    "model_name": "watsonx/ibm/slate-125m-english-rtrvr",
    "project_id": "your-project-id"
  }
}
```

**Available Models**:

- `watsonx/ibm/slate-30m-english-rtrvr` - 30M parameter model
- `watsonx/ibm/slate-125m-english-rtrvr` - 125M parameter model

For all available models, see [watsonx.ai embedding documentation](https://dataplatform.cloud.ibm.com/docs/content/wsj/analyze-data/fm-models-embed.html?context=wx).

**Python Example**:

```python
import pyarrow as pa
from datasift_opensource.backend.core.operators.functional.embeddings.embeddings_operator import EmbeddingsOperator

# Initialize operator
operator = EmbeddingsOperator(
    provider="litellm",
    model_name="watsonx/ibm/slate-125m-english-rtrvr",
    project_id="your-project-id"  # Optional if set in environment
)

# Create sample data
table = pa.table({
    "text": ["Enterprise document processing", "AI-powered embeddings"],
    "doc_id": ["doc1", "doc2"]
})

# Generate embeddings
result = operator.process(table)
print(f"Generated {len(result)} embeddings")
```

**Notes**:

- watsonx.ai models are optimized for enterprise use cases
- Supports both cloud and on-premises deployments
- Requires IBM Cloud account or watsonx.ai subscription

## Usage Examples

### Complete Flow Example

```json
{
  "nodes": [
    {
      "id": "ingest",
      "operator_type": "datasift_opensource.backend.core.operators.ingest.ingest_local_folder.IngestLocalFolder",
      "operator_params": {
        "folder_path": "data/documents"
      }
    },
    {
      "id": "chunk",
      "operator_type": "datasift_opensource.backend.core.operators.functional.chunker.DoclingChunker",
      "operator_params": {
        "chunk_size": 512
      }
    },
    {
      "id": "embed",
      "operator_type": "datasift_opensource.backend.core.operators.functional.embeddings.embeddings_operator.EmbeddingsOperator",
      "operator_params": {
        "provider": "litellm",
        "model_name": "text-embedding-3-small"
      }
    }
  ],
  "edges": [
    { "from": "ingest", "to": "chunk" },
    { "from": "chunk", "to": "embed" }
  ]
}
```

### Python Script Example

```python
from datasift_opensource.backend.core.operators.functional.embeddings.embeddings_operator import EmbeddingsOperator
import pyarrow as pa

# Initialize operator
operator = EmbeddingsOperator(
    provider="litellm",
    model_name="text-embedding-3-small"
)

# Create sample data
table = pa.table({
    "text": ["Hello world", "LiteLLM is awesome"],
    "doc_id": ["doc1", "doc2"]
})

# Generate embeddings
result = operator.process(table)
print(f"Generated {len(result)} embeddings")
```

## Error Handling

### Common Errors

#### 1. Missing API Key

**Error**:

```
ExternalServiceError: The api_key client option must be set either by passing api_key to the client or by setting the OPENAI_API_KEY environment variable
```

**Solution**:

```bash
export OPENAI_API_KEY=sk-proj-your-key-here
```

#### 2. Invalid Model Name

**Error**:

```
ConfigurationError: Model 'invalid-model' not found
```

**Solution**: Check [LiteLLM Supported Models](https://docs.litellm.ai/docs/embedding/supported_embedding) for valid model names.

#### 3. Rate Limiting

**Error**:

```
ExternalServiceError: Rate limit exceeded
```

**Solution**: The adapter automatically retries with exponential backoff (3 attempts). If persistent, reduce batch size or add delays between requests.

#### 4. Network Timeout

**Error**:

```
ExternalServiceError: Request timeout after 30s
```

**Solution**: Check network connectivity and API endpoint availability. The adapter retries automatically.

## Performance Considerations

### Embedding Dimensions

Different models produce different embedding dimensions:

| Model                   | Dimensions | Use Case                        |
| ----------------------- | ---------- | ------------------------------- |
| text-embedding-3-small  | 1536       | General purpose, cost-effective |
| text-embedding-3-large  | 3072       | Higher accuracy, more expensive |
| embed-english-v3.0      | 1024       | English documents               |
| embed-multilingual-v3.0 | 1024       | Multilingual documents          |

### Cost Optimization

1. **Choose appropriate model**: Use smaller models for simple tasks
2. **Batch processing**: Process multiple texts in single API call (coming soon)
3. **Caching**: Cache embeddings for frequently accessed documents
4. **Monitor usage**: Track API calls and costs

### Rate Limits

Different providers have different rate limits:

- **OpenAI**: 3,000 requests/min (tier 1), 5,000 requests/min (tier 2+)
- **Cohere**: 10,000 requests/min (trial), higher for production
- **Azure**: Depends on deployment configuration

The adapter handles rate limiting with automatic retries and exponential backoff.

## Troubleshooting

### Debug Mode

Enable debug logging to see detailed API interactions:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Verify API Key

Test your API key manually:

```bash
# OpenAI
curl https://api.openai.com/v1/embeddings \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "input": "test",
    "model": "text-embedding-3-small"
  }'
```

### Check Provider Status

- **OpenAI**: https://status.openai.com/
- **Cohere**: https://status.cohere.com/
- **Azure**: https://status.azure.com/

## API Key Management and Security

### Security Best Practices

**✅ Recommended: Environment Variables**

```bash
export OPENAI_API_KEY=your-key-here
export COHERE_API_KEY=your-key-here
export WATSONX_APIKEY=your-key-here
```

**⚠️ Not Recommended: Flow Configuration**

```json
{
  "operator_params": {
    "provider": "litellm",
    "model_name": "text-embedding-3-small",
    "api_key": "sk-proj-..." // pragma: allowlist secret
  }
}
```

### Why Environment Variables?

1. **Not Version Controlled**: Environment variables aren't committed to Git
2. **Per-Environment**: Different keys for dev/staging/prod
3. **Standard Practice**: Industry-standard approach
4. **Audit Trail**: Easier to track and rotate keys

### When Flow-Based Keys Are Acceptable

- **Local development/testing only**
- **Temporary test keys**
- **Keys that will be immediately rotated**
- **Never in production**

### API Key Validation

The operator validates API key presence before making calls:

- Checks environment variables first
- Falls back to flow configuration if provided
- Shows security warning if API key is in flow
- Fails fast with clear error message if missing

Example error:

```
ConfigurationError: API key required for openai provider.
Please set OPENAI_API_KEY environment variable or pass api_key parameter.
Example: export OPENAI_API_KEY=your-key-here
```

### Provider-Specific Environment Variables

| Provider     | Environment Variable             |
| ------------ | -------------------------------- |
| OpenAI       | `OPENAI_API_KEY`                 |
| Azure OpenAI | `AZURE_API_KEY`                  |
| Cohere       | `COHERE_API_KEY`                 |
| Anthropic    | `ANTHROPIC_API_KEY`              |
| Vertex AI    | `GOOGLE_APPLICATION_CREDENTIALS` |
| Bedrock      | `AWS_ACCESS_KEY_ID`              |
| watsonx      | `WATSONX_APIKEY`                 |
| Hugging Face | `HUGGINGFACE_API_KEY`            |

## Security Best Practices

1. **Never commit API keys**: Use environment variables or secret management
2. **Rotate keys regularly**: Change API keys periodically
3. **Use least privilege**: Grant minimum required permissions
4. **Monitor usage**: Track API calls for anomalies
5. **Secure storage**: Store keys in secure vaults (AWS Secrets Manager, Azure Key Vault, etc.)

## Migration from Other Providers

### From Ollama

```python
# Before (Ollama)
{
    "provider": "ollama",
    "model_name": "nomic-embed-text"
}

# After (LiteLLM with OpenAI)
{
    "provider": "litellm",
    "model_name": "text-embedding-3-small"
}
```

### From HuggingFace Local

```python
# Before (HuggingFace local)
{
    "provider": "huggingface",
    "model_name": "sentence-transformers/all-MiniLM-L6-v2",
    "use_local": true
}

# After (LiteLLM with HuggingFace API)
{
    "provider": "litellm",
    "model_name": "huggingface/sentence-transformers/all-MiniLM-L6-v2"
}
```

## Additional Resources

- [LiteLLM Documentation](https://docs.litellm.ai/)
- [LiteLLM GitHub](https://github.com/BerriAI/litellm)
- [OpenAI Embeddings Guide](https://platform.openai.com/docs/guides/embeddings)
- [Cohere Embeddings Guide](https://docs.cohere.com/docs/embeddings)
- [Azure OpenAI Service](https://learn.microsoft.com/en-us/azure/ai-services/openai/)

## Support

For issues specific to:

- **LiteLLM adapter**: Open an issue in the datasift-opensource repository
- **LiteLLM library**: Check [LiteLLM GitHub Issues](https://github.com/BerriAI/litellm/issues)
- **Provider APIs**: Contact the respective provider's support
