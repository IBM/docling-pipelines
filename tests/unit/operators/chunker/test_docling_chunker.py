#!/usr/bin/env python3
"""
Comprehensive unit tests for DoclingChunkerOperator.

Tests cover:
- Initialization and configuration validation
- Basic chunking functionality
- Chunk size and overlap validation
- Metadata generation
- Edge cases (empty documents, very small/large documents)
- Error handling (invalid configurations, missing fields)
- Integration with PyArrow tables
- Hash ID generation
- Content retention options
"""

import json
import pytest
import pyarrow as pa
from unittest.mock import patch, MagicMock

from core.operators.universal.chunker.docling_chunker import DoclingChunkerOperator
from common.constants.constants import Metrics, ExecutionStatus
from common.constants.operator_constants import OperatorConstants


# ---------------------------------------------------------------------------
# Test Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def basic_config():
    """Basic configuration for DoclingChunkerOperator."""
    return {
        "doc_column": "content",
        "chunk_size": 512,
        "chunk_overlap": 128,
        "retain_original_content": True,
        "tokenizer": "sentence-transformers/all-MiniLM-L6-v2",
    }


@pytest.fixture
def minimal_config():
    """Minimal configuration using defaults."""
    return {}


@pytest.fixture
def sample_table_single_doc():
    """PyArrow table with a single document."""
    data = {
        "id": ["doc1"],
        "name": ["Document 1"],
        "content": [
            "This is a test document with some content. It has multiple sentences. This helps test chunking."
        ],
    }
    return pa.table(data)


@pytest.fixture
def sample_table_multiple_docs():
    """PyArrow table with multiple documents."""
    data = {
        "id": ["doc1", "doc2", "doc3"],
        "name": ["Document 1", "Document 2", "Document 3"],
        "content": [
            "First document with short content.",
            "Second document with different content that is a bit longer.",
            "Third document with unique text and more sentences to test.",
        ],
    }
    return pa.table(data)


@pytest.fixture
def sample_table_long_doc():
    """PyArrow table with a long document requiring multiple chunks."""
    long_text = (
        "This is a sentence. " * 200
    )  # ~4000 chars, should create multiple chunks
    data = {
        "id": ["doc1"],
        "name": ["Long Document"],
        "content": [long_text],
    }
    return pa.table(data)


@pytest.fixture
def sample_table_empty_content():
    """PyArrow table with empty content."""
    data = {
        "id": ["doc1"],
        "name": ["Empty Document"],
        "content": [""],
    }
    return pa.table(data)


@pytest.fixture
def sample_table_no_content_column():
    """PyArrow table missing the content column."""
    data = {
        "id": ["doc1"],
        "name": ["Document 1"],
        "text": ["This should fail because column name is wrong"],
    }
    return pa.table(data)


@pytest.fixture
def mock_docling_chunker():
    """Mock the HybridChunker to avoid external dependencies."""
    with patch(
        "core.operators.universal.chunker.docling_chunker.HybridChunker"
    ) as mock_chunker_class:
        mock_chunker = MagicMock()
        mock_chunker_class.return_value = mock_chunker

        # Mock chunk iterator
        def mock_chunk_iter(dl_doc):
            # Return mock chunks
            mock_chunk1 = MagicMock()
            mock_chunk1.text = "First chunk of text."
            mock_chunk1.start_index = 0

            mock_chunk2 = MagicMock()
            mock_chunk2.text = "Second chunk of text."
            mock_chunk2.start_index = 100

            return iter([mock_chunk1, mock_chunk2])

        mock_chunker.chunk = mock_chunk_iter
        yield mock_chunker


# ---------------------------------------------------------------------------
# 1. Initialization Tests
# ---------------------------------------------------------------------------


def test_initialization_with_basic_config(basic_config, mock_docling_chunker):
    """Operator initializes correctly with basic configuration."""
    operator = DoclingChunkerOperator(basic_config)

    assert operator.doc_column == "content"
    assert operator.chunk_size == 512
    assert operator.chunk_overlap == 128
    assert operator.retain_original_content is True
    assert operator.tokenizer == "sentence-transformers/all-MiniLM-L6-v2"


