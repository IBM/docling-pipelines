---
title: Document Classification Operator
---

# Document Classification Operator

## Overview

The Document Classification operator classifies documents into predefined types using Large Language Models (LLMs) with confidence scoring and reasoning. It uses a **simplified service-based architecture** that leverages shared LLM infrastructure for multi-provider support.

### Key Features

- **Multi-Provider Support**: LiteLLM (100+ providers including Ollama via OpenAI-compatible API) and IBM Watsonx.ai
- **Confidence Scoring**: 1-10 scale confidence scores for each classification
- **Reasoning Output**: Optional explanations for classification decisions
- **Flexible Document Types**: Support for both simple lists and detailed descriptions
- **Parallel Processing**: Efficient batch processing with configurable workers
- **Shared Infrastructure**: Leverages common LLM adapter factory for consistency

### Operator Category

**Quality** - Document classification and enrichment

---

## Architecture

### Simplified Service-Based Architecture

The operator uses a streamlined architecture that leverages shared LLM infrastructure:

```
┌─────────────────────────────────────────────────────────────┐
│                   DocumentClassifierOperator                 │
│                     (Main Operator)                          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  ClassificationService                       │
│              (Business Logic Layer)                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Domain Models:                                       │  │
│  │  - ClassificationRequest                              │  │
│  │  - ClassificationResponse                             │  │
│  │  - build_classification_prompt()                      │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              Shared LLM Adapter Infrastructure               │
│                  (LLMAdapterFactory)                         │
└────────────────────────┬────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   LiteLLM    │  │  Watsonx.ai  │  │ HuggingFace  │
│   Client     │  │   Client     │  │   Client     │
└──────────────┘  └──────────────┘  └──────────────┘
```

### Component Responsibilities

#### 1. **Operator Layer** ([`document_classifier.py`](../../src/datasift/core/operators/quality/classification/document_classifier.py))
- Handles PyArrow table processing and orchestration
- Manages parallel document classification
- Integrates with job tracking and progress reporting

#### 2. **Service Layer** ([`classification_service.py`](../../src/datasift/core/operators/quality/classification/classification_service.py))
- Contains business logic for document classification
- Validates configuration parameters
- Manages LLM adapter lifecycle

#### 3. **Domain Layer** ([`domain/models.py`](../../src/datasift/core/operators/quality/classification/domain/models.py))
- Pure domain models: `ClassificationRequest`, `ClassificationResponse`
- Provider-agnostic prompt building logic
- No infrastructure dependencies

#### 4. **Infrastructure Layer** (Shared `LLMAdapterFactory`)
- Creates provider-specific LLM adapters (LiteLLM, Watsonx)
- Manages adapter configuration and initialization
- Provides unified `LLMInferencePort` interface

---

## Supported Providers

### 1. LiteLLM (100+ LLM Providers)

**Use Case**: Unified interface for OpenAI, Anthropic, Azure, AWS Bedrock, Google, Ollama (via OpenAI-compatible API), and 100+ other providers

**Configuration Examples**:

**OpenAI:**
```json
{
  "provider": "litellm",
  "model_id": "openai/gpt-4o-mini",
  "provider_config": {
    "api_key": "${OPENAI_API_KEY}"
  }
}
```

**Ollama (via OpenAI-compatible API):**
```json
{
  "provider": "litellm",
  "model_id": "openai/granite3.1-dense:8b",
  "provider_config": {
    "api_base": "http://localhost:11434/v1",
    "api_key": "ollama" # pragma: allowlist secret
  }
}
```

**Supported Providers**:
- OpenAI (openai/gpt-4, openai/gpt-4o-mini, openai/gpt-3.5-turbo)
- Anthropic (anthropic/claude-3-opus, anthropic/claude-3-sonnet, anthropic/claude-3-haiku)
- Azure OpenAI (azure/gpt-4)
- AWS Bedrock (bedrock/anthropic.claude-3-sonnet)
- Google Vertex AI (vertex_ai/gemini-pro)
- HuggingFace (huggingface/meta-llama/Llama-3.3-70B-Instruct)
- **Ollama via OpenAI-compatible endpoint** (openai/llama3.2:latest, openai/granite3.1-dense:8b with api_base)
- Cohere, Replicate, and 100+ more

