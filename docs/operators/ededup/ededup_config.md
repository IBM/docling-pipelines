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

## Complete Flow Example

```json
{
    "dag": [
      {
        "id": "a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d",
        "name": "ingest_documents",
        "operator": "ingest_local_folder",
        "config": {
          "input_folder": "sample_documents"
        },
        "input_edges": [],
        "output_edges": [
          {
            "node_id_ref": "b2c3d4e5-f6a7-4b5c-9d0e-1f2a3b4c5d6e"
          }
        ]
      },
      {
        "id": "b2c3d4e5-f6a7-4b5c-9d0e-1f2a3b4c5d6e",
        "name": "extract_documents",
        "operator": "extract",
        "config": {
          "text_extraction_mode": "basic"
        },
        "input_edges": [
          {
            "node_id_ref": "a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d"
          }
        ],
        "output_edges": [
          {
            "node_id_ref": "c3d4e5f6-a7b8-4c5d-0e1f-2a3b4c5d6e7f"
          }
        ]
      },
      {
        "id": "c3d4e5f6-a7b8-4c5d-0e1f-2a3b4c5d6e7f",
        "name": "generate_doc_hash",
        "operator": "doc_id_hash",
        "config": {
          "hash_column": "doc_id_hash"
        },
        "input_edges": [
          {
            "node_id_ref": "b2c3d4e5-f6a7-4b5c-9d0e-1f2a3b4c5d6e"
          }
        ],
        "output_edges": [
          {
            "node_id_ref": "d4e5f6a7-b8c9-4d5e-1f2a-3b4c5d6e7f8a"
          }
        ]
      },
      {
        "id": "d4e5f6a7-b8c9-4d5e-1f2a-3b4c5d6e7f8a",
        "name": "deduplicate_documents",
        "operator": "ededup",
        "input_edges": [
          {
            "node_id_ref": "c3d4e5f6-a7b8-4c5d-0e1f-2a3b4c5d6e7f"
          }
        ],
        "output_edges": [
          {
            "node_id_ref": "e5f6a7b8-c9d0-4e5f-2a3b-4c5d6e7f8a9b"
          }
        ]
      },
      {
        "id": "e5f6a7b8-c9d0-4e5f-2a3b-4c5d6e7f8a9b",
        "name": "chunk_documents",
        "operator": "chunker",
        "config": {
          "chunking_type": "simple",
          "chunk_size": 512
        },
        "input_edges": [
          {
            "node_id_ref": "d4e5f6a7-b8c9-4d5e-1f2a-3b4c5d6e7f8a"
          }
        ],
        "output_edges": []
      }
    ]
  }
}
```
