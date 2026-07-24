# BranchingOperator

Splits a PyArrow table into multiple output tables based on filter criteria. Short name: `branching` · Category: Functional

## Overview

The BranchingOperator evaluates each document against one or more branch conditions and routes it to the matching branch output. Use it to implement conditional processing paths — for example, separating high-quality documents from low-quality ones, routing by language, or splitting by document type before applying different downstream operators.

## Key Features

- Any number of branches, each with independent filter criteria
- Criteria can be SQL-like string expressions or structured JSON
- `AND` / `OR` logical combination of criteria within a branch
- Unconditional branches (no criteria) receive all documents — use for fan-out
- Returns one PyArrow table per branch
- Pairs with `MergeOperator` to recombine branches after parallel processing

## Operator Configuration

```json
{
  "name": "branch_by_quality",
  "type": "branching",
  "depends_on": ["extract"],
  "config": {
    "branch_criteria": [
      {
        "link_id": "high-quality",           // required — unique branch identifier
        "link_name": "High Quality Docs",    // optional — human-readable label
        "criteria_list": [
          "flesch_ease > 60",
          "num_words > 200"
        ],
        "logical_operator": "AND"            // optional, default AND
      },
      {
        "link_id": "low-quality",
        "link_name": "Low Quality Docs",
        "criteria_list": ["flesch_ease <= 60"]
      }
    ]
  }
}
```

## Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `branch_criteria` | `list[object]` | Yes | — | List of branch definitions. Minimum 1 branch. |

**Branch object fields:**

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `link_id` | `string` | Yes | Unique identifier for this branch. Used by `MergeOperator` to reference the branch output. |
| `link_name` | `string` | No | Human-readable branch label. |
| `criteria_list` | `list[string]` | No | SQL-like filter expressions (e.g. `"lang_name = 'en'"`). Omit for an unconditional branch. |
| `criteria_json` | `object` | No | Structured filter criteria (alternative to `criteria_list`). |
| `logical_operator` | `string` | No | `"AND"` | Combine multiple criteria with `"AND"` or `"OR"`. |

**`criteria_json` format** (alternative to `criteria_list`):

```json
{
  "criteria_list": [
    { "variable": "lang_name", "operator": "==", "value": "en" }
  ]
}
```

Supported operators: `>` `<` `>=` `<=` `==` `!=` `LIKE` `IN` `NOT IN`

## Output Columns

The branching operator adds no new columns. Each branch output is a filtered subset of the input table with the same schema.

## Examples

### Example 1: Route by language

```json
{
  "name": "branch_language",
  "type": "branching",
  "depends_on": ["detect_language"],
  "config": {
    "branch_criteria": [
      {
        "link_id": "english",
        "criteria_list": ["lang_name == 'en'"]
      },
      {
        "link_id": "other",
        "criteria_list": ["lang_name != 'en'"]
      }
    ]
  }
}
```

### Example 2: Fan-out to two parallel paths (unconditional)

```json
{
  "name": "fan_out",
  "type": "branching",
  "depends_on": ["extract"],
  "config": {
    "branch_criteria": [
      { "link_id": "path-a", "link_name": "Embed path" },
      { "link_id": "path-b", "link_name": "Store path" }
    ]
  }
}
```

## Troubleshooting

**Column referenced in criteria does not exist** — ensure the upstream operator that produces that column (e.g. `readability`, `language_detection`) ran before the branching operator.

**All documents go to one branch** — verify your criteria values match the actual column values. Use `docling-pipelines --list-operators --verbose` to check column types.

**`MergeOperator` cannot find a branch** — the `link_name` in your merge `input_links` must match the `link_id` value (not `link_name`) of the branching operator.

## Sample Flow

See [`sample_flows/advanced/branching_quality_routing.json`](../../../sample_flows/advanced/branching_quality_routing.json) for a complete example using branching with quality-based routing.
