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
- **Multiple Text Extraction Strategies**: Docling Library (with optional VLM pipeline) and Docling Serve API
- **Multiple Entity Extraction Strategies**: Ollama LLM, Docling template-based, and LiteLLM
- **Parallel Processing**: Automatic worker optimization based on CPU count
- **Flexible Configuration**: Mode-specific parameters with sensible defaults
- **Consistent Error Handling**: Unified error handling and metadata across all modes

## Operator Configuration

```json
{
  
  "operator_params": {
    "text_extraction_mode": "docling_library",
    "entity_extraction_mode": "none",
    "doc_column": "content",
    "extract_tables": true,
    "extract_images": true,
    "max_workers": 4
  }
}
```

## Text Extraction Modes

### 1. Docling Library Mode (Default)

Standard document extraction using the Docling library locally. Supports optional VLM (Vision-Language Model) pipeline for enhanced extraction.

**Basic Configuration:**
```json
{
  "text_extraction_mode": "docling_library",
  "entity_extraction_mode": "none",
  "doc_column": "content",
  "extract_tables": true,
  "extract_images": true,
  "max_workers": 4
}
```

**VLM Pipeline Configuration:**

Enable VLM pipeline for enhanced extraction with vision-language models:

```json
{
  "text_extraction_mode": "docling_library",
  "entity_extraction_mode": "none",
  "doc_column": "content",
  "use_vlm_pipeline": true,
  "vlm_preset": "granite_docling",
  "vlm_engine_type": "transformers",
  "max_workers": 1
}
```

**Supported VLM Engines:**
- `transformers`: Local inference using Transformers library (default)
- `mlx`: Local inference optimized for macOS (Apple Silicon)
- `api`: Generic API endpoint
- `api_lmstudio`: LM Studio API
- `api_ollama`: Ollama API
- `api_openai`: OpenAI API
- `api_watsonx`: IBM watsonx.ai API

**VLM Provider Configuration Examples:**

Ollama:
```json
{
  "text_extraction_mode": "docling_library",
  "use_vlm_pipeline": true,
  "vlm_engine_type": "api_ollama",
  "vlm_provider_config": {
    "api_base_url": "http://localhost:11434/v1/chat/completions",
    "vlm_model_name": "llama3.2-vision"
  }
}
```

OpenAI:
```json
{
  "text_extraction_mode": "docling_library",
  "use_vlm_pipeline": true,
  "vlm_engine_type": "api_openai",
  "vlm_provider_config": {
    "vlm_api_key": "your-api-key",
    "vlm_model_name": "gpt-4-vision-preview"
  }
}
```

**Use Cases:**
- Simple document conversion to markdown (without VLM)
- Complex document layouts (with VLM)
- Documents with mixed content types (with VLM)
- Local processing without external dependencies
- High-accuracy extraction requirements (with VLM)
- Quick prototyping and testing

**Sample Flows:**
- Basic: [`tests/sample_test_flows/extract/flow_extract_basic.json`](../../../../tests/sample_test_flows/extract/flow_extract_basic.json)
- VLM: [`tests/sample_test_flows/extract/flow_extract_vlm.json`](../../../../tests/sample_test_flows/extract/flow_extract_vlm.json)

### 2. Docling Serve Mode

REST API-based extraction using the Docling-Serve service for scalable, production-ready document processing.

**Configuration:**
```json
{
  "text_extraction_mode": "docling_serve",
  "entity_extraction_mode": "none",
  "doc_column": "content",
  "docling_serve_base_url": "http://localhost:5001",
  "docling_serve_timeout": 300,
  "docling_serve_poll_interval": 2,
  "docling_serve_max_retries": 3,
  "docling_serve_do_ocr": true,
  "docling_serve_ocr_engine": "easyocr",
  "docling_serve_ocr_languages": ["en"],
  "docling_serve_pdf_backend": "dlparse_v4",
  "docling_serve_table_mode": "accurate",
  "docling_serve_image_export_mode": "embedded"
}
```

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
  "text_extraction_mode": "docling_library",
  "entity_extraction_mode": "none"
}
```

### 2. Ollama Mode

LLM-based entity extraction using locally running Ollama models.

**Configuration:**
```json
{
  "text_extraction_mode": "docling_library",
  "entity_extraction_mode": "ollama",
  "entity_model_name": "llama3.2",
  "entity_temperature": 0.0,
  "entity_max_tokens": 4096,
  "max_doc_chars": 8000,
  "custom_schema": {
    "invoice_number": "string",
    "invoice_date": "string",
    "total_amount": "float",
    "vendor_name": "string"
  }
}
```

**Parameters:**
- `entity_model_name`: Ollama model to use (default: "llama3.2")
- `entity_temperature`: Sampling temperature 0.0-1.0 (default: 0.0, deterministic)
- `entity_max_tokens`: Maximum response tokens (default: 4096)
- `entity_max_doc_chars`: Maximum document characters to send to LLM (default: 8000)
- `custom_schema`: Optional schema dictionary defining expected entity structure

**Prerequisites:**
- Ollama server running on `http://localhost:11434`
- Model pulled: `ollama pull llama3.2`

