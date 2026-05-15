# Merge Operator Configuration Reference

## Overview
The Merge operator combines multiple PyArrow tables from different branches in a flow. It supports two merge strategies: row concatenation (vertical merge) and column joins (horizontal merge).

- **Operator Name**: `merge`
- **Category**: Functional
- **Short Name**: `merge`

## Configuration Parameters

### 1. merge_type
- **Type**: String
- **Required**: Yes
- **Default**: `"rows"`
- **Valid Values**: `"rows"`, `"columns"`
- **Description**: Specifies how tables should be merged

**Values:**
- `"rows"`: Concatenates tables vertically (one after another)
- `"columns"`: Joins tables horizontally on the ID column

**Example:**
```json
"merge_type": "rows"
```

### 2. column_option
- **Type**: String
- **Required**: Only when `merge_type` is `"columns"`
- **Valid Values**: `"inner_join"`, `"full_outer"`
- **Description**: Specifies the join type for column merges

**Values:**
- `"inner_join"`: Only keeps rows with matching IDs in all tables
- `"full_outer"`: Keeps all rows from all tables, filling missing values with null

**Example:**
```json
"column_option": "inner_join"
```

### 3. input_links
- **Type**: Array of objects
- **Required**: Yes (minimum 2 links)
- **Description**: Defines the input branches to merge

**Structure:**
```json
"input_links": [
  {"link_name": "branch1"},
  {"link_name": "branch2"}
]
```

## Merge Strategies

### Row Merge (Concatenation)
Stacks tables vertically, combining all rows from all input branches.

**Requirements:**
- All tables must have compatible schemas
- Document IDs must be unique across all branches (no duplicates)

**Use Cases:**
- Merging documents from different sources
- Combining results from parallel processing paths
- Aggregating data from multiple ingest operators

**Behavior:**
- Preserves all columns from all tables
- Automatically promotes compatible types
- Fails if duplicate document IDs are detected

### Column Merge (Join)
Joins tables horizontally on the ID column, adding columns from each branch.

**Requirements:**
- All tables must have an `id` column
- Join type determines how missing IDs are handled

**Use Cases:**
- Combining different analyses of the same documents
- Adding enrichment data to existing documents
- Merging quality scores with document content

**Behavior:**
- Joins on the `id` column
- Adds suffix to duplicate column names (e.g., `name_branch2`)
- Handles complex data types (lists, structs) through remapping
- Preserves the original `id` column without suffix

## Configuration Examples

### Example 1: Row Merge (Basic)
Merge documents from two different directories:

```json
{
  "id": "merge-node-1",
  "name": "merge_documents",
  "operator": "merge",
  "config": {
    "merge_type": "rows",
    "input_links": [
      {"link_name": "source1"},
      {"link_name": "source2"}
    ]
  },
  "input_edges": [
    {"node_id_ref": "ingest-node-1", "link_name": "source1"},
    {"node_id_ref": "ingest-node-2", "link_name": "source2"}
  ]
}
```

### Example 2: Column Merge (Inner Join)
Combine readability scores with language detection results:

```json
{
  "id": "merge-node-2",
  "name": "merge_analyses",
  "operator": "merge",
  "config": {
    "merge_type": "columns",
    "column_option": "inner_join",
    "input_links": [
      {"link_name": "readability"},
      {"link_name": "language"}
    ]
  },
  "input_edges": [
    {"node_id_ref": "readability-node", "link_name": "readability"},
    {"node_id_ref": "language-node", "link_name": "language"}
  ]
}
```

### Example 3: Column Merge (Full Outer Join)
Merge optional enrichments, keeping all documents:

```json
{
  "id": "merge-node-3",
  "name": "merge_enrichments",
  "operator": "merge",
  "config": {
    "merge_type": "columns",
    "column_option": "full_outer",
    "input_links": [
      {"link_name": "base_docs"},
      {"link_name": "optional_scores"}
    ]
  },
  "input_edges": [
    {"node_id_ref": "extract-node", "link_name": "base_docs"},
    {"node_id_ref": "scoring-node", "link_name": "optional_scores"}
  ]
}
```

## Complete Flow Examples

