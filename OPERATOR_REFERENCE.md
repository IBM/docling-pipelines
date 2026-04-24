# Operator Reference

## Table of Contents

- [Operator Reference](#operator-reference)
  - [Table of Contents](#table-of-contents)
  - [Overview](#overview)
    - [How to use this reference](#how-to-use-this-reference)
  - [Operator API Reference](#operator-api-reference)
    - [Common Operator Contract](#common-operator-contract)
    - [Extract Operators](#extract-operators)
      - [ExtractDoclingOperator](#extractdoclingoperator)
      - [ExtractEntitiesOllamaOperator](#extractentitiesollamaoperator)
    - [Ingest Operators](#ingest-operators)
      - [IngestLocalOperator](#ingestlocaloperator)
      - [IngestSourceOperator](#ingestsourceoperator)
    - [Functional Operators](#functional-operators)
      - [ChunkerOperator](#chunkeroperator)
      - [EmbeddingsOperator](#embeddingsoperator)
      - [BranchingOperator](#branchingoperator)
      - [NOOPOperator](#noopoperator)
      - [DocIdHashOperator](#docidhashoperator)
    - [Quality Operators](#quality-operators)
      - [LanguageDetect](#languagedetect)
      - [ReadabilityOperator](#readabilityoperator)
      - [RedactionOperator](#redactionoperator)
      - [DocumentClassifierOperator](#documentclassifieroperator)
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

[`OPERATOR_REFERENCE.md`](OPERATOR_REFERENCE.md) centralizes the public APIs that are visible to pipeline authors, application integrators, and operators users.

This reference is organized around four entry points:

- **Operators**: flow node implementations under [`src/datasift_opensource/backend/core/operators`](src/datasift_opensource/backend/core/operators)
- **Programmatic execution**: [`DatasiftFlowManager`](src/datasift_opensource/backend/lib/datasift_flow_manager.py:24)
- **CLI execution**: [`datasift-orchestrator`](src/datasift_opensource/backend/cli/datasift_cli.py:147)
- **Flow JSON definitions**: DAG configuration consumed by the orchestrator

### How to use this reference

- Use the operator sections when authoring flow JSON.
- Use the flow manager section when embedding datasift in Python code.
- Use the CLI section when running or validating flows from the shell.

---

## Operator API Reference

### Common Operator Contract

All operators ultimately inherit from [`AbstractOperator`](src/datasift_opensource/backend/core/operators/abstract_operator.py:28).

**Shared behavior**

- Operators receive a `config` dictionary during initialization.
- Operators expose metadata through [`get_metadata()`](src/datasift_opensource/backend/core/operators/abstract_operator.py:59).
- Input column requirements are expressed with [`get_required_features()`](src/datasift_opensource/backend/core/operators/abstract_operator.py:55).
- Validation hooks are implemented via [`validate()`](src/datasift_opensource/backend/core/operators/abstract_operator.py:51).
- Runtime work is usually performed by `transform()` or `runner()` methods depending on the operator.

**Common input shape**

Most operators consume a `pyarrow.Table` with some subset of these columns:

| Column            | Type                                    | Meaning                                       |
| ----------------- | --------------------------------------- | --------------------------------------------- |
| `id`              | string                                  | Document identifier                           |
| `name`            | string                                  | Source path or display name                   |
| `content`         | string                                  | Extracted text or serialized document content |
| `binary_content`  | binary                                  | Raw file bytes for extractors                 |
| `doc_id_hash`     | string                                  | Stable hashed identifier                      |
| `chunked_content` | list or JSON string                     | Chunk payloads generated by chunking          |
| `embeddings`      | vector/list[float] or list[list[float]] | Dense vector output                           |

### Extract Operators

#### ExtractDoclingOperator

**Purpose:** Extract structured or markdown content from PDFs/images using Docling, optional VLM pipelines, and optional document templates.

**Category:** Extract

**Class:** `core.operators.extract.extract_docling.ExtractDoclingOperator`

| Parameter               | Type   | Required | Default                  | Description                                                     |
| ----------------------- | ------ | -------: | ------------------------ | --------------------------------------------------------------- |
| `doc_column`            | string |       No | `content`                | Target content column                                           |
| `use_template`          | bool   |       No | `false`                  | Enables template-based structured extraction                    |
| `template`              | object |       No | -                        | Inline Docling extraction template                              |
| `doc_class_path`        | string |       No | -                        | Path to a document class JSON used to build a template          |
| `expand_extracted_data` | bool   |       No | `false`                  | Expands structured output into prefixed columns                 |
| `extract_tables`        | bool   |       No | implementation-dependent | Include table extraction                                        |
| `extract_images`        | bool   |       No | implementation-dependent | Include image extraction metadata                               |
| `use_vlm_pipeline`      | bool   |       No | `false`                  | Use Docling VLM pipeline                                        |
| `vlm_preset`            | string |       No | provider default         | VLM preset name                                                 |
| `vlm_engine_type`       | string |       No | Docling default          | Engine family such as transformers, mlx, or API-backed variants |
| `vlm_provider_config`   | object |       No | `{}`                     | Provider-specific VLM settings                                  |
| `max_workers`           | int    |       No | implementation-dependent | Parallel extraction worker count                                |

**Input Schema**

- `name` (`string`)
- binary payload column from an ingest operator
- optional existing `content`

**Output Schema**

- `content` (`string`)
- `structured_data` (`list[object]`)
- expanded extracted columns when configured
- `doc_id_hash` (`string`) via internal hashing support

**Exceptions**

- [`FlowExecutionFailedException`](src/datasift_opensource/backend/common/exceptions/datasift_exceptions.py:79)
- `ImportError`
- `ValueError`
- Docling runtime exceptions

**Example**

```json
{
  "id": "extract-node",
  "name": "extract",
  "operator": "extract_docling",
  "config": {
    "doc_column": "content",
    "use_template": true,
    "expand_extracted_data": true,
    "template": {
      "invoice_number": "string",
      "invoice_date": "string",
      "total": "float"
    }
  }
}
```

**Usage Notes**

- Usually follows ingest operators in the pipeline
- VLM support requires Docling VLM dependencies
- API-backed VLM engines automatically normalize output to markdown format

---

#### ExtractEntitiesOllamaOperator

**Purpose:** Extract structured entities from text using a locally running Ollama model and either a schema template or schema-free mode.

**Category:** Extract

**Class:** `core.operators.extract.extract_entities_ollama.ExtractEntitiesOllamaOperator`

| Parameter              | Type   | Required | Default                  | Description                                        |
| ---------------------- | ------ | -------: | ------------------------ | -------------------------------------------------- |
| `doc_column`           | string |       No | `content`                | Input content column                               |
| `model_name`           | string |      Yes | -                        | Ollama model used for extraction                   |
| `schema`               | object |       No | -                        | Explicit extraction schema                         |
| `doc_class_path`       | string |       No | -                        | Document class JSON used to derive schema/template |
| `output_column`        | string |       No | implementation default   | Target column for extracted entity JSON            |
| `max_workers`          | int    |       No | implementation-dependent | Parallel worker count                              |
| `include_raw_response` | bool   |       No | `false`                  | Preserve raw LLM payload if supported              |
| `schema_free`          | bool   |       No | `false`                  | Extract broad entities without fixed schema        |

**Input Schema**

- `content` (`string`) or configured `doc_column`

**Output Schema**

- structured entity JSON
- optional expanded entity fields

**Exceptions**

- [`DatasiftException`](src/datasift_opensource/backend/common/exceptions/datasift_exceptions.py:8)
- JSON parsing failures
- Ollama connectivity failures

**Example**

```json
{
  "id": "entity-node",
  "name": "extract_entities",
  "operator": "extract_entities_ollama",
  "config": {
    "doc_column": "content",
    "model_name": "llama3.2",
    "schema": {
      "fields": [
        { "name": "invoice_number", "type": "string" },
        { "name": "invoice_date", "type": "string" },
        { "name": "total", "type": "float" }
      ]
    }
  }
}
```

### Ingest Operators

#### IngestLocalOperator

**Purpose:** Discover files in a local directory, collect metadata, and optionally load binary content for downstream extraction.

**Category:** Ingest

**Class:** `core.operators.ingest.ingest_local_folder.IngestLocalOperator`

| Parameter              | Type   | Required | Default              | Description                                         |
| ---------------------- | ------ | -------: | -------------------- | --------------------------------------------------- |
| `input_folder`         | string |      Yes | `../test-data/input` | Root folder to crawl                                |
| `include_filter`       | string |       No | -                    | Comma-separated extensions to include               |
| `exclude_filter`       | string |       No | -                    | Comma-separated extensions to exclude               |
| `max_files`            | int    |       No | `100`                | Maximum number of files to ingest                   |
| `max_file_size`        | int    |       No | `100`                | Maximum file size in MB                             |
| `store_binary_content` | bool   |       No | `true`               | Preserve raw file bytes for extractors              |
| `force_ingest`         | bool   |       No | `false`              | Reprocess already-seen documents                    |
| `retain_deleted_docs`  | bool   |       No | project constant     | Retain source-deleted docs in incremental scenarios |

**Input Schema**

- No input table required

**Output Schema**

- `id`
- `name`
- `size`
- `created_time`
- `modified_time`
- binary content column when enabled

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
    "include_filter": ".pdf",
    "store_binary_content": true
  }
}
```

---

#### IngestSourceOperator

**Purpose:** Multi-provider ingest abstraction for sources such as object storage, SharePoint, OneDrive, Google Drive, and filesystem adapters.

**Category:** Ingest

**Class:** `core.operators.ingest.ingest_source.IngestSourceOperator`

| Parameter              | Type   | Required | Default            | Description                     |
| ---------------------- | ------ | -------: | ------------------ | ------------------------------- |
| `source_type`          | string |      Yes | -                  | Adapter type                    |
| `include_filter`       | string |       No | -                  | Extension include list          |
| `exclude_filter`       | string |       No | -                  | Extension exclude list          |
| `force_ingest`         | bool   |       No | `false`            | Reprocess prior docs            |
| `store_binary_content` | bool   |       No | provider-dependent | Preserve binary content         |
| `provider_config`      | object |      Yes | -                  | Provider-specific configuration |

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

- [`DatasiftException`](src/datasift_opensource/backend/common/exceptions/datasift_exceptions.py:8)
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

- [`DatasiftException`](src/datasift_opensource/backend/common/exceptions/datasift_exceptions.py:8)
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

| Parameter              | Type           |    Required | Default           | Description                   |
| ---------------------- | -------------- | ----------: | ----------------- | ----------------------------- |
| `provider`             | string         |          No | `ollama`          | `ollama` or `watsonx`         |
| `api_base`             | string         | Conditional | -                 | Required for watsonx          |
| `api_key`              | string         | Conditional | `not-needed`      | Required for watsonx          |
| `model_id`             | string         |          No | provider-specific | Classification model          |
| `project_id`           | string         | Conditional | -                 | Required for watsonx          |
| `document_types`       | list or object |         Yes | catalog-derived   | Allowed target document types |
| `confidence_threshold` | float          |          No | `7.0`             | Minimum accepted confidence   |
| `doc_column`           | string         |          No | `content`         | Input content column          |
| `output_column`        | string         |          No | `document_type`   | Classification result column  |
| `include_confidence`   | bool           |          No | `true`            | Emit confidence column        |
| `include_reasoning`    | bool           |          No | `false`           | Emit reasoning column         |

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

| Parameter             | Type   | Required | Default       | Description                 |
| --------------------- | ------ | -------: | ------------- | --------------------------- |
| `vector_db_type`      | string |       No | `opensearch`  | Vector backend              |
| `index_name`          | string |      Yes | -             | Target index name           |
| `doc_id_column`       | string |       No | `doc_id_hash` | Primary document id column  |
| `embeddings_column`   | string |       No | `embeddings`  | Vector column               |
| `create_index`        | bool   |       No | `true`        | Auto-create index           |
| `vector_dimension`    | int    |       No | `384`         | Configured vector dimension |
| `vectordb_parameters` | object |      Yes | -             | Adapter-specific settings   |

**Input Schema**

- `doc_id_column`
- `embeddings_column`

**Output Schema**

- input table unchanged
- side effect: indexed vector records

**Exceptions**

- [`DatasiftException`](src/datasift_opensource/backend/common/exceptions/datasift_exceptions.py:8)

---

### Storage Operators

#### DocumentSetOperator

**Purpose:** Store PyArrow table data in persistent document sets with DuckDB backend, enabling reusable document collections across workflows.

**Category:** Storage

**Class:** `core.operators.storage.document_set_operator.DocumentSetOperator`

| Parameter             | Type   | Required | Default                            | Description                              |
| --------------------- | ------ | -------: | ---------------------------------- | ---------------------------------------- |
| `document_set_name`   | string |      Yes | -                                  | Name of the document set                 |
| `description`         | string |       No | `null`                             | Description of the document set          |
| `metadata`            | object |       No | `null`                             | Additional metadata as JSON              |
| `retain_deleted_docs` | bool   |       No | `false`                            | Whether to retain soft-deleted documents |
| `document_set_id`     | string |       No | `null`                             | Existing document set ID for updates     |
| `database_path`       | string |       No | `data/duckdb/document_sets.duckdb` | Path to DuckDB database file             |

**Input Schema**

- `id` (required): Document identifier

**Output Schema**

- Input table unchanged (pass-through design)
- Side effect: data persisted to DuckDB

**Metadata Output**

- `document_set_id`: UUID of the document set
- `document_set_name`: Name of the document set
- `table_name`: DuckDB table name
- `stored_documents`: Total document count
- `total_size_bytes`: Total size in bytes
- `total_pages`: Total pages processed
- `deleted_documents`: Count of soft-deleted documents cleaned up
- `database_path`: Path to DuckDB database

**Features**

- Persistent storage of document collections in DuckDB
- Automatic handling of schema changes when new fields are added
- Automatic calculation of document metrics (count, size, pages)
- Optional cleanup of soft-deleted documents
- Pass-through design allows chaining with downstream operators
- Data integrity verification during storage operations

**Exceptions**

- [`FlowValidationException`](src/datasift_opensource/backend/common/exceptions/datasift_exceptions.py): Invalid configuration
- [`FlowExecutionFailedException`](src/datasift_opensource/backend/common/exceptions/datasift_exceptions.py): Storage operation failed
- [`DatasiftException`](src/datasift_opensource/backend/common/exceptions/datasift_exceptions.py): General errors

**Example Configuration**

```json
{
  "operator": "document_set",
  "config": {
    "document_set_name": "processed_invoices",
    "description": "Invoices processed through extraction pipeline",
    "metadata": {
      "source": "invoice_pipeline_v2",
      "created_by": "data_team"
    },
    "retain_deleted_docs": false
  }
}
```

**Usage Pattern**

```
Ingest → Extract → [Processing] → DocumentSetOperator → [Downstream Operators]
                                         │
                                         └─> DuckDB Storage (side effect)
```

---

## DatasiftFlowManager API

**Class:** [`DatasiftFlowManager`](src/datasift_opensource/backend/lib/datasift_flow_manager.py:24)

### Constructor

- `DatasiftFlowManager(flow_file=None, flow_def=None, log_level="info", job_id=None, job_run_id=None, flow_id=None)`

Exactly one of `flow_file` or `flow_def` must be provided.

### `validate()`

Defined at [`validate()`](src/datasift_opensource/backend/lib/datasift_flow_manager.py:165).

Returns:

```python
{
  "valid": bool,
  "errors": list,
  "warnings": list
}
```

### `execute()`

Defined at [`execute()`](src/datasift_opensource/backend/lib/datasift_flow_manager.py:213).

Returns the result of flow execution from the executor.

### `get_execution_metadata()`

Defined at [`get_execution_metadata()`](src/datasift_opensource/backend/lib/datasift_flow_manager.py:245).

Returns job and flow metadata.

### `get_execution_logs()`

Defined at [`get_execution_logs()`](src/datasift_opensource/backend/lib/datasift_flow_manager.py:272).

Returns `list[str]`.

### `list_operators(verbose=False)`

Defined at [`list_operators()`](src/datasift_opensource/backend/lib/datasift_flow_manager.py:308).

Returns a formatted operator listing via [`common.util.operators.display.list_operators()`](src/datasift_opensource/backend/common/util/operators/display.py:135).

### Method name note

The current class does **not** expose `execute_flow()` or `validate_flow()` methods. Use:

- [`execute()`](src/datasift_opensource/backend/lib/datasift_flow_manager.py:213)
- [`validate()`](src/datasift_opensource/backend/lib/datasift_flow_manager.py:165)

---

## CLI API Reference

**Entry point:** [`main()`](src/datasift_opensource/backend/cli/datasift_cli.py:147)

### Command forms

```bash
datasift-orchestrator --flow-file ./path/to/flow.json
datasift-orchestrator --flow-file ./path/to/flow.json --validate
datasift-orchestrator validate-flow ./path/to/flow.json
datasift-orchestrator --list-operators
datasift-orchestrator --list-operators --verbose
```

### Global arguments

| Argument           | Short |    Required | Description                                     |
| ------------------ | ----- | ----------: | ----------------------------------------------- |
| `--flow-file`      | `-f`  | Conditional | Flow JSON path                                  |
| `--log-level`      | `-l`  |          No | `debug`, `info`, `warning`, `error`, `critical` |
| `--list-operators` | `-lo` |          No | List operators and exit                         |
| `--verbose`        | `-v`  |          No | Verbose operator listing                        |
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

[`DatasiftFlowManager`](src/datasift_opensource/backend/lib/datasift_flow_manager.py:140) also accepts root-level flow definitions without a wrapping `flow` key.

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

Validation is performed by [`FlowValidator`](src/datasift_opensource/backend/lib/datasift_flow_manager.py:20) and CLI validation helpers.

Practical rules from the reviewed code:

- operator short names must resolve to registered operators
- required operator config must validate
- required input features must be present
- branch and filter references must use valid columns
- flow file must be valid JSON

---

## Exception Reference

All custom exception types reviewed here come from [`datasift_exceptions.py`](src/datasift_opensource/backend/common/exceptions/datasift_exceptions.py).

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

Defined in [`pyarrow_handler.py`](src/datasift_opensource/backend/common/util/data/pyarrow_handler.py:1)

#### `BaseParquetTableHandler`

Abstract contract for parquet read/write/delete operations.

Key methods:

- [`read_table()`](src/datasift_opensource/backend/common/util/data/pyarrow_handler.py:46)
- [`save_table()`](src/datasift_opensource/backend/common/util/data/pyarrow_handler.py:63)
- [`delete_rows()`](src/datasift_opensource/backend/common/util/data/pyarrow_handler.py:73)
- [`delete_file()`](src/datasift_opensource/backend/common/util/data/pyarrow_handler.py:96)

#### `CpdParquetTableHandler`

Concrete local-file implementation.

#### `get_parquet_table_handler()`

Defined at [`get_parquet_table_handler()`](src/datasift_opensource/backend/common/util/data/pyarrow_handler.py:151)

Returns the default parquet handler implementation.

### Schema utilities

Defined in [`schema_utils.py`](src/datasift_opensource/backend/common/util/data/schema_utils.py:1)

#### `align_table_schema(table, all_cols)`

Defined at [`align_table_schema()`](src/datasift_opensource/backend/common/util/data/schema_utils.py:10)

Adds missing columns with null values and aligns ordering.

#### `_combine_tables(tables, table_type)`

Defined at [`_combine_tables()`](src/datasift_opensource/backend/common/util/data/schema_utils.py:34)

Safely concatenates tables and warns on duplicate IDs.

#### `_total_rows(tables)`

Defined at [`_total_rows()`](src/datasift_opensource/backend/common/util/data/schema_utils.py:68)

Computes total row counts across a table, list, dict, or `None`.

### Document class utilities

Defined in [`document_class_utils.py`](src/datasift_opensource/backend/common/util/document_class_utils.py:18)

#### `DocumentClassUtils.normalize_filename(name)`

Defined at [`normalize_filename()`](src/datasift_opensource/backend/common/util/document_class_utils.py:36)

Normalizes human labels into stable filenames.

#### `DocumentClassUtils.load_document_class(doc_class_path)`

Defined at [`load_document_class()`](src/datasift_opensource/backend/common/util/document_class_utils.py:46)

Loads a document class JSON definition.

#### `DocumentClassUtils.generate_docling_template(doc_class_path, include_nested=True, max_fields=None)`

Defined at [`generate_docling_template()`](src/datasift_opensource/backend/common/util/document_class_utils.py:167)

Builds a Docling extraction template from a document class schema.

**Raises**

- `FileNotFoundError`
- `json.JSONDecodeError`

### Operator display utility

Defined in [`display.py`](src/datasift_opensource/backend/common/util/operators/display.py:135)

#### `list_operators(verbose=False, summary_only=False)`

Generates the same operator catalog used by the CLI and [`DatasiftFlowManager.list_operators()`](src/datasift_opensource/backend/lib/datasift_flow_manager.py:308).