**Use Cases:**
- Flexible entity extraction without predefined templates
- Complex document understanding
- Schema-based or schema-free extraction
- Local LLM processing

**Sample Flow:** [`tests/sample_test_flows/extract/flow_extract_text_and_entities_ollama.json`](../../../../tests/sample_test_flows/extract/flow_extract_text_and_entities_ollama.json)

### 3. Docling Mode (Template-Based)

Template-based entity extraction using Docling's structured extraction capabilities.

**Configuration:**
```json
{
  "text_extraction_mode": "docling_library",
  "entity_extraction_mode": "docling",
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
```

**Use Cases:**
- Extracting structured data from standardized forms
- Processing documents with known schema
- Fast, deterministic extraction
- Template-driven workflows

**Sample Flow:** [`tests/sample_test_flows/extract/flow_extract_template.json`](../../../../tests/sample_test_flows/extract/flow_extract_template.json)

### 4. LiteLLM Mode

Multi-provider LLM extraction using LiteLLM for accessing 100+ LLM providers (OpenAI, Anthropic, Cohere, etc.).

**Configuration:**
```json
{
  "text_extraction_mode": "docling_library",
  "entity_extraction_mode": "litellm",
  "entity_model_name": "gpt-3.5-turbo",
  "entity_temperature": 0.0,
  "entity_max_tokens": 2000,
  "entity_provider_config": {
    "api_key": "your-api-key",
    "api_base": "https://api.openai.com/v1"
  }
}
```

**Supported Providers:**
- OpenAI (GPT-3.5, GPT-4, GPT-4o)
- Anthropic (Claude 3 Opus, Sonnet, Haiku)
- Cohere (Command, Command-R)
- Google (Gemini Pro, Gemini Ultra)
- Azure OpenAI
- AWS Bedrock
- And 100+ other providers via LiteLLM

**Use Cases:**
- Multi-provider LLM support without code changes
- Enterprise LLM deployments (Azure, AWS Bedrock)
- Cost optimization by switching between providers
- Fallback strategies across multiple providers
- Schema-based and schema-free entity extraction

**Sample Flow:** [`tests/sample_test_flows/extract/flow_extract_basic_litellm.json`](../../../../tests/sample_test_flows/extract/flow_extract_basic_litellm.json)

## Configuration Parameters

### Common Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `text_extraction_mode` | string | `"docling_library"` | Text extraction strategy: `"docling_library"` or `"docling_serve"` |
| `entity_extraction_mode` | string | `"none"` | Entity extraction strategy: `"ollama"`, `"docling"`, `"litellm"`, or `"none"` |
| `doc_column` | string | `"doc_content"` | Column name for storing extracted content |
| `extract_tables` | boolean | `true` | Whether to extract tables from documents |
| `extract_images` | boolean | `true` | Whether to extract images from documents |
| `max_workers` | integer | auto | Maximum number of parallel workers (auto-detected based on CPU) |
| `use_processes` | boolean | `false` | Use ProcessPoolExecutor instead of ThreadPoolExecutor |
| `expand_extracted_data` | boolean | `false` | Expand entity data JSON into individual columns (entity extraction only) |
| `custom_schema` | object | `{}` | Schema dictionary for structured extraction |

### Docling Library Mode Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `use_vlm_pipeline` | boolean | `false` | Enable VLM (Vision-Language Model) pipeline for enhanced extraction |
| `vlm_preset` | string | `"granite_docling"` | VLM preset configuration name (when VLM enabled) |
| `vlm_engine_type` | string | `"transformers"` | VLM engine type (when VLM enabled) |
| `vlm_provider_config` | object | `null` | Provider-specific configuration dictionary (when VLM enabled) |

