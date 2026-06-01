# Extract Operator - Configuration Reference

## Overview

The Extract Operator is a unified extraction operator that provides text and entity extraction from documents using multiple strategies. It uses hexagonal architecture (ports and adapters pattern) to support various extraction modes through specialized adapters.

**Architecture Layers:**
- **Domain Layer**: `EntityExtractionService` for business logic
- **Port Layer**: `TextExtractionPort` and `EntityExtractionPort` interfaces
- **Adapter Layer**: Concrete implementations (DoclingAdapter, DoclingServeAdapter, LLMEntityAdapter, DoclingEntityAdapter)
- **Factory Layer**: Adapter creation based on configuration

- **Operator Name:** `extract_operator`
- **Category**: Extract
- **Short Name**: `extract_operator`

## Supported Extraction Modes

### Text Extraction Modes
- **docling_library**: Local Docling extraction with tables, images, and optional VLM support
- **docling_serve**: Remote extraction via Docling Serve API

### Entity Extraction Modes
- **litellm**: Multi-provider LLM extraction (OpenAI, Anthropic, Cohere, etc.). Use this mode to access Ollama models with the `openai/` prefix (e.g., `openai/llama3.2`)
- **watsonx**: IBM watsonx.ai LLM-based entity extraction
- **docling**: Template-based entity extraction using Docling templates
- **none**: No entity extraction (default)

## Configuration Parameters

### Core Parameters

#### 1. `text_extraction` (Object)
**Type:** JSON Object
**Required:** No
**Default:** `{}`
**Description:** Text extraction configuration object containing all text extraction parameters.

**Sub-parameters:**
- `provider` (String): Text extraction strategy (`docling_library`, `docling_serve`)
- `doc_column` (String): Column name for extracted content
- `additional_formats` (Array): Additional output formats
- `extract_tables` (Boolean): Extract tables from documents
- `extract_images` (Boolean): Extract images from documents
- `provider_config` (Object): Provider-specific configuration only
- VLM parameters in `text_extraction.provider_config.vlm_pipeline` (for docling_library mode)
- Docling Serve parameters in `text_extraction.provider_config` (for docling_serve mode)

**Examples:**
```json
"text_extraction": {
  "provider": "docling_library",
  "doc_column": "content",
  "provider_config": {
    "extract_tables": true,
    "extract_images": true
  }
}
```

#### 2. `entity_extraction` (Object)
**Type:** JSON Object
**Required:** No
**Default:** `{}`
**Description:** Entity extraction configuration object containing all entity extraction parameters.

**Sub-parameters:**
- `provider` (String): Entity extraction strategy (`litellm`, `watsonx`, `docling`, `none`)
- `output_column` (String): Column name for extracted entities
- `max_doc_chars` (Integer): Maximum document characters passed to entity extraction
- `custom_schema` (Object): Schema for structured extraction
- `expand_extracted_data` (Boolean): Expand entities into individual columns
- `provider_config` (Object): Provider-specific configuration only, including `model_id`

**Note:** To use Ollama models, set `provider` to `"litellm"` and use the `openai/` prefix in `provider_config.model_id` (e.g., `"openai/llama3.2"`). Configure `provider_config.api_base` with `"http://localhost:11434/v1"`.

**Examples:**
```json
"entity_extraction": {
  "provider": "litellm",
  "provider_config": {
    "model_id": "openai/llama3.2",
    "api_base": "http://localhost:11434/v1"
  },
  "output_column": "entities",
  "max_doc_chars": 8000,
  "custom_schema": {
    "invoice_number": "string"
  },
  "expand_extracted_data": true
}
```

#### 3. `text_extraction.doc_column` (String)
**Type:** String
**Required:** No
**Default:** `"content"`
**Description:** Name of the column to store extracted document content.

**Examples:**
```json
"text_extraction": {
  "doc_column": "content"
}
```

