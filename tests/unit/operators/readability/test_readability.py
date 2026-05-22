import unittest

import pyarrow as pa

from datasift.core.constants.constants import Metrics
from datasift.core.constants.operator_constants import OperatorConstants
from datasift.core.operators.quality.readability import (
    DEFAULT_READABILITY_SCORES,
    ReadabilityOperator,
)


class TestReadabilityOperator(unittest.TestCase):
    def test_init(self):
        config = {
            "readability_contents_column_name": "content",
            "readability_score_list": ["flesch_ease_textstat", "flesch_kincaid_textstat"],
        }
        operator = ReadabilityOperator(config=config)
        self.assertIsNotNone(operator, "Readability Operator is not None")
        self.assertEqual(operator.contents_column_name, "content")
        self.assertIn("flesch_ease_textstat", operator.score_list)

    def test_readability_metadata(self):
        operator = ReadabilityOperator(config={"readability_score_list": ["flesch_ease"]})
        metadata = operator.get_metadata()

        self.assertIn(OperatorConstants.Misc.SDK, metadata)
        self.assertTrue(metadata[OperatorConstants.Misc.SDK])
        self.assertIn(OperatorConstants.Misc.CATEGORY, metadata)
        self.assertIn(OperatorConstants.Misc.LABEL, metadata)
        self.assertEqual(metadata[OperatorConstants.Misc.LABEL], "Readability Operator")
        self.assertIn(OperatorConstants.Config.FEATURES, metadata)
        # Metadata uses names without _textstat suffix
        self.assertIn("flesch_ease", metadata[OperatorConstants.Config.FEATURES])

    def test_readability_transform(self):
        config = {
            "readability_contents_column_name": "content",
            "readability_score_list": ["flesch_ease", "flesch_kincaid"],
        }
        operator = ReadabilityOperator(config=config)

        content = pa.array(
            [
                "The cat sat on the mat. It was a sunny day.",
                "Python is a high-level programming language used for web development.",
                "The implementation of sophisticated algorithms necessitates comprehensive understanding.",
            ]
        )
        test_table = pa.Table.from_arrays([content], names=["content"])

        table_list, metadata = operator.transform(table=test_table)

        self.assertEqual(len(table_list), 1)
        transformed_table = table_list[0]

        # Transform output uses names with _textstat suffix
        self.assertIn("flesch_ease_textstat", transformed_table.column_names)
        self.assertIn("flesch_kincaid_textstat", transformed_table.column_names)

        self.assertIn(Metrics.External.PROCESSED_DOCS, metadata)
        self.assertEqual(metadata[Metrics.External.PROCESSED_DOCS], 3)

    def test_readability_required_features(self):
        config = {
            "readability_contents_column_name": "content",
            "readability_score_list": ["flesch_ease", "flesch_kincaid"],
        }
        operator = ReadabilityOperator(config=config)
        required_features = operator.get_required_features()

        self.assertEqual(len(required_features), 1)
        self.assertIn("content", required_features)

    def test_readability_validation_warning(self):
        operator = ReadabilityOperator(config={"readability_score_list": []})
        errors = []
        warnings = []

        operator.validate(errors=errors, warnings=warnings, available_features=["content"])

        self.assertEqual(len(errors), 0)
        self.assertEqual(len(warnings), 1)
        self.assertIn("at least one readability score must be selected", warnings[0].lower())

    def test_readability_all_scores(self):
        config = {
            "readability_contents_column_name": "content",
            "readability_score_list": DEFAULT_READABILITY_SCORES,
        }

        operator = ReadabilityOperator(config=config)
        content = pa.array(["This is a simple test sentence."])
        test_table = pa.Table.from_arrays([content], names=["content"])

        table_list, _ = operator.transform(table=test_table)
        transformed_table = table_list[0]
        # Transform output adds _textstat suffix to score names
        for score in DEFAULT_READABILITY_SCORES:
            self.assertIn(f"{score}_textstat", transformed_table.column_names)


def test_operator_metadata():
    operator = ReadabilityOperator(config={"readability_score_list": ["flesch_ease"]})

    operator_metadata = operator.get_metadata()

    expected_keys = [
        OperatorConstants.Misc.SDK,
        OperatorConstants.Misc.CATEGORY,
        OperatorConstants.Misc.IS_OPERATOR_AVAILABLE,
        OperatorConstants.Misc.LABEL,
        OperatorConstants.Config.FEATURES,
        OperatorConstants.Config.ATTRIBUTES,
    ]

    for key in expected_keys:
        assert key in operator_metadata, f"Missing key: {key}"

    assert operator_metadata[OperatorConstants.Misc.CATEGORY] == "Quality"
    assert operator_metadata[OperatorConstants.Misc.IS_OPERATOR_AVAILABLE] is True
    assert operator_metadata[OperatorConstants.Misc.LABEL] == "Readability Operator"