### Docling Serve Mode Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `docling_serve_base_url` | string | `"http://localhost:5001"` | Docling Serve API endpoint URL |
| `docling_serve_api_key` | string | `null` | Optional API key for authentication |
| `docling_serve_timeout` | integer | `300` | Request timeout in seconds |
| `docling_serve_poll_interval` | integer | `2` | Polling interval in seconds |
| `docling_serve_max_retries` | integer | `3` | Maximum retry attempts |
| `docling_serve_do_ocr` | boolean | `true` | Enable OCR processing |
| `docling_serve_ocr_engine` | string | `"easyocr"` | OCR engine: `"easyocr"` or `"tesseract"` |
| `docling_serve_ocr_languages` | array | `null` | List of OCR languages (e.g., `["en", "es"]`) |
| `docling_serve_pdf_backend` | string | `"dlparse_v2"` | PDF backend: `"dlparse_v4"`, `"dlparse_v3"`, or `"pypdfium2"` |
| `docling_serve_table_mode` | string | `"fast"` | Table extraction mode: `"accurate"` or `"fast"` |
| `docling_serve_image_export_mode` | string | `"placeholder"` | Image export mode: `"embedded"`, `"referenced"`, or `"none"` |

### Ollama Entity Extraction Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `entity_model_name` | string | `"llama3.2"` | Ollama model name |
| `entity_temperature` | float | `0.0` | Sampling temperature (0.0-1.0) |
| `entity_max_tokens` | integer | `4096` | Maximum response tokens |
| `entity_max_doc_chars` | integer | `8000` | Maximum document characters to send to LLM |

### LiteLLM Entity Extraction Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `entity_model_name` | string | `"gpt-3.5-turbo"` | LLM model identifier |
| `entity_temperature` | float | `0.0` | Sampling temperature |
| `entity_max_tokens` | integer | `2000` | Maximum response tokens |

## Input/Output Data Formats

### Input Table Schema

The operator expects a PyArrow table with the following columns:

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `id` | string | Yes | Document identifier |
| `name` | string | Yes | Document name/filename |
| `path` | string | Yes | Document file path |
| `document_type` | string | No | Document type for template selection |

### Output Table Schema

The operator produces a PyArrow table with the following columns:

| Column | Type | Description |
|--------|------|-------------|
| `id` | string | Document identifier |
| `name` | string | Document name |
| `doc_content` | string | Extracted markdown content |
| `doc_id_hash` | string | Hash ID of the document row |
| `entities` | string | Extracted entities as JSON (if entity extraction enabled) |
| `extracted_data` | string | Structured data from template extraction (if applicable) |

When `expand_extracted_data=true` is set for entity extraction, entity fields are expanded into individual columns.

## Usage Examples

### Example 1: Basic Text Extraction Only

```json
{
  
  "operator_params": {
    "text_extraction_mode": "docling_library",
    "entity_extraction_mode": "none",
    "doc_column": "content",
    "extract_tables": true,
    "extract_images": true,
    "max_workers": 4
  }
}
```

### Example 2: Text + Entity Extraction with Ollama

```json
{
  
  "operator_params": {
    "text_extraction_mode": "docling_library",
    "entity_extraction_mode": "ollama",
    "doc_column": "content",
    "entity_model_name": "llama3.2",
    "entity_temperature": 0.0,
    "entity_max_tokens": 4096,
    "custom_schema": {
      "invoice_number": "string",
      "vendor_name": "string",
      "total_amount": "float"
    },
    "max_workers": 2
  }
}
```

### Example 3: VLM Pipeline Text Extraction

```json
{
  
  "operator_params": {
    "text_extraction_mode": "docling_library",
    "entity_extraction_mode": "none",
    "doc_column": "content",
    "use_vlm_pipeline": true,
    "vlm_preset": "granite_docling",
    "vlm_engine_type": "transformers",
    "max_workers": 1
  }
}
```

### Example 4: Docling Serve with OCR

```json
{
  
  "operator_params": {
    "text_extraction_mode": "docling_serve",
    "entity_extraction_mode": "none",
    "doc_column": "content",
    "docling_serve_base_url": "http://localhost:5001",
    "docling_serve_do_ocr": true,
    "docling_serve_ocr_engine": "easyocr",
    "docling_serve_ocr_languages": ["en", "es"],
    "docling_serve_pdf_backend": "dlparse_v4",
    "docling_serve_table_mode": "accurate",
    "max_workers": 4
  }
}
```

### Example 5: Template-Based Entity Extraction

```json
{
  
  "operator_params": {
    "text_extraction_mode": "docling_library",
    "entity_extraction_mode": "docling",
    "doc_column": "content",
    "custom_schema": {
      "type": "object",
      "properties": {
        "invoice_number": { "type": "string" },
        "invoice_date": { "type": "string" },
        "total_amount": { "type": "number" }
      }
    },
    "max_workers": 2
  }
}
```

### Example 6: VLM Pipeline + Ollama Entity Extraction

```json
{
  
  "operator_params": {
    "text_extraction_mode": "docling_library",
    "entity_extraction_mode": "ollama",
    "doc_column": "content",
    "use_vlm_pipeline": true,
    "vlm_preset": "granite_docling",
    "vlm_engine_type": "transformers",
    "entity_model_name": "llama3.2",
    "entity_temperature": 0.0,
    "max_workers": 1
  }
}
```