def test_initialization_with_defaults(minimal_config, mock_docling_chunker):
    """Operator initializes with default values when not specified."""
    operator = DoclingChunkerOperator(minimal_config)

    assert operator.doc_column == OperatorConstants.Columns.DOC_COLUMN_DEFAULT
    assert operator.chunk_size == OperatorConstants.Processing.CHUNK_SIZE_DEFAULT
    assert operator.chunk_overlap == 128
    assert operator.retain_original_content is True


def test_initialization_validates_chunk_size_too_small(mock_docling_chunker):
    """Operator raises error when chunk_size is too small."""
    config = {"chunk_size": 50}

    with pytest.raises(ValueError, match="chunk_size must be at least 100 tokens"):
        DoclingChunkerOperator(config)


def test_initialization_validates_chunk_size_too_large(mock_docling_chunker):
    """Operator raises error when chunk_size is too large."""
    config = {"chunk_size": 3000}

    with pytest.raises(ValueError, match="chunk_size must not exceed 2048 tokens"):
        DoclingChunkerOperator(config)


def test_initialization_validates_chunk_overlap_negative(mock_docling_chunker):
    """Operator raises error when chunk_overlap is negative."""
    config = {"chunk_overlap": -10}

    with pytest.raises(ValueError, match="chunk_overlap must be non-negative"):
        DoclingChunkerOperator(config)


def test_initialization_validates_chunk_overlap_exceeds_size(mock_docling_chunker):
    """Operator raises error when chunk_overlap >= chunk_size."""
    config = {"chunk_size": 512, "chunk_overlap": 512}

    with pytest.raises(ValueError, match="chunk_overlap must be less than chunk_size"):
        DoclingChunkerOperator(config)


def test_initialization_validates_empty_doc_column(mock_docling_chunker):
    """Operator raises error when doc_column is empty."""
    config = {"doc_column": ""}

    with pytest.raises(ValueError, match="doc_column must be a non-empty string"):
        DoclingChunkerOperator(config)


def test_initialization_validates_empty_tokenizer(mock_docling_chunker):
    """Operator raises error when tokenizer is empty."""
    config = {"tokenizer": ""}

    with pytest.raises(ValueError, match="tokenizer must be a non-empty string"):
        DoclingChunkerOperator(config)


# ---------------------------------------------------------------------------
# 2. Transform Method Tests
# ---------------------------------------------------------------------------


def test_transform_single_document(
    basic_config, sample_table_single_doc, mock_docling_chunker
):
    """Transform successfully chunks a single document."""
    operator = DoclingChunkerOperator(basic_config)
    result_tables, metadata = operator.transform(sample_table_single_doc)
    result = result_tables[0]

    # Check that chunked_content column was added
    assert "chunked_content" in result.column_names

    # Check metadata
    assert metadata[Metrics.External.PROCESSED_DOCS] == 1
    assert metadata[Metrics.External.TOTAL_CHUNKS] == 2  # Mock returns 2 chunks
    assert metadata[Metrics.External.NODE_STATUS] == ExecutionStatus.COMPLETED.value


def test_transform_multiple_documents(
    basic_config, sample_table_multiple_docs, mock_docling_chunker
):
    """Transform successfully chunks multiple documents."""
    operator = DoclingChunkerOperator(basic_config)
    result_tables, metadata = operator.transform(sample_table_multiple_docs)
    result = result_tables[0]

    # Check that all rows are preserved
    assert result.num_rows == 3

    # Check metadata
    assert metadata[Metrics.External.PROCESSED_DOCS] == 3
    assert metadata[Metrics.External.TOTAL_CHUNKS] == 6  # 2 chunks per doc


def test_transform_adds_hash_column(
    basic_config, sample_table_single_doc, mock_docling_chunker
):
    """Transform adds doc_id_hash column."""
    operator = DoclingChunkerOperator(basic_config)
    result_tables, metadata = operator.transform(sample_table_single_doc)
    result = result_tables[0]

    # Check that hash column was added
    assert OperatorConstants.Columns.DOC_ID_HASH_DEFAULT in result.column_names


