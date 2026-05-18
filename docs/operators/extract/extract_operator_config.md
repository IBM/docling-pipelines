# Extract Operator - Configuration Reference

## Overview

The Extract Operator is a unified extraction operator that provides text and entity extraction from documents using multiple strategies. It uses hexagonal architecture to support various extraction modes through specialized adapters.

- **Operator Name:** `extract_operator`
- **Category**: Extract
- **Short Name**: `extract_operator`

## Supported Extraction Modes

### Text Extraction Modes
- **docling_library**: Local Docling extraction with tables, images, and optional VLM support
- **docling_serve**: Remote extraction via Docling Serve API

### Entity Extraction Modes
- **ollama**: LLM-based entity extraction using Ollama models
- **docling**: Template-based entity extraction using Docling templates
- **litellm**: Multi-provider LLM extraction (OpenAI, Anthropic, Cohere, etc.)
- **none**: No entity extraction (default)

## Configuration Parameters

### Core Parameters

#### 1. `text_extraction_mode` (String)
**Type:** String  
**Required:** Yes  
**Default:** `"docling_library"`  
**Description:** Text extraction strategy to use.

**Valid Values:** `docling_library`, `docling_serve`

**Examples:**
```json
"text_extraction_mode": "docling_library"
```

```json
"text_extraction_mode": "docling_serve"
```

#### 2. `entity_extraction_mode` (String)
**Type:** String  
**Required:** No  
**Default:** `"none"`  
**Description:** Entity extraction strategy. Set to enable structured data extraction from documents.

**Valid Values:** `ollama`, `docling`, `litellm`, `none`

**Examples:**
```json
"entity_extraction_mode": "ollama"
```

```json
"entity_extraction_mode": "none"
```

#### 3. `doc_column` (String)
**Type:** String
**Required:** No
**Default:** `"content"`
**Description:** Name of the column to store extracted document content.

**Examples:**
```json
"doc_column": "content"
```

#### 4. `output_column` (String)
**Type:** String
**Required:** No
**Default:** `"entities"`
**Description:** Name of the column to store extracted entities (entity extraction only).

**Examples:**
```json
"output_column": "entities"
```

#### 5. `extract_tables` (Boolean)
**Type:** Boolean  
**Required:** No  
**Default:** `true`  
**Description:** Whether to extract tables from documents.

**Examples:**
```json
"extract_tables": true
```

#### 5. `extract_images` (Boolean)
**Type:** Boolean  
**Required:** No  
**Default:** `true`  
**Description:** Whether to extract images from documents.

**Examples:**
```json
"extract_images": false
```

#### 6. `max_workers` (Integer)
**Type:** Integer  
**Required:** No  
**Default:** Auto (CPU-based)  
**Description:** Maximum number of parallel workers for extraction. Auto-detects optimal value based on CPU count.

**Examples:**
```json
"max_workers": 4
```

#### 7. `use_processes` (Boolean)
**Type:** Boolean  
**Required:** No  
**Default:** `false`  
**Description:** Use ProcessPoolExecutor instead of ThreadPoolExecutor for CPU-intensive tasks.

**Examples:**
```json
"use_processes": true
```

### Entity Extraction Parameters

#### 8. `entity_model_name` (String)
**Type:** String  
**Required:** No  
**Default:** `"llama3.2"`  
**Description:** LLM model name for entity extraction (ollama: 'llama3.2', litellm: 'gpt-3.5-turbo').

**Examples:**
```json
"entity_model_name": "llama3.2"
```

```json
"entity_model_name": "gpt-4"
```

#### 9. `entity_temperature` (Float)
**Type:** Float  
**Required:** No  
**Default:** `0.0`  
**Description:** Sampling temperature for entity extraction LLM (0.0-1.0). Lower values are more deterministic.

**Examples:**
```json
"entity_temperature": 0.0
```

#### 10. `entity_max_tokens` (Integer)
**Type:** Integer  
**Required:** No  
**Default:** `4096`  
**Description:** Maximum tokens for entity extraction LLM response.

**Examples:**
```json
"entity_max_tokens": 8192
```

#### 11. `entity_max_doc_chars` (Integer)
**Type:** Integer  
**Required:** No  
**Default:** `8000`  
**Description:** Maximum characters to pass for entity extraction. Documents longer than this will be truncated.

**Examples:**
```json
"entity_max_doc_chars": 10000
```

#### 12. `entity_provider_config` (JSON)
**Type:** JSON Object  
**Required:** No  
**Default:** `null`  
**Description:** Provider-specific configuration for entity extraction (e.g., API keys, base URLs).

**Examples:**
```json
"entity_provider_config": {
  "api_key": "sk-...", # pragma: allowlist secret
  "api_base": "https://api.openai.com/v1"
}
```

#### 13. `custom_schema` (JSON)
**Type:** JSON Object  
**Required:** No  
**Default:** None
**Description:** Schema dictionary for structured extraction. Defines the structure of entities to extract.

**Examples:**
```json
"custom_schema": {
  "invoice_number": "string",
  "date": "string",
  "total_amount": "number"
}
```

