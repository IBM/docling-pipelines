import unittest
from unittest.mock import patch, MagicMock

import pyarrow as pa
import numpy as np

from core.operators.functional.semantic_chunker import (
    SemanticChunkerOperator,
    ChunkType,
    BreakpointThresholdType,
    CHUNK_MIN_SIZE,
    CHUNK_MAX_SIZE,
    CHUNK_OVERLAP_MAX_SIZE,
)
from common.constants.operator_constants import OperatorConstants


class TestSemanticChunkerOperator(unittest.TestCase):
    """Test SemanticChunkerOperator initialization and basic functionality"""

    def test_init(self):
        """Test operator initialization with simple chunking config"""
        config = {
            "chunk_type": ChunkType.SIMPLE.value,
            "chunk_size": 1000,
            "chunk_overlap": 200,
            "doc_column": "content",
        }
        operator = SemanticChunkerOperator(config)
        self.assertIsNotNone(operator, "SemanticChunker Operator is not None")
        self.assertEqual(operator.chunk_type, ChunkType.SIMPLE.value)
        self.assertEqual(operator.chunk_size, 1000)
        self.assertEqual(operator.chunk_overlap, 200)

    def test_init_semantic_chunking(self):
        """Test operator initialization with semantic chunking config"""
        config = {
            "chunk_type": ChunkType.SEMANTIC.value,
            "semantic_embeddings_model": "granite4",
            "breakpoint_threshold_type": BreakpointThresholdType.PERCENTILE.value,
            "breakpoint_threshold_amount": 95.0,
            "doc_column": "content",
        }
        operator = SemanticChunkerOperator(config)
        self.assertIsNotNone(operator)
        self.assertEqual(operator.chunk_type, ChunkType.SEMANTIC.value)
        self.assertEqual(operator.semantic_embeddings_model, "granite4")
        self.assertEqual(
            operator.breakpoint_threshold_type, BreakpointThresholdType.PERCENTILE.value
        )

    def test_simple_chunking_transform(self):
        """Test simple chunking with a PyArrow table"""
        # 1. Create a PyArrow table with sample content
        content = [
            "This is the first sentence. This is the second sentence. "
            "This is the third sentence. This is the fourth sentence."
        ]
        doc_ids = ["doc1"]
        names = ["Document 1"]

        data = {
            OperatorConstants.Columns.ID: doc_ids,
            OperatorConstants.Columns.NAME: names,
            "content": content,
        }
        input_table = pa.table(data)

        # 2. Create operator with simple chunking config
        config = {
            "chunk_type": ChunkType.SIMPLE.value,
            "chunk_size": 1000,
            "chunk_overlap": 200,
            "doc_column": "content",
            "retain_original_content": True,
        }
        operator = SemanticChunkerOperator(config)

        # 3. Transform the table
        result_tables, metadata = operator.transform(input_table)
        result_table = result_tables[0]

        # 4. Perform assertions
        self.assertEqual(result_table.num_rows, 1)
        self.assertIn(
            OperatorConstants.Columns.CHUNKED_CONTENT, result_table.column_names
        )

        # Check that chunks were created
        chunked_content = result_table[OperatorConstants.Columns.CHUNKED_CONTENT][
            0
        ].as_py()
        self.assertIsNotNone(chunked_content)
        self.assertGreater(len(chunked_content), 0)

    def test_simple_chunking_long_text(self):
        """Test simple chunking with long text that requires multiple chunks"""
        # Create long text
        long_text = ". ".join([f"This is sentence number {i}" for i in range(100)])

        data = {
            OperatorConstants.Columns.ID: ["doc1"],
            OperatorConstants.Columns.NAME: ["Long Document"],
            "content": [long_text],
        }
        input_table = pa.table(data)

        config = {
            "chunk_type": ChunkType.SIMPLE.value,
            "chunk_size": 500,
            "chunk_overlap": 100,
            "doc_column": "content",
        }
        operator = SemanticChunkerOperator(config)

        result_tables, metadata = operator.transform(input_table)
        result_table = result_tables[0]

        # Should create multiple chunks
        chunked_content = result_table[OperatorConstants.Columns.CHUNKED_CONTENT][
            0
        ].as_py()
        self.assertGreater(
            len(chunked_content), 1, "Long text should create multiple chunks"
        )

    @patch("core.operators.functional.semantic_chunker.OllamaClient")
    def test_semantic_chunking_transform(self, mock_ollama_client_class):
        """Test semantic chunking with fully mocked Ollama client"""
        # Mock the OllamaClient to avoid any real API calls
        mock_client = MagicMock()
        mock_client.generate_embeddings.return_value = np.random.rand(384).tolist()
        mock_ollama_client_class.return_value = mock_client

        # Create test data
        content = [
            "First topic sentence. Another first topic sentence. "
            "Second topic sentence. Another second topic sentence."
        ]
        data = {
            OperatorConstants.Columns.ID: ["doc1"],
            OperatorConstants.Columns.NAME: ["Document 1"],
            "content": content,
        }
        input_table = pa.table(data)

        # Create operator with semantic chunking
        config = {
            "chunk_type": ChunkType.SEMANTIC.value,
            "semantic_embeddings_model": "granite4",
            "breakpoint_threshold_type": BreakpointThresholdType.PERCENTILE.value,
            "doc_column": "content",
        }

        operator = SemanticChunkerOperator(config)

        # Transform
        result_tables, metadata = operator.transform(input_table)
        result_table = result_tables[0]

        # Assertions
        self.assertEqual(result_table.num_rows, 1)
        self.assertIn(
            OperatorConstants.Columns.CHUNKED_CONTENT, result_table.column_names
        )

        # Check that chunks were created
        chunked_content = result_table[OperatorConstants.Columns.CHUNKED_CONTENT][
            0
        ].as_py()
        self.assertIsNotNone(chunked_content)
        self.assertGreater(len(chunked_content), 0)

        # Verify mock was used (no real Ollama calls)
        mock_ollama_client_class.assert_called_once()


