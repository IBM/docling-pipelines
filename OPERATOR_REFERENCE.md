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
- For classification-specific architecture details, see [`docs/operators/document_classifier.md`](docs/operators/document_classifier.md), which documents the runtime-native hexagonal package used by [`DocumentClassifierOperator`](src/datasift/core/operators/quality/document_classifier.py:26).

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

**Purpose:** Discover files in a local directory and collect metadata for downstream extraction.

**Category:** Ingest

**Class:** `core.operators.ingest.ingest_local_folder.IngestLocalOperator`

| Parameter             | Type   | Required | Default              | Description                                         |
| --------------------- | ------ | -------: | -------------------- | --------------------------------------------------- |
| `input_folder`        | string |      Yes | `../test-data/input` | Root folder to crawl                                |
| `include_filter`      | string |       No | -                    | Comma-separated extensions to include               |
| `exclude_filter`      | string |       No | -                    | Comma-separated extensions to exclude               |
| `max_files`           | int    |       No | `100`                | Maximum number of files to ingest                   |
| `max_file_size`       | int    |       No | `100`                | Maximum file size in MB                             |
| `force_ingest`        | bool   |       No | `false`              | Reprocess already-seen documents                    |
| `retain_deleted_docs` | bool   |       No | project constant     | Retain source-deleted docs in incremental scenarios |

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
    "input_folder": "./tests/fixtures/invoices",
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

- provider-normalized document rows with metadata and optional binary content

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

**Purpose:** Classifies documents into predefined types using LLM-based classification with confidence scoring and reasoning. Implements hexagonal architecture supporting multiple LLM providers (Ollama, LiteLLM, Watsonx).

**Category:** Quality

**Class:** `core.operators.quality.classification.document_classifier.DocumentClassifierOperator`

| Parameter              | Type      | Required | Default             | Description                                                                               |
| ---------------------- | --------- | -------- | ------------------- | ----------------------------------------------------------------------------------------- |
| `provider`             | string    | No       | `"ollama"`          | LLM provider: `"ollama"`, `"litellm"`, or `"watsonx"`                                     |
| `model_id`             | string    | No       | `"granite4:latest"` | Model identifier (e.g., `"granite4:latest"`, `"openai/gpt-4o-mini"`, `"claude-3-sonnet"`) |
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

**Ollama:**

```json
{
  "provider": "ollama",
  "model_id": "granite4:latest"
}
```

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
- Ollama via OpenAI-compatible endpoint: `openai/llama3` with `api_base: "http://localhost:11434/v1"`

**Watsonx:**