class TestReadabilityOperatorEdgeCases(unittest.TestCase):
    def test_empty_table(self):
        data = {"content": []}
        empty_table = pa.table(data)

        operator = ReadabilityOperator(
            config={
                "readability_contents_column_name": "content",
                "readability_score_list": ["flesch_ease"],
            }
        )

        result_tables, metadata = operator.transform(empty_table)
        self.assertEqual(result_tables[0].num_rows, 0)
        self.assertEqual(metadata[Metrics.External.PROCESSED_DOCS], 0)

    def test_single_document(self):
        content = pa.array(["Single document for testing."])
        test_table = pa.Table.from_arrays([content], names=["content"])

        operator = ReadabilityOperator(
            config={
                "readability_contents_column_name": "content",
                "readability_score_list": ["flesch_ease", "flesch_kincaid"],
            }
        )

        result_tables, metadata = operator.transform(test_table)

        self.assertEqual(result_tables[0].num_rows, 1)
        self.assertEqual(metadata[Metrics.External.PROCESSED_DOCS], 1)
        self.assertIn("flesch_ease_textstat", result_tables[0].column_names)

    def test_custom_column_name(self):
        custom_col = "my_text"
        content = pa.array(["Test document content."])
        test_table = pa.Table.from_arrays([content], names=[custom_col])

        operator = ReadabilityOperator(
            config={
                "readability_contents_column_name": custom_col,
                "readability_score_list": ["flesch_ease"],
            }
        )

        result_tables, _ = operator.transform(test_table)

        self.assertEqual(result_tables[0].num_rows, 1)
        self.assertIn("flesch_ease_textstat", result_tables[0].column_names)

    def test_output_table_structure(self):
        content = pa.array(["Doc 1", "Doc 2"])
        test_table = pa.Table.from_arrays([content], names=["content"])

        operator = ReadabilityOperator(
            config={
                "readability_contents_column_name": "content",
                "readability_score_list": ["flesch_ease", "flesch_kincaid"],
            }
        )

        result_tables, _ = operator.transform(test_table)
        result_table = result_tables[0]

        self.assertIn("content", result_table.column_names)
        self.assertIn("flesch_ease_textstat", result_table.column_names)
        self.assertIn("flesch_kincaid_textstat", result_table.column_names)
        self.assertEqual(result_table.num_rows, 2)

    def test_metadata_completeness(self):
        content = pa.array(["Doc 1", "Doc 2", "Doc 3"])
        test_table = pa.Table.from_arrays([content], names=["content"])

        operator = ReadabilityOperator(
            config={
                "readability_contents_column_name": "content",
                "readability_score_list": ["flesch_ease"],
            }
        )

        _, metadata = operator.transform(test_table)

        required_fields = [
            Metrics.External.TOTAL_DOCS,
            Metrics.External.PROCESSED_DOCS,
            Metrics.External.FAILED_DOCS_COUNT,
            Metrics.External.FAILED_DOCS,
            Metrics.External.SKIPPED_DOCS_COUNT,
            Metrics.External.SKIPPED_DOCS,
            Metrics.External.NODE_STATUS,
        ]

        for field in required_fields:
            self.assertIn(field, metadata, f"Missing required metadata field: {field}")

    def test_validation_invalid_scores(self):
        operator = ReadabilityOperator(config={"readability_score_list": ["invalid_score", "another_invalid"]})
        errors = []
        warnings = []

        operator.validate(errors=errors, warnings=warnings, available_features=["content"])
        self.assertEqual(len(warnings), 1)
        self.assertIn("invalid", warnings[0].lower())

    def test_multiple_documents_varying_complexity(self):
        content = pa.array(
            [
                "Cat.",
                "The quick brown fox jumps over the lazy dog.",
                "Python is a high-level programming language.",
                "The implementation of sophisticated algorithms necessitates comprehensive understanding.",
            ]
        )
        test_table = pa.Table.from_arrays([content], names=["content"])

        operator = ReadabilityOperator(
            config={
                "readability_contents_column_name": "content",
                "readability_score_list": [
                    "flesch_ease",
                    "flesch_kincaid",
                    "gunning_fog",
                ],
            }
        )

        result_tables, metadata = operator.transform(test_table)
        result_table = result_tables[0]

        self.assertEqual(result_table.num_rows, 4)
        self.assertEqual(metadata[Metrics.External.PROCESSED_DOCS], 4)
        self.assertIn("flesch_ease_textstat", result_table.column_names)
        self.assertIn("flesch_kincaid_textstat", result_table.column_names)
        self.assertIn("gunning_fog_textstat", result_table.column_names)


if __name__ == "__main__":
    unittest.main()
