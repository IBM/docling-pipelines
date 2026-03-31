# SPINE Operators Integration Report for DataSift

**Document Version:** 1.1
**Date:** March 3, 2026
**Author:** DataSift Technical Documentation Team

---

## Executive Summary

This report provides a comprehensive analysis of integrating SPINE (Structured Processing and Intelligent Normalization Engine) operators into the DataSift-opensource framework. SPINE offers five specialized operators that complement DataSift's existing capabilities, with particular emphasis on AI-powered schema discovery and data transformation.

### Key Findings

- **High-Value Opportunity**: SPINE's `schema_discoverer` fills a critical gap in DataSift's automated schema discovery capabilities
- **Strong Architectural Alignment**: Both frameworks use PyArrow tables as the primary data structure
- **Integration Complexity**: Ranges from EASY (file ingestion) to HARD (schema mapping concepts)
- **AI Integration Required**: Three operators require IBM watsonx.ai/IX integration
- **Recommended Approach**: Phased integration starting with highest-value, lowest-complexity operators

### Strategic Recommendations

1. **Priority 1**: Integrate `schema_discoverer` (HIGH VALUE, MEDIUM complexity)
2. **Priority 2**: Integrate `folder2parquet` as enhanced ingestion (EASY)
3. **Priority 3**: Evaluate `data_extractor` vs. existing Ollama-based extraction
4. **Priority 4**: Research `smt_builder` and `smt_executor` for advanced transformation needs

---

## Table of Contents

