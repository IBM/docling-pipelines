import json
import unittest
from unittest.mock import MagicMock, patch

import pyarrow as pa

from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.functional.entity_curation.entity_curation_operator import (
    EntityCurationOperator,
)


class TestEntityCurationOperator(unittest.TestCase):
    """Test EntityCurationOperator functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.config = {
            "entities_column": "entities",
            "document_type_column": "document_type",
        }

    def test_init_default_config(self):
        """Test operator initialization with default configuration"""
        operator = EntityCurationOperator(config={})

        self.assertEqual(operator.entities_column, "entities")
        self.assertEqual(operator.document_type_column, "document_type")

    def test_init_custom_config(self):
        """Test operator initialization with custom configuration"""
        config = {
            "entities_column": "custom_entities",
            "document_type_column": "doc_class",
        }
        operator = EntityCurationOperator(config=config)

        self.assertEqual(operator.entities_column, "custom_entities")
        self.assertEqual(operator.document_type_column, "doc_class")

    def test_validate_success(self):
        """Test validation with valid configuration"""
        operator = EntityCurationOperator(config=self.config)
        errors = []
        warnings = []
        available_features = ["entities", "document_type", "id", "name"]

        operator.validate(errors=errors, warnings=warnings, available_features=available_features)

        self.assertEqual(len(errors), 0)
        self.assertEqual(len(warnings), 0)

    def test_validate_missing_entities_column(self):
        """Test validation with missing entities column"""
        operator = EntityCurationOperator(config=self.config)
        errors = []
        warnings = []
        available_features = ["document_type", "id", "name"]  # Missing entities

        operator.validate(errors=errors, warnings=warnings, available_features=available_features)

        self.assertGreater(len(errors), 0)
        self.assertTrue(any("entities" in str(e).lower() for e in errors))

    def test_validate_missing_document_type_column(self):
        """Test validation with missing document_type column"""
        operator = EntityCurationOperator(config=self.config)
        errors = []
        warnings = []
        available_features = ["entities", "id", "name"]  # Missing document_type

        operator.validate(errors=errors, warnings=warnings, available_features=available_features)

        self.assertGreater(len(errors), 0)
        self.assertTrue(any("document_type" in str(e).lower() for e in errors))

    def test_get_metadata(self):
        """Test metadata retrieval"""
        operator = EntityCurationOperator(config=self.config)
        metadata = operator.get_metadata()

        self.assertIsInstance(metadata, dict)
        self.assertIn("short_name", metadata)
        self.assertEqual(metadata["short_name"], "entity_curation")
        self.assertIn("category", metadata)

    @patch("docpipe.core.operators.functional.entity_curation.entity_curation_operator.SchemaProcessor")
    def test_transform_with_schema(self, mock_schema_processor_class):
        """Test transform with schema-based processing"""
        # Mock schema processor
        mock_processor = MagicMock()
        mock_processor.process_with_schema.return_value = {
            "invoice_header": {"invoice_number": "INV-001", "total_amount": 1234.56}
        }
        mock_schema_processor_class.return_value = mock_processor

        # Create input table
        input_table = pa.table(
            {
                "id": ["doc1"],
                "name": ["invoice.pdf"],
                "document_type": ["invoice"],
                "entities": [{"invoice_number": "INV-001", "total_amount": "$1,234.56"}],
            }
        )

        operator = EntityCurationOperator(config=self.config)
        result_tables, _metadata = operator.transform(table=input_table, file_name="test_flow.json")

        self.assertEqual(len(result_tables), 1)
        result_table = result_tables[0]
        self.assertGreater(result_table.num_rows, 0)

        # Verify transformed_entities column exists and contains JSON
        transformed_col = OperatorConstants.Columns.TRANSFORMED_ENTITIES_COLUMN_NAME
        self.assertIn(transformed_col, result_table.column_names)

        transformed_json = result_table[transformed_col][0].as_py()
        self.assertIsNotNone(transformed_json)
        transformed_data = json.loads(transformed_json)
        self.assertIsInstance(transformed_data, dict)

    @patch("docpipe.core.operators.functional.entity_curation.entity_curation_operator.SchemaProcessor")
    def test_transform_without_schema(self, mock_schema_processor_class):
        """Test transform without schema (returns empty dict)"""
        # Mock schema processor - returns empty dict for unknown types
        mock_processor = MagicMock()
        mock_processor.process_with_schema.return_value = {}
        mock_schema_processor_class.return_value = mock_processor

        # Create input table with unknown document type
        input_table = pa.table(
            {
                "id": ["doc1"],
                "name": ["document.pdf"],
                "document_type": ["unknown_type"],
                "entities": [{"field1": "value1", "field2": "value2"}],
            }
        )

        operator = EntityCurationOperator(config=self.config)
        result_tables, _metadata = operator.transform(table=input_table, file_name="test_flow.json")

        self.assertEqual(len(result_tables), 1)
        result_table = result_tables[0]
        self.assertGreater(result_table.num_rows, 0)

        # Verify transformed_entities column contains empty dict as JSON
        transformed_col = OperatorConstants.Columns.TRANSFORMED_ENTITIES_COLUMN_NAME
        self.assertIn(transformed_col, result_table.column_names)

        transformed_json = result_table[transformed_col][0].as_py()
        self.assertIsNotNone(transformed_json)
        transformed_data = json.loads(transformed_json)
        self.assertEqual(transformed_data, {})

    def test_transform_empty_table(self):
        """Test transform with empty input table"""
        # Create empty table with correct schema
        input_table = pa.table(
            {
                "id": pa.array([], type=pa.string()),
                "name": pa.array([], type=pa.string()),
                "document_type": pa.array([], type=pa.string()),
                "entities": pa.array([], type=pa.string()),  # Will be converted to dict
            }
        )

        operator = EntityCurationOperator(config=self.config)
        result_tables, _metadata = operator.transform(table=input_table, file_name="test_flow.json")

        self.assertEqual(len(result_tables), 1)
        result_table = result_tables[0]
        self.assertEqual(result_table.num_rows, 0)


if __name__ == "__main__":
    unittest.main()
