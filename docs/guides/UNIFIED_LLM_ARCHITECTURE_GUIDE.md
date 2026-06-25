<!-- sonar.exclusions=**/*.md -->
# Complete Adapter Restructuring Guide

## Unified LLM Architecture for All Operators

This document outlines the complete adapter restructuring plan across all operators using a shared, provider-agnostic architecture.

---

# Overview

The goal of this restructuring is to:

* Standardize all LLM integrations
* Eliminate duplicated provider-specific logic
* Reuse common interfaces and factories
* Support multiple providers consistently
* Simplify future provider onboarding

---

# Core Architecture

## Unified Design Pattern (Simplified)

All operators follow the same structure:

```text
Operator
   ↓
Service Layer (business logic)
   ↓ uses directly
Common Port Interface
   ↑ implemented by
Consolidated Provider Adapters (one per provider)
   ↑ created by
Factory
```

**Key Simplification**: No operator-specific adapters. Services use common ports directly.

---

# Key Decisions

## 1. Ollama via LiteLLM

Ollama is accessed through LiteLLM using the OpenAI-compatible API:

```yaml
api_base: http://localhost:11434/v1
model_id: openai/<model_name>
```

### Benefits

* Removes duplicate Ollama implementations
* Reuses LiteLLM infrastructure
* Consistent provider handling
* Easier maintenance

---

## 2. Common Ports

Three shared interfaces are introduced:

| Port                | Purpose                    |
| ------------------- | -------------------------- |
| `LLMInferencePort`  | Chat/generation APIs       |
| `LLMEmbeddingPort`  | Embedding generation       |
| `TextDetectionPort` | Specialized detection APIs |

---

## 3. Unified Factories

Factories create adapters dynamically:

| Factory                       | Responsibility         |
| ----------------------------- | ---------------------- |
| `LLMAdapterFactory`           | Inference + Embeddings |
| `TextDetectionAdapterFactory` | Detection APIs         |

---

# Common Infrastructure (Foundation Layer)

## New Port Interfaces

### 1. LLM Inference Port

**File**

```text
src/docpipe/core/ports/llm_inference_port.py
```

### Purpose

Common interface for:

* chat()
* generate()

### Used By

* Classification
* Entity Extraction
* Summarization
* PII/HAP (LLM mode)

---

### 2. LLM Embedding Port

**File**

```text
src/docpipe/core/ports/llm_embedding_port.py
```

### Purpose

Common interface for:

* generate_embeddings()
* generate_embeddings_batch()
* get_embedding_dimension()

### Used By

* Embeddings Operator

---

### 3. Text Detection Port

**File**

```text
src/docpipe/core/ports/text_detection_port.py
```

### Purpose

Generic interface for:

* PII detection
* HAP detection
* Future detection APIs

### Used By

* WatsonX Detection APIs

---

# Provider Adapters (Consolidated Architecture)

## Overview

Each provider now has a **single consolidated adapter** that implements multiple port interfaces. This eliminates duplication and simplifies maintenance.

---

## WatsonX Adapter (Unified)

**File**

```text
src/docpipe/core/adapters/watsonx/watsonx_adapter.py
```

### Implements Three Ports

```text
LLMInferencePort      (chat, generate)
LLMEmbeddingPort      (generate_embeddings, generate_embeddings_batch, get_embedding_dimension)
TextDetectionPort     (detect, detect_entities, detect_entities_batch)
```

### Key Features

* **Single adapter** for all WatsonX capabilities
* **Model override**: All methods accept optional `model_name` parameter
* **Flexible response format**: `response_format` passed as method parameter, not in `__init__`
* **Specialized detection**: Uses WatsonX detection APIs for PII/HAP

### Usage Example

```python
from docpipe.core.adapters import WatsonXAdapter

# Create adapter
adapter = WatsonXAdapter(
    api_key="<your-watsonx-api-key>",
    container_id="<your-project-id>",
    api_base="https://us-south.ml.cloud.ibm.com",
    model_name="ibm/granite-13b-chat-v2"  # default model
)

# Inference with JSON response
response = adapter.chat(
    messages=[{"role": "user", "content": "Classify this"}],
    response_format={"type": "json_object"}
)

# Embeddings
embeddings = adapter.generate_embeddings(
    model_name="ibm/slate-125m-english-rtrvr",  # override model
    text="Sample text"
)

# Text detection
result = adapter.detect(text="Check for PII")
```

---

## LiteLLM Adapter (Unified)

**File**

```text
src/docpipe/core/adapters/litellm/litellm_adapter.py
```

### Implements Two Ports

```text
LLMInferencePort      (chat, generate)
LLMEmbeddingPort      (generate_embeddings, generate_embeddings_batch, get_embedding_dimension)
```

### Supports 100+ Providers

* **OpenAI**: gpt-4, text-embedding-3-small
* **Anthropic**: claude-3-opus-20240229
* **Ollama**: openai/llama2, openai/nomic-embed-text (via OpenAI-compatible API)
* **HuggingFace**: huggingface/sentence-transformers/all-MiniLM-L6-v2
* **And 90+ more providers**

### Key Features

* **Single adapter** for all LiteLLM capabilities
* **Model override**: All methods accept optional `model_name` parameter
* **Flexible response format**: `response_format` passed as method parameter (not hardcoded)
* **No default JSON format**: Callers explicitly specify when needed

### Usage Example

```python
from docpipe.core.adapters import LiteLLMAdapter

# Ollama inference
adapter = LiteLLMAdapter(
    model_name="openai/llama2",
    api_key="<not-required-for-ollama>",
    api_base="http://localhost:11434/v1"
)

# Inference with explicit JSON format
response = adapter.chat(
    messages=[{"role": "user", "content": "Classify this"}],
    response_format={"type": "json_object"}  # Explicitly passed
)

# Embeddings with model override
embeddings = adapter.generate_embeddings(
    model_name="openai/nomic-embed-text",
    text="Sample text"
)
```

---

# Unified Factory

---

## LLM Adapter Factory (Consolidated)

**File**

```text
src/docpipe/core/adapters/llm_adapter_factory.py
```

### Overview

Single unified factory for creating all types of LLM adapters across all providers.

### Methods

```python
# Create inference adapter
create_inference_adapter(provider, model_id, provider_config)

# Create embedding adapter
create_embedding_adapter(provider, model_id, provider_config)

# Create text detection adapter
create_text_detection_adapter(provider, model_id, provider_config)

# Query supported providers
get_supported_providers(capability="inference")
```

### Supported Providers

| Provider | Inference | Embeddings | Text Detection | Notes |
| -------- | --------- | ---------- | -------------- | ----- |
| WatsonX  | ✅         | ✅          | ✅              | IBM watsonx.ai models (single consolidated adapter) |
| LiteLLM  | ✅         | ✅          | ❌              | 100+ providers including Ollama, HuggingFace, OpenAI (single consolidated adapter) |

### Usage Examples

```python
from docpipe.core.adapters import LLMAdapterFactory

# Create WatsonX inference adapter
adapter = LLMAdapterFactory.create_inference_adapter(
    provider="watsonx",
    model_id="ibm/granite-13b-chat-v2",
    provider_config={
        "api_key": "<your-watsonx-api-key>",
        "api_base": "https://us-south.ml.cloud.ibm.com",
        "container_id": "<your-project-id>",
        "container_kind": "project"
    }
)

# Create LiteLLM embedding adapter (Ollama)
adapter = LLMAdapterFactory.create_embedding_adapter(
    provider="litellm",
    model_id="openai/nomic-embed-text",
    provider_config={
        "api_base": "http://localhost:11434/v1",
        "api_key": "<not-required-for-ollama>"
    }
)

# Create WatsonX text detection adapter
adapter = LLMAdapterFactory.create_text_detection_adapter(
    provider="watsonx",
    model_id="ibm/granite-13b-chat-v2",
    provider_config={
        "api_key": "<your-watsonx-api-key>",
        "api_base": "https://us-south.ml.cloud.ibm.com",
        "container_id": "<your-project-id>",
        "container_kind": "project"
    }
)
```

### LiteLLM Provider Examples

LiteLLM provides unified access to multiple providers via model ID prefixes:

- **Ollama**: Use `openai/model-name` with `api_base: http://localhost:11434/v1`
- **HuggingFace**: Use `huggingface/model-name` with HuggingFace API key
- **OpenAI**: Use `gpt-4`, `text-embedding-3-small`, etc.
- **Anthropic**: Use `claude-3-opus-20240229`, etc.
- **And 90+ more providers**

### Key Changes from Previous Architecture

1. **Single factory file** instead of two separate factories
2. **Returns consolidated adapters** (one per provider, not one per capability)
3. **Unified import**: `from docpipe.core.adapters import LLMAdapterFactory`

---

# Operator Refactoring

---

# 1. Classification Operator

## Current State

### Operator

```text
DocumentClassifierOperator
```

### Current Problem

Each provider has its own dedicated adapter:

* WatsonX adapter
* Ollama adapter
* LiteLLM adapter

This creates:

* duplicated logic
* provider-specific maintenance
* inconsistent behavior

---

## New Architecture (Simplified)

```text
DocumentClassifierOperator
    ↓
ClassificationService
    ↓ uses directly
LLMInferencePort
    ↑ implemented by
WatsonXAdapter (consolidated)
LiteLLMAdapter (consolidated)
```

**Key Change**: No operator-specific adapter layer. Service uses port directly.

---

## New Components

### ClassificationService

**File**

```text
src/docpipe/core/operators/quality/classification/services/classification_service.py
```

### Responsibilities

* Classification business logic (prompt building, response parsing)
* Retry handling
* Validation
* Metrics
* Post-processing

### Dependencies

* Receives `LLMInferencePort` instance (WatsonXAdapter or LiteLLMAdapter)
* Calls `chat()` or `generate()` methods directly
* No intermediate adapter needed

### Example Implementation

```python
class ClassificationService:
    def __init__(self, llm_adapter: LLMInferencePort):
        self.llm = llm_adapter
    
    def classify(self, text: str, categories: list[str]) -> dict:
        # Build classification prompt
        messages = [
            {"role": "system", "content": "You are a document classifier."},
            {"role": "user", "content": f"Classify: {text}\nCategories: {categories}"}
        ]
        
        # Call port method directly
        response = self.llm.chat(
            messages=messages,
            response_format={"type": "json_object"}
        )
        
        # Parse and return
        return json.loads(response)
```

---

## Operator Changes

### Setup in Operator

```python
# Create adapter via factory
adapter = LLMAdapterFactory.create_inference_adapter(
    provider=config["provider"],  # "watsonx" or "litellm"
    model_id=config["model_id"],
    provider_config=config["provider_config"]
)

# Create service with adapter
self.classification_service = ClassificationService(llm_adapter=adapter)

# Use in operator
result = self.classification_service.classify(text, categories)
```

---

## Consolidated Architecture

Operator-specific adapters have been replaced by consolidated provider adapters that implement common ports:

```text
Previous operator-specific files:
- watsonx_adapter.py
- ollama_adapter.py
- litellm_adapter.py

Now replaced by unified provider adapters
```

---

# 2. Entity Extraction Operator

## New Architecture (Simplified)

```text
ExtractOperator
    ↓
EntityExtractionService
    ↓ uses directly
LLMInferencePort
    ↑ implemented by
WatsonXAdapter (consolidated)
LiteLLMAdapter (consolidated)
```

**Key Change**: No operator-specific adapter or port. Service uses LLMInferencePort directly.

---

## New Components

### EntityExtractionService

**File**

```text
src/docpipe/core/operators/extract/services/entity_extraction_service.py
```

### Responsibilities

* Entity extraction business logic (prompt building with schema, response parsing)
* Schema validation
* Entity post-processing
* Error handling

### Dependencies

* Receives `LLMInferencePort` instance (WatsonXAdapter or LiteLLMAdapter)
* Calls `chat()` or `generate()` methods directly
* No intermediate adapter or custom port needed

### Example Implementation

```python
class EntityExtractionService:
    def __init__(self, llm_adapter: LLMInferencePort):
        self.llm = llm_adapter
    
    def extract_entities(self, text: str, schema: dict) -> dict:
        # Build extraction prompt with schema
        messages = [
            {"role": "system", "content": "Extract entities according to schema."},
            {"role": "user", "content": f"Text: {text}\nSchema: {json.dumps(schema)}"}
        ]
        
        # Call port method directly
        response = self.llm.chat(
            messages=messages,
            response_format={"type": "json_object"}
        )
        
        # Parse and validate entities
        entities = json.loads(response)
        return self._validate_against_schema(entities, schema)
```

---

## Setup in Operator

```python
# Create adapter via factory
adapter = LLMAdapterFactory.create_inference_adapter(
    provider=config["provider"],
    model_id=config["model_id"],
    provider_config=config["provider_config"]
)

# Create service with adapter
self.entity_service = EntityExtractionService(llm_adapter=adapter)

# Use in operator
entities = self.entity_service.extract_entities(text, schema)
```

---

## Benefits

* Direct port usage (no intermediate layers)
* Reusable extraction logic in service
* Cleaner operator implementation
* Works with any provider implementing LLMInferencePort

---

# 3. PII/HAP Operator

## Special Case: Dual Architecture (Simplified)

WatsonX uses a dedicated detection API, while other providers use prompt-based LLM detection.

---

## Architecture

```text
PIIAndHAPAnnotator
    ↓
PIIHAPService
    ↓
┌─────────────────────┬─────────────────────┐
│ WatsonX Detection   │ LLM-Based Detection │
└─────────────────────┴─────────────────────┘
        ↓                          ↓
TextDetectionPort             LLMInferencePort
        ↑                          ↑
WatsonXAdapter                LiteLLMAdapter
(consolidated)                (consolidated)
```

**Key Change**: Service uses ports directly. No intermediate operator-specific adapter.

---

## Why Two Paths?

### WatsonX Path

Uses specialized detection API:

```text
/ml/v1/text/detection
```

This is NOT a standard chat API, so it requires `TextDetectionPort`.

### LiteLLM Path

Uses standard LLM inference:

* Prompts with detection instructions
* Chat completions
* JSON structured outputs

---

## New Component

### PIIHAPService

**File**

```text
src/docpipe/core/operators/quality/pii_and_hap/services/pii_hap_service.py
```

### Responsibilities

* Prompt generation for LLM-based detection
* Detection orchestration (dual-path logic)
* JSON parsing and validation
* Result normalization across providers

### Dependencies

* Receives either `TextDetectionPort` (WatsonX) or `LLMInferencePort` (LiteLLM)
* Calls port methods directly based on provider
* No intermediate adapter needed

### Example Implementation

```python
class PIIHAPService:
    def __init__(self, adapter: TextDetectionPort | LLMInferencePort, provider: str):
        self.adapter = adapter
        self.provider = provider
    
    def detect_pii_hap(self, text: str) -> dict:
        if self.provider == "watsonx":
            # Use specialized detection API
            return self.adapter.detect(
                text=text,
                prompt=self._get_detection_prompt()
            )
        else:
            # Use LLM-based detection
            messages = self._build_detection_messages(text)
            response = self.adapter.chat(
                messages=messages,
                response_format={"type": "json_object"}
            )
            return self._parse_llm_response(response)
```

---

## Setup in Operator

```python
# WatsonX path
if provider == "watsonx":
    adapter = LLMAdapterFactory.create_text_detection_adapter(
        provider="watsonx",
        model_id=config["model_id"],
        provider_config=config["provider_config"]
    )
else:
    # LiteLLM path
    adapter = LLMAdapterFactory.create_inference_adapter(
        provider="litellm",
        model_id=config["model_id"],
        provider_config=config["provider_config"]
    )

# Create service with adapter
self.pii_hap_service = PIIHAPService(adapter=adapter, provider=provider)

# Use in operator
result = self.pii_hap_service.detect_pii_hap(text)
```

---

# 4. Embeddings Operator

## New Architecture (Simplified)

```text
EmbeddingsOperator
    ↓ uses directly
LLMEmbeddingPort
    ↑ implemented by
WatsonXAdapter (consolidated)
LiteLLMAdapter (consolidated - supports HuggingFace, Ollama, OpenAI, etc.)
```

**Key Change**: Operator uses port directly. No service layer needed for simple embedding operations.

---

## Setup in Operator

```python
# Create adapter via factory
adapter = LLMAdapterFactory.create_embedding_adapter(
    provider=config["provider"],
    model_id=config["model_id"],
    provider_config=config["provider_config"]
)

# Use directly in operator
embeddings = adapter.generate_embeddings_batch(texts=texts)
dimension = adapter.get_embedding_dimension()
```

---

## Benefits

* Direct port usage (simplest case)
* Shared embedding interface
* Batch support
* Consistent dimensions API
* Easier provider swapping

---

# 5. Chunker / Summarization

## Current Problem

Summarization is:

* Ollama-only
* Tightly coupled
* Not reusable

---

## New Architecture (Simplified)

```text
ChunkerOperator
    ↓
SummarizationService
    ↓ uses directly
LLMInferencePort
    ↑ implemented by
WatsonXAdapter (consolidated)
LiteLLMAdapter (consolidated)
```

**Key Change**: Service uses LLMInferencePort directly. No custom port or intermediate adapter needed.

---

## New Component

### SummarizationService

**File**

```text
src/docpipe/core/operators/functional/chunker/services/summarization_service.py
```

### Responsibilities

* Prompt generation for summarization
* Chunk summarization logic
* Sliding window handling
* Summary parsing and validation

### Dependencies

* Receives `LLMInferencePort` instance (WatsonXAdapter or LiteLLMAdapter)
* Calls `chat()` or `generate()` methods directly
* No custom port or intermediate adapter needed

### Example Implementation

```python
class SummarizationService:
    def __init__(self, llm_adapter: LLMInferencePort):
        self.llm = llm_adapter
    
    def generate_summary(self, text: str, max_length: int = 100) -> str:
        # Build summarization prompt
        messages = [
            {"role": "system", "content": "You are a text summarizer."},
            {"role": "user", "content": f"Summarize in {max_length} words: {text}"}
        ]
        
        # Call port method directly
        return self.llm.chat(messages=messages)
    
    def generate_summaries_batch(self, texts: list[str]) -> list[str]:
        return [self.generate_summary(text) for text in texts]
```

---

## Setup in Operator

```python
# Create adapter via factory
adapter = LLMAdapterFactory.create_inference_adapter(
    provider=config["provider"],
    model_id=config["model_id"],
    provider_config=config["provider_config"]
)

# Create service with adapter
self.summarization_service = SummarizationService(llm_adapter=adapter)

# Use in operator
summary = self.summarization_service.generate_summary(text)
```

---

## Provider Support

| Provider           | Supported |
| ------------------ | --------- |
| WatsonX            | ✅         |
| LiteLLM            | ✅         |
| Ollama via LiteLLM | ✅         |

---

# Provider Support Matrix

| Provider | Inference | Embeddings | Text Detection | Notes |
| -------- | --------- | ---------- | -------------- | ----- |
| WatsonX  | ✅         | ✅          | ✅              | IBM watsonx.ai specialized APIs |
| LiteLLM  | ✅         | ✅          | ❌              | 100+ providers (Ollama, HuggingFace, OpenAI, etc.) |

---

# Benefits of the New Architecture

## Reduced Duplication

One adapter per domain instead of:

* WatsonX adapter
* Ollama adapter
* LiteLLM adapter

for every operator.

---

## Easier Provider Expansion

Adding a new provider now only requires:

1. Implement common port
2. Register in factory

No operator changes needed.

---

## Better Separation of Concerns

| Layer    | Responsibility       |
| -------- | -------------------- |
| Operator | Workflow             |
| Service  | Business logic       |
| Adapter  | Provider translation |
| Port     | Interface contract   |

---

## Easier Testing

* Mock common ports
* Test services independently
* Reuse test suites across providers

---


# Success Criteria

* ✅ Unified provider architecture
* ✅ Shared reusable interfaces
* ✅ No provider-specific operator logic
* ✅ Ollama migrated to LiteLLM
* ✅ Backward compatibility preserved
* ✅ Existing configs continue working
* ✅ Easier future provider onboarding