def test_operator_metadata():
    """Test that operator returns correct metadata"""
    operator = SemanticChunkerOperator({})

    operator_metadata = operator.get_metadata()

    # Check that metadata has required keys
    assert OperatorConstants.Misc.CATEGORY in operator_metadata
    assert OperatorConstants.Config.FEATURES in operator_metadata
    assert OperatorConstants.Config.ATTRIBUTES in operator_metadata
    assert operator_metadata[OperatorConstants.Misc.IS_OPERATOR_AVAILABLE] is True


class TestSemanticChunkerValidation(unittest.TestCase):
    """Test configuration validation"""

    def test_validate_chunk_size_in_range(self):
        """Test validation accepts valid chunk sizes"""
        config = {
            "chunk_type": ChunkType.SIMPLE.value,
            "chunk_size": 1000,
            "doc_column": "content",
        }
        operator = SemanticChunkerOperator(config)
        errors = []
        warnings = []
        operator.validate(errors, warnings, ["content"])

        self.assertEqual(len(errors), 0, "Valid chunk size should not produce errors")

    def test_validate_chunk_size_too_small(self):
        """Test validation rejects chunk size below minimum"""
        config = {
            "chunk_type": ChunkType.SIMPLE.value,
            "chunk_size": CHUNK_MIN_SIZE - 1,
            "doc_column": "content",
        }
        operator = SemanticChunkerOperator(config)
        errors = []
        warnings = []
        operator.validate(errors, warnings, ["content"])

        self.assertGreater(
            len(errors), 0, "Chunk size below minimum should produce errors"
        )

    def test_validate_chunk_size_too_large(self):
        """Test validation rejects chunk size above maximum"""
        config = {
            "chunk_type": ChunkType.SIMPLE.value,
            "chunk_size": CHUNK_MAX_SIZE + 1,
            "doc_column": "content",
        }
        operator = SemanticChunkerOperator(config)
        errors = []
        warnings = []
        operator.validate(errors, warnings, ["content"])

        self.assertGreater(
            len(errors), 0, "Chunk size above maximum should produce errors"
        )

    def test_validate_chunk_overlap_too_large(self):
        """Test validation rejects chunk overlap above maximum"""
        config = {
            "chunk_type": ChunkType.SIMPLE.value,
            "chunk_overlap": CHUNK_OVERLAP_MAX_SIZE + 1,
            "doc_column": "content",
        }
        operator = SemanticChunkerOperator(config)
        errors = []
        warnings = []
        operator.validate(errors, warnings, ["content"])

        self.assertGreater(
            len(errors), 0, "Chunk overlap above maximum should produce errors"
        )

    def test_validate_invalid_chunk_type(self):
        """Test validation rejects invalid chunk type"""
        config = {
            "chunk_type": "invalid_type",
            "doc_column": "content",
        }
        operator = SemanticChunkerOperator(config)
        errors = []
        warnings = []
        operator.validate(errors, warnings, ["content"])

        self.assertGreater(len(errors), 0, "Invalid chunk type should produce errors")

    def test_validate_semantic_percentile_threshold_invalid(self):
        """Test validation rejects invalid percentile threshold"""
        config = {
            "chunk_type": ChunkType.SEMANTIC.value,
            "breakpoint_threshold_type": BreakpointThresholdType.PERCENTILE.value,
            "breakpoint_threshold_amount": 150.0,  # Invalid: > 100
            "semantic_embeddings_model": "granite4",
            "doc_column": "content",
        }
        operator = SemanticChunkerOperator(config)
        errors = []
        warnings = []
        operator.validate(errors, warnings, ["content"])

        self.assertGreater(len(errors), 0, "Invalid percentile should produce errors")

    def test_validate_semantic_std_dev_threshold_negative(self):
        """Test validation rejects negative standard deviation threshold"""
        config = {
            "chunk_type": ChunkType.SEMANTIC.value,
            "breakpoint_threshold_type": BreakpointThresholdType.STANDARD_DEVIATION.value,
            "breakpoint_threshold_amount": -1.0,  # Invalid: negative
            "semantic_embeddings_model": "granite4",
            "doc_column": "content",
        }
        operator = SemanticChunkerOperator(config)
        errors = []
        warnings = []
        operator.validate(errors, warnings, ["content"])

        self.assertGreater(len(errors), 0, "Negative std dev should produce errors")