#### 4. `entity_extraction.output_column` (String)
**Type:** String
**Required:** No
**Default:** `"entities"`
**Description:** Name of the column to store extracted entities.

**Examples:**
```json
"entity_extraction": {
  "output_column": "entities"
}
```

#### 5. `text_extraction.provider_config.extract_tables` (Boolean)
**Type:** Boolean
**Required:** No
**Default:** `true`
**Description:** Whether to extract tables from documents.

**Examples:**
```json
"text_extraction": {
  "provider_config": {
    "extract_tables": true
  }
}
```

#### 6. `text_extraction.provider_config.extract_images` (Boolean)
**Type:** Boolean
**Required:** No
**Default:** `true`
**Description:** Whether to extract images from documents.

**Examples:**
```json
"text_extraction": {
  "provider_config": {
    "extract_images": false
  }
}
```

#### 7. `text_extraction.provider_config.additional_formats` (Array)
**Type:** Array of strings
**Required:** No
**Default:** `[]` (empty array - markdown only)
**Description:** Additional output formats to generate beyond the mandatory markdown format. Each format creates a separate column in the output table.

**Valid Values:** `"html"`, `"json"`, `"text"`, `"doctags"`

**Examples:**
```json
"text_extraction": {
  "provider_config": {
    "additional_formats": ["html", "json"]
  }
}
```

```json
"text_extraction": {
  "provider_config": {
    "additional_formats": ["html", "json", "text", "doctags"]
  }
}
```

**Important Notes:**
- Markdown format is ALWAYS generated in the `content` column regardless of this parameter (column name can be customized via `doc_column` parameter)
- This parameter specifies which formats to generate **in addition to** markdown
- Each additional format creates a corresponding column: `content_html`, `content_json`, `content_text`, `content_doctags`
- **Additional formats are only generated for documents processed through Docling** (docling_library or docling_serve modes). Plain text files (.txt, .md) are read directly and will not generate these additional format columns.
- Only request formats you actually need to minimize memory usage and storage

#### 8. `max_workers` (Integer)
**Type:** Integer  
**Required:** No  
**Default:** Auto (CPU-based)  
**Description:** Maximum number of parallel workers for extraction. Auto-detects optimal value based on CPU count.

**Examples:**
```json
"max_workers": 4
```

#### 9. `use_processes` (Boolean)
**Type:** Boolean  
**Required:** No  
**Default:** `false`  
**Description:** Use ProcessPoolExecutor instead of ThreadPoolExecutor for CPU-intensive tasks.

**Examples:**
```json
"use_processes": true
```

### Entity Extraction Parameters

#### 10. `entity_extraction.provider_config` (Object)
**Type:** JSON Object
**Required:** No
**Default:** `{}`
**Description:** Provider-specific configuration for entity extraction only, including model_id and authentication. Operator-level keys such as `output_column`, `max_doc_chars`, `custom_schema`, and `expand_extracted_data` must be defined directly under `entity_extraction`, not inside `provider_config`.

**For LiteLLM:**
- `model_id` (String, Required): Model identifier. **Must include provider prefix when using LiteLLM** (e.g., `"openai/gpt-4"`, `"openai/llama3.2"` for Ollama, `"anthropic/claude-3-opus"`)
- `api_key` (String, Optional): API key for authentication
- `api_base` (String, Optional): Custom API endpoint (e.g., `"http://localhost:11434/v1"` for Ollama)
- `temperature` (Float, Optional): Sampling temperature (default: 0.0)
- `max_tokens` (Integer, Optional): Maximum response tokens (default: 4096)
- `stream` (Boolean, Optional): Enable HTTP chunked transfer encoding for streaming responses (default: false). Recommended for remote vLLM clusters processing large documents to prevent connection drops.
- `timeout` (Integer, Optional): HTTP client read timeout in seconds (default: 300). Set to 1800 (30 minutes) for large documents requiring extended generation time.

