---
title: Operator Reference
---

# Operator Reference

## Table of Contents

- [Operator Reference](#operator-reference)
  - [Table of Contents](#table-of-contents)
  - [Overview](#overview)
    - [How to use this reference](#how-to-use-this-reference)
  - [Operator API Reference](#operator-api-reference)
    - [Common Operator Contract](#common-operator-contract)
      - [Operator Ownership Attribute](#operator-ownership-attribute)
    - [Ingest Operators](#ingest-operators)
      - [IngestLocalOperator](#ingestlocaloperator)
      - [IngestSourceOperator](#ingestsourceoperator)
    - [Quality Operators](#quality-operators)
      - [DocumentClassifierOperator](#documentclassifieroperator)
    - [Extract Operators](#extract-operators)
      - [ExtractOperator](#extractoperator)
    - [Functional Operators](#functional-operators)
      - [ChunkerOperator](#chunkeroperator)
      - [EntityCurationOperator](#entitycurationoperator)
      - [EmbeddingsOperator](#embeddingsoperator)
      - [BranchingOperator](#branchingoperator)
      - [MergeOperator](#mergeoperator)
      - [NOOPOperator](#noopoperator)
      - [DocIdHashOperator](#docidhashoperator)
    - [Quality Operators](#quality-operators-1)
      - [LanguageDetect](#languagedetect)
      - [ReadabilityOperator](#readabilityoperator)
      - [RedactionOperator](#redactionoperator)
      - [DocumentClassifierOperator](#documentclassifieroperator-1)
      - [EdedupOperator](#ededupoperator)
      - [MLEnrichmentOperator](#mlenrichmentoperator)
      - [SQLFilterOperator](#sqlfilteroperator)
    - [VectorDB Operators](#vectordb-operators)
      - [VectorDBOperator](#vectordboperator)
    - [Storage Operators](#storage-operators)
      - [DocumentSetOperator](#documentsetoperator)
  - [DatasiftFlowManager API](#datasiftflowmanager-api)
    - [Constructor](#constructor)
    - [`validate()`](#validate)
    - [`execute()`](#execute)
    - [`get_execution_metadata()`](#get_execution_metadata)
    - [`get_execution_logs()`](#get_execution_logs)
    - [`list_operators(verbose=False)`](#list_operatorsverbosefalse)
    - [Method name note](#method-name-note)
  - [CLI API Reference](#cli-api-reference)
    - [Command forms](#command-forms)
    - [Global arguments](#global-arguments)
    - [Exit codes](#exit-codes)
  - [Flow Configuration API](#flow-configuration-api)
    - [Root structure](#root-structure)
    - [Flow fields](#flow-fields)
    - [Node structure](#node-structure)
    - [Node fields](#node-fields)
    - [Edge structure](#edge-structure)
    - [Validation rules](#validation-rules)
  - [Exception Reference](#exception-reference)
    - [`DatasiftException`](#datasiftexception)
    - [`FlowExecutionFailedException`](#flowexecutionfailedexception)
    - [`FlowValidationException`](#flowvalidationexception)
    - [`PrefectFlowFailed`](#prefectflowfailed)
    - [`ValidationException`](#validationexception)
    - [`ConfigurationError`](#configurationerror)
    - [`DependencyError`](#dependencyerror)
    - [`ExternalServiceError`](#externalserviceerror)
    - [`FlowNotFoundException`](#flownotfoundexception)
    - [`FlowAlreadyExistsException`](#flowalreadyexistsexception)
    - [`FlowInvalidDataException`](#flowinvaliddataexception)
    - [`FlowStorageException`](#flowstorageexception)
    - [`RepositoryConfigurationException`](#repositoryconfigurationexception)
    - [`ValidationAlert`](#validationalert)
    - [`ValidationAlertEncoder`](#validationalertencoder)
  - [Utilities API](#utilities-api)
    - [PyArrow handler utilities](#pyarrow-handler-utilities)
      - [`BaseParquetTableHandler`](#baseparquettablehandler)
      - [`CpdParquetTableHandler`](#cpdparquettablehandler)
      - [`get_parquet_table_handler()`](#get_parquet_table_handler)
    - [Schema utilities](#schema-utilities)
      - [`align_table_schema(table, all_cols)`](#align_table_schematable-all_cols)
      - [`_combine_tables(tables, table_type)`](#_combine_tablestables-table_type)
      - [`_total_rows(tables)`](#_total_rowstables)
    - [Document class utilities](#document-class-utilities)
      - [`DocumentClassUtils.normalize_filename(name)`](#documentclassutilsnormalize_filenamename)
      - [`DocumentClassUtils.load_document_class(doc_class_path)`](#documentclassutilsload_document_classdoc_class_path)
      - [`DocumentClassUtils.generate_docling_template(doc_class_path, include_nested=True, max_fields=None)`](#documentclassutilsgenerate_docling_templatedoc_class_path-include_nestedtrue-max_fieldsnone)
    - [Operator display utility](#operator-display-utility)
      - [`list_operators(verbose=False, summary_only=False)`](#list_operatorsverbosefalse-summary_onlyfalse)

## Overview

[`OPERATOR_REFERENCE.md`](OPERATOR_REFERENCE.md) centralizes the public APIs that are visible to pipeline authors, application integrators, and operator users.

This reference is organized around four entry points:

- **Operators**: flow node implementations under [`src/datasift/core/operators`](src/datasift/core/operators)
- **Programmatic execution**: [`DatasiftFlowManager`](src/datasift/lib/datasift_flow_manager.py:24)
- **CLI execution**: [`datasift-orchestrator`](src/datasift/cli/datasift_cli.py:147)
- **Flow JSON definitions**: DAG configuration consumed by the orchestrator

### How to use this reference

- Use the operator sections when authoring flow JSON.
- Use the flow manager section when embedding datasift in Python code.
- Use the CLI section when running or validating flows from the shell.
- For classification-specific architecture details, see [`docs/operators/document_classifier.md`](docs/operators/document_classifier.md), which documents the simplified service-based architecture used by [`DocumentClassifierOperator`](src/datasift/core/operators/quality/document_classifier.py:26).

---

## Operator API Reference

### Common Operator Contract

All operators ultimately inherit from [`AbstractOperator`](src/datasift/core/operators/abstract_operator.py:28).

**Shared behavior**

- Operators receive a `config` dictionary during initialization.
- Operators expose metadata through the static method [`get_metadata()`](src/datasift/core/operators/abstract_operator.py:59), which can be called on the class without instantiation (e.g., `OperatorClass.get_metadata()`).
- Input column requirements are expressed with [`get_required_features()`](src/datasift/core/operators/abstract_operator.py:55).
- Validation hooks are implemented via [`validate()`](src/datasift/core/operators/abstract_operator.py:51).
- Runtime work is usually performed by `transform()` or `runner()` methods depending on the operator.

**Common input shape**

Most operators consume a `pyarrow.Table` with some subset of these columns:

| Column            | Type                                    | Meaning                                       |
| ----------------- | --------------------------------------- | --------------------------------------------- |
| `id`              | string                                  | Document identifier                           |
| `name`            | string                                  | Source path or display name                   |
| `content`         | string                                  | Extracted text or serialized document content |
| `doc_id_hash`     | string                                  | Stable hashed identifier                      |
| `chunked_content` | list or JSON string                     | Chunk payloads generated by chunking          |
| `embeddings`      | vector/list[float] or list[list[float]] | Dense vector output                           |

#### Operator Ownership Attribute

All operators must declare an `owner` attribute to support priority-based resolution when multiple operators share the same `short_name`.

**Where to Add the Owner Attribute:**

The `owner` attribute must be declared as a **class variable** at the top of your operator class, alongside `short_name` and `category`.

**Important**: To override an existing datasift operator, use the **same `short_name`** as the datasift operator. The priority system will ensure your custom operator (priority 2) takes precedence over the datasift operator (priority 1).

```python
from datasift.core.operators.abstract_operator import AbstractOperator, OperatorCategory
from datasift.core.constants.operator_constants import OperatorConstants

class CustomChunkerOperator(AbstractOperator):
    """Custom chunking operator that overrides the datasift chunker."""

    # Class-level attributes (declare these at the top)
    short_name: str = OperatorConstants.Operators.CHUNKER  # Same as datasift chunker!
    category: OperatorCategory = OperatorCategory.Functional
    owner: str = "custom"  # REQUIRED: This gives priority 1 (overrides datasift)

    def __init__(self, *, config: dict[str, Any]) -> None:
        super().__init__(config=config)
        # Your custom chunking logic here
```

**Key Point**: When both datasift's `ChunkerOperator` and your `CustomChunkerOperator` have `short_name = "chunker"`, the operator factory will load **only your custom operator** because it has higher priority (1 vs 2), and lower priority numbers carry higher precedence.

**For Datasift Operators:**

```python
from datasift.core.constants.constants import DatasiftConstants

owner: str = DatasiftConstants.OWNER_DATASIFT  # MUST be explicitly set for built-in operators
```

**For Custom Operators:**

```python
owner: str = "custom"  # MUST be explicitly set as shown above
```

**Why This Matters:**

- Custom operators with `owner="custom"` receive **priority 1** (highest)
- Datasift operators with `owner="datasift"` receive **priority 2**
- Operators without an explicit `owner` attribute inherit `owner=None` from [`AbstractOperator`](src/datasift/core/operators/abstract_operator.py:32), which are treated as custom operators
- During operator loading, the factory validates that custom operators (not in DATASIFT_OPERATORS frozenset) have `owner="custom"` and **rejects** those with `owner="datasift"`
- **All built-in datasift operators must explicitly set** `owner = DatasiftConstants.OWNER_DATASIFT`
- The `owner` attribute is included in operator metadata and can be queried via `OperatorMetadata.get_operator_metadata()`

**Priority Resolution Example:**

If both a datasift operator and custom operator have `short_name="chunker"`:

- Custom operator with `owner="custom"` → **Selected** (priority 1, highest)
- Datasift operator with `owner="datasift"` → Overridden (priority 2)

See [`OperatorFactory`](src/datasift/core/orchestration/operator_factory.py:97) for implementation details.

### Ingest Operators

#### IngestLocalOperator

**Purpose:** Discover files in a local file or directory and collect metadata for downstream extraction.

**Category:** Ingest

**Class:** `core.operators.ingest.ingest_local.IngestLocalOperator`

| Parameter             | Type          | Required | Default              | Description                                                                             |
| --------------------- | ------------- | -------: | -------------------- | ----------------------------------------------------------------------------------------|
| `paths`               | string/list   |      Yes | `../test-data/input` | Path(s) to file(s) or folder(s) to ingest. Can be a single path string or list of paths |
| `include_filter`      | string        |       No | -                    | Comma-separated extensions to include                                                   |
| `exclude_filter`      | string        |       No | -                    | Comma-separated extensions to exclude                                                   |
| `max_files`           | int           |       No | `100`                | Maximum number of files to ingest                                                       |
| `max_file_size`       | int           |       No | `100`                | Maximum file size in MB                                                                 |
| `force_ingest`        | bool          |       No | `false`              | Reprocess already-seen documents                                                        |
| `retain_deleted_docs` | bool          |       No | project constant     | Retain source-deleted docs in incremental scenarios                                     |

**Input Schema**

- No input table required

**Output Schema**

- `id`
- `name`
- `size`
- `created_time`
- `modified_time`

**Exceptions**

- `ValueError`
- file system errors
- incremental update utility failures

**Example**

```json
{
  "id": "ingest-node",
  "name": "ingest",
  "operator": "ingest_local",
  "config": {
    "paths": "./tests/fixtures/invoices",
    "include_filter": ".pdf"
  }
}
```

---

#### IngestSourceOperator

**Purpose:** Multi-provider ingest abstraction for sources such as object storage, SharePoint, OneDrive, Google Drive, web pages, and filesystem adapters.

**Category:** Ingest

**Class:** `core.operators.ingest.ingest_source.IngestSourceOperator`

| Parameter         | Type   | Required | Default | Description                     |
| ----------------- | ------ | -------: | ------- | ------------------------------- |
| `source_type`     | string |      Yes | -       | Adapter type                    |
| `include_filter`  | string |       No | -       | Extension include list          |
| `exclude_filter`  | string |       No | -       | Extension exclude list          |
| `force_ingest`    | bool   |       No | `false` | Reprocess prior docs            |
| `provider_config` | object |      Yes | -       | Provider-specific configuration |

**Input Schema**

- No input table required

**Output Schema**

| Column            | Type   | Description                                           |
| ----------------- | ------ | ----------------------------------------------------- |
| `id`              | string | MD5 hash of the source path                           |
| `name`            | string | Source identifier (file path, URL, etc.)              |
| `document_format` | string | File extension (e.g., `.pdf`, `.xlsx`, `.docx`)       |
| `metadata`        | string | JSON-serialized metadata from the source document     |
| `source_id`       | string | The source identifier                                 |
| `path`            | string | Source path/URL for on-demand binary loading          |
| `modified_time`   | int64  | Document modification timestamp (Unix timestamp)      |

**Exceptions**

- `ImportError`
- `ValueError`
- authentication and network failures

**Example**

```json
{
  "id": "ingest-source-node",
  "name": "s3-ingest",
  "operator": "ingest_source",
  "config": {
    "source_type": "s3",
    "provider_config": {
      "bucket": "example-bucket",
      "prefix": "incoming/"
    }
  }
}
```

---

### Quality Operators

#### DocumentClassifierOperator

**Purpose:** Classifies documents into predefined types using LLM-based classification with confidence scoring and reasoning. Uses simplified service-based architecture with shared LLM infrastructure supporting multiple providers (LiteLLM, Watsonx).

**Category:** Quality

**Class:** `core.operators.quality.classification.document_classifier.DocumentClassifierOperator`

| Parameter              | Type      | Required | Default                  | Description                                                                               |
| ---------------------- | --------- | -------- | ------------------------ | ----------------------------------------------------------------------------------------- |
| `provider`             | string    | No       | `"litellm"`              | LLM provider: `"litellm"` or `"watsonx"`                                                  |
| `model_id`             | string    | No       | `"openai/granite3.1-dense:8b"`   | Model identifier in `<provider>/<model_id>` format (e.g., `"openai/granite3.1-dense:8b"` for Ollama, `"openai/gpt-4o-mini"`, `"huggingface/meta-llama/Llama-3.3-70B-Instruct"`)  |
| `provider_config`      | object    | No       | `{}`                | Provider-specific configuration (api_key, api_base, etc.)                                 |
| `document_types`       | list/dict | No       | Auto-loaded         | Document types to classify into (list or dict with descriptions)                          |
| `confidence_threshold` | float     | No       | `7.0`               | Minimum confidence for classification (1-10 scale)                                        |
| `doc_column`           | string    | No       | `"content"`         | Column containing document text                                                           |
| `output_column`        | string    | No       | `"document_type"`   | Column name for classification result                                                     |
| `include_confidence`   | boolean   | No       | `true`              | Include confidence score in output                                                        |
| `include_reasoning`    | boolean   | No       | `false`             | Include reasoning explanation in output                                                   |
| `max_content_length`   | integer   | No       | `2000`              | Maximum content length to send to LLM                                                     |
| `max_workers`          | integer   | No       | Auto                | Number of parallel workers                                                                |
| `use_processes`        | boolean   | No       | `false`             | Use processes instead of threads                                                          |

**Provider-Specific Configuration**

**LiteLLM (100+ providers):**

```json
{
  "provider": "litellm",
  "model_id": "openai/gpt-4o-mini",
  "provider_config": {
    "api_key": "${OPENAI_API_KEY}",
    "request_timeout": 120
  }
}
```

Supported LiteLLM providers:

- OpenAI: `openai/gpt-4o-mini`, `openai/gpt-4`, `openai/gpt-3.5-turbo`
- Anthropic: `anthropic/claude-3-opus`, `anthropic/claude-3-sonnet`, `anthropic/claude-3-haiku`
- Azure OpenAI: `azure/gpt-4`
- AWS Bedrock: `bedrock/anthropic.claude-3-sonnet`
- Google Vertex AI: `vertex_ai/gemini-pro`
- HuggingFace: `huggingface/meta-llama/Llama-3.3-70B-Instruct`, `huggingface/mistralai/Mistral-7B-Instruct-v0.2`
- Ollama via OpenAI-compatible endpoint: `openai/llama3.2:latest`, `openai/granite3.1-dense:8b` with `api_base: "http://localhost:11434/v1"`

**Watsonx:**

```json
{
  "provider": "watsonx",
  "model_id": "ibm/granite-13b-chat-v2",
  "provider_config": {
    "api_base": "https://us-south.ml.cloud.ibm.com",
    "api_key": "${WATSONX_API_KEY}",
    "container_kind": "project",
    "container_id": "${WATSONX_CONTAINER_ID}",
    "request_timeout": 120
  }
}
```

**Input Schema**

- PyArrow Table with document content (text column or binary content for extraction)
- Optional `content` column (if not present, will be fetched from binary content)

**Output Schema**

Adds the following columns:

- `document_type` (string): Classified document type
- `document_type_confidence` (float): Confidence score 1-10 (if `include_confidence=true`)
- `document_type_reasoning` (string): Classification explanation (if `include_reasoning=true`)
- `content` (string): Document content (if fetched and not already present)

**Document Types Configuration**

Simple list format:

```json
{
  "document_types": ["invoice", "receipt", "contract", "report", "letter"]
}
```

Detailed dictionary format (recommended):

```json
{
  "document_types": {
    "invoice": "Business invoice with line items, totals, and payment terms",
    "receipt": "Payment receipt or transaction confirmation",
    "contract": "Legal contract or agreement document",
    "report": "Business or technical report with analysis and findings",
    "other": "Other document types not fitting above categories"
  }
}
```

**Exceptions**

- `DatasiftException`: Adapter initialization failures, invalid provider configuration
- `ValueError`: Invalid response format from LLM
- `json.JSONDecodeError`: Failed to parse LLM response

**Example - LiteLLM with OpenAI**

```json
{
  "id": "classify-node",
  "name": "classify",
  "operator": "classification_operator",
  "config": {
    "provider": "litellm",
    "model_id": "openai/gpt-4o-mini",
    "provider_config": {
      "api_key": "${OPENAI_API_KEY}"
    },
    "document_types": {
      "invoice": "Business invoice with line items and totals",
      "receipt": "Payment receipt or confirmation",
      "contract": "Legal contract or agreement",
      "report": "Business or technical report"
    },
    "confidence_threshold": 8.0,
    "include_confidence": true,
    "include_reasoning": true,
    "max_content_length": 4000
  }
}
```

**Example - LiteLLM with Ollama OpenAI-Compatible Endpoint**

```json
{
  "id": "classify-node",
  "name": "classify",
  "operator": "document_classifier",
  "config": {
    "provider": "litellm",
    "model_id": "openai/llama3.2:latest",
    "provider_config": {
      "api_key": "${api-key}",
      "api_base": "http://localhost:11434/v1"
    },
    "document_types": {
      "invoice": "Business invoice with line items, totals, and payment terms",
      "receipt": "Payment receipt or transaction confirmation",
      "contract": "Legal contract or agreement document",
      "other": "Other document types"
    },
    "confidence_threshold": 7.0,
    "include_confidence": true,
    "include_reasoning": true
  }
}
```

**Architecture**

Uses simplified service-based architecture:

- **Operator Layer**: `DocumentClassifierOperator` handles PyArrow table processing and orchestration
- **Service Layer**: `ClassificationService` contains business logic for document classification
- **Domain Layer**: Pure domain models (`ClassificationRequest`, `ClassificationResponse`) and prompt building
- **Infrastructure Layer**: Leverages shared `LLMAdapterFactory` for multi-provider LLM support (LiteLLM, Watsonx)

This simplified design removes the port/adapter overhead while maintaining clean separation of concerns and provider flexibility through the shared LLM infrastructure.

**Related Documentation**

- [Classification Operator Guide](docs/operators/document_classifier.md)
- [Extract Operator](docs/operators/extract_operator.md)

---

### Extract Operators

#### ExtractOperator

**Purpose:** Unified extraction operator using hexagonal architecture with multiple adapters for text extraction (docling_library, docling_serve) and entity extraction (litellm, watsonx, docling, none).

**Category:** Extract

**Class:** `core.operators.extract.extract_operator.ExtractOperator`

| Parameter                                                 | Type   | Required | Default                   | Description                                                                                        |
|-----------------------------------------------------------|--------|---------:|---------------------------|----------------------------------------------------------------------------------------------------|
| `text_extraction_mode`                                    | string |       No | `docling_library`         | Text extraction mode: `docling_library` (local with optional VLM) or `docling_serve` (remote API)  |
| `entity_extraction_mode`                                  | string |       No | `none`                    | Entity extraction mode: `litellm` (includes Ollama via openai/ prefix), `watsonx`, `docling`, or `none`. **Note:** When using any entity extraction mode (not `none`), either `custom_schema` must be provided in the operator configuration OR a `document_type` column must be present from an upstream classification operator (e.g., DocumentClassifierOperator). If neither is provided, a `ConfigurationError` will be thrown. |
| `doc_column`                                              | string |       No | `doc_content`             | Column name for storing extracted text content                                                     |
| `output_column`                                           | string |       No | `entities`                | Column name for storing extracted entities                                                         |
| `additional_formats`                                      | array  |       No | `[]`                      | Additional output formats beyond markdown: `html`, `json`, `text`, `doctags`                       |
| `extract_tables`                                          | bool   |       No | `false`                   | Extract tables from documents (text extraction)                                                    |
| `extract_images`                                          | bool   |       No | `false`                   | Extract images from documents (text extraction)                                                    |
| `max_workers`                                             | int    |       No | auto                      | Maximum parallel workers (auto-detected based on CPU)                                              |
| `use_processes`                                           | bool   |       No | `false`                   | Use ProcessPoolExecutor vs ThreadPoolExecutor                                                      |
| `expand_extracted_data`                                   | bool   |       No | `false`                   | Expand entity JSON into individual columns (entity extraction only)                                |
| `custom_schema`                                           | object |       No | `{}`                      | Schema dictionary for structured extraction. **Required** when using entity extraction modes (`litellm`, `watsonx`, `docling`) unless a `document_type` column is present from an upstream classification operator. |
| **VLM Parameters (docling_library mode)**                 |
| `use_vlm_pipeline`                                        | bool   |       No | `false`                   | Enable VLM (Vision-Language Model) pipeline                                                        |
| `vlm_preset`                                              | string |       No | `granite_docling`         | VLM preset name when VLM enabled                                                                   |
| `vlm_engine_type`                                         | string |       No | `transformers`            | VLM engine: `transformers`, `mlx`, `api_*` variants                                                |
| `vlm_provider_config`                                     | object |       No | `null`                    | Provider-specific VLM configuration                                                                |
| **ASR Parameters (docling_library mode for audio/video)** |
| `use_asr_pipeline`                                        | bool   |       No | `false`                   | Enable ASR (Automatic Speech Recognition) for audio/video files                                    |
| `asr_model_name`                                          | string |       No | `whisper_turbo`           | ASR model name (e.g., `whisper_turbo`, `whisper_large`)                                            |
| **Docling Serve Parameters (docling_serve mode)**         |
| `docling_serve_base_url`                                  | string |       No | `http://localhost:5001`   | Docling Serve API endpoint                                                                         |
| `docling_serve_api_key`                                   | string |       No | `null`                    | Optional API key for authentication                                                                |
| `docling_serve_timeout`                                   | int    |       No | `300`                     | Request timeout in seconds                                                                         |
| `docling_serve_do_ocr`                                    | bool   |       No | `true`                    | Enable OCR processing                                                                              |
| `docling_serve_ocr_engine`                                | string |       No | `easyocr`                 | OCR engine: `easyocr` or `tesseract`                                                               |
| `docling_serve_pdf_backend`                               | string |       No | `dlparse_v2`              | PDF backend: `dlparse_v4`, `dlparse_v3`, `pypdfium2`                                               |
| **LiteLLM Entity Parameters (litellm mode)**              |
| `entity_model_name`                                       | string |    Yes\* | `gpt-3.5-turbo`           | LLM model identifier. For Ollama, use `openai/` prefix (e.g., `openai/llama3.2`) (\*required for litellm mode) |
| `entity_temperature`                                      | float  |       No | `0.0`                     | Sampling temperature                                                                               |
| `entity_max_tokens`                                       | int    |       No | `2000`                    | Maximum response tokens                                                                            |
| `entity_provider_config`                                  | object |       No | `{}`                      | Provider config with `api_key`, `api_base`. For Ollama, set `api_base` to `http://localhost:11434/v1` |
| **WatsonX Entity Parameters (watsonx mode)**              |
| `entity_model_name`                                       | string |    Yes\* | `ibm/granite-13b-chat-v2` | WatsonX model identifier (\*required for watsonx mode)                                             |
| `entity_temperature`                                      | float  |       No | `0.0`                     | Sampling temperature                                                                               |
| `entity_max_tokens`                                       | int    |       No | `2000`                    | Maximum response tokens                                                                            |
| `entity_provider_config`                                  | object |    Yes\* | `{}`                      | Provider config with `api_key`, `container_id`, `api_base` (optional), `container_kind` (optional) |

**Input Schema**

- `name` (`string`)
- binary payload column from an ingest operator
- optional existing content column

**Output Schema**

- `content` (or configured via `doc_column` parameter) - Extracted markdown text (always generated)
- `content_html` - HTML format (if `additional_formats` includes "html")
- `content_json` - JSON structured format (if `additional_formats` includes "json")
- `content_text` - Plain text format (if `additional_formats` includes "text")
- `content_doctags` - Docling's native DocTags format (if `additional_formats` includes "doctags")
- `entities` (or configured `output_column`) - Extracted entities as JSON string (if entity extraction enabled)
- `doc_id_hash` - Document hash identifier
- `tables` - Extracted tables as JSON (if `extract_tables=true`)
- `images` - Extracted images metadata as JSON (if `extract_images=true`)
- `pages_processed` - Estimated number of pages for the extracted document text, calculated using 3000 characters = 1 page
- Individual entity columns (if `expand_extracted_data=true`)

**Execution Metadata**

The operator provides the following metadata after execution:

- `page_type_stats` (dict): Aggregate estimated pages grouped by source document format (e.g., `{"pdf": 120, "docx": 45}`)
- `total_pages_converted` (int): Total estimated pages across all successfully processed documents

**Exceptions**

- [`FlowExecutionFailedException`](src/datasift/exceptions/datasift_exceptions.py)
- `ValueError` for invalid configuration
- Provider-specific exceptions (Ollama, LiteLLM, Docling)

**Example: Basic Text Extraction**

```json
{
  "id": "extract-node",
  "name": "extract",
  "operator": "extract_operator",
  "config": {
    "text_extraction_mode": "docling_library",
    "entity_extraction_mode": "none",
    "doc_column": "content",
    "extract_tables": true,
    "extract_images": true
  }
}
```

**Example: VLM Text Extraction**

```json
{
  "id": "extract-node",
  "name": "extract",
  "operator": "extract_operator",
  "config": {
    "text_extraction_mode": "docling_library",
    "entity_extraction_mode": "none",
    "use_vlm_pipeline": true,
    "vlm_preset": "granite_docling",
    "vlm_engine_type": "transformers",
    "max_workers": 1
  }
}
```

**Example: Docling Serve with OCR**

```json
{
  "id": "extract-node",
  "name": "extract",
  "operator": "extract_operator",
  "config": {
    "text_extraction_mode": "docling_serve",
    "entity_extraction_mode": "none",
    "docling_serve_base_url": "http://localhost:5001",
    "docling_serve_do_ocr": true,
    "docling_serve_ocr_engine": "easyocr",
    "docling_serve_pdf_backend": "dlparse_v4"
  }
}
```

**Example: Text + LiteLLM Entity Extraction (with Ollama)**

```json
{
  "id": "extract-node",
  "name": "extract",
  "operator": "extract_operator",
  "config": {
    "text_extraction_mode": "docling_library",
    "entity_extraction_mode": "litellm",
    "entity_model_name": "openai/granite4:latest",
    "entity_temperature": 0.0,
    "entity_max_tokens": 4096,
    "entity_provider_config": {
      "api_base": "http://localhost:11434/v1",
      "api_key": "<ollama_key>"
    },
    "custom_schema": {
      "invoice_number": "string",
      "total_amount": "float"
    }
  }
}
```

**Example: Text + LiteLLM Entity Extraction (with OpenAI)**

```json
{
  "id": "extract-node",
  "name": "extract",
  "operator": "extract_operator",
  "config": {
    "text_extraction_mode": "docling_library",
    "entity_extraction_mode": "litellm",
    "entity_model_name": "gpt-3.5-turbo",
    "entity_temperature": 0.0,
    "entity_max_tokens": 2000,
    "entity_provider_config": {
      "api_key": "${OPENAI_API_KEY}",
      "api_base": "https://api.openai.com/v1"
    }
  }
}
```

**Example: Multi-Format Output**

```json
{
  "id": "extract-node",
  "name": "extract",
  "operator": "extract_operator",
  "config": {
    "text_extraction_mode": "docling_library",
    "additional_formats": ["html", "json", "text"],
    "extract_tables": true,
    "extract_images": true
  }
}
```

**Example: Text + WatsonX Entity Extraction**

```json
{
  "id": "extract-node",
  "name": "extract",
  "operator": "extract_operator",
  "config": {
    "text_extraction_mode": "docling_library",
    "entity_extraction_mode": "watsonx",
    "entity_model_name": "ibm/granite-13b-chat-v2",
    "entity_temperature": 0.0,
    "entity_max_tokens": 2000,
    "entity_provider_config": {
      "api_key": "${WATSONX_API_KEY}",
      "container_id": "${WATSONX_CONTAINER_ID}",
      "api_base": "https://us-south.ml.cloud.ibm.com",
      "container_kind": "project"
    },
    "custom_schema": {
      "invoice_number": "string",
      "total_amount": "float"
    }
  }
}
```

**Example: Docling Template-Based Entity Extraction**

```json
{
  "id": "extract-node",
  "name": "extract",
  "operator": "extract_operator",
  "config": {
    "text_extraction_mode": "docling_library",
    "entity_extraction_mode": "docling",
    "custom_schema": {
      "type": "object",
      "properties": {
        "invoice_number": { "type": "string" },
        "total_amount": { "type": "number" }
      }
    }
  }
}
```

**Example: Docling Entity Extraction with Custom Inline Model**

```json
{
  "id": "extract-node",
  "name": "extract",
  "operator": "extract_operator",
  "config": {
    "text_extraction_mode": "docling_library",
    "entity_extraction_mode": "docling",
    "entity_config": {
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
      "type": "object",
      "properties": {
        "invoice_number": { "type": "string" },
        "total_amount": { "type": "number" }
      }
    }
  }
}
```

**Custom Model Configuration for Docling Entity Extraction**

The `entity_config` parameter enables custom inline model configuration for the Docling entity extraction adapter. Only inline models (HuggingFace) are supported as DocumentExtractor does not support remote API endpoints.

**Note:** For API-based entity extraction, use `entity_extraction_mode: "litellm"` or `"watsonx"` instead of Docling.

**Configuration Structure:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `entity_config` | object | No | Custom inline model configuration for Docling entity extraction |
| `entity_config.model_type` | string | Yes* | Model type: must be `inline` (*required if `entity_config` provided) |
| `entity_config.inline_model` | object | Yes* | Inline model configuration (*required if `entity_config` provided) |
| `entity_config.inline_model.repo_id` | string | Yes | HuggingFace model repository ID (e.g., `numind/NuExtract-2.0-2B`) |
| `entity_config.inline_model.inference_framework` | string | No | Inference framework: `transformers`, `vllm`, or `mlx` (default: `transformers`) |
| `entity_config.inline_model.scale` | float | No | Image scaling factor (default: `2.0`) |
| `entity_config.inline_model.temperature` | float | No | Sampling temperature (default: `0.0`) |
| `entity_config.inline_model.max_new_tokens` | int | No | Maximum generation length (default: `4096`) |
| `entity_config.inline_model.load_in_8bit` | bool | No | Enable 8-bit quantization (default: `true`) |
| `entity_config.inline_model.torch_dtype` | string | No | Precision type: `bfloat16`, `float16`, `float32` (default: `bfloat16`) |
| `entity_config.inline_model.prompt` | string | No | Custom prompt template (default: `""`) |
| `entity_config.inline_model.response_format` | string | No | Response format: `markdown`, `doctags`, `html`, etc. (default: `markdown`) |

**Usage Notes:**

- **Inline Models Only**: Only HuggingFace models loaded directly into memory are supported. DocumentExtractor does not support remote API endpoints.
- **API-Based Extraction**: For API-based entity extraction (Ollama via LiteLLM, OpenAI, etc.), use `entity_extraction_mode: "litellm"` or `"watsonx"` instead.
- **Default Behavior**: If `entity_config` is not provided, Docling uses its default model configuration.
- **Performance**: Inline models require sufficient GPU memory and are suitable for local deployment with GPU resources.
- **Compatibility**: Ensure the chosen model supports the inference framework and hardware configuration.

**Architecture**

The ExtractOperator uses hexagonal architecture (ports and adapters pattern) with clear separation of concerns:

**Layers:**
- **Domain Layer**: `EntityExtractionService` handles business logic (prompt building, schema validation, response parsing)
- **Port Layer**: `TextExtractionPort` and `EntityExtractionPort` define extraction interfaces
- **Adapter Layer**: Concrete implementations for different extraction strategies
  - Text: `DoclingAdapter` (docling_library), `DoclingServeAdapter` (docling_serve)
  - Entity: `LLMEntityAdapter` (unified for litellm/watsonx), `DoclingEntityAdapter` (docling)
- **Factory Layer**: `TextExtractionAdapterFactory` and `EntityExtractionAdapterFactory` create adapters based on mode

**Key Benefits:**
- Easy addition of new extraction strategies by implementing ports
- Clear separation between business logic, interfaces, and implementations
- Independent text and entity extraction mode selection
- Unified LLM support: Both `litellm` and `watsonx` modes use the same `LLMEntityAdapter`
- Parallel processing with auto-optimized worker counts

**Integration Requirements**

- **Ollama** (for litellm entity mode with Ollama): Server at `http://localhost:11434`, model pulled (e.g., `ollama pull llama3.2`). Access via litellm mode with `openai/` model prefix
- **Docling Serve** (for docling_serve text mode): Service at configured URL (default `http://localhost:5001`)
- **LiteLLM** (for litellm entity mode): API keys for chosen provider (OpenAI, Anthropic, etc.)
- **WatsonX** (for watsonx entity mode): Environment variables `WATSONX_API_KEY`, `WATSONX_CONTAINER_ID`, optional `WATSONX_API_BASE_URL`, `WATSONX_CONTAINER_KIND`
- **ffmpeg** (for audio/video processing): Required for M4A, AAC, OGG, FLAC audio formats and all video formats (MP4, AVI, MOV). Not required for WAV/MP3. Install: `brew install ffmpeg` (macOS) or `sudo apt install ffmpeg` (Linux)

**Usage Notes**

- Dual-mode operation: text and entity extraction in single operator
- Text modes: `docling_library` (local, optional VLM) or `docling_serve` (remote API with OCR)
- Entity modes: `litellm` (100+ providers including Ollama via openai/ prefix), `watsonx` (IBM WatsonX.ai), `docling` (template-based), `none` (default)
- **Entity Extraction Validation**: When using any entity extraction mode (not `none`), you must provide either:
  - A `custom_schema` in the operator configuration, OR
  - A `document_type` column from an upstream classification operator (e.g., DocumentClassifierOperator)
  - If neither is provided, a `ConfigurationError` will be thrown with message: "Entity extraction requires either a custom_schema in operator config OR a document_type column from upstream classification operator"
- VLM pipeline (docling_library mode) enhances extraction for complex documents
- Docling Serve mode supports OCR for scanned documents and multi-language processing
- **Text File Handling**: `.txt` files are automatically processed locally using UTF-8/latin-1 decoding, bypassing Docling Serve even when `docling_serve` mode is configured
- **Extension Detection**: Files without extensions are automatically detected using magic byte analysis (supports PDF, DOCX, XLSX, PPTX, images, HTML, and text formats)
- Audio/Video Support Processes audio (WAV, MP3, M4A, AAC, OGG, FLAC) and video (MP4, AVI, MOV) files using ASR (Automatic Speech Recognition) via Docling. Requires ffmpeg for M4A, AAC, OGG, FLAC, and all video formats
- See [ExtractOperator README](src/datasift/core/operators/extract/README.md) for complete documentation

---

### Functional Operators

#### ChunkerOperator

**Purpose:** Split extracted text into chunks using simple, semantic, or hybrid/docling strategies with optional multi-provider LLM summarization.

**Category:** Functional

**Class:** `core.operators.functional.chunker.ChunkerOperator`

| Parameter                       | Type   | Required | Default                                  | Description                                                    |
| ------------------------------- | ------ | -------: | ---------------------------------------- | -------------------------------------------------------------- |
| `doc_column`                    | string |      Yes | `content`                                | Input content column                                           |
| `chunk_type`                    | string |      Yes | `simple`                                 | `simple`, `semantic`, or `hybrid`                              |
| `chunk_size`                    | int    |       No | project default                          | Character or token size depending on chunker                   |
| `chunk_overlap`                 | int    |       No | `200`                                    | Overlap between chunks                                         |
| `semantic_embeddings_model`     | string |       No | `granite4`                               | Ollama model for semantic chunking                             |
| `breakpoint_threshold_type`     | string |       No | `percentile`                             | Semantic split threshold method                                |
| `breakpoint_threshold_amount`   | float  |       No | `null`                                   | Threshold amount                                               |
| `docling_tokenizer`             | string |       No | `sentence-transformers/all-MiniLM-L6-v2` | Hybrid chunking tokenizer                                      |
| `retain_original_content`       | bool   |       No | `false`                                  | Keep original content                                          |
| `enable_summarization`          | bool   |       No | `false`                                  | Enable chunk summarization using LLM                           |
| `summarization_provider`        | string |       No | `litellm`                                | LLM provider: `litellm` or `watsonx`                           |
| `summarization_model_id`        | string |       No | `granite4`                               | Model ID (auto-prefixed with `openai/` for LiteLLM)           |
| `summarization_provider_config` | object |       No | `{}`                                     | Provider-specific configuration (see below)                    |
| `max_input_tokens`              | int    |       No | `8000`                                   | Maximum tokens per LLM request (range: 1000-32000)             |
| `overlap_ratio`                 | float  |       No | `0.2`                                    | Overlap ratio for sliding window summarization                 |
| `summary_sentences`             | int    |       No | `2`                                      | Target sentences per summary (range: 1-5)                      |
| `summary_max_words`             | int    |       No | `20`                                     | Maximum words per summary (range: 10-100)                      |

**Summarization Providers:**

When `enable_summarization` is `true`, the operator uses the common LLM infrastructure to generate summaries for each chunk:

- **LiteLLM** (default): Unified API for 100+ providers (OpenAI, Azure, Anthropic, Cohere, AWS Bedrock, GCP Vertex AI, etc.)
- **Watsonx**: IBM watsonx.ai cloud service (enterprise AI)

**Provider-Specific Configuration (`summarization_provider_config`):**

| Provider     | Parameter  | Type   | Default                          | Description                                     |
| ------------ | ---------- | ------ | -------------------------------- | ----------------------------------------------- |
| **LiteLLM**  | `api_base` | string | `http://localhost:11434/v1`      | API endpoint URL (defaults to Ollama)           |
|              | `api_key`  | string | `ollama`                         | Provider API key                                |
| **Watsonx**  | `api_key`  | string | -                                | IBM Cloud API key                               |
|              | `project_id` | string | -                              | watsonx.ai project ID                           |
|              | `url`      | string | `https://us-south.ml.cloud.ibm.com` | watsonx.ai service URL                       |

**Backward Compatibility:**

Legacy configurations using only `summarization_model_id` without provider settings are automatically converted to LiteLLM with Ollama defaults:

```json
{
  "enable_summarization": true,
  "summarization_model_id": "llama3.2:3b"
}
```

Becomes:

```json
{
  "enable_summarization": true,
  "summarization_provider": "litellm",
  "summarization_model_id": "openai/llama3.2:3b",
  "summarization_provider_config": {
    "api_base": "http://localhost:11434/v1",
    "api_key": "ollama"
  }
}
```

**Input Schema**

- configured `doc_column`, usually `content`

**Output Schema**

- `chunk_sequence_number`
- `start_index`
- `chunked_content` (array of objects with `chunk`, `start_index`, and optional `summary` fields when `enable_summarization` is `true`)

**Exceptions**

- [`DatasiftException`](src/datasift/exceptions/datasift_exceptions.py)
- validation messages
- Ollama errors for semantic chunking
- LLM provider errors for summarization (handled gracefully)

**Examples**

Basic chunking without summarization:

```json
{
  "id": "chunk-node",
  "name": "chunk",
  "operator": "chunker",
  "config": {
    "chunk_type": "hybrid",
    "doc_column": "content",
    "chunk_size": 512,
    "chunk_overlap": 128
  }
}
```

Chunking with LiteLLM summarization (Ollama):

```json
{
  "id": "chunk-with-summary",
  "name": "chunk",
  "operator": "chunker",
  "config": {
    "chunk_type": "simple",
    "doc_column": "content",
    "chunk_size": 1000,
    "chunk_overlap": 200,
    "enable_summarization": true,
    "summarization_provider": "litellm",
    "summarization_model_id": "llama3.2:3b",
    "summarization_provider_config": {
      "api_base": "http://localhost:11434/v1",
      "api_key": "ollama"
    },
    "summary_sentences": 2,
    "summary_max_words": 20
  }
}
```

Chunking with Watsonx summarization:

```json
{
  "id": "chunk-watsonx",
  "name": "chunk",
  "operator": "chunker",
  "config": {
    "chunk_type": "simple",
    "doc_column": "content",
    "chunk_size": 1000,
    "enable_summarization": true,
    "summarization_provider": "watsonx",
    "summarization_model_id": "ibm/granite-13b-chat-v2",
    "summarization_provider_config": {
      "api_key": "${WATSONX_API_KEY}",
      "project_id": "${WATSONX_PROJECT_ID}"
    }
  }
}
```

#### EntityCurationOperator

**Purpose:** Transform extracted entities into structured, curated data using document class schemas with 4 core transformation functions for currency, date, number, and weight parsing.

**Category:** Functional

**Class:** `datasift.core.operators.functional.entity_curation.entity_curation_operator.EntityCurationOperator`

| Parameter              | Type   | Required | Default         | Description                                 |
| ---------------------- | ------ | -------: | --------------- | ------------------------------------------- |
| `entities_column`      | string |       No | `entities`      | Column containing extracted entities (dict) |
| `document_type_column` | string |       No | `document_type` | Column containing document type identifier  |

**Input Schema**

- `entities` (dict): Extracted entity key-value pairs from ExtractOperator
- `document_type` (string): Document class identifier (e.g., "invoice", "purchase_order")
- Other columns are preserved

**Output Schema**

- All input columns preserved
- `transformed_entities` column: JSON string containing nested structure of curated entities organized by target tables

**Transformation Functions**

The operator includes 4 core transformations:

| Function              | Purpose                               | Example                               |
| --------------------- | ------------------------------------- | ------------------------------------- |
| `currency_to_numeric` | Locale-aware currency parsing (Babel) | `"1.234,56 €"` (de_DE) → `1234.56`    |
| `make_date_uniform`   | Date normalization to YYYY-MM-DD      | `"January 15, 2024"` → `"2024-01-15"` |
| `to_number`           | Multi-language number parsing         | `"一千二百三十四"` (Chinese) → `1234` |
| `weight_to_numeric`   | Locale-aware weight conversion to kg  | `"5斤"` (zh_CN) → `2.5`               |

**Document Class Schemas**

Schemas are defined with `target_tables` specifying field mappings and transformations. Supports 40+ document classes including invoice, purchase_order, receipt, insurance_claim, passport, and more.

**Exceptions**

- [`ValidationError`](src/datasift/exceptions/datasift_exceptions.py) - Missing required columns
- Transformation errors are logged but don't stop processing (graceful degradation)

**Example**

```json
{
  "id": "curate-node",
  "name": "entity_curation",
  "operator": "entity_curation",
  "config": {
    "entities_column": "entities",
    "document_type_column": "document_type"
  }
}
```

**Usage Notes**

- Should be placed after `ExtractOperator` in the pipeline when entity extraction is enabled
- Requires document class schemas for transformation (returns empty dict for unknown document types)
- Output is always in JSON format with nested structure matching schema's target tables
- See [Entity Curation README](src/datasift/core/operators/functional/entity_curation/README.md) for detailed documentation

---

---

#### EmbeddingsOperator

**Purpose:** Generate dense embeddings using pluggable providers such as Ollama, HuggingFace, LiteLLM-backed vendors, and IBM watsonx.ai.

**Category:** Functional

**Class:** `core.operators.functional.embeddings.embeddings_operator.EmbeddingsOperator`

| Parameter             | Type   | Required | Default       | Description                                                    |
| --------------------- | ------ | -------: | ------------- | -------------------------------------------------------------- |
| `provider`            | string |      Yes | `litellm`     | Provider type: `litellm`, `watsonx`                            |
| `model_id`            | string |      Yes | `openai/nomic-embed-text` | Model identifier in `<provider>/<model_id>` format for litellm (e.g., `openai/nomic-embed-text`, `huggingface/sentence-transformers/all-MiniLM-L6-v2`) |
| `embeddings_column`   | string |       No | `embeddings`  | Output vector column                                           |
| `doc_column`          | string |       No | `content`     | Input content column                                           |
| `doc_id_hash`         | string |       No | `doc_id_hash` | Hash column name                                               |
| `overlap_ratio`       | float  |       No | `0.2`         | Long-text chunk overlap ratio                                  |
| `token_limit`         | integer |      No | `8192`        | Maximum token limit for text chunking. Adjust based on model's context window (512-8192 tokens). |
| `provider_config`     | object |       No | `{}`          | Provider-specific configuration (see below)                    |

**Supported Providers:**

- **LiteLLM**: Unified API for 100+ providers (OpenAI, Azure, Cohere, AWS, GCP, Ollama, HuggingFace)
- **Watsonx**: IBM watsonx.ai cloud service (enterprise AI)

**Provider-Specific Configuration (`provider_config`):**

| Provider     | Parameter          | Type                      | Default | Description                                           |
| ------------ | ------------------ |---------------------------| ------- | ----------------------------------------------------- |
| **LiteLLM**  | `api_base`         | string                    | -       | Custom API endpoint URL (e.g., `http://localhost:11434` for Ollama) |
|              | `api_key`          | string                    | -       | Provider API key (required for most providers, not needed for Ollama) |
|              | `batch_size`       | int                       | `32`    | Number of texts to process in each batch              |
|              | `timeout`          | int                       | `120`   | Request timeout in seconds                            |
| **Watsonx**  | `api_key`          | string                    | Yes     | IBM Cloud API key (required)                          |
|              | `project_id`       | string                    | Yes     | WatsonX project ID (required)                         |
|              | `url`              | string                    | `https://us-south.ml.cloud.ibm.com` | WatsonX API URL |
|              | `batch_size`       | int                       | `800`   | Number of texts to process in each batch              |
|              | `timeout`          | int                       | `120`   | Request timeout in seconds                            |
|              | `enable_rate_limiting` | bool                  | `false` | Enable rate limiting for API calls                    |

**Note:** For Ollama models via LiteLLM, use `openai/` prefix (e.g., `openai/nomic-embed-text`). For HuggingFace models via LiteLLM, use `huggingface/` prefix (e.g., `huggingface/sentence-transformers/all-MiniLM-L6-v2`).

**Input Schema**

- `content` or `chunked_content`

**Output Schema**

- `embeddings`
- `doc_id_hash`

**Exceptions**

- [`DatasiftException`](src/datasift/exceptions/datasift_exceptions.py)
- provider authentication/network failures

**Example 1: LiteLLM with Ollama (local)**

```json
{
  "id": "embedding-node",
  "name": "embeddings",
  "operator": "embeddings",
  "config": {
    "provider": "litellm",
    "model_id": "openai/nomic-embed-text",
    "embeddings_column": "embeddings",
    "text_column": "content",
    "batch_size": 32,
    "provider_config": {
      "api_base": "http://localhost:11434",
      "timeout": 120
    }
  }
}
```

**Example 2: LiteLLM with HuggingFace**

```json
{
  "id": "embedding-node",
  "name": "embeddings",
  "operator": "embeddings",
  "config": {
    "provider": "litellm",
    "model_id": "huggingface/sentence-transformers/all-MiniLM-L6-v2",
    "embeddings_column": "embeddings",
    "text_column": "content",
    "batch_size": 16,
    "provider_config": {
      "api_key": "${HUGGINGFACE_API_KEY}"
    }
  }
}
```

**Example 3: WatsonX embeddings**

```json
{
  "id": "embedding-node",
  "name": "embeddings",
  "operator": "embeddings",
  "config": {
    "provider": "watsonx",
    "model_id": "ibm/slate-125m-english-rtrvr",
    "embeddings_column": "embeddings",
    "text_column": "content",
    "batch_size": 32,
    "provider_config": {
      "api_key": "${WATSONX_API_KEY}",
      "project_id": "${WATSONX_PROJECT_ID}",
      "url": "https://us-south.ml.cloud.ibm.com"
    }
  }
}
```

**Example 4: LiteLLM with OpenAI**

```json
{
  "id": "embedding-node",
  "name": "embeddings",
  "operator": "embeddings",
  "config": {
    "provider": "litellm",
    "model_id": "openai/text-embedding-3-small",
    "embeddings_column": "embeddings",
    "text_column": "content",
    "batch_size": 32,
    "provider_config": {
      "api_key": "${OPENAI_API_KEY}"
    }
  }
}
```



---

#### BranchingOperator

**Purpose:** Split a table into multiple output tables using SQL-like filter conditions.

**Category:** Functional

**Class:** `core.operators.functional.branching_operator.BranchingOperator`

| Parameter                         | Type         | Required | Default          | Description                   |
| --------------------------------- | ------------ | -------: | ---------------- | ----------------------------- |
| `branches`                        | list[object] |      Yes | `[]`             | Branch definitions            |
| `branches[].link_id`              | string       |      Yes | -                | Output edge identifier        |
| `branches[].link_name`            | string       |       No | -                | Human-friendly branch name    |
| `branches[].logical_operator`     | string       |       No | `AND`/per-branch | Logical join between criteria |
| `branches[].filter_criteria_list` | list[string] |       No | `[]`             | SQL-like filters              |
| `branches[].filter_criteria_json` | object       |       No | -                | Structured filter criteria    |

**Input Schema**

- Any table with columns referenced by branch criteria

**Output Schema**

- Multiple output tables, one per branch

**Exceptions**

- validation errors
- propagated SQL filter errors

---

#### MergeOperator

**Purpose:** Combine multiple PyArrow tables from different branches using row concatenation or column joins.

**Category:** Functional

**Class:** `core.operators.functional.merge.MergeOperator`

| Parameter                  | Type         | Required | Default | Description                                                    |
| -------------------------- | ------------ | -------: | ------- | -------------------------------------------------------------- |
| `merge_type`               | string       |      Yes | `rows`  | Merge strategy: `rows` (concatenate) or `columns` (join)      |
| `column_option`            | string       |  Conditional | -       | Join type when `merge_type=columns`: `inner_join` or `full_outer` |
| `input_links`              | list[object] |      Yes | `[]`    | Input link configurations                                      |
| `input_links[].link_name`  | string       |      Yes | -       | Unique identifier for each input branch                        |

**Input Schema**

- Multiple PyArrow tables from different branches, each identified by `link_name`
- All tables must contain an `id` column for row merge duplicate detection and column merge joins

**Output Schema**

- **Row Merge (`merge_type=rows`)**: Single table with all rows concatenated vertically
  - Preserves all columns from all input tables
  - Validates no duplicate IDs across tables
- **Column Merge (`merge_type=columns`)**: Single table with columns joined horizontally
  - `inner_join`: Only rows with matching IDs across all tables
  - `full_outer`: All rows from all tables, with nulls for missing values
  - Non-ID columns from subsequent tables get `_<link_name>` suffix
  - Complex types (lists, structs) are remapped without suffix

**Exceptions**

- `FlowExecutionFailedException`: Fewer than 2 input links provided
- `DatasiftException`: Duplicate IDs detected in row merge
- Validation errors for missing or invalid configuration

**Usage Notes**

- Typically used after [`BranchingOperator`](#branchingoperator) to recombine split data flows
- The order of `input_links` determines column suffix application in column merge
- Row merge requires unique IDs across all input tables
- Column merge performs ID-based joins, similar to SQL JOIN operations

**Example Flow Configuration**

```json
{
  "id": "merge-node",
  "name": "merge_branches",
  "operator": "merge",
  "config": {
    "merge_type": "columns",
    "column_option": "inner_join",
    "input_links": [
      {"link_name": "branch1"},
      {"link_name": "branch2"}
    ]
  },
  "input_edges": [
    {"node_id_ref": "branch1-node", "link_name": "branch1"},
    {"node_id_ref": "branch2-node", "link_name": "branch2"}
  ]
}
```

---

#### NOOPOperator

**Purpose:** Pass input rows through unchanged, optionally sleeping for a configured interval.

**Category:** Functional

**Class:** `core.operators.functional.noop.NOOPOperator`

| Parameter   | Type | Required | Default | Description                          |
| ----------- | ---- | -------: | ------- | ------------------------------------ |
| `sleep_sec` | int  |       No | `1`     | Optional delay for testing/debugging |

**Input Schema**

- Any `pyarrow.Table`

**Output Schema**

- Same as input table

---

#### DocIdHashOperator

**Purpose:** Generate a stable hash identifier from content.

**Category:** Functional

**Class:** `core.operators.functional.doc_id_hash.DocIdHashOperator`

**Availability:** Internal operator.

| Parameter     | Type   | Required | Default       | Description        |
| ------------- | ------ | -------: | ------------- | ------------------ |
| `doc_column`  | string |       No | `content`     | Input text column  |
| `doc_id_hash` | string |       No | `doc_id_hash` | Output hash column |

**Output Schema**

- `doc_id_hash`

### Quality Operators

#### LanguageDetect

**Purpose:** Detect document language and confidence scores using a pluggable adapter.

**Category:** Quality

**Class:** `core.operators.quality.language_detection.lang_id.LanguageDetect`

| Parameter                 | Type   | Required | Default      | Description                              |
| ------------------------- | ------ | -------: | ------------ | ---------------------------------------- |
| `doc_column`              | string |       No | `content`    | Text input column                        |
| `filter_unknown_language` | bool   |       No | `false`      | Drop documents that cannot be classified |
| `language_provider`       | string |       No | `langdetect` | Detection provider                       |

**Output Schema**

- language name column
- language score column

---

#### ReadabilityOperator

**Purpose:** Compute readability metrics using `dpk_readability`.

**Category:** Quality

**Class:** `core.operators.quality.readability.ReadabilityOperator`

| Parameter                | Type         | Required | Default           | Description        |
| ------------------------ | ------------ | -------: | ----------------- | ------------------ |
| `doc_column`             | string       |       No | `content`         | Input text column  |
| `readability_score_list` | list[string] |      Yes | default score set | Metrics to compute |

**Output Schema**

- selected readability columns

---

#### RedactionOperator

**Purpose:** Mask words or regex matches in document content.

**Category:** Quality

**Class:** `core.operators.quality.redaction.RedactionOperator`

| Parameter           | Type   | Required | Default           | Description                  |
| ------------------- | ------ | -------: | ----------------- | ---------------------------- |
| `doc_column`        | string |       No | `content`         | Input text column            |
| `regex`             | string |      Yes | -                 | Pattern or literal to redact |
| `masking_character` | string |       No | `*`               | Replacement character        |
| `stats_column`      | string |       No | `redaction_stats` | Per-row redaction count      |

**Output Schema**

- updated `content`
- redaction stats column

---
#### PIIAndHAPAnnotator

**Purpose:** Detect Personally Identifiable Information (PII) and Hate, Abuse, and Profanity (HAP) content using Large Language Models.

**Category:** Quality

**Short Name:** `pii_and_hap`

**Class:** `core.operators.quality.pii_and_hap.pii_and_hap_annotator.PIIAndHAPAnnotator`

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `provider` | string | No | `ollama` | LLM provider (`ollama`, `watsonx`, `litellm`) |
| `provider_config` | object | No | `{}` | Provider-specific configuration |
| `model_id` | string | Conditional | `openai/granite3.1-dense:8b` | Model for detection in `<provider>/<model_id>` format (required for watsonx/litellm) |
| `doc_column` | string | No | `content` | Input text column |
| `pii_types` | list[string] | No | all types | PII types to detect |
| `hap_types` | list[string] | No | all types | HAP types to detect |
| `output_column_prefix` | string | No | `pii_hap_` | Prefix for output columns |

**Output Schema:**
- `{prefix}pii_detected` (bool)
- `{prefix}hap_detected` (bool)
- `{prefix}pii_types` (list)
- `{prefix}hap_types` (list)
- Optional confidence and reasoning columns

**See Also:** [PII and HAP Documentation](docs/operators/pii_and_hap/pii_and_hap.md)

---



#### EdedupOperator

**Purpose:** Remove exact duplicate documents using `dpk_ededup`.

**Category:** Quality

**Class:** `core.operators.quality.ededup.EdedupOperator`

| Parameter     | Type   | Required | Default          | Description               |
| ------------- | ------ | -------: | ---------------- | ------------------------- |
| `doc_column`  | string |       No | `content`        | Content column to compare |
| `doc_id_hash` | string |       No | `doc_id_hash`    | Hash/id column            |
| `filter`      | object |       No | `HashFilter({})` | Hash filter state/config  |

---

#### MLEnrichmentOperator

**Purpose:** Compute text quality features using `dpk_enrichment`.

**Category:** Quality

**Class:** `core.operators.quality.ml_enrichment.MLEnrichmentOperator`

| Parameter                        | Type   | Required | Default           | Description                          |
| -------------------------------- | ------ | -------: | ----------------- | ------------------------------------ |
| `doc_column`                     | string |       No | `content`         | Input text column                    |
| `lang_column`                    | string |       No | language constant | Language column                      |
| `output_column_prefix`           | string |       No | `""`              | Prefix for generated feature columns |
| `newline_normalized_column_name` | string |       No | `""`              | Optional normalized text output      |
| `error_column_name`              | string |       No | `""`              | Optional per-row error column        |

---

#### SQLFilterOperator

**Purpose:** Filter rows with SQL-like expressions or structured criteria and optionally drop selected columns.

**Category:** Quality

**Class:** `core.operators.quality.sql_filter.SQLFilterOperator`

| Parameter                 | Type         | Required | Default | Description                       |
| ------------------------- | ------------ | -------: | ------- | --------------------------------- |
| `filter_criteria_list`    | list[string] |       No | `[]`    | SQL-style predicates              |
| `filter_logical_operator` | string       |       No | `AND`   | Join operator for criteria        |
| `features_to_drop`        | list[string] |       No | `[]`    | Columns to remove after filtering |
| `filter_criteria_json`    | object       |       No | -       | Structured criteria format        |

### VectorDB Operators

#### VectorDBOperator

**Purpose:** Index documents and embeddings into a vector database through a provider adapter interface.

**Category:** VectorDB

**Class:** `core.operators.vectordb.vectordb_operator.VectorDBOperator`

| Parameter | Type | Required | Default | Description                 |
|---|---|---:|---|-----------------------------|
| `provider` | string | Yes | - | VectorDB backend (`opensearch` or `milvus`) |
| `index_name` | string | Yes | - | Target index/collection name |
| `doc_id_column` | string | No | `doc_id_hash` | Primary document id column  |
| `create_index` | bool | No | `true` | Auto-create index           |
| `provider_config` | object | Yes | - | Provider-specific configuration (see examples below) |
| `available_features` | object | No | - | Feature definitions for vector DB schema |
| `feature_mappings` | object | No | - | Mapping of PyArrow columns to vector DB fields |

**Multi-Model Embeddings Support:**

The VectorDBOperator supports multiple embedding columns with different dimensions:
- **OpenSearch**: Full multi-model support
  - Automatically detects all vector columns from `available_features` (columns with `type: "vector"`)
  - Auto-detects dimension for each vector column from actual embedding data
  - Creates index fields for all vector columns with their respective dimensions
  - Example: Store both 384-dim and 768-dim embeddings in same document (e.g., `embeddings` and `embeddings_alt`)
  - Use with BranchingOperator + multiple EmbeddingsOperators + MergeOperator for multi-model pipelines
  - See `sample_flows/branching_dual_embeddings_flow.json` for complete example
- **Milvus**: Single-model support (uses `embeddings` column only)
  - Dimension auto-detected from `embeddings` column data
  - Additional vector columns in the table are stored as metadata but not indexed as vectors
  - Multi-model support planned for future update
  - For multi-model scenarios with Milvus, use separate collections per embedding model

**Supported Vector Databases:**

1. **OpenSearch** (`provider: "opensearch"`)
   - Multiple KNN engines: NMSLIB, Faiss, Lucene
   - Configurable space types: cosinesimil, l2, innerproduct
   - HTTP/HTTPS connections with optional authentication

2. **Milvus** (`provider: "milvus"`)
   - **Index Types**:
     - Dense: HNSW, IVF_FLAT, IVF_SQ8, IVF_PQ, FLAT, DISKANN, AUTOINDEX
     - Sparse: SPARSE_INVERTED_INDEX, SPARSE_WAND
   - **Metric Types**:
     - Dense: L2 (Euclidean), IP (Inner Product), COSINE
     - Sparse: BM25 (required for sparse mode)
   - **Vector Modes**:
     - Dense vectors only (default)
     - Sparse + Dense vectors (dual storage with BM25 function)
   - **Deployment Options**:
     - Standalone Milvus (local or remote)
     - Watsonx.data Milvus (IBM Cloud, SSL-enabled)
   - **Features**:
     - Auto-detection of vector dimensions from embeddings
     - BM25 sparse vector generation from content
     - Configurable index parameters (M, efConstruction for HNSW)
     - Batch processing with configurable batch sizes
     - SSL/TLS support for secure connections

**OpenSearch Configuration Example:**
```json
{
  "operator": "vectordb",
  "config": {
    "provider": "opensearch",
    "index_name": "my_documents",
    "create_index": true,
    "provider_config": {
      "host": "localhost",
      "port": 9200,
      "engine": "nmslib",
      "space_type": "cosinesimil",
      "username": "admin",
      "password": "admin"
    }
  }
}
```

**Milvus Standalone Configuration Example:**
```json
{
  "operator": "vectordb",
  "config": {
    "provider": "milvus",
    "index_name": "my_collection",
    "create_index": true,
    "add_sparse_vector": false,
    "provider_config": {
      "auth_type": "standalone",
      "host": "localhost",
      "port": 19530,
      "uri": null,
      "token": null,
      "username": "root",
      "password": "Milvus", # pragma: allowlist secret
      "database": "default",
      "secure": false,
      "index_type": "HNSW",
      "metric_type": "L2",
      "index_parameters": {
        "M": 16,
        "efConstruction": 256
      },
      "batch_size": 100,
      "primary_key_field": "pk"
    },
    "available_features": {
      "doc_id_hash": {
        "name": "Document ID",
        "available_for_vector_db": true,
        "mandatory_for_vector_db": true,
        "type": "string",
        "is_primary": true
      },
      "embeddings": {
        "name": "Embeddings",
        "available_for_vector_db": true,
        "mandatory_for_vector_db": true,
        "type": "vector"
      }
    },
    "feature_mappings": {
      "doc_id_hash": "pk",
      "embeddings": "vector_embeddings"
    }
  }
}
```

**Milvus Watsonx.data with gRPC Configuration Example:**
```json
{
  "operator": "vectordb",
  "config": {
    "provider": "milvus",
    "index_name": "wxdata_collection",
    "add_sparse_vector": false,
    "create_index": true,
    "provider_config": {
      "auth_type": "grpc",
      "host": "YOUR_WXDATA_HOST.lakehouse.ibmappdomain.cloud",
      "port": 32671,
      "uri": null,
      "token": null,
      "username": "ibmlhapikey_YOUR_USERNAME",
      "password": "YOUR_API_KEY", # pragma: allowlist secret
      "database": "default",
      "secure": true,
      "index_type": "HNSW",
      "metric_type": "L2",
      "index_parameters": {
        "M": 16,
        "efConstruction": 256
      },
      "batch_size": 100,
      "primary_key_field": "pk"
    }
  }
}
```

**Milvus Watsonx.data with IAM Token Configuration Example:**
```json
{
  "operator": "vectordb",
  "config": {
    "provider": "milvus",
    "index_name": "wxdata_token_collection",
    "create_index": true,
    "add_sparse_vector": false,
    "provider_config": {
      "auth_type": "token",
      "host": "YOUR_WXDATA_HOST.lakehouse.ibmappdomain.cloud",
      "port": 32671,
      "uri": null,
      "token": "YOUR_IAM_TOKEN",
      "username": "YOUR_USERNAME",
      "password": null,
      "database": "default",
      "secure": true,
      "index_type": "HNSW",
      "metric_type": "L2",
      "index_parameters": {
        "M": 16,
        "efConstruction": 256
      },
      "batch_size": 100,
      "primary_key_field": "pk"
    }
  }
}
```

**Provider Config Parameters:**

**OpenSearch:**
- `host`: OpenSearch server hostname
- `port`: OpenSearch server port (default: 9200)
- `engine`: KNN engine (nmslib, faiss, lucene)
- `space_type`: Distance metric (cosinesimil, l2, innerproduct)
- `username`: Optional authentication username
- `password`: Optional authentication password

**Milvus:**
- `auth_type`: **Required** - Authentication type (`standalone`, `grpc`, `uri`, or `token`)
- `host`: Milvus server hostname (required for `standalone`, `grpc`, `token`)
- `port`: Milvus server port (default: 19530, required for `standalone`, `grpc`, `token`)
- `uri`: Full connection URI (required for `uri` auth_type)
- `token`: IAM token (required for `token` auth_type)
- `username`: Authentication username (optional for `standalone`, required for `grpc` and `token`)
- `password`: Authentication password/API key (optional for `standalone`, required for `grpc` - should be API key)
- `database`: Database name (default: "default")
- `secure` : Required for IBM watsonx.data MilvusDB for https connection and is set to true in this case.
- `index_type`: Index algorithm (HNSW, IVF_FLAT, IVF_SQ8, IVF_PQ, FLAT, DISKANN, AUTOINDEX for dense; SPARSE_INVERTED_INDEX, SPARSE_WAND for sparse)
- `metric_type`: Distance metric (L2, IP, COSINE for dense; BM25 required for sparse mode)
- `index_parameters`: Index-specific parameters (e.g., M and efConstruction for HNSW)
- `batch_size`: Batch size for bulk operations (default: 100)
- `primary_key_field`: Name of the primary key field in Milvus collection (default: "pk")

**Milvus Authentication Types:**
- `standalone`: Local Milvus with optional username/password
- `grpc`: IBM wx.data with gRPC (username must have `ibmlhapikey_` prefix, password is API key)
- `uri`: Pre-constructed URI with embedded API key (format: `https://ibmlhapikey_<username>:<api-key>@<host>:<port>`)
- `token`: IAM token-based (constructs URI internally: `https://ibmlhtoken_<username>:<token>@<host>:<port>`)

**Sparse Vector Mode:**

When `add_sparse_vector: true` is set:
- Requires `metric_type: "BM25"` (validated)
- Creates BM25 function for automatic sparse vector generation from text content
- Feature mappings must include:
  - `embeddings` → `vector` (dense embeddings)
  - `sparse_embeddings` → `sparse_vector` (BM25-generated)
  - `content` → `text` (source text for BM25)
- Index type auto-set to `SPARSE_INVERTED_INDEX` if not specified
- See [`sample_flows/milvus_sparse_localhost_flow.json`](sample_flows/milvus_sparse_localhost_flow.json) for complete example

**Notes:**
- Vector dimensions are auto-detected from actual embedding data for each vector column
- OpenSearch supports multiple vector columns with different dimensions in a single index
- Milvus currently supports single vector column (multi-model support planned for future update)
- See [`docs/milvus/README.md`](../../docs/milvus/README.md) for detailed Milvus configuration
- See [`PROVIDER_CONFIG_GUIDE.md`](src/datasift/core/operators/vectordb/PROVIDER_CONFIG_GUIDE.md) for provider configuration patterns

**Provider Config (OpenSearch)**

The `provider_config` object supports the following parameters for OpenSearch:

| Parameter              | Type   | Required | Default         | Description                                                                        |
| ---------------------- | ------ | -------: | --------------- | ---------------------------------------------------------------------------------- |
| `host`                 | string |       No | `localhost`     | OpenSearch host                                                                    |
| `port`                 | int    |       No | `9200`          | OpenSearch port                                                                    |
| `engine`               | string |       No | `faiss`         | KNN engine (faiss, lucene, nmslib, jvector)                                        |
| `algorithm`            | string |       No | `hnsw`          | KNN algorithm (hnsw, ivf)                                                          |
| `space_type`           | string |       No | `l2`            | Similarity metric (l2, cosine, inner_product)                                      |
| `schema_template_path` | string |       No | `null`          | Path to JSON schema template (relative to `src/datasift/core/operators/vectordb/`) |
| `engine_parameters`    | object |       No | Auto-configured | Engine-specific parameters (ef_construction, m, nlist, nprobe)                     |
| `index_settings`       | object |       No | `{}`            | Additional OpenSearch index settings                                               |

**Schema Templates**

Schema templates provide reusable index configurations with placeholder-based dynamic values:

- **Built-in Templates**:
  - `schemas/default_schema.v1.json`: Basic schema with standard field types
  - `schemas/template_with_content_analyzer.v1.json`: Template with custom content analyzer for text processing

- **Placeholders**: Templates support the following placeholders that are replaced at runtime:
  - `__VECTOR_DIMENSION__`: Vector embedding dimension
  - `__ENGINE__`: KNN engine name
  - `__ALGORITHM__`: KNN algorithm name
  - `__SPACE_TYPE__`: Similarity metric
  - `__ENGINE_PARAMETERS__`: Engine-specific parameters object

- **Fallback Behavior**: If template is not found or invalid, the system falls back to dynamic schema generation with a warning

**Metadata Normalization**

The VectorDBOperator automatically normalizes and aggregates metadata columns:

- **Column Aliases**: Automatically maps common column name variations:
  - `path` → `source`
  - `pages_processed` → `page_count`
  - `mime_type`, `content_type` → `mimetype`

- **Field Derivation**: Automatically derives missing metadata fields:
  - `extension`: Derived from `name` or `source` if missing
  - `mimetype`: Derived from `extension` using standard MIME type mappings

- **Predefined Metadata Fields**: The following fields are automatically collected into a `metadata` object:
  - `name`, `size`, `created_time`, `modified_time`, `source`, `mimetype`, `extension`, `page_count`

**Input Schema**

- `doc_id_column`
- `embeddings_column`

**Output Schema**

- input table unchanged
- side effect: indexed vector records

**Exceptions**

- [`DatasiftException`](src/datasift/exceptions/datasift_exceptions.py)

**Example Configuration**

Basic usage with default schema:

```json
{
  "operator_type": "datasift.core.operators.vectordb.vectordb_operator.VectorDBOperator",
  "operator_params": {
    "provider": "opensearch",
    "index_name": "my_documents",
    "provider_config": {
      "host": "localhost",
      "port": 9200,
      "engine": "faiss",
      "algorithm": "hnsw",
      "vector_dimension": 384
    }
  }
}
```

Using a schema template:

```json
{
  "operator_type": "datasift.core.operators.vectordb.vectordb_operator.VectorDBOperator",
  "operator_params": {
    "provider": "opensearch",
    "index_name": "document_chunks",
    "provider_config": {
      "schema_template_path": "schemas/template_with_content_analyzer.v1.json",
      "host": "localhost",
      "port": 9200,
      "engine": "faiss",
      "algorithm": "hnsw",
      "vector_dimension": 768
    }
  }
}
```

---

### Storage Operators

#### DocumentSetOperator

**Purpose:** Store PyArrow table data and document-set metadata using a hexagonal architecture with pluggable metadata and data adapters.

**Category:** Storage

**Class:** `core.operators.document_sets.document_set_operator.DocumentSetOperator`

| Parameter             | Type   | Required | Default                            | Description                                              |
| --------------------- | ------ | -------: | ---------------------------------- | -------------------------------------------------------- |
| `document_set_name`   | string |      Yes | -                                  | Unique name for the document set                         |
| `description`         | string |       No | `null`                             | Description of the document set                          |
| `metadata`            | object |       No | `null`                             | Additional metadata payload stored with the document set |
| `retain_deleted_docs` | bool   |       No | `false`                            | Whether to retain soft-deleted documents                 |
| `document_set_id`     | string |       No | `null`                             | Existing document set UUID for update flows              |
| `database_path`       | string |       No | `data/duckdb/document_sets.duckdb` | Database file path used by DuckDB-backed adapters        |
| `metadata_backend`    | string |       No | `duckdb`                           | Metadata repository backend                              |
| `data_backend`        | string |       No | `duckdb`                           | Data store backend                                       |
| `metadata_config`     | object |       No | `{}`                               | Backend-specific metadata repository configuration       |
| `data_config`         | object |       No | `{}`                               | Backend-specific data store configuration                |

**Description**

The Document Set operator persists table rows and document-set metadata through separate port interfaces:

- `DocumentSetMetadataRepository`
- `DocumentSetDataStore`

The operator creates concrete adapters through:

- `MetadataRepositoryFactory`
- `DataStoreFactory`

Current production support is DuckDB for both metadata and data storage. The operator returns the input table unchanged, so it can be placed mid-pipeline without breaking downstream processing.

**Architecture**

- Hexagonal architecture with ports and adapters
- Separate metadata and data storage abstractions
- Factory-based backend creation
- Shared DuckDB storage reuse for current adapters

**Input Schema**

- `id` (required): UUID document identifier

Common upstream fields from the sample flow:

- `name`
- binary content from ingest
- `content`

**Output Schema**

- Input table unchanged (pass-through design)
- Side effect: data and metadata persisted through configured adapters

**Metadata Output**

- `document_set_id`: UUID of the document set
- `document_set_name`: Name of the document set
- `database_path`: Database path used for storage
- `stored_documents`: Number of rows written in the operation
- error metadata when persistence fails

**Features**

- Persistent storage of document collections
- Hexagonal architecture for backend extensibility
- Separate metadata and data persistence layers
- Automatic schema handling through data-store adapters
- Automatic metric recomputation through `DocumentSetService`
- Pass-through design allows chaining with downstream operators

**Exceptions**

- [`FlowValidationException`](src/datasift/exceptions/datasift_exceptions.py): Invalid operator configuration
- [`FlowExecutionFailedException`](src/datasift/exceptions/datasift_exceptions.py): Storage execution failed
- [`DatasiftException`](src/datasift/exceptions/datasift_exceptions.py): Adapter, validation, or persistence error

**Sample Flow Configuration**

```json
{
  "global_config": {
    "storage_type": "duckdb",
    "database_path": "data/assets.db"
  },
  "nodes": [
    {
      "id": "c3d4e5f6-a7b8-4c9d-0e1f-2a3b4c5d6e7f",
      "name": "store_in_document_set",
      "operator_type": "datasift.core.operators.storage.document_set.DocumentSetOperator",
      "operator_params": {
        "document_set_name": "integration_test_documents",
        "description": "Integration test for hexagonal architecture",
        "data_backend": "duckdb"
      }
    }
  ]
}
```

**Configuration Notes:**

- `storage_type` in `global_config` controls metadata storage backend (default: "duckdb")
- `database_path` in `global_config` specifies the database file location
- `data_backend` in operator parameters controls PyArrow table data storage
- Metadata and data can use different backends independently

**Flow Pattern**

```text
IngestLocalOperator -> ExtractOperator -> DocumentSetOperator
```

**End-to-End Flow Example**

```json
{
  "name": "ingest-extract-documentset",
  "flow_id": "d1e2f3a4-b5c6-4d7e-8f9a-0b1c2d3e4f5a",
  "description": "Integration test flow for document set hexagonal architecture: Ingest -> Extract -> DocumentSet",
  "global_config": {
    "storage_type": "duckdb",
    "database_path": "data/integration_test.db"
  },
  "storage": "in-memory",
  "execute_type": "local",
  "global_config": {
    "doc_column": "content",
    "disable_validation": true,
    "force_ingest": true
  },
  "dag": [
    {
      "id": "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
      "name": "ingest_local_folder",
      "operator": "ingest_local",
      "config": {
        "paths": "tests/fixtures/invoices",
        "include_filter": "pdf,txt,md",
        "store_binary_content": true
      }
    },
    {
      "id": "b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e",
      "name": "extract_documents",
      "operator": "extract_operator",
      "config": {
        "text_extraction_mode": "docling_library",
        "entity_extraction_mode": "none",
        "doc_column": "content"
      }
    },
    {
      "id": "c3d4e5f6-a7b8-4c9d-0e1f-2a3b4c5d6e7f",
      "name": "store_in_document_set",
      "operator": "document_set",
      "config": {
        "document_set_name": "integration_test_documents",
        "description": "Integration test for hexagonal architecture",
        "database_path": "data/integration_test.db",
        "metadata_backend": "duckdb",
        "data_backend": "duckdb"
      }
    }
  ]
}
```

**API Integration**

Document sets are also exposed through `/api/v1/document-sets`:

- `POST /api/v1/document-sets`
- `GET /api/v1/document-sets`
- `GET /api/v1/document-sets/{id}`
- `PATCH /api/v1/document-sets/{id}`
- `DELETE /api/v1/document-sets/{id}`
- `GET /api/v1/document-sets/{id}/preview`

**Error Codes**

- `document_set_not_found`
- `document_set_invalid_data`
- `document_set_storage_error`
- `document_set_already_exists`
- `document_set_data_store_error`
- `document_set_table_not_found`

**Testing**

```bash
source src/datasift_opensource/backend/.venv/bin/activate
export PYTHONPATH="$(pwd)/src:${PYTHONPATH}"
uv run pytest tests/integration/api/test_document_sets_api.py -v
```

**Extension**

For new backends, implement the document set ports, register adapters with the factories, and configure `metadata_backend` and `data_backend`. See [`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## DatasiftFlowManager API

**Class:** [`DatasiftFlowManager`](src/datasift/lib/datasift_flow_manager.py:24)

### Constructor
- `DatasiftFlowManager(flow_file=None, flow_def=None, job_id=None, job_run_id=None, flow_id=None, enable_custom_operators=None)`


Exactly one of `flow_file` or `flow_def` must be provided.

### `validate()`

Defined at [`validate()`](src/datasift/lib/datasift_flow_manager.py:165).

Returns:

```python
{
  "valid": bool,
  "errors": list,
  "warnings": list
}
```

### `execute()`

Defined at [`execute()`](src/datasift/lib/datasift_flow_manager.py:213).

Returns the result of flow execution from the executor.

### `get_execution_metadata()`

Defined at [`get_execution_metadata()`](src/datasift/lib/datasift_flow_manager.py:245).

Returns job and flow metadata.

### `get_execution_logs()`

Defined at [`get_execution_logs()`](src/datasift/lib/datasift_flow_manager.py:272).

Returns `list[str]`.

### `list_operators(verbose=False)`

Defined at [`list_operators()`](src/datasift/lib/datasift_flow_manager.py:308).

Returns a formatted operator listing via [`datasift.utils.operators.display.list_operators()`](src/datasift/utils/operators/display.py).

**Display Modes:**

- **Default (verbose=False)**: Summary table with Owner, Attributes (count), Features (count) columns
- **Verbose (verbose=True)**: Detailed view with full operator parameters and descriptions

**Category Sorting Order:**
Operators are sorted by category: Ingest, Extract, Quality, Functional, VectorDB, Storage

### Method name note

The current class does **not** expose `execute_flow()` or `validate_flow()` methods. Use:

- [`execute()`](src/datasift/lib/datasift_flow_manager.py:213)
- [`validate()`](src/datasift/lib/datasift_flow_manager.py:165)

---

## CLI API Reference

**Entry point:** [`main()`](src/datasift/cli/datasift_cli.py:147)

### Command forms

```bash
datasift-orchestrator --flow-file ./path/to/flow.json
datasift-orchestrator --flow-file ./path/to/flow.json --validate
datasift-orchestrator validate-flow ./path/to/flow.json
datasift-orchestrator --list-operators              # Summary table
datasift-orchestrator --list-operators --verbose    # Detailed view
```

### Global arguments

| Argument           | Short |    Required | Description                                     |
| ------------------ | ----- | ----------: | ----------------------------------------------- |
| `--flow-file`      | `-f`  | Conditional | Flow JSON path                                  |
| `--list-operators` | `-lo` |          No | List operators and exit (summary table format)  |
| `--verbose`        | `-v`  |          No | Show detailed operator info (use with `-lo`)    |
| `--validate`       | -     |          No | Validate instead of executing                   |

### Exit codes

| Exit code | Meaning                                       |
| --------- | --------------------------------------------- |
| `0`       | Validation succeeded                          |
| `1`       | Validation failed or file/JSON loading failed |

---

## Flow Configuration API

Datasift uses a simplified authoring format for creating flows. See [`sample_flows/complete_pipeline_flow.json`](sample_flows/complete_pipeline_flow.json) for a complete example.

### Root structure

```json
{
  "flow_name": "invoice processing flow",
  "description": "description",
  "flow": [],
  "global_config": {
    "storage": "in-memory",
    "execute_type": "local"
  }
}
```
[`DatasiftFlowManager`](src/datasift/lib/datasift_flow_manager.py:140) also accepts root-level flow definitions without a wrapping `flow` key.

### Flow fields

| Field           | Type   | Required | Description                       |
| --------------- | ------ | -------: | --------------------------------- |
| `flow_name`     | string |      Yes | Human-readable flow name          |
| `description`   | string |       No | Flow description                  |
| `flow`          | array  |      Yes | Ordered operator definitions      |
| `global_config` | object |       No | Shared runtime config             |

### Operator structure

```json
{
  "name": "operator_name",
  "type": "operator_type",
  "depends_on": ["upstream_operator"],
  "config": {}
}
```

### Operator fields

| Field       | Type   | Required | Description                                |
| ----------- | ------ | -------: | ------------------------------------------ |
| `name`      | string |      Yes | Unique operator name within the flow       |
| `type`      | string |      Yes | Registered operator type (e.g., `chunker`) |
| `depends_on`| array  |       No | List of upstream operator names            |
| `config`    | object |       No | Operator-specific configuration            |

### Dependency declaration

Operators declare dependencies using the `depends_on` field:

```json
{
  "name": "extract",
  "type": "extract_operator",
  "depends_on": ["ingest"],
  "config": {}
}
```

The system automatically generates the execution DAG from these dependencies.

### Validation rules

Validation is performed by [`FlowValidator`](src/datasift/lib/datasift_flow_manager.py:20) and CLI validation helpers.

Practical rules from the reviewed code:

- operator short names must resolve to registered operators
- required operator config must validate
- required input features must be present
- branch and filter references must use valid columns
- flow file must be valid JSON

---

## Exception Reference

All custom exception types reviewed here come from [`datasift_exceptions.py`](src/datasift/exceptions/datasift_exceptions.py).

### `DatasiftException`

Base exception for application-level failures.

Use when:

- a caller needs an HTTP status code
- an error code should propagate through middleware
- a general Datasift runtime/configuration failure occurs

### `FlowExecutionFailedException`

Raised for flow execution failures.

### `FlowValidationException`

Raised when a flow definition is invalid.

Carries:

- `errors`
- `warnings`

### `PrefectFlowFailed`

Raised when Prefect-backed orchestration fails for a task.

### `ValidationException`

Generic validation failure outside full flow validation.

### `ConfigurationError`

Raised for invalid or missing configuration.

### `DependencyError`

Raised when an optional dependency is missing.

### `ExternalServiceError`

Raised when external services fail.

Typical cases:

- API calls
- auth problems
- rate limits
- network failures

### `FlowNotFoundException`

Raised when requested flow storage entries do not exist.

### `FlowAlreadyExistsException`

Raised when creating a duplicate flow.

### `FlowInvalidDataException`

Raised when flow payload or fields are malformed.

### `FlowStorageException`

Raised when storage operations fail, such as file I/O problems.

### `RepositoryConfigurationException`

Raised when repository type or repository config is invalid.

### `ValidationAlert`

Dictionary-like validation payload used in warnings/errors.

### `ValidationAlertEncoder`

JSON encoder for validation alerts.

---

## Utilities API

### PyArrow handler utilities

Defined in [`pyarrow_handler.py`](src/datasift/utils/data/pyarrow_handler.py)

#### `BaseParquetTableHandler`

Abstract contract for parquet read/write/delete operations.

Key methods:

- `read_table()` - Read PyArrow table from file
- `save_table()` - Save PyArrow table to file
- `delete_rows()` - Delete rows from table
- `delete_file()` - Delete file from storage

#### `CpdParquetTableHandler`

Concrete local-file implementation.

#### `get_parquet_table_handler()`

Defined at [`get_parquet_table_handler()`](src/datasift/utils/data/pyarrow_handler.py) in datasift utilities

Returns the default parquet handler implementation.

### Schema utilities

Defined in [`schema_utils.py`](src/datasift/utils/data/schema_utils.py)

#### `align_table_schema(table, all_cols)`

Defined at [`align_table_schema()`](src/datasift/utils/data/schema_utils.py) in schema utilities

Adds missing columns with null values and aligns ordering.

#### `_combine_tables(tables, table_type)`

Defined at [`_combine_tables()`](src/datasift/utils/data/schema_utils.py) in schema utilities

Safely concatenates tables and warns on duplicate IDs.

#### `_total_rows(tables)`

Defined at [`_total_rows()`](src/datasift/utils/data/schema_utils.py) in schema utilities

Computes total row counts across a table, list, dict, or `None`.

### Document class utilities

Defined in [`document_class_utils.py`](src/datasift/utils/document_class_utils.py)

#### `DocumentClassUtils.normalize_filename(name)`

Defined at [`normalize_filename()`](src/datasift/utils/document_class_utils.py) in document class utilities

Normalizes human labels into stable filenames.

#### `DocumentClassUtils.load_document_class(doc_class_path)`

Defined at [`load_document_class()`](src/datasift/utils/document_class_utils.py) in document class utilities

Loads a document class JSON definition.

#### `DocumentClassUtils.generate_docling_template(doc_class_path, include_nested=True, max_fields=None)`

Defined at [`generate_docling_template()`](src/datasift/utils/document_class_utils.py) in document class utilities

Builds a Docling extraction template from a document class schema.

**Raises**

- `FileNotFoundError`
- `json.JSONDecodeError`

### Operator display utility

Defined in [`display.py`](src/datasift/utils/operators/display.py)

#### `list_operators(verbose=False)`

Defined at [`list_operators()`](src/datasift/utils/operators/display.py)

Generates the same operator catalog used by the CLI and [`DatasiftFlowManager.list_operators()`](src/datasift/lib/datasift_flow_manager.py).

**Parameters:**

- `verbose` (bool): If True, shows detailed operator information with all parameters. If False (default), shows summary table with Owner, Attributes, Features columns.

**Output Format:**

- **Summary mode**: Table with columns: Owner (operator name), Attributes (parameter count), Features (capability count)
- **Verbose mode**: Detailed listing with full parameter descriptions, types, and default values
- **Category order**: Ingest, Extract, Quality, Functional, VectorDB, Storage