#### 14. `expand_extracted_data` (Boolean)
**Type:** Boolean  
**Required:** No  
**Default:** `false`  
**Description:** Whether to expand entity data JSON into individual columns (applies to entity extraction only).

**Examples:**
```json
"expand_extracted_data": true
```

### VLM (Vision-Language Model) Parameters

#### 15. `use_vlm_pipeline` (Boolean)
**Type:** Boolean  
**Required:** No  
**Default:** `false`  
**Description:** Enable Vision-Language Model for enhanced extraction (docling_library mode only).

**Examples:**
```json
"use_vlm_pipeline": true
```

#### 16. `vlm_preset` (String)
**Type:** String  
**Required:** No  
**Default:** `"granite_docling"`  
**Description:** VLM preset name for document processing (when use_vlm_pipeline=true).

**Examples:**
```json
"vlm_preset": "granite_docling"
```

#### 17. `vlm_engine_type` (String)
**Type:** String  
**Required:** No  
**Default:** None
**Description:** VLM engine type: 'transformers' (local, default), 'mlx' (macOS optimized), or 'api' (remote API).

**Valid Values:** `transformers`, `mlx`, `api`

**Examples:**
```json
"vlm_engine_type": "transformers"
```

#### 18. `vlm_provider_config` (JSON)
**Type:** JSON Object  
**Required:** No  
**Default:** `null`  
**Description:** Provider-specific configuration for VLM. Required keys vary by engine type.

**Watsonx Example:**
```json
"vlm_provider_config": {
  "api_key": "...", # pragma: allowlist secret
  "container_id": "...",
  "model_id": "...",
  "api_base_url": "https://..."
}
```

**Ollama/LMStudio Example:**
```json
"vlm_provider_config": {
  "api_base_url": "http://localhost:11434"
}
```

**OpenAI Example:**
```json
"vlm_provider_config": {
  "api_key": "sk-...", # pragma: allowlist secret
  "api_base_url": "https://api.openai.com/v1"
}
```

### Docling Serve Parameters

#### 19. `docling_serve_base_url` (String)
**Type:** String  
**Required:** No  
**Default:** `"http://localhost:5001"`  
**Description:** Base URL for the docling-serve service (docling_serve mode only).

**Examples:**
```json
"docling_serve_base_url": "http://docling-serve:5001"
```

#### 20. `docling_serve_api_key` (String)
**Type:** String  
**Required:** No  
**Default:** None
**Description:** Optional API key sent as X-API-KEY when calling docling-serve.

**Examples:**
```json
"docling_serve_api_key": "your-api-key" # pragma: allowlist secret
```

#### 21. `docling_serve_timeout` (Integer)
**Type:** Integer  
**Required:** No  
**Default:** `300`  
**Description:** Request timeout in seconds for docling-serve operations.

**Examples:**
```json
"docling_serve_timeout": 600
```

#### 22. `docling_serve_poll_interval` (Integer)
**Type:** Integer  
**Required:** No  
**Default:** `2`  
**Description:** Polling interval in seconds when waiting for docling-serve task completion.

**Examples:**
```json
"docling_serve_poll_interval": 5
```

#### 23. `docling_serve_max_retries` (Integer)
**Type:** Integer  
**Required:** No  
**Default:** `3`  
**Description:** Maximum retry attempts for docling-serve status polling.

**Examples:**
```json
"docling_serve_max_retries": 5
```

#### 24. `docling_serve_do_ocr` (Boolean)
**Type:** Boolean  
**Required:** No  
**Default:** `true`  
**Description:** Whether OCR should be enabled when processing documents with docling-serve.

**Examples:**
```json
"docling_serve_do_ocr": true
```

#### 25. `docling_serve_ocr_engine` (String)
**Type:** String  
**Required:** No  
**Default:** `"easyocr"`  
**Description:** OCR engine name passed to docling-serve.

**Examples:**
```json
"docling_serve_ocr_engine": "tesseract"
```

#### 26. `docling_serve_ocr_languages` (JSON)
**Type:** JSON Array  
**Required:** No  
**Default:** None
**Description:** List of OCR languages passed to docling-serve.

**Examples:**
```json
"docling_serve_ocr_languages": ["en", "es", "fr"]
```

#### 27. `docling_serve_pdf_backend` (String)
**Type:** String  
**Required:** No  
**Default:** `"dlparse_v2"`  
**Description:** PDF backend to use in docling-serve.

**Examples:**
```json
"docling_serve_pdf_backend": "dlparse_v2"
```

#### 28. `docling_serve_table_mode` (String)
**Type:** String  
**Required:** No  
**Default:** `"fast"`  
**Description:** Table structure extraction mode for docling-serve.

**Valid Values:** `fast`, `accurate`

**Examples:**
```json
"docling_serve_table_mode": "accurate"
```

#### 29. `docling_serve_image_export_mode` (String)
**Type:** String  
**Required:** No  
**Default:** `"placeholder"`  
**Description:** Image export mode passed to docling-serve.

**Examples:**
```json
"docling_serve_image_export_mode": "embedded"
```

