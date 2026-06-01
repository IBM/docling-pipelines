# Document Classifier Operator - Configuration Reference

## Overview

The Document Classifier operator uses LLM-based classification to identify document types with confidence scores and reasoning. It supports multiple LLM providers (LiteLLM and watsonx) and can classify documents into predefined categories.

- **Operator Name:** `document_classifier`
- **Category**: Quality
- **Short Name**: `document_classifier`

### Supported File Extensions

The operator validates file extensions and only processes documents with the following formats:
- **PDF**: `.pdf`
- **Microsoft Word**: `.docx`, `.doc`
- **Microsoft PowerPoint**: `.pptx`, `.ppt`

**Unsupported formats** are automatically **skipped** (not classified) but remain in the output table with `None` classification values. These documents are tracked as skipped documents in the operator metadata with the reason "Unsupported file extension".

## Configuration Parameters

#### 1. `provider` (String)
**Type:** String
**Required:** No
**Default:** `"litellm"`
**Description:** LLM provider to use for classification.

**Valid Values:**
- `"litellm"` - Unified interface for 100+ LLM providers (OpenAI, Anthropic, Azure, AWS Bedrock, Google, Ollama via OpenAI-compatible API, etc.)
- `"watsonx"` - Uses IBM watsonx.ai via REST API (requires API credentials)

**Examples:**
```json
"provider": "litellm"
"provider": "watsonx"
```

#### 2. `provider_config` (JSON/Dictionary)
**Type:** JSON Object
**Required:** No (Yes for watsonx and most litellm providers)
**Default:** `{}`
**Description:** Provider-specific configuration parameters.

**For LiteLLM:**
- `api_key` (String, Required for most providers): API key for authentication
- `api_base` (String, Optional): Custom API endpoint (e.g., for Ollama OpenAI-compatible endpoint)
- `request_timeout` (Integer, Optional): Request timeout in seconds (default: 120)
- `stream` (Boolean, Optional): Enable HTTP chunked transfer encoding to keep connections alive during long-running requests (default: false). Recommended for remote vLLM clusters processing large documents.
- `timeout` (Integer, Optional): HTTP client read timeout in seconds (default: 60). Set to 1800 (30 minutes) for large documents requiring extended generation time.

**For watsonx:**
- `api_base` (String, Required): API endpoint URL
- `api_key` (String, Required): API key for authentication
- `container_kind` (String, Required): Container type (`"project"` or `"space"` or `"catalog"`)
- `container_id` (String, Required): Container ID (UUID format)
- `request_timeout` (Integer, Optional): Request timeout in seconds (default: 120)

**Examples:**

LiteLLM with OpenAI:
```json
"provider_config": {
  "api_key": "${OPENAI_API_KEY}",
  "request_timeout": 120
}
```

LiteLLM with Ollama (OpenAI-compatible endpoint):
```json
"provider_config": {
  "api_key": "ollama",  # pragma: allowlist secret
  "api_base": "http://localhost:11434/v1",
  "request_timeout": 120
}
```

LiteLLM with Remote vLLM (with streaming and extended timeout for large documents):
```json
"provider_config": {
  "api_key": "YOUR_API_KEY",  # pragma: allowlist secret
  "api_base": "https://your-vllm-route/v1",
  "stream": true,
  "timeout": 1800,
  "request_timeout": 1800
}
```

**Note on Streaming & Extended Timeout:**
For high-concurrency scenarios with remote vLLM clusters processing large documents, use `stream: true` and `timeout: 1800` to prevent connection drops. This combination ensures continuous packet flow (preventing idle timeout detection) and allows completion of large document processing that may take longer than the default 60-second timeout.

watsonx:
```json
"provider_config": {
  "api_base": "https://us-south.ml.cloud.ibm.com",
  "api_key": "your-watsonx-api-key", # pragma: allowlist secret
  "container_kind": "project",
  "container_id": "12345678-1234-1234-1234-123456789abc",
  "request_timeout": 120
}
```

#### 4. `model_id` (String)
**Type:** String
**Required:** No (Yes for watsonx)
**Default:** `"openai/granite3.1-dense:8b"` (Default is for LiteLLM with Ollama; no default model_id for watsonx)
**Description:** Model identifier in `<provider>/<model_id>` format for the selected provider.

**Valid Values:**

