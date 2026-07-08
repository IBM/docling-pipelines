# Ededup (Exact Deduplication) Operator Configuration Reference

## Overview
The Ededup (Exact Deduplication) operator removes duplicate documents from a dataset by comparing document hashes. It identifies and eliminates identical documents to reduce processing overhead and improve data quality.

- **Short Name**: `ededup`
- **Category**: Quality
- **Operator Name:** `ededup`

## How It Works

### Deduplication Process
1. **Hash Comparison**: Compares document hashes in the `doc_id_column`
2. **Duplicate Detection**: Identifies documents with identical hash values
3. **Removal**: Removes duplicate documents, keeping only the first occurrence
4. **Statistics**: Tracks number of duplicates removed

### Cross-Batch Deduplication
The operator maintains its hash state across all `transform()` calls for the lifetime of the operator instance. This means duplicates are detected globally across all batches processed by the same operator — not just within a single batch. A document seen in batch 1 will be correctly identified as a duplicate if it appears again in batch 2, 3, or any subsequent batch.

## Complete Flow Example

```json
{
  "flow_name": "Deduplication Pipeline",
  "description": "Ingest, extract, hash, deduplicate, and chunk documents",
  "flow": [
    {
      "name": "ingest_documents",
      "type": "ingest_local_folder",
      "config": {
        "paths": "./sample_documents"
      }
    },
    {
      "name": "extract_documents",
      "type": "extract_operator",
      "depends_on": ["ingest_documents"],
      "config": {
        "text_extraction": {
          "provider": "docling_library"
        },
        "entity_extraction": {
          "provider": "none"
        }
      }
    },
    {
      "name": "generate_doc_hash",
      "type": "doc_id_hash",
      "depends_on": ["extract_documents"],
      "config": {
        "hash_column": "doc_id_hash"
      }
    },
    {
      "name": "deduplicate_documents",
      "type": "ededup",
      "depends_on": ["generate_doc_hash"]
    },
    {
      "name": "chunk_documents",
      "type": "chunker",
      "depends_on": ["deduplicate_documents"],
      "config": {
        "chunking_type": "simple",
        "chunk_size": 512
      }
    }
  ]
}
```
