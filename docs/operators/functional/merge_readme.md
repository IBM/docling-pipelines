# MergeOperator

Combines multiple PyArrow table inputs into a single table. Short name: `merge` · Category: Functional

## Overview

The MergeOperator accepts two or more input tables and merges them using one of two strategies: row concatenation (stacking tables vertically) or column join (combining columns by document ID). Use it to recombine branches after parallel processing with `BranchingOperator`, or to merge documents from multiple ingest sources.

## Key Features

- Two merge strategies: row concatenation and column join
- Column join supports inner join and full outer join
- Handles complex PyArrow types (lists, structs) in column merges
- Duplicate document detection in row merges (fails fast on collision)
- Column suffix applied automatically when column names conflict

## Operator Configuration

```json
{
  "name": "merge_sources",
  "type": "merge",
  "depends_on": ["ingest_folder_1", "ingest_folder_2"],
  "config": {
    "merge_type": "rows",          // "rows" or "columns"
    "input_links": [
      { "link_name": "source1" },
      { "link_name": "source2" }
    ]
  }
}
```

## Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `merge_type` | `string` | Yes | — | `"rows"` to concatenate tables vertically; `"columns"` to join on the `id` column. |
| `column_option` | `string` | Conditional | — | Required when `merge_type` is `"columns"`. `"inner_join"` or `"full_outer"`. |
| `input_links` | `list[object]` | Yes | — | At least 2 link definitions. Each object has a `link_name` field matching a branch `link_id`. |

## Output Columns

**Row merge:** output has the same columns as the input tables. Row count is the sum of all input tables.

**Column merge:** output has all columns from all input tables combined. Duplicate column names get a suffix based on their `link_name` (e.g. `name_branch2`). The `id` column is never suffixed.

## Examples

### Example 1: Merge two ingest sources (row merge)

```json
{
  "name": "merge_sources",
  "type": "merge",
  "depends_on": ["ingest_folder_1", "ingest_folder_2"],
  "config": {
    "merge_type": "rows",
    "input_links": [
      { "link_name": "source1" },
      { "link_name": "source2" }
    ]
  }
}
```

### Example 2: Combine analysis results from parallel branches (column merge)

```json
{
  "name": "merge_analyses",
  "type": "merge",
  "depends_on": ["compute_readability", "detect_language"],
  "config": {
    "merge_type": "columns",
    "column_option": "inner_join",
    "input_links": [
      { "link_name": "readability" },
      { "link_name": "language" }
    ]
  }
}
```

### Example 3: Full outer join to preserve all documents

```json
{
  "name": "merge_all",
  "type": "merge",
  "depends_on": ["base_docs", "optional_scores"],
  "config": {
    "merge_type": "columns",
    "column_option": "full_outer",
    "input_links": [
      { "link_name": "base_docs" },
      { "link_name": "optional_scores" }
    ]
  }
}
```

## Troubleshooting

**`merge_type` required** — add `"merge_type": "rows"` or `"merge_type": "columns"` to the config.

**`column_option` required when `merge_type` is `"columns"`** — add `"column_option": "inner_join"` or `"column_option": "full_outer"`.

**`The Merging operator received the same documents from multiple branches`** — duplicate document IDs detected in a row merge. Either use a column merge, or ensure branches process non-overlapping documents.

**Fewer than 2 input links** — `input_links` must contain at least 2 entries.

## Sample Flow

See [`sample_flows/advanced/quality_branching_merge_pipeline.json`](../../../sample_flows/advanced/quality_branching_merge_pipeline.json) for a complete example using merge to recombine branched pipelines.