def test_transform_retains_original_content(
    basic_config, sample_table_single_doc, mock_docling_chunker
):
    """Transform retains original content when configured."""
    operator = DoclingChunkerOperator(basic_config)
    result_tables, metadata = operator.transform(sample_table_single_doc)
    result = result_tables[0]

    # Original content column should still exist
    assert "content" in result.column_names


def test_transform_removes_original_content(
    basic_config, sample_table_single_doc, mock_docling_chunker
):
    """Transform removes original content when configured."""
    config = basic_config.copy()
    config["retain_original_content"] = False

    operator = DoclingChunkerOperator(config)
    result_tables, metadata = operator.transform(sample_table_single_doc)
    result = result_tables[0]

    # Original content column should be removed
    assert "content" not in result.column_names


def test_transform_empty_table(basic_config, mock_docling_chunker):
    """Transform handles empty table gracefully."""
    empty_table = pa.table({"id": [], "name": [], "content": []})

    operator = DoclingChunkerOperator(basic_config)
    result_tables, metadata = operator.transform(empty_table)
    result = result_tables[0]

    assert result.num_rows == 0
    assert metadata[Metrics.External.PROCESSED_DOCS] == 0


def test_transform_missing_content_column(
    basic_config, sample_table_no_content_column, mock_docling_chunker
):
    """Transform fails gracefully when content column is missing."""
    operator = DoclingChunkerOperator(basic_config)
    result_tables, metadata = operator.transform(sample_table_no_content_column)

    # Should return original table
    assert result_tables[0].num_rows == 1

    # Metadata should indicate failure
    assert metadata[Metrics.External.NODE_STATUS] == ExecutionStatus.FAILED.value
    assert OperatorConstants.Extraction.ERROR in metadata


def test_transform_empty_content(
    basic_config, sample_table_empty_content, mock_docling_chunker
):
    """Transform handles empty content gracefully."""
    operator = DoclingChunkerOperator(basic_config)
    result_tables, metadata = operator.transform(sample_table_empty_content)

    # Should record as failed document
    assert metadata[Metrics.External.FAILED_DOCS_COUNT] == 1
    assert (
        metadata[Metrics.External.NODE_STATUS]
        == ExecutionStatus.COMPLETED_WITH_ERRORS.value
    )


# ---------------------------------------------------------------------------
# 3. Chunking Logic Tests
# ---------------------------------------------------------------------------


def test_chunk_document_creates_proper_structure(basic_config, mock_docling_chunker):
    """_chunk_document creates chunks with proper structure."""
    operator = DoclingChunkerOperator(basic_config)

    # Create a simple DoclingDocument JSON
    from docling_core.types.doc.document import DoclingDocument
    from docling_core.types.doc.labels import DocItemLabel

    doc = DoclingDocument(name="test_doc")
    doc.add_text(text="This is a test paragraph.", label=DocItemLabel.TEXT)
    docling_doc_json = doc.model_dump_json()

    chunks = operator._chunk_document(docling_doc_json, "test_doc")

    # Check chunk structure
    assert len(chunks) == 2  # Mock returns 2 chunks
    assert "chunk" in chunks[0]
    assert "start_index" in chunks[0]
    assert "metadata" in chunks[0]
    assert chunks[0]["metadata"]["doc_name"] == "test_doc"


def test_chunk_document_handles_empty_json(basic_config, mock_docling_chunker):
    """_chunk_document handles empty JSON gracefully."""
    operator = DoclingChunkerOperator(basic_config)

    chunks = operator._chunk_document("", "test_doc")

    assert chunks == []


def test_create_docling_document_from_markdown(basic_config, mock_docling_chunker):
    """_create_docling_document_from_markdown creates valid DoclingDocument."""
    operator = DoclingChunkerOperator(basic_config)

    markdown_content = "# Title\n\nThis is a paragraph.\n\nAnother paragraph."
    docling_json = operator._create_docling_document_from_markdown(
        markdown_content, "test_doc"
    )

    # Should return valid JSON string
    assert isinstance(docling_json, str)
    assert len(docling_json) > 0

    # Should be parseable as DoclingDocument
    from docling_core.types.doc.document import DoclingDocument

    doc = DoclingDocument.model_validate_json(docling_json)
    assert doc.name == "test_doc"