```json
{
  "provider": "watsonx",
  "model_id": "ibm/granite-13b-chat-v2",
  "provider_config": {
    "api_base": "https://us-south.ml.cloud.ibm.com",
    "api_key": "${WATSONX_API_KEY}",
    "container_kind": "project",
    "container_id": "${WATSONX_PROJECT_ID}",
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

**Example - Basic Ollama Classification**

```json
{
  "id": "classify-node",
  "name": "classify",
  "operator": "document_classifier",
  "config": {
    "provider": "ollama",
    "model_id": "granite4:latest",
    "document_types": ["invoice", "receipt", "contract", "report"],
    "confidence_threshold": 7.0,
    "include_confidence": true,
    "include_reasoning": false
  }
}
```

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
    "model_id": "openai/llama3",
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

Uses hexagonal architecture (ports and adapters pattern):

- **Domain Layer**: Pure business logic with `ClassificationRequest`, `ClassificationResponse`, `ModelInfo` models
- **Ports Layer**: `ClassificationServicePort` interface defining classification contract
- **Adapters Layer**: Provider-specific implementations (OllamaClassificationAdapter, LiteLLMClassificationAdapter, WatsonxClassificationAdapter)
- **Factory Layer**: `ClassificationAdapterFactory` with decorator-based auto-registration

**Related Documentation**

- [Classification Operator Guide](docs/operators/document_classifier.md)
- [Extract Operator](docs/operators/extract_operator.md)

---

### Extract Operators

#### ExtractOperator

**Purpose:** Unified extraction operator using hexagonal architecture with multiple adapters for text extraction (docling_library, docling_serve) and entity extraction (ollama, docling, litellm, none).

**Category:** Extract

**Class:** `core.operators.extract.extract_operator.ExtractOperator`

| Parameter                                                 | Type   | Required | Default                 | Description                                                                                       |
| --------------------------------------------------------- | ------ | -------: | ----------------------- | ------------------------------------------------------------------------------------------------- |
| `text_extraction_mode`                                    | string |       No | `docling_library`       | Text extraction mode: `docling_library` (local with optional VLM) or `docling_serve` (remote API) |
| `entity_extraction_mode`                                  | string |       No | `none`                  | Entity extraction mode: `ollama`, `docling`, `litellm`, or `none`                                 |
| `doc_column`                                              | string |       No | `doc_content`           | Column name for storing extracted text content                                                    |
| `output_column`                                           | string |       No | `entities`              | Column name for storing extracted entities                                                        |
| `extract_tables`                                          | bool   |       No | `true`                  | Extract tables from documents (text extraction)                                                   |
| `extract_images`                                          | bool   |       No | `true`                  | Extract images from documents (text extraction)                                                   |
| `max_workers`                                             | int    |       No | auto                    | Maximum parallel workers (auto-detected based on CPU)                                             |
| `use_processes`                                           | bool   |       No | `false`                 | Use ProcessPoolExecutor vs ThreadPoolExecutor                                                     |
| `expand_extracted_data`                                   | bool   |       No | `false`                 | Expand entity JSON into individual columns (entity extraction only)                               |
| `custom_schema`                                           | object |       No | `{}`                    | Schema dictionary for structured extraction                                                       |
| **VLM Parameters (docling_library mode)**                 |
| `use_vlm_pipeline`                                        | bool   |       No | `false`                 | Enable VLM (Vision-Language Model) pipeline                                                       |
| `vlm_preset`                                              | string |       No | `granite_docling`       | VLM preset name when VLM enabled                                                                  |
| `vlm_engine_type`                                         | string |       No | `transformers`          | VLM engine: `transformers`, `mlx`, `api_*` variants                                               |
| `vlm_provider_config`                                     | object |       No | `null`                  | Provider-specific VLM configuration                                                               |
| **ASR Parameters (docling_library mode for audio/video)** |
| `use_asr_pipeline`                                        | bool   |       No | `false`                 | Enable ASR (Automatic Speech Recognition) for audio/video files                                   |
| `asr_model_name`                                          | string |       No | `whisper_turbo`         | ASR model name (e.g., `whisper_turbo`, `whisper_large`)                                           |
| **Docling Serve Parameters (docling_serve mode)**         |
| `docling_serve_base_url`                                  | string |       No | `http://localhost:5001` | Docling Serve API endpoint                                                                        |
| `docling_serve_api_key`                                   | string |       No | `null`                  | Optional API key for authentication                                                               |
| `docling_serve_timeout`                                   | int    |       No | `300`                   | Request timeout in seconds                                                                        |
| `docling_serve_do_ocr`                                    | bool   |       No | `true`                  | Enable OCR processing                                                                             |
| `docling_serve_ocr_engine`                                | string |       No | `easyocr`               | OCR engine: `easyocr` or `tesseract`                                                              |
| `docling_serve_pdf_backend`                               | string |       No | `dlparse_v2`            | PDF backend: `dlparse_v4`, `dlparse_v3`, `pypdfium2`                                              |
| **Ollama Entity Parameters (ollama mode)**                |
| `entity_model_name`                                       | string |    Yes\* | `llama3.2`              | Ollama model name (\*required for ollama mode)                                                    |
| `entity_temperature`                                      | float  |       No | `0.0`                   | Sampling temperature (0.0-1.0)                                                                    |
| `entity_max_tokens`                                       | int    |       No | `4096`                  | Maximum response tokens                                                                           |
| `entity_max_doc_chars`                                    | int    |       No | `8000`                  | Maximum document characters to send to LLM                                                        |
| **LiteLLM Entity Parameters (litellm mode)**              |
| `entity_model_name`                                       | string |    Yes\* | `gpt-3.5-turbo`         | LLM model identifier (\*required for litellm mode)                                                |
| `entity_temperature`                                      | float  |       No | `0.0`                   | Sampling temperature                                                                              |
| `entity_max_tokens`                                       | int    |       No | `2000`                  | Maximum response tokens                                                                           |
| `entity_provider_config`                                  | object |       No | `{}`                    | Provider config with `api_key`, `api_base`                                                        |