**LiteLLM Models (100+ providers):**
- OpenAI: `"openai/gpt-4o-mini"`, `"openai/gpt-4"`, `"openai/gpt-3.5-turbo"`
- Anthropic: `"anthropic/claude-3-opus"`, `"anthropic/claude-3-sonnet"`, `"anthropic/claude-3-haiku"`
- Azure OpenAI: `"azure/gpt-4"`
- AWS Bedrock: `"bedrock/anthropic.claude-3-sonnet"`
- Google Vertex AI: `"vertex_ai/gemini-pro"`
- HuggingFace: `"huggingface/meta-llama/Llama-3.3-70B-Instruct"`, `"huggingface/mistralai/Mistral-7B-Instruct-v0.2"`
- Ollama (via OpenAI-compatible API): `"openai/llama3.2:latest"`, `"openai/granite3.1-dense:8b"`, `"openai/mistral:latest"`

**watsonx Models:**
- `"ibm/granite-3-8b-instruct"` - IBM Granite 3 8B
- `"ibm/granite-3-2b-instruct"` - IBM Granite 3 2B
- `"meta-llama/llama-3-70b-instruct"` - Meta Llama 3 70B
- `"meta-llama/llama-3-8b-instruct"` - Meta Llama 3 8B
- `"mistralai/mixtral-8x7b-instruct-v01"` - Mixtral 8x7B

**Examples:**
```json
"model_id": "openai/gpt-4o-mini"
"model_id": "openai/llama3.2:latest"
"model_id": "openai/granite3.1-dense:8b"
"model_id": "huggingface/meta-llama/Llama-3.3-70B-Instruct"
"model_id": "ibm/granite-3-8b-instruct"
```

#### 6. `document_types` (List or Dictionary)
**Type:** List or Dictionary
**Required:** No
**Default:** Auto-loaded from document class definitions
**Description:** Document types to classify into.

**Valid Values:**

**List Format (Simple):**
```json
"document_types": [
  "invoice",
  "receipt",
  "contract",
  "report"
]
```

**Dictionary Format (With Descriptions):**
```json
"document_types": {
  "invoice": "Commercial document requesting payment for goods or services",
  "receipt": "Proof of payment transaction",
  "contract": "Legal agreement between parties",
  "report": "Formal document presenting information"
}
```

**Default Document Types:**
If not specified, the operator loads 30+ predefined document types from `common/document_classes/`:
- Financial: `invoice`, `receipt`, `bank_statement`, `credit_card_statement`
- Legal: `contract`, `agreement`, `license`
- Identity: `passport`, `driver_license`, `national_id_card`
- Insurance: `insurance_claim`, `acord_form`
- And many more...

#### 8. `confidence_threshold` (Float)
**Type:** Float
**Required:** No
**Default:** `7.0`
**Description:** Minimum confidence score for classification (1-10 scale).

**Valid Values:**
- Range: `1.0` to `10.0`
- Recommended: `7.0` to `8.0` for balanced accuracy

**Examples:**
```json
"confidence_threshold": 7.0
"confidence_threshold": 8.5
```

#### 9. `output_column` (String)
**Type:** String
**Required:** No
**Default:** `"document_type"`
**Description:** Column name for classification result.

**Valid Values:**
- Any valid column name
- Common values: `"document_type"`, `"doc_category"`, `"classification"`

**Examples:**
```json
"output_column": "document_type"
"output_column": "doc_category"
```

#### 10. `include_confidence` (Boolean)
**Type:** Boolean
**Required:** No
**Default:** `true`
**Description:** Include confidence score in output.

**Valid Values:**
- `true` - Adds `{output_column}_confidence` column with scores 1-10
- `false` - No confidence column added

**Examples:**
```json
"include_confidence": true
"include_confidence": false
```

#### 11. `include_reasoning` (Boolean)
**Type:** Boolean
**Required:** No
**Default:** `false`
**Description:** Include reasoning explanation in output.

**Valid Values:**
- `true` - Adds `{output_column}_reasoning` column with LLM's explanation
- `false` - No reasoning column added

**Examples:**
```json
"include_reasoning": true
"include_reasoning": false
```

#### 12. `extract_tables` (Boolean)
**Type:** Boolean
**Required:** No
**Default:** `true`
**Description:** Extract tables from documents during content extraction.

**Valid Values:**
- `true` - Extract and include table content
- `false` - Skip table extraction

**Examples:**
```json
"extract_tables": true
"extract_tables": false
```

#### 13. `extract_images` (Boolean)
**Type:** Boolean
**Required:** No
**Default:** `true`
**Description:** Extract images from documents during content extraction.

**Valid Values:**
- `true` - Extract and include image descriptions
- `false` - Skip image extraction

**Examples:**
```json
"extract_images": true
"extract_images": false
```

#### 14. `max_workers` (Integer)
**Type:** Integer
**Required:** No
**Default:** Auto-calculated based on CPU cores
**Description:** Maximum number of parallel workers for processing.

**Valid Values:**
- Range: `1` to `32`
- Recommended: `4` to `8` for most systems

