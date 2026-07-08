# PII and HAP Detection - Common Infrastructure Architecture

This module implements PII (Personally Identifiable Information) and HAP (Hate, Abuse, and Profanity) detection using the common infrastructure architecture with shared ports and adapters.

## Architecture Overview

```
pii_and_hap/
├── domain/              # Core business logic (provider-agnostic)
│   └── models.py       # DetectionResult, PIIHAPDetectionResponse
├── services/           # Business logic layer
│   └── pii_hap_service.py  # PIIHAPService (wraps common ports)
└── adapters/           # Provider implementations
    └── outbound/       # Adapters (removed)
```

## New Architecture (Phase 2)

The PII/HAP operator now uses the **common infrastructure** located in `src/docpipe/core/adapters/`:

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
┌─────────┐  ┌─────────┐      ┌─────────┐ ┌─────────┐
│LiteLLM  │  │WatsonX  │      │WatsonX  │ │  (More  │
│Inference│  │Inference│      │  Text   │ │ Coming) │
│Adapter  │  │Adapter  │      │Detection│ │         │
└─────────┘  └─────────┘      └─────────┘ └─────────┘
```

### Key Changes from Old Architecture

**Before (Operator-Specific Adapters):**
- Each operator had its own adapter implementations
- Duplicate code across operators
- Hard to maintain consistency

**After (Common Infrastructure):**
- Shared port interfaces in `src/docpipe/core/adapters/ports/`
- Shared adapter implementations in `src/docpipe/core/adapters/{provider}/`
- Service layer wraps common ports for operator-specific logic
- Single source of truth for each provider

## Supported Providers

### 1. LiteLLM (Default - Recommended)
- **Use Case**: Access Ollama and 100+ LLM providers through unified interface
- **Adapter**: `LiteLLMInferenceAdapter` (common infrastructure)
- **Configuration**:
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

**Accessing Ollama via LiteLLM:**
```json
{
  "provider": "litellm",
  "model_name": "openai/granite3.1-dense:8b",
  "provider_config": {
    "api_key": "${LITELLM_API_KEY}",
    "api_base": "http://localhost:11434/v1"
  }
}
```

**Accessing OpenAI:**
```json
{
  "provider": "litellm",
  "model_name": "gpt-4",
  "provider_config": {
    "api_key": "${OPENAI_API_KEY}"
  }
}
```

### 2. WatsonX.ai
- **Use Case**: Enterprise deployments with IBM WatsonX
- **Adapter**: `WatsonXTextDetectionAdapter` (common infrastructure)
- **Configuration**:
  ```json
  {
    "provider": "watsonx",
    "provider_config": {
      "api_key": "${WATSONX_API_KEY}",
      "api_base": "https://us-south.ml.cloud.ibm.com",
      "container_kind": "project",
      "container_id": "your-project-id"
    }
  }
  ```

**Note:** Ollama is NOT a direct provider. Use LiteLLM with `api_base` to access Ollama.

## Detection Paths

PIIHAPService implements two detection paths:

### 1. WatsonX Path (Specialized API)
- Uses `TextDetectionPort` → `WatsonXTextDetectionAdapter`
- Native `/ml/v1/text/detection` API endpoint
- Optimized for PII/HAP detection
- IAM token caching and automatic refresh

### 2. LiteLLM Path (Prompt-Based)
- Uses `LLMInferencePort` → `LiteLLMInferenceAdapter`
- Prompt-based detection using chat completion
- Supports 100+ LLM providers
- Flexible model selection

## Usage Example

### In Flow Configuration

```json
{
  "operator_type": "PIIAndHAPAnnotator",
  "operator_params": {
    "provider": "litellm",
    "model_name": "openai/granite4",
    "provider_config": {
      "api_key": "${LITELLM_API_KEY}",
      "api_base": "http://localhost:11434/v1"
    },
    "pii_threshold": 0.5,
    "hap_threshold": 0.8,
    "redaction": true,
    "expected_redactions": ["pii", "hap"]
  }
}
```

### Programmatic Usage

```python
from docpipe.core.operators.quality.pii_and_hap.services.pii_hap_service import PIIHAPService

# Create service (uses common infrastructure)
service = PIIHAPService(
    provider="litellm",
    model_id="openai/granite4",
    provider_config={
        "api_key": "${LITELLM_API_KEY}",
        "api_base": "http://localhost:11434/v1"
    }
)

