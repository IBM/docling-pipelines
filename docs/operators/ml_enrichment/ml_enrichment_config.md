# ML Enrichment Operator Configuration Reference

## Overview
The ML Enrichment operator computes 30+ text quality features for document content using machine learning-based analysis. It extracts statistical, structural, and quality metrics that can be used for data quality assessment, filtering, and feature engineering.

- **Operator Name**: `ml_enrichment`
- **Category**: Quality
- **Short Name**: `ml_enrichment`

## Configuration Parameters

### 1. lang_column
- **Type**: String
- **Required**: No
- **Default**: `"lang_name"`
- **Description**: Name of the column containing language identifier

Used for language-specific text processing and tokenization.

**Example:**
```json
"lang_column": "lang_name"
```

### 2. output_column_prefix
- **Type**: String
- **Required**: No
- **Default**: `""` (empty string)
- **Description**: Prefix to add to all output column names

Useful for avoiding column name conflicts or organizing features.

**Examples:**
```json
// No prefix
"output_column_prefix": ""
// Result: num_words, num_chars, etc.

// With prefix
"output_column_prefix": "ml_"
// Result: ml_num_words, ml_num_chars, etc.
```

## Output Features

The operator computes exactly 30 text quality metrics as defined in `DEFAULT_TEXT_ENRICHER_DICT`:

### Basic Counts
1. **num_newlines** (Integer) - Number of newline characters
2. **num_paragraphs** (Integer) - Number of paragraphs
3. **num_words** (Integer) - Total word count
4. **num_chars** (Integer) - Total character count
5. **total_non_newline_chars** (Integer) - Characters excluding newlines

### Average Metrics
6. **avg_word_length** (Float) - Average word length in characters
7. **avg_paragraph_length_chars** (Float) - Average paragraph length in characters
8. **avg_paragraph_length_words** (Float) - Average paragraph length in words

### Character Ratios
9. **alphanumeric_char_ratio** (Float) - Ratio of alphanumeric characters
10. **control_char_ratio** (Float) - Ratio of control characters
11. **punctuation_char_ratio** (Float) - Ratio of punctuation characters
12. **other_symbol_char_ratio** (Float) - Ratio of other symbol characters

### Special Pattern Ratios
13. **tabs_word_ratio** (Float) - Ratio of tabs to words
14. **hashes_word_ratio** (Float) - Ratio of hash symbols to words
15. **ellipsis_ratio** (Float) - Ratio of ellipsis characters
16. **bulletpoint_ratio** (Float) - Ratio of bullet point characters

### Paragraph Duplication
17. **dup_paragraphs_ratio** (Float) - Ratio of duplicate paragraphs
18. **dup_paragraphs_char_ratio** (Float) - Character ratio in duplicate paragraphs

### N-gram Top Frequency Ratios
19. **top_2_gram_char_ratio** (Float) - Character ratio of most frequent 2-gram
20. **top_3_gram_char_ratio** (Float) - Character ratio of most frequent 3-gram
21. **top_4_gram_char_ratio** (Float) - Character ratio of most frequent 4-gram

### N-gram Duplication Ratios
22. **dup_5_gram_char_ratio** (Float) - Character ratio of duplicate 5-grams
23. **dup_6_gram_char_ratio** (Float) - Character ratio of duplicate 6-grams
24. **dup_7_gram_char_ratio** (Float) - Character ratio of duplicate 7-grams
25. **dup_8_gram_char_ratio** (Float) - Character ratio of duplicate 8-grams
26. **dup_9_gram_char_ratio** (Float) - Character ratio of duplicate 9-grams
27. **dup_10_gram_char_ratio** (Float) - Character ratio of duplicate 10-grams

**Note:** All ratio metrics range from 0.0 to 1.0. All metrics are available for filtering in downstream operators.

**Note**: All features are filterable and can be used in SQL Filter or other downstream operators.

## Configuration Examples

### Example 1: Basic Enrichment
```json
{
  "id": "enrichment-node-1",
  "operator": "ml_enrichment",
  "config": {
    "lang_column": "lang_name"
  }
}
```

### Example 2: With Column Prefix
```json
{
  "id": "enrichment-node-2",
  "operator": "ml_enrichment",
  "config": {
    "lang_column": "language",
    "output_column_prefix": "quality_"
  }
}
```

### Example 3: Custom Column Names
```json
{
  "id": "enrichment-node-3",
  "operator": "ml_enrichment",
  "config": {
    "lang_column": "lang_name",
    "output_column_prefix": "ml_"
  }
}
```

## Complete Flow Example

```json
{
  "flow": {
    "name": "Language-Aware ML Enrichment and Quality Filtering Flow",
    "flow_id": "7f3a9c2d-1b6e-4d8a-9c5f-2e7a1b3d4f6c",
    "description": "A sample flow demonstrating ingestion, extraction, language detection, ML-based enrichment, and quality filtering",
    "storage": "in-memory",
    "execute_type": "local",

    "global_config": {
      "doc_column": "content",
      "disable_validation": "false",
      "force_ingest": true,
      "enable_micro_batching": true,
      "micro_batch_size": 10
    },

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
        "name": "detect_language",
        "operator": "lang_detect",
        "config": {
          "language_provider": "fasttext"
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
        "name": "ml_enrichment",
        "operator": "ml_enrichment",
        "config": {
          "lang_column": "language",
          "output_column_prefix": "quality_"
        },
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
        "name": "filter_quality_documents",
        "operator": "sql_filter",
        "config": {
          "filter_criteria": [
            "quality_num_words >= 100",
            "quality_alphanumeric_ratio >= 0.8",
            "quality_paragraph_duplicate_ratio < 0.3"
          ],
          "logical_operator": "AND"
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

## Use Cases

### 1. Basic ML Enrichment
Compute all 30 text quality metrics using default settings:
```json
{
  "id": "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
  "operator": "ml_enrichment",
  "config": {},
  "input_edges": [],
  "output_edges": []
}
```

### 2. Pipeline: Enrichment + Filtering
Use ML enrichment metrics for quality filtering:
```json
{
  "dag": [
    {
      "id": "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
      "operator": "ml_enrichment",
      "config": {},
      "input_edges": [],
      "output_edges": [
        {
          "node_id_ref": "b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e"
        }
      ]
    },
    {
      "id": "b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e",
      "operator": "sql_filter",
      "config": {
        "criteria_list": [
          "num_words >= 50",
          "alphanumeric_char_ratio >= 0.75",
          "control_char_ratio < 0.05"
        ]
      },
      "input_edges": [
        {
          "node_id_ref": "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d"
        }
      ],
      "output_edges": []
    }
  ]
}
```

## Downstream Usage Examples

After ML enrichment, use the computed metrics in downstream operators:

### Filter by Document Length
```json
{
  "operator": "sql_filter",
  "config": {
    "criteria_list": ["num_words >= 100", "num_paragraphs >= 3"]
  }
}
```

### Filter by Character Quality
```json
{
  "operator": "sql_filter",
  "config": {
    "criteria_list": [
      "alphanumeric_char_ratio >= 0.80",
      "control_char_ratio < 0.02"
    ]
  }
}
```

### Filter by Duplication
```json
{
  "operator": "sql_filter",
  "config": {
    "criteria_list": [
      "dup_paragraphs_ratio < 0.30",
      "top_3_gram_char_ratio < 0.20"
    ]
  }
}
```

```