**Input Schema**

- `name` (`string`)
- binary payload column from an ingest operator
- optional existing content column

**Output Schema**

- `doc_content` (or configured `doc_column`) - Extracted markdown text
- `entities` (or configured `output_column`) - Extracted entities as JSON string (if entity extraction enabled)
- `doc_id_hash` - Document hash identifier
- `tables` - Extracted tables as JSON (if `extract_tables=true`)
- `images` - Extracted images metadata as JSON (if `extract_images=true`)
- `pages_processed` - Estimated number of pages for the extracted document text, calculated using 3000 characters = 1 page
- Individual entity columns (if `expand_extracted_data=true`)

**Execution Metadata**

The operator provides the following metadata after execution:

- `pages_by_format` (dict): Aggregate estimated pages grouped by source document format (e.g., `{"pdf": 120, "docx": 45}`)
- `total_pages_converted` (int): Total estimated pages across all successfully processed documents

**Exceptions**

- [`FlowExecutionFailedException`](src/datasift/common/exceptions/datasift_exceptions.py:79)
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

**Example: Text + Ollama Entity Extraction**

```json
{
  "id": "extract-node",
  "name": "extract",
  "operator": "extract_operator",
  "config": {
    "text_extraction_mode": "docling_library",
    "entity_extraction_mode": "ollama",
    "entity_model_name": "llama3.2",
    "entity_temperature": 0.0,
    "entity_max_tokens": 4096,
    "custom_schema": {
      "invoice_number": "string",
      "total_amount": "float"
    }
  }
}
```

**Example: Text + LiteLLM Entity Extraction**

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

**Architecture**

- Uses hexagonal architecture (ports and adapters pattern)
- Text extraction adapters: DoclingAdapter (docling_library), DoclingServeAdapter (docling_serve)
- Entity extraction adapters: OllamaEntityAdapter (ollama), DoclingEntityAdapter (docling), LiteLLMEntityAdapter (litellm)
- Supports independent text and entity extraction mode selection
- Parallel processing with auto-optimized worker counts

**Integration Requirements**

- **Ollama** (for ollama entity mode): Server at `http://localhost:11434`, model pulled (e.g., `ollama pull llama3.2`)
- **Docling Serve** (for docling_serve text mode): Service at configured URL (default `http://localhost:5001`)
- **LiteLLM** (for litellm entity mode): API keys for chosen provider (OpenAI, Anthropic, etc.)
- **ffmpeg** (for audio/video processing): Required for M4A, AAC, OGG, FLAC audio formats and all video formats (MP4, AVI, MOV). Not required for WAV/MP3. Install: `brew install ffmpeg` (macOS) or `sudo apt install ffmpeg` (Linux)

**Usage Notes**

- Dual-mode operation: text and entity extraction in single operator
- Text modes: `docling_library` (local, optional VLM) or `docling_serve` (remote API with OCR)
- Entity modes: `ollama` (local LLM), `litellm` (100+ providers), `docling` (template-based), `none` (default)
- VLM pipeline (docling_library mode) enhances extraction for complex documents
- Docling Serve mode supports OCR for scanned documents and multi-language processing
- **Text File Handling**: `.txt` files are automatically processed locally using UTF-8/latin-1 decoding, bypassing Docling Serve even when `docling_serve` mode is configured
- **Extension Detection**: Files without extensions are automatically detected using magic byte analysis (supports PDF, DOCX, XLSX, PPTX, images, HTML, and text formats)
- Audio/Video Support Processes audio (WAV, MP3, M4A, AAC, OGG, FLAC) and video (MP4, AVI, MOV) files using ASR (Automatic Speech Recognition) via Docling. Requires ffmpeg for M4A, AAC, OGG, FLAC, and all video formats
- See [ExtractOperator README](src/datasift/core/operators/extract/README.md) for complete documentation