# Detect PII/HAP
payload = {
    "input": "My email is john@example.com",
    "detectors": {
        "pii": {"threshold": 0.5},
        "hap": {"threshold": 0.8}
    }
}
response = service.detect_pii_hap(payload=payload)
print(f"Detections: {response.detections}")
```

## Migration from Old Architecture

### BREAKING CHANGE: Ollama Provider Removed

**Important:** Direct Ollama provider support has been removed. Ollama is now accessed through LiteLLM with an OpenAI-compatible endpoint.

### Old Configuration (No Longer Supported)
```json
{
  "provider": "ollama",
  "model_name": "granite4"
}
```

### New Configuration (Required)
```json
{
  "provider": "litellm",
  "model_name": "openai/granite4",
  "provider_config": {
    "api_key": "${OLLAMA_API_KEY}",
    "api_base": "http://localhost:11434/v1"
  }
}
```

### Migration Steps for Ollama Users

1. **Change provider** from `"ollama"` to `"litellm"`
2. **Update model_name** to use OpenAI-compatible format: `"openai/your-model-name"`
3. **Add provider_config** with:
   - `api_base`: `"http://localhost:11434/v1"` (Ollama's OpenAI-compatible endpoint)
   - `api_key`: Any non-empty string (e.g., `"ollama"`)

### Code Migration Example

**Old Code:**
```text
from docpipe.core.operators.quality.pii_and_hap.adapters.outbound.ollama_adapter import OllamaAdapter

adapter = OllamaAdapter(model_name="granite4")
response = adapter.detect_pii_hap(payload)
```

**New Code:**
```text
from docpipe.core.operators.quality.pii_and_hap.services.pii_hap_service import PIIHAPService

service = PIIHAPService(
    provider="litellm",
    model_id="openai/granite4",
    provider_config={
        "api_key": "${OLLAMA_API_KEY}",
        "api_base": "http://localhost:11434/v1"
    }
)
response = service.detect_pii_hap(text_payload=text_payload)
```

### Why This Change?

- **Eliminates code duplication**: Single LiteLLM adapter instead of separate Ollama adapter
- **Broader compatibility**: LiteLLM provides access to 100+ LLM providers
- **Consistent interface**: Same configuration pattern across all providers
- **Better maintained**: LiteLLM handles provider-specific quirks

## Testing

```bash
# From project root
source .venv/bin/activate

# Run all PII/HAP tests
pytest tests/unit/operators/pii_and_hap/ -v

# Test specific components
pytest tests/unit/operators/pii_and_hap/test_pii_hap_service.py -v  # Service layer
pytest tests/unit/core/adapters/watsonx/ -v  # WatsonX adapters
pytest tests/unit/core/adapters/litellm/ -v  # LiteLLM adapters
```

## Architecture Benefits

### 1. Code Reuse
- Single adapter implementation per provider
- Shared across all operators (PII/HAP, Classification, Entity Extraction, Embeddings)
- Reduced maintenance burden

### 2. Consistency
- Uniform error handling across operators
- Consistent configuration patterns
- Standardized testing approach

### 3. Extensibility
- Add new providers once, use everywhere
- Service layer isolates operator-specific logic
- Easy to add new detection methods

### 4. Testability
- Mock at service layer for operator tests
- Mock at adapter layer for service tests
- Mock at HTTP layer for adapter tests

## Common Infrastructure Location

All shared components are in `src/docpipe/core/adapters/`:

```
src/docpipe/core/adapters/
├── ports/                    # Common port interfaces
│   ├── llm_inference.py     # LLMInferencePort
│   ├── llm_embedding.py     # LLMEmbeddingPort
│   └── text_detection.py    # TextDetectionPort
├── watsonx/                  # WatsonX provider
│   ├── inference_adapter.py
│   └── text_detection_adapter.py
├── litellm/                  # LiteLLM provider
│   ├── inference_adapter.py
│   └── embedding_adapter.py
└── factories/                # Adapter factories
    ├── llm_factory.py
    └── text_detection_factory.py
```

## References

- [PII and HAP Configuration Guide](pii_and_hap_config.md)
- [Operator Reference](../../reference/OPERATORS.md#piiandhapannotator)
- [Hexagonal Architecture](https://alistair.cockburn.us/hexagonal-architecture/)
- [Ports and Adapters Pattern](https://herbertograca.com/2017/09/14/ports-adapters-architecture/)