def test_simple_chunk_fallback(basic_config, mock_docling_chunker):
    """_simple_chunk_fallback creates chunks when Docling fails."""
    operator = DoclingChunkerOperator(basic_config)

    content = "This is a test. " * 100  # ~1600 chars
    chunks = operator._simple_chunk_fallback(content, "test_doc")

    # Should create at least one chunk
    assert len(chunks) > 0

    # Check chunk structure
    assert "chunk" in chunks[0]
    assert "start_index" in chunks[0]
    assert "metadata" in chunks[0]
    assert chunks[0]["metadata"]["fallback"] is True


# ---------------------------------------------------------------------------
# 4. Metadata Tests
# ---------------------------------------------------------------------------


def test_get_metadata_structure(basic_config, mock_docling_chunker):
    """get_metadata returns proper structure."""
    operator = DoclingChunkerOperator(basic_config)
    metadata = operator.get_metadata()

    # Check top-level keys
    assert OperatorConstants.Misc.CATEGORY in metadata
    assert OperatorConstants.Config.FEATURES in metadata
    assert OperatorConstants.Config.ATTRIBUTES in metadata
    assert OperatorConstants.Misc.IS_OPERATOR_AVAILABLE in metadata


def test_get_metadata_features(basic_config, mock_docling_chunker):
    """get_metadata includes expected features."""
    operator = DoclingChunkerOperator(basic_config)
    metadata = operator.get_metadata()

    features = metadata[OperatorConstants.Config.FEATURES]

    # Check for chunked_content feature
    assert OperatorConstants.Columns.CHUNKED_CONTENT in features
    assert features[OperatorConstants.Columns.CHUNKED_CONTENT][
        OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB
    ]


def test_get_metadata_attributes(basic_config, mock_docling_chunker):
    """get_metadata includes configuration attributes."""
    operator = DoclingChunkerOperator(basic_config)
    metadata = operator.get_metadata()

    attributes = metadata[OperatorConstants.Config.ATTRIBUTES]

    # Check for expected attributes
    assert OperatorConstants.Columns.DOC_COLUMN in attributes
    assert OperatorConstants.Processing.CHUNK_SIZE in attributes
    assert "chunk_overlap" in attributes
    assert "retain_original_content" in attributes
    assert "tokenizer" in attributes


# ---------------------------------------------------------------------------
# 5. Edge Cases and Error Handling
# ---------------------------------------------------------------------------


def test_transform_with_special_characters(basic_config, mock_docling_chunker):
    """Transform handles special characters in content."""
    special_chars_table = pa.table(
        {
            "id": ["doc1"],
            "name": ["Special Doc"],
            "content": ["Content with special chars: @#$%^&*()_+-=[]{}|;':\",./<>?"],
        }
    )

    operator = DoclingChunkerOperator(basic_config)
    result_tables, metadata = operator.transform(special_chars_table)

    # Should process successfully
    assert metadata[Metrics.External.PROCESSED_DOCS] == 1


def test_transform_with_unicode(basic_config, mock_docling_chunker):
    """Transform handles Unicode characters."""
    unicode_table = pa.table(
        {
            "id": ["doc1"],
            "name": ["Unicode Doc"],
            "content": ["Content with Unicode: 你好世界 مرحبا العالم Привет мир"],
        }
    )

    operator = DoclingChunkerOperator(basic_config)
    result_tables, metadata = operator.transform(unicode_table)

    # Should process successfully
    assert metadata[Metrics.External.PROCESSED_DOCS] == 1


def test_transform_with_very_short_document(basic_config, mock_docling_chunker):
    """Transform handles very short documents."""
    short_table = pa.table(
        {
            "id": ["doc1"],
            "name": ["Short Doc"],
            "content": ["Hi"],
        }
    )

    operator = DoclingChunkerOperator(basic_config)
    result_tables, metadata = operator.transform(short_table)

    # Should process successfully
    assert metadata[Metrics.External.PROCESSED_DOCS] == 1


