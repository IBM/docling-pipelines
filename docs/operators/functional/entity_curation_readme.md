# EntityCurationOperator

Transforms extracted entities into curated, type-normalised data using document class schemas.

- **Short Name:** `entity_curation`
- **Category:** Functional

---

## Overview

`EntityCurationOperator` takes the raw key-value pairs produced by the Extract operator and
applies schema-driven field filtering and type transformations — currency conversion, date
normalisation, number parsing, and weight conversion — to produce a clean, structured
`transformed_entities` column ready for downstream storage or search indexing.

Documents whose type has no registered schema pass through with an empty `{}` in
`transformed_entities`; the operator never discards a row.

---

## Key Features

- Schema-based field filtering — only schema-defined fields are retained
- 4 built-in type transformations: `currency_to_numeric`, `make_date_uniform`, `to_number`, `weight_to_numeric`
- Locale-aware parsing via Babel (currency, weight)
- Multi-language number parsing (English, Chinese, Japanese, Korean, Spanish, French, German, Portuguese, Italian, Russian)
- Date normalisation to ISO 8601 (`YYYY-MM-DD`) with `datefinder` fallback
- Graceful degradation — transformation failures log a warning and preserve the original value
- 40+ pre-defined document class schemas bundled with the operator

---

## Operator Configuration

```json
{
  "type": "entity_curation",
  "name": "curate_entities",
  "config": {
    "entities_column": "entities",
    "document_type_column": "document_type"
  },
  "depends_on": ["extract_documents"]
}
```

---

## Parameters

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `entities_column` | string | No | `"entities"` | Column containing extracted entities (dict or JSON string) |
| `document_type_column` | string | No | `"document_type"` | Column containing the document type identifier for schema lookup |

---

## Output Columns

The operator appends one column to the input table; all original columns are preserved.

| Column | PyArrow Type | Description |
|---|---|---|
| `transformed_entities` | `string` | JSON string containing curated entities structured per the document class schema, or `"{}"` when no schema exists for the document type |

---

## Examples

### Example 1 — Invoice with full schema

```json
{
  "type": "entity_curation",
  "name": "curate_invoice_entities",
  "config": {
    "entities_column": "entities",
    "document_type_column": "document_type"
  },
  "depends_on": ["extract_invoice"]
}
```

Input `entities` value:
```json
{
  "invoice_number": "INV-001",
  "invoice_date": "March 15, 2024",
  "total_amount": "$1,234.56",
  "vendor_name": "Acme Corp"
}
```

Output `transformed_entities` value:
```json
{
  "invoice_header": {
    "invoice_number": "INV-001",
    "invoice_date": "2024-03-15",
    "total_amount": 1234.56,
    "currency": "USD",
    "vendor_name": "Acme Corp"
  }
}
```

### Example 2 — Unknown document type (no schema)

```json
{
  "type": "entity_curation",
  "name": "curate_entities",
  "config": {},
  "depends_on": ["extract_custom"]
}
```

When `document_type` has no matching schema, `transformed_entities` is `"{}"`.  
No error is raised; a warning is logged.

### Example 3 — Custom column names

```json
{
  "type": "entity_curation",
  "name": "curate_entities",
  "config": {
    "entities_column": "raw_kvp",
    "document_type_column": "doc_class"
  },
  "depends_on": ["extract_step"]
}
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ValidationError: Required column 'entities' not found` | Input table is missing the entities column | Set `entities_column` to the correct column name, or ensure the Extract operator runs first |
| `transformed_entities` is always `"{}"` | `document_type` does not match any bundled schema | Check the value in `document_type_column` against the list of supported document classes below |
| `Error: Failed to apply transformation … to field …` | Input value is in an unexpected format (e.g. currency string in a date field) | Review the schema mapping; the error is non-fatal and the original value is preserved |
| Dates not normalised to `YYYY-MM-DD` | Date string is in an unusual locale or format that `datefinder` cannot parse | Pre-process dates with a dedicated normalisation step before this operator |

### Supported document classes (40+)

**Financial:** `invoice`, `purchase_order`, `receipt`, `bank_statements`, `credit_card_statements`, `financial_statement`, `expense_reports`, `remittance_payment_advice`

**Insurance:** `acord_insurance_form`, `insurance_claim`, `claimant_s_statement`, `life_insurance_authorization_form`

**Identity:** `driver_license`, `passport`, `national_id_card`

**Business:** `bill_of_lading`, `customs_form`, `delivery_receipt`, `sales_agreements`, `business_licenses_permits`

**HR:** `i_9_form`, `w_4_form`, `tax_forms_w_9_1099_941_1120`

**Education:** `diploma_certification`, `transcripts`, `schooladmissonform`

**Healthcare:** `patient_intake_form`

**Legal:** `federal_law_cs`, `management_quarterly_cs`

**Other:** `order_request_form`, `mortgage_lending_document`, `utility_bill`, `client_success_case_study`, `customer_data_table`, `customerinfo`

---

## Architecture

### Transformation functions

| Function | Purpose | Example input → output |
|---|---|---|
| `currency_to_numeric` | Locale-aware currency parsing via Babel | `"$1,234.56"` → `1234.56` |
| `make_date_uniform` | Normalise dates to `YYYY-MM-DD`; `datefinder` used as fallback | `"March 15, 2024"` → `"2024-03-15"` |
| `to_number` | Multi-language number word parsing | `"一千二百三十四"` → `1234` |
| `weight_to_numeric` | Locale-aware weight conversion | `"5斤"` (zh_CN) → `2.5` (kg) |

### Schema structure

Document class schemas are JSON files that map entity fields to target table columns:

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
        }
      ]
    }
  ]
}
```

### Typical pipeline position

```
Ingest → Extract (entity_extraction enabled) → EntityCuration → Embeddings → VectorDB
```

### Sample flow

See [`sample_flows/operators/entity_curation_ollama.json`](../../../sample_flows/operators/entity_curation_ollama.json).
