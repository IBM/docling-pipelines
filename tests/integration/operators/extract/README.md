# ExtractOperator Integration Tests

This directory contains integration tests for the unified `ExtractOperator` that uses hexagonal architecture to support multiple extraction strategies.

## Overview

The ExtractOperator supports two types of extraction:
- **Text Extraction**: Converting documents to markdown (docling_library or docling_serve modes)
- **Entity Extraction**: Extracting structured data from text (ollama, docling, or litellm modes)

These integration tests verify the operator works with real extraction scenarios, including actual document processing and parallel execution.

## Architecture

The operator follows hexagonal architecture (ports and adapters pattern) with clear separation of concerns:

**Layers:**
- **Domain Layer**: `EntityExtractionService` handles business logic (prompt building, schema validation, response parsing)
- **Port Layer**: `TextExtractionPort` and `EntityExtractionPort` define extraction interfaces
- **Adapter Layer**: Concrete implementations for different extraction strategies
  - Text: `DoclingAdapter` (docling_library), `DoclingServeAdapter` (docling_serve)
  - Entity: `LLMEntityAdapter` (unified for litellm/watsonx), `DoclingEntityAdapter` (docling)
- **Factory Layer**: `TextExtractionAdapterFactory` and `EntityExtractionAdapterFactory` create adapters based on mode
- **Operator**: Thin wrapper handling configuration and delegation

**Key Benefits:**
- Easy addition of new extraction strategies by implementing ports
- Clear separation between business logic, interfaces, and implementations
- Unified LLM support: Both `litellm` and `watsonx` modes use the same `LLMEntityAdapter`

## Test Coverage

The integration test suite (`test_extract_operator_integration.py`) covers:

### Basic Integration Tests
- ✅ Basic text extraction with PyArrow tables
- ✅ Template-based entity extraction
- ✅ VLM-enhanced text extraction
- ✅ Docling Serve remote API extraction
- ✅ Parallel processing with multiple workers
- ✅ Error handling with invalid documents
- ✅ Metadata propagation through pipeline

### Real-World Tests
- ✅ Extraction from real PDF documents
- ✅ Docling Serve with OCR on scanned documents
- ✅ VLM extraction on complex layouts
- ✅ Template extraction with data expansion

## Prerequisites

### For Text Extraction Tests

**Docling Library Mode (Default):**
- No external dependencies required
- Docling library installed via project dependencies

**Docling Serve Mode:**
- Docling Serve running on `http://localhost:5001`

```bash
# Start docling-serve
docker run -p 5001:5001 ds4sd/docling-serve:latest

# Verify it's running
curl http://localhost:5001/health
```

### For Entity Extraction Tests

**LiteLLM Mode (including Ollama):**
- For Ollama via LiteLLM: Ollama server running on `http://localhost:11434`
- For other providers: API keys configured in `entity_extraction.provider_config`

```bash
# For Ollama setup
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull model
ollama pull llama3.2

# Verify Ollama is running
curl http://localhost:11434/api/tags
```

**Docling Mode:**
- No external dependencies required
- Uses Docling's template-based extraction

**WatsonX Mode:**
- WatsonX API credentials configured
- Environment variables: `WATSONX_API_KEY`, `WATSONX_CONTAINER_ID`

## Running the Tests

### Setup Environment

```bash
# Activate virtual environment (from repo root)
source .venv/bin/activate

# Sync dependencies (if needed)
uv sync --extra dev
```

### Run All Integration Tests

```bash
# Run all extract operator integration tests (from repo root)
uv run pytest tests/integration/operators/extract/test_extract_operator_integration.py -v

# Run with integration marker
uv run pytest tests/integration/operators/extract/ -v -m integration
```

### Run Specific Test Classes

```bash
# Basic integration tests
uv run pytest tests/integration/operators/extract/test_extract_operator_integration.py::TestExtractOperatorIntegration -v

# Real-world integration tests
uv run pytest tests/integration/operators/extract/test_extract_operator_integration.py::TestExtractOperatorRealWorld -v
```

### Run Specific Test Methods

```bash
# Test basic extraction
uv run pytest tests/integration/operators/extract/test_extract_operator_integration.py::TestExtractOperatorIntegration::test_basic_extraction_integration -v

# Test parallel processing
uv run pytest tests/integration/operators/extract/test_extract_operator_integration.py::TestExtractOperatorIntegration::test_parallel_processing_with_multiple_workers -v

# Test error handling
uv run pytest tests/integration/operators/extract/test_extract_operator_integration.py::TestExtractOperatorIntegration::test_error_handling_with_invalid_documents -v

# Test template extraction with expansion
uv run pytest tests/integration/operators/extract/test_extract_operator_integration.py::TestExtractOperatorRealWorld::test_template_extraction_with_expansion -v
```

### Run with Verbose Output

```bash
# Show detailed output including print statements
uv run pytest tests/integration/operators/extract/test_extract_operator_integration.py -v -s
```

## Test Fixtures

Tests use sample documents from `tests/fixtures/`:
- `tests/fixtures/invoices/TR-INV_044_1_1.1.pdf` - Primary test document
- `tests/fixtures/invoices/TR-INV_001_3_2.1.pdf` - Secondary test document
- `tests/fixtures/invoices/TR-INV_003_3_2.1.pdf` - Tertiary test document

