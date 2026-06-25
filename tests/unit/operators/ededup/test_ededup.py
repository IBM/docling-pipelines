import os
import unittest

import pyarrow as pa
from data_processing.test_support import get_tables_in_folder
from data_processing.test_support.transform import AbstractTableTransformTest
from dpk_ededup import (
    EdedupTransform,
    HashFilter,
    doc_column_name_key,
    int_column_name_key,
)

from docpipe.core.constants.constants import Metrics
from docpipe.core.constants.operator_constants import OperatorConstants

# from dpk_ededup.transform_python import EdedupTransform
# from docpipe_core.operators.quality.ededup import EdedupOperator
from docpipe.core.operators.quality.ededup import EdedupOperator


class TestEdedupTransformFromParquetFile(AbstractTableTransformTest):
    """
    Extends the super-class to define the test data for the tests defined there.
    The name of this class MUST begin with the word Test so that pytest recognizes it as a test class.
    """

    def get_test_transform_fixtures(self) -> list[tuple]:
        # Use the correct path relative to the test file location
        basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../fixtures"))
        input_dir = os.path.join(basedir, "ededup_input")
        expected_dir = os.path.join(basedir, "ededup_expected")

        # Create directories if they don't exist
        os.makedirs(input_dir, exist_ok=True)
        os.makedirs(expected_dir, exist_ok=True)

        input_tables = get_tables_in_folder(input_dir)
        expected_tables = get_tables_in_folder(expected_dir)

        # Ensure fixture files are present — fail fast with a clear message if not
        assert len(input_tables) > 0, f"No input parquet files found in {input_dir}"
        assert len(expected_tables) > 0, f"No expected parquet files found in {expected_dir}"
        expected_metadata_list = [
            {
                "result_documents": 3,
                "source_documents": 5,
                "removed_documents": [
                    "c86996cf20920d0955a38580abb650b00d0e1df5f7bd98646669561fd89c1627",
                    "3e4d6c6c89dd166c88d79a6cbe3d90c8db2c9847fca19893409ec29434643c3d",
                ],
            },
            {},
        ]  # pragma: allowlist secret
        # Expected metadata should be produced for each transform call plus a final flush
        assert len(expected_metadata_list) == len(input_tables) + 1, (
            f"Expected metadata list length ({len(expected_metadata_list)}) does not match number of input tables plus flush ({len(input_tables) + 1})"
        )
        config = {
            doc_column_name_key: "contents",
            int_column_name_key: "document_id",
            "filter": HashFilter({}),
        }
        return [
            (
                EdedupTransform(config),
                input_tables,
                expected_tables,
                expected_metadata_list,
            ),
        ]


class TestDocpipeEdedupOperator(unittest.TestCase):
    def test_init(self):
        config = {"doc_column": "content", "doc_id_hash_column": "doc_id_hash"}
        operator = EdedupOperator(config)
        self.assertIsNotNone(operator, "Ededup Operator is not None")

    def test_ededup_transform_from_table(self):
        # 1. Create a Pyarrow table
        content = ["Document content 1", "Document content 1", "Document content 3"]
        doc_id_hash = [str(101), str(102), str(103)]
        name = ["Doc 1", "Doc 2", "Doc 3"]

        data = {
            OperatorConstants.Columns.ID: doc_id_hash,
            OperatorConstants.Columns.DOC_COLUMN_DEFAULT: content,
            OperatorConstants.Columns.DOC_ID_HASH_DEFAULT: doc_id_hash,
            OperatorConstants.Columns.NAME: name,
        }
        input_table = pa.table(data)

        # 2. Using the output of local ingest into the ededup_input for the edudep transform
        ededup_operator = EdedupOperator(
            {
                OperatorConstants.Columns.DOC_COLUMN: OperatorConstants.Columns.DOC_COLUMN_DEFAULT,
                OperatorConstants.Columns.DOC_ID_HASH_DEFAULT: OperatorConstants.Columns.DOC_ID_HASH_DEFAULT,
            }
        )

        # 3. Create Expected MetaData
        expected_metadata = {
            Metrics.External.TOTAL_DOCS: 3,
            Metrics.External.PROCESSED_DOCS: 2,
            Metrics.External.FAILED_DOCS_COUNT: 0,
            Metrics.External.FAILED_DOCS: [],
            Metrics.External.SKIPPED_DOCS: [
                {
                    "id": "102",
                    "name": "Doc 2",
                    "reason": "This document was identified as a duplicate and removed.",
                    "document_url": "",
                }
            ],
            Metrics.External.SKIPPED_DOCS_COUNT: 1,
            Metrics.External.REMOVED_DOCUMENTS: 1,
            Metrics.External.NODE_STATUS: "Completed",
        }

        _, metadata = ededup_operator.transform(input_table)

        # 4. Perform Assertions
        assert metadata == expected_metadata


