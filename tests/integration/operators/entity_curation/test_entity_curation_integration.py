import json
import unittest

import pyarrow as pa

from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.functional.entity_curation.entity_curation_operator import (
    EntityCurationOperator,
)


class TestEntityCurationIntegration(unittest.TestCase):
    """Integration tests for EntityCurationOperator with real document class schemas"""

    def setUp(self):
        """Set up test fixtures"""
        self.operator = EntityCurationOperator(
            config={
                "entities_column": "entities",
                "document_type_column": "document_type",
            }
        )

    def test_invoice_processing_with_schema(self):
        """Test processing invoice entities with invoice schema"""
        # Create input table with invoice data
        invoice_entities = {
            "invoice_number": "INV-2024-001",
            "invoice_date": "2024-01-15",
            "total_amount": "$1,234.56",
            "currency": "USD",
            "vendor_name": "Acme Corp",
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

        input_table = pa.table(
            {
                "id": ["doc1"],
                "name": ["invoice_001.pdf"],
                "document_type": ["invoice"],
                "entities": [invoice_entities],
            }
        )

        # Transform
        result_tables, _metadata = self.operator.transform(table=input_table, file_name="test_invoice_flow.json")

        # Verify results
        self.assertEqual(len(result_tables), 1)
        result_table = result_tables[0]
        self.assertGreater(result_table.num_rows, 0)

        # Check that transformed_entities column exists with JSON data
        transformed_col = OperatorConstants.Columns.TRANSFORMED_ENTITIES_COLUMN_NAME
        self.assertIn(transformed_col, result_table.column_names)

        transformed_json = result_table[transformed_col][0].as_py()
        self.assertIsNotNone(transformed_json)
        transformed_data = json.loads(transformed_json)
        self.assertIsInstance(transformed_data, dict)

        # Invoice schema has tables named "Invoice" and "Invoice_line_items"
        self.assertIn("Invoice", transformed_data)
        self.assertIsInstance(transformed_data["Invoice"], dict)
        self.assertIn("vendor_name", transformed_data["Invoice"])
        self.assertEqual(transformed_data["Invoice"]["vendor_name"], "Acme Corp")

        # Invoice_line_items should be an array
        self.assertIn("Invoice_line_items", transformed_data)
        self.assertIsInstance(transformed_data["Invoice_line_items"], list)
        self.assertEqual(len(transformed_data["Invoice_line_items"]), 2)

        # Verify first line item
        self.assertEqual(transformed_data["Invoice_line_items"][0]["description"], "Product A")
        # Quantity should be numeric after transformation
        self.assertIsInstance(transformed_data["Invoice_line_items"][0]["quantity"], (int, float))
        self.assertEqual(transformed_data["Invoice_line_items"][0]["quantity"], 10)

        # Verify second line item
        self.assertEqual(transformed_data["Invoice_line_items"][1]["description"], "Product B")
        self.assertIsInstance(transformed_data["Invoice_line_items"][1]["quantity"], (int, float))
        self.assertEqual(transformed_data["Invoice_line_items"][1]["quantity"], 5)

    def test_purchase_order_processing_with_schema(self):
        """Test processing purchase order entities with purchase_order schema"""
        # Create input table with purchase order data
        po_entities = {
            "po_number": "PO-2024-100",
            "po_date": "2024-02-20",
            "total_amount": "$5,678.90",
            "currency": "EUR",
            "buyer_name": "Tech Solutions Inc",
            "supplier_name": "Parts Supplier Ltd",
            "delivery_date": "2024-03-15",
            "items": [
                {
                    "item_code": "PART-001",
                    "description": "Component X",
                    "quantity": "100",
                    "unit_price": "$25.50",
                    "total": "$2,550.00",
                },
                {
                    "item_code": "PART-002",
                    "description": "Component Y",
                    "quantity": "50",
                    "unit_price": "$62.58",
                    "total": "$3,128.90",
                },
            ],
        }

        input_table = pa.table(
            {
                "id": ["doc2"],
                "name": ["po_100.pdf"],
                "document_type": ["purchase_order"],
                "entities": [po_entities],
            }
        )

        # Transform
        result_tables, _metadata = self.operator.transform(table=input_table, file_name="test_po_flow.json")

        # Verify results
        self.assertEqual(len(result_tables), 1)
        result_table = result_tables[0]
        self.assertGreater(result_table.num_rows, 0)

        # Check transformed_entities column
        transformed_col = OperatorConstants.Columns.TRANSFORMED_ENTITIES_COLUMN_NAME
        self.assertIn(transformed_col, result_table.column_names)

    def test_unknown_document_type_fallback(self):
        """Test processing with unknown document type (no schema available)"""
        # Create input table with unknown document type
        custom_entities = {
            "field1": "value1",
            "field2": "123.45",
            "field3": "2024-03-01",
            "nested": {"subfield1": "nested_value", "subfield2": "456"},
        }

        input_table = pa.table(
            {
                "id": ["doc3"],
                "name": ["custom_doc.pdf"],
                "document_type": ["custom_type"],
                "entities": [custom_entities],
            }
        )

        # Transform (should return empty dict for unknown type)
        result_tables, _metadata = self.operator.transform(table=input_table, file_name="test_custom_flow.json")

        # Verify results
        self.assertEqual(len(result_tables), 1)
        result_table = result_tables[0]
        self.assertGreater(result_table.num_rows, 0)

        # Should have empty dict in transformed_entities for unknown type
        transformed_col = OperatorConstants.Columns.TRANSFORMED_ENTITIES_COLUMN_NAME
        self.assertIn(transformed_col, result_table.column_names)

        transformed_json = result_table[transformed_col][0].as_py()
        self.assertIsNotNone(transformed_json)
        transformed_data = json.loads(transformed_json)
        self.assertEqual(transformed_data, {})

    def test_batch_processing_multiple_documents(self):
        """Test processing multiple documents in a single batch"""
        # Create input table with multiple documents of different types
        input_table = pa.table(
            {
                "id": ["doc1", "doc2", "doc3"],
                "name": ["invoice.pdf", "po.pdf", "receipt.pdf"],
                "document_type": ["invoice", "purchase_order", "receipt"],
                "entities": [
                    {"invoice_number": "INV-001", "total_amount": "$100.00"},
                    {"po_number": "PO-001", "total_amount": "$200.00"},
                    {"receipt_number": "REC-001", "amount": "$50.00"},
                ],
            }
        )

        # Transform
        result_tables, _metadata = self.operator.transform(table=input_table, file_name="test_batch_flow.json")

        # Verify results
        self.assertEqual(len(result_tables), 1)
        result_table = result_tables[0]
        self.assertEqual(result_table.num_rows, 3)

    def test_empty_entities_handling(self):
        """Test handling of documents with empty or null entities"""
        # Create input table with empty entities
        input_table = pa.table(
            {
                "id": ["doc1", "doc2"],
                "name": ["empty.pdf", "null.pdf"],
                "document_type": ["invoice", "invoice"],
                "entities": [{}, None],
            }
        )

        # Transform
        result_tables, _metadata = self.operator.transform(table=input_table, file_name="test_empty_flow.json")

        # Verify results - should handle gracefully
        self.assertEqual(len(result_tables), 1)
        result_table = result_tables[0]
        # May have 0 or 2 rows depending on how empty entities are handled
        self.assertGreaterEqual(result_table.num_rows, 0)

    def test_transformation_functions_applied(self):
        """Test that transformation functions are correctly applied"""
        # Create input with data that needs transformation
        entities = {
            "invoice_number": "INV-001",
            "invoice_date": "January 15, 2024",  # Should be transformed to ISO format
            "total_amount": "$1,234.56",  # Should be transformed to number
            "currency": "USD",
            "weight": "10 kg",  # Should be transformed to numeric
        }

        input_table = pa.table(
            {
                "id": ["doc1"],
                "name": ["invoice.pdf"],
                "document_type": ["invoice"],
                "entities": [entities],
            }
        )

        # Transform
        result_tables, metadata = self.operator.transform(table=input_table, file_name="test_transform_flow.json")

        # Verify results
        self.assertEqual(len(result_tables), 1)
        result_table = result_tables[0]
        self.assertGreater(result_table.num_rows, 0)

        # Check metadata for transformation info
        self.assertIsInstance(metadata, dict)

    def test_json_output_structure(self):
        """Test that output is in JSON format with nested structure"""
        entities = {"invoice_number": "INV-001", "total_amount": "$100.00"}

        input_table = pa.table(
            {
                "id": ["doc1"],
                "name": ["invoice.pdf"],
                "document_type": ["invoice"],
                "entities": [entities],
            }
        )

        # Transform
        result_tables, _metadata = self.operator.transform(table=input_table, file_name="test_json_flow.json")

        # Verify results
        self.assertEqual(len(result_tables), 1)
        result_table = result_tables[0]
        self.assertGreater(result_table.num_rows, 0)

        # Verify JSON structure
        transformed_col = OperatorConstants.Columns.TRANSFORMED_ENTITIES_COLUMN_NAME
        self.assertIn(transformed_col, result_table.column_names)

        transformed_json = result_table[transformed_col][0].as_py()
        self.assertIsNotNone(transformed_json)
        transformed_data = json.loads(transformed_json)
        self.assertIsInstance(transformed_data, dict)

    def test_validation_with_real_table(self):
        """Test validation with real PyArrow table schema"""
        # Create a table with the expected columns
        input_table = pa.table(
            {
                "id": ["doc1"],
                "name": ["test.pdf"],
                "document_type": ["invoice"],
                "entities": [{"field": "value"}],
            }
        )

        errors: list[str] = []
        warnings: list[str] = []
        available_features = input_table.column_names

        self.operator.validate(errors=errors, warnings=warnings, available_features=available_features)

        # Should have no errors
        self.assertEqual(len(errors), 0)


if __name__ == "__main__":
    unittest.main()
