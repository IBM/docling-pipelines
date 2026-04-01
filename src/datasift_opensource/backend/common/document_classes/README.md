# Document Schemas

This directory stores document class definitions as JSON files. Each JSON file represents a document schema that can be used for document classification, entity extraction, and other document processing tasks.

## Structure

Each document schema JSON file should follow this format:

```json
{
  "document_type": "invoice",
  "description": "Schema for invoice documents",
  "fields": [
    {
      "name": "invoice_number",
      "type": "string",
      "description": "Unique invoice identifier"
    },
    {
      "name": "date",
      "type": "date",
      "description": "Invoice date"
    }
  ]
}
```

## Usage

Document schemas can be referenced by operators that need structured document definitions, such as:
- Document classification operators
- Entity extraction operators
- Validation operators

## Adding New Schemas

To add a new document schema:
1. Create a new JSON file in this directory
2. Follow the schema format above
3. Name the file descriptively (e.g., `invoice_schema.json`, `purchase_order_schema.json`)