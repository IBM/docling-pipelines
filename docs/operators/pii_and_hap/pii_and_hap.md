# PII and HAP Detection Operator

## Overview

The PII and HAP Detection operator identifies and annotates sensitive content in documents using Large Language Models (LLMs). It follows hexagonal architecture principles with support for multiple detection providers through a pluggable adapter system.

## Architecture

The operator implements hexagonal architecture (ports and adapters pattern) to maintain clean separation between business logic and external service integrations:

```
┌─────────────────────────────────────────────────────────────┐
│                    PIIAndHAPAnnotator                        │
│                   (Core Operator Logic)                      │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │  PIIHAPServicePort   │
              │     (Interface)      │
              └──────────┬───────────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
         ▼               ▼               ▼
   ┌──────────┐   ┌──────────┐   ┌──────────┐
   │  Ollama  │   │ WatsonX  │   │ LiteLLM  │
   │ Adapter  │   │ Adapter  │   │ Adapter  │
   └────┬─────┘   └────┬─────┘   └────┬─────┘
        │              │              │
        ▼              ▼              ▼
   ┌──────────┐   ┌──────────┐   ┌──────────┐
   │  Ollama  │   │ WatsonX  │   │ LiteLLM  │
   │  Server  │   │   API    │   │   API    │
   └──────────┘   └──────────┘   └──────────┘
```

### Key Components

#### 1. Domain Layer (`domain/`)
- **PIIDetectionResult**: Represents a single PII detection with type, score, location, and text
- **HAPDetectionResult**: Represents a single HAP detection with type, score, location, and text
- **PIIHAPDetectionResponse**: Aggregates all detections for a document

#### 2. Port Layer (`ports/outbound/`)
- **PIIHAPServicePort**: Interface defining the contract for detection services
  - `detect_pii_hap(payload: dict) -> PIIHAPDetectionResponse`
  - `cleanup() -> None`

#### 3. Adapter Layer (`adapters/outbound/`)
- **OllamaAdapter**: Local LLM detection using Ollama
- **WatsonXAdapter**: IBM WatsonX.ai detection API
- **LiteLLMAdapter**: Multi-provider support (OpenAI, Anthropic, Azure, Cohere, Bedrock, Vertex AI, 100+ providers)

#### 4. Factory Pattern (`adapters/outbound/factories/`)
- **PIIHAPAdapterFactory**: Registry-based factory for creating adapters
- Supports dynamic adapter registration via `@register_pii_hap_adapter` decorator

## Supported Providers

### 1. Ollama (Local LLM)

**Use Case**: Local development, privacy-sensitive deployments, offline processing

**Configuration**:
```json
{
  "operator": "pii_and_hap",
  "config": {
    "provider": "ollama",
    "model_name": "granite3.1-dense:8b",
    "provider_config": {}
  }
}
```

**Requirements**:
- Ollama server running on `http://localhost:11434`
- Model pulled: `ollama pull granite3.1-dense:8b`

### 2. WatsonX.ai

**Use Case**: Enterprise deployments, IBM Cloud environments, regulated industries

**Configuration**:
```json
{
  "operator": "pii_and_hap",
  "config": {
    "provider": "watsonx",
    "provider_config": {
      "api_key": "your-ibm-cloud-api-key", # pragma: allowlist secret
      "url": "https://us-south.ml.cloud.ibm.com",
      "container_id": "your-project-id",
      "container_kind": "project"
    }
  }
}
```

**Requirements**:
- IBM Cloud account
- WatsonX.ai service instance
- IAM API key with appropriate permissions

### 3. LiteLLM (Multi-Provider)

**Use Case**: Flexible provider selection, cloud-based deployments, production workloads

**Configuration**:

**OpenAI**:
```json
{
  "operator": "pii_and_hap",
  "config": {
    "provider": "litellm",
    "model_name": "gpt-4",
    "provider_config": {
      "api_key": "sk-..." # pragma: allowlist secret
    }
  }
}
```

**Anthropic**:
```json
{
  "operator": "pii_and_hap",
  "config": {
    "provider": "litellm",
    "model_name": "claude-3-opus-20240229",
    "provider_config": {
      "api_key": "sk-ant-..." # pragma: allowlist secret
    }
  }
}
```

**Azure OpenAI**:
```json
{
  "operator": "pii_and_hap",
  "config": {
    "provider": "litellm",
    "model_name": "azure/gpt-4-deployment",
    "provider_config": {
      "api_key": "your-azure-key", # pragma: allowlist secret
      "api_base": "https://your-resource.openai.azure.com"
    }
  }
}
```

**Supported Providers** (100+):
- OpenAI (gpt-4, gpt-3.5-turbo)
- Anthropic (claude-3-opus, claude-3-sonnet)
- Azure OpenAI
- Cohere (command, command-light)
- AWS Bedrock (bedrock/anthropic.claude-v2)
- Google Vertex AI (vertex_ai/gemini-pro)
- Hugging Face
- And many more...

## Detection Types

### PII (Personally Identifiable Information)
- Email addresses
- Phone numbers
- Social Security Numbers
- Credit card numbers
- Addresses
- Names
- Dates of birth
- Medical record numbers
- Financial account numbers

### HAP (Hate, Abuse, and Profanity)
- Hate speech
- Abusive language
- Profanity
- Discriminatory content
- Threatening language
- Harassment

## Output Format

The operator adds a `pii_hap_detections` column to the PyArrow table with the following structure:

```json
{
  "detections": [
    {
      "detection": "email",
      "detection_type": "pii",
      "score": 0.95,
      "start": 12,
      "end": 29,
      "text": "john@example.com"
    },
    {
      "detection": "profanity",
      "detection_type": "hap",
      "score": 0.88,
      "start": 45,
      "end": 52,
      "text": "badword"
    }
  ]
}
```

## Configuration Parameters

### Common Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `provider` | string | Yes | - | Detection provider: "ollama", "watsonx", or "litellm" |
| `model_name` | string | Conditional | - | Model name (required for ollama and litellm) |
| `provider_config` | dict | No | {} | Provider-specific configuration |

### Provider-Specific Parameters

#### Ollama
- No additional parameters required
- Uses local Ollama server at `http://localhost:11434`

#### WatsonX
- `api_key`: IBM Cloud API key (required)
- `url`: WatsonX.ai service URL (required)
- `container_id`: Project or space or Catalog ID (required)
- `container_kind`: "project" or "space" or "catalog" (required)
- `timeout`: Request timeout in seconds (optional, default: 300)

#### LiteLLM
- `api_key`: Provider API key (optional, can use environment variables)
- `api_base`: Custom API base URL (optional)
- Additional provider-specific parameters (temperature, max_tokens, etc.)

## Example Flows

### Basic PII Detection with Ollama

```json
{
  "nodes": [
    {
      "id": "ingest",
      "operator": "ingest_local",
      "config": {
        "input_folder": "data/documents"
      }
    },
    {
      "id": "extract",
      "operator": "extract_operator",
      "config": {
        "text_extraction_mode": "docling_library"
      }
    },
    {
      "id": "pii_detection",
      "operator": "pii_and_hap",
      "config": {
        "provider": "ollama",
        "model_name": "granite3.1-dense:8b"
      }
    }
  ],
  "edges": [
    {"from": "ingest", "to": "extract"},
    {"from": "extract", "to": "pii_detection"}
  ]
}
```

### Enterprise PII Detection with WatsonX

```json
{
  "nodes": [
    {
      "id": "ingest",
      "operator": "ingest_source",
      "config": {
        "source_type": "s3",
        "bucket": "my-documents",
        "prefix": "sensitive/"
      }
    },
    {
      "id": "extract",
      "operator": "extract_operator",
      "config": {
        "text_extraction_mode": "docling_library"
      }
    },
    {
      "id": "pii_detection",
      "operator": "pii_and_hap",
      "config": {
        "provider": "watsonx",
        "provider_config": {
          "api_key": "${WATSONX_API_KEY}", # pragma: allowlist secret
          "url": "https://us-south.ml.cloud.ibm.com",
          "container_id": "${WATSONX_PROJECT_ID}",
          "container_kind": "project"
        }
      }
    }
  ],
  "edges": [
    {"from": "ingest", "to": "extract"},
    {"from": "extract", "to": "pii_detection"}
  ]
}
```

## Best Practices

### 1. Provider Selection
- **Development**: Use Ollama for fast local testing
- **Production**: Use WatsonX for enterprise compliance or LiteLLM for flexibility
- **Cost-sensitive**: Use Ollama to avoid API costs

### 2. Model Selection
- **Ollama**: Use `granite3.1-dense:8b` or `llama3.2` for balanced performance
- **LiteLLM**: Use `gpt-4` for highest accuracy, `gpt-3.5-turbo` for cost efficiency
- **WatsonX**: Use recommended models from IBM documentation

### 3. Threshold Configuration
- Default PII threshold: 0.5 (50% confidence)
- Default HAP threshold: 0.8 (80% confidence)
- Adjust based on false positive/negative tolerance

### 4. Performance Optimization
- Batch documents when possible
- Use local Ollama for high-volume processing
- Consider caching for repeated content
- Monitor API rate limits for cloud providers

### 5. Security
- Never commit API keys to version control
- Use environment variables for sensitive configuration
- Rotate API keys regularly
- Use IAM roles when possible (WatsonX)

## Troubleshooting

### Ollama Connection Issues
```
Error: Failed to connect to Ollama server
```
**Solution**: Ensure Ollama is running: `ollama serve`

### WatsonX Authentication Errors
```
Error: Invalid IAM token
```
**Solution**: Verify API key and ensure it has WatsonX.ai permissions

### LiteLLM API Key Errors
```
Error: API key required for openai provider
```
**Solution**: Set environment variable or pass `api_key` in `provider_config`

### Model Not Found
```
Error: Model 'granite3.1-dense:8b' not found
```
**Solution**: Pull the model: `ollama pull granite3.1-dense:8b`

## Testing

The operator includes comprehensive test coverage:

- **Unit Tests**: `tests/unit/operators/pii_and_hap/`
  - Adapter tests for each provider
  - Domain model tests
  - Factory pattern tests
  - Integration tests

Run tests:
```bash
# From project root
source .venv/bin/activate
export PYTHONPATH="$(pwd)/src/datasift:${PYTHONPATH}"
uv run pytest tests/unit/operators/pii_and_hap/ -v
```

## Related Documentation

- [PII and HAP Configuration Guide](pii_and_hap_config.md) - Complete configuration reference with all parameters
- [Operator README](../../src/datasift/core/operators/quality/pii_and_hap/README.md) - Detailed technical documentation
- [Architecture Guide](../ARCHITECTURE.md) - Hexagonal architecture patterns
- [Ollama Setup](../README.md#embeddings-operator--ollama-setup) - Ollama installation guide
- [LiteLLM Documentation](../../src/datasift/core/operators/functional/embeddings/adapters/outbound/README_LITELLM.md) - LiteLLM provider guide
