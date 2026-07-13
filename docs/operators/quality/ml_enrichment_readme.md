# MLEnrichmentOperator

Computes 30 text quality and statistical features for document content. Short name: `ml_enrichment` · Category: Quality

## Overview

The MLEnrichmentOperator analyses the text of each document and adds 30 feature columns covering word counts, character ratios, paragraph duplication, and n-gram frequency metrics. Use it before `SQLFilterOperator` to filter documents based on statistical quality signals, or to enrich your dataset with features for downstream ML pipelines.

## Key Features

- 30 features computed in a single pass
- All features are filterable in `SQLFilterOperator`
- Configurable output column prefix to avoid name collisions
- Language-aware tokenisation via an input language column
- Covers basic counts, ratio metrics, paragraph duplication, and n-gram statistics

## Operator Configuration

```json
{
  "name": "ml_enrichment",
  "type": "ml_enrichment",
  "depends_on": ["detect_language"],
  "config": {
    "lang_column": "lang_name",          // optional, default "lang_name"
    "output_column_prefix": ""           // optional, default ""
  }
}
```

## Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `lang_column` | `string` | No | `"lang_name"` | Column containing the ISO 639-1 language code for language-aware tokenisation. |
| `output_column_prefix` | `string` | No | `""` | Prefix applied to all output column names (e.g. `"ml_"` → `ml_num_words`). Useful when running multiple enrichment passes. |

## Output Columns

All 30 columns are added to the PyArrow table. Column names gain the `output_column_prefix` if set.

| Column | Type | Description |
| --- | --- | --- |
| `num_newlines` | `int` | Number of newline characters |
| `num_paragraphs` | `int` | Number of paragraphs |
| `num_words` | `int` | Total word count |
| `num_chars` | `int` | Total character count |
| `total_non_newline_chars` | `int` | Characters excluding newlines |
| `avg_word_length` | `float` | Average word length in characters |
| `avg_paragraph_length_chars` | `float` | Average paragraph length in characters |
| `avg_paragraph_length_words` | `float` | Average paragraph length in words |
| `alphanumeric_char_ratio` | `float` | Ratio of alphanumeric characters (0.0–1.0) |
| `control_char_ratio` | `float` | Ratio of control characters (0.0–1.0) |
| `punctuation_char_ratio` | `float` | Ratio of punctuation characters (0.0–1.0) |
| `other_symbol_char_ratio` | `float` | Ratio of other symbol characters (0.0–1.0) |
| `tabs_word_ratio` | `float` | Ratio of tab characters to words |
| `hashes_word_ratio` | `float` | Ratio of `#` characters to words |
| `ellipsis_ratio` | `float` | Ratio of ellipsis characters |
| `bulletpoint_ratio` | `float` | Ratio of bullet point characters |
| `dup_paragraphs_ratio` | `float` | Ratio of duplicate paragraphs |
| `dup_paragraphs_char_ratio` | `float` | Character ratio in duplicate paragraphs |
| `top_2_gram_char_ratio` | `float` | Character ratio of most frequent 2-gram |
| `top_3_gram_char_ratio` | `float` | Character ratio of most frequent 3-gram |
| `top_4_gram_char_ratio` | `float` | Character ratio of most frequent 4-gram |
| `dup_5_gram_char_ratio` | `float` | Character ratio of duplicate 5-grams |
| `dup_6_gram_char_ratio` | `float` | Character ratio of duplicate 6-grams |
| `dup_7_gram_char_ratio` | `float` | Character ratio of duplicate 7-grams |
| `dup_8_gram_char_ratio` | `float` | Character ratio of duplicate 8-grams |
| `dup_9_gram_char_ratio` | `float` | Character ratio of duplicate 9-grams |
| `dup_10_gram_char_ratio` | `float` | Character ratio of duplicate 10-grams |

(30 columns total; 3 additional columns are computed internally and not listed here)

## Examples

### Example 1: Enrich and filter on word count

```json
{
  "flow": [
    {
      "name": "enrich",
      "type": "ml_enrichment",
      "depends_on": ["detect_language"],
      "config": { "lang_column": "lang_name" }
    },
    {
      "name": "filter",
      "type": "sql_filter",
      "depends_on": ["enrich"],
      "config": {
        "criteria_list": [
          "num_words >= 100",
          "dup_paragraphs_ratio < 0.3",
          "alphanumeric_char_ratio >= 0.7"
        ]
      }
    }
  ]
}
```

### Example 2: Use a column prefix to avoid conflicts

```json
{
  "name": "ml_enrichment",
  "type": "ml_enrichment",
  "depends_on": ["detect_language"],
  "config": {
    "lang_column": "lang_name",
    "output_column_prefix": "ml_"
  }
}
```

## Troubleshooting

**`lang_column` column not found** — ensure `LanguageDetectionOperator` ran before `MLEnrichmentOperator`, or set `lang_column` to match the actual column name in your table.

**All ratio columns are `0.0`** — the `content` column is empty. Ensure `ExtractOperator` produced text content before this operator runs.

**Column name conflicts** — set `output_column_prefix` to a unique prefix (e.g. `"ml_"`) to avoid collisions with columns from other operators.

## Sample Flow

See [`sample_flows/advanced/quality_branching_merge_pipeline.json`](../../../sample_flows/advanced/quality_branching_merge_pipeline.json) for a complete example that includes ML text enrichment.
