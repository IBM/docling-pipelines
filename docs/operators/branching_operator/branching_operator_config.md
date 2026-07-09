# Branching Operator - Configuration Reference

## Overview

The Branching Operator enables conditional workflow branching based on specified filter criteria. It allows data to flow through multiple paths simultaneously, with each branch applying its own filter conditions to create different subsets of the input data.

- **Operator Name:** `branching`
- **Category**: Functional
- **Short Name**: `branching`

## Configuration Parameters

### 1. `branch_criteria` (List)
**Type:** List of Branch Objects  
**Required:** Yes  
**Description:** A list of branch configurations. Each branch includes a set of filter conditions, a logical operator (AND/OR) to combine them, and features to drop from the resulting table.  

**Branch Object Structure:**
- `link_id` (String, Required): Unique identifier for the branch
- `link_name` (String, Optional): Human-readable name for the branch
- `criteria_list` (List, Optional): List of SQL-like filter expressions
- `criteria_json` (JSON, Optional): JSON-formatted filter criteria with nested conditions
- `logical_operator` (String, Optional): "AND" or "OR" to combine criteria (default: "AND")

**Examples:**

Simple branching with criteria_list:
```json
"branch_criteria": [
  {
    "link_id": "high-quality",
    "link_name": "High Quality Documents",
    "criteria_list": [
      "flesch_reading_ease > 60",
      "num_words > 100"
    ],
    "logical_operator": "AND"
  },
  {
    "link_id": "low-quality",
    "link_name": "Low Quality Documents",
    "criteria_list": [
      "flesch_reading_ease <= 60"
    ]
  }
]
```

Advanced branching with criteria_json:
```json
"branch_criteria": [
  {
    "link_id": "english-docs",
    "link_name": "English Documents",
    "criteria_json": {
      "criteria_list": [
        {
          "variable": "lang_name",
          "operator": "==",
          "value": "en"
        }
      ]
    }
  },
  {
    "link_id": "other-langs",
    "link_name": "Other Languages",
    "criteria_json": {
      "criteria_list": [
        {
          "variable": "lang_name",
          "operator": "!=",
          "value": "en"
        }
      ]
    }
  }
]
```

Unconditional branching (duplicate data to multiple paths):
```json
"branch_criteria": [
  {
    "link_id": "path-a",
    "link_name": "Processing Path A"
  },
  {
    "link_id": "path-b",
    "link_name": "Processing Path B"
  }
]
```

## Output Behavior

The Branching Operator returns **multiple PyArrow tables** (one per branch), each containing documents that match the branch's filter criteria.

**Metadata Structure:**
```json
{
  "branches": {
    "high-quality": {
      "result_index": 0,
      "docs_filtered": 50,
      "remaining_docs": 150,
      "processed_docs": 150,
      "skipped_docs_count": 0,
      "failed_docs_count": 0
    },
    "low-quality": {
      "result_index": 1,
      "docs_filtered": 150,
      "remaining_docs": 50,
      "processed_docs": 50,
      "skipped_docs_count": 0,
      "failed_docs_count": 0
    }
  },
  "processed_docs": 200,
  "total_docs_count": 200
}
```

## Filter Criteria Syntax

### Criteria List Format
SQL-like expressions using column names and operators:

**Supported Operators:**
- Comparison: `>`, `<`, `>=`, `<=`, `==`, `!=`
- String: `LIKE`, `IN`, `NOT IN`
- Logical: Combined using `logical_operator` (AND/OR)

**Examples:**
```json
"criteria_list": [
  "num_words > 100",
  "flesch_reading_ease >= 60",
  "lang_name == 'en'",
  "document_type IN ('invoice', 'receipt')"
]
```

### Criteria JSON Format
Structured JSON format for complex conditions:

```json
"criteria_json": {
  "logical_operator": "AND",
  "criteria_list": [
    {
      "variable": "num_words",
      "operator": ">",
      "value": 100
    },
    {
      "variable": "lang_name",
      "operator": "==",
      "value": "en"
    }
  ]
}
```

## Configuration Examples

### Example 1: Quality-Based Branching
```json
{
  "operator": "branching",
  "config": {
    "branch_criteria": [
      {
        "link_id": "high-quality",
        "link_name": "High Quality",
        "criteria_list": [
          "flesch_reading_ease > 60",
          "num_words > 200"
        ],
        "logical_operator": "AND"
      },
      {
        "link_id": "medium-quality",
        "link_name": "Medium Quality",
        "criteria_list": [
          "flesch_reading_ease > 40",
          "flesch_reading_ease <= 60"
        ],
        "logical_operator": "AND"
      },
      {
        "link_id": "low-quality",
        "link_name": "Low Quality",
        "criteria_list": [
          "flesch_reading_ease <= 40"
        ]
      }
    ]
  }
}
```

### Example 2: Language-Based Branching
```json
{
  "operator": "branching",
  "config": {
    "branch_criteria": [
      {
        "link_id": "english",
        "criteria_json": {
          "criteria_list": [
            {
              "variable": "lang_name",
              "operator": "==",
              "value": "en"
            }
          ]
        }
      },
      {
        "link_id": "spanish",
        "criteria_json": {
          "criteria_list": [
            {
              "variable": "lang_name",
              "operator": "==",
              "value": "es"
            }
          ]
        }
      }
    ]
  }
}
```

### Example 3: Document Type Branching
```json
{
  "operator": "branching",
  "config": {
    "branch_criteria": [
      {
        "link_id": "financial",
        "link_name": "Financial Documents",
        "criteria_list": [
          "document_type IN ('invoice', 'receipt', 'bank_statement')"
        ]
      },
      {
        "link_id": "legal",
        "link_name": "Legal Documents",
        "criteria_list": [
          "document_type IN ('contract', 'agreement', 'license')"
        ]
      },
      {
        "link_id": "other",
        "link_name": "Other Documents",
        "criteria_list": [
          "document_type NOT IN ('invoice', 'receipt', 'bank_statement', 'contract', 'agreement', 'license')"
        ]
      }
    ]
  }
}
```

## Best Practices

1. **Branch Naming**: Use descriptive `link_name` values for better flow visualization
2. **Unique IDs**: Ensure each branch has a unique `link_id`
3. **Criteria Validation**: Test filter criteria with sample data before production
4. **Logical Operators**: Use AND for restrictive filters, OR for inclusive filters
5. **Unconditional Branching**: Omit criteria for branches that should receive all documents
6. **Column Availability**: Ensure all columns referenced in criteria exist in the input data


## Complete Flow Example

- [Branching with Quality operators](../../../sample_flows/advanced/branching_quality_routing.json)