def test_operator_metadata():
    """Test that operator returns correct metadata"""
    ededup_operator = EdedupOperator({})

    operator_metadata = ededup_operator.get_metadata()

    expected_operator_metadata = {
        "category": "Quality",
        "description": "Exact deduplication operator that removes duplicate documents based on content hash",
        "is_operator_available": True,
        "label": "De-duplicator",
    }

    assert operator_metadata == expected_operator_metadata, "Ededup Operator metadata mismatch"


class TestEdedupOperatorEdgeCases(unittest.TestCase):
    """Test edge cases and error handling for EdedupOperator"""

    def test_empty_table(self):
        """Test deduplication with an empty table"""
        # Create empty table with correct schema
        data = {
            OperatorConstants.Columns.ID: [],
            OperatorConstants.Columns.DOC_COLUMN_DEFAULT: [],
            OperatorConstants.Columns.DOC_ID_HASH_DEFAULT: [],
            OperatorConstants.Columns.NAME: [],
        }
        empty_table = pa.table(data)

        operator = EdedupOperator(
            {
                OperatorConstants.Columns.DOC_COLUMN: OperatorConstants.Columns.DOC_COLUMN_DEFAULT,
                OperatorConstants.Columns.DOC_ID_HASH_DEFAULT: OperatorConstants.Columns.DOC_ID_HASH_DEFAULT,
            }
        )

        result_tables, metadata = operator.transform(empty_table)

        # Should return empty table
        self.assertEqual(result_tables[0].num_rows, 0)
        self.assertEqual(metadata[Metrics.External.TOTAL_DOCS], 0)
        self.assertEqual(metadata[Metrics.External.PROCESSED_DOCS], 0)

    def test_no_duplicates(self):
        """Test when all documents are unique (no duplicates)"""
        content = ["Document 1", "Document 2", "Document 3", "Document 4"]
        doc_id_hash = [str(i) for i in range(101, 105)]
        name = [f"Doc {i}" for i in range(1, 5)]

        data = {
            OperatorConstants.Columns.ID: doc_id_hash,
            OperatorConstants.Columns.DOC_COLUMN_DEFAULT: content,
            OperatorConstants.Columns.DOC_ID_HASH_DEFAULT: doc_id_hash,
            OperatorConstants.Columns.NAME: name,
        }
        input_table = pa.table(data)

        operator = EdedupOperator(
            {
                OperatorConstants.Columns.DOC_COLUMN: OperatorConstants.Columns.DOC_COLUMN_DEFAULT,
                OperatorConstants.Columns.DOC_ID_HASH_DEFAULT: OperatorConstants.Columns.DOC_ID_HASH_DEFAULT,
            }
        )

        result_tables, metadata = operator.transform(input_table)

        # All documents should remain
        self.assertEqual(result_tables[0].num_rows, 4)
        self.assertEqual(metadata[Metrics.External.TOTAL_DOCS], 4)
        self.assertEqual(metadata[Metrics.External.PROCESSED_DOCS], 4)
        self.assertEqual(metadata[Metrics.External.SKIPPED_DOCS_COUNT], 0)
        self.assertEqual(metadata[Metrics.External.REMOVED_DOCUMENTS], 0)

    def test_all_duplicates(self):
        """Test when all documents are identical"""
        content = ["Same content"] * 5
        doc_id_hash = [str(i) for i in range(101, 106)]
        name = [f"Doc {i}" for i in range(1, 6)]

        data = {
            OperatorConstants.Columns.ID: doc_id_hash,
            OperatorConstants.Columns.DOC_COLUMN_DEFAULT: content,
            OperatorConstants.Columns.DOC_ID_HASH_DEFAULT: doc_id_hash,
            OperatorConstants.Columns.NAME: name,
        }
        input_table = pa.table(data)

        operator = EdedupOperator(
            {
                OperatorConstants.Columns.DOC_COLUMN: OperatorConstants.Columns.DOC_COLUMN_DEFAULT,
                OperatorConstants.Columns.DOC_ID_HASH_DEFAULT: OperatorConstants.Columns.DOC_ID_HASH_DEFAULT,
            }
        )

        result_tables, metadata = operator.transform(input_table)

        # Only first occurrence should remain
        self.assertEqual(result_tables[0].num_rows, 1)
        self.assertEqual(metadata[Metrics.External.TOTAL_DOCS], 5)
        self.assertEqual(metadata[Metrics.External.PROCESSED_DOCS], 1)
        self.assertEqual(metadata[Metrics.External.SKIPPED_DOCS_COUNT], 4)
        self.assertEqual(metadata[Metrics.External.REMOVED_DOCUMENTS], 4)

    def test_none_table(self):
        """Test handling of None table input"""
        operator = EdedupOperator(
            {
                OperatorConstants.Columns.DOC_COLUMN: OperatorConstants.Columns.DOC_COLUMN_DEFAULT,
                OperatorConstants.Columns.DOC_ID_HASH_DEFAULT: OperatorConstants.Columns.DOC_ID_HASH_DEFAULT,
            }
        )

        result_tables, _ = operator.transform(None)

        # Should handle gracefully and return None in output
        self.assertIsNone(result_tables[0])

    def test_custom_column_names(self):
        """Test with custom column names"""
        custom_doc_col = "my_content"
        custom_hash_col = "my_hash"

        content = ["Doc 1", "Doc 1", "Doc 2"]
        doc_id_hash = ["hash1", "hash2", "hash3"]
        name = ["Name 1", "Name 2", "Name 3"]

        data = {
            OperatorConstants.Columns.ID: doc_id_hash,
            custom_doc_col: content,
            custom_hash_col: doc_id_hash,
            OperatorConstants.Columns.NAME: name,
        }
        input_table = pa.table(data)

        operator = EdedupOperator(
            {
                OperatorConstants.Columns.DOC_COLUMN: custom_doc_col,
                OperatorConstants.Columns.DOC_ID_HASH: custom_hash_col,
            }
        )

        result_tables, metadata = operator.transform(input_table)

        # Should process with custom columns
        self.assertEqual(result_tables[0].num_rows, 2)
        self.assertEqual(metadata[Metrics.External.TOTAL_DOCS], 3)
        self.assertEqual(metadata[Metrics.External.PROCESSED_DOCS], 2)

    def test_output_table_structure(self):
        """Test that output table maintains correct structure"""
        content = ["Doc 1", "Doc 2"]
        doc_id_hash = ["101", "102"]
        name = ["Name 1", "Name 2"]

        data = {
            OperatorConstants.Columns.ID: doc_id_hash,
            OperatorConstants.Columns.DOC_COLUMN_DEFAULT: content,
            OperatorConstants.Columns.DOC_ID_HASH_DEFAULT: doc_id_hash,
            OperatorConstants.Columns.NAME: name,
        }
        input_table = pa.table(data)

        operator = EdedupOperator(
            {
                OperatorConstants.Columns.DOC_COLUMN: OperatorConstants.Columns.DOC_COLUMN_DEFAULT,
                OperatorConstants.Columns.DOC_ID_HASH_DEFAULT: OperatorConstants.Columns.DOC_ID_HASH_DEFAULT,
            }
        )

        result_tables, _ = operator.transform(input_table)
        result_table = result_tables[0]

        # Verify output table has same columns as input
        self.assertEqual(set(result_table.column_names), set(input_table.column_names))
        # Verify output table has correct schema
        self.assertEqual(result_table.schema, input_table.schema)

    def test_metadata_completeness(self):
        """Test that all required metadata fields are present"""
        content = ["Doc 1", "Doc 1", "Doc 2"]
        doc_id_hash = ["101", "102", "103"]
        name = ["Name 1", "Name 2", "Name 3"]

        data = {
            OperatorConstants.Columns.ID: doc_id_hash,
            OperatorConstants.Columns.DOC_COLUMN_DEFAULT: content,
            OperatorConstants.Columns.DOC_ID_HASH_DEFAULT: doc_id_hash,
            OperatorConstants.Columns.NAME: name,
        }
        input_table = pa.table(data)

        operator = EdedupOperator(
            {
                OperatorConstants.Columns.DOC_COLUMN: OperatorConstants.Columns.DOC_COLUMN_DEFAULT,
                OperatorConstants.Columns.DOC_ID_HASH_DEFAULT: OperatorConstants.Columns.DOC_ID_HASH_DEFAULT,
            }
        )

        _, metadata = operator.transform(input_table)

        # Verify all required metadata fields are present
        required_fields = [
            Metrics.External.TOTAL_DOCS,
            Metrics.External.PROCESSED_DOCS,
            Metrics.External.FAILED_DOCS_COUNT,
            Metrics.External.FAILED_DOCS,
            Metrics.External.SKIPPED_DOCS_COUNT,
            Metrics.External.SKIPPED_DOCS,
            Metrics.External.REMOVED_DOCUMENTS,
            Metrics.External.NODE_STATUS,
        ]

        for field in required_fields:
            self.assertIn(field, metadata, f"Missing required metadata field: {field}")

    def test_single_document(self):
        """Test with a single document (edge case)"""
        content = ["Single document"]
        doc_id_hash = ["101"]
        name = ["Doc 1"]

        data = {
            OperatorConstants.Columns.ID: doc_id_hash,
            OperatorConstants.Columns.DOC_COLUMN_DEFAULT: content,
            OperatorConstants.Columns.DOC_ID_HASH_DEFAULT: doc_id_hash,
            OperatorConstants.Columns.NAME: name,
        }
        input_table = pa.table(data)

        operator = EdedupOperator(
            {
                OperatorConstants.Columns.DOC_COLUMN: OperatorConstants.Columns.DOC_COLUMN_DEFAULT,
                OperatorConstants.Columns.DOC_ID_HASH_DEFAULT: OperatorConstants.Columns.DOC_ID_HASH_DEFAULT,
            }
        )

        result_tables, metadata = operator.transform(input_table)

        # Single document should pass through
        self.assertEqual(result_tables[0].num_rows, 1)
        self.assertEqual(metadata[Metrics.External.TOTAL_DOCS], 1)
        self.assertEqual(metadata[Metrics.External.PROCESSED_DOCS], 1)
        self.assertEqual(metadata[Metrics.External.SKIPPED_DOCS_COUNT], 0)

    def test_multiple_duplicate_groups(self):
        """Test with multiple groups of duplicates"""
        content = ["Doc A", "Doc A", "Doc B", "Doc B", "Doc C"]
        doc_id_hash = [str(i) for i in range(101, 106)]
        name = [f"Name {i}" for i in range(1, 6)]

        data = {
            OperatorConstants.Columns.ID: doc_id_hash,
            OperatorConstants.Columns.DOC_COLUMN_DEFAULT: content,
            OperatorConstants.Columns.DOC_ID_HASH_DEFAULT: doc_id_hash,
            OperatorConstants.Columns.NAME: name,
        }
        input_table = pa.table(data)

        operator = EdedupOperator(
            {
                OperatorConstants.Columns.DOC_COLUMN: OperatorConstants.Columns.DOC_COLUMN_DEFAULT,
                OperatorConstants.Columns.DOC_ID_HASH_DEFAULT: OperatorConstants.Columns.DOC_ID_HASH_DEFAULT,
            }
        )

        result_tables, metadata = operator.transform(input_table)

        # Should keep first of each duplicate group: Doc A, Doc B, Doc C
        self.assertEqual(result_tables[0].num_rows, 3)
        self.assertEqual(metadata[Metrics.External.TOTAL_DOCS], 5)
        self.assertEqual(metadata[Metrics.External.PROCESSED_DOCS], 3)
        self.assertEqual(metadata[Metrics.External.SKIPPED_DOCS_COUNT], 2)
        self.assertEqual(metadata[Metrics.External.REMOVED_DOCUMENTS], 2)