## Skip Conditions

Many tests are skipped by default because they require external dependencies:

1. **Docling Library Tests**: Skipped if Docling dependencies not available
2. **VLM Tests**: Skipped - require VLM models and GPU resources
3. **Docling Serve Tests**: Skipped - require Docling Serve running on localhost:5001
4. **Real PDF Tests**: Skipped - require actual PDF files and Docling installation

To run skipped tests, ensure prerequisites are met and remove the `@pytest.mark.skip` decorator.

## Extraction Modes

### Text Extraction Modes

**1. Docling Library (Default)**
```json
{
    "text_extraction": {
        "provider": "docling_library",
        "doc_column": "document",
        "provider_config": {
        }
    },
    "entity_extraction": {
        "provider": "none"
    },
    "max_workers": 4
}
```

**2. Docling Library with VLM Pipeline**
```json
{
    "text_extraction": {
        "provider": "docling_library",
        "doc_column": "document",
        "provider_config": {
            "vlm_pipeline": {
                "preset": "granite_docling",
                "engine": "transformers",
                "engine_options": {
                    "model_id": "microsoft/Florence-2-large"
                }
            }
        }
    },
    "entity_extraction": {
        "provider": "none"
    },
    "max_workers": 1
}
```

**3. Docling Serve**
```json
{
    "text_extraction": {
        "provider": "docling_serve",
        "doc_column": "document",
        "provider_config": {
            "base_url": "http://localhost:5001",
            "timeout": 300,
            "do_ocr": true
        }
    },
    "entity_extraction": {
        "provider": "none"
    }
}
```

### Entity Extraction Modes

**1. None (Default)**
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

**2. LiteLLM (with Ollama via OpenAI-compatible API)**
```json
{
    "text_extraction": {
        "provider": "docling_library",
        "doc_column": "content"
    },
    "entity_extraction": {
        "provider": "litellm",
        "max_doc_chars": 50000,
        "provider_config": {
            "model_id": "openai/llama3.2",
            "api_base": "http://localhost:11434/v1",
            "api_key": "<ollama_key>",
            "temperature": 0.0
        },
        "custom_schema": {
            "invoice_number": "string",
            "total_amount": "float"
        }
    }
}
```

**Note:** When using LiteLLM, `model_id` **must include provider prefix** (e.g., `openai/llama3.2` for Ollama, `openai/gpt-4`, `anthropic/claude-3-opus`).

**3. Docling (Template-Based)**
```json
{
    "text_extraction": {
        "provider": "docling_library",
        "doc_column": "content"
    },
    "entity_extraction": {
        "provider": "docling",
        "custom_schema": {
            "type": "object",
            "properties": {
                "invoice_number": {"type": "string"},
                "total_amount": {"type": "number"}
            }
        }
    }
}
```

## Troubleshooting

### Tests are Skipped

Most integration tests are skipped by default. To run them:

1. **Install required dependencies**:
   ```bash
   # From repo root
   uv sync --extra dev
   ```

2. **Start external services** (if needed):
   ```bash
   # For Docling Serve tests
   docker run -p 5001:5001 ds4sd/docling-serve:latest

   # For Ollama tests
   ollama serve
   ollama pull llama3.2
   ```

3. **Remove skip decorators** from tests you want to run

### Connection Errors

**Docling Serve Connection Issues:**
```bash
# Verify service is running
curl http://localhost:5001/health

# Check if port is in use
lsof -i :5001

# Restart service
docker restart <container-id>
```

**Ollama Connection Issues:**
```bash
# Verify Ollama is running
curl http://localhost:11434/api/tags

# Check if model is available
ollama list

# Restart Ollama
ollama serve
```

### Import Errors

```bash
# Verify imports work (from repo root with activated .venv)
python -c "from docpipe.core.operators.extract.extract_operator import ExtractOperator; print('OK')"
```

### Timeout Errors

If tests timeout:
1. Increase timeout values in test configuration
2. Check service logs for processing issues
3. Try with smaller or simpler documents
4. Reduce `max_workers` to avoid overwhelming services

## Performance Notes

- **Basic extraction**: ~2-5 seconds per document
- **VLM extraction**: ~10-30 seconds per document (GPU-dependent)
- **Docling Serve with OCR**: ~5-15 seconds per document
- **Entity extraction with Ollama**: ~2-10 seconds per document

Actual times depend on:
- Document complexity
- Number of pages
- Table/image count
- OCR requirements
- Server resources
- Model size (for LLM-based extraction)

## Related Documentation

- [ExtractOperator README](../../../../docs/operators/extract/extract_operator_readme.md) - Complete operator documentation
- [ExtractOperator Source](../../../../src/docpipe/core/operators/extract/extract_operator.py) - Operator implementation
- [Sample Flows](../../../../sample_flows/) - Example flow configurations
- [Docling Documentation](https://github.com/DS4SD/docling) - Docling library docs
- [Ollama Documentation](https://ollama.com/docs) - Ollama setup and usage
