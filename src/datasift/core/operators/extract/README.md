# ExtractOperator

The `ExtractOperator` is a unified extraction operator that provides a single interface for multiple extraction strategies using hexagonal architecture. It supports both text extraction (converting documents to markdown) and entity extraction (extracting structured data from text).

## Overview

The operator follows hexagonal architecture principles, separating business logic from infrastructure concerns:

- **Domain Layer**: Core models (`TextExtractionMode`, `EntityExtractionMode`, extraction requests/results)
- **Port Layer**: Interfaces defining extraction contracts (`TextExtractionPort`, `EntityExtractionPort`)
- **Adapter Layer**: Concrete implementations for different extraction strategies
- **Factory Layer**: Creates appropriate adapters based on configuration

This architecture enables:
- Easy addition of new extraction strategies
- Clear separation of concerns
- Testability through dependency injection
- Flexibility in switching between implementations

## Key Features

- **Dual-Mode Operation**: Supports both text extraction and entity extraction in a single operator
- **Multiple Text Extraction Strategies**: Docling Library (with optional VLM and ASR pipeline) and Docling Serve API
- **Multiple Entity Extraction Strategies**: LiteLLM (including Ollama via openai/ prefix), Docling template-based, and WatsonX
- **Estimated Page Count Calculation**: Automatically calculates estimated page counts for extracted text
- **Parallel Processing**: Automatic worker optimization based on CPU count
- **Flexible Configuration**: Mode-specific parameters with sensible defaults
- **Consistent Error Handling**: Unified error handling and metadata across all modes

## Operator Configuration

```json
{
  
  "operator_params": {
    "max_workers": 4,
    "text_extraction": {
      "provider": "docling_library",
      "doc_column": "content",
      "provider_config": {
      }
    },
    "entity_extraction": {
      "provider": "none"
    }
  }
}
```

## Text Extraction Modes

### 1. Docling Library Mode (Default)

Standard document extraction using the Docling library locally. Supports optional VLM (Vision-Language Model) pipeline for enhanced extraction and ASR (Automatic Speech Recognition) pipeline for audio/video processing.

**Basic Configuration:**
```json
{
  "max_workers": 4,
  "text_extraction": {
    "provider": "docling_library",
    "doc_column": "content",
    "provider_config": {
    }
  },
  "entity_extraction": {
    "provider": "none"
  }
}
```

**VLM Pipeline Configuration:**

Enable VLM pipeline for enhanced extraction with vision-language models:

```json
{
  "max_workers": 1,
  "text_extraction": {
    "provider": "docling_library",
    "doc_column": "content",
    "provider_config": {
      "vlm_pipeline": {
        "preset": "granite_docling",
        "engine": "transformers",
        "engine_options": {}
      }
    }
  },
  "entity_extraction": {
    "provider": "none"
  }
}
```

**Supported VLM Engines:**
- `transformers`: Local inference using Transformers library
- `mlx`: Local inference optimized for macOS (Apple Silicon)
- `api_ollama`: Ollama API
- `api_openai`: OpenAI API
- `api_watsonx`: IBM watsonx.ai API
- `api_lmstudio`: LM Studio API
- `api`: Generic API endpoint

**VLM Pipeline Configuration Examples:**

Ollama:
```json
{
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
  }
}
```

OpenAI:
```json
{
  "text_extraction": {
    "provider": "docling_library",
    "provider_config": {
      "vlm_pipeline": {
        "preset": "qwen",
        "engine": "api_openai",
        "engine_options": {
          "api_base": "https://api.openai.com/v1",
          "model_id": "gpt-4-vision-preview",
          "api_key": "<your-api-key>"
        }
      }
    }
  }
}
```

**ASR Pipeline Configuration:**

Enable ASR pipeline for audio and video file transcription:

```json
{
  "max_workers": 2,
  "text_extraction": {
    "provider": "docling_library",
    "doc_column": "content",
    "provider_config": {
      "asr_pipeline": {
        "model_id": "whisper_turbo"
      }
    }
  },
  "entity_extraction": {
    "provider": "none"
  }
}
```

**Use Cases:**
- Simple document conversion to markdown (without VLM)
- Complex document layouts (with VLM)
- Documents with mixed content types (with VLM)
- Audio/video transcription (with ASR)
- Local processing without external dependencies
- High-accuracy extraction requirements (with VLM)
- Quick prototyping and testing

**Sample Flows:**
- Basic: [`tests/sample_test_flows/extract/flow_extract_basic.json`](../../../../tests/sample_test_flows/extract/flow_extract_basic.json)
- VLM: [`tests/sample_test_flows/extract/flow_extract_vlm.json`](../../../../tests/sample_test_flows/extract/flow_extract_vlm.json)
- Audio/Video: [`tests/sample_test_flows/audio_video/flow_audio_video_extraction.json`](../../../../../tests/sample_test_flows/audio_video/flow_audio_video_extraction.json)

### 2. Docling Serve Mode

REST API-based extraction using the Docling-Serve service for scalable, production-ready document processing.

