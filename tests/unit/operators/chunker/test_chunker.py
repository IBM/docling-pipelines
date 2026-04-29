import sys
import unittest
from unittest.mock import MagicMock, Mock, patch

import numpy as np
import pyarrow as pa

# Mock langchain_experimental before any imports that might use it
if "langchain_experimental" not in sys.modules:
    sys.modules["langchain_experimental"] = Mock()
    sys.modules["langchain_experimental.text_splitter"] = Mock()

from datasift.core.constants.operator_constants import OperatorConstants
from datasift.core.operators.functional.chunker import (
    CHUNK_MAX_SIZE,
    CHUNK_MIN_SIZE,
    CHUNK_OVERLAP_MAX_SIZE,
    BreakpointThresholdType,
    ChunkerOperator,
    ChunkType,
)


class TestChunkerOperator(unittest.TestCase):
    """Test ChunkerOperator initialization and basic functionality"""

    def test_init(self):
        """Test operator initialization with simple chunking config"""
        config = {
            "chunk_type": ChunkType.SIMPLE.value,
            "chunk_size": 1000,
            "chunk_overlap": 200,
            "doc_column": "content",
        }
        operator = ChunkerOperator(config)
        self.assertIsNotNone(operator, "Chunker Operator is not None")
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
        operator = ChunkerOperator(config)
        self.assertIsNotNone(operator)
        self.assertEqual(operator.chunk_type, ChunkType.SEMANTIC.value)
        self.assertEqual(operator.semantic_embeddings_model, "granite4")
        self.assertEqual(operator.breakpoint_threshold_type, BreakpointThresholdType.PERCENTILE.value)

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
        operator = ChunkerOperator(config)

        # 3. Transform the table
        result_tables, metadata = operator.transform(input_table)
        result_table = result_tables[0]

        # 4. Perform assertions
        self.assertEqual(result_table.num_rows, 1)
        self.assertIn(OperatorConstants.Columns.CHUNKED_CONTENT, result_table.column_names)

        # Check that chunks were created
        chunked_content = result_table[OperatorConstants.Columns.CHUNKED_CONTENT][0].as_py()
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
        operator = ChunkerOperator(config)

        result_tables, metadata = operator.transform(input_table)
        result_table = result_tables[0]

        # Should create multiple chunks
        chunked_content = result_table[OperatorConstants.Columns.CHUNKED_CONTENT][0].as_py()
        self.assertGreater(len(chunked_content), 1, "Long text should create multiple chunks")

    @patch("langchain_experimental.text_splitter.SemanticChunker")
    @patch("datasift.core.operators.functional.chunker.OllamaClient")
    def test_semantic_chunking_transform(self, mock_ollama_client_class, mock_semantic_chunker_class):
        """Test semantic chunking with fully mocked Ollama client and SemanticChunker"""
        # Mock the OllamaClient to avoid any real API calls
        mock_client = MagicMock()
        # Mock generate_embeddings to return different embeddings for each call
        # This simulates semantic differences between sentences
        mock_client.generate_embeddings.side_effect = lambda text: np.random.rand(384).tolist()
        mock_ollama_client_class.return_value = mock_client

        # Mock SemanticChunker to return mock chunks
        mock_chunker = MagicMock()
        from langchain_core.documents import Document as LCDocument

        mock_chunks = [
            LCDocument(
                page_content="First topic sentence. Another first topic sentence.",
                metadata={"start_index": 0},
            ),
            LCDocument(
                page_content="Second topic sentence. Another second topic sentence.",
                metadata={"start_index": 52},
            ),
        ]
        mock_chunker.create_documents.return_value = mock_chunks
        mock_semantic_chunker_class.return_value = mock_chunker

        # Create test data
        content = [
            "First topic sentence. Another first topic sentence. Second topic sentence. Another second topic sentence."
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

        operator = ChunkerOperator(config)

        # Transform
        result_tables, metadata = operator.transform(input_table)
        result_table = result_tables[0]

        # Assertions
        self.assertEqual(result_table.num_rows, 1)
        self.assertIn(OperatorConstants.Columns.CHUNKED_CONTENT, result_table.column_names)

        # Check that chunks were created
        chunked_content = result_table[OperatorConstants.Columns.CHUNKED_CONTENT][0].as_py()
        self.assertIsNotNone(chunked_content)
        self.assertGreater(len(chunked_content), 0)

        # Verify mocks were used (no real Ollama calls or SemanticChunker)
        mock_ollama_client_class.assert_called_once()
        mock_semantic_chunker_class.assert_called_once()


def test_operator_metadata():
    """Test that operator returns correct metadata"""
    operator = ChunkerOperator({})

    operator_metadata = operator.get_metadata()

    # Check that metadata has required keys
    assert OperatorConstants.Misc.CATEGORY in operator_metadata
    assert OperatorConstants.Config.FEATURES in operator_metadata
    assert OperatorConstants.Config.ATTRIBUTES in operator_metadata
    assert operator_metadata[OperatorConstants.Misc.IS_OPERATOR_AVAILABLE] is True


class TestChunkerValidation(unittest.TestCase):
    """Test configuration validation"""

    def test_validate_chunk_size_in_range(self):
        """Test validation accepts valid chunk sizes"""
        config = {
            "chunk_type": ChunkType.SIMPLE.value,
            "chunk_size": 1000,
            "doc_column": "content",
        }
        operator = ChunkerOperator(config)
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
        operator = ChunkerOperator(config)
        errors = []
        warnings = []
        operator.validate(errors, warnings, ["content"])

        self.assertGreater(len(errors), 0, "Chunk size below minimum should produce errors")

    def test_validate_chunk_size_too_large(self):
        """Test validation rejects chunk size above maximum"""
        config = {
            "chunk_type": ChunkType.SIMPLE.value,
            "chunk_size": CHUNK_MAX_SIZE + 1,
            "doc_column": "content",
        }
        operator = ChunkerOperator(config)
        errors = []
        warnings = []
        operator.validate(errors, warnings, ["content"])

        self.assertGreater(len(errors), 0, "Chunk size above maximum should produce errors")

    def test_validate_chunk_overlap_too_large(self):
        """Test validation rejects chunk overlap above maximum"""
        config = {
            "chunk_type": ChunkType.SIMPLE.value,
            "chunk_overlap": CHUNK_OVERLAP_MAX_SIZE + 1,
            "doc_column": "content",
        }
        operator = ChunkerOperator(config)
        errors = []
        warnings = []
        operator.validate(errors, warnings, ["content"])

        self.assertGreater(len(errors), 0, "Chunk overlap above maximum should produce errors")

    def test_validate_invalid_chunk_type(self):
        """Test validation rejects invalid chunk type"""
        config = {
            "chunk_type": "invalid_type",
            "doc_column": "content",
        }
        operator = ChunkerOperator(config)
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
        operator = ChunkerOperator(config)
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
        operator = ChunkerOperator(config)
        errors = []
        warnings = []
        operator.validate(errors, warnings, ["content"])

        self.assertGreater(len(errors), 0, "Negative std dev should produce errors")


class TestChunkerEdgeCases(unittest.TestCase):
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
        operator = ChunkerOperator(config)

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
        operator = ChunkerOperator(config)

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
        operator = ChunkerOperator(config)

        result_tables, metadata = operator.transform(input_table)
        result_table = result_tables[0]

        # Original content column should exist
        self.assertIn("content", result_table.column_names)
        original_content = result_table["content"][0].as_py()
        self.assertEqual(original_content, "Test content for chunking.")

    @patch("langchain_experimental.text_splitter.SemanticChunker")
    @patch("datasift.core.operators.functional.chunker.OllamaClient")
    def test_chunker_different_breakpoint_types(self, mock_ollama_client_class, mock_semantic_chunker_class):
        """Test semantic chunking with different breakpoint types - fully mocked"""
        # Mock the OllamaClient to avoid any real API calls
        mock_client = MagicMock()
        # Mock generate_embeddings to return different embeddings for each call
        mock_client.generate_embeddings.side_effect = lambda text: np.random.rand(384).tolist()
        mock_ollama_client_class.return_value = mock_client

        # Mock SemanticChunker to return mock chunks
        mock_chunker = MagicMock()
        from langchain_core.documents import Document as LCDocument

        mock_chunks = [
            LCDocument(
                page_content="Test content with multiple sentences.",
                metadata={"start_index": 0},
            ),
            LCDocument(page_content="Another sentence here.", metadata={"start_index": 38}),
        ]
        mock_chunker.create_documents.return_value = mock_chunks
        mock_semantic_chunker_class.return_value = mock_chunker

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
            operator = ChunkerOperator(config)

            result_tables, metadata = operator.transform(input_table)
            result_table = result_tables[0]

            # Should successfully process with any breakpoint type
            self.assertEqual(result_table.num_rows, 1)
            self.assertIn(OperatorConstants.Columns.CHUNKED_CONTENT, result_table.column_names)

        # Verify mocks were used for all breakpoint types (no real Ollama calls)
        self.assertEqual(mock_ollama_client_class.call_count, len(breakpoint_types))
        self.assertEqual(mock_semantic_chunker_class.call_count, len(breakpoint_types))


class TestDoclingChunking(unittest.TestCase):
    """Test Docling chunking functionality integrated into ChunkerOperator"""

    @patch("docling_core.transforms.chunker.hybrid_chunker.HybridChunker")
    def test_docling_chunking_initialization(self, mock_hybrid_chunker_class):
        """Test operator initialization with docling chunking config"""
        # Mock the HybridChunker
        mock_chunker = MagicMock()
        mock_hybrid_chunker_class.return_value = mock_chunker

        config = {
            "chunk_type": ChunkType.HYBRID.value,
            "chunk_size": 512,
            "docling_tokenizer": "sentence-transformers/all-MiniLM-L6-v2",
            "doc_column": "content",
        }
        operator = ChunkerOperator(config)

        self.assertIsNotNone(operator)
        self.assertEqual(operator.chunk_type, ChunkType.HYBRID.value)
        self.assertEqual(operator.chunk_size, 512)
        self.assertEqual(operator.docling_tokenizer, "sentence-transformers/all-MiniLM-L6-v2")

    @patch("docling_core.transforms.chunker.hybrid_chunker.HybridChunker")
    def test_docling_chunking_transform(self, mock_hybrid_chunker_class):
        """Test docling chunking with a PyArrow table"""
        # Mock the HybridChunker and its chunk method
        mock_chunker = MagicMock()
        mock_hybrid_chunker_class.return_value = mock_chunker

        # Create mock chunks
        mock_chunk1 = MagicMock()
        mock_chunk1.text = "First chunk of text."
        mock_chunk1.start_index = 0

        mock_chunk2 = MagicMock()
        mock_chunk2.text = "Second chunk of text."
        mock_chunk2.start_index = 100

        mock_chunker.chunk.return_value = iter([mock_chunk1, mock_chunk2])

        # Create test data
        content = ["This is a test document with some content. It has multiple sentences. This helps test chunking."]
        data = {
            OperatorConstants.Columns.ID: ["doc1"],
            OperatorConstants.Columns.NAME: ["Document 1"],
            "content": content,
        }
        input_table = pa.table(data)

        # Create operator with docling chunking
        config = {
            "chunk_type": ChunkType.HYBRID.value,
            "chunk_size": 512,
            "docling_tokenizer": "sentence-transformers/all-MiniLM-L6-v2",
            "doc_column": "content",
        }
        operator = ChunkerOperator(config)

        # Transform
        result_tables, metadata = operator.transform(input_table)
        result_table = result_tables[0]

        # Assertions
        self.assertEqual(result_table.num_rows, 1)
        self.assertIn(OperatorConstants.Columns.CHUNKED_CONTENT, result_table.column_names)

        # Check that chunks were created
        chunked_content = result_table[OperatorConstants.Columns.CHUNKED_CONTENT][0].as_py()
        self.assertIsNotNone(chunked_content)
        self.assertGreater(len(chunked_content), 0)

    def test_docling_validation_chunk_size_valid(self):
        """Test validation accepts valid chunk size for docling"""
        config = {
            "chunk_type": ChunkType.HYBRID.value,
            "chunk_size": 512,
            "doc_column": "content",
        }
        operator = ChunkerOperator(config)
        errors = []
        warnings = []
        operator.validate(errors, warnings, ["content"])

        self.assertEqual(len(errors), 0, "Valid chunk size should not produce errors")

    def test_docling_validation_chunk_size_too_small(self):
        """Test validation rejects chunk size below minimum for hybrid chunking (100 tokens)"""
        config = {
            "chunk_type": ChunkType.HYBRID.value,
            "chunk_size": 50,  # Below DOCLING_CHUNK_SIZE_MIN (100)
            "doc_column": "content",
        }
        operator = ChunkerOperator(config)
        errors = []
        warnings = []
        operator.validate(errors, warnings, ["content"])

        self.assertGreater(len(errors), 0, "Chunk size below minimum should produce errors")

    def test_docling_validation_chunk_size_too_large(self):
        """Test validation rejects chunk size above maximum for docling (2048 tokens)"""
        config = {
            "chunk_type": ChunkType.HYBRID.value,
            "chunk_size": 3000,  # Above DOCLING_CHUNK_SIZE_MAX (2048)
            "doc_column": "content",
        }
        operator = ChunkerOperator(config)
        errors = []
        warnings = []
        operator.validate(errors, warnings, ["content"])

        self.assertGreater(len(errors), 0, "Chunk size above maximum should produce errors")

    @patch("docling_core.transforms.chunker.hybrid_chunker.HybridChunker")
    def test_docling_multiple_documents(self, mock_hybrid_chunker_class):
        """Test docling chunking with multiple documents"""
        # Mock the HybridChunker
        mock_chunker = MagicMock()
        mock_hybrid_chunker_class.return_value = mock_chunker

        # Create mock chunks
        mock_chunk1 = MagicMock()
        mock_chunk1.text = "Chunk text."
        mock_chunk1.start_index = 0

        mock_chunker.chunk.return_value = iter([mock_chunk1])

        content = [
            "First document with short content.",
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
            "chunk_type": ChunkType.HYBRID.value,
            "chunk_size": 512,
            "doc_column": "content",
        }
        operator = ChunkerOperator(config)

        result_tables, metadata = operator.transform(input_table)
        result_table = result_tables[0]

        # Should process all documents
        self.assertEqual(result_table.num_rows, 3)
        self.assertEqual(metadata["total_docs_count"], 3)

    @patch("docling_core.transforms.chunker.hybrid_chunker.HybridChunker")
    def test_docling_retain_original_content(self, mock_hybrid_chunker_class):
        """Test that original content is retained when configured for docling"""
        mock_chunker = MagicMock()
        mock_hybrid_chunker_class.return_value = mock_chunker

        mock_chunk = MagicMock()
        mock_chunk.text = "Chunk text."
        mock_chunk.start_index = 0
        mock_chunker.chunk.return_value = iter([mock_chunk])

        data = {
            OperatorConstants.Columns.ID: ["doc1"],
            OperatorConstants.Columns.NAME: ["Document 1"],
            "content": ["Test content for chunking."],
        }
        input_table = pa.table(data)

        config = {
            "chunk_type": ChunkType.HYBRID.value,
            "chunk_size": 512,
            "doc_column": "content",
            "retain_original_content": True,
        }
        operator = ChunkerOperator(config)

        result_tables, metadata = operator.transform(input_table)
        result_table = result_tables[0]

        # Original content column should exist
        self.assertIn("content", result_table.column_names)
        original_content = result_table["content"][0].as_py()
        self.assertEqual(original_content, "Test content for chunking.")

    @patch("docling_core.transforms.chunker.hybrid_chunker.HybridChunker")
    def test_docling_remove_original_content(self, mock_hybrid_chunker_class):
        """Test that original content is removed when configured for docling"""
        mock_chunker = MagicMock()
        mock_hybrid_chunker_class.return_value = mock_chunker

        mock_chunk = MagicMock()
        mock_chunk.text = "Chunk text."
        mock_chunk.start_index = 0
        mock_chunker.chunk.return_value = iter([mock_chunk])

        data = {
            OperatorConstants.Columns.ID: ["doc1"],
            OperatorConstants.Columns.NAME: ["Document 1"],
            "content": ["Test content for chunking."],
        }
        input_table = pa.table(data)

        config = {
            "chunk_type": ChunkType.HYBRID.value,
            "chunk_size": 512,
            "doc_column": "content",
            "retain_original_content": False,
        }
        operator = ChunkerOperator(config)

        result_tables, metadata = operator.transform(input_table)
        result_table = result_tables[0]

        # Original content column should be removed
        self.assertNotIn("content", result_table.column_names)

    @patch("docling_core.transforms.chunker.hybrid_chunker.HybridChunker")
    def test_docling_empty_content(self, mock_hybrid_chunker_class):
        """Test docling handles empty content gracefully"""
        mock_chunker = MagicMock()
        mock_hybrid_chunker_class.return_value = mock_chunker
        mock_chunker.chunk.return_value = iter([])

        data = {
            OperatorConstants.Columns.ID: ["doc1"],
            OperatorConstants.Columns.NAME: ["Empty Document"],
            "content": [""],
        }
        input_table = pa.table(data)

        config = {
            "chunk_type": ChunkType.HYBRID.value,
            "chunk_size": 512,
            "doc_column": "content",
        }
        operator = ChunkerOperator(config)

        result_tables, metadata = operator.transform(input_table)

        # Should record as failed document
        self.assertGreater(metadata.get("failed_docs_count", 0), 0)

    @patch("docling_core.transforms.chunker.hybrid_chunker.HybridChunker")
    def test_docling_long_document(self, mock_hybrid_chunker_class):
        """Test docling with long document requiring multiple chunks"""
        mock_chunker = MagicMock()
        mock_hybrid_chunker_class.return_value = mock_chunker

        # Create multiple mock chunks
        mock_chunks = []
        for i in range(5):
            mock_chunk = MagicMock()
            mock_chunk.text = f"Chunk {i} text."
            mock_chunk.start_index = i * 100
            mock_chunks.append(mock_chunk)

        mock_chunker.chunk.return_value = iter(mock_chunks)

        long_text = "This is a sentence. " * 200  # ~4000 chars
        data = {
            OperatorConstants.Columns.ID: ["doc1"],
            OperatorConstants.Columns.NAME: ["Long Document"],
            "content": [long_text],
        }
        input_table = pa.table(data)

        config = {
            "chunk_type": ChunkType.HYBRID.value,
            "chunk_size": 512,
            "doc_column": "content",
        }
        operator = ChunkerOperator(config)

        result_tables, metadata = operator.transform(input_table)
        result_table = result_tables[0]

        # Check that multiple chunks were created
        chunked_content = result_table[OperatorConstants.Columns.CHUNKED_CONTENT][0].as_py()
        self.assertGreater(len(chunked_content), 1, "Long document should create multiple chunks")

    @patch("docling_core.transforms.chunker.hybrid_chunker.HybridChunker")
    def test_docling_preserves_all_columns(self, mock_hybrid_chunker_class):
        """Test docling preserves all original columns"""
        mock_chunker = MagicMock()
        mock_hybrid_chunker_class.return_value = mock_chunker

        mock_chunk = MagicMock()
        mock_chunk.text = "Chunk text."
        mock_chunk.start_index = 0
        mock_chunker.chunk.return_value = iter([mock_chunk])

        data = {
            OperatorConstants.Columns.ID: ["doc1"],
            OperatorConstants.Columns.NAME: ["Document 1"],
            "content": ["Test content"],
            "extra_col1": ["value1"],
            "extra_col2": [42],
        }
        input_table = pa.table(data)

        config = {
            "chunk_type": ChunkType.HYBRID.value,
            "chunk_size": 512,
            "doc_column": "content",
        }
        operator = ChunkerOperator(config)

        result_tables, metadata = operator.transform(input_table)
        result_table = result_tables[0]

        # All original columns should be preserved
        self.assertIn("extra_col1", result_table.column_names)
        self.assertIn("extra_col2", result_table.column_names)

    @patch("docling_core.transforms.chunker.hybrid_chunker.HybridChunker")
    def test_docling_with_special_characters(self, mock_hybrid_chunker_class):
        """Test docling handles special characters in content"""
        mock_chunker = MagicMock()
        mock_hybrid_chunker_class.return_value = mock_chunker

        mock_chunk = MagicMock()
        mock_chunk.text = "Special chars chunk."
        mock_chunk.start_index = 0
        mock_chunker.chunk.return_value = iter([mock_chunk])

        data = {
            OperatorConstants.Columns.ID: ["doc1"],
            OperatorConstants.Columns.NAME: ["Special Doc"],
            "content": ["Content with special chars: @#$%^&*()_+-=[]{}|;':\",./<>?"],
        }
        input_table = pa.table(data)

        config = {
            "chunk_type": ChunkType.HYBRID.value,
            "chunk_size": 512,
            "doc_column": "content",
        }
        operator = ChunkerOperator(config)

        result_tables, metadata = operator.transform(input_table)

        # Should process successfully
        self.assertEqual(metadata["total_docs_count"], 1)

    @patch("docling_core.transforms.chunker.hybrid_chunker.HybridChunker")
    def test_docling_with_unicode(self, mock_hybrid_chunker_class):
        """Test docling handles Unicode characters"""
        mock_chunker = MagicMock()
        mock_hybrid_chunker_class.return_value = mock_chunker

        mock_chunk = MagicMock()
        mock_chunk.text = "Unicode chunk."
        mock_chunk.start_index = 0
        mock_chunker.chunk.return_value = iter([mock_chunk])

        data = {
            OperatorConstants.Columns.ID: ["doc1"],
            OperatorConstants.Columns.NAME: ["Unicode Doc"],
            "content": ["Content with Unicode: 你好世界 مرحبا العالم Привет мир"],
        }
        input_table = pa.table(data)

        config = {
            "chunk_type": ChunkType.HYBRID.value,
            "chunk_size": 512,
            "doc_column": "content",
        }
        operator = ChunkerOperator(config)

        result_tables, metadata = operator.transform(input_table)

        # Should process successfully
        self.assertEqual(metadata["total_docs_count"], 1)

    def test_docling_validation_chunk_overlap_negative(self):
        """Test validation rejects negative chunk overlap for docling"""
        config = {
            "chunk_type": ChunkType.HYBRID.value,
            "chunk_size": 512,
            "chunk_overlap": -10,
            "doc_column": "content",
        }
        operator = ChunkerOperator(config)
        errors = []
        warnings = []
        operator.validate(errors, warnings, ["content"])

        self.assertGreater(len(errors), 0, "Negative chunk overlap should produce errors")

    def test_docling_validation_chunk_overlap_exceeds_size(self):
        """Test validation rejects chunk overlap >= chunk_size for docling"""
        config = {
            "chunk_type": ChunkType.HYBRID.value,
            "chunk_size": 512,
            "chunk_overlap": 512,
            "doc_column": "content",
        }
        operator = ChunkerOperator(config)
        errors = []
        warnings = []
        operator.validate(errors, warnings, ["content"])

        self.assertGreater(len(errors), 0, "Chunk overlap >= chunk_size should produce errors")

    def test_docling_validation_empty_tokenizer(self):
        """Test validation rejects empty tokenizer for docling"""
        config = {
            "chunk_type": ChunkType.HYBRID.value,
            "chunk_size": 512,
            "docling_tokenizer": "",
            "doc_column": "content",
        }
        operator = ChunkerOperator(config)
        errors = []
        warnings = []
        operator.validate(errors, warnings, ["content"])

        self.assertGreater(len(errors), 0, "Empty tokenizer should produce errors")
