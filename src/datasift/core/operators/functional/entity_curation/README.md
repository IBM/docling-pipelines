# Entity Curation Operator

## Overview

The Entity Curation Operator transforms extracted entities into structured, curated data based on document class schemas. It applies field-specific transformations (currency conversion, date normalization, number parsing, etc.) to prepare entities for downstream processing and storage.

**Key Principle**: This operator processes entities that have already been extracted by operators like `ExtractEntitiesOllama`. It does NOT perform entity extraction itself.

## Features

- Schema-based entity transformation using document class definitions
- 4 built-in transformation functions for common data types
- Multi-language support for dates, numbers, and currencies
- Locale-aware parsing with Babel library
- JSON output format with nested structure matching schema's target tables
- Support for custom document types without schemas (returns empty dict)

## Quick Start

### Basic Configuration

```json
{
  "operator_type": "datasift.core.operators.functional.entity_curation.entity_curation_operator.EntityCurationOperator",
  "operator_params": {
    "entities_column": "entities",
    "document_type_column": "document_type"
  }
}
```

### Complete Pipeline Example (DAG Format)

Here's a complete working example:

```json
{
  "flow_name": "classify, extract entities, and curate flow",
  "description": "A flow to classify documents, extract entities with Ollama, and curate them using document schemas",
  "global_config": {
    "doc_column": "content",
    "disable_validation": true,
    "force_ingest": true,
    "output_folder": "./tests/fixtures/invoices",
    "storage": "disk",
    "execute_type": "local"
  },
  "flow": [
    {
      "name": "ingest",
      "type": "ingest_local",
      "config": {
        "paths": "./tests/fixtures/invoices",
        "include_filter": "txt,pdf,docx",
        "store_binary_content": "true",
        "max_workers": 2
      }
    },
    {
      "name": "classify",
      "type": "document_classifier",
      "depends_on": ["ingest"],
      "config": {
        "provider": "litellm",
        "model_id": "openai/granite4:latest",
        "provider_config": {
          "api_base": "http://localhost:11434/v1",
          "api_key": "<ollama_key>"
        },
        "confidence_threshold": 7.0,
        "doc_column": "content",
        "output_column": "document_type",
        "include_confidence": true,
        "include_reasoning": true,
        "max_content_length": 8000
      }
    },
    {
      "name": "extract_entities",
      "type": "extract_operator",
      "depends_on": ["classify"],
      "config": {
        "text_extraction_provider": "docling_library",
        "entity_extraction_provider": "litellm",
        "entity_model_id": "openai/granite4:latest",
        "entity_temperature": 0.0,
        "entity_max_tokens": 4096,
        "entity_provider_config": {
          "api_base": "http://localhost:11434/v1",
          "api_key": "<ollama_key>"
        },
        "doc_column": "content",
        "output_column": "entities",
        "max_workers": 4,
        "expand_extracted_data": true
      }
    },
    {
      "name": "curate_entities",
      "type": "entity_curation",
      "depends_on": ["extract_entities"],
      "config": {
        "entities_column": "entities",
        "document_type_column": "document_type"
      }
    }
  ]
}
```

**Important Notes**:
- Use the authoring format with `flow_name`, `flow` array, and `depends_on` for dependencies
- Operator types use short names (e.g., `"type": "entity_curation"`)
- The system automatically generates UUIDs and edges from the `depends_on` declarations

## Transformation Functions

The operator includes 4 core transformation functions:

### 1. currency_to_numeric
**Purpose**: Locale-aware currency parsing using Babel
**Supports**: All locales supported by Babel library
```python
# Input: "$1,234.56" (locale: en_US)
# Output: 1234.56

# Input: "1.234,56 €" (locale: de_DE)
# Output: 1234.56
```

### 2. make_date_uniform
**Purpose**: Date normalization to YYYY-MM-DD format
**Supports**: ISO, US, European, text, and compact date formats
**Features**: Uses datefinder as fallback for complex date parsing
```python
# Input: "2024-01-15" (ISO format)
# Output: "2024-01-15"

# Input: "01/15/2024" (US format)
# Output: "2024-01-15"

# Input: "January 15, 2024" (Text format)
# Output: "2024-01-15"

# Input: "20240115" (Compact format)
# Output: "2024-01-15"

# Input: "15 mars 2024" (French - via datefinder)
# Output: "2024-03-15"
```

