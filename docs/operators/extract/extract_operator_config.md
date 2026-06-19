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

## Supported File Extensions

The ExtractOperator validates file extensions before processing to ensure compatibility with the selected extraction mode. Files with unsupported extensions are automatically skipped and logged.

### Text Extraction Modes

#### Docling Library (`docling_library`)
**Base Document Formats:**
- PDF: `.pdf`
- Office Documents: `.docx`, `.pptx`, `.xlsx`
- Images: `.png`, `.jpg`, `.jpeg`, `.tiff`, `.bmp`
- HTML: `.html`, `.htm`
- Markdown: `.md`
- AsciiDoc: `.asciidoc`, `.adoc`
- Plain Text: `.txt`

**Audio/Video Formats (requires ASR dependencies):**
- Audio: `.wav`, `.mp3`, `.m4a`, `.aac`, `.ogg`, `.flac`
- Video: `.mp4`, `.avi`, `.mov`

**Note:** Audio and video formats require ASR (Automatic Speech Recognition) dependencies to be installed. If ASR dependencies are not available, these formats will be skipped. Additionally, M4A, AAC, OGG, FLAC, and all video formats require `ffmpeg` to be installed on the system.

#### Docling Serve (`docling_serve`)
**Supported Formats:**
- PDF: `.pdf`
- Office Documents: `.docx`, `.pptx`, `.xlsx`
- Images: `.png`, `.jpg`, `.jpeg`, `.tiff`, `.bmp`
- HTML: `.html`, `.htm`
- Markdown: `.md`
- AsciiDoc: `.asciidoc`, `.adoc`
- Plain Text: `.txt`

**Note:** Docling Serve does NOT support audio or video formats. Only the Docling Library mode supports audio/video processing via ASR.

### Entity Extraction Mode

#### Docling Entity Extraction (`docling`)
**Supported Formats:**
- PDF: `.pdf`
- Office Documents: `.docx`, `.pptx`
- HTML: `.html`
- Images: `.png`, `.jpg`, `.jpeg`, `.tiff`, `.tif`, `.bmp`, `.gif`, `.jfif`

**Note:** Docling entity extraction uses template-based extraction and supports a subset of formats compared to text extraction modes. Not supported: Excel (`.xlsx`), plain text (`.txt`), Markdown (`.md`), and WebP (`.webp`) files.

### Extension Validation Behavior

- **Automatic Skipping**: Files with unsupported extensions are automatically skipped during processing
- **Metadata Tracking**: Skipped files are recorded in the `skipped_docs` metadata with reason "unsupported_extension"
- **No Errors**: Unsupported files do not cause pipeline failures - they are silently skipped with logging
- **Mode-Specific**: Extension validation is performed based on the configured text extraction mode
- **ASR Detection**: For Docling Library mode, audio/video support is automatically detected based on ASR dependency availability

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
- `provider_config` (Object): Provider-specific configuration only
- VLM parameters in `text_extraction.provider_config.vlm_pipeline` (for docling_library mode)
- Docling Serve parameters in `text_extraction.provider_config` (for docling_serve mode)

**Examples:**
```json
"text_extraction": {
  "provider": "docling_library",
  "doc_column": "content",
  "provider_config": {
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

#### 5. `text_extraction.provider_config.additional_formats` (Array)
**Type:** Array of strings  
**Required:** No  
**Default:** `[]` (empty array - markdown only)  
**Description:** Additional output formats to generate beyond the mandatory markdown format. Each format creates a separate column in the output table.  

**Valid Values:** `"html"`, `"json"`, `"text"`, `"doctags"`, `"doclang"`

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
    "additional_formats": ["html", "json", "text", "doctags", "doclang"]
  }
}
```

**Important Notes:**
- Markdown format is ALWAYS generated in the `content` column regardless of this parameter (column name can be customized via `doc_column` parameter)
- This parameter specifies which formats to generate **in addition to** markdown
- Each additional format creates a corresponding column: `content_html`, `content_json`, `content_text`, `content_doctags`, `content_doclang`
- **Additional formats are only generated for documents processed through Docling** (docling_library or docling_serve modes). Plain text files (.txt, .md) are read directly and will not generate these additional format columns.
- Only request formats you actually need to minimize memory usage and storage

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