**For WatsonX:**
- `model_id` (String, Required): WatsonX model identifier
- `api_key` (String, Required): IBM Cloud API key
- `api_base` (String, Optional): WatsonX API endpoint
- `container_id` (String, Required): Project or space ID
- `container_kind` (String, Optional): Container type (default: "project")
- `temperature` (Float, Optional): Sampling temperature (default: 0.0)
- `max_tokens` (Integer, Optional): Maximum response tokens (default: 2000)

#### 11. `entity_extraction.custom_schema` (JSON)
**Type:** JSON Object  
**Required:** No  
**Default:** None
**Description:** Schema dictionary for structured extraction. Defines the structure of entities to extract.

**Examples:**
```json
"entity_extraction": {
  "custom_schema": {
    "invoice_number": "string",
    "date": "string",
    "total_amount": "number"
  }
}
```

#### 12. `entity_extraction.expand_extracted_data` (Boolean)
**Type:** Boolean  
**Required:** No  
**Default:** `false`  
**Description:** Whether to expand entity data JSON into individual columns (applies to entity extraction only).

**Examples:**
```json
"entity_extraction": {
  "expand_extracted_data": true
}
```

### VLM (Vision-Language Model) Parameters

#### 13. `text_extraction.provider_config.vlm_pipeline` (Object)
**Type:** JSON Object
**Required:** No
**Default:** `null`
**Description:** Provider-specific VLM pipeline configuration for enhanced extraction (docling_library mode only). When provided, enables Vision-Language Model processing.

**Sub-parameters:**
- `preset` (String): VLM preset name (`fast`, `accurate`, or custom)
- `engine` (String): VLM engine (`ollama`, `transformers`, `mlx`, `openai`, etc.)
- `engine_options` (Object): Engine-specific configuration

**Examples:**
```json
"text_extraction": {
  "vlm_pipeline": {
    "preset": "fast",
    "engine": "ollama",
    "engine_options": {
      "api_base": "http://localhost:11434",
      "model_id": "llama3.2-vision"
    }
  }
}
```

**Transformers Example:**
```json
"vlm_pipeline": {
  "preset": "accurate",
  "engine": "transformers",
  "engine_options": {
    "model_id": "microsoft/Florence-2-large"
  }
}
```

**OpenAI Example:**
```json
"vlm_pipeline": {
  "preset": "fast",
  "engine": "openai",
  "engine_options": {
    "api_key": "sk-...", # pragma: allowlist secret
    "api_base": "https://api.openai.com/v1",
    "model_id": "gpt-4-vision-preview"
  }
}
```

### Docling Serve Parameters

All Docling Serve parameters should be nested under `text_extraction.provider_config` when using `provider: "docling_serve"`.

#### 14. `text_extraction.provider_config.base_url` (String)
**Type:** String
**Required:** No
**Default:** `"http://localhost:5001"`
**Description:** Base URL for the docling-serve service (docling_serve mode only).

**Examples:**
```json
"text_extraction": {
  "provider": "docling_serve",
  "provider_config": {
    "base_url": "http://docling-serve:5001"
  }
}
```

#### 15. `text_extraction.provider_config.api_key` (String)
**Type:** String
**Required:** No
**Default:** None
**Description:** Optional API key sent as X-API-KEY when calling docling-serve.

**Examples:**
```json
"text_extraction": {
  "provider": "docling_serve",
  "provider_config": {
    "api_key": "your-api-key" # pragma: allowlist secret
  }
}
```

#### 16. `text_extraction.provider_config.timeout` (Integer)
**Type:** Integer
**Required:** No
**Default:** `300`
**Description:** Request timeout in seconds for docling-serve operations.

**Examples:**
```json
"text_extraction": {
  "provider": "docling_serve",
  "provider_config": {
    "timeout": 600
  }
}
```