### 3. to_number
**Purpose**: Multi-language number parsing
**Supports**: English, Chinese, Japanese, Korean, Spanish, French, German, Portuguese, Italian, Russian
```python
# Input: "一千二百三十四" (Chinese)
# Output: 1234

# Input: "mil doscientos treinta y cuatro" (Spanish)
# Output: 1234
```

### 4. weight_to_numeric
**Purpose**: Locale-aware weight conversion with ambiguous unit handling
**Supports**: Chinese (斤 = 500g), Japanese (斤 = 600g), and standard units
```python
# Input: "5斤" (locale: zh_CN)
# Output: 2.5  # 5 * 500g = 2500g = 2.5kg

# Input: "5斤" (locale: ja_JP)
# Output: 3.0  # 5 * 600g = 3000g = 3.0kg
```

## Document Class Schemas

The operator uses JSON schema files to define field mappings and transformations.

### Schema Structure

```json
{
  "document_class": "invoice",
  "target_tables": [
    {
      "table_name": "invoice_header",
      "columns": [
        {
          "column_name": "invoice_date",
          "source": "entities",
          "field": "invoice_date",
          "transform": "make_date_uniform"
        },
        {
          "column_name": "total_amount",
          "source": "entities",
          "field": "total_amount",
          "transform": "currency_to_numeric"
        },
        {
          "column_name": "quantity",
          "source": "entities",
          "field": "quantity",
          "transform": "to_number"
        },
        {
          "column_name": "weight_kg",
          "source": "entities",
          "field": "weight",
          "transform": "weight_to_numeric"
        }
      ]
    }
  ]
}
```

### Available Document Classes

The operator supports 40+ pre-defined document classes:

**Financial Documents**:
- invoice
- purchase_order
- receipt
- bank_statements
- credit_card_statements
- financial_statement
- expense_reports
- remittance_payment_advice

**Insurance Documents**:
- acord_insurance_form
- insurance_claim
- claimant_s_statement
- life_insurance_authorization_form

**Identity Documents**:
- driver_license
- passport
- national_id_card

**Business Documents**:
- bill_of_lading
- customs_form
- delivery_receipt
- sales_agreements
- business_licenses_permits

**HR Documents**:
- i_9_form
- w_4_form
- tax_forms_w_9_1099_941_1120

**Education Documents**:
- diploma_certification
- transcripts
- schooladmissonform

**Healthcare Documents**:
- patient_intake_form

**Legal Documents**:
- federal_law_cs
- management_quarterly_cs

**Other Documents**:
- order_request_form
- mortgage_lending_document
- utility_bill
- client_success_case_study
- customer_data_table
- customerinfo

## Configuration Reference

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `entities_column` | string | No | `"entities"` | Column containing extracted entities (dict) |
| `document_type_column` | string | No | `"document_type"` | Column containing document type identifier |

### Output Format

The operator outputs a single `transformed_entities` column containing a JSON string with nested structure matching the schema's target tables:

```python
# Input entities: {"invoice_number": "INV-001", "total_amount": "$1,234.56"}
# Output column (transformed_entities):
# {
#   "invoice_header": {
#     "invoice_number": "INV-001",
#     "total_amount": 1234.56,
#     "currency": "USD"
#   }
# }
```

For unknown document types (no schema available), the operator returns an empty dict `{}` in the `transformed_entities` column.

## Usage Examples

### Example 1: Invoice Processing with Schema

