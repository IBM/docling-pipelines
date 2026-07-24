# IngestLocalOperator

Discovers files on the local filesystem and emits a PyArrow table of file metadata.

- **Short Name:** `ingest_local`
- **Category:** Ingest

---

## Overview

`IngestLocalOperator` is a metadata-only operator. It does **not** read or extract file content.
It walks a file path or directory, applies extension filters and size/count limits, and emits one
row per discovered file containing path, size, and timestamp information.

Text extraction is handled by a downstream [`ExtractOperator`](../extract/extract_operator_readme.md).

---

## Key Features

- Single file or recursive directory ingestion
- Extension-based include/exclude filtering
- Configurable file count and size limits
- Incremental updates — skips previously processed files unless `force_ingest: true`
- Optional soft-delete retention for removed files

---

## Operator Configuration

```json
{
  "type": "ingest_local",
  "name": "ingest_documents",
  "config": {
    "paths": "/data/documents",
    "include_filter": "pdf,docx,pptx",
    "max_files": 500,
    "max_file_size": 100
  }
}
```

---

## Parameters

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `paths` | string | **Yes** | — | Path to a single file or directory to ingest |
| `include_filter` | string | No | `"pdf,docx,pptx,txt,md"` | Comma-separated list of extensions to include (no leading dot) |
| `exclude_filter` | string | No | — | Comma-separated list of extensions to exclude |
| `max_files` | integer | No | `100` | Maximum number of files to ingest |
| `max_file_size` | integer | No | `100` | Maximum file size in MB; larger files are skipped |
| `force_ingest` | boolean | No | `false` | Re-ingest all files even if previously processed |
| `retain_deleted_docs` | boolean | No | `false` | Retain records for files deleted from the source |

---

## Output Columns

This operator produces a new table; it does not receive an input table.

| Column | PyArrow Type | Description |
|---|---|---|
| `id` | `string` | Document identifier (file inode) |
| `name` | `string` | File path |
| `path` | `string` | Absolute file path |
| `document_format` | `string` | File extension (e.g. `.pdf`, `.docx`) |
| `size` | `int64` | File size in bytes |
| `created_time` | `int64` | Creation timestamp (Unix epoch) |
| `modified_time` | `int64` | Modification timestamp (Unix epoch) |

---

## Examples

### Example 1 — Basic local ingestion

```json
{
  "type": "ingest_local",
  "name": "ingest_docs",
  "config": {
    "paths": "/data/documents",
    "include_filter": "pdf,docx",
    "max_files": 500
  }
}
```

### Example 2 — With size limit and exclude filter

```json
{
  "type": "ingest_local",
  "name": "ingest_docs",
  "config": {
    "paths": "./documents",
    "max_files": 1000,
    "max_file_size": 50,
    "include_filter": "pdf,txt,md",
    "exclude_filter": "tmp,bak"
  }
}
```

### Example 3 — Force re-ingestion

```json
{
  "type": "ingest_local",
  "name": "ingest_docs",
  "config": {
    "paths": "/data/updated_docs",
    "force_ingest": true,
    "retain_deleted_docs": true
  }
}
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Zero rows returned | `paths` does not exist or no files match the filter | Verify `paths` is accessible; check `include_filter` extensions match your files |
| Files skipped unexpectedly | `max_file_size` too small or `max_files` reached | Increase the limits or split directories into smaller batches |
| Previously ingested files are re-processed | `force_ingest: true` | Set `force_ingest: false` for incremental mode |
| File extension not matching | Extension listed with a leading dot (`.pdf`) | Remove the dot — use `pdf`, not `.pdf` |

---

## Architecture

### Typical pipeline position

```
IngestLocalOperator → ExtractOperator → [Chunker → Embeddings → VectorDB]
```

`IngestLocalOperator` never passes `None` downstream; it always produces a table (possibly with
zero rows if no files match). `ExtractOperator` reads the `path` column to load binary content
from disk.

### Sample flow

See [`sample_flows/quickstart/complete_pipeline_ollama.json`](../../../sample_flows/quickstart/complete_pipeline_ollama.json).