#### 17. `text_extraction.provider_config.poll_interval` (Integer)
**Type:** Integer
**Required:** No
**Default:** `2`
**Description:** Polling interval in seconds when waiting for docling-serve task completion.

**Examples:**
```json
"text_extraction": {
  "provider": "docling_serve",
  "provider_config": {
    "poll_interval": 5
  }
}
```

#### 18. `text_extraction.provider_config.max_retries` (Integer)
**Type:** Integer
**Required:** No
**Default:** `3`
**Description:** Maximum retry attempts for docling-serve status polling.

**Examples:**
```json
"text_extraction": {
  "provider": "docling_serve",
  "provider_config": {
    "max_retries": 5
  }
}
```

#### 19. `text_extraction.provider_config.do_ocr` (Boolean)
**Type:** Boolean
**Required:** No
**Default:** `true`
**Description:** Whether OCR should be enabled when processing documents with docling-serve.

**Examples:**
```json
"text_extraction": {
  "provider": "docling_serve",
  "provider_config": {
    "do_ocr": true
  }
}
```

#### 25. `text_extraction.provider_config.ocr_engine` (String)
**Type:** String
**Required:** No
**Default:** `"easyocr"`
**Description:** OCR engine name passed to docling-serve.

**Examples:**
```json
"text_extraction": {
  "provider": "docling_serve",
  "provider_config": {
    "ocr_engine": "tesseract"
  }
}
```

#### 26. `text_extraction.provider_config.ocr_languages` (JSON)
**Type:** JSON Array
**Required:** No
**Default:** None
**Description:** List of OCR languages passed to docling-serve.

**Examples:**
```json
"text_extraction": {
  "provider": "docling_serve",
  "provider_config": {
    "ocr_languages": ["en", "es", "fr"]
  }
}
```

#### 27. `text_extraction.provider_config.pdf_backend` (String)
**Type:** String
**Required:** No
**Default:** `"dlparse_v2"`
**Description:** PDF backend to use in docling-serve.

**Examples:**
```json
"text_extraction": {
  "provider": "docling_serve",
  "provider_config": {
    "pdf_backend": "dlparse_v2"
  }
}
```

#### 28. `text_extraction.provider_config.table_mode` (String)
**Type:** String
**Required:** No
**Default:** `"fast"`
**Description:** Table structure extraction mode for docling-serve.

**Valid Values:** `fast`, `accurate`

**Examples:**
```json
"text_extraction": {
  "provider": "docling_serve",
  "provider_config": {
    "table_mode": "accurate"
  }
}
```

#### 29. `text_extraction.provider_config.image_export_mode` (String)
**Type:** String
**Required:** No
**Default:** `"placeholder"`
**Description:** Image export mode passed to docling-serve.

**Examples:**
```json
"text_extraction": {
  "provider": "docling_serve",
  "provider_config": {
    "image_export_mode": "embedded"
  }
}
```

## Output Features

### `content` (String)
**Type:** String
**Description:** The markdown content extracted from the document (always generated). Column name can be customized via `doc_column` parameter (default: "content")
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

### `content_html` (String)
**Type:** String
**Description:** HTML format of extracted content (when `additional_formats` includes "html")
**Available for Filter:** Yes
**Available for Vector DB:** Yes
**Note:** Only present when "html" is specified in `additional_formats` parameter

### `content_json` (String)
**Type:** String
**Description:** JSON structured format of extracted content (when `additional_formats` includes "json")
**Available for Filter:** Yes
**Available for Vector DB:** Yes
**Note:** Only present when "json" is specified in `additional_formats` parameter

### `content_text` (String)
**Type:** String
**Description:** Plain text format of extracted content (when `additional_formats` includes "text")
**Available for Filter:** Yes
**Available for Vector DB:** Yes
**Note:** Only present when "text" is specified in `additional_formats` parameter