---

### Functional Operators

#### ChunkerOperator

**Purpose:** Split extracted text into chunks using simple, semantic, or hybrid/docling strategies.

**Category:** Functional

**Class:** `core.operators.functional.chunker.ChunkerOperator`

| Parameter                     | Type   | Required | Default                                  | Description                                  |
| ----------------------------- | ------ | -------: | ---------------------------------------- | -------------------------------------------- |
| `doc_column`                  | string |      Yes | `content`                                | Input content column                         |
| `chunk_type`                  | string |      Yes | `simple`                                 | `simple`, `semantic`, or `hybrid`            |
| `chunk_size`                  | int    |       No | project default                          | Character or token size depending on chunker |
| `chunk_overlap`               | int    |       No | `200`                                    | Overlap between chunks                       |
| `semantic_embeddings_model`   | string |       No | `granite4`                               | Ollama model for semantic chunking           |
| `breakpoint_threshold_type`   | string |       No | `percentile`                             | Semantic split threshold method              |
| `breakpoint_threshold_amount` | float  |       No | `null`                                   | Threshold amount                             |
| `docling_tokenizer`           | string |       No | `sentence-transformers/all-MiniLM-L6-v2` | Hybrid chunking tokenizer                    |
| `retain_original_content`     | bool   |       No | `true`                                   | Keep original content                        |
| `enable_summarization`        | bool   |       No | `false`                                  | Create chunk summaries                       |

**Input Schema**

- configured `doc_column`, usually `content`

**Output Schema**

- `chunk_sequence_number`
- `start_index`
- `chunked_content`

**Exceptions**

- [`DatasiftException`](src/datasift/common/exceptions/datasift_exceptions.py:8)
- validation messages
- Ollama errors for semantic chunking

**Example**

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

Schemas are defined in `src/datasift/common/document_classes/*.json` with `target_tables` specifying field mappings and transformations. Supports 40+ document classes including invoice, purchase_order, receipt, insurance_claim, passport, and more.

**Exceptions**

- [`ValidationError`](src/datasift_opensource/backend/common/exceptions/datasift_exceptions.py) - Missing required columns
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

**Purpose:** Generate dense embeddings using pluggable providers such as Ollama, HuggingFace, and LiteLLM-backed vendors.

**Category:** Functional

**Class:** `core.operators.functional.embeddings.embeddings_operator.EmbeddingsOperator`

| Parameter             | Type   | Required | Default       | Description                           |
| --------------------- | ------ | -------: | ------------- | ------------------------------------- |
| `embeddings_type`     | string |      Yes | `ollama`      | Provider type                         |
| `embeddings_model_id` | string |      Yes | `granite4`    | Provider model                        |
| `embeddings_column`   | string |       No | `embeddings`  | Output vector column                  |
| `doc_column`          | string |       No | `content`     | Input content column                  |
| `doc_id_hash`         | string |       No | `doc_id_hash` | Hash column name                      |
| `overlap_ratio`       | float  |       No | `0.2`         | Long-text chunk overlap ratio         |
| `batch_size`          | int    |       No | `32`          | Embedding batch size                  |
| `provider_config`     | object |       No | `{}`          | Adapter-specific credentials/settings |

**Input Schema**

- `content` or `chunked_content`

**Output Schema**

- `embeddings`
- `doc_id_hash`

**Exceptions**

- [`DatasiftException`](src/datasift/common/exceptions/datasift_exceptions.py:8)
- provider authentication/network failures

**Example**

