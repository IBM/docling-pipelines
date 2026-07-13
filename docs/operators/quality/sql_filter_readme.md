# SQLFilterOperator

Filters a PyArrow table using SQL-like WHERE conditions. Short name: `sql_filter` · Category: Quality

## Overview

The SQLFilterOperator applies row-level filter criteria to a PyArrow table, keeping only rows that satisfy the conditions. Use it after any quality-scoring operator (readability, language detection, doc quality, ml enrichment) to discard documents that do not meet your quality threshold. It also supports dropping columns from the result.

## Key Features

- SQL-style filter expressions using column names and standard comparison operators
- Supports list-based criteria (simple strings) and JSON-based criteria (structured, nestable)
- Logical `AND` / `OR` combining of multiple conditions
- Nested logical groups for complex filter trees
- Optional column dropping from the filtered output
- Works on any columns present in the input table

## Operator Configuration

```json
{
  "name": "filter_documents",
  "type": "sql_filter",
  "depends_on": ["previous_op"],
  "config": {
    "criteria_list": [
      "lang_name = 'en'",
      "docq_total_words >= 50"
    ],
    "logical_operator": "AND"   // optional, default AND
  }
}
```

## Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `criteria_list` | `list[string]` | No* | `[]` | SQL WHERE expressions as strings. At least one of `criteria_list` or `criteria_json` must be provided. |
| `criteria_json` | `object` | No* | `null` | Structured filter criteria with nested logical groups. See format below. |
| `logical_operator` | `string` | No | `"AND"` | How to join multiple `criteria_list` items. `"AND"` or `"OR"`. |
| `features_to_drop` | `list[string]` | No | `[]` | Column names to remove from the output table. Cannot drop `id`, `contents`, or `pages_processed`. |

**`criteria_json` format:**

```json
{
  "logical_operator": "AND",
  "criteria_list": [
    { "variable": "column_name", "operator": "=", "value": "en" },
    {
      "logical_operator": "OR",
      "criteria_list": [
        { "variable": "num_words", "operator": ">", "value": 100 },
        { "variable": "page_count", "operator": ">", "value": 5 }
      ]
    }
  ]
}
```

Supported operators: `=` `==` `!=` `<>` `>` `<` `>=` `<=` `LIKE` `NOT LIKE` `IN` `NOT IN` `IS NULL` `IS NOT NULL` `BETWEEN`

## Output Columns

This operator removes rows and optionally removes columns but adds no new columns. The output schema is a subset of the input schema.

## Examples

### Example 1: Keep only English documents with enough words

```json
{
  "name": "filter_quality",
  "type": "sql_filter",
  "depends_on": ["detect_language"],
  "config": {
    "criteria_list": ["lang_name = 'en'", "num_words >= 50"],
    "logical_operator": "AND"
  }
}
```

### Example 2: Complex nested filter with column dropping

```json
{
  "name": "filter_complex",
  "type": "sql_filter",
  "depends_on": ["ml_enrichment"],
  "config": {
    "criteria_json": {
      "logical_operator": "AND",
      "criteria_list": [
        { "variable": "lang_name", "operator": "in", "value": ["en", "fr"] },
        {
          "logical_operator": "OR",
          "criteria_list": [
            { "variable": "num_words", "operator": ">", "value": 100 },
            { "variable": "page_count", "operator": ">", "value": 5 }
          ]
        }
      ]
    },
    "features_to_drop": ["intermediate_score"]
  }
}
```

## Troubleshooting

**`Column not found` error** — the column referenced in your filter does not exist in the table. Check that the upstream operator producing that column ran successfully. Use `docling-pipelines --list-operators --verbose` to see what columns each operator produces.

**All documents filtered out** — your threshold is too strict. Start with a loose filter and tighten it after inspecting the distribution of values.

**`features_to_drop` raises an error** — you cannot drop `id`, `contents`, or `pages_processed`. Remove those from the drop list.

## Sample Flow

See [`sample_flows/advanced/quality_branching_merge_pipeline.json`](../../../sample_flows/advanced/quality_branching_merge_pipeline.json) for a complete example using SQL filtering for quality-based routing.