**Configuration:**
```json
{
  "text_extraction": {
    "provider": "docling_serve",
    "provider_config": {
      "base_url": "http://localhost:5001",
      "timeout": 300,
      "poll_interval": 2,
      "max_retries": 3,
      "do_ocr": true,
      "ocr_engine": "easyocr",
      "ocr_languages": ["en"],
      "pdf_backend": "dlparse_v4",
      "table_mode": "accurate",
      "image_export_mode": "embedded"
    }
  },
  "entity_extraction": {
    "provider": "none"
  }
}
```

**File Handling:**
- `.txt` files are processed locally using basic text extraction (not sent to Docling Serve)
- Binary content submissions preserve the original filename for proper MIME type detection
- Supported MIME types are automatically detected based on file extension

**MIME Type Mapping:**

| Extension | MIME Type |
|-----------|-----------|
| `.html`, `.htm` | `text/html` |
| `.md` | `text/markdown` |
| `.txt` | `text/plain` |
| `.pdf` | `application/pdf` |
| `.docx` | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` |
| `.xlsx` | `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` |
| `.pptx` | `application/vnd.openxmlformats-officedocument.presentationml.presentation` |
| Other | `application/octet-stream` |

**Prerequisites:**
```bash
# Start docling-serve locally
docker run -p 5001:5001 ds4sd/docling-serve:latest

# Or use docker-compose
docker-compose -f docker-compose.docling-serve.yml up -d
```

**Features:**
- **OCR Support**: Process scanned documents and images
  - EasyOCR engine (supports 80+ languages)
  - Tesseract engine
  - Multi-language support
- **Multiple PDF Backends**:
  - `dlparse_v4`: Latest Docling parser (recommended)
  - `dlparse_v3`: Legacy Docling parser
  - `pypdfium2`: PyPDFium2 backend
- **Table Extraction Modes**:
  - `accurate`: High accuracy (slower)
  - `fast`: Fast processing (less accurate)
- **Image Export Options**:
  - `embedded`: Embed images in output
  - `referenced`: Reference images by path
  - `none`: Skip image export

**Use Cases:**
- Production document processing pipelines
- High-volume document ingestion
- Scanned document processing with OCR
- Multi-language document processing
- Distributed processing architectures

**Sample Flow:** [`tests/sample_test_flows/extract/flow_extract_docling_serve.json`](../../../../tests/sample_test_flows/extract/flow_extract_docling_serve.json)

## Entity Extraction Modes

Entity extraction can be combined with any text extraction mode to extract structured data from the extracted text.

### 1. None Mode (Default)

No entity extraction is performed. Only text extraction is executed.

**Configuration:**
```json
{
  "text_extraction": {
    "provider": "docling_library"
  },
  "entity_extraction": {
    "provider": "none"
  }
}
```

### 2. Docling Mode (VLM-Based)

Vision-Language Model (VLM) based entity extraction using Docling's VLM pipeline for structured data extraction from documents.

**Basic Configuration:**
```json
{
  "text_extraction": {
    "provider": "docling_library"
  },
  "entity_extraction": {
    "provider": "docling",
    "provider_config": {
      "custom_schema": {
        "type": "object",
        "properties": {
          "invoice_number": { "type": "string" },
          "invoice_date": { "type": "string" },
          "total_amount": { "type": "number" },
          "line_items": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "description": { "type": "string" },
                "quantity": { "type": "number" },
                "unit_price": { "type": "number" }
              }
            }
          }
        }
      }
    }
  }
}
```

**Custom Model Configuration:**

Users can configure custom inline VLM models for entity extraction using the `vlm_pipeline` parameter. Only inline models (HuggingFace) are supported as DocumentExtractor does not support remote API endpoints.

**Inline Model (HuggingFace with Transformers):**
```json
{
  "text_extraction": {
    "provider": "docling_library"
  },
  "entity_extraction": {
    "provider": "docling",
    "provider_config": {
      "vlm_pipeline": {
        "model_type": "inline",
        "inline_model": {
          "repo_id": "numind/NuExtract-2.0-2B",
          "inference_framework": "transformers",
          "scale": 2.0,
          "temperature": 0.0,
          "max_new_tokens": 4096,
          "load_in_8bit": true,
          "torch_dtype": "bfloat16"
        }
      },
      "custom_schema": {
        "invoice_number": "string",
        "total_amount": "float"
      }
    }
  }
}
```

**Note:** API model configuration is not supported. For API-based entity extraction, use `entity_extraction.provider: "litellm"` instead.

**Supported Model Types:**
- **Inline Models**: HuggingFace models with Transformers, vLLM, or MLX backends
- **API Models**: Ollama, vLLM server, OpenAI-compatible endpoints

**Supported Backends (for inline models):**
- `transformers`: HuggingFace Transformers library
- `vllm`: vLLM inference engine
- `mlx`: Apple MLX framework (macOS only)

**Use Cases:**
- Extracting structured data from standardized forms
- Processing documents with known schema
- Vision-based entity extraction from complex layouts
- Custom model integration for specialized domains
- Template-driven workflows with VLM enhancement

**Sample Flows:**
- Basic: [`tests/sample_test_flows/extract/flow_extract_template.json`](../../../../tests/sample_test_flows/extract/flow_extract_template.json)
- Custom Model: [`tests/sample_test_flows/extract/flow_extract_docling_custom_model.json`](../../../../tests/sample_test_flows/extract/flow_extract_docling_custom_model.json)

### 3. LiteLLM Mode

Multi-provider LLM extraction using LiteLLM for accessing 100+ LLM providers (OpenAI, Anthropic, Cohere, Ollama, etc.).

**Configuration (OpenAI):**
```json
{
  "text_extraction": {
    "provider": "docling_library"
  },
  "entity_extraction": {
    "provider": "litellm",
    "provider_config": {
      "model_id": "openai/gpt-3.5-turbo",
      "api_key": "your-api-key",  # pragma: allowlist secret
      "api_base": "https://api.openai.com/v1",
      "temperature": 0.0,
      "max_tokens": 2000,
      "custom_schema": {
        "invoice_number": "string",
        "total_amount": "float"
      }
    }
  }
}
```

**Configuration (Ollama via LiteLLM):**
```json
{
  "text_extraction": {
    "provider": "docling_library"
  },
  "entity_extraction": {
    "provider": "litellm",
    "provider_config": {
      "model_id": "openai/llama3.2",
      "api_base": "http://localhost:11434/v1",
      "api_key": "<ollama_key>",
      "temperature": 0.0,
      "max_tokens": 4096,
      "custom_schema": {
        "invoice_number": "string",
        "total_amount": "float"
      }
    }
  }
}
```

**Configuration (Remote vLLM with Streaming & Extended Timeout):**

For high-concurrency scenarios with remote vLLM clusters processing large documents, use streaming and extended timeouts to prevent connection drops:

```json
{
  "text_extraction_mode": "docling_library",
  "entity_extraction_mode": "litellm",
  "entity_model_name": "openai/granite4:latest",
  "entity_temperature": 0.0,
  "entity_max_tokens": 5000,
  "entity_provider_config": {
    "api_base": "https://your-vllm-route/v1",
    "api_key": "YOUR_API_KEY",  # pragma: allowlist secret
    "stream": true,
    "timeout": 1800
  },
  "custom_schema": {
    "invoice_number": "string",
    "total_amount": "float"
  }
}
```

**Advanced Provider Configuration Parameters:**
- `stream` (boolean, default: `false`): Enable HTTP chunked transfer encoding to keep connections alive during long-running requests. Recommended for remote vLLM clusters processing large documents.
- `timeout` (integer, default: `60`): HTTP client read timeout in seconds. Set to 1800 (30 minutes) for large documents that require extended generation time.

**Why Streaming & Extended Timeout?**

During high-concurrency scalability testing with remote vLLM clusters, connection issues were identified:
1. **Infrastructure Idle Timeout**: Load balancers (IBM Cloud Edge, HAProxy) reset idle connections after ~100 seconds without data transmission. With `stream=false`, vLLM waits until entire generation completes (150+ seconds for large documents) before sending response, causing connections to be dropped mid-generation.
2. **Extended Processing Time**: Large documents requiring 5000+ tokens at ~88 tokens/sec take 150+ seconds to generate, exceeding typical load balancer idle timeouts.

**Solution**: Combining `stream=true` with `timeout=1800` ensures:
- Continuous packet flow (streaming chunks) prevents idle timeout detection by load balancers
- Extended timeout (30 minutes) allows completion of large document processing
- Connections remain stable under high concurrency (10,000+ documents)

**Supported Providers:**
- OpenAI (GPT-3.5, GPT-4, GPT-4o)
- Anthropic (Claude 3 Opus, Sonnet, Haiku)
- Cohere (Command, Command-R)
- Google (Gemini Pro, Gemini Ultra)
- Azure OpenAI
- AWS Bedrock
- Ollama (via openai/ model prefix)
- And 100+ other providers via LiteLLM

**Prerequisites for Ollama:**
- Ollama server running on `http://localhost:11434`
- Model pulled: `ollama pull llama3.2`

