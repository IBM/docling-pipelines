# Document ID Hash Operator - Configuration Reference

## Overview

The Document ID Hash Operator generates unique hash identifiers for documents by hashing their content.

**⚠️ INTERNAL OPERATOR - NOT AVAILABLE FOR DIRECT USE**

This is an internal operator (`IS_OPERATOR_AVAILABLE = False`) that **cannot be used directly in flow configurations**. It is automatically invoked by other operators to generate document hash IDs:

- **ExtractOperator**: Generates hash IDs for extracted documents
- **ChunkerOperator**: Generates hash IDs for document chunks
- **EmbeddingsOperator**: Generates hash IDs for embedded content

The operator uses `dpk_doc_id.DocIDTransform` when available, otherwise falls back to `hashlib.sha256` for hash generation.

- **Operator Name:** `doc_id_hash`
- **Category**: Functional
- **Short Name**: `doc_id_hash`
- **Availability**: Internal operator only (not exposed in flow API)

## Configuration Parameters

### 1. `doc_column` (String)
**Type:** String
**Required:** No
**Default:** `"content"`
**Description:** Column containing document content for hashing.

**Examples:**
```json
"doc_column": "content"
```

### 2. `doc_id_hash_column` (String)
**Type:** String
**Required:** No
**Default:** `"doc_id_hash"`
**Description:** Name of the output column for the generated hash IDs. This parameter allows you to customize the name of the column where document hash IDs will be stored.

**Examples:**
```json
"doc_id_hash_column": "doc_id_hash"
```

```json
"doc_id_hash_column": "content_hash"
```

## Output Features

### `doc_id_hash` (String)
**Type:** String
**Description:** Generated hash ID for the document (output column).
**Available for Vector DB:** Yes
**Is Primary:** Yes
**Tags:** `mandatory`, `primary`

This is the actual output column that contains the generated hash values. The column name can be customized using the `doc_id_hash_column` configuration parameter.

## Hash Generation

The operator uses SHA-256 hashing algorithm:
1. Extracts content from specified `doc_column`
2. Encodes content as UTF-8
3. Generates SHA-256 hash
4. Returns 64-character hexadecimal string

**Hash Properties:**
- **Deterministic**: Same content always produces same hash
- **Unique**: Different content produces different hashes (collision-resistant)
- **Fixed Length**: Always 64 characters
- **One-Way**: Cannot reverse hash to get original content

## Implementation Details

The operator uses two approaches:
1. **Primary**: Uses `dpk_doc_id.DocIDTransform` when available
2. **Fallback**: Uses Python's `hashlib.sha256` directly

Both approaches produce identical SHA-256 hashes.

## Usage Context

This operator is **internal** and typically not used directly in flows. It's automatically invoked by:

1. **ExtractOperator**: Generates hashes for extracted documents
2. **EmbeddingsOperator**: Ensures documents have hashes before embedding
3. **VectorDBOperator**: Requires hashes as primary keys
4. **Deduplication**: Uses hashes to identify duplicate documents

## Configuration Examples

### Example 1: Default Configuration
```json
{
  "id": "30953cfb-a3a2-4688-9aea-ff9fff10f7bd",
  "operator": "doc_id_hash",
  "config": {
    "doc_column": "content",
    "doc_id_hash_column": "doc_id_hash"
  }
}
```

## Best Practices

1. **Automatic Usage**: Let other operators invoke this automatically
2. **Column Consistency**: Use default column names for compatibility
3. **Content Stability**: Hash after content is finalized (after extraction/cleaning)
4. **Deduplication**: Use hashes to identify and remove duplicates
5. **Primary Keys**: Use hashes as primary keys in vector databases

## Integration with Other Operators

### ExtractOperator
```json
{
  "id": "30953cfb-a3a2-4688-9aea-ff9fff10f7bd",
  "operator": "extract_operator",
  "config": {
    "text_extraction_mode": "docling_library"
  }
}
// Automatically generates doc_id_hash for extracted content
```

### EmbeddingsOperator
```json
{
  "id": "30953cfb-a3a2-4688-9aea-ff9fff10f7bd",
  "operator": "embeddings",
  "config": {
    "provider": "litellm",
    "model_id": "openai/nomic-embed-text"
  }
}
// Automatically generates doc_id_hash if not present
```

### VectorDBOperator
```json
{
  "id": "30953cfb-a3a2-4688-9aea-ff9fff10f7bd",
  "operator": "vectordb",
  "config": {
    "provider": "opensearch",
    "index_name": "documents",
    "doc_id_column": "doc_id_hash"
  }
}
// Uses doc_id_hash as primary key
```

## Validation Rules

- `doc_column` must exist in input data
- `doc_column` must contain non-empty content
- Output hash is always 64 characters (SHA-256)
- Hash column is added to output table

## Notes

- This is an **internal operator** (IS_OPERATOR_AVAILABLE = False)
- Not typically used directly in flow configurations
- Automatically invoked by other operators when needed
- Uses industry-standard SHA-256 hashing
- Hashes are deterministic and reproducible
- Cannot be reversed to get original content