1. [SPINE Operators Overview](#spine-operators-overview)
2. [Watsonx.ai/IX Integration Deep Dive](#watsonxaiix-integration-deep-dive)
3. [Integration Analysis](#integration-analysis)
4. [Architectural Considerations](#architectural-considerations)
5. [Implementation Roadmap](#implementation-roadmap)
6. [Code Integration Guidelines](#code-integration-guidelines)
7. [Testing Strategy](#testing-strategy)
8. [Risk Assessment](#risk-assessment)
9. [Conclusion](#conclusion)

---

## SPINE Operators Overview

SPINE provides five specialized operators for data processing and transformation:

| Operator | Purpose | Primary Technology |
|----------|---------|-------------------|
| `folder2parquet` | File ingestion to PyArrow tables | PyArrow, file I/O |
| `schema_discoverer` | AI-powered schema discovery | IBM watsonx.ai/IX |
| `data_extractor` | AI-powered KVP extraction | IBM watsonx.ai/IX |
| `smt_builder` | Schema mapping generation | IBM watsonx.ai/IX |
| `smt_executor` | Data transformation & CSV export | PyArrow, pandas |


## Watsonx.ai/IX Integration Deep Dive

This section provides comprehensive technical details on how SPINE operators integrate with IBM watsonx.ai through the IX (Intelligence eXtraction) library, including architecture, configuration, data flow, and implementation requirements for DataSift integration.

---

### IX Library Overview

**IX (Intelligence eXtraction)** is an open-source library developed by the SPINE-Docs team that provides AI-powered document processing capabilities through a unified API interface.

**Repository:** [`https://github.com/SPINE-Docs/ix`](https://github.com/SPINE-Docs/ix)

**Core Purpose:**
- Abstracts AI model interactions for document processing tasks
- Provides consistent API interface across different AI backends
- Supports OpenAI-compatible endpoints (including IBM watsonx.ai)
- Enables document classification, schema discovery, and data extraction

**Key Characteristics:**
- **Model Agnostic**: Works with any OpenAI-compatible API endpoint
- **Configurable**: Supports environment variable substitution for credentials
- **Production Ready**: Includes retry logic, error handling, and logging
- **Lightweight**: Minimal dependencies, focused on document intelligence tasks

---

### IX Services Architecture

IX provides three specialized services that work together to process documents intelligently:

#### 1. Classifier Service

**Purpose:** Identifies document types and categories to route processing appropriately.

**Functionality:**
- Analyzes document content to determine document type
- Returns classification with confidence scores
- Enables conditional processing based on document type
- Supports custom classification taxonomies

**Use Cases:**
- Routing invoices vs. receipts vs. contracts to different processing pipelines
- Identifying language or format before extraction
- Quality filtering based on document characteristics

**API Endpoint Pattern:**
```
{api_base}/classifier/classify
```

#### 2. Discoverer Service

**Purpose:** Automatically generates schemas from document content without predefined templates.

**Functionality:**
- Analyzes document structure and content
- Infers field names, types, and relationships
- Generates JSON schema definitions
- Provides confidence scores for discovered fields
- Supports iterative schema refinement

**Use Cases:**
- Rapid onboarding of new document types
- Schema evolution detection
- Automated data catalog generation
- Exploratory data analysis

**API Endpoint Pattern:**
```
{api_base}/discoverer/discover
```

#### 3. Extractor Service

**Purpose:** Extracts structured data from documents using provided or discovered schemas.

**Functionality:**
- Schema-guided extraction of key-value pairs
- Entity recognition and relationship extraction
- Supports nested and complex data structures
- Returns extracted data with confidence scores

**Use Cases:**
- Invoice data extraction (line items, totals, dates)
- Form processing (structured field extraction)
- Entity extraction from unstructured text
- Table data extraction

**API Endpoint Pattern:**
```
{api_base}/extractor/extract
```

---

### Exact API Endpoints and HTTP Calls

**CRITICAL FINDING:** All IX services use the OpenAI Chat Completions API specification. This is a fundamental architectural decision that enables IX to work seamlessly with watsonx.ai, OpenAI, and any OpenAI-compatible API endpoint.

#### Single Endpoint Architecture

All three IX services (Classifier, Discoverer, Extractor) use the **same HTTP endpoint** with different system prompts and user messages:

```
POST {base_url}/v1/chat/completions
```

**Key Insight:** IX is an abstraction layer over OpenAI-compatible APIs. The service differentiation happens through prompt engineering, not different API endpoints.

#### Base URL Configuration

The `base_url` parameter determines which AI service is used:

| Service | Base URL Example | Notes |
|---------|------------------|-------|
| **watsonx.ai** | `https://us-south.ml.cloud.ibm.com/ml` | IBM Cloud watsonx.ai endpoint |
| **OpenAI** | `https://api.openai.com` | Official OpenAI API |
| **Local Models** | `http://localhost:11434` | Ollama or other local inference servers |
| **Azure OpenAI** | `https://{resource}.openai.azure.com` | Azure-hosted OpenAI models |

**Default Model:** `mistralai/Mistral-Small-3.1-24B-Instruct-2503` (watsonx.ai model ID)

#### Authentication Mechanism

All IX services use API key authentication passed through the OpenAI Python SDK:

```python
from openai import OpenAI

client = OpenAI(
    api_key="your-api-key-here",
    base_url="https://us-south.ml.cloud.ibm.com/ml/v1"
)
```

**HTTP Header Format:**
```
Authorization: Bearer {api_key}
Content-Type: application/json
```

Optional custom headers can be added for watsonx.ai-specific requirements (e.g., project IDs, space IDs).

---

#### Complete HTTP Request Structure

##### 1. Classifier Service Request

**Endpoint:** `POST {base_url}/v1/chat/completions`

**Request Body:**
```json
{
  "model": "mistralai/Mistral-Small-3.1-24B-Instruct-2503",
  "messages": [
    {
      "role": "system",
      "content": "You are a document classification expert. Analyze the provided document and classify it into one of the following categories: [invoice, receipt, contract, form, letter, report, other]. Return only the category name and a confidence score between 0 and 1."
    },
    {
      "role": "user",
      "content": "Classify this document:\n\n[DOCUMENT CONTENT HERE]\n\nProvide your response in JSON format: {\"category\": \"...\", \"confidence\": 0.XX}"
    }
  ],
  "temperature": 0.1,
  "max_tokens": 500,
  "response_format": { "type": "json_object" }
}
```

**Key Parameters:**
- `temperature`: Low (0.1) for consistent classification
- `max_tokens`: Limited to 500 for concise responses
- `response_format`: Enforces JSON output for structured parsing

**Example Response:**
```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "created": 1677652288,
  "model": "mistralai/Mistral-Small-3.1-24B-Instruct-2503",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "{\"category\": \"invoice\", \"confidence\": 0.95}"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 245,
    "completion_tokens": 12,
    "total_tokens": 257
  }
}
```

---

##### 2. Discoverer Service Request

**Endpoint:** `POST {base_url}/v1/chat/completions`

**Request Body:**
```json
{
  "model": "mistralai/Mistral-Small-3.1-24B-Instruct-2503",
  "messages": [
    {
      "role": "system",
      "content": "You are a schema discovery expert. Analyze the provided document and generate a JSON schema that describes its structure. Identify all key fields, their data types, and relationships. Include confidence scores for each discovered field."
    },
    {
      "role": "user",
      "content": "Discover the schema for this document:\n\n[DOCUMENT CONTENT HERE]\n\nProvide a JSON schema with the following structure:\n{\n  \"fields\": [\n    {\"name\": \"field_name\", \"type\": \"string|number|date|array|object\", \"confidence\": 0.XX, \"description\": \"...\"}\n  ],\n  \"relationships\": [...]\n}"
    }
  ],
  "temperature": 0.2,
  "max_tokens": 2000,
  "response_format": { "type": "json_object" }
}
```

**Key Parameters:**
- `temperature`: Slightly higher (0.2) for creative schema inference
- `max_tokens`: Higher limit (2000) for complex schemas
- `response_format`: Enforces JSON schema output

**Example Response:**
```json
{
  "id": "chatcmpl-def456",
  "object": "chat.completion",
  "created": 1677652300,
  "model": "mistralai/Mistral-Small-3.1-24B-Instruct-2503",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "{\"fields\": [{\"name\": \"invoice_number\", \"type\": \"string\", \"confidence\": 0.98, \"description\": \"Unique invoice identifier\"}, {\"name\": \"invoice_date\", \"type\": \"date\", \"confidence\": 0.95, \"description\": \"Date of invoice issuance\"}, {\"name\": \"total_amount\", \"type\": \"number\", \"confidence\": 0.97, \"description\": \"Total invoice amount\"}], \"relationships\": []}"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 512,
    "completion_tokens": 156,
    "total_tokens": 668
  }
}
```

---

##### 3. Extractor Service Request

**Endpoint:** `POST {base_url}/v1/chat/completions`

**Request Body:**
```json
{
  "model": "mistralai/Mistral-Small-3.1-24B-Instruct-2503",
  "messages": [
    {
      "role": "system",
      "content": "You are a data extraction expert. Extract structured data from the provided document according to the given schema. Return extracted values with confidence scores."
    },
    {
      "role": "user",
      "content": "Extract data from this document using the provided schema:\n\nSCHEMA:\n{\n  \"fields\": [\n    {\"name\": \"invoice_number\", \"type\": \"string\"},\n    {\"name\": \"invoice_date\", \"type\": \"date\"},\n    {\"name\": \"total_amount\", \"type\": \"number\"}\n  ]\n}\n\nDOCUMENT:\n[DOCUMENT CONTENT HERE]\n\nProvide extracted data in JSON format:\n{\n  \"extracted_data\": {\n    \"field_name\": {\"value\": \"...\", \"confidence\": 0.XX}\n  }\n}"
    }
  ],
  "temperature": 0.1,
  "max_tokens": 1500,
  "response_format": { "type": "json_object" }
}
```

**Key Parameters:**
- `temperature`: Very low (0.1) for accurate extraction
- `max_tokens`: Moderate limit (1500) for extracted data
- `response_format`: Enforces JSON output with confidence scores

**Example Response:**
```json
{
  "id": "chatcmpl-ghi789",
  "object": "chat.completion",
  "created": 1677652315,
  "model": "mistralai/Mistral-Small-3.1-24B-Instruct-2503",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "{\"extracted_data\": {\"invoice_number\": {\"value\": \"INV-2024-001\", \"confidence\": 0.99}, \"invoice_date\": {\"value\": \"2024-01-15\", \"confidence\": 0.96}, \"total_amount\": {\"value\": 1250.50, \"confidence\": 0.98}}}"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 423,
    "completion_tokens": 89,
    "total_tokens": 512
  }
}
```

---

#### Debugging and Inspecting API Calls

To debug or inspect the actual API calls made by IX services:

**1. Enable OpenAI SDK Logging:**
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

**2. Use HTTP Proxy for Request Inspection:**
```python
import os
os.environ['HTTP_PROXY'] = 'http://localhost:8080'
os.environ['HTTPS_PROXY'] = 'http://localhost:8080'
```

**3. Review IX Source Code:**
The exact prompt templates and API call logic are available in the IX library source code:
- **Repository:** https://github.com/SPINE-Docs/ix
- **Classifier Prompts:** `ix/classifier/prompts.py`
- **Discoverer Prompts:** `ix/discoverer/prompts.py`
- **Extractor Prompts:** `ix/extractor/prompts.py`
- **API Client:** `ix/client/openai_client.py`

**4. Monitor Network Traffic:**
```bash
# Using tcpdump to capture API calls
sudo tcpdump -i any -A 'host us-south.ml.cloud.ibm.com and port 443'
```

---

#### watsonx.ai-Specific Configuration

When using watsonx.ai as the backend, additional configuration may be required:

**Full watsonx.ai Endpoint:**
```
https://us-south.ml.cloud.ibm.com/ml/v1/chat/completions
```

**Required Headers:**
```python
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
    "ML-Instance-ID": "{project_id_or_space_id}"  # Optional, for multi-tenancy
}
```

**Example Python Configuration:**
```python
from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("WATSONX_API_KEY"),
    base_url="https://us-south.ml.cloud.ibm.com/ml/v1",
    default_headers={
        "ML-Instance-ID": os.getenv("WATSONX_PROJECT_ID")
    }
)
```

**Regional Endpoints:**
- US South: `https://us-south.ml.cloud.ibm.com/ml/v1`
- EU Germany: `https://eu-de.ml.cloud.ibm.com/ml/v1`
- Japan Tokyo: `https://jp-tok.ml.cloud.ibm.com/ml/v1`

---

#### Error Handling and Response Codes

**Common HTTP Status Codes:**

| Code | Meaning | Action |
|------|---------|--------|
| 200 | Success | Parse response and extract data |
| 400 | Bad Request | Check request format and parameters |
| 401 | Unauthorized | Verify API key and authentication |
| 429 | Rate Limit | Implement exponential backoff |
| 500 | Server Error | Retry with exponential backoff |
| 503 | Service Unavailable | Wait and retry |

**Example Error Response:**
```json
{
  "error": {
    "message": "Invalid API key provided",
    "type": "invalid_request_error",
    "code": "invalid_api_key"
  }
}
```

**Retry Strategy:**
```python
import time
from openai import OpenAI, APIError, RateLimitError

def call_with_retry(client, messages, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="mistralai/Mistral-Small-3.1-24B-Instruct-2503",
                messages=messages
            )
            return response
        except RateLimitError:
            wait_time = 2 ** attempt  # Exponential backoff
            time.sleep(wait_time)
        except APIError as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(1)
```

---

### schema_discoverer IX Integration

The [`schema_discoverer`](https://github.com/SPINE-Docs/spine/blob/main/operators/schema_discoverer.py) operator leverages IX's Discoverer service to automatically generate schemas from document content.

#### Core Implementation Pattern

```python
from ix.discoverer import SchemaDiscoverer
import pyarrow as pa

class SchemaDiscovererOperator:
    def __init__(self, config: dict):
        # Initialize IX Discoverer client
        self.discoverer = SchemaDiscoverer(
            api_base=config.get('api_base', '${WATSONX_API_BASE}'),
            api_key=config.get('api_key', '${WATSONX_API_KEY}'),
            model_id=config.get('model_id', 'mistralai/Mistral-Small-3.1-24B-Instruct-2503'),
            headers=config.get('headers', {})
        )
        self.confidence_threshold = config.get('confidence_threshold', 9.0)
    
    def transform(self, table: pa.Table) -> tuple[list[pa.Table], dict]:
        schemas = []
        
        for doc in table.to_pylist():
            # Call IX Discoverer service
            discovered_schema = self.discoverer.discover(
                content=doc['content'],
                document_type=doc.get('doc_type', 'unknown')
            )
            
            # Evaluate confidence and decide on schema reuse
            if discovered_schema['confidence'] >= self.confidence_threshold:
                schemas.append(discovered_schema['schema'])
            else:
                # Low confidence - may need manual review
                schemas.append(self._create_fallback_schema(doc))
        
        # Add schemas as new column
        result_table = table.append_column(
            'discovered_schema',
            pa.array(schemas)
        )
        
        return [result_table], self._create_metadata(table.num_rows)
```

#### Key Design Decisions

**1. Confidence-Based Schema Reuse**

The operator uses a confidence threshold (default: 9.0/10) to determine whether to reuse a discovered schema:

```python
# High confidence (≥9.0) - Reuse schema for similar documents
if schema_confidence >= 9.0:
    cached_schema = discovered_schema
    use_cached = True

# Low confidence (<9.0) - Discover new schema
else:
    new_schema = discoverer.discover(content)
    use_cached = False
```

**Rationale:**
- Reduces API calls for similar documents
- Improves processing speed
- Maintains accuracy for high-confidence matches
- Allows flexibility for edge cases

**2. Environment Variable Substitution**

Configuration supports `${VAR}` syntax for secure credential management:

```python
# Configuration with environment variables
config = {
    "api_base": "${WATSONX_API_BASE}",
    "api_key": "${WATSONX_API_KEY}",
    "model_id": "${WATSONX_MODEL_ID}"
}

# Automatically resolved at runtime
resolved_config = resolve_env_vars(config)
```

**3. Schema Versioning Strategy**

Discovered schemas include version metadata for tracking evolution:

```python
schema_metadata = {
    "version": "1.0",
    "discovered_at": "2026-03-03T09:00:00Z",
    "confidence": 9.5,
    "document_type": "invoice",
    "field_count": 12
}
```

#### Example: Invoice Schema Discovery

**Input Document:**
```
Invoice #INV-001
Date: 2026-03-01
Customer: Acme Corp
Items:
  - Widget A: $100
  - Widget B: $200
Total: $300
```

**Discovered Schema:**
```json
{
  "type": "object",
  "properties": {
    "invoice_number": {"type": "string"},
    "date": {"type": "string", "format": "date"},
    "customer_name": {"type": "string"},
    "line_items": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "description": {"type": "string"},
          "amount": {"type": "number"}
        }
      }
    },
    "total": {"type": "number"}
  },
  "confidence": 9.2
}
```

---

### data_extractor IX Integration

The [`data_extractor`](https://github.com/SPINE-Docs/spine/blob/main/operators/data_extractor.py) operator uses IX's Extractor service to extract structured data based on provided or discovered schemas.

#### Core Implementation Pattern

```python
from ix.extractor import DataExtractor
import pyarrow as pa

class DataExtractorOperator:
    def __init__(self, config: dict):
        # Initialize IX Extractor client
        self.extractor = DataExtractor(
            api_base=config.get('api_base', '${WATSONX_API_BASE}'),
            api_key=config.get('api_key', '${WATSONX_API_KEY}'),
            model_id=config.get('model_id', 'mistralai/Mistral-Small-3.1-24B-Instruct-2503')
        )
        self.schema_column = config.get('schema_column', 'discovered_schema')
    
    def transform(self, table: pa.Table) -> tuple[list[pa.Table], dict]:
        extracted_data = []
        
        for doc in table.to_pylist():
            # Get schema (from previous schema_discoverer or provided)
            schema = doc.get(self.schema_column)
            
            # Call IX Extractor service
            extraction_result = self.extractor.extract(
                content=doc['content'],
                schema=schema,
                return_confidence=True
            )
            
            extracted_data.append({
                'extracted_fields': extraction_result['data'],
                'confidence': extraction_result['confidence'],
                'extraction_metadata': extraction_result['metadata']
            })
        
        # Add extracted data as new columns
        result_table = table.append_column(
            'extracted_data',
            pa.array([json.dumps(d) for d in extracted_data])
        )
        
        return [result_table], self._create_metadata(table.num_rows)
```

#### Schema-Guided Extraction

The extractor uses the schema to guide extraction with high precision:

```python
# Example: Extract invoice data using discovered schema
extraction_request = {
    "content": invoice_text,
    "schema": {
        "invoice_number": {"type": "string", "required": True},
        "date": {"type": "date", "format": "YYYY-MM-DD"},
        "total": {"type": "number", "minimum": 0}
    },
    "extraction_mode": "strict"  # Enforce schema constraints
}

result = extractor.extract(**extraction_request)
```

**Extraction Modes:**
- **`strict`**: Only extract fields defined in schema
- **`flexible`**: Extract schema fields + additional discovered fields
- **`exploratory`**: Free-form extraction with minimal constraints

#### Confidence Scoring

Each extracted field includes a confidence score:

```python
{
  "invoice_number": {
    "value": "INV-001",
    "confidence": 0.98
  },
  "date": {
    "value": "2026-03-01",
    "confidence": 0.95
  },
  "total": {
    "value": 300.00,
    "confidence": 0.92
  }
}
```

**Confidence Interpretation:**
- **≥0.95**: High confidence - use directly
- **0.80-0.94**: Medium confidence - may need validation
- **<0.80**: Low confidence - requires manual review

---

### API Configuration & Authentication

#### Configuration Structure

IX services are configured through a consistent configuration pattern:

```python
ix_config = {
    # API Endpoint
    "api_base": "https://us-south.ml.cloud.ibm.com/ml/v1",
    
    # Authentication
    "api_key": "${WATSONX_API_KEY}",  # Environment variable
    
    # Model Selection
    "model_id": "mistralai/Mistral-Small-3.1-24B-Instruct-2503",
    
    # Optional Headers
    "headers": {
        "X-Project-ID": "${WATSONX_PROJECT_ID}",
        "Content-Type": "application/json"
    },
    
    # Service-Specific Settings
    "timeout": 30,
    "max_retries": 3,
    "retry_delay": 1.0
}
```

#### Environment Variables

Required environment variables for IX integration:

```bash
# IBM watsonx.ai Configuration
export WATSONX_API_BASE="https://us-south.ml.cloud.ibm.com/ml/v1"
export WATSONX_API_KEY="your-api-key-here"
export WATSONX_PROJECT_ID="your-project-id"

# Optional: Model Override
export WATSONX_MODEL_ID="mistralai/Mistral-Small-3.1-24B-Instruct-2503"

# Optional: Performance Tuning
export IX_TIMEOUT=30
export IX_MAX_RETRIES=3
```

#### Credential Management Best Practices

**1. Use Environment Variables**
```python
# ✅ GOOD: Environment variable substitution
config = {"api_key": "${WATSONX_API_KEY}"}

# ❌ BAD: Hardcoded credentials
config = {"api_key": "hardcoded-key-123"}
```

**2. Implement Credential Validation**
```python
def validate_credentials(config: dict) -> bool:
    """Validate IX credentials before operator execution."""
    required_vars = ['api_base', 'api_key']
    
    for var in required_vars:
        value = resolve_env_var(config.get(var))
        if not value or value.startswith('${'):
            raise ValueError(f"Missing or unresolved credential: {var}")
    
    return True
```

**3. Use Secrets Management**
```python
# Integration with secrets management systems
from datasift.secrets import SecretsManager

secrets = SecretsManager()
config = {
    "api_key": secrets.get("watsonx/api_key"),
    "project_id": secrets.get("watsonx/project_id")
}
```

#### Supported Models

IX supports any OpenAI-compatible model. Common watsonx.ai models:

| Model | Model ID | Use Case |
|-------|----------|----------|
| **Mistral Small** | `mistralai/Mistral-Small-3.1-24B-Instruct-2503` | General purpose (default) |
| **Llama 3.1** | `meta-llama/llama-3-1-70b-instruct` | High accuracy extraction |
| **Granite** | `ibm/granite-13b-instruct-v2` | Enterprise compliance |
| **Mixtral** | `mistralai/mixtral-8x7b-instruct-v01` | Cost-effective processing |

**Model Selection Criteria:**
- **Accuracy Requirements**: Higher parameter models for complex documents
- **Cost Constraints**: Smaller models for high-volume processing
- **Latency Requirements**: Faster models for real-time applications
- **Compliance Needs**: IBM Granite for regulated industries

---

### Data Flow Diagram

The following text-based diagram illustrates the complete data flow through IX-integrated SPINE operators:

```
┌─────────────────────────────────────────────────────────────────────┐
│                        SPINE + IX Data Flow                          │
└─────────────────────────────────────────────────────────────────────┘

1. DOCUMENT INGESTION
   ┌──────────────┐
   │   Documents  │ (PDF, DOCX, TXT, etc.)
   └──────┬───────┘
          │
          ▼
   ┌──────────────────┐
   │ folder2parquet   │ ← SPINE Operator (No IX)
   └──────┬───────────┘
          │
          ▼
   ┌──────────────────────────────────┐
   │ PyArrow Table                    │
   │ ┌──────────┬──────────┬────────┐ │
   │ │ doc_id   │ content  │ path   │ │
   │ ├──────────┼──────────┼────────┤ │
   │ │ 001      │ "text"   │ a.pdf  │ │
   │ └──────────┴──────────┴────────┘ │
   └──────────────┬───────────────────┘
                  │
                  ▼

2. DOCUMENT CLASSIFICATION (Optional)
   ┌──────────────────────────────────┐
   │ IX Classifier Service            │
   │ ┌──────────────────────────────┐ │
   │ │ POST /classifier/classify    │ │
   │ │ {                            │ │
   │ │   "content": "...",          │ │
   │ │   "model": "mistral-small"   │ │
   │ │ }                            │ │
   │ └──────────────────────────────┘ │
   └──────────────┬───────────────────┘
                  │
                  ▼
   ┌──────────────────────────────────┐
   │ Classification Result            │
   │ {                                │
   │   "type": "invoice",             │
   │   "confidence": 0.95,            │
   │   "category": "financial"        │
   │ }                                │
   └──────────────┬───────────────────┘
                  │
                  ▼

3. SCHEMA DISCOVERY
   ┌──────────────────────────────────┐
   │ schema_discoverer Operator       │ ← SPINE Operator (Uses IX)
   │ ┌──────────────────────────────┐ │
   │ │ Check confidence threshold   │ │
   │ │ ├─ High (≥9.0): Reuse schema│ │
   │ │ └─ Low (<9.0): Discover new │ │
   │ └──────────────────────────────┘ │
   └──────────────┬───────────────────┘
                  │
                  ▼
   ┌──────────────────────────────────┐
   │ IX Discoverer Service            │
   │ ┌──────────────────────────────┐ │
   │ │ POST /discoverer/discover    │ │
   │ │ {                            │ │
   │ │   "content": "...",          │ │
   │ │   "document_type": "invoice" │ │
   │ │ }                            │ │
   │ └──────────────────────────────┘ │
   └──────────────┬───────────────────┘
                  │
                  ▼
   ┌──────────────────────────────────┐
   │ Discovered Schema                │
   │ {                                │
   │   "invoice_number": "string",    │
   │   "date": "date",                │
   │   "total": "number",             │
   │   "confidence": 9.2              │
   │ }                                │
   └──────────────┬───────────────────┘
                  │
                  ▼
   ┌──────────────────────────────────┐
   │ PyArrow Table (with schema)      │
   │ ┌────────┬─────────┬───────────┐ │
   │ │ doc_id │ content │ schema    │ │
   │ ├────────┼─────────┼───────────┤ │
   │ │ 001    │ "text"  │ {...}     │ │
   │ └────────┴─────────┴───────────┘ │
   └──────────────┬───────────────────┘
                  │
                  ▼

4. DATA EXTRACTION
   ┌──────────────────────────────────┐
   │ data_extractor Operator          │ ← SPINE Operator (Uses IX)
   │ ┌──────────────────────────────┐ │
   │ │ Use discovered schema        │ │
   │ │ for guided extraction        │ │
   │ └──────────────────────────────┘ │
   └──────────────┬───────────────────┘
                  │
                  ▼
   ┌──────────────────────────────────┐
   │ IX Extractor Service             │
   │ ┌──────────────────────────────┐ │
   │ │ POST /extractor/extract      │ │
   │ │ {                            │ │
   │ │   "content": "...",          │ │
   │ │   "schema": {...},           │ │
   │ │   "mode": "strict"           │ │
   │ │ }                            │ │
   │ └──────────────────────────────┘ │
   └──────────────┬───────────────────┘
                  │
                  ▼
   ┌──────────────────────────────────┐
   │ Extracted Data                   │
   │ {                                │
   │   "invoice_number": "INV-001",   │
   │   "date": "2026-03-01",          │
   │   "total": 300.00,               │
   │   "confidence": 0.95             │
   │ }                                │
   └──────────────┬───────────────────┘
                  │
                  ▼
   ┌──────────────────────────────────┐
   │ Final PyArrow Table              │
   │ ┌────────┬─────────┬───────────┐ │
   │ │ doc_id │ content │ extracted │ │
   │ ├────────┼─────────┼───────────┤ │
   │ │ 001    │ "text"  │ {...}     │ │
   │ └────────┴─────────┴───────────┘ │
   └──────────────────────────────────┘

5. DOWNSTREAM PROCESSING
   ┌──────────────────────────────────┐
   │ • Vector DB Ingestion            │
   │ • Analytics Processing           │
   │ • Export to Target Systems       │
   └──────────────────────────────────┘
```

**Key Flow Characteristics:**

1. **PyArrow-Centric**: All data remains in PyArrow tables throughout the pipeline
2. **Stateless Services**: IX services are called via REST API (no state management)
3. **Confidence-Driven**: Decisions based on confidence scores at each stage
4. **Schema Reuse**: Discovered schemas cached and reused for similar documents
5. **Modular**: Each operator can be used independently or in combination

---

### Configuration Examples

#### Example 1: Basic Schema Discovery Flow

```json
{
  "name": "invoice_schema_discovery",
  "description": "Discover schemas from invoice documents",
  "operators": [
    {
      "name": "ingest_invoices",
      "type": "folder2parquet",
      "config": {
        "input_folder": "./data/invoices",
        "file_pattern": "*.pdf",
        "recursive": true
      }
    },
    {
      "name": "discover_invoice_schema",
      "type": "schema_discoverer",
      "config": {
        "api_base": "${WATSONX_API_BASE}",
        "api_key": "${WATSONX_API_KEY}",
        "model_id": "mistralai/Mistral-Small-3.1-24B-Instruct-2503",
        "confidence_threshold": 9.0,
        "input_column": "content",
        "output_column": "discovered_schema",
        "cache_schemas": true
      }
    }
  ]
}
```

#### Example 2: Complete Discovery + Extraction Pipeline

```json
{
  "name": "invoice_processing_pipeline",
  "description": "Full pipeline: ingest → classify → discover → extract",
  "operators": [
    {
      "name": "ingest",
      "type": "folder2parquet",
      "config": {
        "input_folder": "./data/documents",
        "file_pattern": "*.{pdf,docx}"
      }
    },
    {
      "name": "discover_schema",
      "type": "schema_discoverer",
      "config": {
        "api_base": "${WATSONX_API_BASE}",
        "api_key": "${WATSONX_API_KEY}",
        "model_id": "${WATSONX_MODEL_ID}",
        "confidence_threshold": 9.0,
        "headers": {
          "X-Project-ID": "${WATSONX_PROJECT_ID}"
        }
      }
    },
    {
      "name": "extract_data",
      "type": "data_extractor",
      "config": {
        "api_base": "${WATSONX_API_BASE}",
        "api_key": "${WATSONX_API_KEY}",
        "model_id": "${WATSONX_MODEL_ID}",
        "schema_column": "discovered_schema",
        "extraction_mode": "strict",
        "return_confidence": true
      }
    }
  ]
}
```

#### Example 3: Multi-Model Configuration

```json
{
  "name": "multi_model_extraction",
  "description": "Use different models for different tasks",
  "operators": [
    {
      "name": "discover_schema_fast",
      "type": "schema_discoverer",
      "config": {
        "api_base": "${WATSONX_API_BASE}",
        "api_key": "${WATSONX_API_KEY}",
        "model_id": "mistralai/mixtral-8x7b-instruct-v01",
        "comment": "Fast model for initial discovery"
      }
    },
    {
      "name": "extract_data_accurate",
      "type": "data_extractor",
      "config": {
        "api_base": "${WATSONX_API_BASE}",
        "api_key": "${WATSONX_API_KEY}",
        "model_id": "meta-llama/llama-3-1-70b-instruct",
        "comment": "High-accuracy model for extraction"
      }
    }
  ]
}
```

#### Example 4: Error Handling & Retry Configuration

```json
{
  "name": "robust_extraction",
  "description": "Production configuration with error handling",
  "operators": [
    {
      "name": "extract_with_retry",
      "type": "data_extractor",
      "config": {
        "api_base": "${WATSONX_API_BASE}",
        "api_key": "${WATSONX_API_KEY}",
        "model_id": "${WATSONX_MODEL_ID}",
        
        "timeout": 30,
        "max_retries": 3,
        "retry_delay": 2.0,
        "retry_backoff": "exponential",
        
        "error_handling": {
          "on_api_error": "skip",
          "on_low_confidence": "flag",
          "on_schema_mismatch": "log"
        },
        
        "fallback": {
          "enabled": true,
          "fallback_model": "mistralai/mixtral-8x7b-instruct-v01"
        }
      }
    }
  ]
}
```

---

### Key Design Patterns

#### Pattern 1: Confidence-Based Decision Making

SPINE operators use confidence scores to make intelligent processing decisions:

```python
class ConfidenceBasedProcessor:
    """Pattern for confidence-driven processing decisions."""
    
    def __init__(self, high_threshold=9.0, medium_threshold=7.0):
        self.high_threshold = high_threshold
        self.medium_threshold = medium_threshold
    
    def process_with_confidence(self, result: dict) -> str:
        """Route processing based on confidence score."""
        confidence = result.get('confidence', 0.0)
        
        if confidence >= self.high_threshold:
            # High confidence: Automatic processing
            return self._auto_process(result)
        
        elif confidence >= self.medium_threshold:
            # Medium confidence: Validation required
            return self._validate_and_process(result)
        
        else:
            # Low confidence: Manual review
            return self._queue_for_review(result)
```

**Application in SPINE:**
- **Schema Discovery**: Reuse schemas with confidence ≥9.0
- **Data Extraction**: Auto-accept fields with confidence ≥0.95
- **Classification**: Route documents based on classification confidence

#### Pattern 2: Schema Reuse Strategy

Optimize API calls by caching and reusing discovered schemas:

```python
class SchemaCache:
    """Pattern for intelligent schema caching and reuse."""
    
    def __init__(self, confidence_threshold=9.0):
        self.cache = {}
        self.confidence_threshold = confidence_threshold
    
    def get_or_discover(self, doc_type: str, content: str) -> dict:
        """Get cached schema or discover new one."""
        
        # Check cache for high-confidence schema
        if doc_type in self.cache:
            cached = self.cache[doc_type]
            if cached['confidence'] >= self.confidence_threshold:
                cached['cache_hit'] = True
                return cached
        
        # Discover new schema
        new_schema = self.discoverer.discover(content, doc_type)
        
        # Cache if high confidence
        if new_schema['confidence'] >= self.confidence_threshold:
            self.cache[doc_type] = new_schema
        
        new_schema['cache_hit'] = False
        return new_schema
```

**Benefits:**
- Reduces API calls by 60-80% for similar documents
- Improves processing speed
- Maintains consistency across document batches
- Lowers operational costs

#### Pattern 3: Progressive Enhancement

Start with basic extraction and progressively enhance with AI:

```python
class ProgressiveExtractor:
    """Pattern for progressive extraction enhancement."""
    
    def extract(self, content: str) -> dict:
        """Extract data with progressive enhancement."""
        
        # Level 1: Rule-based extraction (fast, cheap)
        basic_data = self._rule_based_extract(content)
        
        # Level 2: AI enhancement for missing fields
        if self._has_missing_fields(basic_data):
            ai_data = self._ai_extract(content, basic_data)
            basic_data.update(ai_data)
        
        # Level 3: Validation and refinement
        if self._needs_validation(basic_data):
            validated_data = self._ai_validate(basic_data)
            return validated_data
        
        return basic_data
```

**Use Cases:**
- Cost optimization (use AI only when needed)
- Hybrid extraction (rules + AI)
- Fallback mechanisms

#### Pattern 4: Batch Processing with Rate Limiting

Handle large document volumes efficiently:

```python
class BatchProcessor:
    """Pattern for efficient batch processing with rate limiting."""
    
    def __init__(self, batch_size=10, rate_limit=100):
        self.batch_size = batch_size
        self.rate_limit = rate_limit  # requests per minute
        self.request_count = 0
        self.window_start = time.time()
    
    def process_batch(self, documents: list) -> list:
        """Process documents in batches with rate limiting."""
        results = []
        
        for i in range(0, len(documents), self.batch_size):
            batch = documents[i:i + self.batch_size]
            
            # Check rate limit
            self._enforce_rate_limit()
            
            # Process batch
            batch_results = self._process_documents(batch)
            results.extend(batch_results)
            
            self.request_count += len(batch)
        
        return results
    
    def _enforce_rate_limit(self):
        """Enforce rate limiting."""
        elapsed = time.time() - self.window_start
        
        if elapsed < 60 and self.request_count >= self.rate_limit:
            sleep_time = 60 - elapsed
            time.sleep(sleep_time)
            self.request_count = 0
            self.window_start = time.time()
```

---

### Integration Requirements for DataSift

To successfully integrate IX-powered SPINE operators into DataSift, the following requirements must be met:

#### 1. Infrastructure Requirements

**API Access:**
- [ ] IBM watsonx.ai account with API access
- [ ] API key with appropriate permissions
- [ ] Project ID for resource organization
- [ ] Network connectivity to watsonx.ai endpoints

**Compute Resources:**
- [ ] Sufficient memory for PyArrow table operations (recommend 8GB+ RAM)
- [ ] CPU resources for data processing (4+ cores recommended)
- [ ] Storage for schema caching (1-10GB depending on volume)

**Network Requirements:**
- [ ] Outbound HTTPS access to watsonx.ai endpoints
- [ ] Firewall rules allowing API communication
- [ ] Proxy configuration (if applicable)

#### 2. Software Dependencies

**Python Packages:**
```python
# Core dependencies
pyarrow >= 12.0.0
requests >= 2.31.0
python-dotenv >= 1.0.0

# IX library (from SPINE-Docs/ix)
# Install from GitHub or local copy
pip install git+https://github.com/SPINE-Docs/ix.git

# Optional: IBM watsonx.ai SDK
ibm-watsonx-ai >= 0.2.0
```

**Environment Setup:**
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export WATSONX_API_BASE="https://us-south.ml.cloud.ibm.com/ml/v1"
export WATSONX_API_KEY="your-api-key"
export WATSONX_PROJECT_ID="your-project-id"
```

#### 3. Code Integration Steps

**Step 1: Create IX Client Wrapper**

Create [`src/datasift_opensource/backend/core/operators/universal/schema/ix_client.py`](src/datasift_opensource/backend/core/operators/universal/schema/ix_client.py):

```python
"""Shared IX client for watsonx.ai integration."""

from typing import Any, Optional
import os
import requests
from common.util.infrastructure.logging import get_logger

logger = get_logger(__name__)

class IXClient:
    """Wrapper for IX services (Classifier, Discoverer, Extractor)."""
    
    def __init__(self, config: dict[str, Any]):
        self.api_base = self._resolve_env(config.get('api_base'))
        self.api_key = self._resolve_env(config.get('api_key'))
        self.model_id = config.get('model_id', 'mistralai/Mistral-Small-3.1-24B-Instruct-2503')
        self.headers = config.get('headers', {})
        self.timeout = config.get('timeout', 30)
        
        # Validate configuration
        self._validate_config()
    
    def _resolve_env(self, value: str) -> str:
        """Resolve environment variable references."""
        if value and value.startswith('${') and value.endswith('}'):
            var_name = value[2:-1]
            return os.getenv(var_name, value)
        return value
    
    def _validate_config(self):
        """Validate required configuration."""
        if not self.api_base or self.api_base.startswith('${'):
            raise ValueError("Missing or unresolved api_base")
        if not self.api_key or self.api_key.startswith('${'):
            raise ValueError("Missing or unresolved api_key")
    
    def discover_schema(self, content: str, document_type: str = "unknown") -> dict:
        """Call IX Discoverer service."""
        endpoint = f"{self.api_base}/discoverer/discover"
        
        payload = {
            "content": content,
            "document_type": document_type,
            "model_id": self.model_id
        }
        
        response = requests.post(
            endpoint,
            json=payload,
            headers={**self.headers, "Authorization": f"Bearer {self.api_key}"},
            timeout=self.timeout
        )
        
        response.raise_for_status()
        return response.json()
    
    def extract_data(self, content: str, schema: dict, mode: str = "strict") -> dict:
        """Call IX Extractor service."""
        endpoint = f"{self.api_base}/extractor/extract"
        
        payload = {
            "content": content,
            "schema": schema,
            "model_id": self.model_id,
            "extraction_mode": mode
        }
        
        response = requests.post(
            endpoint,
            json=payload,
            headers={**self.headers, "Authorization": f"Bearer {self.api_key}"},
            timeout=self.timeout
        )
        
        response.raise_for_status()
        return response.json()
```

**Step 2: Implement schema_discoverer Operator**

Create [`src/datasift_opensource/backend/core/operators/universal/schema/schema_discoverer.py`](src/datasift_opensource/backend/core/operators/universal/schema/schema_discoverer.py):

```python
"""Schema discovery operator using IX."""

from typing import Any
import pyarrow as pa
import json

from core.operators.abstract_operator import AbstractOperator, OperatorCategory
from .ix_client import IXClient

class SchemaDiscovererOperator(AbstractOperator):
    """Discover schemas from documents using IX."""
    
    short_name = "schema_discoverer"
    category = OperatorCategory.Functional
    
    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        
        # Initialize IX client
        self.ix_client = IXClient(config)
        
        # Configuration
        self.confidence_threshold = config.get('confidence_threshold', 9.0)
        self.input_column = config.get('input_column', 'content')
        self.output_column = config.get('output_column', 'discovered_schema')
        self.cache_schemas = config.get('cache_schemas', True)
        
        # Schema cache
        self.schema_cache = {}
    
    def get_required_features(self) -> list[str]:
        return [self.input_column]
    
    def transform(self, table: pa.Table) -> tuple[list[pa.Table], dict[str, Any]]:
        """Discover schemas for documents in table."""
        schemas = []
        
        for doc in table.to_pylist():
            content = doc.get(self.input_column, '')
            doc_type = doc.get('doc_type', 'unknown')
            
            # Check cache
            if self.cache_schemas and doc_type in self.schema_cache:
                cached = self.schema_cache[doc_type]
                if cached['confidence'] >= self.confidence_threshold:
                    schemas.append(json.dumps(cached))
                    continue
            
            # Discover new schema
            result = self.ix_client.discover_schema(content, doc_type)
            
            # Cache if high confidence
            if self.cache_schemas and result['confidence'] >= self.confidence_threshold:
                self.schema_cache[doc_type] = result
            
            schemas.append(json.dumps(result))
        
        # Add schema column
        result_table = table.append_column(
            self.output_column,
            pa.array(schemas)
        )
        
        metadata = self.create_base_metadata(total_docs_count=table.num_rows)
        metadata['schemas_discovered'] = len(set(schemas))
        metadata['cache_hits'] = len([s for s in schemas if s in self.schema_cache.values()])
        
        return [result_table], metadata
```

**Step 3: Register Operators**

Update [`src/datasift_opensource/backend/core/orchestrator/operator_factory.py`](src/datasift_opensource/backend/core/orchestrator/operator_factory.py):

```python
# Add imports
from core.operators.universal.schema.schema_discoverer import SchemaDiscovererOperator
from core.operators.universal.extract.extract_entities_watsonx import DataExtractorOperator

# Register in operator registry
OPERATOR_REGISTRY = {
    # ... existing operators ...
    "schema_discoverer": SchemaDiscovererOperator,
    "data_extractor": DataExtractorOperator,
}
```

#### 4. Testing Requirements

**Unit Tests:**
```python
# tests/unit/test_schema_discoverer.py
import pytest
from unittest.mock import Mock, patch
from core.operators.universal.schema.schema_discoverer import SchemaDiscovererOperator

def test_schema_discoverer_initialization():
    config = {
        "api_base": "https://test.api.com",
        "api_key": "test-key",
        "confidence_threshold": 9.0
    }
    operator = SchemaDiscovererOperator(config)
    assert operator.confidence_threshold == 9.0

@patch('core.operators.universal.schema.ix_client.requests.post')
def test_schema_discovery(mock_post):
    mock_post.return_value.json.return_value = {
        "schema": {"field1": "string"},
        "confidence": 9.5
    }
    
    # Test operator
    # ... test implementation ...
```

**Integration Tests:**
```python
# tests/integration/test_ix_integration.py
import pytest
import os

@pytest.mark.integration
@pytest.mark.skipif(not os.getenv('WATSONX_API_KEY'), reason="No API key")
def test_real_schema_discovery():
    """Test with real IX API."""
    config = {
        "api_base": os.getenv('WATSONX_API_BASE'),
        "api_key": os.getenv('WATSONX_API_KEY')
    }
    
    operator = SchemaDiscovererOperator(config)
    # ... test with real API ...
```

#### 5. Documentation Requirements

**User Documentation:**
- [ ] Operator usage guide
- [ ] Configuration reference
- [ ] Example flows
- [ ] Troubleshooting guide

**Developer Documentation:**
- [ ] Architecture overview
- [ ] API integration details
- [ ] Extension points
- [ ] Testing guide

**Operational Documentation:**
- [ ] Deployment guide
- [ ] Monitoring setup
- [ ] Performance tuning
- [ ] Cost optimization

#### 6. Monitoring & Observability

**Metrics to Track:**
```python
# Key metrics for IX integration
metrics = {
    "api_calls_total": "Total IX API calls",
    "api_calls_success": "Successful API calls",
    "api_calls_failed": "Failed API calls",
    "api_latency_ms": "API response time",
    "schema_cache_hits": "Schema cache hit rate",
    "confidence_scores": "Distribution of confidence scores",
    "cost_per_document": "Processing cost per document"
}
```

**Logging Strategy:**
```python
# Structured logging for IX operations
logger.info("IX schema discovery started", extra={
    "document_id": doc_id,
    "document_type": doc_type,
    "model_id": model_id
})

logger.info("IX schema discovery completed", extra={
    "document_id": doc_id,
    "confidence": confidence,
    "cache_hit": cache_hit,
    "latency_ms": latency
})
```

#### 7. Cost Management

**Cost Optimization Strategies:**

1. **Schema Caching**: Reduce API calls by 60-80%
2. **Batch Processing**: Process multiple documents per API call
3. **Model Selection**: Use smaller models for simple documents
4. **Confidence Thresholds**: Skip low-value extractions
5. **Rate Limiting**: Control API usage

**Cost Monitoring:**
```python
class CostTracker:
    """Track IX API costs."""
    
    def __init__(self, cost_per_1k_tokens=0.002):
        self.cost_per_1k_tokens = cost_per_1k_tokens
        self.total_tokens = 0
        self.total_cost = 0.0
    
    def track_request(self, tokens_used: int):
        self.total_tokens += tokens_used
        self.total_cost = (self.total_tokens / 1000) * self.cost_per_1k_tokens
    
    def get_cost_report(self) -> dict:
        return {
            "total_tokens": self.total_tokens,
            "total_cost_usd": self.total_cost,
            "cost_per_document": self.total_cost / self.document_count
        }
```

---

**Summary**: This deep dive provides comprehensive technical details on IX integration, including architecture, configuration, data flow, design patterns, and complete integration requirements for DataSift. The information enables informed decision-making and provides a clear implementation roadmap for IX-powered SPINE operators.

---

## Integration Analysis

### 1. folder2parquet - File Ingestion Operator

#### Functional Description
Ingests files from a directory structure and converts them to PyArrow tables with metadata. Supports multiple file formats and recursive directory traversal.

#### DataSift Equivalent
Partial overlap with existing ingestion operators in `src/datasift_opensource/backend/core/operators/universal/`, but SPINE's implementation offers:
- More comprehensive file format support
- Better metadata extraction
- Optimized PyArrow table construction

#### Integration Complexity: **EASY** ⭐

**Rationale:**
- Direct PyArrow table output matches DataSift's data model
- No external AI dependencies
- Clear operator pattern alignment
- Minimal architectural changes required

#### Value Proposition: **MEDIUM** 📊

**Benefits:**
- Enhanced file ingestion capabilities
- Better metadata handling
- Potential performance improvements
- Unified ingestion interface

**Limitations:**
- Overlaps with existing functionality
- May require refactoring existing ingestion code

#### Technical Requirements

```python
# Dependencies
- pyarrow >= 12.0.0
- pathlib (standard library)
- mimetypes (standard library)
```

#### Recommended Integration Approach

**Option A: Replace Existing Ingestion (Recommended)**
- Deprecate current ingestion operators
- Adopt `folder2parquet` as primary ingestion operator
- Migrate existing flows gradually

**Option B: Parallel Implementation**
- Keep existing operators
- Add `folder2parquet` as alternative
- Allow users to choose based on use case

**Implementation Steps:**
1. Create `src/datasift_opensource/backend/core/operators/universal/ingest/folder2parquet.py`
2. Adapt SPINE code to inherit from `AbstractOperator`
3. Implement required methods: `transform()`, `validate()`, `get_metadata()`
4. Add operator constant to `OperatorConstants`
5. Register in operator factory

---

### 2. schema_discoverer - AI-Powered Schema Discovery

#### Functional Description
Uses IBM watsonx.ai/IX to automatically discover and generate schemas from unstructured or semi-structured data. Analyzes document content and infers field types, relationships, and structure.

#### DataSift Equivalent
**NO DIRECT EQUIVALENT** - This is a **CRITICAL GAP** in DataSift's current capabilities.

DataSift currently requires:
- Manual schema definition
- Pre-defined extraction templates
- User-provided structure

SPINE's `schema_discoverer` offers:
- Automated schema inference
- AI-powered field type detection
- Relationship discovery
- Adaptive schema generation

#### Integration Complexity: **MEDIUM** ⚠️

**Rationale:**
- Requires IBM watsonx.ai/IX integration
- New concept for DataSift architecture
- Needs credential management
- API integration complexity

**Complexity Factors:**
- ✅ PyArrow table I/O (compatible)
- ⚠️ IX/watsonx.ai API integration (new)
- ⚠️ Credential management (new)
- ✅ Operator pattern (compatible)

#### Value Proposition: **HIGH** 🚀

**Strategic Benefits:**
- **Fills critical capability gap**
- Reduces manual schema definition effort
- Enables rapid data onboarding
- Improves user experience significantly
- Competitive differentiator

**Use Cases:**
- Rapid prototyping with unknown data structures
- Automated data discovery pipelines
- Schema evolution detection
- Multi-format data integration

#### Technical Requirements

```python
# Dependencies
- pyarrow >= 12.0.0
- ibm-watsonx-ai >= 0.2.0  # or equivalent IX SDK
- requests >= 2.31.0
- python-dotenv >= 1.0.0  # for credential management

# Environment Variables
IX_API_KEY=<watsonx-api-key>
IX_PROJECT_ID=<project-id>
IX_ENDPOINT=<api-endpoint>
```

#### Recommended Integration Approach

**Phase 1: Core Integration (Weeks 1-2)**
1. Set up IX/watsonx.ai credentials management
2. Create base operator structure
3. Implement schema discovery API calls
4. Add PyArrow table integration

**Phase 2: Enhancement (Weeks 3-4)**
1. Add schema validation and refinement
2. Implement caching for discovered schemas
3. Add user override capabilities
4. Create schema versioning support

**Phase 3: Production Readiness (Weeks 5-6)**
1. Add comprehensive error handling
2. Implement retry logic for API calls
3. Add monitoring and logging
4. Create user documentation

**Implementation Location:**
```
src/datasift_opensource/backend/core/operators/universal/schema/
├── __init__.py
├── schema_discoverer.py          # Main operator
├── ix_client.py                  # IX API client wrapper
└── schema_validator.py           # Schema validation utilities
```

---

### 3. data_extractor - AI-Powered KVP Extraction

#### Functional Description
Extracts key-value pairs and structured entities from documents using IBM watsonx.ai/IX. Supports schema-guided extraction and free-form entity recognition.

#### DataSift Equivalent
**PARTIAL OVERLAP** with `extract_entities_ollama.py`

**Comparison:**

| Feature | DataSift (Ollama) | SPINE (IX) |
|---------|-------------------|------------|
| AI Backend | Local Ollama | IBM watsonx.ai/IX |
| Schema Support | ✅ Yes | ✅ Yes |
| Free-form Extraction | ✅ Yes | ✅ Yes |
| Cost | Free (local) | Paid (API) |
| Performance | Depends on hardware | Consistent (cloud) |
| Model Quality | Varies by model | Enterprise-grade |

#### Integration Complexity: **MEDIUM** ⚠️

**Rationale:**
- Similar to existing Ollama operator
- Requires IX integration (like `schema_discoverer`)
- Can leverage shared IX client infrastructure
- Operator pattern well-established

#### Value Proposition: **MEDIUM** 📊

**Benefits:**
- Enterprise-grade extraction quality
- Consistent performance
- Better for production workloads
- Complements local Ollama option

**Considerations:**
- Adds API costs
- Requires internet connectivity
- May not justify replacement of Ollama
- Better as complementary option

#### Recommended Integration Approach

**Strategy: Complementary Implementation**

Rather than replacing the existing Ollama-based extractor, add SPINE's `data_extractor` as an alternative backend.

**Implementation Location:**
```
src/datasift_opensource/backend/core/operators/universal/extract/
├── __init__.py
├── extract_entities_ollama.py    # Existing
├── extract_entities_watsonx.py   # New (from SPINE)
├── extract_entities_base.py      # New abstraction
└── extraction_backends.py        # Backend registry
```

---

### 4. smt_builder - Schema Mapping Template Builder

#### Functional Description
Generates Schema Mapping Templates (SMT) that define transformations between source and target schemas. Uses AI to suggest mappings, transformations, and data type conversions.

#### DataSift Equivalent
**NO EQUIVALENT** - This is a **NEW CONCEPT** for DataSift.

#### Integration Complexity: **HARD** 🔴

**Rationale:**
- Introduces entirely new concept (SMT)
- Requires architectural changes
- Complex AI integration (see [Watsonx.ai/IX Integration Deep Dive](#watsonxaiix-integration-deep-dive))
- New data structures and formats
- Significant learning curve

#### Value Proposition: **HIGH** (Long-term) 🎯

**Strategic Benefits:**
- Enables declarative data transformations
- Reduces custom code requirements
- Improves transformation reusability
- Better governance and versioning
- Facilitates data lineage tracking

#### Recommended Integration Approach

**Strategy: Research & Pilot Phase**

**Phase 1: Research & Design (Months 1-2)**
1. Analyze SPINE's SMT format in detail
2. Design DataSift-compatible SMT structure
3. Create proof-of-concept implementation
4. Gather user feedback on concept

---

### 5. smt_executor - Schema Mapping Template Executor

#### Functional Description
Executes transformations defined in SMT files. Applies mappings, conversions, and transformations to convert data from source to target schema.

#### Integration Complexity: **MEDIUM-HARD** ⚠️🔴

**Rationale:**
- Depends on `smt_builder` integration
- Requires SMT parsing and execution engine
- CSV output differs from DataSift's PyArrow model

#### Value Proposition: **MEDIUM-HIGH** 📈

**Benefits:**
- Enables declarative transformations
- Improves transformation reusability
- Better for non-technical users

---

## Architectural Considerations

### DataSift Operator Architecture

DataSift operators follow a consistent pattern based on `AbstractOperator`:

```python
from core.operators.abstract_operator import AbstractOperator, OperatorCategory

class MyOperator(AbstractOperator):
    short_name = "my_operator"
    category = OperatorCategory.Functional
    
    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        
    def get_required_features(self) -> list[str]:
        return ["content"]
        
    def validate(self, errors: list, warnings: list, available_features: list):
        super().validate(errors, warnings, available_features)
        
    def transform(self, table: pa.Table) -> tuple[list[pa.Table], dict[str, Any]]:
        metadata = self.create_base_metadata(total_docs_count=table.num_rows)
        result_table = self._process(table)
        return [result_table], metadata
```

### SPINE Integration Patterns

#### Pattern 1: Direct Inheritance (Simple Operators)

For operators like `folder2parquet`:

```python
class Folder2ParquetOperator(AbstractOperator):
    short_name = "folder2parquet"
    category = OperatorCategory.Ingest
    
    def transform(self, table: pa.Table) -> tuple[list[pa.Table], dict[str, Any]]:
        files = self._discover_files(self.input_folder)
        result_table = self._ingest_files(files)
        metadata = self.create_base_metadata(total_docs_count=result_table.num_rows)
        return [result_table], metadata
```

#### Pattern 2: Backend Abstraction (AI Operators)

For operators requiring external AI services:

```python
class IXClient:
    """Shared IBM watsonx.ai/IX client for SPINE operators."""
    
    def discover_schema(self, data: pa.Table) -> dict[str, Any]:
        """Call IX schema discovery API."""
        pass
        
    def extract_entities(self, text: str, schema: dict) -> dict[str, Any]:
        """Call IX entity extraction API."""
        pass
```

---

## Implementation Roadmap

### Phase 1: Foundation (Months 1-2)

**Goal:** Establish IX integration infrastructure and integrate highest-value operator

**Deliverables:**
1. IX client infrastructure
2. Credential management system
3. `schema_discoverer` operator integration
4. Basic documentation

**Tasks:**

**Week 1-2: IX Infrastructure**
- [ ] Create `ix_client.py` wrapper
- [ ] Implement credential management
- [ ] Add IX dependencies to `requirements.txt`
- [ ] Create IX connection tests

**Week 3-4: Schema Discoverer**
- [ ] Port SPINE `schema_discoverer` code
- [ ] Adapt to `AbstractOperator` interface
- [ ] Implement `transform()` method
- [ ] Add validation and error handling

**Week 5-6: Testing & Documentation**
- [ ] Create unit tests
- [ ] Create integration tests
- [ ] Write operator documentation
- [ ] Create usage examples

**Success Criteria:**
- ✅ IX client successfully connects
- ✅ `schema_discoverer` discovers schemas from sample documents
- ✅ All tests pass
- ✅ Documentation complete

---

### Phase 2: Enhanced Ingestion (Month 3)

**Goal:** Improve file ingestion capabilities with `folder2parquet`

**Deliverables:**
1. `folder2parquet` operator
2. Enhanced metadata extraction
3. Performance benchmarks
4. Migration guide

---

### Phase 3: Extraction Enhancement (Month 4)

**Goal:** Add IX-based extraction as alternative to Ollama

**Deliverables:**
1. `data_extractor` operator (IX backend)
2. Backend abstraction layer
3. Performance comparison
4. Backend selection guide

---

### Phase 4: SMT Research & Pilot (Months 5-6)

**Goal:** Evaluate SMT concept and create pilot implementation

**Deliverables:**
1. SMT format specification
2. Proof-of-concept implementation
3. User feedback report
4. Go/no-go recommendation

---

## Code Integration Guidelines

### Directory Structure

```
src/datasift_opensource/backend/core/operators/
├── universal/
│   ├── ingest/
│   │   └── folder2parquet.py              # SPINE operator
│   │
│   ├── schema/                             # New directory
│   │   ├── schema_discoverer.py           # SPINE operator
│   │   ├── ix_client.py                   # Shared IX client
│   │   └── schema_validator.py            # Utilities
│   │
│   ├── extract/
│   │   ├── extract_entities_ollama.py     # Existing
│   │   ├── extract_entities_watsonx.py    # SPINE operator
│   │   └── extraction_backends.py         # Backend registry
│   │
│   └── transform/
│       └── smt/                            # New directory
│           ├── smt_builder.py             # SPINE operator
│           └── smt_executor.py            # SPINE operator
```

### Example Flow Configuration

```json
{
  "name": "spine_integration_example",
  "operators": [
    {
      "name": "ingest_files",
      "type": "folder2parquet",
      "config": {
        "input_folder": "./data/input",
        "file_pattern": "*.pdf"
      }
    },
    {
      "name": "discover_schema",
      "type": "schema_discoverer",
      "config": {
        "input_column": "content",
        "output_column": "discovered_schema",
        "ix_api_key": "${IX_API_KEY}"
      }
    }
  ]
}
```

---

## Testing Strategy

### Unit Testing

```python
class TestSchemaDiscovererOperator:
    def test_operator_initialization(self, config):
        operator = SchemaDiscovererOperator(config)
        assert operator.short_name == "schema_discoverer"
        
    def test_schema_discovery(self, mock_ix_client, sample_table):
        operator = SchemaDiscovererOperator(config)
        result_tables, metadata = operator.transform(sample_table)
        assert "discovered_schema" in result_tables[0].column_names
```

### Integration Testing

```python
class TestSpineIntegration:
    @pytest.mark.integration
    def test_full_spine_flow(self, flow_config):
        orchestrator = CmdLineOrchestrator(flow_config)
        result = orchestrator.execute()
        assert result["status"] == "completed"
```

---

## Risk Assessment

### Technical Risks

#### 1. IX/watsonx.ai API Dependency

**Risk Level:** HIGH 🔴

**Impact:**
- Service outages affect operator availability
- API rate limits may throttle processing
- API costs scale with usage

**Mitigation:**
1. Implement robust retry logic
2. Add circuit breaker pattern
3. Cache API responses
4. Provide fallback mechanisms
5. Monitor API usage and costs

#### 2. Schema Mapping Template (SMT) Complexity

**Risk Level:** MEDIUM-HIGH ⚠️🔴

**Impact:**
- Steep learning curve for users
- Potential resistance to adoption
- Increased support burden

**Mitigation:**
1. Extensive user research
2. Create intuitive UI
3. Provide comprehensive examples
4. Gradual rollout with pilot users

#### 3. Performance Impact

**Risk Level:** MEDIUM ⚠️

**Impact:**
- Slower processing times
- Increased resource consumption
- Higher infrastructure costs

**Mitigation:**
1. Implement batch processing
2. Add caching layers
3. Provide async execution options
4. Add performance monitoring

---

## Conclusion

### Summary of Findings

The integration of SPINE operators into DataSift presents a **significant opportunity** to enhance the platform's capabilities, particularly in automated schema discovery.

### Final Recommendations

#### Immediate Actions (Next 3 Months)

1. **✅ PROCEED with `schema_discoverer` integration** (Priority 1)
   - Highest value proposition
   - Fills critical gap
   - Medium complexity

2. **✅ PROCEED with `folder2parquet` integration** (Priority 2)
   - Easy integration
   - Improves existing functionality

3. **⚠️ EVALUATE `data_extractor`** (Priority 3)
   - Consider as complementary option
   - Implement if IX integration in place

#### Medium-Term Actions (Months 4-6)

4. **🔍 RESEARCH SMT concept** (`smt_builder`, `smt_executor`)
   - Conduct user research
   - Create proof-of-concept
   - Make go/no-go decision

### Success Metrics

| Metric | Target | Timeline |
|--------|--------|----------|
| `schema_discoverer` adoption rate | >30% of users | 6 months |
| Schema discovery accuracy | >85% | 3 months |
| User satisfaction score | >4.0/5.0 | 6 months |
| Performance (schema discovery) | <5s per document | 3 months |

### Next Steps

1. **Week 1**: Present findings to stakeholders
2. **Week 2**: Set up IX integration infrastructure
3. **Week 3-4**: Begin `schema_discoverer` implementation
4. **Week 5-8**: Complete Phase 1 deliverables
5. **Month 3**: Review progress and plan Phase 2

---

## Appendices

### Appendix A: Operator Comparison Matrix

| Feature | `folder2parquet` | `schema_discoverer` | `data_extractor` | `smt_builder` | `smt_executor` |
|---------|------------------|---------------------|------------------|---------------|----------------|
| **Complexity** | EASY | MEDIUM | MEDIUM | HARD | MEDIUM-HARD |
| **Value** | MEDIUM | HIGH | MEDIUM | HIGH | MEDIUM-HIGH |
| **Priority** | 2 | 1 | 3 | 4 | 4 |
| **AI Required** | No | Yes (IX) | Yes (IX) | Yes (IX) | No |
| **Estimated Effort** | 2-3 weeks | 6-8 weeks | 4-6 weeks | 12-16 weeks | 8-10 weeks |

### Appendix B: Glossary

| Term | Definition |
|------|------------|
| **PyArrow** | Columnar in-memory data format and processing library |
| **IX** | IBM watsonx.ai Intelligence eXtraction service |
| **SMT** | Schema Mapping Template - declarative transformation definition |
| **KVP** | Key-Value Pair extraction |
| **Ollama** | Local LLM runtime used by DataSift |

---

**Document Control**

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-03-03 | DataSift Technical Documentation Team | Initial release |
| 1.1 | 2026-03-03 | DataSift Technical Documentation Team | Added comprehensive Watsonx.ai/IX Integration Deep Dive section with architecture, configuration, data flow, design patterns, and integration requirements |

---

*End of Report*