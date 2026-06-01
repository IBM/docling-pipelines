# PII and HAP Detection Operator

## Overview

The PII and HAP Detection operator identifies and annotates sensitive content in documents using Large Language Models (LLMs). It uses the **common infrastructure architecture** with shared ports and adapters for consistent, maintainable provider integrations.

## Architecture

The operator implements a service-based architecture that wraps common infrastructure components:

```
┌─────────────────────────────────────────────────────────────┐
│                    PIIAndHAPAnnotator                        │
│                   (Operator - Orchestration)                 │
└────────────────────────┬────────────────────────────────────┘
                         │ uses
                         ▼
              ┌──────────────────────┐
              │   PIIHAPService      │
              │  (Business Logic)    │
              └──────────┬───────────┘
                         │ depends on
         ┌───────────────┴───────────────┐
         │                               │
         ▼                               ▼
┌─────────────────────┐         ┌─────────────────────┐
│ LLMInferencePort    │         │ TextDetectionPort   │
│ (Common Interface)  │         │ (Common Interface)  │
└──────────┬──────────┘         └──────────┬──────────┘
           │                               │
    ┌──────┴──────┐                 ┌─────┴─────┐
    │             │                 │           │
    ▼             ▼                 ▼           ▼
┌─────────┐  ┌─────────┐      ┌─────────┐ ┌──────────┐
│LiteLLM  │  │WatsonX  │      │WatsonX  │ │ Future   │
│Inference│  │Inference│      │  Text   │ │ Adapters │
│Adapter  │  │Adapter  │      │Detection│ │          │
└─────────┘  └─────────┘      └─────────┘ └──────────┘
```

### Key Components

#### 1. Operator Layer
- **PIIAndHAPAnnotator**: Orchestrates detection workflow, manages PyArrow tables, handles redaction

#### 2. Service Layer
- **PIIHAPService**: Business logic layer that wraps common ports
- Implements dual detection paths (WatsonX specialized API vs LiteLLM prompt-based)
- Handles prompt generation, response parsing, error handling

#### 3. Common Infrastructure (`src/datasift/core/adapters/`)
- **Ports**: Interface contracts (LLMInferencePort, TextDetectionPort)
- **Adapters**: Provider implementations (WatsonX, LiteLLM)
- **Factories**: Adapter creation and registration

## Supported Providers

### 1. LiteLLM (Default - Recommended)

**Use Case**: Access Ollama and 100+ LLM providers through unified interface

**Configuration for Ollama**:
```json
{
  "operator": "pii_and_hap",
  "config": {
    "provider": "litellm",
    "model_name": "openai/granite3.1-dense:8b",
    "provider_config": {
      "api_key": "${LITELLM_API_KEY}",
      "api_base": "http://localhost:11434/v1"
    }
  }
}
```

**Configuration for OpenAI**:
```json
{
  "operator": "pii_and_hap",
  "config": {
    "provider": "litellm",
    "model_name": "gpt-4",
    "provider_config": {
      "api_key": "${OPENAI_API_KEY}"
    }
  }
}
```

**Configuration for Anthropic**:
```json
{
  "operator": "pii_and_hap",
  "config": {
    "provider": "litellm",
    "model_name": "claude-3-opus-20240229",
    "provider_config": {
      "api_key": "${ANTHROPIC_API_KEY}"
    }
  }
}
```

**Requirements**:
- For Ollama: Ollama server running on `http://localhost:11434`
- For cloud providers: Valid API key for the chosen provider

**Supported Providers** (100+):
- OpenAI (gpt-4, gpt-3.5-turbo)
- Anthropic (claude-3-opus, claude-3-sonnet)
- Azure OpenAI
- Cohere (command, command-light)
- AWS Bedrock
- Google Vertex AI
- Hugging Face
- And many more...

### 2. WatsonX.ai

**Use Case**: Enterprise deployments with IBM WatsonX, specialized detection API