**Use Cases:**
- Multi-provider LLM support without code changes
- Enterprise LLM deployments (Azure, AWS Bedrock)
- Cost optimization by switching between providers
- Fallback strategies across multiple providers
- Schema-based and schema-free entity extraction
- Local LLM processing via Ollama

**Sample Flow:** [`tests/sample_test_flows/extract/flow_extract_basic_litellm.json`](../../../../tests/sample_test_flows/extract/flow_extract_basic_litellm.json)

### 4. WatsonX Mode

IBM WatsonX.ai LLM-based entity extraction for enterprise deployments.

**Configuration:**
```json
{
  "text_extraction": {
    "provider": "docling_library"
  },
  "entity_extraction": {
    "provider": "watsonx",
    "provider_config": {
      "model_id": "ibm/granite-13b-chat-v2",
      "api_key": "${WATSONX_API_KEY}",
      "container_id": "${WATSONX_CONTAINER_ID}",
      "api_base": "https://us-south.ml.cloud.ibm.com",
      "container_kind": "project",
      "temperature": 0.0,
      "max_tokens": 2000,
      "custom_schema": {
        "invoice_number": "string",
        "total_amount": "float"
      }
    }
  }
}
```

**Environment Variables:**
- `WATSONX_API_KEY`: WatsonX API key (required)
- `WATSONX_CONTAINER_ID`: WatsonX project or space ID (required)
- `WATSONX_API_BASE_URL`: WatsonX API base URL (optional, defaults to us-south)
- `WATSONX_CONTAINER_KIND`: Container type - "project" or "space" (optional, defaults to "project")

