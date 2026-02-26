"""
Unit tests for ReadabilityOperator
"""
import unittest
import pyarrow as pa
from core.operators.universal.readability.readability import ReadabilityOperator, DEFAULT_READABILITY_SCORES
from common.util.constants import Metrics, OperatorConstants


class TestReadabilityOperator(unittest.TestCase):
    """Test cases for ReadabilityOperator"""

    def test_init(self):
        """Test that the operator initializes correctly."""
        config = {
            "readability_contents_column_name": "content",
            "readability_score_list": ["flesch_ease", "flesch_kincaid"]
        }
        operator = ReadabilityOperator(config=config)
        self.assertIsNotNone(operator, "Readability Operator is not None")
        self.assertEqual(operator.contents_column_name, "content")
        self.assertIn("flesch_ease", operator.score_list)

    def test_readability_metadata(self):
        """Test that metadata is returned correctly."""
        operator = ReadabilityOperator(config={"readability_score_list": ["flesch_ease"]})
        metadata = operator.get_metadata()
        
        self.assertIn(OperatorConstants.SDK, metadata)
        self.assertTrue(metadata[OperatorConstants.SDK])
        self.assertIn(OperatorConstants.CATEGORY, metadata)
        self.assertIn(OperatorConstants.LABEL, metadata)
        self.assertEqual(metadata[OperatorConstants.LABEL], "Readability Operator")
        self.assertIn(OperatorConstants.FEATURES, metadata)
        self.assertIn("flesch_ease", metadata[OperatorConstants.FEATURES])

    def test_readability_transform(self):
        """Test the transform method."""
        config = {
            "readability_contents_column_name": "content",
            "readability_score_list": ["flesch_ease", "flesch_kincaid"]
        }
        operator = ReadabilityOperator(config=config)
        
        content = pa.array([
            "The cat sat on the mat. It was a sunny day.",
            "Python is a high-level programming language used for web development.",
            "The implementation of sophisticated algorithms necessitates comprehensive understanding."
        ])
        test_table = pa.Table.from_arrays([content], names=["content"])
        
        table_list, metadata = operator.transform(table=test_table)
        
        self.assertEqual(len(table_list), 1)
        transformed_table = table_list[0]
        
        # Check that new columns were added
        self.assertIn("flesch_ease_textstat", transformed_table.column_names)
        self.assertIn("flesch_kincaid_textstat", transformed_table.column_names)
        
        # Check metadata
        self.assertIn(Metrics.External.PROCESSED_DOCS, metadata)
        self.assertEqual(metadata[Metrics.External.PROCESSED_DOCS], 3)

    def test_readability_required_features(self):
        """Test that required features are returned correctly."""
        config = {
            "readability_contents_column_name": "content",
            "readability_score_list": ["flesch_ease", "flesch_kincaid"]
        }
        operator = ReadabilityOperator(config=config)
        required_features = operator.get_required_features()
        
        self.assertEqual(len(required_features), 1)
        self.assertIn("content", required_features)

    def test_readability_validation_warning(self):
        """Test that validation warns when no scores are selected."""
        operator = ReadabilityOperator(config={"readability_score_list": []})
        errors = []
        warnings = []
        
        operator.validate(errors=errors, warnings=warnings, available_features=["content"])
        
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(warnings), 1)
        self.assertIn("at least one readability score must be selected", warnings[0].lower())

    def test_readability_all_scores(self):
        """Test with all available readability scores."""
        config = {
            "readability_contents_column_name": "content",
            "readability_score_list": DEFAULT_READABILITY_SCORES
        }
        
        operator = ReadabilityOperator(config=config)
        content = pa.array(["This is a simple test sentence."])
        test_table = pa.Table.from_arrays([content], names=["content"])
        
        table_list, metadata = operator.transform(table=test_table)
        transformed_table = table_list[0]
        
        # Check that all score columns were added
        for score in DEFAULT_READABILITY_SCORES:
            self.assertIn(f"{score}_textstat", transformed_table.column_names)


def test_operator_metadata():
    """Test that operator returns correct metadata"""
    operator = ReadabilityOperator(config={"readability_score_list": ["flesch_ease"]})
    
    operator_metadata = operator.get_metadata()
    
    expected_keys = [
        OperatorConstants.SDK,
        OperatorConstants.CATEGORY,
        OperatorConstants.IS_OPERATOR_AVAILABLE,
        OperatorConstants.LABEL,
        OperatorConstants.FEATURES,
        OperatorConstants.ATTRIBUTES
    ]
    
    for key in expected_keys:
        assert key in operator_metadata, f"Missing key: {key}"
    
    assert operator_metadata[OperatorConstants.CATEGORY] == "Quality"
    assert operator_metadata[OperatorConstants.IS_OPERATOR_AVAILABLE] is True
    assert operator_metadata[OperatorConstants.LABEL] == "Readability Operator"


