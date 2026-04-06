# Extract Operators

This directory contains operators for extracting content and structure from various document formats.

## Available Operators

### ExtractDoclingOperator

The `ExtractDoclingOperator` provides flexible document extraction with multiple processing modes:

1. **Basic Mode**: Standard markdown extraction using Docling library
2. **VLM Pipeline Mode**: Vision Language Model enhanced extraction
3. **Template-Based Mode**: Structured data extraction using predefined templates
4. **Docling-Serve Mode**: REST API-based extraction for scalable processing

## Extraction Modes

### 1. Basic Mode (Default)

Standard document extraction using the Docling library locally.

**Configuration:**
```python
config = {
    "doc_column": "content",
    "doc_id_hash": "doc_id",
    "extract_tables": True,
    "extract_images": True
}
```

**Use Cases:**
- Simple document conversion to markdown
- Local processing without external dependencies
- Quick prototyping and testing

### 2. VLM Pipeline Mode

Enhanced extraction using Vision Language Models for better understanding of document structure and content.

**Configuration:**
```python
config = {
    "doc_column": "content",
    "use_vlm_pipeline": True,
    "vlm_preset": "granite_docling",
    "vlm_engine_type": "transformers",  # or "mlx", "api", etc.
    "vlm_api_base_url": None,  # Required for API engines
    "vlm_api_key": None  # Required for some API engines
}
```

**Supported VLM Engines:**
- `transformers`: Local inference using Transformers library
- `mlx`: Local inference optimized for macOS (Apple Silicon)
- `api`: Generic API endpoint
- `api_lmstudio`: LMStudio API
- `api_ollama`: Ollama API
- `api_openai`: OpenAI API
- `api_watsonx`: IBM watsonx.ai API

**Use Cases:**
- Complex document layouts
- Documents with mixed content types
- High-accuracy extraction requirements

### 3. Template-Based Mode

Structured data extraction using predefined JSON templates.

**Configuration:**
```python
config = {
    "doc_column": "content",
    "use_template": True,
    "template": {
        "invoice_number": "string",
        "invoice_date": "string",
        "total": "float"
    }
}
```

**Use Cases:**
- Extracting structured data from forms
- Invoice processing
- Standardized document types

### 4. Docling-Serve Mode

REST API-based extraction using the Docling-Serve service for scalable, production-ready document processing.

> **Docling-Serve API compatibility:** The current operator integration targets the Docling-Serve v1 async API. It submits documents to `/v1/convert/file/async`, polls `/v1/status/poll/{task_id}`, and retrieves output from `/v1/result/{task_id}`.

**Configuration:**
```python
config = {
    "doc_column": "content",
    "use_docling_serve": True,
    "docling_serve_base_url": "http://0.0.0.0:5001",
    "docling_serve_api_key": None,  # Optional
    "docling_serve_timeout": 300,
    "docling_serve_poll_interval": 2,
    "docling_serve_max_retries": 3,
    # OCR Configuration
    "docling_serve_do_ocr": True,
    "docling_serve_ocr_engine": "easyocr",  # or "tesseract"
    "docling_serve_ocr_languages": ["en"],
    # PDF Processing
    "docling_serve_pdf_backend": "dlparse_v4",  # or "dlparse_v3", "pypdfium2"
    "docling_serve_table_mode": "accurate",  # or "fast"
    "docling_serve_image_export_mode": "embedded"  # or "referenced", "none"
}
```

**v1 API request model:**
- Documents are uploaded as **multipart/form-data**
- The file is sent in the `files` field
- Processing options are sent as form fields
- The service returns a `task_id` for async tracking

**v1 API response model:**
- Polling responses use `task_status` with lowercase values such as `pending`, `processing`, and `success`
- Result payloads return extracted markdown in `document.md_content`

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
- **Scalability**: Horizontal scaling for production workloads
- **Async Processing**: Non-blocking document processing
- **Error Handling**: Automatic retries and timeout management

**Use Cases:**
- Production document processing pipelines
- High-volume document ingestion
- Scanned document processing with OCR
- Multi-language document processing
- Distributed processing architectures

## Mode Comparison

| Feature | Basic | VLM Pipeline | Template | Docling-Serve |
|---------|-------|--------------|----------|---------------|
| **Processing Location** | Local | Local/API | Local | Remote API |
| **OCR Support** | No | Limited | No | Yes (EasyOCR, Tesseract) |
| **Structured Extraction** | No | Yes | Yes | Yes |
| **Multi-language OCR** | No | No | No | Yes |
| **Scalability** | Low | Medium | Low | High |
| **Setup Complexity** | Low | Medium | Low | Medium |
| **Processing Speed** | Fast | Slow | Fast | Medium |
| **Accuracy** | Good | Excellent | Good | Excellent |
| **External Dependencies** | None | Model files | None | Docker container |

## When to Use Each Mode

### Use Basic Mode When:
- Processing simple documents locally
- No OCR required
- Quick prototyping
- Minimal setup needed

### Use VLM Pipeline Mode When:
- Complex document layouts
- High accuracy requirements
- Local processing preferred
- GPU available for inference

### Use Template Mode When:
- Extracting structured data
- Processing standardized forms
- Known document schema
- Fast processing needed

### Use Docling-Serve Mode When:
- Production deployment
- OCR required for scanned documents
- Multi-language support needed
- Horizontal scaling required
- Processing high document volumes
- Distributed architecture

## Configuration Examples

### Example 1: Basic Extraction
```python
from core.operators.extract.extract_docling import ExtractDoclingOperator

config = {
    "doc_column": "content",
    "extract_tables": True,
    "extract_images": True
}

operator = ExtractDoclingOperator(config)
result_tables, metadata = operator.transform(input_table)
```

### Example 2: Docling-Serve with OCR
```python
config = {
    "doc_column": "content",
    "use_docling_serve": True,
    "docling_serve_base_url": "http://0.0.0.0:5001",
    "docling_serve_do_ocr": True,
    "docling_serve_ocr_engine": "easyocr",
    "docling_serve_ocr_languages": ["en", "es", "fr"],
    "docling_serve_pdf_backend": "dlparse_v4",
    "docling_serve_table_mode": "accurate"
}

operator = ExtractDoclingOperator(config)
result_tables, metadata = operator.transform(input_table)
```

### Example 3: v1 API Interaction
```bash
# Submit a document
curl -X POST http://localhost:5001/v1/convert/file/async \
  -F "files=@/path/to/document.pdf" \
  -F "to_formats=md" \
  -F "do_ocr=true" \
  -F "pdf_backend=dlparse_v4"

# Poll task status
curl http://localhost:5001/v1/status/poll/<task_id>

# Fetch result
curl http://localhost:5001/v1/result/<task_id>
```

### Example 4: Reading v1-Compatible Metadata
```python
result_tables, metadata = operator.transform(input_table)

print(metadata["processed_docs"])
print(metadata["failed_docs_count"])  # Integer count
print(metadata["failed_docs"])        # List of failed document entries
```

## Notes

- Legacy docling-serve API paths such as `/convert/submit`, `/convert/status/{task_id}`, and `/convert/result/{task_id}` are no longer accurate for this integration.
- Older JSON submission examples using base64-encoded file content are not compatible with the current client.
- If you need detailed operational guidance, troubleshooting, or expanded examples, see [docs/operators/extract_docling_serve.md](../../../../../../docs/operators/extract_docling_serve.md).