def test_transform_with_null_content(basic_config, mock_docling_chunker):
    """Transform handles null content gracefully."""
    null_table = pa.table(
        {
            "id": ["doc1"],
            "name": ["Null Doc"],
            "content": [None],
        }
    )

    operator = DoclingChunkerOperator(basic_config)
    result_tables, metadata = operator.transform(null_table)

    # Should record as failed
    assert metadata[Metrics.External.FAILED_DOCS_COUNT] == 1


def test_transform_preserves_all_columns(basic_config, mock_docling_chunker):
    """Transform preserves all original columns."""
    table_with_extra_cols = pa.table(
        {
            "id": ["doc1"],
            "name": ["Document 1"],
            "content": ["Test content"],
            "extra_col1": ["value1"],
            "extra_col2": [42],
        }
    )

    operator = DoclingChunkerOperator(basic_config)
    result_tables, metadata = operator.transform(table_with_extra_cols)
    result = result_tables[0]

    # All original columns should be preserved
    assert "extra_col1" in result.column_names
    assert "extra_col2" in result.column_names


def test_chunk_size_boundary_conditions(mock_docling_chunker):
    """Test chunk_size at boundary values."""
    # Minimum valid chunk_size
    config_min = {"chunk_size": 100}
    operator_min = DoclingChunkerOperator(config_min)
    assert operator_min.chunk_size == 100

    # Maximum valid chunk_size
    config_max = {"chunk_size": 2048}
    operator_max = DoclingChunkerOperator(config_max)
    assert operator_max.chunk_size == 2048


def test_chunk_overlap_boundary_conditions(mock_docling_chunker):
    """Test chunk_overlap at boundary values."""
    # Minimum valid chunk_overlap
    config_min = {"chunk_overlap": 0}
    operator_min = DoclingChunkerOperator(config_min)
    assert operator_min.chunk_overlap == 0

    # Maximum valid chunk_overlap (just below chunk_size)
    config_max = {"chunk_size": 512, "chunk_overlap": 511}
    operator_max = DoclingChunkerOperator(config_max)
    assert operator_max.chunk_overlap == 511


# ---------------------------------------------------------------------------
# 6. Integration Tests
# ---------------------------------------------------------------------------


def test_full_pipeline_with_chunking(
    basic_config, sample_table_single_doc, mock_docling_chunker
):
    """Test full pipeline: input table -> chunking -> output with hash."""
    operator = DoclingChunkerOperator(basic_config)
    result_tables, metadata = operator.transform(sample_table_single_doc)
    result = result_tables[0]

    # Verify all expected columns exist
    assert "id" in result.column_names
    assert "name" in result.column_names
    assert "content" in result.column_names
    assert "chunked_content" in result.column_names
    assert OperatorConstants.Columns.DOC_ID_HASH_DEFAULT in result.column_names

    # Verify chunked_content is valid JSON
    chunked_content_json = result["chunked_content"][0].as_py()
    chunks = json.loads(chunked_content_json)
    assert isinstance(chunks, list)
    assert len(chunks) == 2


def test_chunked_content_json_structure(
    basic_config, sample_table_single_doc, mock_docling_chunker
):
    """Verify chunked_content JSON has correct structure."""
    operator = DoclingChunkerOperator(basic_config)
    result_tables, metadata = operator.transform(sample_table_single_doc)
    result = result_tables[0]

    chunked_content_json = result["chunked_content"][0].as_py()
    chunks = json.loads(chunked_content_json)

    # Check first chunk structure
    first_chunk = chunks[0]
    assert "chunk" in first_chunk
    assert "start_index" in first_chunk
    assert "metadata" in first_chunk
    assert "chunk_id" in first_chunk["metadata"]
    assert "doc_name" in first_chunk["metadata"]
    assert "token_count" in first_chunk["metadata"]


# Made with Bob