**Use Cases:**
- Enterprise LLM deployments with IBM WatsonX.ai
- Regulated industries requiring on-premises or private cloud LLM
- Schema-based entity extraction with IBM Granite models
- Integration with existing IBM Cloud infrastructure

**Sample Flow:** [`tests/sample_test_flows/extract/flow_extract_basic_watsonx.json`](../../../../tests/sample_test_flows/extract/flow_extract_basic_watsonx.json)

## Configuration Parameters

### Common Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `text_extraction.provider` | string | `"docling_library"` | Text extraction strategy: `"docling_library"` or `"docling_serve"` |
| `text_extraction.doc_column` | string | `"doc_content"` | Column name for storing extracted content |
| `text_extraction.provider_config.additional_formats` | array | `[]` | Additional output formats (e.g., `["html", "markdown"]`) |
| `max_workers` | integer | auto | Maximum number of parallel workers (auto-detected based on CPU) |
| `text_extraction.provider_config.use_processes` | boolean | `false` | Use ProcessPoolExecutor instead of ThreadPoolExecutor |
| `entity_extraction.provider` | string | `"none"` | Entity extraction strategy: `"litellm"` (includes Ollama via openai/ prefix), `"docling"`, `"watsonx"`, or `"none"` |
| `entity_extraction.provider_config.expand_extracted_data` | boolean | `false` | Expand entity data JSON into individual columns (entity extraction only) |
| `entity_extraction.provider_config.custom_schema` | object | `{}` | Schema dictionary for structured extraction |

### Docling Library Mode Parameters

| Parameter             | Type    | Default             | Description                                                         |
|-----------------------|---------|---------------------|---------------------------------------------------------------------|
| `text_extraction.provider_config.vlm_pipeline`        | object  | `null`              | VLM (Vision-Language Model) pipeline configuration object. Provide empty dict `{}` to enable with defaults, or omit to disable. |
| `text_extraction.provider_config.vlm_pipeline.preset` | string  | `"granite_docling"` | VLM preset name. Valid presets: `smoldocling`, `granite_docling`, `deepseek_ocr`, `granite_vision`, `pixtral`, `got_ocr`, `phi4`, `qwen`, `nanonets_ocr2`, `gemma_12b`, `gemma_27b`, `dolphin`, `glm_ocr`, `lightonocr`, `falcon_ocr` |
| `text_extraction.provider_config.vlm_pipeline.engine` | string  | `"api_ollama"`      | VLM engine type. Valid engines: `api_ollama`, `api_openai`, `api_watsonx`, `api_lmstudio`, `api` (generic), `transformers` (local), `mlx` (macOS) |
| `text_extraction.provider_config.vlm_pipeline.engine_options` | object | `{}`        | Engine-specific options (api_base, model_id, etc.)                  |
| `text_extraction.provider_config.asr_pipeline`        | object  | `null`              | ASR (Automatic Speech Recognition) pipeline configuration object. Provide empty dict `{}` to enable with defaults, or omit to disable. |
| `text_extraction.provider_config.asr_pipeline.model_id` | string | `"whisper_turbo"` | ASR model name. Valid values: `whisper_tiny`, `whisper_small`, `whisper_medium`, `whisper_base`, `whisper_large`, `whisper_turbo`, and their `_mlx`/`_native` variants (e.g., `whisper_tiny_mlx`, `whisper_tiny_native`) |

### Docling Serve Mode Parameters

| Parameter              | Type     | Default                   | Description                                                   |
|------------------------|----------|---------------------------|---------------------------------------------------------------|
| `text_extraction.provider_config.base_url`             | string   | `"http://localhost:5001"` | Docling Serve API endpoint URL                                |
| `text_extraction.provider_config.api_key`              | string   | `null`                    | Optional API key for authentication                           |
| `text_extraction.provider_config.timeout`              | integer  | `300`                     | Request timeout in seconds                                    |
| `text_extraction.provider_config.poll_interval`        | integer  | `2`                       | Polling interval in seconds                                   |
| `text_extraction.provider_config.max_retries`          | integer  | `3`                       | Maximum retry attempts                                        |
| `text_extraction.provider_config.do_ocr`               | boolean  | `true`                    | Enable OCR processing                                         |
| `text_extraction.provider_config.ocr_engine`           | string   | `"easyocr"`               | OCR engine: `"easyocr"` or `"tesseract"`                      |
| `text_extraction.provider_config.ocr_languages`        | array    | `null`                    | List of OCR languages (e.g., `["en", "es"]`)                  |
| `text_extraction.provider_config.pdf_backend`          | string   | `"dlparse_v2"`            | PDF backend: `"dlparse_v4"`, `"dlparse_v3"`, or `"pypdfium2"` |
| `text_extraction.provider_config.table_mode`           | string   | `"fast"`                  | Table extraction mode: `"accurate"` or `"fast"`               |
| `text_extraction.provider_config.image_export_mode`    | string   | `"placeholder"`           | Image export mode: `"embedded"`, `"referenced"`, or `"none"`  |