#### 8. `entity_extraction.provider_config` (Object)
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

**For Docling:**
- `vlm_pipeline` (Object, Optional): Custom VLM model configuration for Docling entity extraction
  - `model_type` (String, Required): Model type - must be `"inline"` (API model not supported by DocumentExtractor)
  - `inline_model` (Object, Required when model_type is "inline"): Inline model configuration
    - `repo_id` (String, Required): HuggingFace model repository ID (e.g., `"microsoft/Florence-2-large"`)
    - `inference_framework` (String, Optional): Inference framework (default: `"transformers"`)
    - `scale` (Float, Optional): Image scaling factor (default: 2.0)
    - `temperature` (Float, Optional): Sampling temperature (default: 0.0)
    - `max_new_tokens` (Integer, Optional): Maximum tokens to generate (default: 4096)
    - `load_in_8bit` (Boolean, Optional): Load model in 8-bit precision (default: true)
    - `torch_dtype` (String, Optional): PyTorch data type (default: `"bfloat16"`)
    - `prompt` (String, Optional): Custom prompt template (default: empty string)
    - `response_format` (String, Optional): Response format (default: `"markdown"`)

**Note:** Docling entity extraction uses template-based extraction with Docling's DocumentExtractor. When `vlm_pipeline` is not provided, it uses the default model configuration. Custom models allow fine-tuning extraction behavior for specific document types.

#### 9. `entity_extraction.custom_schema` (JSON)
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

#### 10. `entity_extraction.expand_extracted_data` (Boolean)
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

#### 11. `text_extraction.provider_config.vlm_pipeline` (Object)
**Type:** JSON Object  
**Required:** No  
**Default:** `null`  
**Description:** Provider-specific VLM pipeline configuration for enhanced extraction (docling_library mode only). When provided, enables Vision-Language Model processing.  

**Sub-parameters:**
- `preset` (String): VLM preset name. Valid presets include: `smoldocling`, `granite_docling`, `deepseek_ocr`, `granite_vision`, `pixtral`, `got_ocr`, `phi4`, `qwen`, `nanonets_ocr2`, `gemma_12b`, `gemma_27b`, `dolphin`, `glm_ocr`, `lightonocr`, `falcon_ocr`
- `engine` (String): VLM engine type. Valid engines: `api_ollama`, `api_openai`, `api_watsonx`, `api_lmstudio`, `api` (generic), `transformers` (local), `mlx` (macOS)
- `engine_options` (Object): Engine-specific configuration
  - `api_base` (String, Optional): API base URL for API-based engines (e.g., `http://localhost:11434` for Ollama)
  - `model_id` (String, Optional): Model identifier
  - `request_timeout` (Integer, Optional): Request timeout in seconds (default: 90)

**Examples:**
```json
"text_extraction": {
  "provider": "docling_library",
  "provider_config": {
    "vlm_pipeline": {
      "preset": "granite_docling",
      "engine": "api_ollama",
      "engine_options": {
        "api_base": "http://localhost:11434",
        "model_id": "ibm/granite-docling:258m",
        "request_timeout": 300
      }
    }
  }
}
```

**Transformers Example:**
```json
"text_extraction": {
  "provider": "docling_library",
  "provider_config": {
    "vlm_pipeline": {
      "preset": "granite_docling",
      "engine": "transformers",
      "engine_options": {
        "model_id": "microsoft/Florence-2-large"
      }
    }
  }
}
```