class TestSemanticChunkerEdgeCases(unittest.TestCase):
    """Test edge cases and error handling"""

    def test_empty_table(self):
        """Test chunking with an empty table"""
        data = {
            OperatorConstants.Columns.ID: [],
            OperatorConstants.Columns.NAME: [],
            "content": [],
        }
        empty_table = pa.table(data)

        config = {
            "chunk_type": ChunkType.SIMPLE.value,
            "doc_column": "content",
        }
        operator = SemanticChunkerOperator(config)

        result_tables, metadata = operator.transform(empty_table)

        # Should return empty table
        self.assertEqual(result_tables[0].num_rows, 0)
        self.assertEqual(metadata["total_docs_count"], 0)

    def test_multiple_documents(self):
        """Test chunking with multiple documents"""
        content = [
            "First document with some content.",
            "Second document with different content.",
            "Third document with unique text.",
        ]
        data = {
            OperatorConstants.Columns.ID: ["doc1", "doc2", "doc3"],
            OperatorConstants.Columns.NAME: ["Doc 1", "Doc 2", "Doc 3"],
            "content": content,
        }
        input_table = pa.table(data)

        config = {
            "chunk_type": ChunkType.SIMPLE.value,
            "chunk_size": 1000,
            "doc_column": "content",
        }
        operator = SemanticChunkerOperator(config)

        result_tables, metadata = operator.transform(input_table)
        result_table = result_tables[0]

        # Should process all documents
        self.assertEqual(result_table.num_rows, 3)
        self.assertEqual(metadata["total_docs_count"], 3)

    def test_retain_original_content(self):
        """Test that original content is retained when configured"""
        data = {
            OperatorConstants.Columns.ID: ["doc1"],
            OperatorConstants.Columns.NAME: ["Document 1"],
            "content": ["Test content for chunking."],
        }
        input_table = pa.table(data)

        config = {
            "chunk_type": ChunkType.SIMPLE.value,
            "chunk_size": 1000,
            "doc_column": "content",
            "retain_original_content": True,
        }
        operator = SemanticChunkerOperator(config)

        result_tables, metadata = operator.transform(input_table)
        result_table = result_tables[0]

        # Original content column should exist
        self.assertIn("content", result_table.column_names)
        original_content = result_table["content"][0].as_py()
        self.assertEqual(original_content, "Test content for chunking.")

    @patch("core.operators.functional.semantic_chunker.OllamaClient")
    def test_semantic_chunker_different_breakpoint_types(
        self, mock_ollama_client_class
    ):
        """Test semantic chunking with different breakpoint types - fully mocked"""
        # Mock the OllamaClient to avoid any real API calls
        mock_client = MagicMock()
        mock_client.generate_embeddings.return_value = np.random.rand(384).tolist()
        mock_ollama_client_class.return_value = mock_client

        data = {
            OperatorConstants.Columns.ID: ["doc1"],
            OperatorConstants.Columns.NAME: ["Document 1"],
            "content": ["Test content with multiple sentences. Another sentence here."],
        }
        input_table = pa.table(data)

        breakpoint_types = [
            BreakpointThresholdType.PERCENTILE.value,
            BreakpointThresholdType.STANDARD_DEVIATION.value,
            BreakpointThresholdType.INTERQUARTILE.value,
            BreakpointThresholdType.GRADIENT.value,
        ]

        for breakpoint_type in breakpoint_types:
            config = {
                "chunk_type": ChunkType.SEMANTIC.value,
                "semantic_embeddings_model": "granite4",
                "breakpoint_threshold_type": breakpoint_type,
                "doc_column": "content",
            }
            operator = SemanticChunkerOperator(config)

            result_tables, metadata = operator.transform(input_table)
            result_table = result_tables[0]

            # Should successfully process with any breakpoint type
            self.assertEqual(result_table.num_rows, 1)
            self.assertIn(
                OperatorConstants.Columns.CHUNKED_CONTENT, result_table.column_names
            )

        # Verify mock was used for all breakpoint types (no real Ollama calls)
        self.assertEqual(mock_ollama_client_class.call_count, len(breakpoint_types))
