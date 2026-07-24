import unittest
from unittest.mock import MagicMock, Mock, patch

import numpy as np
import pyarrow as pa

# langchain_experimental is mocked in conftest.py at collection time.
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.functional.chunker import (
    CHUNK_MAX_SIZE,
    CHUNK_MIN_SIZE,
    CHUNK_OVERLAP_MAX_SIZE,
    BreakpointThresholdType,
    ChunkerOperator,
    ChunkType,
)
from docpipe.exceptions.docpipe_exceptions import DocpipeException


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
        self.assertFalse(operator.retain_original_content)

    def test_init_without_chunk_type_uses_default(self):
        """Test operator initialization without chunk_type uses default 'simple'"""
        config = {
            "chunk_size": 1000,
            "chunk_overlap": 200,
            "doc_column": "content",
        }
        operator = ChunkerOperator(config)
        self.assertIsNotNone(operator, "Chunker Operator is not None")
        self.assertEqual(operator.chunk_type, ChunkType.SIMPLE.value, "Should default to 'simple' chunk type")
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
        }
        operator = ChunkerOperator(config)

        # 3. Transform the table
        result_tables, _metadata = operator.transform(input_table)
        result_table = result_tables[0]

        # 4. Perform assertions
        self.assertEqual(result_table.num_rows, 1)
        self.assertIn(OperatorConstants.Columns.CHUNKED_CONTENT, result_table.column_names)
        self.assertNotIn("content", result_table.column_names)

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

        result_tables, _metadata = operator.transform(input_table)
        result_table = result_tables[0]

        # Should create multiple chunks
        chunked_content = result_table[OperatorConstants.Columns.CHUNKED_CONTENT][0].as_py()
        self.assertGreater(len(chunked_content), 1, "Long text should create multiple chunks")

    @patch("langchain_experimental.text_splitter.SemanticChunker")
    @patch("docpipe.core.operators.functional.chunker.OllamaClient")
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
        result_tables, _metadata = operator.transform(input_table)
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

    @patch("docpipe.core.operators.functional.chunker.OllamaClient")
    def test_chunker_provider_config_host(self, mock_ollama_client_class):
        """Test that host in the provider_config is passed to OllamaClient."""
        mock_client_instance = MagicMock()
        mock_ollama_client_class.return_value = mock_client_instance

        config = {
            "chunk_type": "semantic",
            "semantic_embeddings_model": "nomic-embed-text",
            "provider_config": {
                "host": "http://test.server.com:11434",
            },
        }
        operator = ChunkerOperator(config)
        operator._get_ollama_client()

        mock_ollama_client_class.assert_called_once()
        call_kwargs = mock_ollama_client_class.call_args.kwargs
        assert call_kwargs["model_name"] == "nomic-embed-text", "Model name mismatch"
        assert call_kwargs["host"] == "http://test.server.com:11434", "Host not passed correctly"


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

    def test_validate_chunk_size_string_type(self):
        """Test validation rejects chunk_size with string type"""
        config = {
            "chunk_type": ChunkType.SIMPLE.value,
            "chunk_size": "1000",  # String instead of int
            "doc_column": "content",
        }
        operator = ChunkerOperator(config)
        errors = []
        warnings = []
        operator.validate(errors, warnings, ["content"])

        self.assertGreater(len(errors), 0, "String type for chunk_size should produce errors")
        # Check that the error message mentions the type issue
        error_messages = [str(e) for e in errors]
        self.assertTrue(
            any("Invalid type for chunk_size" in msg for msg in error_messages),
            f"Expected type error for chunk_size, got: {error_messages}",
        )

    def test_validate_chunk_overlap_string_type(self):
        """Test validation rejects chunk_overlap with string type"""
        config = {
            "chunk_type": ChunkType.SIMPLE.value,
            "chunk_size": 1000,
            "chunk_overlap": "200",  # String instead of int
            "doc_column": "content",
        }
        operator = ChunkerOperator(config)
        errors = []
        warnings = []
        operator.validate(errors, warnings, ["content"])

        self.assertGreater(len(errors), 0, "String type for chunk_overlap should produce errors")
        # Check that the error message mentions the type issue
        error_messages = [str(e) for e in errors]
        self.assertTrue(
            any("Invalid type for chunk_overlap" in msg for msg in error_messages),
            f"Expected type error for chunk_overlap, got: {error_messages}",
        )

    def test_validate_retain_original_content_string_type(self):
        """Test validation rejects retain_original_content with string type"""
        config = {
            "chunk_type": ChunkType.SIMPLE.value,
            "chunk_size": 1000,
            "chunk_overlap": 200,
            "retain_original_content": "true",  # String instead of bool
            "doc_column": "content",
        }
        operator = ChunkerOperator(config)
        errors = []
        warnings = []
        operator.validate(errors, warnings, ["content"])

        self.assertGreater(len(errors), 0, "String type for retain_original_content should produce errors")
        # Check that the error message mentions the type issue
        error_messages = [str(e) for e in errors]
        self.assertTrue(
            any("Invalid type for retain_original_content" in msg for msg in error_messages),
            f"Expected type error for retain_original_content, got: {error_messages}",
        )

    def test_validate_multiple_errors_collected(self):
        """Test that multiple validation errors are collected without early return"""
        config = {
            "chunk_type": "invalid_type",  # Invalid chunk_type
            "chunk_size": 1000,
            "chunk_overlap": -1,  # Invalid: negative
            "doc_column": "content",
        }
        operator = ChunkerOperator(config)
        errors = []
        warnings = []
        operator.validate(errors, warnings, ["content"])

        # Should have at least 2 errors: one for chunk_overlap and one for chunk_type
        self.assertGreaterEqual(len(errors), 2, f"Should collect multiple errors, got {len(errors)}: {errors}")

        # Verify both error types are present
        error_messages = " ".join(str(e) for e in errors)
        self.assertIn("chunk_overlap", error_messages.lower(), "Should have chunk_overlap error")
        self.assertIn("chunk_type", error_messages.lower(), "Should have chunk_type error")

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

    def test_validate_semantic_missing_embeddings_model(self):
        """Test validation rejects semantic chunking without embeddings model"""
        config = {
            "chunk_type": ChunkType.SEMANTIC.value,
            "doc_column": "content",
            # Missing semantic_embeddings_model
        }
        operator = ChunkerOperator(config)
        errors = []
        warnings = []
        operator.validate(errors, warnings, ["content"])

        self.assertGreater(len(errors), 0, "Semantic chunking without embeddings model should produce errors")
        # Verify the error message mentions the missing model
        error_messages = " ".join(errors)
        self.assertIn("semantic_embeddings_model", error_messages.lower())

    def test_validate_semantic_multiple_errors(self):
        """Test validation collects multiple semantic chunking errors at once"""
        config = {
            "chunk_type": ChunkType.SEMANTIC.value,
            "doc_column": "content",
            # Missing semantic_embeddings_model
            "breakpoint_threshold_type": BreakpointThresholdType.PERCENTILE.value,
            "breakpoint_threshold_amount": 150,  # Invalid: must be 0-100 for percentile
        }
        operator = ChunkerOperator(config)
        errors = []
        warnings = []
        operator.validate(errors, warnings, ["content"])

        # Should catch both errors: missing model AND invalid threshold
        self.assertEqual(len(errors), 2, "Should catch both missing model and invalid threshold errors")
        error_messages = " ".join(errors)
        self.assertIn("semantic_embeddings_model", error_messages.lower())
        self.assertIn("percentile", error_messages.lower())


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

    def test_default_removes_original_content(self):
        """Test that original content is removed by default"""
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
        }
        operator = ChunkerOperator(config)

        result_tables, _metadata = operator.transform(input_table)
        result_table = result_tables[0]

        self.assertNotIn("content", result_table.column_names)

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

        result_tables, _metadata = operator.transform(input_table)
        result_table = result_tables[0]

        self.assertIn("content", result_table.column_names)
        original_content = result_table["content"][0].as_py()
        self.assertEqual(original_content, "Test content for chunking.")

    @patch("langchain_experimental.text_splitter.SemanticChunker")
    @patch("docpipe.core.operators.functional.chunker.OllamaClient")
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

            result_tables, _metadata = operator.transform(input_table)
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
        result_tables, _metadata = operator.transform(input_table)
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
    def test_docling_default_removes_original_content(self, mock_hybrid_chunker_class):
        """Test that original content is removed by default for docling"""
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
        }
        operator = ChunkerOperator(config)

        result_tables, _metadata = operator.transform(input_table)
        result_table = result_tables[0]

        self.assertNotIn("content", result_table.column_names)

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

        result_tables, _metadata = operator.transform(input_table)
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

        result_tables, _metadata = operator.transform(input_table)
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

        _result_tables, metadata = operator.transform(input_table)

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

        result_tables, _metadata = operator.transform(input_table)
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

        result_tables, _metadata = operator.transform(input_table)
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

        _result_tables, metadata = operator.transform(input_table)

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

        _result_tables, metadata = operator.transform(input_table)

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
        """Test validation rejects empty tokenizer and negative chunk_overlap for docling"""
        config = {
            "chunk_type": ChunkType.HYBRID.value,
            "chunk_size": 512,
            "chunk_overlap": -1,  # Invalid: negative
            "docling_tokenizer": "",  # Invalid: empty
            "doc_column": "content",
        }
        operator = ChunkerOperator(config)
        errors = []
        warnings = []
        operator.validate(errors, warnings, ["content"])

        # Should have exactly 2 errors:
        # 1. chunk_overlap must be non-negative (from common validation)
        # 2. docling_tokenizer cannot be empty for hybrid chunking
        self.assertEqual(len(errors), 2, f"Should have exactly 2 errors, got {len(errors)}: {errors}")

        # Verify both types of errors are present
        error_messages = " ".join(errors)
        self.assertIn("docling_tokenizer", error_messages.lower())
        self.assertIn("chunk_overlap", error_messages.lower())


