# Examples

This directory contains example scripts demonstrating various operators in the docpipe project.

## Environment Variables for Credentials

Some examples require API credentials (e.g., VLM engines like Watsonx, OpenAI). These should be stored in a `.env` file in the **project root** for security.

**Setup:**

1. Copy `.env.example` to `.env` in the project root:

   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your credentials:

   ```bash
   # For Watsonx AI
   WATSONX_API_KEY=your_api_key_here
   WATSONX_CONTAINER_KIND=project  # optional: project, space, or catalog
   WATSONX_CONTAINER_ID=your_project_or_space_id_here
   WATSONX_MODEL=your_model_id_here  # required - specify your model

   # For Watsonx AI (Entity extraction)
   WATSONX_ENTITY_MODEL=your_model_id_here  # required - specify your model
   WATSONX_API_BASE=https://us-south.ml.cloud.ibm.com  # optional, has default

   # For OpenAI
   OPENAI_API_KEY=your_api_key_here

   # For Generic API
   GENERIC_API_BASE_URL=https://your-api.com/v1/chat
   ```

3. The `.env` file is automatically loaded by examples that need credentials

**Security Note:** Never commit `.env` files to version control. The `.gitignore` file already excludes them.

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

#### [`ingest_filesystem_example.py`](ingest_filesystem_example.py)

Demonstrates ingesting documents from a local folder using `ingest_source` with the `filesystem` provider.

```bash
python examples/ingest_filesystem_example.py
```

#### [`ingest_source_example.py`](ingest_source_example.py)

Shows multi-provider ingestion from cloud sources (Google Drive, S3, OneDrive, SharePoint).

```bash
python examples/ingest_source_example.py
```

### Extraction Operators

#### ExtractOperator

Demonstrates document content extraction using Docling (supports PDFs, DOCX, etc.).
Supports both basic markdown extraction and template-based structured extraction.

See [`extract_operator_example.py`](extract_operator_example.py) and [`docs/operators/extract/extract_operator_readme.md`](../docs/operators/extract/extract_operator_readme.md) for details.

```bash
python examples/extract_operator_example.py
```

#### ExtractOperator with Docling Serve provider

Demonstrates document extraction using the Docling-Serve REST API. Provides scalable document processing with support for OCR, table extraction, and multiple PDF backends.

**Prerequisites:**

```bash
# Start docling-serve locally
docker run -p 5001:5001 ds4sd/docling-serve:latest
```

**Usage:**

```bash
python examples/extract_operator_example.py
```

**Features:**

- REST API-based document processing
- OCR support with EasyOCR and Tesseract engines
- Multiple PDF backends (dlparse_v4, dlparse_v3, pypdfium2)
- Configurable table extraction modes (accurate/fast)
- Multi-language OCR support
- Scalable for production workloads

#### [`extract_operator_example.py`](extract_operator_example.py)

Comprehensive examples of document extraction with independent text and entity extraction providers. Demonstrates the ExtractOperator's flexible architecture where text extraction and entity extraction are independent dimensions that can be combined in multiple ways.

**Text Extraction Providers:**

- **Basic**: Docling Library provider - standard extraction (fast)
- **VLM**: Docling Library with VLM pipeline - vision-enhanced extraction with 7 engine options
- **ASR**: Docling Library with ASR pipeline - audio/video transcription with Whisper models
- **Serve**: Docling Serve API - remote extraction for scalable production workloads

**Entity Extraction Providers:**

- **None**: Text extraction only (default)
- **LiteLLM**: Multi-provider LLM entity extraction (OpenAI, Anthropic, Cohere, Ollama via openai/ prefix, etc.)
- **WatsonX**: IBM WatsonX AI LLM-based entity extraction
- **Docling**: Template-based entity extraction with JSON schemas

**Supported VLM Engines:**

- **Transformers**: Local inference (GPU recommended) - no credentials needed
- **MLX**: macOS Apple Silicon optimized - no credentials needed
- **Ollama**: Local or remote API - no credentials needed
- **LM Studio**: Local API server - no credentials needed
- **Watsonx AI**: IBM Cloud enterprise - **requires credentials in `.env`**
- **OpenAI**: Cloud-based API - **requires credentials in `.env`**
- **Generic API**: Custom endpoints - **requires credentials in `.env`**

> **Note:** When using VLM engines in flow JSON configurations, use these engine values:
> - Transformers → `"engine": "transformers"`
> - MLX → `"engine": "mlx"`
> - Ollama → `"engine": "api_ollama"`
> - LM Studio → `"engine": "api_lmstudio"`
> - Watsonx AI → `"engine": "api_watsonx"`
> - OpenAI → `"engine": "api_openai"`
> - Generic API → `"engine": "api"`

**Prerequisites:**