```json
{
  "id": "embedding-node",
  "name": "embeddings",
  "operator": "embeddings",
  "config": {
    "embeddings_type": "ollama",
    "embeddings_model_id": "nomic-embed-text",
    "embeddings_column": "embeddings",
    "doc_column": "content"
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

#### DocumentClassifierOperator

**Purpose:** Classify documents into a predefined set of document types using Ollama or watsonx-compatible model calls.

**Category:** Quality in intent; current source sets a functional category.

**Class:** `core.operators.quality.document_classifier.DocumentClassifierOperator`

| Parameter              | Type           |    Required | Default           | Description                                                      |
| ---------------------- | -------------- | ----------: | ----------------- | ---------------------------------------------------------------- |
| `provider`             | string         |          No | `ollama`          | `ollama` or `watsonx`                                            |
| `provider_config`      | object         |          No | `{}`              | Provider-specific configuration (see below)                      |
| `model_id`             | string         | Conditional | `granite4:latest` | Classification model (required for watsonx, optional for ollama) |
| `document_types`       | list or object |         Yes | catalog-derived   | Allowed target document types                                    |
| `confidence_threshold` | float          |          No | `7.0`             | Minimum accepted confidence                                      |
| `doc_column`           | string         |          No | `content`         | Input content column                                             |
| `output_column`        | string         |          No | `document_type`   | Classification result column                                     |
| `include_confidence`   | bool           |          No | `true`            | Emit confidence column                                           |
| `include_reasoning`    | bool           |          No | `false`           | Emit reasoning column                                            |

**Provider Configuration (`provider_config`)**

For **watsonx** provider:

- `api_base` (string, required): API endpoint URL
- `api_key` (string, required): API key for authentication
- `container_kind` (string, optional): Container type (`project` or `space`, default: `project`)
- `container_id` (string, required): Container ID
- `request_timeout` (integer, optional): Request timeout in seconds (default: `120`)

For **ollama** provider:

- Currently no provider-specific configuration required (uses defaults)

**Output Schema**

- `document_type`
- optional confidence and reasoning columns

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

| Parameter           | Type   | Required | Default       | Description                 |
| ------------------- | ------ | -------: | ------------- | --------------------------- |
| `provider`          | string |       No | `opensearch`  | VectorDB backend            |
| `index_name`        | string |      Yes | -             | Target index name           |
| `doc_id_column`     | string |       No | `doc_id_hash` | Primary document id column  |
| `embeddings_column` | string |       No | `embeddings`  | Vector column               |
| `create_index`      | bool   |       No | `true`        | Auto-create index           |
| `vector_dimension`  | int    |       No | `384`         | Configured vector dimension |
| `provider_config`   | object |      Yes | -             | Adapter-specific settings   |

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
  - `schemas/document_chunks_schema.v1.json`: Optimized for document chunking with custom analyzers

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

- [`DatasiftException`](src/datasift/common/exceptions/datasift_exceptions.py:8)

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
      "schema_template_path": "schemas/document_chunks_schema.v1.json",
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
    "disable_validation": "true",
    "force_ingest": true
  },
  "dag": [
    {
      "id": "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
      "name": "ingest_local_folder",
      "operator": "ingest_local",
      "config": {
        "input_folder": "tests/fixtures/invoices",
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

- `DatasiftFlowManager(flow_file=None, flow_def=None, log_level="info", job_id=None, job_run_id=None, flow_id=None)`

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
| `--log-level`      | `-l`  |          No | `debug`, `info`, `warning`, `error`, `critical` |
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

The sample flow structure in [`tests/sample_test_flows/invoice_processing/flow_invoice.json`](tests/sample_test_flows/invoice_processing/flow_invoice.json) shows the current schema style.

### Root structure

```json
{
  "flow": {
    "name": "invoice processing flow",
    "flow_id": "uuid",
    "description": "description",
    "storage": "in-memory",
    "execute_type": "local",
    "global_config": {},
    "dag": []
  }
}
```

[`DatasiftFlowManager`](src/datasift/lib/datasift_flow_manager.py:140) also accepts root-level flow definitions without a wrapping `flow` key.

### Flow fields

| Field           | Type   | Required | Description                       |
| --------------- | ------ | -------: | --------------------------------- |
| `name`          | string |      Yes | Human-readable flow name          |
| `flow_id`       | string |       No | Stable identifier                 |
| `description`   | string |       No | Flow description                  |
| `storage`       | string |       No | Storage mode                      |
| `execute_type`  | string |       No | Execution backend                 |
| `global_config` | object |       No | Shared runtime config             |
| `dag`           | array  |      Yes | Ordered operator node definitions |

### Node structure

```json
{
  "id": "uuid",
  "name": "operator name",
  "operator": "short_name",
  "config": {},
  "input_edges": [],
  "output_edges": []
}
```

### Node fields

| Field          | Type   | Required | Description                    |
| -------------- | ------ | -------: | ------------------------------ |
| `id`           | string |      Yes | Unique node ID                 |
| `name`         | string |      Yes | Display name                   |
| `operator`     | string |      Yes | Registered operator short name |
| `config`       | object |       No | Operator-specific config       |
| `input_edges`  | array  |       No | Upstream links                 |
| `output_edges` | array  |       No | Downstream links               |

### Edge structure

Observed forms in the sample flow:

```json
{ "node_id_ref": "target-node-id" }
```

and direct string references in some `output_edges` entries.

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

All custom exception types reviewed here come from [`datasift_exceptions.py`](src/datasift/common/exceptions/datasift_exceptions.py).

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

Defined in [`pyarrow_handler.py`](src/datasift/common/util/data/pyarrow_handler.py:1)

#### `BaseParquetTableHandler`

Abstract contract for parquet read/write/delete operations.

Key methods:

- [`read_table()`](src/datasift/common/util/data/pyarrow_handler.py:46)
- [`save_table()`](src/datasift/common/util/data/pyarrow_handler.py:63)
- [`delete_rows()`](src/datasift/common/util/data/pyarrow_handler.py:73)
- [`delete_file()`](src/datasift/common/util/data/pyarrow_handler.py:96)

#### `CpdParquetTableHandler`

Concrete local-file implementation.

#### `get_parquet_table_handler()`

Defined at [`get_parquet_table_handler()`](src/datasift/common/util/data/pyarrow_handler.py:151)

Returns the default parquet handler implementation.

### Schema utilities

Defined in [`schema_utils.py`](src/datasift/common/util/data/schema_utils.py:1)

#### `align_table_schema(table, all_cols)`

Defined at [`align_table_schema()`](src/datasift/common/util/data/schema_utils.py:10)

Adds missing columns with null values and aligns ordering.

#### `_combine_tables(tables, table_type)`

Defined at [`_combine_tables()`](src/datasift/common/util/data/schema_utils.py:34)

Safely concatenates tables and warns on duplicate IDs.

#### `_total_rows(tables)`

Defined at [`_total_rows()`](src/datasift/common/util/data/schema_utils.py:68)

Computes total row counts across a table, list, dict, or `None`.

### Document class utilities

Defined in [`document_class_utils.py`](src/datasift/common/util/document_class_utils.py:18)

#### `DocumentClassUtils.normalize_filename(name)`

Defined at [`normalize_filename()`](src/datasift/common/util/document_class_utils.py:36)

Normalizes human labels into stable filenames.

#### `DocumentClassUtils.load_document_class(doc_class_path)`

Defined at [`load_document_class()`](src/datasift/common/util/document_class_utils.py:46)

Loads a document class JSON definition.

#### `DocumentClassUtils.generate_docling_template(doc_class_path, include_nested=True, max_fields=None)`

Defined at [`generate_docling_template()`](src/datasift/common/util/document_class_utils.py:167)

Builds a Docling extraction template from a document class schema.

**Raises**

- `FileNotFoundError`
- `json.JSONDecodeError`

### Operator display utility

Defined in [`display.py`](src/datasift/common/util/operators/display.py:135)

#### `list_operators(verbose=False)`

Generates the same operator catalog used by the CLI and [`DatasiftFlowManager.list_operators()`](src/datasift/lib/datasift_flow_manager.py:308).

**Parameters:**
- `verbose` (bool): If True, shows detailed operator information with all parameters. If False (default), shows summary table with Owner, Attributes, Features columns.

**Output Format:**
- **Summary mode**: Table with columns: Owner (operator name), Attributes (parameter count), Features (capability count)
- **Verbose mode**: Detailed listing with full parameter descriptions, types, and default values
- **Category order**: Ingest, Extract, Quality, Functional, VectorDB, Storage