**OpenAI Example:**
```json
"text_extraction": {
  "provider": "docling_library",
  "provider_config": {
    "vlm_pipeline": {
      "preset": "qwen",
      "engine": "api_openai",
      "engine_options": {
        "api_key": "sk-...", # pragma: allowlist secret
        "api_base": "https://api.openai.com",
        "model_id": "gpt-4-vision-preview"
      }
    }
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

### `content_doclang` (String)
**Type:** String
**Description:** DocLang format of extracted content (when `additional_formats` includes "doclang")
**Available for Filter:** Yes
**Available for Vector DB:** Yes
**Note:** Only present when "doclang" is specified in `additional_formats` parameter

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
  "operator": "extract_operator",
  "config": {
    "text_extraction": {
      "provider": "docling_library",
      "provider_config": {
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
  "operator": "extract_operator",
  "config": {
    "text_extraction": {
      "provider": "docling_library",
      "provider_config": {
        "vlm_pipeline": {
          "preset": "granite_docling",
          "engine": "api_ollama",
          "engine_options": {
            "api_base": "http://localhost:11434",
            "model_id": "ibm/granite-docling:258m"
          }
        }
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
  "operator": "extract_operator",
  "config": {
    "text_extraction": {
      "provider": "docling_library",
      "provider_config": {
        "additional_formats": ["html", "json", "text", "doclang"],
      }
    },
    "entity_extraction": {
      "provider": "none"
    }
  }
}
```
**Output columns**: `content` (markdown), `content_html`, `content_json`, `content_text`, `content_doclang`, `tables`, `images`

### Example 6: LiteLLM Entity Extraction with OpenAI
```json
{
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

### Example 7: WatsonX Entity Extraction
Extract entities using IBM WatsonX AI models. This example demonstrates using WatsonX for structured entity extraction from documents with custom schema definition.

```json
{
  "operator": "extract_operator",
  "config": {
    "text_extraction": {
      "provider": "docling_library"
    },
    "entity_extraction": {
      "provider": "watsonx",
      "provider_config": {
        "model_id": "ibm/granite-13b-chat-v2",
        "api_key": "YOUR_IBM_CLOUD_API_KEY",  # pragma: allowlist secret
        "api_base": "https://us-south.ml.cloud.ibm.com",
        "container_id": "your-project-id",
        "container_kind": "project",
        "temperature": 0.0,
        "max_tokens": 2000
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

**Key Configuration:**
- `model_id`: WatsonX model identifier (e.g., `ibm/granite-13b-chat-v2`)
- `api_key`: IBM Cloud API key for authentication
- `api_base`: WatsonX API endpoint URL (region-specific)
- `container_id`: Project or space ID in WatsonX
- `container_kind`: Either "project" or "space"
- `temperature`: Controls randomness (0.0 for deterministic output)
- `max_tokens`: Maximum tokens in the response
- `expand_extracted_data`: Expands extracted entities into separate columns

```

### Example 8: LiteLLM Entity Extraction with Remote vLLM (Streaming)
```json
{
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

### Example 9: Docling Entity Extraction with Custom Model
```json
{
  "operator": "extract_operator",
  "config": {
    "text_extraction": {
      "provider": "docling_library"
    },
    "entity_extraction": {
      "provider": "docling",
      "provider_config": {
        "vlm_pipeline": {
          "model_type": "inline",
          "inline_model": {
            "repo_id": "microsoft/Florence-2-large",
            "inference_framework": "transformers",
            "scale": 2.0,
            "temperature": 0.0,
            "max_new_tokens": 4096,
            "load_in_8bit": true,
            "torch_dtype": "bfloat16"
          }
        }
      },
      "custom_schema": {
        "invoice_number": "string",
        "vendor_name": "string",
        "total_amount": "number",
        "invoice_date": "string"
      },
      "expand_extracted_data": true
    }
  }
}
```

### Example 10: Docling Entity Extraction with Default Model
```json
{
  "operator": "extract_operator",
  "config": {
    "text_extraction": {
      "provider": "docling_library"
    },
    "entity_extraction": {
      "provider": "docling",
      "custom_schema": {
        "person_name": "string",
        "organization": "string",
        "location": "string"
      },
      "output_column": "entities"
    }
  }
}
```

### Example 11: ASR Pipeline for Audio/Video Transcription

Extract text from audio/video files using Automatic Speech Recognition:

```json
{
  "operator_id": "extract_audio",
  "operator_type": "ExtractOperator",
  "config": {
    "text_extraction": {
      "provider": "docling_library",
      "provider_config": {
        "asr_pipeline": {
          "model_id": "whisper_turbo"
        }
      }
    },
    "entity_extraction": {
      "provider": "none"
    }
  },
  "dependencies": []
}
```

**Use Case:** Transcribing audio/video content from documents

**Model Options:** `whisper_tiny`, `whisper_small`, `whisper_medium`, `whisper_base`, `whisper_large`, `whisper_turbo`, and their `_mlx`/`_native` variants

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