### Docling Entity Extraction Parameters

| Parameter               | Type   | Default | Description                                                                                     |
|-------------------------|--------|---------|-------------------------------------------------------------------------------------------------|
| `entity_extraction.provider_config.vlm_pipeline` | object | `null`  | Custom VLM model configuration (see Custom Model Configuration section above for full details) |

**vlm_pipeline Structure:**

For inline models (HuggingFace):
```json
{
  "model_type": "inline",
  "model_name": "ibm-granite/granite-3.0-8b-instruct",
  "backend": "transformers|vllm|mlx",
  "device": "cuda|cpu|mps",
  "quantization": "4bit|8bit|none",
  "temperature": 0.0,
  "max_new_tokens": 2048
}
```

For API models (Ollama, vLLM, OpenAI-compatible):
```json
{
  "model_type": "api",
  "model_name": "ibm/granite-docling:258m",
  "api_url": "http://localhost:11434/v1/chat/completions",
  "api_key": "optional-api-key",  # pragma: allowlist secret
  "temperature": 0.0,
  "max_new_tokens": 2048
}
```

### LiteLLM Entity Extraction Parameters

All parameters are nested under `entity_extraction.provider_config`:

| Parameter                | Type    | Default           | Description                                                                                        |
|--------------------------|---------|-------------------|----------------------------------------------------------------------------------------------------|
| `model_id`      | string  | `"gpt-3.5-turbo"` | LLM model identifier. **Must include provider prefix** when using LiteLLM (e.g., `openai/gpt-4`, `openai/llama3.2` for Ollama, `anthropic/claude-3-opus`)                  |
| `temperature`     | float   | `0.0`             | Sampling temperature                                                                               |
| `max_tokens`      | integer | `2000`            | Maximum response tokens                                                                            |
| `api_key` | string  | `null`              | API key for the provider. For Ollama, can be any value |
| `api_base` | string  | `null`              | API base URL. For Ollama, set to `http://localhost:11434/v1` |
| `stream` | boolean  | `false`              | Enable HTTP chunked transfer encoding. For remote vLLM with large documents, use `stream: true` and `timeout: 1800` |
| `timeout` | integer  | `60`              | HTTP client read timeout in seconds. For remote vLLM with large documents, use `stream: true` and `timeout: 1800` |

### WatsonX Entity Extraction Parameters

All parameters are nested under `entity_extraction.provider_config`:

| Parameter                | Type    | Default                     | Description                                                                                        |
|--------------------------|---------|-----------------------------|----------------------------------------------------------------------------------------------------|
| `model_id`      | string  | `"ibm/granite-13b-chat-v2"` | WatsonX model identifier                                                                           |
| `temperature`     | float   | `0.0`                       | Sampling temperature                                                                               |
| `max_tokens`      | integer | `2000`                      | Maximum response tokens                                                                            |
| `api_key` | string  | required                        | WatsonX API key |
| `container_id` | string  | required                        | WatsonX project or space ID |
| `api_base` | string  | `"https://us-south.ml.cloud.ibm.com"` | WatsonX API base URL (optional) |
| `container_kind` | string  | `"project"` | Container type: "project" or "space" (optional) |

## Input/Output Data Formats

### Input Table Schema

The operator expects a PyArrow table with the following columns:

| Column          | Type   | Required   | Description                          |
|-----------------|--------|------------|--------------------------------------|
| `id`            | string | Yes        | Document identifier                  |
| `name`          | string | Yes        | Document name/filename               |
| `path`          | string | Yes        | Document file path                   |
| `document_type` | string | No         | Document type for template selection |

### Output Table Schema

The operator produces a PyArrow table with the following columns:

| Column            | Type   | Description                                                                                          |
|-------------------|--------|------------------------------------------------------------------------------------------------------|
| `id`              | string | Document identifier                                                                                  |
| `name`            | string | Document name                                                                                        |
| `doc_content`     | string | Extracted markdown content                                                                           |
| `doc_id_hash`     | string | Hash ID of the document row                                                                          |
| `pages_processed` | int32  | Estimated number of pages for the extracted document text, calculated using 3000 characters = 1 page |
| `entities`        | string | Extracted entities as JSON (if entity extraction enabled)                                            |
| `extracted_data`  | string | Structured data from template extraction (if applicable)                                             |

When `expand_extracted_data=true` is set for entity extraction, entity fields are expanded into individual columns.

**Note:** Page counts are estimates derived from extracted text length using 3000 characters per page.

## Usage Examples

### Example 1: Basic Text Extraction Only

```json
{
  
  "operator_params": {
    "text_extraction": {
      "provider": "docling_library",
      "doc_column": "content",
      "provider_config": {
      }
    },
    "entity_extraction": {
      "provider": "none"
    }
  }
}
```

### Example 2: Text + Entity Extraction with Ollama (via LiteLLM)