**Configuration**:
```json
{
  "operator": "pii_and_hap",
  "config": {
    "provider": "watsonx",
    "provider_config": {
      "api_key": "${WATSONX_API_KEY}",
      "api_base": "https://us-south.ml.cloud.ibm.com",
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

**Features**:
- Native `/ml/v1/text/detection` API endpoint
- IAM token caching (55-minute cache with 5-minute buffer)
- Automatic token refresh
- Retry logic with exponential backoff

## Detection Types

### PII (Personally Identifiable Information)
- Email addresses
- Phone numbers
- Social Security Numbers (SSN)
- Credit card numbers
- IP addresses
- Bank account numbers
- Names
- Addresses
- Dates of birth
- Medical record numbers

### HAP (Hate, Abuse, and Profanity)
- Hate speech
- Abusive language
- Profanity
- Discriminatory content
- Threatening language
- Harassment

## Output Format

The operator adds PII/HAP detection columns to the PyArrow table:

```
Columns added:
- pii_email_address: Count of email addresses detected
- pii_phone_number: Count of phone numbers detected
- pii_ssn_details: Count of SSNs detected
- pii_credit_card: Count of credit cards detected
- pii_ip_address: Count of IP addresses detected
- pii_bank_account: Count of bank accounts detected
- hap: Count of HAP instances detected

Optional (when display_pii=true):
- pii_email_address_info: Detailed detection info with text
- pii_phone_number_info: Detailed detection info with text
- ... (similar for other PII types)
```

## Configuration Parameters

### Common Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `provider` | string | No | "litellm" | Detection provider: "watsonx" or "litellm" |
| `model_name` | string | Conditional | "granite4" | Model name (required for litellm) |
| `provider_config` | dict | No | {} | Provider-specific configuration |
| `pii_threshold` | float | No | 0.5 | PII detection confidence threshold (0.0-1.0) |
| `hap_threshold` | float | No | 0.8 | HAP detection confidence threshold (0.0-1.0) |
| `redaction` | boolean | No | false | Enable PII redaction in document content |
| `hap_redaction` | boolean | No | false | Enable HAP redaction in document content |
| `display_pii` | boolean | No | false | Include actual PII values in output columns |
| `expected_redactions` | list | No | ["pii", "hap"] | Types to detect/redact |
| `batch_size` | int | No | 4 | Parallel processing batch size |

### Provider-Specific Parameters

#### LiteLLM
- `api_key`: Provider API key (optional, can use environment variables)
- `api_base`: Custom API base URL (required for Ollama: `http://localhost:11434/v1`)
- Additional provider-specific parameters (temperature, max_tokens, etc.)

#### WatsonX
- `api_key`: IBM Cloud API key (required)
- `api_base`: WatsonX.ai service URL (required)
- `container_id`: Project/Space/Catalog ID (required)
- `container_kind`: "project", "space", or "catalog" (required)
- `timeout`: Request timeout in seconds (optional, default: 300)

## Example Flows

### Basic PII Detection with Ollama (via LiteLLM)

```json
{
  "flow_name": "pii-detection-ollama",
  "description": "Basic PII detection pipeline using Ollama via LiteLLM",
  "global_config": {
    "doc_column": "content",
    "disable_validation": false,
    "force_ingest": true
  },
  "flow": [
    {
      "name": "ingest",
      "type": "ingest_local",
      "config": {
        "paths": "data/documents"
      }
    },
    {
      "name": "extract",
      "type": "extract_operator",
      "depends_on": ["ingest"],
      "config": {
        "text_extraction": {
          "provider": "docling_library"
        }
      }
    },
    {
      "name": "pii_detection",
      "type": "pii_and_hap",
      "depends_on": ["extract"],
      "config": {
        "provider": "litellm",
        "model_name": "openai/granite3.1-dense:8b",
        "provider_config": {
          "api_key": "${LITELLM_API_KEY}",
          "api_base": "http://localhost:11434/v1"
        }
      }
    }
  ]
}
```

### Enterprise PII Detection with WatsonX

```json
{
  "flow_name": "pii-detection-watsonx",
  "description": "Enterprise PII detection pipeline using WatsonX",
  "global_config": {
    "doc_column": "content",
    "disable_validation": false,
    "force_ingest": true
  },
  "flow": [
    {
      "name": "ingest",
      "type": "ingest_source",
      "config": {
        "provider": "s3",
        "connection_params": {
          "bucket": "my-documents",
          "prefix": "sensitive/"
        }
      }
    },
    {
      "name": "extract",
      "type": "extract_operator",
      "depends_on": ["ingest"],
      "config": {
        "text_extraction": {
          "provider": "docling_library"
        }
      }
    },
    {
      "name": "pii_detection",
      "type": "pii_and_hap",
      "depends_on": ["extract"],
      "config": {
        "provider": "watsonx",
        "provider_config": {
          "api_key": "${WATSONX_API_KEY}",
          "api_base": "https://us-south.ml.cloud.ibm.com",
          "container_id": "${WATSONX_PROJECT_ID}",
          "container_kind": "project"
        }
      }
    }
  ]
}
```