**Examples:**
```json
"max_workers": 4
"max_workers": 8
```

#### 15. `use_processes` (Boolean)
**Type:** Boolean
**Required:** No
**Default:** `false`
**Description:** Use process-based parallelism instead of threads.

**Valid Values:**
- `true` - Use multiprocessing (better for CPU-intensive tasks)
- `false` - Use threading (lower overhead)

**Examples:**
```json
"use_processes": false
"use_processes": true
```

## Output Features

**The operator adds the following columns to the PyArrow table:**

### 1. `document_type` (String)
**Description:** Classified document type
**Available for Filter:** Yes
**Available for Vector DB:** Yes
**Type:** String

**Example Values:**
- `"invoice"` - Commercial invoice
- `"receipt"` - Payment receipt
- `"contract"` - Legal contract
- `"report"` - Business or technical report
- `"passport"` - Identity document

### 2. `document_type_confidence` (Float) - Optional
**Description:** Confidence score for classification (1-10 scale)
**Available for Filter:** Yes
**Type:** Float
**Enabled By:** `include_confidence: true`

**Example Values:**
- `9.5` - Very high confidence
- `8.0` - High confidence
- `7.0` - Medium confidence (default threshold)
- `5.0` - Low confidence

### 3. `document_type_reasoning` (String) - Optional
**Description:** LLM's explanation for the classification decision
**Available for Filter:** No
**Type:** String
**Enabled By:** `include_reasoning: true`

**Example Values:**
- `"Contains line items, totals, and payment terms typical of invoices"`
- `"Document structure and legal language indicate a contract"`
- `"Receipt format with transaction details and payment confirmation"`

## Configuration Examples

### Example 1: LiteLLM with OpenAI
```json
{
  "id": "classifier-node-1",
  "operator": "document_classifier",
  "config": {
    "provider": "litellm",
    "model_id": "openai/gpt-4o-mini",
    "provider_config": {
      "api_key": "${OPENAI_API_KEY}"
    },
    "document_types": ["invoice", "receipt", "contract", "report"],
    "confidence_threshold": 7.0,
    "include_confidence": true
  }
}
```

### Example 2: LiteLLM with Ollama (OpenAI-Compatible Endpoint)
```json
{
  "id": "classifier-node-2",
  "operator": "document_classifier",
  "config": {
    "provider": "litellm",
    "model_id": "openai/llama3.2:latest",
    "provider_config": {
      "api_key": "ollama",  # pragma: allowlist secret
      "api_base": "http://localhost:11434/v1"
    },
    "document_types": {
      "invoice": "Business invoice with line items and totals",
      "receipt": "Payment receipt or confirmation",
      "contract": "Legal contract or agreement",
      "report": "Business or technical report"
    },
    "confidence_threshold": 7.0,
    "include_confidence": true,
    "include_reasoning": true
  }
}
```

### Example 3: watsonx Classification with Reasoning
```json
{
  "id": "classifier-node-3",
  "operator": "document_classifier",
  "config": {
    "provider": "watsonx",
    "provider_config": {
      "api_base": "https://us-south.ml.cloud.ibm.com",
      "api_key": "${WATSONX_API_KEY}", # pragma: allowlist secret
      "container_kind": "project",
      "container_id": "${WATSONX_PROJECT_ID}",
      "request_timeout": 120
    },
    "model_id": "ibm/granite-3-8b-instruct",
    "document_types": {
      "invoice": "Commercial invoice requesting payment",
      "purchase_order": "Order document from buyer to seller",
      "receipt": "Proof of payment"
    },
    "include_confidence": true,
    "include_reasoning": true,
    "confidence_threshold": 8.0
  }
}
```

## Best Practices

1. **Document Type Selection**: Choose 3-10 distinct document types for best results
2. **Content Length**: Balance between accuracy (more content) and speed (less content)
3. **Confidence Threshold**: Start with 7.0, adjust based on accuracy requirements
4. **Provider Selection**:
   - Use LiteLLM with Ollama (OpenAI-compatible endpoint) for local development and privacy
   - Use LiteLLM with OpenAI/Anthropic for high accuracy in production
   - Use watsonx for enterprise deployments with IBM infrastructure
5. **Error Handling**: Always check confidence scores and handle low-confidence results
6. **Testing**: Test with representative sample documents before production deployment
7. **Model Selection**: Choose models appropriate for your document types and language
8. **Migration from Ollama**: If upgrading from direct Ollama provider, switch to LiteLLM with `api_base: "http://localhost:11434/v1"` and prefix model names with `openai/`

## Complete flow example

tests/sample_test_flows/classification/flow_document_classifier.json