```json
{
  
  "operator_params": {
    "max_workers": 2,
    "text_extraction": {
      "provider": "docling_library",
      "doc_column": "content"
    },
    "entity_extraction": {
      "provider": "litellm",
      "provider_config": {
        "model_id": "openai/llama3.2",
        "api_base": "http://localhost:11434/v1",
        "api_key": "<ollama_key>",
        "temperature": 0.0,
        "max_tokens": 4096,
        "custom_schema": {
          "invoice_number": "string",
          "vendor_name": "string",
          "total_amount": "float"
        }
      }
    }
  }
}
```

### Example 3: VLM Pipeline Text Extraction

```json
{
  
  "operator_params": {
    "max_workers": 1,
    "text_extraction": {
      "provider": "docling_library",
      "doc_column": "content",
      "provider_config": {
        "vlm_pipeline": {
          "preset": "granite_docling",
          "engine": "transformers",
          "engine_options": {}
        }
      }
    },
    "entity_extraction": {
      "provider": "none"
    }
  }
}
```

### Example 4: Docling Serve with OCR

```json
{
  "operator_params": {
    "max_workers": 4,
    "text_extraction": {
      "provider": "docling_serve",
      "doc_column": "content",
      "provider_config": {
        "base_url": "http://localhost:5001",
        "do_ocr": true,
        "ocr_engine": "easyocr",
        "ocr_languages": ["en", "es"],
        "pdf_backend": "dlparse_v4",
        "table_mode": "accurate"
      }
    },
    "entity_extraction": {
      "provider": "none"
    }
  }
}
```

### Example 5: Template-Based Entity Extraction

```json
{
  
  "operator_params": {
    "max_workers": 2,
    "text_extraction": {
      "provider": "docling_library",
      "doc_column": "content"
    },
    "entity_extraction": {
      "provider": "docling",
      "provider_config": {
        "custom_schema": {
          "type": "object",
          "properties": {
            "invoice_number": { "type": "string" },
            "invoice_date": { "type": "string" },
            "total_amount": { "type": "number" }
          }
        }
      }
    }
  }
}
```

### Example 6: VLM Pipeline + Ollama Entity Extraction (via LiteLLM)

```json
{
  
  "operator_params": {
    "max_workers": 1,
    "text_extraction": {
      "provider": "docling_library",
      "doc_column": "content",
      "provider_config": {
        "vlm_pipeline": {
          "preset": "granite_docling",
          "engine": "transformers",
          "engine_options": {}
        }
      }
    },
    "entity_extraction": {
      "provider": "litellm",
      "provider_config": {
        "model_id": "openai/llama3.2",
        "api_base": "http://localhost:11434/v1",
        "api_key": "<ollama_key>",
        "temperature": 0.0
      }
    }
  }
}
```

### Example 7: ASR Pipeline for Audio/Video Transcription

```json
{
  
  "operator_params": {
    "max_workers": 2,
    "text_extraction": {
      "provider": "docling_library",
      "doc_column": "content",
      "provider_config": {
        "asr_pipeline": {
          "model_id": "whisper_turbo"
        }
      }
    },
    "entity_extraction": {
      "provider": "none"
    }
  }
}
```

## Integration Requirements

### ASR Dependencies (for Audio/Video Processing)

**Requirement:** ASR (Automatic Speech Recognition) dependencies must be installed to process audio and video files

**Installation:**
```bash
# Install ASR dependencies
uv pip install -e '.[asr]'
```

**Supported Audio/Video Formats (when ASR is installed):**
- Audio: MP3, WAV, M4A, FLAC, OGG
- Video: MP4, AVI, MOV, MKV

**Note:** If ASR dependencies are not installed, the operator will only support standard document formats (PDF, DOCX, PPTX, etc.) and will log a warning if `use_asr_pipeline=true` is configured.

**Used By:** Text extraction with ASR when `use_asr_pipeline=true`

### ffmpeg (for Audio/Video Processing)

**Requirement:** ffmpeg must be installed and available on your PATH for processing certain audio and video formats

**Required For:**
- Audio formats: M4A, AAC, OGG, FLAC
- All video formats: MP4, AVI, MOV, etc.

**Not Required For:**
- Audio formats: WAV, MP3
- Document formats: PDF, images, etc.

**Installation:**

**macOS (using Homebrew):**
```bash
brew install ffmpeg
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install ffmpeg
```

**Linux (RHEL/CentOS/Fedora):**
```bash
sudo dnf install ffmpeg
```

**Verify Installation:**
```bash
ffmpeg -version
```

**Used By:** Text extraction with ASR (Automatic Speech Recognition) when processing audio/video files

### Ollama Integration (for LiteLLM entity extraction with Ollama)

**Requirement:** Ollama server must be running on `http://localhost:11434`

**Setup:**
```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull required model
ollama pull llama3.2

# Verify Ollama is running
curl http://localhost:11434/api/tags
```

**Used By:** Entity extraction when `entity_extraction.provider="litellm"` with `entity_extraction.provider_config.model_id="openai/llama3.2"` and `entity_extraction.provider_config.api_base="http://localhost:11434/v1"`

### Docling Serve Integration (for docling_serve text extraction)

**Requirement:** Docling Serve must be running (default: `http://localhost:5001`)

