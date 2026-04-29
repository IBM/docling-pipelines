# PII and HAP Detection - Hexagonal Architecture

This module implements PII (Personally Identifiable Information) and HAP (Hate, Abuse, and Profanity) detection using hexagonal architecture (ports and adapters pattern).

## Architecture Overview

```
pii_and_hap/
├── domain/              # Core business logic (provider-agnostic)
│   └── models.py       # DetectionResult, PIIHAPDetectionResponse
├── ports/              # Interface contracts
│   └── outbound/
│       └── pii_hap_service.py  # PIIHAPServicePort (abstract interface)
├── adapters/           # Provider implementations
│   └── outbound/
│       ├── ollama_adapter.py    # Ollama LLM implementation
│       ├── watsonx_adapter.py   # IBM WatsonX.ai implementation
│       ├── litellm_adapter.py   # LiteLLM multi-provider implementation
│       └── factories/
│           └── pii_hap_adapter_factory.py  # Adapter registry & factory
```

## Supported Providers

### 1. Ollama (Default)
- **Adapter Name**: `ollama`
- **Description**: Local LLM models via Ollama
- **Requirements**: Ollama server running on `http://localhost:11434`
- **Configuration**:
  ```json
  {
    "provider": "ollama",
    "model_name": "llama3.2:3b"
  }
  ```

### 2. WatsonX.ai
- **Adapter Name**: `watsonx`
- **Description**: IBM WatsonX.ai detection API with IAM authentication
- **Requirements**:
  - IBM Cloud API key for IAM token generation
  - WatsonX.ai service instance
  - Container ID (project or space or catalog ID)
  - Container kind (`project` or `space` or `catalog`)
- **Configuration**:
  ```json
  {
    "provider": "watsonx",
    "provider_config": {
      "api_key": "your-ibm-cloud-api-key", // pragma: allowlist secret
      "url": "https://us-south.ml.cloud.ibm.com",
      "container_kind": "project",
      "container_id": "your-project-or-space-or-catalog-id"
    }
  }
  ```
- **Features**:
  - Uses WatsonX.ai native `/ml/v1/text/detection` API endpoint
  - IAM token caching (55-minute cache with 5-minute buffer)
  - Automatic token refresh on expiry
  - Retry logic with exponential backoff
  - Support for multiple WatsonX regions

### 3. LiteLLM (Multi-Provider)
- **Adapter Name**: `litellm`
- **Description**: Unified interface to 100+ LLM providers (OpenAI, Anthropic, Azure, Cohere, Bedrock, etc.)
- **Requirements**:
  - `litellm` package installed
  - Provider-specific API keys
- **Configuration**:
  ```json
  {
    "provider": "litellm",
    "model_name": "gpt-4",
    "provider_config": {
      "api_key": "your-api-key" // pragma: allowlist secret
    }
  }
  ```
- **Supported Providers** (100+):
  - **OpenAI**: `gpt-4`, `gpt-3.5-turbo`, `gpt-4-turbo`
  - **Anthropic**: `claude-3-opus-20240229`, `claude-3-sonnet-20240229`
  - **Azure OpenAI**: `azure/your-deployment-name`
  - **Cohere**: `command`, `command-light`, `command-nightly`
  - **AWS Bedrock**: `bedrock/anthropic.claude-v2`, `bedrock/anthropic.claude-instant-v1`
  - **Google Vertex AI**: `vertex_ai/gemini-pro`, `vertex_ai/chat-bison`
  - **Hugging Face**: `huggingface/model-name`
  - And 100+ more providers

## Usage Example

### In Flow Configuration

```json
{
  "operator_type": "PIIAndHAPAnnotator",
  "operator_params": {
    "provider": "ollama",
    "model_name": "granite4",
    "pii_threshold": 0.5,
    "hap_threshold": 0.8,
    "redaction": true,
    "expected_redactions": ["pii", "hap"]
  }
}
```

### Programmatic Usage

```python
from core.operators.quality.pii_and_hap.adapters.outbound.factories.pii_hap_adapter_factory import PIIHAPAdapterFactory

# List available adapters
adapters = PIIHAPAdapterFactory.list_adapters()
print(f"Available adapters: {adapters}")

# Create Ollama adapter
ollama_adapter = PIIHAPAdapterFactory.create(
    adapter_name="ollama",
    model_name="granite4"
)

# Detect PII/HAP
payload = {
    "input": "My email is john@example.com",
    "detectors": {
        "pii": {"threshold": 0.5},
        "hap": {"threshold": 0.8}
    }
}
response = ollama_adapter.detect_pii_hap(payload)
print(f"Detections: {response.detections}")
```

## Adding New Providers

To add a new detection provider:

1. **Create Adapter Class** in `adapters/outbound/`:
   ```python
   from core.operators.quality.pii_and_hap.ports.outbound.pii_hap_service import PIIHAPServicePort
   from core.operators.quality.pii_and_hap.adapters.outbound.factories.pii_hap_adapter_factory import register_pii_hap_adapter
   
   @register_pii_hap_adapter
   class MyProviderAdapter(PIIHAPServicePort):
       ADAPTER_NAME = "myprovider"
       ADAPTER_DISPLAY_NAME = "My Provider"
       
       def __init__(self, **config):
           # Initialize provider client
           pass
       
       def detect_pii_hap(self, payload):
           # Implement detection logic
           pass
   ```