```python
from datasift.core.operators.functional.entity_curation import EntityCurationOperator
import pyarrow as pa

# Input table with extracted entities
input_table = pa.table({
    "id": ["doc1"],
    "document_type": ["invoice"],
    "entities": [{
        "invoice_number": "INV-001",
        "invoice_date": "March 15, 2024",
        "total_amount": "$1,234.56",
        "vendor_name": "Acme Corp"
    }]
})

config = {
    "entities_column": "entities",
    "document_type_column": "document_type"
}

operator = EntityCurationOperator(config)
tables, metadata = operator.transform(input_table)
result_table = tables[0]

# Output columns:
# - id: "doc1"
# - document_type: "invoice"
# - entities: {...}
# - transformed_entities: '{"invoice_header": {"invoice_number": "INV-001", "invoice_date": "2024-03-15", ...}}'
# - entity_total_amount: 1234.56
# - entity_currency: "USD"
# - entity_vendor_name: "Acme Corp"
```

### Example 2: Custom Document Type (No Schema)

```python
# Input table with custom document type
input_table = pa.table({
    "id": ["doc1"],
    "document_type": ["custom_form"],
    "entities": [{
        "field1": "value1",
        "field2": "value2",
        "amount": "$100.00"
    }]
})

config = {
    "entities_column": "entities",
    "document_type_column": "document_type"
}

operator = EntityCurationOperator(config)
tables, metadata = operator.transform(input_table)

# Output: transformed_entities column contains empty dict (no schema available)
# - transformed_entities: '{}'
```

### Example 3: Date Format Normalization

```python
input_table = pa.table({
    "id": ["doc1", "doc2", "doc3", "doc4"],
    "document_type": ["invoice", "invoice", "invoice", "invoice"],
    "entities": [
        {"invoice_date": "January 15, 2024"},  # Text format
        {"invoice_date": "01/15/2024"},        # US format
        {"invoice_date": "2024-01-15"},        # ISO format
        {"invoice_date": "20240115"}           # Compact format
    ]
})

operator = EntityCurationOperator(config)
tables, metadata = operator.transform(input_table)

# All dates normalized to: "2024-01-15"
```

## Error Handling

### Common Errors

#### Missing Entities Column

```
ValidationError: Required column 'entities' not found in input table
```

**Solution**: Ensure the input table has the specified entities column

#### Invalid Document Type

```
Warning: No schema found for document type 'unknown_type', using fallback processing
```

**Solution**: This is a warning, not an error. The operator will process entities without transformations.

#### Transformation Failure

```
Error: Failed to apply transformation 'amount_string_to_number' to field 'total_amount'
```

**Solution**: Check the input data format. The operator will log the error and continue processing other fields.

### Graceful Degradation

The operator handles errors gracefully:

1. **Missing Schema**: Falls back to flat structure without transformations
2. **Transformation Errors**: Logs error, keeps original value, continues processing
3. **Missing Fields**: Skips missing fields, processes available ones
4. **Invalid Data**: Logs warning, preserves original value

## Performance Considerations

### Memory Usage

- **Flat Format**: Lower memory overhead, recommended for large datasets
- **Nested Format**: Higher memory usage due to nested dictionaries

### Processing Speed

Transformation performance by function:

| Function | Speed | Notes |
|----------|-------|-------|
| identity | Fastest | No processing |
| amount_string_to_number | Fast | Regex-based |
| identify_currency_from_amount | Fast | Pattern matching |
| to_number | Medium | Multi-language parsing |
| currency_to_numeric | Medium | Babel library |
| make_date_uniform | Medium | Pattern matching + optional datefinder fallback |
| date_string_to_computer_date | Slow | Natural language processing with datefinder |
| weight_to_kilograms | Fast | Simple conversion |
| weight_to_numeric | Medium | Locale-aware parsing |

### Optimization Tips

1. **Use Flat Format**: Faster and more memory-efficient
2. **Minimize Date Transformations**: Date parsing is the slowest operation
3. **Batch Processing**: Process documents in batches for better throughput
4. **Schema Optimization**: Only define transformations for fields that need them

## Architecture

### Component Structure