class TestChunkerSummarization(unittest.TestCase):
    """Test Chunker summarization functionality with multi-provider support"""

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory")
    def test_summarization_initialization_litellm(self, mock_factory):
        """Test operator initialization with LiteLLM summarization config"""
        mock_adapter = MagicMock()
        mock_factory.create_inference_adapter.return_value = mock_adapter

        config = {
            "chunk_type": ChunkType.SIMPLE.value,
            "chunk_size": 1000,
            "doc_column": "content",
            "summarization": {
                "provider": "litellm",
                "provider_config": {
                    "model_id": "llama3.2:3b",
                    "api_base": "http://localhost:11434/v1",
                    "api_key": "<api-key>",
                },
            },
        }
        operator = ChunkerOperator(config)

        self.assertTrue(operator.enable_summarization)
        self.assertEqual(operator.summarization_provider, "litellm")
        self.assertEqual(operator.summarization_model, "openai/llama3.2:3b")

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory")
    def test_summarization_initialization_watsonx(self, mock_factory):
        """Test operator initialization with WatsonX summarization config (nested structure)"""
        mock_adapter = MagicMock()
        mock_factory.create_inference_adapter.return_value = mock_adapter

        config = {
            "chunk_type": ChunkType.SIMPLE.value,
            "chunk_size": 1000,
            "doc_column": "content",
            "summarization": {
                "provider": "watsonx",
                "provider_config": {
                    "model_id": "ibm/granite-13b-chat-v2",
                    "api_key": "<api-key>",
                    "project_id": "test_project",
                },
            },
        }
        operator = ChunkerOperator(config)

        self.assertTrue(operator.enable_summarization)
        self.assertEqual(operator.summarization_provider, "watsonx")
        self.assertEqual(operator.summarization_model, "ibm/granite-13b-chat-v2")

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory")
    def test_summarization_initialization_flat_config_backward_compat(self, mock_factory):
        """Test backward compatibility with flat config structure"""
        mock_adapter = MagicMock()
        mock_factory.create_inference_adapter.return_value = mock_adapter

        # Nested structure is now the only supported format
        config = {
            "chunk_type": ChunkType.SIMPLE.value,
            "chunk_size": 1000,
            "doc_column": "content",
            "summarization": {
                "provider": "litellm",
                "provider_config": {
                    "model_id": "llama3.2:3b",
                    "api_base": "http://localhost:11434/v1",
                    "api_key": "<api-key>",
                },
            },
        }
        operator = ChunkerOperator(config)

        self.assertTrue(operator.enable_summarization)
        self.assertEqual(operator.summarization_provider, "litellm")
        self.assertEqual(operator.summarization_model, "openai/llama3.2:3b")

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory")
    def test_summarization_backward_compatibility(self, mock_factory):
        """Test auto-configuration when provider_config is empty"""
        mock_adapter = MagicMock()
        mock_factory.create_inference_adapter.return_value = mock_adapter

        # Config with enabled but empty provider_config triggers auto-configuration
        config = {
            "chunk_type": ChunkType.SIMPLE.value,
            "chunk_size": 1000,
            "doc_column": "content",
            "summarization": {
                "provider": "litellm",
                "provider_config": {},  # Empty dict triggers auto-config
            },
        }
        operator = ChunkerOperator(config)

        # Should auto-configure with Ollama defaults
        self.assertTrue(operator.enable_summarization)
        self.assertEqual(operator.summarization_provider, "litellm")
        self.assertEqual(operator.summarization_model, "openai/granite4")  # Default model with prefix
        self.assertEqual(operator.summarization_provider_config["api_base"], "http://localhost:11434/v1")
        self.assertEqual(operator.summarization_provider_config["api_key"], "<ollama>")

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory")
    def test_summarization_model_auto_prefix(self, mock_factory):
        """Test automatic prefixing of model names with 'openai/' for LiteLLM"""
        mock_adapter = MagicMock()
        mock_factory.create_inference_adapter.return_value = mock_adapter

        # Model without prefix
        config = {
            "chunk_type": ChunkType.SIMPLE.value,
            "doc_column": "content",
            "summarization": {"provider": "litellm", "model_id": "granite4"},
        }
        operator = ChunkerOperator(config)
        self.assertEqual(operator.summarization_model, "openai/granite4")

        # Model already with prefix
        config["summarization"]["model_id"] = "openai/granite4"
        operator = ChunkerOperator(config)
        self.assertEqual(operator.summarization_model, "openai/granite4")

    def test_summarization_disabled_by_default(self):
        """Test that summarization is disabled by default"""
        config = {"chunk_type": ChunkType.SIMPLE.value, "chunk_size": 1000, "doc_column": "content"}
        operator = ChunkerOperator(config)

        self.assertFalse(operator.enable_summarization)
        self.assertIsNone(operator._summarization_service)

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory")
    def test_summarization_lazy_initialization(self, mock_factory):
        """Test that summarization service is lazily initialized during transform() when summarization is enabled"""
        mock_adapter = MagicMock()
        mock_adapter.chat.return_value = "Summary text."
        mock_factory.create_inference_adapter.return_value = mock_adapter

        # Summarization disabled - service should not be created
        config = {"chunk_type": ChunkType.SIMPLE.value, "doc_column": "content", "summarization": {}}
        operator = ChunkerOperator(config)
        self.assertIsNone(operator._summarization_service)
        mock_factory.create_inference_adapter.assert_not_called()

        # Summarization enabled - service should be lazily created during transform()
        config["summarization"]["provider"] = "litellm"
        config["summarization"]["model_id"] = "granite4"
        operator = ChunkerOperator(config)
        # Service is NOT created during __init__ - it's lazy
        self.assertIsNone(operator._summarization_service)
        mock_factory.create_inference_adapter.assert_not_called()

        # Now call transform() to trigger lazy initialization
        content = ["This is a test document with some content."]
        data = {
            OperatorConstants.Columns.ID: ["doc1"],
            OperatorConstants.Columns.NAME: ["Document 1"],
            "content": content,
        }
        input_table = pa.table(data)
        operator.transform(input_table)

        # After transform(), service should be initialized
        self.assertIsNotNone(operator._summarization_service)
        mock_factory.create_inference_adapter.assert_called_once()

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory")
    def test_summarization_with_chunking(self, mock_factory):
        """Test summarization integrated with chunking"""
        mock_adapter = MagicMock()
        mock_adapter.chat.return_value = "This is a summary of the chunk."
        mock_factory.create_inference_adapter.return_value = mock_adapter

        content = ["This is a test document. " * 50]  # Long enough to create chunks
        data = {
            OperatorConstants.Columns.ID: ["doc1"],
            OperatorConstants.Columns.NAME: ["Document 1"],
            "content": content,
        }
        input_table = pa.table(data)

        config = {
            "chunk_type": ChunkType.SIMPLE.value,
            "chunk_size": 500,
            "chunk_overlap": 100,
            "doc_column": "content",
            "summarization": {"provider": "litellm", "model_id": "granite4"},
        }
        operator = ChunkerOperator(config)

        result_tables, _metadata = operator.transform(input_table)
        result_table = result_tables[0]

        # Should have chunks with summaries
        self.assertEqual(result_table.num_rows, 1)
        chunked_content = result_table[OperatorConstants.Columns.CHUNKED_CONTENT][0].as_py()
        self.assertGreater(len(chunked_content), 0)

        # Verify LLM was called for summarization
        self.assertGreater(mock_adapter.chat.call_count, 0)

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory")
    def test_summarization_parameters(self, mock_factory):
        """Test summarization with custom parameters"""
        mock_adapter = MagicMock()
        mock_adapter.chat.return_value = "Summary text."
        mock_factory.create_inference_adapter.return_value = mock_adapter

        config = {
            "chunk_type": ChunkType.SIMPLE.value,
            "chunk_size": 1000,
            "doc_column": "content",
            "summarization": {
                "provider": "litellm",
                "provider_config": {"model_id": "granite4"},
                "max_input_tokens": 4000,
                "overlap_ratio": 0.3,
                "summary_sentences": 3,
                "summary_max_words": 30,
            },
        }
        operator = ChunkerOperator(config)

        self.assertEqual(operator.max_length, 4000)
        self.assertEqual(operator.overlap_ratio, 0.3)
        self.assertEqual(operator.summary_sentences, 3)
        self.assertEqual(operator.summary_max_words, 30)

    def test_summarization_validation_max_input_tokens(self):
        """Test validation of max_input_tokens parameter"""
        # Valid range
        config = {
            "chunk_type": ChunkType.SIMPLE.value,
            "doc_column": "content",
            "summarization": {"provider": "litellm", "max_input_tokens": 8000},
        }
        operator = ChunkerOperator(config)
        errors = []
        warnings = []
        operator.validate(errors, warnings, ["content"])
        self.assertEqual(len(errors), 0)

        # Below minimum
        config["summarization"]["max_input_tokens"] = 500
        operator = ChunkerOperator(config)
        errors = []
        warnings = []
        operator.validate(errors, warnings, ["content"])
        self.assertGreater(len(errors), 0)

        # Above maximum
        config["summarization"]["max_input_tokens"] = 40000
        operator = ChunkerOperator(config)
        errors = []
        warnings = []
        operator.validate(errors, warnings, ["content"])
        self.assertGreater(len(errors), 0)

    def test_summarization_validation_summary_sentences(self):
        """Test validation of summary_sentences parameter"""
        # Valid range
        config = {
            "chunk_type": ChunkType.SIMPLE.value,
            "doc_column": "content",
            "summarization": {"provider": "litellm", "summary_sentences": 3},
        }
        operator = ChunkerOperator(config)
        errors = []
        warnings = []
        operator.validate(errors, warnings, ["content"])
        self.assertEqual(len(errors), 0)

        # Below minimum
        config["summarization"]["summary_sentences"] = 0
        operator = ChunkerOperator(config)
        errors = []
        warnings = []
        operator.validate(errors, warnings, ["content"])
        self.assertGreater(len(errors), 0)

        # Above maximum
        config["summarization"]["summary_sentences"] = 10
        operator = ChunkerOperator(config)
        errors = []
        warnings = []
        operator.validate(errors, warnings, ["content"])
        self.assertGreater(len(errors), 0)

    def test_summarization_validation_summary_max_words(self):
        """Test validation of summary_max_words parameter"""
        # Valid range
        config = {
            "chunk_type": ChunkType.SIMPLE.value,
            "doc_column": "content",
            "summarization": {"provider": "litellm", "summary_max_words": 50},
        }
        operator = ChunkerOperator(config)
        errors = []
        warnings = []
        operator.validate(errors, warnings, ["content"])
        self.assertEqual(len(errors), 0)

        # Below minimum
        config["summarization"]["summary_max_words"] = 5
        operator = ChunkerOperator(config)
        errors = []
        warnings = []
        operator.validate(errors, warnings, ["content"])
        self.assertGreater(len(errors), 0)

        # Above maximum
        config["summary_max_words"] = 150
        operator = ChunkerOperator(config)
        errors = []
        warnings = []
        operator.validate(errors, warnings, ["content"])
        self.assertGreater(len(errors), 0)

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory")
    def test_summarization_graceful_failure(self, mock_factory):
        """Test that summarization failures are handled gracefully"""
        mock_adapter = MagicMock()
        mock_adapter.chat.side_effect = Exception("LLM service unavailable")
        mock_factory.create_inference_adapter.return_value = mock_adapter

        content = ["This is a test document with some content."]
        data = {
            OperatorConstants.Columns.ID: ["doc1"],
            OperatorConstants.Columns.NAME: ["Document 1"],
            "content": content,
        }
        input_table = pa.table(data)

        config = {
            "chunk_type": ChunkType.SIMPLE.value,
            "chunk_size": 1000,
            "doc_column": "content",
            "summarization": {"provider": "litellm", "model_id": "granite4"},
        }
        operator = ChunkerOperator(config)

        # Should not raise exception, but handle gracefully
        result_tables, _metadata = operator.transform(input_table)
        result_table = result_tables[0]

        # Should still produce chunks even if summarization fails
        self.assertEqual(result_table.num_rows, 1)
        self.assertIn(OperatorConstants.Columns.CHUNKED_CONTENT, result_table.column_names)

    def test_summarization_metadata(self):
        """Test that summarization parameters are included in metadata"""
        config = {
            "chunk_type": ChunkType.SIMPLE.value,
            "doc_column": "content",
            "summarization": {
                "provider": "litellm",
                "provider_config": {"model_id": "granite4"},
            },
        }
        operator = ChunkerOperator(config)
        metadata = operator.get_metadata()

        # Check that summarization attributes are in metadata
        # attributes is a dict, not a list
        attributes = metadata["attributes"]
        self.assertIsInstance(attributes, dict)

        # Check that summarization nested structure is present
        self.assertIn("summarization", attributes)
        summarization = attributes["summarization"]
        self.assertIn("properties", summarization)

        # Check nested properties
        props = summarization["properties"]
        self.assertIn("provider", props)
        self.assertIn("provider_config", props)
        self.assertIn("max_input_tokens", props)
        self.assertIn("summary_sentences", props)
        self.assertIn("summary_max_words", props)

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory")
    def test_summarization_empty_document(self, mock_factory):
        """Test summarization with empty document"""
        mock_adapter = MagicMock()
        mock_factory.create_inference_adapter.return_value = mock_adapter

        data = {
            OperatorConstants.Columns.ID: ["doc1"],
            OperatorConstants.Columns.NAME: ["Empty Document"],
            "content": [""],
        }
        input_table = pa.table(data)

        config = {
            "chunk_type": ChunkType.SIMPLE.value,
            "doc_column": "content",
            "summarization": {"provider": "litellm", "model_id": "granite4"},
        }
        operator = ChunkerOperator(config)

        _result_tables, metadata = operator.transform(input_table)

        # Should handle empty content gracefully
        self.assertEqual(metadata["total_docs_count"], 1)
        # LLM should not be called for empty content

    def test_summarization_service_validation_called_on_init(self):
        """Test that validate() is called during summarization service initialization."""
        from docpipe.core.operators.functional.summarization_service import SummarizationService

        mock_adapter = MagicMock()
        mock_adapter.validate.return_value = {"valid": True, "errors": [], "warnings": []}

        _ = SummarizationService(llm_adapter=mock_adapter)

        # Verify adapter was validated
        mock_adapter.validate.assert_called_once()

    def test_summarization_service_validation_failure_raises_error(self):
        """Test that validation failures raise DocpipeException."""
        from docpipe.core.operators.functional.summarization_service import SummarizationService

        mock_adapter = MagicMock()
        mock_adapter.validate.return_value = {"valid": False, "errors": ["API key is required"], "warnings": []}

        with self.assertRaises(DocpipeException) as context:
            SummarizationService(llm_adapter=mock_adapter)

        self.assertIn("API key is required", str(context.exception))

    def test_summarization_service_validation_with_warnings(self):
        """Test that warnings don't block service initialization."""
        from docpipe.core.operators.functional.summarization_service import SummarizationService

        mock_adapter = MagicMock()
        mock_adapter.validate.return_value = {
            "valid": True,
            "errors": [],
            "warnings": ["Consider setting api_base for better performance"],
        }

        service = SummarizationService(llm_adapter=mock_adapter)

        # Service should be created successfully
        self.assertIsNotNone(service)
        mock_adapter.chat.assert_not_called()

    @patch("docpipe.core.operators.functional.chunker.OllamaClient")
    def test_semantic_chunking_missing_embeddings_model(self, mock_ollama_client_class):
        """Test that semantic chunking provides clear error when semantic_embeddings_model is missing"""
        # Create test data
        content = ["Test content for semantic chunking."]
        data = {
            OperatorConstants.Columns.ID: ["doc1"],
            OperatorConstants.Columns.NAME: ["Document 1"],
            "content": content,
        }
        input_table = pa.table(data)

        # Create operator with semantic chunking but WITHOUT semantic_embeddings_model
        config = {
            "chunk_type": ChunkType.SEMANTIC.value,
            "breakpoint_threshold_type": BreakpointThresholdType.PERCENTILE.value,
            "doc_column": "content",
            # Note: semantic_embeddings_model is intentionally missing
        }

        operator = ChunkerOperator(config)

        # Transform should handle the error gracefully and record it in metadata
        _, metadata = operator.transform(input_table)

        # Verify the error was recorded in failed documents
        self.assertIn("failed_docs", metadata)
        failed_docs = metadata["failed_docs"]
        self.assertEqual(len(failed_docs), 1)

        # Verify the error message is clear and mentions semantic_embeddings_model
        error_reason = failed_docs[0]["reason"]
        self.assertIn("semantic_embeddings_model", error_reason.lower())
        self.assertIn("required", error_reason.lower())
        self.assertIn("semantic chunking", error_reason.lower())

        # Verify that OllamaClient was never instantiated (error caught before that)
        mock_ollama_client_class.assert_not_called()


