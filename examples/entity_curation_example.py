#!/usr/bin/env python3
"""
Example: Entity Curation

This example demonstrates how to curate and transform extracted entities from documents
using the Entity Curation operator. The operator applies schema-based transformations
to normalize entity data (currency, dates, weights, etc.) based on document class schemas.

Supports 40+ document classes including invoices, purchase orders, receipts, and more.
"""

import json
import sys
from pathlib import Path
from typing import Any

import pyarrow as pa

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.functional.entity_curation.entity_curation_operator import (
    EntityCurationOperator,
)
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger()


def create_sample_entities() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Create sample entity data for testing."""
    invoice_entities: dict[str, Any] = {
        "invoice_number": "INV-2024-001",
        "invoice_date": "January 15, 2024",
        "total_amount": "$1,234.56",
        "currency": "USD",
        "vendor_name": "Acme Corporation",
        "vendor_address": "123 Main St, City, State 12345",
        "line_items": [
            {
                "description": "Product A",
                "quantity": "10",
                "unit_price": "$50.00",
                "total": "$500.00",
            },
            {
                "description": "Product B",
                "quantity": "5",
                "unit_price": "$146.91",
                "total": "$734.56",
            },
        ],
    }

    po_entities: dict[str, Any] = {
        "po_number": "PO-2024-100",
        "po_date": "2024-02-20",
        "total_amount": "€5,678.90",
        "currency": "EUR",
        "buyer_name": "Tech Solutions Inc",
        "supplier_name": "Parts Supplier Ltd",
        "delivery_date": "March 15, 2024",
        "items": [
            {
                "item_code": "PART-001",
                "description": "Component X",
                "quantity": "100",
                "unit_price": "€25.50",
                "total": "€2,550.00",
            },
            {
                "item_code": "PART-002",
                "description": "Component Y",
                "quantity": "50",
                "unit_price": "€62.58",
                "total": "€3,128.90",
            },
        ],
    }

    receipt_entities: dict[str, Any] = {
        "receipt_number": "REC-2024-050",
        "receipt_date": "2024-03-10",
        "amount": "¥15,000",
        "currency": "JPY",
        "merchant": "Tokyo Electronics",
        "items": [
            {"product": "Laptop", "weight": "2.5 kg", "price": "¥12,000"},
            {"product": "Mouse", "weight": "100 g", "price": "¥3,000"},
        ],
    }

    custom_entities: dict[str, Any] = {
        "field1": "value1",
        "field2": "123.45",
        "field3": "2024-03-01",
        "nested": {"subfield1": "nested_value", "subfield2": "456"},
    }

    return invoice_entities, po_entities, receipt_entities, custom_entities


def display_document_results(*, output_table: pa.Table, document_type_column: str) -> None:
    """Display curated entities for each document."""
    logger.info(f"\n{'=' * 80}")
    logger.info("Curated Entities for All Documents:")
    logger.info(f"{'=' * 80}\n")

    transformed_col = OperatorConstants.Columns.TRANSFORMED_ENTITIES_COLUMN_NAME

    for i in range(output_table.num_rows):
        doc_name = output_table[OperatorConstants.Columns.NAME][i].as_py()
        doc_type = output_table[document_type_column][i].as_py()
        logger.info(f"Document {i + 1}: {doc_name} (Type: {doc_type})")
        logger.info("-" * 60)

        # Display transformed entities JSON
        transformed_json = output_table[transformed_col][i].as_py()
        if transformed_json:
            transformed_data = json.loads(transformed_json)
            logger.info(f"  {transformed_col}:")
            logger.info(f"    {json.dumps(transformed_data, indent=6)}")
        else:
            logger.info(f"  {transformed_col}: None")

        logger.info("")


def _log_value(*, col: str, value: Any) -> None:
    """Log a single value with appropriate formatting."""
    if isinstance(value, dict):
        logger.info(f"  {col}:")
        for key, val in value.items():
            formatted_val = f"{val:.2f}" if isinstance(val, float) else val
            logger.info(f"    {key}: {formatted_val}")
    elif isinstance(value, list):
        logger.info(f"  {col}: [{len(value)} items]")
        if value and isinstance(value[0], dict):
            logger.info(f"    Example item: {value[0]}")
    elif isinstance(value, float):
        logger.info(f"  {col}: {value:.2f}")
    else:
        logger.info(f"  {col}: {value}")


def display_transformation_examples() -> None:
    """Display examples of transformations."""
    logger.info(f"\n{'=' * 80}")
    logger.info("Transformation Examples:")
    logger.info(f"{'=' * 80}\n")

    logger.info("Currency Transformations:")
    logger.info("  '$1,234.56' → 1234.56 (numeric)")
    logger.info("  '€5,678.90' → 5678.90 (numeric)")
    logger.info("  '¥15,000' → 15000.00 (numeric)")

    logger.info("\nDate Transformations:")
    logger.info("  'January 15, 2024' → '2024-01-15' (ISO format)")
    logger.info("  'March 15, 2024' → '2024-03-15' (ISO format)")

    logger.info("\nWeight Transformations:")
    logger.info("  '2.5 kg' → 2.5 (numeric in kg)")
    logger.info("  '100 g' → 0.1 (converted to kg)")

    logger.info("\nSupported Document Classes:")
    logger.info("  - invoice, purchase_order, receipt")
    logger.info("  - bill_of_lading, customs_form, delivery_receipt")
    logger.info("  - insurance_claim, mortgage_lending_document")
    logger.info("  - driver_license, passport, national_id_card")
    logger.info("  - And 30+ more document classes")

    logger.info("\nFor unknown document types, the operator returns empty dict")
    logger.info("as no schema-based transformations can be applied.")


def main() -> int:
    """Main function to test the Entity Curation operator."""
    # Configuration
    entities_column: str = "entities"
    document_type_column: str = "document_type"

    # Create sample data
    invoice_entities, po_entities, receipt_entities, custom_entities = create_sample_entities()

    data: dict[str, list[Any]] = {
        OperatorConstants.Columns.ID: ["doc1", "doc2", "doc3", "doc4"],
        OperatorConstants.Columns.NAME: [
            "invoice_001.pdf",
            "po_100.pdf",
            "receipt_050.pdf",
            "custom_doc.pdf",
        ],
        document_type_column: ["invoice", "purchase_order", "receipt", "custom_type"],
        entities_column: [
            invoice_entities,
            po_entities,
            receipt_entities,
            custom_entities,
        ],
    }

    input_table: pa.Table = pa.table(data)
    logger.info(f"\nInput PyArrow Table:\n{input_table}\n")
    logger.info(f"Input has {input_table.num_rows} documents to process")

    # Configure and run operator
    config: dict[str, Any] = {
        "entities_column": entities_column,
        "document_type_column": document_type_column,
    }

    operator: EntityCurationOperator = EntityCurationOperator(config=config)
    logger.info("\nOperator Configuration:")
    logger.info(f"  Entities column: {entities_column}")
    logger.info(f"  Document type column: {document_type_column}")
    logger.info(f"\nOperator: {operator}")

    # Transform
    output_tables, metadata = operator.transform(table=input_table, file_name="entity_curation_example.json")

    # Display results
    output_table = output_tables[0]
    logger.info(f"\nOutput Table Shape: {output_table.num_rows} rows x {output_table.num_columns} columns")
    logger.info(f"Output Columns: {output_table.column_names}")
    logger.info(f"\nMetadata: {json.dumps(metadata, indent=2)}")

    # Log the complete PyArrow table
    logger.info(f"\n{'=' * 80}")
    logger.info("Complete Output PyArrow Table:")
    logger.info(f"{'=' * 80}")
    logger.info(f"\n{output_table}")
    logger.info(f"\n{'=' * 80}")

    display_document_results(
        output_table=output_table,
        document_type_column=document_type_column,
    )
    display_transformation_examples()

    return 0


if __name__ == "__main__":
    sys.exit(main())