```
entity_curation/
├── __init__.py                      # Package exports
├── entity_curation_operator.py      # Main operator class
├── schema_processor.py              # Schema loading and processing
├── transforms/                      # Transformation functions
│   ├── __init__.py                  # TRANSFORMS registry
│   ├── identity.py
│   ├── amount_string_to_number.py
│   ├── identify_currency_from_amount.py
│   ├── to_number.py
│   ├── currency_to_numeric.py
│   ├── make_date_uniform.py
│   ├── date_string_to_computer_date.py
│   ├── weight_to_kilograms.py
│   └── weight_to_numeric.py
└── README.md                        # This file
```

### Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│ Input: PyArrow Table                                         │
│   - id: Document ID                                          │
│   - document_type: Document class identifier                │
│   - entities: Dict of extracted entities                    │
│   - ... (other columns)                                     │
└─────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│ EntityCurationOperator                                       │
│   1. Load document class schema (if available)              │
│   2. For each row:                                          │
│      a. Get entities dict                                   │
│      b. Apply schema-based transformations                  │
│      c. Create curated output columns                       │
└─────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│ Output: PyArrow Table                                        │
│   - All input columns preserved                             │
│   - entity_* columns added (flat format)                    │
│     OR                                                       │
│   - curated_entities column added (nested format)           │
└─────────────────────────────────────────────────────────────┘
```

### Adding Custom Transformations

1. **Create Transformation Function** (in `transforms/`):

```python
def my_custom_transform(*, value: str, **kwargs) -> str:
    """
    Custom transformation function.
    
    Args:
        value: Input value to transform
        **kwargs: Additional arguments from schema
    
    Returns:
        Transformed value
    """
    # Implementation
    return transformed_value
```

2. **Register in TRANSFORMS** (in `transforms/__init__.py`):

```python
from .my_custom_transform import my_custom_transform

TRANSFORMS = {
    "identity": identity,
    # ... existing transforms ...
    "my_custom_transform": my_custom_transform,
}
```

3. **Use in Schema**:

```json
{
  "column_name": "my_field",
  "source": "entities",
  "field": "my_field",
  "transform": "my_custom_transform"
}
```

## Testing

### Prerequisites

```bash
cd src/datasift_opensource/backend
source .venv/bin/activate
export PYTHONPATH="$(cd ../../.. && pwd)/src/datasift_opensource/backend:${PYTHONPATH}"
```

### Unit Tests

```bash
# All entity curation tests
uv run pytest ../../../tests/unit/operators/functional/entity_curation/ -v

# Specific transformation function
uv run pytest ../../../tests/unit/operators/functional/entity_curation/test_transforms.py::test_amount_string_to_number -v

# Schema processor tests
uv run pytest ../../../tests/unit/operators/functional/entity_curation/test_schema_processor.py -v

# Operator tests
uv run pytest ../../../tests/unit/operators/functional/entity_curation/test_entity_curation_operator.py -v
```

### Integration Tests

```bash
# Full pipeline test (Ingest → Extract → ExtractEntities → Curate)
uv run pytest ../../../tests/integration/test_entity_curation_integration.py -v
```

### Flow Testing

```bash
# Run sample flow
datasift-orchestrator --flow-file sample_flows/entity_curation_example.json
```

## Dependencies

The operator requires the following Python packages:

- **babel** (>=2.14.0): Locale-aware currency and number parsing
- **datefinder** (>=0.7.3): Flexible date extraction from text

These are automatically installed with the datasift-opensource package.

## Troubleshooting

### Enable Debug Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Verify Schema Loading

```python
from datasift.utils.document_class_utils import DocumentClassUtils

# List available document classes
schemas = DocumentClassUtils.get_schema_templates()
print(f"Available schemas: {list(schemas.keys())}")

# Load specific schema
invoice_schema = schemas.get("invoice")
print(f"Invoice schema: {invoice_schema}")
```

### Test Transformation Functions

```python
from datasift.core.operators.functional.entity_curation.transforms import TRANSFORMS

# Test amount conversion
transform_fn = TRANSFORMS["amount_string_to_number"]
result = transform_fn(value="$1,234.56")
print(f"Result: {result}")  # 1234.56

# Test date parsing
transform_fn = TRANSFORMS["make_date_uniform"]
result = transform_fn(value="March 15, 2024")
print(f"Result: {result}")  # 2024-03-15
```