## Best Practices

### 1. Provider Selection
- **Development**: Use LiteLLM with Ollama for fast local testing
- **Production**: Use WatsonX for enterprise compliance or LiteLLM for flexibility
- **Cost-sensitive**: Use LiteLLM with Ollama to avoid API costs

### 2. Model Selection
- **Ollama (via LiteLLM)**: Use `granite3.1-dense:8b` or `llama3.2` for balanced performance
- **OpenAI**: Use `gpt-4` for highest accuracy, `gpt-3.5-turbo` for cost efficiency
- **WatsonX**: Use recommended models from IBM documentation

### 3. Threshold Configuration
- Default PII threshold: 0.5 (50% confidence)
- Default HAP threshold: 0.8 (80% confidence)
- Adjust based on false positive/negative tolerance
- Lower thresholds = more detections (higher recall, lower precision)
- Higher thresholds = fewer detections (lower recall, higher precision)

### 4. Performance Optimization
- Use `batch_size` parameter to control parallel processing
- Use local Ollama for high-volume processing
- Consider chunking for very large documents
- Monitor API rate limits for cloud providers

### 5. Security
- Never commit API keys to version control
- Use environment variables for sensitive configuration
- Rotate API keys regularly
- Use IAM roles when possible (WatsonX)
- Enable redaction for sensitive data in logs

## Troubleshooting

### Ollama Connection Issues
```
Error: Failed to connect to Ollama server
```
**Solution**: 
1. Ensure Ollama is running: `ollama serve`
2. Verify model is pulled: `ollama pull granite3.1-dense:8b`
3. Check `api_base` is set to `http://localhost:11434/v1`

### WatsonX Authentication Errors
```
Error: Invalid IAM token
```
**Solution**: 
1. Verify API key is correct
2. Ensure API key has WatsonX.ai permissions
3. Check container_id and container_kind are correct

### LiteLLM API Key Errors
```
Error: API key required for openai provider
```
**Solution**: 
1. Set environment variable: `export OPENAI_API_KEY=your-openai-api-key`
2. Or pass `api_key` in `provider_config`

### Model Not Found
```
Error: Model 'granite3.1-dense:8b' not found
```
**Solution**: Pull the model: `ollama pull granite3.1-dense:8b`

### Configuration Errors
```
Error: provider must be one of: watsonx, litellm
```
**Solution**: Ollama is not a direct provider. Use `provider="litellm"` with `api_base="http://localhost:11434/v1"`

## Testing

The operator includes comprehensive test coverage:

- **Unit Tests**: `tests/unit/operators/pii_and_hap/`
  - Operator tests (19 tests)
  - Service layer tests
  - Domain model tests

- **Adapter Tests**: `tests/unit/core/adapters/`
  - WatsonX adapter tests
  - LiteLLM adapter tests

Run tests:
```bash
# From project root
source .venv/bin/activate

# All PII/HAP tests
pytest tests/unit/operators/pii_and_hap/ -v

# Service layer tests
pytest tests/unit/operators/pii_and_hap/test_pii_hap_service.py -v

# Common adapter tests
pytest tests/unit/core/adapters/watsonx/ -v
pytest tests/unit/core/adapters/litellm/ -v
```

## Migration from Old Architecture

### New Configuration (Common Infrastructure)
```json
{
  "provider": "litellm",
  "model_name": "openai/granite4",
  "provider_config": {
    "api_key": "${LITELLM_API_KEY}",
    "api_base": "http://localhost:11434/v1"
  }
}
```

**Key Changes:**
1. Ollama is accessed via LiteLLM (not a direct provider)
2. Model name uses OpenAI-compatible format: `openai/model-name`
3. Must specify `api_base` for Ollama endpoint
4. Default provider changed from "ollama" to "litellm"

## Related Documentation

- [Operator README](../../../src/datasift/core/operators/quality/pii_and_hap/README.md) - Technical implementation details
- [Common Infrastructure](../../../src/datasift/core/adapters/README.md) - Shared ports and adapters
- [Architecture Guide](../../../ARCHITECTURE.md) - Overall system architecture
- [Phase 2 Refactoring Guide](../../../PHASE2_PII_HAP_REFACTORING.md) - Migration details
