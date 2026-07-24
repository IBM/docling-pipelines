# EdedupOperator

Removes exact duplicate documents from a dataset by comparing document hash IDs. Short name: `ededup` · Category: Quality

## Overview

The EdedupOperator (exact deduplication) identifies and removes documents that share the same `doc_id_hash` value, keeping only the first occurrence. Use it after `ExtractOperator` or `ChunkerOperator` to eliminate identical documents before embedding or storing.

## Key Features

- Exact deduplication based on SHA-256 document hash (`doc_id_hash` column)
- Keeps the first occurrence of any duplicated document
- Tracks and reports the number of duplicates removed in operator metadata
- Works on any dataset size with minimal memory overhead

## Operator Configuration

```json
{
  "name": "deduplicate",
  "type": "ededup",
  "depends_on": ["extract"],
  "config": {}
}
```

No configuration parameters are required. The operator uses the `doc_id_hash` column produced automatically by `ExtractOperator` and `ChunkerOperator`.

## Parameters

This operator has no configuration parameters. It always deduplicates on the `doc_id_hash` column.

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| — | — | — | — | No parameters. |

## Output Columns

This operator removes rows but adds no new columns. The output table has the same schema as the input.

## Examples

### Example 1: Deduplicate after extraction

```json
{
  "name": "deduplicate",
  "type": "ededup",
  "depends_on": ["extract_documents"],
  "config": {}
}
```

### Example 2: Full deduplication pipeline

```json
{
  "flow_name": "Deduplication Pipeline",
  "flow": [
    {
      "name": "ingest",
      "type": "ingest_local",
      "config": { "paths": "./sample_documents" }
    },
    {
      "name": "extract",
      "type": "extract_operator",
      "depends_on": ["ingest"],
      "config": {
        "text_extraction": { "provider": "docling_library" },
        "entity_extraction": { "provider": "none" }
      }
    },
    {
      "name": "deduplicate",
      "type": "ededup",
      "depends_on": ["extract"],
      "config": {}
    }
  ]
}
```

## Troubleshooting

**`KeyError: doc_id_hash`** — the `doc_id_hash` column is not present. Ensure `ExtractOperator` or `ChunkerOperator` runs before `ededup`; both operators generate this column automatically.

**Deduplication removes too many documents** — check that documents are genuinely identical and not just similar. This operator uses exact hash matching; fuzzy or semantic deduplication is not supported.

## Sample Flow

See [`sample_flows/advanced/quality_branching_merge_pipeline.json`](../../../sample_flows/advanced/quality_branching_merge_pipeline.json) for a complete pipeline example that includes deduplication.