**Setup:**
```bash
# Using Docker
docker run -p 5001:5001 ds4sd/docling-serve:latest

# Or using docker-compose
docker-compose -f docker-compose.docling-serve.yml up -d

# Verify service is running
curl http://localhost:5001/health
```

**Used By:** Text extraction when `text_extraction.provider="docling_serve"`

## Mode Comparison

| Feature                   | Docling Library (Basic)   | Docling Library (VLM)  | Docling Serve            |
|---------------------------|---------------------------|------------------------|--------------------------|
| **Processing Location**   | Local                     | Local/API              | Remote API               |
| **OCR Support**           | No                        | Limited                | Yes (EasyOCR, Tesseract) |
| **Multi-language OCR**    | No                        | No                     | Yes                      |
| **Scalability**           | Low                       | Medium                 | High                     |
| **Setup Complexity**      | Low                       | Medium                 | Medium                   |
| **Processing Speed**      | Fast                      | Slow                   | Medium                   |
| **Accuracy**              | Good                      | Excellent              | Excellent                |
| **External Dependencies** | None                      | Model files            | Docker container         |

| Feature                   | LiteLLM (Ollama) | LiteLLM (Cloud) | Docling   | WatsonX             |
|---------------------------|------------------|-----------------|-----------|---------------------|
| **Processing Location**   | Local            | Remote API      | Local     | Remote API          |
| **Schema Support**        | Yes              | Yes             | Yes       | Yes                 |
| **Schema-Free Mode**      | Yes              | Yes             | No        | Yes                 |
| **Setup Complexity**      | Medium           | Low             | Low       | Medium              |
| **Processing Speed**      | Medium           | Fast            | Fast      | Medium              |
| **Accuracy**              | High             | High            | Good      | High                |
| **External Dependencies** | Ollama server    | API keys        | None      | WatsonX credentials |

## Best Practices

### When to Use Each Text Extraction Mode

**Use Docling Library Mode (Basic) When:**
- Processing simple documents locally
- No OCR required
- Quick prototyping
- Minimal setup needed

**Use Docling Library Mode (VLM Pipeline) When:**
- Complex document layouts
- High accuracy requirements
- Local processing preferred
- GPU available for inference

**Use Docling Serve Mode When:**
- Production deployment
- OCR required for scanned documents
- Multi-language support needed
- Horizontal scaling required
- Processing high document volumes

### When to Use Each Entity Extraction Mode

**Use None Mode When:**
- Only text extraction is needed
- Entity extraction will be done in a separate step

**Use LiteLLM Mode When:**
- Multi-provider LLM support needed
- Cloud-based or local (Ollama) LLM processing
- Cost optimization by switching between providers
- Flexible entity extraction without predefined templates
- Schema-based or schema-free extraction needed

**Use Docling Mode When:**
- Extracting structured data from standardized forms
- Processing documents with known schema
- Fast, deterministic extraction required
- Template-driven workflows

**Use WatsonX Mode When:**
- Enterprise LLM deployments with IBM WatsonX.ai
- Regulated industries requiring private cloud LLM
- Integration with existing IBM Cloud infrastructure
- IBM Granite models preferred

### Performance Optimization

1. **Worker Configuration:**
   - Text extraction: Use default auto-detection (typically 4-8 workers)
   - Entity extraction with LLM: Reduce to 1-2 workers to avoid overwhelming the LLM
   - VLM extraction: Use 1 worker due to high memory requirements

2. **Document Size:**
   - For large documents with entity extraction, adjust `entity_max_doc_chars` to control LLM input size
   - Consider chunking very large documents before extraction

3. **Parallel Processing:**
   - Use `use_processes=true` for CPU-intensive tasks
   - Use `use_processes=false` (default) for I/O-bound tasks

## Execution Metadata

The operator provides the following metadata after execution:

- **`page_type_stats`** (dict): Aggregate estimated pages grouped by source document format (e.g., `{"pdf": 120, "docx": 45}`)
- **`total_pages_converted`** (int): Total estimated pages across all successfully processed documents

These metrics are available through the operator's metadata and can be used for tracking document processing volume and performance analysis.

## Sample Flows

Complete sample flows are available in [`tests/sample_test_flows/extract/`](../../../../tests/sample_test_flows/extract/):

- [`flow_extract_basic.json`](../../../../tests/sample_test_flows/extract/flow_extract_basic.json) - Basic text extraction
- [`flow_extract_vlm.json`](../../../../tests/sample_test_flows/extract/flow_extract_vlm.json) - VLM text extraction
- [`flow_extract_docling_serve.json`](../../../../tests/sample_test_flows/extract/flow_extract_docling_serve.json) - Docling Serve text extraction
- [`flow_extract_text_and_entities_ollama.json`](../../../../tests/sample_test_flows/extract/flow_extract_text_and_entities_ollama.json) - Text + Ollama entity extraction
- [`flow_extract_template.json`](../../../../tests/sample_test_flows/extract/flow_extract_template.json) - Template-based entity extraction
- [`flow_extract_vlm_and_entities_ollama.json`](../../../../tests/sample_test_flows/extract/flow_extract_vlm_and_entities_ollama.json) - VLM + Ollama entity extraction

## Troubleshooting

### Common Issues