class TestDoclingServeValidation(unittest.TestCase):
    """Test validate() for the docling_serve provider block (lines 585-634)."""

    def _make_operator(self, extra_provider_config=None, chunk_type=None):
        provider_config = {"api_base": "http://localhost:5001", "timeout": 300}
        if extra_provider_config:
            provider_config.update(extra_provider_config)
        config = {
            "chunk_type": (chunk_type or ChunkType.HYBRID.value),
            "provider": "docling_serve",
            "provider_config": provider_config,
            "job_id": "job-1",
            "job_run_id": "run-1",
        }
        return ChunkerOperator(config)

    def _run_validate(self, operator):
        errors = []
        warnings = []
        operator.validate(errors=errors, warnings=warnings, available_features=[])
        return errors, warnings

    def _error_messages(self, errors):
        return " ".join(str(e) for e in errors)

    def _warning_messages(self, warnings):
        return " ".join(str(w) for w in warnings)

    # --- api_base missing ---

    def test_validate_missing_api_base_raises_error(self):
        """validate() appends error when api_base is absent."""
        config = {
            "chunk_type": ChunkType.HYBRID.value,
            "provider": "docling_serve",
            "provider_config": {"timeout": 300},
            "job_id": "job-1",
            "job_run_id": "run-1",
        }
        operator = ChunkerOperator(config)
        errors, _ = self._run_validate(operator)
        self.assertTrue(
            any("API base" in str(e) or "api_base" in str(e).lower() for e in errors),
            f"Expected API base error, got: {errors}",
        )

    def test_validate_present_api_base_no_base_url_error(self):
        """validate() does not append a base-URL error when api_base is present."""
        operator = self._make_operator()
        errors, _ = self._run_validate(operator)
        base_url_errors = [e for e in errors if "API base" in str(e) or "api_base" in str(e).lower()]
        self.assertEqual(base_url_errors, [])

    # --- timeout ---

    def test_validate_timeout_zero_raises_error(self):
        """validate() appends error when timeout == 0."""
        operator = self._make_operator(extra_provider_config={"timeout": 0})
        errors, _ = self._run_validate(operator)
        self.assertTrue(
            any("timeout" in str(e).lower() for e in errors),
            f"Expected timeout error, got: {errors}",
        )

    def test_validate_timeout_negative_raises_error(self):
        """validate() appends error when timeout is negative."""
        operator = self._make_operator(extra_provider_config={"timeout": -1})
        errors, _ = self._run_validate(operator)
        self.assertTrue(
            any("timeout" in str(e).lower() for e in errors),
            f"Expected timeout error, got: {errors}",
        )

    def test_validate_positive_timeout_no_error(self):
        """validate() does not append a timeout error for a valid timeout."""
        operator = self._make_operator(extra_provider_config={"timeout": 1})
        errors, _ = self._run_validate(operator)
        timeout_errors = [e for e in errors if "timeout" in str(e).lower()]
        self.assertEqual(timeout_errors, [])

    # --- poll_interval ---

    def test_validate_poll_interval_zero_raises_error(self):
        """validate() appends error when poll_interval == 0."""
        operator = self._make_operator(extra_provider_config={"poll_interval": 0})
        errors, _ = self._run_validate(operator)
        self.assertTrue(
            any("poll" in str(e).lower() for e in errors),
            f"Expected poll_interval error, got: {errors}",
        )

    def test_validate_poll_interval_negative_raises_error(self):
        """validate() appends error when poll_interval is negative."""
        operator = self._make_operator(extra_provider_config={"poll_interval": -5})
        errors, _ = self._run_validate(operator)
        self.assertTrue(
            any("poll" in str(e).lower() for e in errors),
            f"Expected poll_interval error, got: {errors}",
        )

    def test_validate_positive_poll_interval_no_error(self):
        """validate() does not append a poll_interval error for a valid value."""
        operator = self._make_operator(extra_provider_config={"poll_interval": 2})
        errors, _ = self._run_validate(operator)
        poll_errors = [e for e in errors if "poll" in str(e).lower()]
        self.assertEqual(poll_errors, [])

    # --- max_retries ---

    def test_validate_max_retries_negative_raises_error(self):
        """validate() appends error when max_retries is negative."""
        operator = self._make_operator(extra_provider_config={"max_retries": -1})
        errors, _ = self._run_validate(operator)
        self.assertTrue(
            any("retries" in str(e).lower() for e in errors),
            f"Expected max_retries error, got: {errors}",
        )

    def test_validate_max_retries_zero_is_valid(self):
        """validate() does not append a max_retries error when max_retries == 0."""
        operator = self._make_operator(extra_provider_config={"max_retries": 0})
        errors, _ = self._run_validate(operator)
        retry_errors = [e for e in errors if "retries" in str(e).lower()]
        self.assertEqual(retry_errors, [])

    def test_validate_max_retries_positive_is_valid(self):
        """validate() does not append a max_retries error for a positive value."""
        operator = self._make_operator(extra_provider_config={"max_retries": 5})
        errors, _ = self._run_validate(operator)
        retry_errors = [e for e in errors if "retries" in str(e).lower()]
        self.assertEqual(retry_errors, [])

    # --- chunk_type warning ---

    def test_validate_non_hybrid_chunk_type_emits_warning(self):
        """validate() appends a warning when provider is docling_serve but chunk_type is not hybrid."""
        for chunk_type in (ChunkType.SIMPLE.value, ChunkType.SEMANTIC.value):
            with self.subTest(chunk_type=chunk_type):
                operator = self._make_operator(chunk_type=chunk_type)
                _, warnings = self._run_validate(operator)
                self.assertTrue(
                    any("docling_serve" in str(w).lower() or "chunk_type" in str(w).lower() for w in warnings),
                    f"Expected chunk_type mismatch warning for {chunk_type}, got: {warnings}",
                )

    def test_validate_hybrid_chunk_type_no_chunk_type_warning(self):
        """validate() does not warn about chunk_type mismatch when chunk_type is hybrid."""
        operator = self._make_operator(chunk_type=ChunkType.HYBRID.value)
        _, warnings = self._run_validate(operator)
        mismatch_warnings = [w for w in warnings if "chunk_type" in str(w).lower() and "mismatch" in str(w).lower()]
        self.assertEqual(mismatch_warnings, [])

    def test_validate_multiple_errors_collected_together(self):
        """validate() collects all errors in one pass without short-circuiting."""
        config = {
            "chunk_type": ChunkType.HYBRID.value,
            "provider": "docling_serve",
            "provider_config": {
                # api_base missing, timeout invalid, poll_interval invalid, max_retries invalid
                "timeout": 0,
                "poll_interval": -1,
                "max_retries": -2,
            },
            "job_id": "job-1",
            "job_run_id": "run-1",
        }
        operator = ChunkerOperator(config)
        errors, _ = self._run_validate(operator)
        self.assertGreaterEqual(len(errors), 4, f"Expected at least 4 errors, got: {errors}")