## Output Features

### `content` (String)
**Type:** String  
**Description:** The markdown content extracted from the document  
**Available for Filter:** Yes  
**Available for Vector DB:** Yes  
**Tags:** `mandatory`

### `doc_id_hash` (String)
**Type:** String  
**Description:** Hash ID of the document row  
**Available for Vector DB:** Yes  
**Mandatory for Vector DB:** Yes  
**Is Primary:** Yes  
**Tags:** `mandatory`, `primary`

### `entities` (String)
**Type:** String
**Description:** Extracted entities from document content (when entity extraction is enabled)
**Available for Filter:** Yes
**Available for Vector DB:** Yes

### `tables` (String)
**Type:** String
**Description:** Extracted tables from document (when `extract_tables` is enabled)
**Available for Filter:** Yes
**Available for Vector DB:** Yes
**Note:** Added as serialized JSON when tables are extracted from documents

### `images` (String)
**Type:** String
**Description:** Extracted images from document (when `extract_images` is enabled)
**Available for Filter:** Yes
**Available for Vector DB:** Yes
**Note:** Added as serialized JSON when images are extracted from documents

### `entity_{key}` (Dynamic Columns)
**Type:** String
**Description:** Individual entity columns (when `expand_extracted_data` is enabled)
**Available for Filter:** Yes
**Available for Vector DB:** Yes
**Note:** When `expand_extracted_data=true`, each entity key becomes a separate column with format `entity_{key}`. For example, if entities contain `{"name": "John", "age": "30"}`, two columns are created: `entity_name` and `entity_age`. These columns are dynamically generated at runtime based on the actual entity keys found in the data.

## Configuration Examples

### Example 1: Basic Text Extraction
```json
{
  "id": "3e9b7c2a-6f41-4d8e-9a5c-2b7d1e6f8c0a",
  "operator": "extract_operator",
  "config": {
    "text_extraction_mode": "docling_library",
    "entity_extraction_mode": "none",
    "extract_tables": true,
    "extract_images": false,
    "max_workers": 4
  }
}
```

### Example 2: Text + Entity Extraction with Ollama
```json
{
  "id": "3e9b7c2a-6f41-4d8e-9a5c-2b7d1e6f8c0a",
  "operator": "extract_operator",
  "config": {
    "text_extraction_mode": "docling_library",
    "entity_extraction_mode": "ollama",
    "entity_model_name": "llama3.2",
    "entity_temperature": 0.0,
    "custom_schema": {
      "person_name": "string",
      "organization": "string",
      "date": "string"
    },
    "expand_extracted_data": true
  }
}
```

### Example 3: VLM-Enhanced Extraction
```json
{
  "id": "3e9b7c2a-6f41-4d8e-9a5c-2b7d1e6f8c0a",
  "operator": "extract_operator",
  "config": {
    "text_extraction_mode": "docling_library",
    "use_vlm_pipeline": true,
    "vlm_preset": "granite_docling",
    "vlm_engine_type": "transformers",
    "extract_tables": true,
    "extract_images": true,
    "max_workers": 2
  }
}
```

### Example 4: Docling Serve Extraction
```json
{
  "id": "3e9b7c2a-6f41-4d8e-9a5c-2b7d1e6f8c0a",
  "operator": "extract_operator",
  "config": {
    "text_extraction_mode": "docling_serve",
    "docling_serve_base_url": "http://docling-serve:5001",
    "docling_serve_timeout": 300,
    "docling_serve_do_ocr": true,
    "docling_serve_ocr_engine": "easyocr",
    "docling_serve_table_mode": "accurate"
  }
}
```

### Example 5: LiteLLM Entity Extraction
```json
{
  "id": "3e9b7c2a-6f41-4d8e-9a5c-2b7d1e6f8c0a",
  "operator": "extract_operator",
  "config": {
    "text_extraction_mode": "docling_library",
    "entity_extraction_mode": "litellm",
    "entity_model_name": "gpt-4",
    "entity_provider_config": {
      "api_key": "sk-...", # pragma: allowlist secret
      "api_base": "https://api.openai.com/v1"
    },
    "custom_schema": {
      "invoice_number": "string",
      "total_amount": "number",
      "vendor_name": "string"
    }
  }
}
```

## Best Practices

1. **Mode Selection**: Use `docling_library` for local processing, `docling_serve` for distributed workloads
2. **Worker Count**: Start with default auto-detection, adjust based on CPU/memory constraints
3. **Entity Extraction**: Only enable when needed - adds processing time
4. **VLM Usage**: Use VLM for complex documents with charts, diagrams, or handwriting
5. **Table Extraction**: Enable for documents with structured data
6. **Custom Schemas**: Define clear schemas for consistent entity extraction
7. **Temperature**: Use 0.0 for deterministic entity extraction, higher for creative tasks

## Complete Flow Example

- [Sample Flow](../../../tests/sample_test_flows/extract/flow_extract_complete.json)
- [Sample Flow](../../../tests/sample_test_flows/invoice_processing/flow_invoice_entities.json)
