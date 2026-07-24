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

        entities: dict[str, str] = {}  # Missing invoice_number
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
        # Field paths must be lists for _get_nested_value
        arguments = [{"name": "input", "value": {"field": ["field1"]}}]
        result = self.processor._apply_transformation(
            transform_name="test_transform", arguments=arguments, entities=entities
        )

        self.assertEqual(result, "transformed_value")
        mock_transform_fn.assert_called_once_with(input="original_value")

    def test_apply_transformation_unknown_transform(self):
        """Test transformation with unknown transform name"""
        entities = {"field1": "value"}
        # Use correct constant keys and field as list
        arguments = [{"name": "input", "value": {"field": ["field1"]}}]
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

    def test_process_array_field_detection(self):
        """Test detection of array fields in schema"""
        self.processor.schema_cache = {
            "invoice": {
                "target_tables": [
                    {
                        "name": "Invoice_line_items",
                        "columns": [
                            {
                                "name": "amount",
                                "source": {
                                    "transform": {
                                        "transform_name": "currency_to_numeric",
                                        "arguments": [{"name": "amount", "value": {"field": ["line_items", "amount"]}}],
                                    }
                                },
                            },
                            {"name": "description", "source": {"field": ["line_items", "description"]}},
                        ],
                    }
                ]
            }
        }

        entities = {
            "line_items": [
                {"amount": "$100.00", "description": "Item 1"},
                {"amount": "$200.00", "description": "Item 2"},
            ]
        }

        result = self.processor.process_with_schema(entities=entities, document_type="invoice")

        # Should return array of objects
        self.assertIn("Invoice_line_items", result)
        self.assertIsInstance(result["Invoice_line_items"], list)
        self.assertEqual(len(result["Invoice_line_items"]), 2)
        self.assertEqual(result["Invoice_line_items"][0]["description"], "Item 1")
        self.assertEqual(result["Invoice_line_items"][1]["description"], "Item 2")

    def test_process_mixed_tables_array_and_single(self):
        """Test processing with both array-based and single-object tables"""
        self.processor.schema_cache = {
            "invoice": {
                "target_tables": [
                    {
                        "name": "Invoice",
                        "columns": [{"name": "invoice_number", "source": {"field": ["invoice_number"]}}],
                    },
                    {
                        "name": "Invoice_line_items",
                        "columns": [{"name": "description", "source": {"field": ["line_items", "description"]}}],
                    },
                ]
            }
        }

        entities = {"invoice_number": "INV-001", "line_items": [{"description": "Item 1"}, {"description": "Item 2"}]}

        result = self.processor.process_with_schema(entities=entities, document_type="invoice")

        # Invoice should be single object
        self.assertIn("Invoice", result)
        self.assertIsInstance(result["Invoice"], dict)
        self.assertEqual(result["Invoice"]["invoice_number"], "INV-001")

        # Invoice_line_items should be array
        self.assertIn("Invoice_line_items", result)
        self.assertIsInstance(result["Invoice_line_items"], list)
        self.assertEqual(len(result["Invoice_line_items"]), 2)

    def test_process_empty_array_field(self):
        """Test processing when array field is empty"""
        self.processor.schema_cache = {
            "invoice": {
                "target_tables": [
                    {
                        "name": "Invoice_line_items",
                        "columns": [{"name": "description", "source": {"field": ["line_items", "description"]}}],
                    }
                ]
            }
        }

        entities: dict[str, list] = {"line_items": []}

        result = self.processor.process_with_schema(entities=entities, document_type="invoice")

        # Should return empty array
        self.assertIn("Invoice_line_items", result)
        self.assertIsInstance(result["Invoice_line_items"], list)
        self.assertEqual(len(result["Invoice_line_items"]), 0)


if __name__ == "__main__":
    unittest.main()


# ---------------------------------------------------------------------------
# Additional tests to cover remaining missing lines
# ---------------------------------------------------------------------------