**Requirements**:
- Valid API key for chosen provider (or "ollama" for local Ollama)
- Network access to API endpoint
- For Ollama: Server running on `http://localhost:11434`

**Advantages**:
- Single interface for 100+ providers
- Easy provider switching
- High-quality classifications
- Automatic retry and fallback support
- Local Ollama support via OpenAI-compatible API

### 2. Watsonx (IBM Watsonx.ai)

**Use Case**: Enterprise deployments with IBM Cloud infrastructure

**Configuration**:
```json
{
  "provider": "watsonx",
  "model_id": "ibm/granite-13b-chat-v2",
  "provider_config": {
    "api_base": "https://us-south.ml.cloud.ibm.com",
    "api_key": "${WATSONX_API_KEY}",
    "container_kind": "project",
    "container_id": "${WATSONX_PROJECT_ID}"
  }
}
```

**Requirements**:
- IBM Cloud account
- Watsonx.ai project or space
- Valid API key

**Advantages**:
- Enterprise-grade security
- Compliance certifications
- IBM support

---

## Configuration Parameters

### Required Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `provider` | string | LLM provider: `"litellm"` or `"watsonx"` |
| `model_id` | string | Model identifier in `<provider>/<model_id>` format for LiteLLM (e.g., `"openai/granite3.1-dense:8b"`, `"openai/gpt-4o-mini"`, `"anthropic/claude-3-sonnet"`), or plain format for Watsonx (e.g., `"ibm/granite-13b-chat-v2"`) |

### Optional Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `document_types` | list or dict | Auto-loaded | Document types to classify into |
| `confidence_threshold` | float | 7.0 | Minimum confidence for classification (1-10) |
| `doc_column` | string | `"content"` | Column containing document text |
| `output_column` | string | `"document_type"` | Column name for classification result |
| `include_confidence` | boolean | true | Include confidence score in output |
| `include_reasoning` | boolean | false | Include reasoning explanation in output |
| `max_content_length` | integer | 2000 | Maximum content length to send to LLM |
| `max_workers` | integer | Auto | Number of parallel workers |
| `use_processes` | boolean | false | Use processes instead of threads |

### Provider-Specific Configuration

#### LiteLLM
```json
{
  "provider": "litellm",
  "model_id": "openai/gpt-4o-mini",
  "provider_config": {
    "api_key": "${OPENAI_API_KEY}",
    "request_timeout": 120
  }
}
```

**Examples for different providers**:
```json
// OpenAI
{"provider": "litellm", "model_id": "openai/gpt-4o-mini"}

// Anthropic
{"provider": "litellm", "model_id": "anthropic/claude-3-sonnet-20240229"}

// Azure OpenAI
{"provider": "litellm", "model_id": "azure/gpt-4"}

// AWS Bedrock
{"provider": "litellm", "model_id": "bedrock/anthropic.claude-3-sonnet"}

// Google Vertex AI
{"provider": "litellm", "model_id": "vertex_ai/gemini-pro"}

// Ollama via OpenAI-compatible endpoint
{"provider": "litellm", "model_id": "openai/llama3.2:latest", "provider_config": {"api_base": "http://localhost:11434/v1"}}
{"provider": "litellm", "model_id": "openai/granite3.1-dense:8b", "provider_config": {"api_base": "http://localhost:11434/v1"}}

// HuggingFace
{"provider": "litellm", "model_id": "huggingface/meta-llama/Llama-3.3-70B-Instruct"}
```