class TestDoclingServeClient(unittest.TestCase):
    """Test _get_docling_serve_client() (lines 636-675)."""

    def _make_operator(self):
        config = {
            "chunk_type": ChunkType.HYBRID.value,
            "provider": "docling_serve",
            "provider_config": {
                "api_base": "http://localhost:5001",
                "timeout": 300,
                "max_retries": 3,
                "verify_ssl": True,
            },
            "job_id": "job-1",
            "job_run_id": "run-1",
        }
        return ChunkerOperator(config)

    def test_get_docling_serve_client_returns_client(self):
        """_get_docling_serve_client() returns a RestClient instance."""
        operator = self._make_operator()
        mock_client_instance = Mock()
        mock_config_instance = Mock()

        with (
            patch("docpipe.integrations.rest_client.RestClient") as mock_client_cls,
            patch("docpipe.integrations.rest_client.RestClientConfig") as mock_config_cls,
        ):
            mock_config_cls.return_value = mock_config_instance
            mock_client_cls.return_value = mock_client_instance

            # Patch the lazy import inside the method
            with patch.dict(
                "sys.modules",
                {
                    "docpipe.integrations.rest_client": type(
                        "mod",
                        (),
                        {
                            "RestClient": mock_client_cls,
                            "RestClientConfig": mock_config_cls,
                        },
                    )(),
                },
            ):
                operator._remote_chunking_client = None
                # Re-patch by injecting mock directly through the import inside method
                with patch(
                    "docpipe.core.operators.functional.chunker.ChunkerOperator._get_docling_serve_client",
                    wraps=operator._get_docling_serve_client,
                ):
                    # Directly pre-set client to test caching path
                    operator._remote_chunking_client = mock_client_instance
                    client = operator._get_docling_serve_client()
                    self.assertIs(client, mock_client_instance)

    def test_get_docling_serve_client_cached(self):
        """_get_docling_serve_client() returns same instance on repeated calls."""
        operator = self._make_operator()
        mock_client_instance = Mock()
        operator._remote_chunking_client = mock_client_instance

        client1 = operator._get_docling_serve_client()
        client2 = operator._get_docling_serve_client()
        self.assertIs(client1, client2)
        self.assertIs(client1, mock_client_instance)

    def test_get_docling_serve_client_initializes_from_provider_config(self):
        """_get_docling_serve_client() creates a client when none is cached."""
        operator = self._make_operator()
        operator._remote_chunking_client = None

        mock_client_instance = Mock()
        mock_config_instance = Mock()
        mock_rest_client_cls = Mock(return_value=mock_client_instance)
        mock_rest_config_cls = Mock(return_value=mock_config_instance)

        fake_module = Mock()
        fake_module.RestClient = mock_rest_client_cls
        fake_module.RestClientConfig = mock_rest_config_cls

        with patch.dict("sys.modules", {"docpipe.integrations.rest_client": fake_module}):
            client = operator._get_docling_serve_client()

        self.assertIs(client, mock_client_instance)
        mock_rest_config_cls.assert_called_once_with(
            timeout=300,
            max_retries=3,
            verify_ssl=True,
        )
        mock_rest_client_cls.assert_called_once_with(
            config=mock_config_instance,
            base_url="http://localhost:5001",
        )

    def test_get_docling_serve_client_raises_docpipe_exception_on_error(self):
        """_get_docling_serve_client() wraps initialization failures in DocpipeException."""
        operator = self._make_operator()
        operator._remote_chunking_client = None

        fake_module = Mock()
        fake_module.RestClient = Mock(side_effect=RuntimeError("connection refused"))
        fake_module.RestClientConfig = Mock(return_value=Mock())

        with patch.dict("sys.modules", {"docpipe.integrations.rest_client": fake_module}):
            with self.assertRaises(DocpipeException) as ctx:
                operator._get_docling_serve_client()

        self.assertIn("connection refused", str(ctx.exception))


