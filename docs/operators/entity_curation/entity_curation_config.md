# Entity Curation Operator - Configuration Reference

## Overview

The Entity Curation Operator transforms extracted entities into structured, curated data based on document class schemas. It applies field-specific transformations (currency conversion, date normalization, number parsing, etc.) to prepare entities for downstream processing and storage.

- **Operator Name:** `entity_curation`
- **Category**: Functional
- **Short Name**: `entity_curation`

## Features

- Schema-based entity transformation using document class definitions
- 4 built-in transformation functions for common data types
- Multi-language support for dates, numbers, and currencies
- Locale-aware parsing with Babel library
- JSON output format with nested structure matching schema's target tables
- Support for custom document types without schemas (returns empty dict)

## Configuration Parameters

### 1. `entities_column` (String)
**Type:** String  
**Required:** No  
**Default:** `"entities"`  
**Description:** Column containing extracted entities (dict or JSON string).  

**Sample Data Structure for entities:**
```python
# The entities_column should contain a dict or JSON string with extracted key-value pairs:
{
    "invoice_number": "INV-001",
    "invoice_date": "March 15, 2024",
    "total_amount": "$1,234.56",
    "vendor_name": "Acme Corp"
}
```

### 2. `document_type_column` (String)
**Type:** String  
**Required:** No  
**Default:** `"document_type"`  
**Description:** Column containing document type identifier for schema lookup.  

**Sample Data Structure for document_type:**
```python
# The document_type_column should contain a string identifier matching a schema:
"invoice"           # Financial document
"purchase_order"    # Business document
"driver_license"    # Identity document
"passport"          # Identity document
```

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

**Example:**
```python
# Input with unknown document type
input_table = pa.table({
    "id": ["doc1"],
    "document_type": ["custom_form"],  # No schema available
    "entities": [{"field1": "value1", "amount": "$100.00"}]
})

# Output: transformed_entities column contains empty dict
# - transformed_entities: '{}'
```

## Usage Examples

### Example 1: Invoice Processing with Schema

```python
from docpipe.core.operators.functional.entity_curation import EntityCurationOperator
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

**Solution**: This is a warning, not an error. The operator will return an empty dict `{}` in the `transformed_entities` column.

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

## Performance Tips

1. **Schema Optimization**: Only define transformations for fields that need them
2. **Batch Processing**: Process documents in batches for better throughput
3. **Minimize Complex Transformations**: Date parsing with datefinder is slower than simple pattern matching

## Complete Flow Example

- [Entity Curation Flow with Classification](../../../sample_flows/operators/entity_curation_ollama.json) - Demonstrates document classification, entity extraction, and entity curation using Ollama
