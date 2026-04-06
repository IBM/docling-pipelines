# Examples

This directory contains example scripts demonstrating various operators in the datasift-opensource project.

## Operator Examples

### Core Operators

#### [`operator_metadata_example.py`](operator_metadata_example.py)
Demonstrates how to retrieve metadata for all available operators in the framework.

```bash
python examples/operator_metadata_example.py
```

#### [`noop_operator_example.py`](noop_operator_example.py)
Shows the NOOP (No Operation) operator, useful for testing and debugging pipelines.

```bash
python examples/noop_operator_example.py
```

### Ingestion Operators

#### [`ingest_local_folder_example.py`](ingest_local_folder_example.py)
Demonstrates ingesting documents from a local folder.

```bash
python examples/ingest_local_folder_example.py
```

#### [`ingest_source_example.py`](ingest_source_example.py)
Shows multi-provider ingestion from cloud sources (Google Drive, S3, OneDrive, SharePoint).

```bash
python examples/ingest_source_example.py
```

### Extraction Operators

#### [`extract_docling_example.py`](extract_docling_example.py)
Demonstrates document content extraction using Docling (supports PDFs, DOCX, etc.).
Supports both basic markdown extraction and template-based structured extraction.

```bash
python examples/extract_docling_example.py
```

#### [`extract_docling_serve_example.py`](extract_docling_serve_example.py)
Demonstrates document extraction using the Docling-Serve REST API. Provides scalable document processing with support for OCR, table extraction, and multiple PDF backends.

**Prerequisites:**
```bash
# Start docling-serve locally
docker run -p 5001:5001 ds4sd/docling-serve:latest
```

**Usage:**
```bash
python examples/extract_docling_serve_example.py
```

**Features:**
- REST API-based document processing
- OCR support with EasyOCR and Tesseract engines
- Multiple PDF backends (dlparse_v4, dlparse_v3, pypdfium2)
- Configurable table extraction modes (accurate/fast)
- Multi-language OCR support
- Scalable for production workloads

### Functional Operators

#### [`chunker_example.py`](chunker_example.py)
Shows different chunking strategies: simple, semantic, and hybrid chunking.
Includes a complete pipeline: Ingest → Extract → Chunk.

```bash
python examples/chunker_example.py
```

#### [`embeddings_pipeline_example.py`](embeddings_pipeline_example.py)
Complete end-to-end pipeline: Ingest → Extract → Chunk → Embeddings.
Automatically handles Ollama setup and model management.

```bash
# Use default settings
python examples/embeddings_pipeline_example.py

# Specify custom PDF and model
python examples/embeddings_pipeline_example.py --pdf tests/fixtures/invoices/TR-INV_001_3_2.1.pdf --model mistral

# Skip automatic Ollama setup
python examples/embeddings_pipeline_example.py --no-auto-setup
```

### Quality Operators

#### [`deduplication_example.py`](deduplication_example.py)
Demonstrates removing duplicate documents based on content.

```bash
python examples/deduplication_example.py
```

#### [`language_detection_example.py`](language_detection_example.py)
Shows basic language detection for documents.

```bash
python examples/language_detection_example.py
```

#### [`language_detection_fasttext_example.py`](language_detection_fasttext_example.py)
Demonstrates FastText-based language detection supporting 176 languages.

```bash
python examples/language_detection_fasttext_example.py
```

#### [`ml_enrichment_example.py`](ml_enrichment_example.py)
Shows ML-based document enrichment with quality metrics (word counts, character ratios, etc.).
Supports multiple languages (English, Spanish, French, etc.).

```bash
python examples/ml_enrichment_example.py
```

#### [`readability_example.py`](readability_example.py)
Demonstrates calculating readability scores (Flesch Reading Ease, Flesch-Kincaid Grade Level, etc.).

```bash
python examples/readability_example.py
```

#### [`redaction_example.py`](redaction_example.py)
Shows how to redact sensitive information (SSN, emails, etc.) using regex patterns.

```bash
python examples/redaction_example.py
```

#### [`pii_hap_detection_example.py`](pii_hap_detection_example.py)
Demonstrates detection of Personally Identifiable Information (PII) and Hate, Abuse, and Profanity (HAP).

```bash
python examples/pii_hap_detection_example.py
```

### Vector Database Integration

#### [`opensearch_integration_example.py`](opensearch_integration_example.py)
Comprehensive OpenSearch integration example showing:
- Document indexing with different engines (FAISS, Lucene, NMSLIB)
- Query and delete operations
- Batch processing
- Error handling

See [`opensearch_example_README.md`](opensearch_example_README.md) for detailed documentation.

```bash
python examples/opensearch_integration_example.py
```

## Prerequisites

### General Requirements
```bash
cd src/datasift_opensource/backend
uv sync --extra dev
```

### Ollama (for embeddings examples)
The embeddings pipeline example requires Ollama for generating embeddings:

```bash
# Install Ollama (macOS)
brew install ollama

# Start Ollama server
ollama serve

# Pull a model
ollama pull granite4
```

### OpenSearch (for vector database examples)
See [`opensearch_example_README.md`](opensearch_example_README.md) for OpenSearch setup instructions.

## Running Examples

All examples can be run directly from the project root:

```bash
# Run from project root
python examples/<example_name>.py

# Or with full path
python examples/embeddings_pipeline_example.py --pdf tests/fixtures/invoices/
```

## Creating Your Own Examples

1. Copy an existing example as a template
2. Modify the operator configuration
3. Adjust input data and parameters
4. Test locally before deployment

## Common Patterns

### Basic Operator Usage
```python
from core.operators.some_operator import SomeOperator

# 1. Configure the operator
config = {
    "param1": "value1",
    "param2": "value2"
}

# 2. Initialize the operator
operator = SomeOperator(config)

# 3. Prepare input data (PyArrow table)
input_table = pa.table({"column": ["data"]})

# 4. Transform the data
output_tables, metadata = operator.transform(input_table)

# 5. Process results
result_table = output_tables[0]
print(f"Processed {result_table.num_rows} rows")
```

### Pipeline Pattern
```python
# Chain multiple operators
ingest_tables, _ = ingest_operator.transform(None)
extract_tables, _ = extract_operator.transform(ingest_tables[0])
chunk_tables, _ = chunk_operator.transform(extract_tables[0])
embeddings_tables, _ = embeddings_operator.transform(chunk_tables[0])
```

## Additional Resources

- [OpenSearch Quick Start](../docs/opensearch/OPENSEARCH_QUICKSTART.md)
- [Environment Setup Guide](../docs/opensearch/ENVIRONMENT_SETUP.md)
- [Operator Documentation](../docs/operators/)