class TestSchemaProcessorMissingCoverage(unittest.TestCase):
    """Cover missing lines in schema_processor.py."""

    def setUp(self):
        self.processor = SchemaProcessor()

    # --- load_schemas ---

    def test_load_schemas_skips_empty_document_type(self):
        """Line 40: empty string document_type causes 'continue'."""
        # No file I/O needed - empty string is filtered before open()
        self.processor.load_schemas(document_types=[""])
        self.assertEqual(self.processor.schema_cache, {})

    def test_load_schemas_skips_already_cached(self):
        """Line 39: already-cached type causes 'continue' (second load is no-op)."""
        self.processor.schema_cache["invoice"] = {"target_tables": []}
        # Should not try to open any file
        self.processor.load_schemas(document_types=["invoice"])
        # Cache unchanged - no overwrite
        self.assertEqual(self.processor.schema_cache["invoice"], {"target_tables": []})

    @patch("builtins.open")
    @patch("docpipe.core.operators.functional.entity_curation.schema_processor.Path")
    def test_load_schemas_no_valid_schema(self, mock_path, mock_open):
        """Lines 52-53: file opens OK but document_class_schema is empty dict."""
        import json
        from unittest.mock import mock_open as mock_open_func

        mock_data = {"document_class_schema": {}}  # empty schema
        mock_open.return_value = mock_open_func(read_data=json.dumps(mock_data)).return_value

        mock_path_instance = MagicMock()
        mock_path.return_value = mock_path_instance
        mock_path_instance.__truediv__.return_value = mock_path_instance

        self.processor.load_schemas(document_types=["invoice"])
        # Schema not cached since it was empty
        self.assertNotIn("invoice", self.processor.schema_cache)

    @patch("builtins.open", side_effect=OSError("file not found"))
    @patch("docpipe.core.operators.functional.entity_curation.schema_processor.Path")
    def test_load_schemas_os_error(self, mock_path, mock_open):
        """Lines 53-54: OSError during open is caught, logged, not re-raised."""
        mock_path_instance = MagicMock()
        mock_path.return_value = mock_path_instance
        mock_path_instance.__truediv__.return_value = mock_path_instance

        # Should not raise
        self.processor.load_schemas(document_types=["invoice"])
        self.assertNotIn("invoice", self.processor.schema_cache)

    # --- process_with_schema ---

    def test_process_with_schema_no_target_tables(self):
        """Lines 77-78: schema has no target_tables key returns empty dict."""
        self.processor.schema_cache["invoice"] = {}  # no "target_tables" key
        result = self.processor.process_with_schema(entities={"x": 1}, document_type="invoice")
        self.assertEqual(result, {})

    def test_process_with_schema_empty_target_tables(self):
        """Lines 77-78: schema has empty target_tables list returns empty dict."""
        self.processor.schema_cache["invoice"] = {"target_tables": []}
        result = self.processor.process_with_schema(entities={"x": 1}, document_type="invoice")
        self.assertEqual(result, {})

    @patch("docpipe.core.operators.functional.entity_curation.schema_processor.TRANSFORMS")
    def test_process_with_schema_transform_path(self, mock_transforms):
        """Lines 101-109: column source has 'transform' key triggers _apply_transformation."""
        mock_fn = MagicMock(return_value="transformed")
        mock_transforms.get.return_value = mock_fn

        self.processor.schema_cache["invoice"] = {
            "target_tables": [
                {
                    "name": "header",
                    "columns": [
                        {
                            "name": "result_col",
                            "source": {
                                "transform": {
                                    "transform_name": "concat",
                                    "arguments": [
                                        {"name": "a", "value": {"field": ["field1"]}},
                                    ],
                                }
                            },
                        }
                    ],
                }
            ]
        }

        entities = {"field1": "hello"}
        result = self.processor.process_with_schema(entities=entities, document_type="invoice")
        self.assertIn("header", result)
        self.assertEqual(result["header"]["result_col"], "transformed")

    # --- _apply_transformation ---

    @patch("docpipe.core.operators.functional.entity_curation.schema_processor.TRANSFORMS")
    def test_apply_transformation_invalid_arg_name_type(self, mock_transforms):
        """Lines 147-150: non-string arg_name causes warning and skip."""
        mock_fn = MagicMock(return_value="ok")
        mock_transforms.get.return_value = mock_fn

        entities = {"field1": "val"}
        # arg_name is None (not a string) — should be skipped
        arguments = [{"name": None, "value": {"field": ["field1"]}}]
        result = self.processor._apply_transformation(
            transform_name="test_transform", arguments=arguments, entities=entities
        )
        # func called with no kwargs since arg was skipped
        mock_fn.assert_called_once_with()
        self.assertEqual(result, "ok")

    @patch("docpipe.core.operators.functional.entity_curation.schema_processor.TRANSFORMS")
    def test_apply_transformation_arg_value_no_field(self, mock_transforms):
        """Line 152: arg_value without 'field' key is passed directly."""
        mock_fn = MagicMock(return_value="direct")
        mock_transforms.get.return_value = mock_fn

        entities = {}
        arguments = [{"name": "separator", "value": "-"}]
        result = self.processor._apply_transformation(
            transform_name="test_transform", arguments=arguments, entities=entities
        )
        # The raw arg_value ("-") is passed directly
        mock_fn.assert_called_once_with(separator="-")
        self.assertEqual(result, "direct")

    @patch("docpipe.core.operators.functional.entity_curation.schema_processor.TRANSFORMS")
    def test_apply_transformation_func_raises_exception(self, mock_transforms):
        """Lines 156-158: func() raises, warning logged, None returned."""
        mock_fn = MagicMock(side_effect=ValueError("bad input"))
        mock_transforms.get.return_value = mock_fn

        entities = {}
        arguments = []
        result = self.processor._apply_transformation(
            transform_name="test_transform", arguments=arguments, entities=entities
        )
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
