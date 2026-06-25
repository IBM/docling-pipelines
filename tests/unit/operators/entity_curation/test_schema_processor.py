import unittest
from unittest.mock import MagicMock, patch

from docpipe.core.operators.functional.entity_curation.schema_processor import SchemaProcessor


class TestSchemaProcessor(unittest.TestCase):
    """Test SchemaProcessor functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.processor = SchemaProcessor()

    @patch("builtins.open", create=True)
    @patch("docpipe.core.operators.functional.entity_curation.schema_processor.Path")
    def test_load_schemas_success(self, mock_path, mock_open):
        """Test successful schema loading"""
        import json
        from unittest.mock import MagicMock
        from unittest.mock import mock_open as mock_open_func

        # Mock schema data
        mock_schema_data = {
            "document_class_schema": {
                "document": {},
                "target_tables": [
                    {
                        "name": "invoice_header",
                        "columns": [
                            {
                                "name": "invoice_number",
                                "source": {"field": ["invoice_number"]},
                            }
                        ],
                    }
                ],
            }
        }

        # Mock file operations
        mock_file = mock_open_func(read_data=json.dumps(mock_schema_data))
        mock_open.return_value = mock_file.return_value

        # Mock Path operations
        mock_path_instance = MagicMock()
        mock_path.return_value = mock_path_instance
        mock_path_instance.__truediv__.return_value = mock_path_instance

        self.processor.load_schemas(document_types=["invoice"])

        # Verify schema was loaded into cache
        self.assertIn("invoice", self.processor.schema_cache)
        self.assertIn("target_tables", self.processor.schema_cache["invoice"])

    def test_process_with_schema_no_transform(self):
        """Test processing with no transformation (passthrough)"""
        # Mock schema
        self.processor.schema_cache = {
            "invoice": {
                "target_tables": [
                    {
                        "name": "invoice_header",
                        "columns": [
                            {
                                "name": "invoice_number",
                                "source": {"field": ["invoice_number"]},
                            }
                        ],
                    }
                ]
            }
        }

        entities = {"invoice_number": "INV-001"}
        result = self.processor.process_with_schema(entities=entities, document_type="invoice")

        self.assertIsNotNone(result)
        self.assertIn("invoice_header", result)
        self.assertEqual(result["invoice_header"]["invoice_number"], "INV-001")

    def test_process_with_schema_missing_field(self):
        """Test processing when entity field is missing"""
        self.processor.schema_cache = {
            "invoice": {
                "target_tables": [
                    {
                        "name": "invoice_header",
                        "columns": [
                            {
                                "name": "invoice_number",
                                "source": {"field": ["invoice_number"]},
                            }
                        ],
                    }
                ]
            }
        }

        entities = {}  # Missing invoice_number
        result = self.processor.process_with_schema(entities=entities, document_type="invoice")

        # Should still return structure but with None value
        self.assertIsNotNone(result)
        self.assertIn("invoice_header", result)

    def test_process_unknown_document_type(self):
        """Test processing with unknown document type returns empty dict"""
        entities = {
            "field1": "value1",
            "field2": "value2",
            "nested": {"inner": "value3"},
        }

        result = self.processor.process_with_schema(entities=entities, document_type="unknown_type")

        # Should return empty dict for unknown document types
        self.assertIsNotNone(result)
        self.assertEqual(result, {})

    def test_process_empty_document_type(self):
        """Test processing with empty document type returns empty dict"""
        entities = {"field1": "value1"}

        result = self.processor.process_with_schema(entities=entities, document_type="")

        # Should return empty dict when document_type is empty
        self.assertIsNotNone(result)
        self.assertEqual(result, {})

    @patch("docpipe.core.operators.functional.entity_curation.schema_processor.TRANSFORMS")
    def test_apply_transformation_success(self, mock_transforms):
        """Test successful transformation application"""
        mock_transform_fn = MagicMock(return_value="transformed_value")
        mock_transforms.get.return_value = mock_transform_fn

        entities = {"field1": "original_value"}
        # Arguments should be list of dicts with arg_name and arg_value
        arguments = [{"arg_name": "input", "arg_value": {"field": "field1"}}]
        result = self.processor._apply_transformation(
            transform_name="test_transform", arguments=arguments, entities=entities
        )

        self.assertEqual(result, "transformed_value")
        mock_transform_fn.assert_called_once()

    def test_apply_transformation_unknown_transform(self):
        """Test transformation with unknown transform name"""
        entities = {"field1": "value"}
        arguments = [{"arg_name": "input", "arg_value": {"field": "field1"}}]
        result = self.processor._apply_transformation(
            transform_name="unknown_transform", arguments=arguments, entities=entities
        )

        # Should return None for unknown transforms
        self.assertIsNone(result)

    def test_get_nested_value_simple(self):
        """Test getting simple nested value"""
        entities = {"field1": "value1"}
        result = self.processor._get_nested_value(obj=entities, path=["field1"])

        self.assertEqual(result, "value1")

    def test_get_nested_value_nested(self):
        """Test getting deeply nested value"""
        entities = {"level1": {"level2": {"level3": "deep_value"}}}
        result = self.processor._get_nested_value(obj=entities, path=["level1", "level2", "level3"])

        self.assertEqual(result, "deep_value")

    def test_get_nested_value_missing(self):
        """Test getting missing nested value"""
        entities = {"field1": "value1"}
        result = self.processor._get_nested_value(obj=entities, path=["missing", "field"])

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