#### Watsonx
```json
{
  "provider": "watsonx",
  "model_id": "ibm/granite-13b-chat-v2",
  "provider_config": {
    "api_base": "https://us-south.ml.cloud.ibm.com",
    "api_key": "${WATSONX_API_KEY}",
    "container_kind": "project",
    "container_id": "${WATSONX_PROJECT_ID}",
    "request_timeout": 120
  }
}
```

---

## Document Types Configuration

### Simple List Format

```json
{
  "document_types": [
    "invoice",
    "receipt",
    "contract",
    "report",
    "letter"
  ]
}
```

### Detailed Dictionary Format (Recommended)

```json
{
  "document_types": {
    "invoice": "Business invoice with line items, totals, and payment terms",
    "receipt": "Payment receipt or transaction confirmation",
    "contract": "Legal contract or agreement document",
    "report": "Business or technical report with analysis and findings",
    "letter": "Formal or informal correspondence letter",
    "email": "Email correspondence or message",
    "form": "Form or application document requiring completion",
    "purchase_order": "Purchase order for goods or services",
    "other": "Other document types not fitting above categories"
  }
}
```

**Benefits of Dictionary Format**:
- More accurate classifications
- Better handling of ambiguous documents
- Improved confidence scores

---

## Output Schema

The operator adds the following columns to the output table:

| Column | Type | Description | Always Present |
|--------|------|-------------|----------------|
| `document_type` | string | Classified document type | Yes |
| `document_type_confidence` | float | Confidence score (1-10) | If `include_confidence=true` |
| `document_type_reasoning` | string | Classification explanation | If `include_reasoning=true` |
| `content` | string | Document content (if fetched) | If not already present |

### Example Output

```python
{
  "id": "doc_001",
  "name": "invoice_2024.pdf",
  "content": "INVOICE\nDate: 2024-01-15\nTotal: $1,234.56...",
  "document_type": "invoice",
  "document_type_confidence": 9.5,
  "document_type_reasoning": "Document contains invoice header, line items, totals, and payment terms typical of business invoices"
}
```

---

## Usage Examples

### Example 1: Basic Classification with LiteLLM (Ollama via OpenAI-compatible API)

```json
{
  "id": "classify_node",
  "name": "classify",
  "operator": "document_classifier",
  "config": {
    "provider": "litellm",
    "model_id": "openai/granite3.1-dense:8b",
    "provider_config": {
      "api_base": "http://localhost:11434/v1",
      "api_key": "ollama" # pragma: allowlist secret
    },
    "document_types": ["invoice", "receipt", "contract", "report"],
    "confidence_threshold": 7.0,
    "include_confidence": true,
    "include_reasoning": false
  }
}
```

### Example 2: Detailed Classification with LiteLLM (OpenAI)

```json
{
  "id": "classify_node",
  "name": "classify",
  "operator": "document_classifier",
  "config": {
    "provider": "litellm",
    "model_id": "openai/gpt-4o-mini",
    "provider_config": {
      "api_key": "${OPENAI_API_KEY}"
    },
    "document_types": {
      "invoice": "Business invoice with line items and totals",
      "receipt": "Payment receipt or confirmation",
      "contract": "Legal contract or agreement",
      "report": "Business or technical report"
    },
    "confidence_threshold": 8.0,
    "include_confidence": true,
    "include_reasoning": true,
    "max_content_length": 4000
  }
}
```

### Example 3: Enterprise Classification with Watsonx

```json
{
  "id": "classify_node",
  "name": "classify",
  "operator": "document_classifier",
  "config": {
    "provider": "watsonx",
    "model_id": "ibm/granite-13b-chat-v2",
    "provider_config": {
      "api_base": "https://us-south.ml.cloud.ibm.com",
      "api_key": "${WATSONX_API_KEY}",
      "container_kind": "project",
      "container_id": "${WATSONX_PROJECT_ID}"
    },
    "document_types": {
      "invoice": "Business invoice document",
      "contract": "Legal contract or agreement",
      "report": "Business report or analysis"
    },
    "confidence_threshold": 7.5,
    "include_confidence": true,
    "include_reasoning": true
  }
}
```