```bash
# For basic text extraction
pip install docling

# For VLM text extraction (Transformers/MLX)
pip install docling[vlm]

# For ASR audio/video transcription
pip install docling[asr]
# For M4A, AAC, OGG, FLAC, and video formats, also install ffmpeg:
brew install ffmpeg  # macOS
# apt-get install ffmpeg  # Linux

# For LiteLLM with Ollama (VLM or entity extraction)
brew install ollama
ollama serve
ollama pull ibm/granite-docling:258m  # For VLM text extraction
ollama pull llama3.2          # For entity extraction

# For Docling Serve
docker run -p 5001:5001 ds4sd/docling-serve:latest

# For Watsonx, OpenAI, or Generic API engines
# Add credentials to .env file (see "Environment Variables" section above)
```

**Usage:**

```bash
# Activate venv and set PYTHONPATH
cd src/docpipe_app/backend
source .venv/bin/activate
PYTHONPATH=. python ../../../examples/extract_operator_example.py [OPTIONS]

# Text extraction only (basic, default)
PYTHONPATH=. python ../../../examples/extract_operator_example.py

# VLM text extraction with Ollama
PYTHONPATH=. python ../../../examples/extract_operator_example.py --text-mode vlm --vlm-engine ollama

# ASR audio/video transcription
PYTHONPATH=. python ../../../examples/extract_operator_example.py --text-mode asr --asr-model whisper_turbo

# ASR with Apple Silicon optimization
PYTHONPATH=. python ../../../examples/extract_operator_example.py --text-mode asr --asr-model whisper_small_mlx

# Docling Serve text extraction
PYTHONPATH=. python ../../../examples/extract_operator_example.py --text-mode serve

# Basic text + LiteLLM entity extraction with Ollama (no schema - free-form)
PYTHONPATH=. python ../../../examples/extract_operator_example.py --entity-mode litellm

# Basic text + LiteLLM entity extraction with Ollama and custom schema
PYTHONPATH=. python ../../../examples/extract_operator_example.py --entity-mode litellm --schema '{"invoice_number": "string", "total_amount": "float"}'

# Basic text + WatsonX entity extraction with custom schema
PYTHONPATH=. python ../../../examples/extract_operator_example.py --entity-mode watsonx --schema '{"invoice_number": "string", "total_amount": "float"}'

# Basic text + Docling template entity extraction (schema required)
PYTHONPATH=. python ../../../examples/extract_operator_example.py --entity-mode docling --schema '{"type": "object", "properties": {"invoice_number": {"type": "string"}}}'

# VLM text + LiteLLM entity extraction with schema
PYTHONPATH=. python ../../../examples/extract_operator_example.py --text-mode vlm --entity-mode litellm --schema '{"vendor": "string", "amount": "float"}'

# Docling Serve + LiteLLM entity extraction (no schema)
PYTHONPATH=. python ../../../examples/extract_operator_example.py --text-mode serve --entity-mode litellm

# Custom PDF
PYTHONPATH=. python ../../../examples/extract_operator_example.py --pdf path/to/document.pdf

# VLM with Watsonx (requires WATSONX_* in .env)
PYTHONPATH=. python ../../../examples/extract_operator_example.py --text-mode vlm --vlm-engine watsonx

# VLM with OpenAI (requires OPENAI_API_KEY in .env)
PYTHONPATH=. python ../../../examples/extract_operator_example.py --text-mode vlm --vlm-engine openai

# VLM with Generic API (requires GENERIC_API_BASE_URL in .env)
PYTHONPATH=. python ../../../examples/extract_operator_example.py --text-mode vlm --vlm-engine generic
```

**Key Features:**

- **Independent modes**: Text and entity extraction can be combined flexibly
- **VLM text extraction**: Enhanced table extraction, complex layouts, visual elements
- **ASR transcription**: Audio and video file transcription with Whisper models
- **Entity extraction**: Structured data extraction with custom schemas
- **Multiple providers**: Support for local (LiteLLM with Ollama), cloud (LiteLLM, WatsonX) LLMs
- **Template-based extraction**: Fast, deterministic extraction with Docling templates

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

Shows basic language detection for documents using the default FastText provider.

```bash
python examples/language_detection_example.py
```

#### `language_detection_fasttext_example.py`

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

### Storage Operators

#### [`document_set_example.py`](document_set_example.py)

Demonstrates the DocumentSetOperator with hexagonal architecture:

- Creating document sets with metadata
- Storing PyArrow table data
- Querying and previewing documents
- Getting statistics
- Using DuckDB backend (default)

```bash
python examples/document_set_example.py
```

**Features Demonstrated**:

- Hexagonal architecture (ports and adapters)
- DuckDB storage backend
- Metadata and data separation
- PyArrow table operations
- Document set CRUD operations

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
# From project root
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
from docpipe.core.operators.some_operator import SomeOperator

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

- [OpenSearch Quick Start](../docs/integrations/opensearch/OPENSEARCH_QUICKSTART.md)
- [Environment Setup Guide](../docs/integrations/opensearch/ENVIRONMENT_SETUP.md)
- [Operator Documentation](../docs/operators/)
