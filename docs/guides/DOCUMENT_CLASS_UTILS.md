# Document Class Utils

Utility for converting document class JSON schemas to Docling extraction templates.

## Overview

The `DocumentClassUtils` class provides methods to:
- Load document class JSON files
- Generate Docling-compatible extraction templates
- Extract field examples and descriptions
- List available document classes

## Key Features

- **Type Mapping**: Automatically maps document class field types to Docling types
- **Nested Field Support**: Handles nested structures like `line_items`
- **Examples & Descriptions**: Extracts metadata for validation
- **Flexible Configuration**: Control nested fields, field limits, etc.

## Usage

### Basic Template Generation

```python
from docpipe.utils.document_class_utils import generate_docling_template

# Generate template from document class
template = generate_docling_template(
    "src/docpipe/utils/document_classes/invoice.json"
)

# Result:
# {
#     "invoice_number": "string",
#     "invoice_date": "string",
#     "customer_name": "string",
#     "sub_total": "float",
#     "tax": "float",
#     "total": "float",
#     "line_items": {
#         "amount": "float",
#         "description": "string",
#         "quantity": "int"
#     }
# }
```

### Use with ExtractOperator

```python
from docpipe.utils.document_class_utils import generate_docling_template
from docpipe.core.operators.extract.extract_operator import ExtractOperator

# Generate template
template = generate_docling_template(
    "src/docpipe/utils/document_classes/invoice.json"
)

# Configure operator
config = {
    "doc_column": "content",
    "doc_id_hash": "doc_id_hash",
    "use_template": True,
    "template": template,
    "expand_extracted_data": True  # Creates individual columns
}

operator = ExtractOperator(config)
result_tables, metadata = operator.transform(input_table)
```

### Advanced Options

```python
from common.util.document_class_utils import DocumentClassUtils

# Without nested fields
template = DocumentClassUtils.generate_docling_template(
    doc_class_path="path/to/invoice.json",
    include_nested=False  # Excludes line_items
)

# Limit number of fields
template = DocumentClassUtils.generate_docling_template(
    doc_class_path="path/to/invoice.json",
    max_fields=10  # Only first 10 fields
)

# Get template with examples
result = DocumentClassUtils.generate_template_with_examples(
    doc_class_path="path/to/invoice.json"
)
# Returns:
# {
#     "template": {...},
#     "examples": {"invoice_number": ["INV-2024-001"], ...},
#     "descriptions": {"invoice_number": "unique identifier...", ...},
#     "document_type": "Invoice",
#     "document_description": "An invoice is..."
# }
```

### List Available Document Classes

```python
from common.util.document_class_utils import DocumentClassUtils

# List all document classes
doc_classes = DocumentClassUtils.list_available_document_classes()

for dc in doc_classes:
    print(f"{dc['name']}: {dc['description']}")
```

## Type Mapping

The utility maps document class types to Docling types:

| Document Class Type | Docling Type |
|---------------------|--------------|
| `string`            | `string`     |
| `date`              | `string`     |
| `decimal`           | `float`      |
| `float`             | `float`      |
| `long`              | `int`        |
| `int`               | `int`        |
| `boolean`           | `boolean`    |

## How It Works

1. **Loads Document Class**: Reads the JSON file containing document schema
2. **Extracts Fields**: Gets field definitions from `document.fields`
3. **Looks Up Types**: Finds corresponding types in `target_tables` section
4. **Maps Types**: Converts to Docling-compatible types
5. **Handles Nesting**: Recursively processes nested fields like `line_items`

## Document Class Structure

Document classes follow this structure:

```json
{
  "document_class_name": "Invoice",
  "document_class_schema": {
    "document": {
      "fields": [
        {
          "name": "invoice_number",
          "examples": ["INV-2024-001"],
          "description": "unique identifier..."
        }
      ]
    },
    "target_tables": [
      {
        "name": "Invoice",
        "columns": [
          {
            "name": "invoice_number",
            "type": "string",
            "source": {"field": ["invoice_number"]}
          }
        ]
      }
    ]
  }
}
```

## Examples

See `examples/generate_docling_template_example.py` for a complete working example.

## Testing

Run tests with:

```bash
# From project root
source .venv/bin/activate
uv run pytest tests/unit/common/util/test_document_class_utils.py -v
```

## Best Practices

1. **Start Simple**: Begin with basic fields, add complex ones incrementally
2. **Test Extraction**: Validate template with sample documents
3. **Use Examples**: Leverage the examples from document class for validation
4. **Limit Fields**: For better accuracy, focus on 10-15 most important fields
5. **Handle Nested Carefully**: Nested structures may need special handling in Docling

## API Reference

### `generate_docling_template(doc_class_path, include_nested=True, max_fields=None)`

Convenience function to generate template.

**Parameters:**
- `doc_class_path`: Path to document class JSON file
- `include_nested`: Include nested fields (default: True)
- `max_fields`: Maximum number of fields (default: None/all)

**Returns:** Dictionary with field names and types

### `DocumentClassUtils.generate_template_with_examples(doc_class_path, include_nested=True)`

Generate template with examples and descriptions.

**Returns:** Dictionary with template, examples, descriptions, and metadata

### `DocumentClassUtils.list_available_document_classes(doc_classes_dir=None)`

List all available document class files.

**Returns:** List of dictionaries with document class info