## Integration Requirements

### Ollama Integration (for Ollama entity extraction)

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

**Used By:** Entity extraction when `entity_extraction_mode="ollama"`

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

**Used By:** Text extraction when `text_extraction_mode="docling_serve"`

## Mode Comparison

| Feature | Docling Library (Basic) | Docling Library (VLM) | Docling Serve |
|---------|-------------------------|----------------------|---------------|
| **Processing Location** | Local | Local/API | Remote API |
| **OCR Support** | No | Limited | Yes (EasyOCR, Tesseract) |
| **Multi-language OCR** | No | No | Yes |
| **Scalability** | Low | Medium | High |
| **Setup Complexity** | Low | Medium | Medium |
| **Processing Speed** | Fast | Slow | Medium |
| **Accuracy** | Good | Excellent | Excellent |
| **External Dependencies** | None | Model files | Docker container |

| Feature | Ollama | Docling | LiteLLM |
|---------|--------|---------|---------|
| **Processing Location** | Local | Local | Remote API |
| **Schema Support** | Yes | Yes | Yes |
| **Schema-Free Mode** | Yes | No | Yes |
| **Setup Complexity** | Medium | Low | Low |
| **Processing Speed** | Medium | Fast | Fast |
| **Accuracy** | High | Good | High |
| **External Dependencies** | Ollama server | None | API keys |

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

**Use Ollama Mode When:**
- Flexible entity extraction without predefined templates
- Complex document understanding required
- Local LLM processing preferred
- Schema-based or schema-free extraction needed

**Use Docling Mode When:**
- Extracting structured data from standardized forms
- Processing documents with known schema
- Fast, deterministic extraction required
- Template-driven workflows

**Use LiteLLM Mode When:**
- Multi-provider LLM support needed
- Cloud-based LLM processing preferred
- (Note: Currently a placeholder implementation)

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
- Verify the `text_extraction_mode` value is valid: `"docling_library"` or `"docling_serve"`
- For VLM pipeline (`use_vlm_pipeline=true`), ensure required model files are available
- For Docling Serve mode, verify the service is running and accessible

**Issue: "Failed to initialize entity extraction adapter"**
- Verify the `entity_extraction_mode` value is valid: `"ollama"`, `"docling"`, `"litellm"`, or `"none"`
- For Ollama mode, ensure Ollama server is running and the model is pulled
- Check that required parameters (model_name, etc.) are provided

**Issue: "Ollama connection refused"**
- Verify Ollama is running: `curl http://localhost:11434/api/tags`
- Check that the specified model is available: `ollama list`
- Ensure no firewall is blocking port 11434

**Issue: "Docling Serve timeout"**
- Increase `docling_serve_timeout` value
- Check Docling Serve service health: `curl http://localhost:5001/health`
- Verify network connectivity to the Docling Serve endpoint

**Issue: "Entity extraction returns empty results"**
- Verify document content is not empty after text extraction
- Check `entity_max_doc_chars` is not too restrictive
- For schema-based extraction, ensure the schema matches the document structure
- Review LLM model capabilities for the extraction task

## Architecture Details

### Hexagonal Architecture

The ExtractOperator follows hexagonal architecture (ports and adapters pattern):

```
ExtractOperator (Orchestrator)
    ↓
TextExtractionPort (Interface)
    ↓
├── DoclingAdapter (docling_library mode, with optional VLM pipeline)
└── DoclingServeAdapter (docling_serve mode)

EntityExtractionPort (Interface)
    ↓
├── OllamaEntityAdapter (ollama mode)
├── DoclingEntityAdapter (docling mode)
└── LiteLLMEntityAdapter (litellm mode)
```

### Execution Flow

1. **Initialization:**
   - Parse extraction modes from configuration
   - Create text extraction adapter via factory
   - Create entity extraction adapter via factory (if enabled)

2. **Text Extraction:**
   - Delegate to text extraction adapter
   - Process documents in parallel using worker pool
   - Collect extracted content and metadata

3. **Entity Extraction (if enabled):**
   - Delegate to entity extraction adapter
   - Process extracted text in parallel
   - Extract structured entities based on schema or LLM

4. **Result Assembly:**
   - Combine text and entity extraction results
   - Update metadata with processing statistics
   - Return transformed PyArrow table

## Related Documentation

- [Docling Documentation](https://github.com/DS4SD/docling)
- [Ollama Documentation](https://ollama.com/docs)
- [Sample Flows](../../../../tests/sample_test_flows/extract/)