### Example 4: Complete Flow with Classification

```json
{
  "flow_name": "Document Classification Pipeline",
  "description": "Classify documents using LiteLLM with Ollama",
  "global_config": {
    "doc_column": "content"
  },
  "flow": [
    {
      "name": "ingest",
      "type": "ingest_local",
      "config": {
        "paths": "./documents",
        "store_binary_content": true
      }
    },
    {
      "name": "extract",
      "type": "extract_operator",
      "depends_on": ["ingest"],
      "config": {
        "doc_column": "content"
      }
    },
    {
      "name": "classify",
      "type": "document_classifier",
      "depends_on": ["extract"],
      "config": {
        "provider": "litellm",
        "model_id": "openai/granite3.1-dense:8b",
        "provider_config": {
          "api_base": "http://localhost:11434/v1",
          "api_key": "ollama" # pragma: allowlist secret
        },
        "document_types": {
          "invoice": "Business invoice with line items",
          "receipt": "Payment receipt",
          "contract": "Legal contract",
          "other": "Other document types"
        },
        "confidence_threshold": 7.0,
        "include_confidence": true,
        "include_reasoning": true
      }
    }
  ]
}
```

---

## Best Practices

### 1. Document Type Definitions

**DO**:
- Use descriptive document type names
- Provide detailed descriptions in dictionary format
- Include an "other" category for unclassified documents
- Keep type count reasonable (5-15 types optimal)

**DON'T**:
- Use overly similar type names
- Create too many granular categories
- Use ambiguous descriptions

### 2. Confidence Threshold

- **7.0-8.0**: Balanced accuracy and coverage (recommended)
- **8.0-9.0**: High precision, may miss some documents
- **6.0-7.0**: High recall, may include false positives

### 3. Content Length

- **2000 chars**: Fast, good for simple documents
- **4000 chars**: Balanced, works for most documents
- **8000+ chars**: Detailed analysis, slower processing

### 4. Provider Selection

| Use Case | Recommended Provider |
|----------|---------------------|
| Local/Privacy | LiteLLM with Ollama (via OpenAI-compatible API) |
| High Accuracy | LiteLLM (GPT-4, Claude-3-Opus) |
| Enterprise | Watsonx or LiteLLM (Azure/Bedrock) |
| Cost-Effective | LiteLLM with Ollama or LiteLLM (GPT-4o-mini) |
| Multi-Provider | LiteLLM (100+ providers) |

### 5. Performance Optimization

```json
{
  "max_workers": 4,
  "use_processes": false,
  "max_content_length": 2000
}
```

- Use threads for I/O-bound operations (API calls)
- Adjust `max_workers` based on API rate limits
- Reduce `max_content_length` for faster processing

---

---

## Troubleshooting

### Issue: "Failed to initialize classification adapter"

**Cause**: Missing or invalid provider configuration

**Solution**:
- Verify provider name is correct (`litellm`, `watsonx`)
- Check all required provider_config parameters
- Ensure API keys and endpoints are valid
- For LiteLLM, verify model ID format matches provider (e.g., `openai/gpt-4o-mini`, `anthropic/claude-3-sonnet-20240229`)
- For Ollama via LiteLLM, ensure api_base is set to `http://localhost:11434/v1`

### Issue: Low confidence scores

**Cause**: Ambiguous document types or insufficient descriptions

**Solution**:
- Use dictionary format with detailed descriptions
- Reduce number of similar document types
- Increase `max_content_length` for more context

### Issue: "Empty content for document"

**Cause**: Document content not extracted or column name mismatch

**Solution**:
- Ensure `extract_operator` runs before classification
- Verify `doc_column` matches extraction output
- Check document extraction was successful

### Issue: Slow processing

**Cause**: Large documents or sequential processing

