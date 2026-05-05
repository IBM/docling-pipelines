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
        "name": "filter_languages",
        "operator": "sql_filter",
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
        },
        "input_edges": [
          {
            "node_id_ref": "c3d4e5f6-a7b8-4c5d-0e1f-2a3b4c5d6e7f"
          }
        ],
        "output_edges": []
      }
    ]
  }

```