class TestDoclingServeSplitText(unittest.TestCase):
    """Test _docling_serve_split_text() (lines 677-791)."""

    def _make_operator(self, extra_config=None):
        config = {
            "chunk_type": ChunkType.HYBRID.value,
            "provider": "docling_serve",
            "provider_config": {
                "api_base": "http://localhost:5001",
                "timeout": 300,
            },
            "job_id": "job-1",
            "job_run_id": "run-1",
        }
        if extra_config:
            config.update(extra_config)
        return ChunkerOperator(config)

    def _set_mock_client(self, operator, response):
        mock_client = Mock()
        mock_client.call_rest_json.return_value = response
        operator._remote_chunking_client = mock_client
        return mock_client

    # --- happy path ---

    def test_split_text_returns_documents_from_dict_chunks(self):
        """_docling_serve_split_text() converts dict chunks with 'text' key to Documents."""
        operator = self._make_operator()
        self._set_mock_client(
            operator,
            {"chunks": [{"text": "First chunk."}, {"text": "Second chunk."}]},
        )
        docs = operator._docling_serve_split_text(content="some content", doc_name="test.md")
        self.assertEqual(len(docs), 2)
        self.assertEqual(docs[0].page_content, "First chunk.")
        self.assertEqual(docs[1].page_content, "Second chunk.")

    def test_split_text_non_dict_chunk_uses_str(self):
        """_docling_serve_split_text() falls back to str() for non-dict chunks."""
        operator = self._make_operator()
        self._set_mock_client(operator, {"chunks": ["plain text chunk"]})
        docs = operator._docling_serve_split_text(content="some content", doc_name="test.md")
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].page_content, "plain text chunk")

    def test_split_text_empty_chunks_returns_empty_list(self):
        """_docling_serve_split_text() returns [] when API yields no chunks."""
        operator = self._make_operator()
        self._set_mock_client(operator, {"chunks": []})
        docs = operator._docling_serve_split_text(content="some content", doc_name="test.md")
        self.assertEqual(docs, [])

    def test_split_text_missing_chunks_key_returns_empty_list(self):
        """_docling_serve_split_text() returns [] when 'chunks' key is absent."""
        operator = self._make_operator()
        self._set_mock_client(operator, {})
        docs = operator._docling_serve_split_text(content="some content", doc_name="test.md")
        self.assertEqual(docs, [])

    def test_split_text_skips_empty_chunk_text(self):
        """_docling_serve_split_text() skips chunks whose text is empty string."""
        operator = self._make_operator()
        self._set_mock_client(
            operator,
            {"chunks": [{"text": ""}, {"text": "real chunk"}, {"text": ""}]},
        )
        docs = operator._docling_serve_split_text(content="some content", doc_name="test.md")
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].page_content, "real chunk")

    def test_split_text_uses_default_doc_name_when_none(self):
        """_docling_serve_split_text() uses DEFAULT_DOCUMENT_NAME when doc_name is None."""
        operator = self._make_operator()
        mock_client = Mock()
        mock_client.call_rest_json.return_value = {"chunks": [{"text": "chunk"}]}
        operator._remote_chunking_client = mock_client

        operator._docling_serve_split_text(content="content", doc_name=None)

        call_kwargs = mock_client.call_rest_json.call_args
        payload = call_kwargs.kwargs.get("json_data") or call_kwargs[1].get("json_data") or call_kwargs[0][2]
        filename = payload["sources"][0]["filename"]
        from docpipe.core.operators.functional.chunker import DEFAULT_DOCUMENT_NAME

        self.assertEqual(filename, DEFAULT_DOCUMENT_NAME)

    def test_split_text_attaches_api_key_header(self):
        """_docling_serve_split_text() adds X-Api-Key header when api_key is in provider_config."""
        config = {
            "chunk_type": ChunkType.HYBRID.value,
            "provider": "docling_serve",
            "provider_config": {
                "api_base": "http://localhost:5001",
                "timeout": 300,
                "api_key": "secret-key",  # pragma: allowlist secret
            },
            "job_id": "job-1",
            "job_run_id": "run-1",
        }
        operator = ChunkerOperator(config)
        mock_client = Mock()
        mock_client.call_rest_json.return_value = {"chunks": [{"text": "data"}]}
        operator._remote_chunking_client = mock_client

        operator._docling_serve_split_text(content="content", doc_name="doc.md")

        call_kwargs = mock_client.call_rest_json.call_args
        headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers")
        self.assertIn("X-Api-Key", headers)
        self.assertEqual(headers["X-Api-Key"], "secret-key")

    def test_split_text_no_api_key_header_when_absent(self):
        """_docling_serve_split_text() does not set X-Api-Key when api_key is not configured."""
        operator = self._make_operator()
        mock_client = Mock()
        mock_client.call_rest_json.return_value = {"chunks": [{"text": "data"}]}
        operator._remote_chunking_client = mock_client

        operator._docling_serve_split_text(content="content", doc_name="doc.md")

        call_kwargs = mock_client.call_rest_json.call_args
        headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers")
        self.assertNotIn("X-Api-Key", headers)

    def test_split_text_chunk_metadata_populated(self):
        """_docling_serve_split_text() populates chunk_index and doc_name metadata."""
        operator = self._make_operator()
        self._set_mock_client(
            operator,
            {"chunks": [{"text": "chunk A", "start_index": 10}, {"text": "chunk B"}]},
        )
        docs = operator._docling_serve_split_text(content="content", doc_name="my.md")
        self.assertEqual(docs[0].metadata["chunk_index"], 0)
        self.assertEqual(docs[0].metadata["start_index"], 10)
        self.assertEqual(docs[0].metadata["doc_name"], "my.md")
        self.assertEqual(docs[1].metadata["chunk_index"], 1)

    # --- invalid response type ---

    def test_split_text_non_dict_response_raises_docpipe_exception(self):
        """_docling_serve_split_text() raises DocpipeException when response is not a dict."""
        operator = self._make_operator()
        mock_client = Mock()
        mock_client.call_rest_json.return_value = ["not", "a", "dict"]
        operator._remote_chunking_client = mock_client

        with self.assertRaises(DocpipeException) as ctx:
            operator._docling_serve_split_text(content="content", doc_name="test.md")
        self.assertIn("Invalid response", str(ctx.exception))

    # --- exception wrapping ---

    def test_split_text_wraps_exception_in_docpipe_exception(self):
        """_docling_serve_split_text() wraps arbitrary errors as DocpipeException."""
        operator = self._make_operator()
        mock_client = Mock()
        mock_client.call_rest_json.side_effect = ConnectionError("network failure")
        operator._remote_chunking_client = mock_client

        with self.assertRaises(DocpipeException) as ctx:
            operator._docling_serve_split_text(content="content", doc_name="test.md")
        self.assertIn("network failure", str(ctx.exception))