**Solution**:
- Reduce `max_content_length`
- Increase `max_workers` (respect API rate limits)
- Use faster models (e.g., `gpt-4o-mini` instead of `gpt-4`)

### Issue: Ollama connection failed

**Cause**: Ollama server not running

**Solution**:
```bash
# Start Ollama server
ollama serve

# Pull required model
ollama pull granite4:latest

# Verify server is running
curl http://localhost:11434/api/tags
```

---

## Test Flows

Sample test flows are available in `tests/sample_test_flows/classification/`:

- `flow_classify_ollama.json`: Ollama provider example
- `flow_classify_litellm_ollama_openai_compat.json`: LiteLLM with OpenAI-compatible endpoint example
- `flow_classify_watsonx.json`: Watsonx provider example

---

## API Reference

### ClassificationService

```python
class ClassificationService:
    """Simplified classification service using LLM adapters directly."""
    
    def __init__(
        self,
        *,
        model_id: str | None = None,
        provider_name: str,
        provider_config: dict[str, Any] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 500,
    ) -> None:
        """Initialize classification service."""
        pass
    
    def classify_document(self, *, request: ClassificationRequest) -> ClassificationResponse:
        """Classify a document using the LLM adapter.
        
        Args:
            request: Classification request with content and document types
            
        Returns:
            Classification response with type, confidence, and reasoning
        """
        pass
    
    def get_model_info(self) -> dict[str, Any]:
        """Get model information.
        
        Returns:
            Dictionary with model_id, provider, temperature, and max_tokens
        """
        pass
    
    @staticmethod
    def validate_config(
        *,
        provider: str | None = None,
        model_id: str | None = None,
        provider_config: dict[str, Any] | None = None,
        document_types: list[str] | dict[str, str] | None = None,
        confidence_threshold: float | None = None,
    ) -> tuple[list[str], list[str]]:
        """Validate classification configuration parameters.
        
        Validates:
        - Provider is 'litellm' or 'watsonx' (rejects 'ollama')
        - provider_config is present for both litellm and watsonx providers
        - model_id is not empty
        - document_types is valid list or dict
        - confidence_threshold is between 1.0 and 10.0
        
        Returns:
            Tuple of (errors, warnings) lists
        """
        pass
```

### Domain Models

```python
@dataclass
class ClassificationRequest:
    content: str
    document_types: list[str] | dict[str, str]
    max_content_length: int = 2000
    confidence_threshold: float = 7.0

@dataclass
class ClassificationResponse:
    document_type: str
    confidence: float
    reasoning: str
    success: bool
    error: str | None = None

@dataclass
class ModelInfo:
    name: str
    provider: str
    supports_json_mode: bool = True
    max_tokens: int = 4096
```

---

## Related Documentation

- [Extract Operator](./extract_operator.md) - Document content extraction
- [Embeddings Operator](./embeddings.md) - Vector embeddings generation
- [Architecture Guide](../../ARCHITECTURE.md) - System architecture overview
- [Operator Reference](../../OPERATOR_REFERENCE.md) - Complete operator API reference

---

## Version History

- **v2.0.0** : Simplified architecture
  - Removed hexagonal architecture (ports/adapters) in favor of simplified service-based design
  - Leverages shared LLM infrastructure (`LLMAdapterFactory`)
  - Removed standalone Ollama provider (use LiteLLM with OpenAI-compatible API instead)
  - Added `validate_config()` static method for configuration validation
  - Supports LiteLLM (100+ providers) and Watsonx
- **v1.1.0** : LiteLLM integration
  - Replaced OpenAI adapter with LiteLLM adapter
  - Support for 100+ LLM providers (OpenAI, Anthropic, Azure, AWS Bedrock, Google, etc.)
  - Unified interface for all providers
- **v1.0.0** : Initial release
  - Ollama, LiteLLM, and Watsonx providers
  - Confidence scoring and reasoning