2. **Import in `__init__.py`**:
   ```python
   from .myprovider_adapter import MyProviderAdapter  # noqa: F401
   ```

3. **Use in Configuration**:
   ```json
   {
     "provider": "myprovider"
   }
   ```

### Configuration Migration

**Ollama:**
```json
{
  "provider": "ollama",
  "model_name": "llama3.2:3b"
}
```

**OpenAI:**
```json
{
  "provider": "openai",
  "model_name": "gpt-4",
  "provider_config": {
    "base_url": "http://localhost:8000/v1",
    "api_key": "your-key" // pragma: allowlist secret
  }
}
```

**WatsonX:**
```json
{
  "provider": "watsonx",
  "provider_config": {
    "api_key": "your-ibm-cloud-api-key", // pragma: allowlist secret
    "url": "https://us-south.ml.cloud.ibm.com",
    "container_kind": "project",
    "container_id": "your-project-or-space-or-catalog-id"
  }
}
```

## Architecture Diagram

```
┌─────────────────────────────────────┐
│   PIIAndHAPAnnotator (Operator)    │
│                                     │
│  - Uses PIIHAPServicePort interface│
│  - Provider-agnostic business logic│
└──────────────┬──────────────────────┘
               │ depends on
               ▼
┌─────────────────────────────────────┐
│     PIIHAPServicePort (Port)        │
│                                     │
│  - detect_pii_hap(payload)         │
│  - cleanup()                        │
└──────────────┬──────────────────────┘
               │ implemented by
               ▼
┌─────────────────────────────────────┐
│         Adapters (Outbound)         │
│                                     │
│  ┌─────────────────────────────┐   │
│  │   OllamaAdapter             │   │
│  │   - Uses OllamaClient       │   │
│  └─────────────────────────────┘   │
│                                     │
│  ┌─────────────────────────────┐   │
│  │   WatsonXAdapter            │   │
│  │   - Uses WatsonX SDK        │   │
│  │   - IAM token caching       │   │
│  └─────────────────────────────┘   │
│                                     │
│  ┌─────────────────────────────┐   │
│  │   OpenAIAdapter             │   │
│  │   - OpenAI-compatible APIs  │   │
│  │   - vLLM, LocalAI, etc.     │   │
│  └─────────────────────────────┘   │
└─────────────────────────────────────┘
```

## Testing

```bash
# From project root
source .venv/bin/activate

# Run all PII/HAP tests
uv run pytest tests/unit/operators/quality/ -v -k pii_hap

# Test specific adapter
uv run pytest tests/unit/operators/quality/ -v -k "pii_hap and ollama"
uv run pytest tests/unit/operators/quality/ -v -k "pii_hap and watsonx"
uv run pytest tests/unit/operators/quality/ -v -k "pii_hap and openai"
```

## Integration Testing

Integration tests require actual service availability:

```bash
# From project root
# Integration tests (requires Ollama running)
source .venv/bin/activate
uv run pytest tests/unit/operators/pii_and_hap/test_pii_and_hap_integration.py -v

# Tests automatically skip if Ollama is not available
# Start Ollama before running: ollama serve
```

**Note**: Integration tests use `validate_model=False` to skip model validation checks and test actual detection logic.

## Example Flows

Example flow configurations are available in `tests/sample_test_flows/quality_and_enrichment/`:

- **Ollama**: `flow_pii_hap_example.json` - Local LLM detection
- **WatsonX**: `flow_pii_hap_watsonx.json` - IBM WatsonX.ai detection
- **OpenAI**: `flow_pii_hap_openai.json` - OpenAI-compatible API detection

Each flow includes a corresponding README with setup instructions.

## Recent Improvements

### Hexagonal Architecture Migration (2026-04)
- Migrated from monolithic DPK implementation to hexagonal architecture
- Added adapter pattern for provider extensibility
- Implemented three adapters: Ollama, WatsonX, OpenAI
- Maintained full backward compatibility with existing flows
- Added shared IBM IAM authentication utility for WatsonX integration

### Key Features
- **Provider Flexibility**: Easy to add new detection providers
- **IAM Token Caching**: WatsonX adapter caches tokens for 55 minutes
- **Retry Logic**: Automatic retry with exponential backoff for API failures
- **Type Safety**: Full type annotations and mypy compliance
- **Code Quality**: Ruff-compliant formatting and import organization

## References

- [Hexagonal Architecture](https://alistair.cockburn.us/hexagonal-architecture/)
- [Ports and Adapters Pattern](https://herbertograca.com/2017/09/14/ports-adapters-architecture/)
- Language Detection Operator (similar hexagonal implementation)
- Ingest Operator (similar hexagonal implementation)
- Embeddings Operator (similar hexagonal implementation)
