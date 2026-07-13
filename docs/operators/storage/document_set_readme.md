# DocumentSetOperator

Persists a PyArrow table into a named DuckDB document set and passes the data through unchanged.

- **Short Name:** `document_set`
- **Category:** Storage

---

## Overview

`DocumentSetOperator` stores pipeline data at rest in DuckDB using the docpipe document set
infrastructure. It uses a get-or-create pattern so re-running the same pipeline is safe
(idempotent). The operator returns the original table untouched, so it can be inserted at any
point in a pipeline without disrupting downstream operators.

---

## Key Features

- Persistent columnar storage via DuckDB with automatic schema evolution
- Automatic metrics tracking (document count, size, page count)
- Upsert-based incremental updates keyed on `id`
- Optional soft-delete cleanup (`retain_deleted_docs`)
- Pass-through design — input table is returned unchanged
- Idempotent: safe to re-run (get-or-create on `document_set_name`)

---

## Operator Configuration

```json
{
  "type": "document_set",
  "name": "store_documents",
  "config": {
    "document_set_name": "research_papers",
    "description": "Processed research papers",
    "retain_deleted_docs": false
  },
  "depends_on": ["previous_operator"]
}
```

---

## Parameters

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `document_set_name` | string | **Yes** | — | Name of the document set to create or update |
| `description` | string | No | `""` | Human-readable description of the document set |
| `metadata` | object | No | `{}` | Arbitrary JSON object stored as document set metadata |
| `retain_deleted_docs` | boolean | No | `false` | When `true`, soft-deleted documents are kept; when `false` they are removed |
| `document_set_id` | string | No | — | UUID of an existing document set to update instead of creating a new one |
| `database_path` | string | No | default path | File path for the DuckDB database file |

---

## Output Columns

This operator does not add or remove columns. The original input table is returned unchanged.

**Required input column:**

| Column | Type | Description |
|---|---|---|
| `id` | string | Unique document identifier — used as the upsert key |

---

## Examples

### Example 1 — Basic storage

```json
{
  "type": "document_set",
  "name": "store_docs",
  "config": {
    "document_set_name": "research_papers"
  },
  "depends_on": ["extract_step"]
}
```

### Example 2 — With metadata and description

```json
{
  "type": "document_set",
  "name": "store_financial_reports",
  "config": {
    "document_set_name": "financial_reports_q1_2024",
    "description": "Quarterly financial reports for Q1 2024",
    "metadata": {
      "department": "finance",
      "year": 2024,
      "quarter": "Q1"
    }
  },
  "depends_on": ["quality_check"]
}
```

### Example 3 — Audit trail (retain soft-deleted docs)

```json
{
  "type": "document_set",
  "name": "store_compliance_docs",
  "config": {
    "document_set_name": "compliance_documents",
    "description": "Compliance documents — full audit trail retained",
    "retain_deleted_docs": true,
    "metadata": {
      "retention_policy": "7_years",
      "compliance_standard": "SOX"
    }
  },
  "depends_on": ["quality_check"]
}
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Error: Required column 'id' not found in table` | Input table is missing the `id` column | Ensure `DocIdHashOperator` runs before this operator |
| `Error: Document set with ID 'xxx' not found` | The UUID passed in `document_set_id` does not exist | Verify the UUID, or omit `document_set_id` to create a new set |
| `Error: Invalid database path: Path traversal detected` | `database_path` contains `..` segments | Use an absolute path or a path relative to the workspace root |
| `Error: Cannot evolve schema: incompatible types` | A column's type changed between runs | Ensure upstream operators produce stable schemas, or recreate the document set |
| Duplicate documents accumulate across runs | Upsert requires a stable `id` per document | Use `DocIdHashOperator` to generate deterministic IDs |

---

## Architecture

### Storage layers

```
DocumentSetOperator
    └── DocumentSetService          (application layer)
            ├── DataStoreFactory    → DuckDBTableStorage  (columnar storage)
            └── MetadataRepositoryFactory → metadata store (document set registry)
```

### Pipeline placement

The operator is intentionally pass-through so it can be placed at multiple checkpoints:

```
Ingest → Extract → [DocumentSetOperator] → Quality → [DocumentSetOperator] → Chunk → Embed → VectorDB
```

Common placements:
- After extraction — store full document content before chunking
- After quality checks — store validated documents only
- Before indexing — create a recoverable checkpoint

### Sample flow

See [`sample_flows/use_cases/document_set_management.json`](../../../sample_flows/use_cases/document_set_management.json).