### `content_doctags` (String)
**Type:** String
**Description:** Docling's native DocTags format (when `additional_formats` includes "doctags")
**Available for Filter:** Yes
**Available for Vector DB:** Yes
**Note:** Only present when "doctags" is specified in `additional_formats` parameter

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
    "text_extraction": {
      "provider": "docling_library",
      "provider_config": {
        "extract_tables": true,
        "extract_images": false
      }
    },
    "entity_extraction": {
      "provider": "none"
    },
    "max_workers": 4
  }
}
```

### Example 2: Text + Entity Extraction with Ollama (via LiteLLM)
```json
{
  "id": "3e9b7c2a-6f41-4d8e-9a5c-2b7d1e6f8c0a",
  "operator": "extract_operator",
  "config": {
    "text_extraction": {
      "provider": "docling_library"
    },
    "entity_extraction": {
      "provider": "litellm",
      "provider_config": {
        "model_id": "openai/llama3.2",
        "api_base": "http://localhost:11434/v1",
        "temperature": 0.0
      },
      "custom_schema": {
        "person_name": "string",
        "organization": "string",
        "date": "string"
      },
      "expand_extracted_data": true
    }
  }
}
```

### Example 3: VLM-Enhanced Extraction
```json
{
  "id": "3e9b7c2a-6f41-4d8e-9a5c-2b7d1e6f8c0a",
  "operator": "extract_operator",
  "config": {
    "text_extraction": {
      "provider": "docling_library",
      "provider_config": {
        "vlm_pipeline": {
          "preset": "fast",
          "engine": "ollama",
          "engine_options": {
            "api_base": "http://localhost:11434",
            "model_id": "llama3.2-vision"
          }
        },
        "extract_tables": true,
        "extract_images": true
      }
    },
    "entity_extraction": {
      "provider": "none"
    },
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
    "text_extraction": {
      "provider": "docling_serve",
      "provider_config": {
        "base_url": "http://docling-serve:5001",
        "timeout": 300,
        "do_ocr": true,
        "ocr_engine": "easyocr",
        "table_mode": "accurate"
      }
    },
    "entity_extraction": {
      "provider": "none"
    }
  }
}
```

### Example 5: Multi-Format Output
```json
{
  "id": "3e9b7c2a-6f41-4d8e-9a5c-2b7d1e6f8c0a",
  "operator": "extract_operator",
  "config": {
    "text_extraction": {
      "provider": "docling_library",
      "provider_config": {
        "additional_formats": ["html", "json", "text"],
        "extract_tables": true,
        "extract_images": true
      }
    },
    "entity_extraction": {
      "provider": "none"
    }
  }
}
```
**Output columns**: `content` (markdown), `content_html`, `content_json`, `content_text`, `tables`, `images`

### Example 6: LiteLLM Entity Extraction with OpenAI
```json
{
  "id": "3e9b7c2a-6f41-4d8e-9a5c-2b7d1e6f8c0a",
  "operator": "extract_operator",
  "config": {
    "text_extraction": {
      "provider": "docling_library"
    },
    "entity_extraction": {
      "provider": "litellm",
      "provider_config": {
        "model_id": "openai/gpt-4",
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
}
```

### Example 7: LiteLLM Entity Extraction with Remote vLLM (Streaming)
```json
{
  "id": "3e9b7c2a-6f41-4d8e-9a5c-2b7d1e6f8c0a",
  "operator": "extract_operator",
  "config": {
    "text_extraction": {
      "provider": "docling_library"
    },
    "entity_extraction": {
      "provider": "litellm",
      "provider_config": {
        "model_id": "huggingface/meta-llama/Llama-3.1-70B-Instruct",
        "api_key": "YOUR_API_KEY",  # pragma: allowlist secret
        "api_base": "https://your-vllm-route/v1",
        "stream": true,
        "timeout": 1800
      },
      "custom_schema": {
        "invoice_number": "string",
        "total_amount": "number",
        "vendor_name": "string",
        "invoice_date": "string"
      },
      "expand_extracted_data": true
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
