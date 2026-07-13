# DocQualityOperator

Computes 11 document quality metrics for text content. Short name: `doc_quality` · Category: Quality

## Overview

The DocQualityOperator analyses each document's text and adds 11 quality metric columns to the PyArrow table. The metrics cover word counts, symbol ratios, formatting patterns, and content quality indicators. Use it before `SQLFilterOperator` to filter out low-quality documents (e.g. placeholder content, profanity, or documents with unusual symbol density).

## Key Features

- 11 quality metrics computed in a single pass
- All output columns are filterable in `SQLFilterOperator`
- Detects placeholder lorem ipsum content
- Detects profanity (configurable language)
- Captures structural signals: bullet points, ellipsis lines, curly brackets (code)
- Powered by the Data Prep Kit (`dpk_doc_quality`) library

## Operator Configuration

```json
{
  "name": "doc_quality",
  "type": "doc_quality",
  "depends_on": ["extract"],
  "config": {
    "text_lang": "en"   // optional, default "en"
  }
}
```

## Parameters

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `text_lang` | `string` | No | `"en"` | Language for profanity detection. Affects `docq_contain_bad_word` accuracy. |

## Output Columns

| Column | Type | Description |
| --- | --- | --- |
| `docq_total_words` | `int` | Total word count |
| `docq_mean_word_len` | `float` | Mean word length in characters |
| `docq_symbol_to_word_ratio` | `float` | Ratio of symbols (emojis, special chars) to words (0.0–1.0+) |
| `docq_sentence_count` | `int` | Number of sentences |
| `docq_lorem_ipsum_ratio` | `float` | Ratio of lorem ipsum placeholder text (0.0–1.0) |
| `docq_contain_bad_word` | `bool` | `true` if the document contains profanity |
| `docq_bullet_point_ratio` | `float` | Ratio of lines starting with bullet points (0.0–1.0) |
| `docq_curly_bracket_ratio` | `float` | Ratio of curly brackets to text length (signal for code/JSON) |
| `docq_ellipsis_line_ratio` | `float` | Ratio of lines ending with `...` |
| `docq_alphabet_word_ratio` | `float` | Ratio of words containing at least one letter (0.0–1.0) |
| `docq_contain_common_en_words` | `float` | `1.0` if text contains common English words, `0.0` otherwise |

## Examples

### Example 1: Quality analysis and filter

```json
{
  "flow": [
    {
      "name": "quality",
      "type": "doc_quality",
      "depends_on": ["extract"],
      "config": { "text_lang": "en" }
    },
    {
      "name": "filter",
      "type": "sql_filter",
      "depends_on": ["quality"],
      "config": {
        "criteria_list": [
          "docq_total_words >= 50",
          "docq_contain_bad_word = false",
          "docq_lorem_ipsum_ratio < 0.1"
        ]
      }
    }
  ]
}
```

### Example 2: Filter out code-heavy documents

```json
{
  "name": "filter_code",
  "type": "sql_filter",
  "depends_on": ["doc_quality"],
  "config": {
    "criteria_list": [
      "docq_curly_bracket_ratio < 0.10",
      "docq_alphabet_word_ratio >= 0.85"
    ]
  }
}
```

## Troubleshooting

**All `docq_*` columns are `0` or `null`** — the `content` column is empty. Ensure `ExtractOperator` ran successfully upstream and produced text content.

**`docq_contain_bad_word` always `false`** — check that `text_lang` matches the document language. The profanity list is language-specific.

**`dpk_doc_quality` import error** — the Data Prep Kit library is not installed. Run `uv pip install dpk-doc-quality` or add it to your project dependencies.

## Sample Flow

See [`sample_flows/advanced/quality_branching_merge_pipeline.json`](../../../sample_flows/advanced/quality_branching_merge_pipeline.json) for a complete example using document quality scoring in a branching pipeline.
