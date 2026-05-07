---
title: Document Classification Operator
---

# Document Classification Operator

## Overview

The Document Classification operator classifies documents into predefined types using Large Language Models (LLMs) with confidence scoring and reasoning. It implements a **hexagonal architecture** (ports and adapters pattern) to support multiple LLM providers through a unified interface.

### Key Features

- **Multi-Provider Support**: Ollama, LiteLLM (100+ providers), and IBM Watsonx.ai
- **Confidence Scoring**: 1-10 scale confidence scores for each classification
- **Reasoning Output**: Optional explanations for classification decisions
- **Flexible Document Types**: Support for both simple lists and detailed descriptions
- **Parallel Processing**: Efficient batch processing with configurable workers
- **Extensible Architecture**: Easy to add new LLM providers via adapter pattern

### Operator Category

**Quality** - Document classification and enrichment

---

## Architecture

### Hexagonal Architecture (Ports and Adapters)

The operator follows hexagonal architecture principles to separate business logic from infrastructure concerns:

```
┌─────────────────────────────────────────────────────────────┐
│                   DocumentClassifierOperator                 │
│                     (Application Layer)                      │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    Domain Layer                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  ClassificationRequest                                │  │
│  │  ClassificationResponse                               │  │
│  │  ModelInfo                                            │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    Ports Layer                               │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  ClassificationServicePort (Interface)                │  │
│  │    - classify_document(request) -> response           │  │
│  │    - get_model_info() -> ModelInfo                    │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   Ollama     │  │   LiteLLM    │  │   Watsonx    │
│   Adapter    │  │   Adapter    │  │   Adapter    │
└──────────────┘  └──────────────┘  └──────────────┘
```

### Component Responsibilities

#### 1. **Domain Layer** ([`domain/models.py`](src/datasift/core/operators/quality/classification/domain/models.py))
- Pure business logic, no infrastructure dependencies
- [`ClassificationRequest`](src/datasift/core/operators/quality/classification/domain/models.py:8): Input data structure
- [`ClassificationResponse`](src/datasift/core/operators/quality/classification/domain/models.py:16): Output data structure
- [`ModelInfo`](src/datasift/core/operators/quality/classification/domain/models.py:24): Model metadata
- [`build_classification_prompt()`](src/datasift/core/operators/quality/classification/domain/models.py:31): Provider-agnostic prompt builder

#### 2. **Ports Layer** ([`ports/outbound/classification_service.py`](src/datasift/core/operators/quality/classification/ports/outbound/classification_service.py))
- [`ClassificationServicePort`](src/datasift/core/operators/quality/classification/ports/outbound/classification_service.py:9): Abstract interface defining classification contract
- Ensures all adapters implement the same interface

#### 3. **Adapters Layer** ([`adapters/outbound/`](src/datasift/core/operators/quality/classification/adapters/outbound))
- [`OllamaClassificationAdapter`](src/datasift/core/operators/quality/classification/adapters/outbound/ollama_adapter.py:18): Native Ollama API integration
- [`LiteLLMClassificationAdapter`](src/datasift/core/operators/quality/classification/adapters/outbound/litellm_adapter.py:18): Unified interface for 100+ LLM providers (OpenAI, Anthropic, Azure, AWS Bedrock, Google, etc.)
- [`WatsonxClassificationAdapter`](src/datasift/core/operators/quality/classification/adapters/outbound/watsonx_adapter.py:19): IBM Watsonx.ai REST API integration
- Each adapter translates between domain models and provider-specific APIs

#### 4. **Factory Layer** ([`adapters/outbound/factories/`](src/datasift/core/operators/quality/classification/adapters/outbound/factories))
- [`ClassificationAdapterFactory`](src/datasift/core/operators/quality/classification/adapters/outbound/factories/classification_adapter_factory.py:9): Registry-based adapter creation
- Decorator-based auto-registration via [`register_classification_adapter()`](src/datasift/core/operators/quality/classification/adapters/outbound/factories/classification_adapter_factory.py:60)
- Centralized adapter management

The active runtime operator remains [`DocumentClassifierOperator`](src/datasift/core/operators/quality/document_classifier.py:26), which delegates provider-specific classification to the runtime-native classification package under [`src/datasift/core/operators/quality/classification`](src/datasift/core/operators/quality/classification).

---

## Supported Providers

### 1. Ollama (Local LLM)

**Use Case**: Local, privacy-focused classification with no external API calls

**Configuration**:
```json
{
  "provider": "ollama",
  "model_id": "granite4:latest"
}
```

**Requirements**:
- Ollama server running on `http://localhost:11434`
- Model pulled: `ollama pull granite4:latest`

**Advantages**:
- No API costs
- Complete data privacy
- Low latency for local deployments

### 2. LiteLLM (100+ LLM Providers)

**Use Case**: Unified interface for OpenAI, Anthropic, Azure, AWS Bedrock, Google, and 100+ other providers

**Configuration**:
```json
{
  "provider": "litellm",
  "model_id": "openai/gpt-4o-mini",
  "provider_config": {
    "api_key": "${OPENAI_API_KEY}"
  }
}
```

