# ReadabilityOperator

Computes text readability scores for document content using established readability formulas. Short name: `readability` · Category: Quality

## Overview

The ReadabilityOperator applies up to 13 readability formulas to the text content of each document and adds a score column for each selected formula. Use it before `SQLFilterOperator` to filter out documents that are too complex or too simple for your target audience, or to enrich your dataset with reading-level metadata for downstream analysis.

## Key Features

- 13 established readability formulas including Flesch, Gunning Fog, SMOG, Coleman-Liau, and more
- Select any subset of scores to compute — no need to run all 13
- Each score is added as a separate filterable column
- Supports grade-level, complexity, and reading-time metrics
- Works on any text content column

## Operator Configuration

```json
{
  "name": "compute_readability",
  "type": "readability",
  "depends_on": ["extract"],
  "config": {
    "readability_score_list": [
      "flesch_ease",       // 0–100, higher = easier
      "flesch_kincaid",    // US grade level
      "gunning_fog"        // grade level based on complex words
    ]
  }
}
```

## Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `readability_score_list` | `list[string]` | Yes | All 13 scores | Names of readability formulas to compute. See score reference below. |

**Available score names:**

| Score name | Output type | Description |
| --- | --- | --- |
| `flesch_ease` | `float` | 0–100 scale; higher = easier to read |
| `flesch_kincaid` | `float` | US grade level |
| `gunning_fog` | `float` | Grade level based on long sentences and hard words |
| `smog_index` | `float` | Grade level from polysyllabic word count |
| `coleman_liau_index` | `float` | Grade level using letter counts |
| `automated_readability_index` | `float` | Grade level using character/word ratios |
| `dale_chall_readability_score` | `float` | Grade level from uncommon word frequency |
| `difficult_words` | `int` | Count of uncommon words |
| `linsear_write_formula` | `float` | Grade level for technical writing |
| `text_standard` | `float` | Consensus grade level from multiple formulas |
| `spache_readability` | `float` | Grade level for primary school texts (grades 1–4) |
| `mcalpine_eflaw` | `float` | Readability metric for ESL/EFL learners |
| `reading_time` | `float` | Estimated reading time in seconds |

## Output Columns

Each score in `readability_score_list` produces one output column named `<score_name>_textstat`.

| Column | Type | Description |
| --- | --- | --- |
| `flesch_ease_textstat` | `float` | Flesch Reading Ease score (if selected) |
| `flesch_kincaid_textstat` | `float` | Flesch-Kincaid grade level (if selected) |
| `gunning_fog_textstat` | `float` | Gunning Fog index (if selected) |
| `<score_name>_textstat` | `float` or `int` | Any other selected score |

## Examples

### Example 1: Grade-level filter pipeline

```json
{
  "flow_name": "Readability Filter",
  "flow": [
    {
      "name": "ingest", "type": "ingest_local",
      "config": { "paths": "./documents" }
    },
    {
      "name": "extract", "type": "extract_operator",
      "depends_on": ["ingest"],
      "config": {
        "text_extraction": { "provider": "docling_library" },
        "entity_extraction": { "provider": "none" }
      }
    },
    {
      "name": "readability", "type": "readability",
      "depends_on": ["extract"],
      "config": {
        "readability_score_list": ["flesch_ease", "flesch_kincaid"]
      }
    },
    {
      "name": "filter", "type": "sql_filter",
      "depends_on": ["readability"],
      "config": {
        "criteria_list": [
          "flesch_ease_textstat >= 60",
          "flesch_kincaid_textstat <= 10"
        ]
      }
    }
  ]
}
```

### Example 2: Compute all 13 scores

```json
{
  "name": "full_readability",
  "type": "readability",
  "depends_on": ["extract"],
  "config": {
    "readability_score_list": [
      "flesch_ease", "flesch_kincaid", "gunning_fog", "smog_index",
      "coleman_liau_index", "automated_readability_index",
      "dale_chall_readability_score", "difficult_words",
      "linsear_write_formula", "text_standard",
      "spache_readability", "mcalpine_eflaw", "reading_time"
    ]
  }
}
```

## Troubleshooting

**`readability_score_list` is empty or missing** — the operator requires at least one score name. Provide a list with one or more valid score names from the table above.

**Invalid score name** — use the exact names from the score reference table. Names are case-sensitive.

**All scores are `0.0` or `NaN`** — the `content` column is empty or the text is too short (fewer than ~30 words). Readability formulas are unreliable on very short texts.

## Sample Flow

See [`sample_flows/advanced/quality_branching_merge_pipeline.json`](../../../sample_flows/advanced/quality_branching_merge_pipeline.json) for a complete example using readability scoring in a quality-filtered pipeline.