### Flow 1: Merging Multiple Data Sources
```json
{
  "dag": [
    {
      "id": "ingest-1",
      "name": "ingest_folder_1",
      "operator": "ingest_local_folder",
      "config": {
        "input_folder": "./data/source1"
      },
      "input_edges": [],
      "output_edges": [{"node_id_ref": "merge-1"}]
    },
    {
      "id": "ingest-2",
      "name": "ingest_folder_2",
      "operator": "ingest_local_folder",
      "config": {
        "input_folder": "./data/source2"
      },
      "input_edges": [],
      "output_edges": [{"node_id_ref": "merge-1"}]
    },
    {
      "id": "merge-1",
      "name": "merge_sources",
      "operator": "merge",
      "config": {
        "merge_type": "rows",
        "input_links": [
          {"link_name": "source1"},
          {"link_name": "source2"}
        ]
      },
      "input_edges": [
        {"node_id_ref": "ingest-1", "link_name": "source1"},
        {"node_id_ref": "ingest-2", "link_name": "source2"}
      ],
      "output_edges": []
    }
  ]
}
```

### Flow 2: Combining Analysis Results
```json
{
  "dag": [
    {
      "id": "ingest-1",
      "name": "ingest_documents",
      "operator": "ingest_local_folder",
      "config": {
        "input_folder": "./documents"
      },
      "input_edges": [],
      "output_edges": [
        {"node_id_ref": "branch-1"},
        {"node_id_ref": "branch-2"}
      ]
    },
    {
      "id": "branch-1",
      "name": "compute_readability",
      "operator": "readability",
      "config": {
        "readability_score_list": ["flesch_ease", "flesch_kincaid"]
      },
      "input_edges": [{"node_id_ref": "ingest-1"}],
      "output_edges": [{"node_id_ref": "merge-1"}]
    },
    {
      "id": "branch-2",
      "name": "detect_language",
      "operator": "language_detection",
      "config": {},
      "input_edges": [{"node_id_ref": "ingest-1"}],
      "output_edges": [{"node_id_ref": "merge-1"}]
    },
    {
      "id": "merge-1",
      "name": "merge_analyses",
      "operator": "merge",
      "config": {
        "merge_type": "columns",
        "column_option": "inner_join",
        "input_links": [
          {"link_name": "readability"},
          {"link_name": "language"}
        ]
      },
      "input_edges": [
        {"node_id_ref": "branch-1", "link_name": "readability"},
        {"node_id_ref": "branch-2", "link_name": "language"}
      ],
      "output_edges": []
    }
  ]
}
```

## Output Schema

### Row Merge Output
- Preserves all columns from all input tables
- Row count = sum of all input table rows
- Column names remain unchanged

### Column Merge Output
- Combines columns from all input tables
- Row count depends on join type:
  - Inner join: Only matching IDs
  - Full outer: All IDs from all tables
- Duplicate column names get suffixed with link name (e.g., `name_branch2`)
- The `id` column is never suffixed

## Validation Rules

1. **Minimum Input Links**: At least 2 input links required
2. **Merge Type Required**: `merge_type` must be specified
3. **Column Option for Column Merge**: `column_option` required when `merge_type` is `"columns"`
4. **Valid Merge Type**: Must be either `"rows"` or `"columns"`
5. **Valid Column Option**: Must be either `"inner_join"` or `"full_outer"`
6. **Unique Link Names**: All link names must be unique
7. **No Duplicate IDs (Row Merge)**: Row merge fails if duplicate document IDs are detected

## Error Handling

### Common Errors

**Error**: "At least two input links are required for merging"
- **Cause**: Less than 2 input links configured
- **Solution**: Add at least 2 input links to the configuration

**Error**: "Merge type is required"
- **Cause**: `merge_type` parameter not specified
- **Solution**: Add `merge_type` to configuration

**Error**: "Column option is required when merge_type is 'columns'"
- **Cause**: `column_option` not specified for column merge
- **Solution**: Add `column_option` with value `"inner_join"` or `"full_outer"`

**Error**: "The Merging operator received the same documents from multiple branches"
- **Cause**: Duplicate document IDs detected in row merge
- **Solution**: Use column merge instead, or ensure branches process different documents

## Best Practices

### When to Use Row Merge
- Combining documents from different sources
- Merging results from parallel processing of different document sets
- Aggregating data where documents are guaranteed to be unique

### When to Use Column Merge
- Adding analysis results to existing documents
- Combining different enrichments of the same documents
- Merging quality scores with document metadata

### Performance Considerations
- Row merge is faster for large datasets
- Column merge with complex data types (lists, structs) requires additional processing
- Use inner join when you only need documents present in all branches
- Use full outer join when you want to preserve all documents

### Link Naming
- Use descriptive link names that indicate the data source or analysis type
- Link names become column suffixes in column merges
- Keep link names short to avoid overly long column names

## Related Operators
- **BranchingOperator**: Creates multiple branches for parallel processing
- **NoopOperator**: Can be used to create test branches
- **SQLFilter**: Can filter merged results based on combined criteria