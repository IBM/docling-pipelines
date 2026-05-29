# DocumentSetOperator Configuration Guide

## Overview

The DocumentSetOperator provides persistent storage for pipeline data using the document set infrastructure. It stores PyArrow table data in DuckDB with automatic metrics computation, schema evolution support, and incremental update handling with soft-delete cleanup.

- **Operator Name:** `document_set`
- **Category**: Storage
- **Short Name**: `document_set`

## Key Features

- **Persistent Storage**: Stores PyArrow tables in DuckDB with automatic schema evolution
- **Metrics Tracking**: Automatically computes and tracks document count, size, and page metrics
- **Incremental Updates**: Supports upsert operations and soft-delete cleanup
- **Pass-Through Design**: Returns original data unchanged for downstream operators
- **Enterprise Architecture**: Uses dependency injection with proper separation of concerns
- **Idempotent Operations**: Get-or-create pattern ensures safe re-execution

## Configuration Parameters

#### 1. document_set_name
- **Type:** `string`
- **Required:** Yes
- **Description:** Name of the document set to create or update

#### 2. description
- **Type:** `string`
- **Required:** No
- **Description:** Human-readable description of the document set

#### 3. metadata
- **Type:** `object` (JSON)
- **Required:** No
- **Description:** Additional metadata as JSON object for custom tracking

- **Example:** 
  ```json
  {
    "source": "financial_reports",
    "year": 2024,
    "quarter": "Q1"
  }
  ```

#### 4. retain_deleted_docs
- **Type:** `boolean`
- **Required:** No
- **Default:** `false`
- **Description:** Whether to retain soft-deleted documents in storage
- **Valid Values:**
  - `false`: Soft-deleted documents are removed from storage
  - `true`: Soft-deleted documents are kept (useful for audit trails)

#### 5. document_set_id
- **Type:** `string`
- **Required:** No
- **Description:** Existing document set ID for updating an existing set
- **Usage:** Provide this when updating metadata/description of an existing document set

### Required Input Columns

The operator requires the following column in the input PyArrow table:

- **`id`**: Unique document identifier (used for upsert operations)

### Output

### Pass-Through Behavior
The operator returns the original input table unchanged, allowing it to be used in the middle of a pipeline without disrupting data flow.

## Configuration Examples

### Example 1: Basic Document Storage

Store documents in a new document set with minimal configuration:

```json
{
  "operator": "document_set",
  "config": {
    "document_set_name": "research_papers"
  }
}
```

### Example 2: Document Set with Metadata

Create a document set with description and custom metadata:

```json
{
  "operator": "document_set",
  "config": {
    "document_set_name": "financial_reports_q1_2024",
    "description": "Quarterly financial reports for Q1 2024",
    "metadata": {
      "department": "finance",
      "year": 2024,
      "quarter": "Q1",
      "classification": "internal"
    }
  }
}
```

### Example 3: Incremental Updates with Soft-Delete Cleanup

Store documents with automatic cleanup of deleted items:

```json
{
  "operator": "document_set",
  "config": {
    "document_set_name": "live_document_collection",
    "description": "Continuously updated document collection",
    "retain_deleted_docs": false
  }
}
```

### Example 4: Audit Trail with Retained Deletes

Keep soft-deleted documents for audit purposes:

```json
{
  "operator": "document_set",
  "config": {
    "document_set_name": "compliance_documents",
    "description": "Compliance documents with full audit trail",
    "retain_deleted_docs": true,
    "metadata": {
      "retention_policy": "7_years",
      "compliance_standard": "SOX"
    }
  }
}
```

### Example 5: Update Existing Document Set

Update metadata of an existing document set:

```json
{
  "operator": "document_set",
  "config": {
    "document_set_id": "550e8400-e29b-41d4-a716-446655440000",
    "document_set_name": "research_papers",
    "description": "Updated description for research papers",
    "metadata": {
      "last_updated": "2024-05-06",
      "status": "active"
    }
  }
}
```

### Example 6: Custom Database Path

Specify a custom database path for document storage:

```json
{
  "type": "document_set",
  "name": "store_in_document_set",
  "config": {
    "document_set_name": "embeddings_dataset",
    "description": "Document set with embeddings",
    "data_backend": "duckdb",
    "database_path": "./data/document_sets/embeddings_dataset.duckdb"
  },
  "depends_on": [
    "generate_embeddings"
  ]
}
```

## Pipeline Placement

Place DocumentSetOperator strategically:

- **After Extraction**: Store raw extracted content
- **After Quality Checks**: Store validated documents
- **Before Chunking**: Store full documents before splitting
- **Multiple Points**: Store at different pipeline stages for checkpointing

## Performance Considerations

### Storage Efficiency

- **Batch Size**: Larger batches are more efficient for storage operations
- **Schema Stability**: Frequent schema changes can impact performance
- **Index Usage**: DuckDB automatically optimizes queries on ID column

### Memory Usage

- **Pass-Through Design**: Minimal memory overhead (original table returned)
- **Metrics Computation**: Computed incrementally, not stored in memory
- **DuckDB Efficiency**: Columnar storage reduces memory footprint

### Concurrent Access

- **File Locking**: DuckDB handles concurrent reads efficiently
- **Write Serialization**: Multiple writers are serialized by DuckDB
- **Distributed Execution**: Consider separate database files for parallel pipelines

## Validation Rules

### Input Validation

1. **Required Column**: Input table must contain `id` column
2. **Non-Empty Name**: `document_set_name` must be non-empty string
3. **Valid Path**: `database_path` must be valid and accessible
4. **Metadata Format**: `metadata` must be valid JSON object if provided

### Runtime Validation

1. **Schema Compatibility**: New data schema must be compatible with existing
2. **ID Uniqueness**: Document IDs should be unique within a batch
3. **Storage Availability**: Database path must be writable

## Error Handling

### Common Errors

#### Missing Required Column

```
Error: Required column 'id' not found in table
```

**Solution:** Ensure upstream operators add the `id` column (e.g., DocIdHashOperator)

#### Invalid Database Path

```
Error: Invalid database path: Path traversal detected
```

**Solution:** Use absolute paths or paths relative to workspace root

#### Document Set Not Found

```
Error: Document set with ID 'xxx' not found
```

**Solution:** Verify `document_set_id` exists or omit to create new set

#### Schema Evolution Failure

```
Error: Cannot evolve schema: incompatible types
```

**Solution:** Ensure new data types are compatible with existing schema


## Complete Flow Example

See [`tests/sample_test_flows/document_set/document_set_flow.json`](tests/sample_test_flows/document_set/document_set_flow.json) for a complete pipeline example.