**Issue: "Failed to initialize text extraction adapter"**
- Verify the `text_extraction.provider` value is valid: `"docling_library"` or `"docling_serve"`
- For VLM pipeline (when `vlm_pipeline` is configured), ensure required model files are available
- For Docling Serve mode, verify the service is running and accessible

**Issue: "Failed to initialize entity extraction adapter"**
- Verify the `entity_extraction.provider` value is valid: `"litellm"`, `"docling"`, `"watsonx"`, or `"none"`
- For LiteLLM mode with Ollama, ensure Ollama server is running and the model is pulled, and use `openai/` model prefix
- For WatsonX mode, ensure environment variables `WATSONX_API_KEY` and `WATSONX_CONTAINER_ID` are set
- Check that required parameters (model_name, etc.) are provided

**Issue: "Ollama connection refused"**
- Verify Ollama is running: `curl http://localhost:11434/api/tags`
- Check that the specified model is available: `ollama list`
- Ensure no firewall is blocking port 11434

**Issue: "Docling Serve timeout"**
- Increase `timeout` value
- Check Docling Serve service health: `curl http://localhost:5001/health`
- Verify network connectivity to the Docling Serve endpoint

**Issue: "Entity extraction returns empty results"**
- Verify document content is not empty after text extraction
- Check `entity_max_doc_chars` is not too restrictive
- For schema-based extraction, ensure the schema matches the document structure
- Review LLM model capabilities for the extraction task

**Issue: "Audio/video processing fails with codec errors"**
- Ensure ffmpeg is installed: `ffmpeg -version`
- Verify ffmpeg is in your PATH: `which ffmpeg` (macOS/Linux) or `where ffmpeg` (Windows)
- Install ffmpeg if missing:
  - macOS: `brew install ffmpeg`
  - Linux: `sudo apt install ffmpeg` or `sudo dnf install ffmpeg`
- Supported formats requiring ffmpeg: M4A, AAC, OGG, FLAC (audio), MP4, AVI, MOV (video)
- WAV and MP3 audio files do not require ffmpeg

**Issue: "ffmpeg not found" error during audio/video extraction**
- Verify ffmpeg installation: `ffmpeg -version`
- Add ffmpeg to your PATH if installed but not found
- Restart your terminal/shell after installing ffmpeg
- On macOS, ensure Homebrew's bin directory is in PATH: `export PATH="/opt/homebrew/bin:$PATH"`

## Architecture Details

### Hexagonal Architecture

The ExtractOperator follows hexagonal architecture (ports and adapters pattern) with clear separation of concerns:

```
ExtractOperator (Orchestrator)
    ↓
┌─────────────────────────────────────────────────────────────┐
│ Domain Layer                                                 │
│  - EntityExtractionService (business logic)                  │
│  - Domain Models (TextExtractionMode, EntityExtractionMode)  │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│ Port Layer (Interfaces)                                      │
│  - TextExtractionPort                                        │
│  - EntityExtractionPort                                      │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│ Adapter Layer (Implementations)                              │
│  Text Extraction:                                            │
│   - DoclingAdapter (docling_library mode, optional VLM/ASR)  │
│   - DoclingServeAdapter (docling_serve mode)                 │
│  Entity Extraction:                                          │
│   - LLMEntityAdapter (litellm and watsonx modes - unified)   │
│   - DoclingEntityAdapter (docling mode)                      │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│ Factory Layer                                                │
│  - TextExtractionAdapterFactory                              │
│  - EntityExtractionAdapterFactory                            │
└─────────────────────────────────────────────────────────────┘
```

**Architecture Components:**

- **Domain Layer**: `EntityExtractionService` handles business logic (prompt building, schema validation, response parsing)
- **Port Layer**: Interfaces define extraction contracts without implementation details
- **Adapter Layer**: Concrete implementations for different extraction strategies
- **Factory Layer**: Creates appropriate adapters based on configuration mode

**Key Benefits:**
- Easy addition of new extraction strategies by implementing ports
- Clear separation between business logic, interfaces, and implementations
- Testability through dependency injection and mocking
- Unified LLM support: Both `litellm` and `watsonx` use the same `LLMEntityAdapter`

### Execution Flow

1. **Initialization:**
   - Parse extraction modes from configuration
   - Create text extraction adapter via `TextExtractionAdapterFactory`
   - Create entity extraction adapter via `EntityExtractionAdapterFactory` (if enabled)
   - Initialize `EntityExtractionService` with the entity adapter

2. **Text Extraction:**
   - Delegate to text extraction adapter
   - Process documents in parallel using worker pool
   - Collect extracted content and metadata

3. **Entity Extraction (if enabled):**
   - `EntityExtractionService` builds prompts with schema
   - Delegate to entity extraction adapter
   - Process extracted text in parallel
   - Extract structured entities based on schema or LLM
   - Service parses and validates responses

4. **Result Assembly:**
   - Combine text and entity extraction results
   - Update metadata with processing statistics
   - Return transformed PyArrow table

## Related Documentation

- [Docling Documentation](https://github.com/DS4SD/docling)
- [Ollama Documentation](https://ollama.com/docs)
- [Sample Flows](../../../../tests/sample_test_flows/extract/)