class TestReadabilityOperatorEdgeCases(unittest.TestCase):
    """Test edge cases and error handling for ReadabilityOperator"""

    def test_empty_table(self):
        """Test readability with an empty table"""
        data = {"content": []}
        empty_table = pa.table(data)
        
        operator = ReadabilityOperator(config={
            "readability_contents_column_name": "content",
            "readability_score_list": ["flesch_ease"]
        })
        
        result_tables, metadata = operator.transform(empty_table)
        
        # Should return empty table with score columns
        self.assertEqual(result_tables[0].num_rows, 0)
        self.assertEqual(metadata[Metrics.External.PROCESSED_DOCS], 0)

    def test_single_document(self):
        """Test with a single document"""
        content = pa.array(["Single document for testing."])
        test_table = pa.Table.from_arrays([content], names=["content"])
        
        operator = ReadabilityOperator(config={
            "readability_contents_column_name": "content",
            "readability_score_list": ["flesch_ease", "flesch_kincaid"]
        })
        
        result_tables, metadata = operator.transform(test_table)
        
        self.assertEqual(result_tables[0].num_rows, 1)
        self.assertEqual(metadata[Metrics.External.PROCESSED_DOCS], 1)
        self.assertIn("flesch_ease_textstat", result_tables[0].column_names)

    def test_custom_column_name(self):
        """Test with custom content column name"""
        custom_col = "my_text"
        content = pa.array(["Test document content."])
        test_table = pa.Table.from_arrays([content], names=[custom_col])
        
        operator = ReadabilityOperator(config={
            "readability_contents_column_name": custom_col,
            "readability_score_list": ["flesch_ease"]
        })
        
        result_tables, metadata = operator.transform(test_table)
        
        self.assertEqual(result_tables[0].num_rows, 1)
        self.assertIn("flesch_ease_textstat", result_tables[0].column_names)

    def test_output_table_structure(self):
        """Test that output table maintains correct structure"""
        content = pa.array(["Doc 1", "Doc 2"])
        test_table = pa.Table.from_arrays([content], names=["content"])
        
        operator = ReadabilityOperator(config={
            "readability_contents_column_name": "content",
            "readability_score_list": ["flesch_ease", "flesch_kincaid"]
        })
        
        result_tables, metadata = operator.transform(test_table)
        result_table = result_tables[0]
        
        # Verify output table has original column plus score columns
        self.assertIn("content", result_table.column_names)
        self.assertIn("flesch_ease_textstat", result_table.column_names)
        self.assertIn("flesch_kincaid_textstat", result_table.column_names)
        self.assertEqual(result_table.num_rows, 2)

    def test_metadata_completeness(self):
        """Test that all required metadata fields are present"""
        content = pa.array(["Doc 1", "Doc 2", "Doc 3"])
        test_table = pa.Table.from_arrays([content], names=["content"])
        
        operator = ReadabilityOperator(config={
            "readability_contents_column_name": "content",
            "readability_score_list": ["flesch_ease"]
        })
        
        _, metadata = operator.transform(test_table)
        
        # Verify all required metadata fields are present
        required_fields = [
            Metrics.External.TOTAL_DOCS,
            Metrics.External.PROCESSED_DOCS,
            Metrics.External.FAILED_DOCS_COUNT,
            Metrics.External.FAILED_DOCS,
            Metrics.External.SKIPPED_DOCS_COUNT,
            Metrics.External.SKIPPED_DOCS,
            Metrics.External.NODE_STATUS
        ]
        
        for field in required_fields:
            self.assertIn(field, metadata, f"Missing required metadata field: {field}")

    def test_validation_invalid_scores(self):
        """Test validation with invalid readability scores"""
        operator = ReadabilityOperator(config={
            "readability_score_list": ["invalid_score", "another_invalid"]
        })
        errors = []
        warnings = []
        
        operator.validate(errors=errors, warnings=warnings, available_features=["content"])
        
        # Should warn about invalid scores
        self.assertEqual(len(warnings), 1)
        self.assertIn("invalid", warnings[0].lower())

    def test_multiple_documents_varying_complexity(self):
        """Test with documents of varying complexity"""
        content = pa.array([
            "Cat.",  # Very simple
            "The quick brown fox jumps over the lazy dog.",  # Simple
            "Python is a high-level programming language.",  # Medium
            "The implementation of sophisticated algorithms necessitates comprehensive understanding."  # Complex
        ])
        test_table = pa.Table.from_arrays([content], names=["content"])
        
        operator = ReadabilityOperator(config={
            "readability_contents_column_name": "content",
            "readability_score_list": ["flesch_ease", "flesch_kincaid", "gunning_fog"]
        })
        
        result_tables, metadata = operator.transform(test_table)
        result_table = result_tables[0]
        
        self.assertEqual(result_table.num_rows, 4)
        self.assertEqual(metadata[Metrics.External.PROCESSED_DOCS], 4)
        
        # Verify all score columns exist
        self.assertIn("flesch_ease_textstat", result_table.column_names)
        self.assertIn("flesch_kincaid_textstat", result_table.column_names)
        self.assertIn("gunning_fog_textstat", result_table.column_names)

    def test_static_required_features(self):
        """Test static required features method"""
        static_features = ReadabilityOperator.get_static_required_features()
        self.assertEqual(len(static_features), 1)
        self.assertEqual(static_features[0], OperatorConstants.DOC_COLUMN_DEFAULT)


if __name__ == '__main__':
    unittest.main()