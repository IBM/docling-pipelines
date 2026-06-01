# SQL Filter Operator Configuration Reference

## Overview
The SQL Filter operator filters PyArrow tables using SQL-like WHERE clauses and optionally drops columns from the result. It supports both list-based and JSON-based filter criteria with complex logical operations.

- **Short Name**: `sql_filter`
- **Category**: Quality
- **Operator Name**: `sql_filter`

## Configuration Parameters

### 1. criteria_list (List Format)
- **Type**: List of strings
- **Required**: No (but either this or `criteria_json` should be provided)
- **Default**: `[]`
- **Description**: List of SQL WHERE clause conditions as strings

**Supported Operators:**
- Comparison: `=`, `==`, `!=`, `<>`, `>`, `<`, `>=`, `<=`
- Pattern matching: `LIKE`, `NOT LIKE`
- Set operations: `IN`, `NOT IN`
- Null checks: `IS NULL`, `IS NOT NULL`
- Range: `BETWEEN`

**Examples:**
```json
"criteria_list": [
  "language = 'en'",
  "word_count > 100",
  "doc_type IN ('pdf', 'docx')",
  "author IS NOT NULL"
]
```

### 2. criteria_json (JSON Format)
- **Type**: JSON object
- **Required**: No (but either this or `criteria_list` should be provided)
- **Default**: `null`
- **Description**: Structured JSON representation of filter criteria with nested logical operations

**JSON Structure:**
```json
{
  "logical_operator": "AND|OR",
  "criteria_list": [
    {
      "variable": "column_name",
      "operator": "=|!=|>|<|>=|<=|in|not in|like|not like|is null|is not null|between",
      "value": "value or [list of values]"
    }
  ]
}
```

**Nested Groups:**
```json
{
  "logical_operator": "AND",
  "criteria_list": [
    {
      "variable": "language",
      "operator": "=",
      "value": "en"
    },
    {
      "logical_operator": "OR",
      "criteria_list": [
        {
          "variable": "word_count",
          "operator": ">",
          "value": 100
        },
        {
          "variable": "page_count",
          "operator": ">",
          "value": 5
        }
      ]
    }
  ]
}
```

### 3. logical_operator
- **Type**: String
- **Required**: No
- **Default**: `"AND"`
- **Valid Values**: `["AND", "OR"]`
- **Description**: Logical operator to join multiple filter criteria (only applies to list format)

**Example:**
```json
{
  "criteria_list": [
    "language = 'en'",
    "word_count > 100"
  ],
  "logical_operator": "AND"
}
```
Result: `WHERE (language = 'en') AND (word_count > 100)`

### 4. features_to_drop
- **Type**: List of strings
- **Required**: No
- **Default**: `[]`
- **Description**: Column names to drop from the filtered result

**Protected Columns (Cannot Drop):**
- `id` - Document identifier
- `contents` - Document content
- `pages_processed` - Processing metadata

**Example:**
```json
"features_to_drop": ["temp_column", "intermediate_result"]
```

## Configuration Examples

### Example 1: Simple List-Based Filter
```json
{
  "id": "5e1a7b3c-8d2f-4c9a-b6e1-3f0d2a7c8b4e",
  "operator": "sql_filter",
  "config": {
    "criteria_list": [
      "language = 'en'",
      "word_count >= 50"
    ],
    "logical_operator": "AND"
  }
}
```

### Example 2: JSON-Based Complex Filter
```json
{
  "id": "5e1a7b3c-8d2f-4c9a-b6e1-3f0d2a7c8b4e",
  "operator": "sql_filter",
  "config": {
    "criteria_json": {
      "logical_operator": "AND",
      "criteria_list": [
        {
          "variable": "doc_type",
          "operator": "in",
          "value": ["pdf", "docx", "txt"]
        },
        {
          "logical_operator": "OR",
          "criteria_list": [
            {
              "variable": "word_count",
              "operator": "between",
              "value": [100, 1000]
            },
            {
              "variable": "page_count",
              "operator": ">",
              "value": 5
            }
          ]
        }
      ]
    }
  }
}
```

### Example 3: Filter with Column Dropping
```json
{
  "id": "5e1a7b3c-8d2f-4c9a-b6e1-3f0d2a7c8b4e",
  "operator": "sql_filter",
  "config": {
    "filter_criteria": ["quality_score > 0.7"],
    "features_to_drop": ["temp_score", "intermediate_data"]
  }
}
```

### Example 4: Pattern Matching
```json
{
  "id": "5e1a7b3c-8d2f-4c9a-b6e1-3f0d2a7c8b4e",
  "operator": "sql_filter",
  "config": {
    "filter_criteria_json": {
      "logical_operator": "AND",
      "criteria_list": [
        {
          "variable": "filename",
          "operator": "like",
          "value": "%.pdf"
        },
        {
          "variable": "author",
          "operator": "is not null"
        }
      ]
    }
  }
}
```

## Complete Flow Example

```json
{
  "flow_name": "Language Filter Pipeline",
  "description": "Ingest, extract, detect language, and filter documents",
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
      "name": "detect_language",
      "type": "language_detection",
      "depends_on": ["extract_documents"],
      "config": {
        "language_provider": "fasttext"
      }
    },
    {
      "name": "filter_languages",
      "type": "sql_filter",
      "depends_on": ["detect_language"],
      "config": {
        "filter_criteria_json": {
          "logical_operator": "AND",
          "criteria_list": [
            {
              "variable": "language",
              "operator": "in",
              "value": ["en", "es", "fr"]
            },
            {
              "variable": "confidence",
              "operator": ">=",
              "value": 0.8
            }
          ]
        },
        "features_to_drop": ["temp_metadata"]
      }
    }
  ]
}

```