**Supported Providers**:
- OpenAI (openai/gpt-4, openai/gpt-4o-mini, openai/gpt-3.5-turbo)
- Anthropic (claude-3-opus, claude-3-sonnet, claude-3-haiku)
- Azure OpenAI
- AWS Bedrock (Claude, Llama, Titan)
- Google Vertex AI (Gemini, PaLM)
- Cohere, Replicate, Hugging Face, and more

**Requirements**:
- Valid API key for chosen provider
- Network access to API endpoint

**Advantages**:
- Single interface for 100+ providers
- Easy provider switching
- High-quality classifications
- Automatic retry and fallback support

### 3. Watsonx (IBM Watsonx.ai)

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
| `provider` | string | LLM provider: `"ollama"`, `"litellm"`, or `"watsonx"` |
| `model_id` | string | Model identifier (e.g., `"granite4:latest"`, `"gpt-4o-mini"`, `"claude-3-sonnet"`) |

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

#### Ollama
```json
{
  "provider": "ollama",
  "model_id": "granite4:latest"
}
```

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
{"provider": "litellm", "model_id": "openai/llama3", "provider_config": {"api_base": "http://localhost:11434/v1"}}
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

### Example 1: Basic Classification with Ollama

```json
{
  "id": "classify_node",
  "name": "classify",
  "operator": "document_classifier",
  "config": {
    "provider": "ollama",
    "model_id": "granite4:latest",
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
  "flow": {
    "name": "Document Classification Pipeline",
    "dag": [
      {
        "id": "ingest_node",
        "operator": "ingest_local",
        "config": {
          "input_folder": "./documents",
          "store_binary_content": true
        }
      },
      {
        "id": "extract_node",
        "operator": "extract_operator",
        "config": {
          "doc_column": "content"
        }
      },
      {
        "id": "classify_node",
        "operator": "document_classifier",
        "config": {
          "provider": "ollama",
          "model_id": "granite4:latest",
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
| Local/Privacy | Ollama |
| High Accuracy | LiteLLM (GPT-4, Claude-3-Opus) |
| Enterprise | Watsonx or LiteLLM (Azure/Bedrock) |
| Cost-Effective | Ollama or LiteLLM (GPT-4o-mini) |
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

## Adding New Providers

The hexagonal architecture makes it easy to add new LLM providers:

### Step 1: Create Adapter Class

```python
from core.operators.quality.classification.ports.outbound.classification_service import ClassificationServicePort
from core.operators.quality.classification.adapters.outbound.factories.classification_adapter_factory import register_classification_adapter

@register_classification_adapter
class MyLLMAdapter(ClassificationServicePort):
    ADAPTER_NAME = "myllm"
    ADAPTER_DISPLAY_NAME = "My LLM Provider"
    
    def __init__(self, *, model_id: str | None = None, **kwargs):
        self.model_id = model_id
        # Initialize your LLM client
    
    def classify_document(self, *, request: ClassificationRequest) -> ClassificationResponse:
        # Implement classification logic
        pass
    
    def get_model_info(self) -> ModelInfo:
        # Return model information
        pass
```

### Step 2: Register Adapter

The `@register_classification_adapter` decorator automatically registers your adapter with the factory.

### Step 3: Use in Configuration

```json
{
  "provider": "myllm",
  "model_id": "my-model-v1",
  "provider_config": {
    "api_key": "${MYLLM_API_KEY}",
    "api_base": "${MYLLM_API_BASE}"
  }
}
```

---

## Troubleshooting

### Issue: "Failed to initialize classification adapter"

**Cause**: Missing or invalid provider configuration

**Solution**:
- Verify provider name is correct (`ollama`, `litellm`, `watsonx`)
- Check all required provider_config parameters
- Ensure API keys and endpoints are valid
- For LiteLLM, verify model ID format matches provider (e.g., `gpt-4o-mini`, `claude-3-sonnet-20240229`)

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

### ClassificationServicePort Interface

```python
class ClassificationServicePort(ABC):
    """Port interface for document classification services."""
    
    @abstractmethod
    def classify_document(self, *, request: ClassificationRequest) -> ClassificationResponse:
        """Classify a document.
        
        Args:
            request: Classification request with content and document types
            
        Returns:
            Classification response with type, confidence, and reasoning
        """
        pass
    
    @abstractmethod
    def get_model_info(self) -> ModelInfo:
        """Get information about the classification model.
        
        Returns:
            Model information including name, provider, and capabilities
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
- [Architecture Guide](../ARCHITECTURE.md) - System architecture overview
- [Hexagonal Architecture](https://en.wikipedia.org/wiki/Hexagonal_architecture_(software)) - Pattern explanation

---

## Version History

- **v1.1.0** : LiteLLM integration
  - Replaced OpenAI adapter with LiteLLM adapter
  - Support for 100+ LLM providers (OpenAI, Anthropic, Azure, AWS Bedrock, Google, etc.)
  - Unified interface for all providers
  - Backward compatible configuration
- **v1.0.0** : Initial release with hexagonal architecture
  - Ollama adapter
  - Watsonx adapter
  - Factory-based adapter registration
  - Confidence scoring and reasoning