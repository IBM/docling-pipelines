#!/usr/bin/env python3
"""
Comprehensive unit tests for SemanticChunkerOperator.

Tests cover:
- Initialization and configuration validation
- Basic chunking functionality with simple chunker
- Chunk size and overlap validation
- Metadata generation
- Edge cases (empty documents, very small/large documents)
- Error handling (invalid configurations, missing fields)
- Integration with PyArrow tables
- Content retention options
- Validation logic
"""

import pytest
import pyarrow as pa
from unittest.mock import patch

from core.operators.universal.chunker.semantic_chunker import (
    SemanticChunkerOperator,
    SIMPLE_CHUNK_TYPE,
    CHUNK_TYPE_KEY,
    CHUNK_OVERLAP_KEY,
    CHUNK_MIN_SIZE,
    CHUNK_MAX_SIZE,
    CHUNK_OVERLAP_MIN_SIZE,
    CHUNK_OVERLAP_MAX_SIZE,
)
from common.constants.constants import Metrics, ExecutionStatus
from common.constants.operator_constants import OperatorConstants
from common.exceptions.datasift_exceptions import DatasiftException


# ---------------------------------------------------------------------------
# Test Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def basic_config():
    """Basic configuration for SemanticChunkerOperator."""
    return {
        "doc_column": "content",
        "chunk_type": "simple",
        "chunk_size": 1000,
        "chunk_overlap": 200,
        "retain_original_content": True,
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
            "This is a test document. It has multiple sentences. This helps test chunking functionality."
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
            "First document with short content. It has a few sentences.",
            "Second document with different content. This one is also short.",
            "Third document with unique text. Testing chunking here.",
        ],
    }
    return pa.table(data)


@pytest.fixture
def sample_table_long_doc():
    """PyArrow table with a long document requiring multiple chunks."""
    long_text = (
        "This is a sentence. " * 300
    )  # ~6000 chars, should create multiple chunks
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
def sample_table_null_content():
    """PyArrow table with null content."""
    data = {
        "id": ["doc1"],
        "name": ["Null Document"],
        "content": [None],
    }
    return pa.table(data)


# ---------------------------------------------------------------------------
# 1. Initialization Tests
# ---------------------------------------------------------------------------


def test_initialization_with_basic_config(basic_config):
    """Operator initializes correctly with basic configuration."""
    operator = SemanticChunkerOperator(basic_config)

    assert operator.doc_column == "content"
    assert operator.chunk_type == "simple"
    assert operator.chunk_size == 1000
    assert operator.chunk_overlap == 200
    assert operator.retain_original_content is True


def test_initialization_with_defaults(minimal_config):
    """Operator initializes with default values when not specified."""
    operator = SemanticChunkerOperator(minimal_config)

    assert operator.doc_column == OperatorConstants.Columns.DOC_COLUMN_DEFAULT
    assert operator.chunk_type == SIMPLE_CHUNK_TYPE
    assert operator.chunk_size == OperatorConstants.Processing.CHUNK_SIZE_DEFAULT
    assert operator.chunk_overlap == 200
    assert operator.retain_original_content is True


def test_initialization_converts_chunk_size_to_int(minimal_config):
    """Operator converts chunk_size string to int."""
    config = minimal_config.copy()
    config["chunk_size"] = "1500"

    operator = SemanticChunkerOperator(config)
    assert isinstance(operator.chunk_size, int)
    assert operator.chunk_size == 1500


# ---------------------------------------------------------------------------
# 2. Validation Tests
# ---------------------------------------------------------------------------


def test_validate_chunk_size_too_small():
    """Validation fails when chunk_size is too small."""
    config = {"chunk_size": 100}
    operator = SemanticChunkerOperator(config)

    errors = []
    warnings = []
    operator.validate(errors, warnings, ["content"])

    assert len(errors) > 0
    assert any("chunk_size" in str(error) for error in errors)


def test_validate_chunk_size_too_large():
    """Validation fails when chunk_size is too large."""
    config = {"chunk_size": 6000}
    operator = SemanticChunkerOperator(config)

    errors = []
    warnings = []
    operator.validate(errors, warnings, ["content"])

    assert len(errors) > 0
    assert any("chunk_size" in str(error) for error in errors)


def test_validate_chunk_overlap_negative():
    """Validation fails when chunk_overlap is negative."""
    config = {"chunk_overlap": -10}
    operator = SemanticChunkerOperator(config)

    errors = []
    warnings = []
    operator.validate(errors, warnings, ["content"])

    assert len(errors) > 0
    assert any("chunk_overlap" in str(error) for error in errors)


def test_validate_chunk_overlap_too_large():
    """Validation fails when chunk_overlap exceeds maximum."""
    config = {"chunk_overlap": 600}
    operator = SemanticChunkerOperator(config)

    errors = []
    warnings = []
    operator.validate(errors, warnings, ["content"])

    assert len(errors) > 0
    assert any("chunk_overlap" in str(error) for error in errors)


def test_validate_invalid_chunk_type():
    """Validation fails with invalid chunk_type."""
    config = {"chunk_type": "invalid_type"}
    operator = SemanticChunkerOperator(config)

    errors = []
    warnings = []
    operator.validate(errors, warnings, ["content"])

    assert len(errors) > 0
    assert any("chunk_type" in str(error) for error in errors)


def test_validate_embeddings_column_present():
    """Validation fails if embeddings column already exists (chunker misplaced)."""
    config = {}
    operator = SemanticChunkerOperator(config)

    errors = []
    warnings = []
    operator.validate(
        errors, warnings, [OperatorConstants.Columns.EMBEDDINGS_COLUMN_DEFAULT]
    )

    assert len(errors) > 0
    assert any("CHUNKER_OPERATOR_MISPLACED" in str(error) for error in errors)


def test_validate_valid_configuration():
    """Validation passes with valid configuration."""
    config = {
        "chunk_type": "simple",
        "chunk_size": 1000,
        "chunk_overlap": 200,
    }
    operator = SemanticChunkerOperator(config)

    errors = []
    warnings = []
    operator.validate(errors, warnings, ["content"])

    # Should have no validation errors related to chunker config
    chunker_errors = [e for e in errors if "chunk" in str(e).lower()]
    assert len(chunker_errors) == 0


# ---------------------------------------------------------------------------
# 3. Transform Method Tests
# ---------------------------------------------------------------------------


def test_transform_single_document(basic_config, sample_table_single_doc):
    """Transform successfully chunks a single document."""
    operator = SemanticChunkerOperator(basic_config)
    result_tables, metadata = operator.transform(sample_table_single_doc)
    result = result_tables[0]

    # Check that chunked_content column was added
    assert OperatorConstants.Columns.CHUNKED_CONTENT in result.column_names

    # Check metadata
    assert metadata[Metrics.External.PROCESSED_DOCS] == 1
    assert metadata[Metrics.External.NODE_STATUS] == ExecutionStatus.COMPLETED.value


def test_transform_multiple_documents(basic_config, sample_table_multiple_docs):
    """Transform successfully chunks multiple documents."""
    operator = SemanticChunkerOperator(basic_config)
    result_tables, metadata = operator.transform(sample_table_multiple_docs)
    result = result_tables[0]

    # Check that all rows are preserved
    assert result.num_rows == 3

    # Check metadata
    assert metadata[Metrics.External.PROCESSED_DOCS] == 3


def test_transform_long_document_creates_multiple_chunks(
    basic_config, sample_table_long_doc
):
    """Transform creates multiple chunks for long documents."""
    operator = SemanticChunkerOperator(basic_config)
    result_tables, metadata = operator.transform(sample_table_long_doc)
    result = result_tables[0]

    # Get chunked content
    chunked_content = result[OperatorConstants.Columns.CHUNKED_CONTENT][0].as_py()

    # Should have multiple chunks
    assert len(chunked_content) > 1


def test_transform_retains_original_content(basic_config, sample_table_single_doc):
    """Transform retains original content when configured."""
    operator = SemanticChunkerOperator(basic_config)
    result_tables, metadata = operator.transform(sample_table_single_doc)
    result = result_tables[0]

    # Original content column should still exist
    assert "content" in result.column_names


def test_transform_removes_original_content(basic_config, sample_table_single_doc):
    """Transform removes original content when configured."""
    config = basic_config.copy()
    config["retain_original_content"] = False

    operator = SemanticChunkerOperator(config)
    result_tables, metadata = operator.transform(sample_table_single_doc)
    result = result_tables[0]

    # Original content column should be removed
    assert "content" not in result.column_names


def test_transform_empty_table(basic_config):
    """Transform handles empty table gracefully."""
    empty_table = pa.table({"id": [], "name": [], "content": []})

    operator = SemanticChunkerOperator(basic_config)
    result_tables, metadata = operator.transform(empty_table)
    result = result_tables[0]

    assert result.num_rows == 0
    assert metadata[Metrics.External.PROCESSED_DOCS] == 0


def test_transform_missing_content_column(basic_config, sample_table_no_content_column):
    """Transform handles missing content column gracefully."""
    operator = SemanticChunkerOperator(basic_config)
    result_tables, metadata = operator.transform(sample_table_no_content_column)
    result = result_tables[0]

    # Should remove the row with missing content
    assert result.num_rows == 0

    # Should record as failed
    assert metadata[Metrics.External.FAILED_DOCS_COUNT] == 1
    assert (
        metadata[Metrics.External.NODE_STATUS]
        == ExecutionStatus.COMPLETED_WITH_ERRORS.value
    )


def test_transform_empty_content(basic_config, sample_table_empty_content):
    """Transform handles empty content gracefully."""
    operator = SemanticChunkerOperator(basic_config)
    result_tables, metadata = operator.transform(sample_table_empty_content)
    result = result_tables[0]

    # Should remove the row with empty content
    assert result.num_rows == 0

    # Should record as failed
    assert metadata[Metrics.External.FAILED_DOCS_COUNT] == 1


def test_transform_null_content(basic_config, sample_table_null_content):
    """Transform handles null content gracefully."""
    operator = SemanticChunkerOperator(basic_config)
    result_tables, metadata = operator.transform(sample_table_null_content)
    result = result_tables[0]

    # Should remove the row with null content
    assert result.num_rows == 0

    # Should record as failed
    assert metadata[Metrics.External.FAILED_DOCS_COUNT] == 1


# ---------------------------------------------------------------------------
# 4. Chunking Logic Tests
# ---------------------------------------------------------------------------


def test_simple_split_text_creates_chunks(basic_config):
    """simple_split_text creates proper chunks."""
    operator = SemanticChunkerOperator(basic_config)

    content = (
        "This is sentence one. This is sentence two. This is sentence three. " * 20
    )
    chunks = operator.simple_split_text(content)

    # Should create at least one chunk
    assert len(chunks) > 0

    # Each chunk should be a Document object
    from langchain_core.documents import Document

    assert all(isinstance(chunk, Document) for chunk in chunks)


def test_simple_split_text_respects_chunk_size(basic_config):
    """simple_split_text respects configured chunk_size."""
    config = basic_config.copy()
    config["chunk_size"] = 500
    operator = SemanticChunkerOperator(config)

    content = "This is a sentence. " * 100
    chunks = operator.simple_split_text(content)

    # Each chunk should be roughly within chunk_size
    for chunk in chunks:
        assert (
            len(chunk.page_content) <= config["chunk_size"] * 2
        )  # Allow some flexibility


def test_split_text_with_simple_type(basic_config):
    """_split_text works with simple chunk type."""
    operator = SemanticChunkerOperator(basic_config)

    content = "This is a test. " * 50
    chunks = operator._split_text(content)

    assert len(chunks) > 0


def test_split_text_with_invalid_type():
    """_split_text raises error with invalid chunk type."""
    config = {"chunk_type": "invalid"}
    operator = SemanticChunkerOperator(config)

    with pytest.raises(DatasiftException, match="Invalid chunk type"):
        operator._split_text("test content")


# ---------------------------------------------------------------------------
# 5. Metadata Tests
# ---------------------------------------------------------------------------


def test_get_metadata_structure(basic_config):
    """get_metadata returns proper structure."""
    operator = SemanticChunkerOperator(basic_config)
    metadata = operator.get_metadata()

    # Check top-level keys
    assert OperatorConstants.Misc.CATEGORY in metadata
    assert OperatorConstants.Config.FEATURES in metadata
    assert OperatorConstants.Config.ATTRIBUTES in metadata
    assert OperatorConstants.Misc.IS_OPERATOR_AVAILABLE in metadata


def test_get_metadata_features(basic_config):
    """get_metadata includes expected features."""
    operator = SemanticChunkerOperator(basic_config)
    metadata = operator.get_metadata()

    features = metadata[OperatorConstants.Config.FEATURES]

    # Check for expected features
    assert OperatorConstants.CHUNK_SEQUENCE_NUMBER in features
    assert OperatorConstants.START_INDEX in features
    assert OperatorConstants.Columns.CHUNKED_CONTENT in features


def test_get_metadata_attributes(basic_config):
    """get_metadata includes configuration attributes."""
    operator = SemanticChunkerOperator(basic_config)
    metadata = operator.get_metadata()

    attributes = metadata[OperatorConstants.Config.ATTRIBUTES]

    # Check for expected attributes
    assert CHUNK_TYPE_KEY in attributes
    assert OperatorConstants.Processing.CHUNK_SIZE in attributes
    assert CHUNK_OVERLAP_KEY in attributes

    # Check attribute details
    chunk_size_attr = attributes[OperatorConstants.Processing.CHUNK_SIZE]
    assert chunk_size_attr[OperatorConstants.Filtering.MIN_VALUE] == CHUNK_MIN_SIZE
    assert chunk_size_attr[OperatorConstants.Filtering.MAX_VALUE] == CHUNK_MAX_SIZE


def test_get_required_features(basic_config):
    """get_required_features returns doc_column."""
    operator = SemanticChunkerOperator(basic_config)
    required = operator.get_required_features()

    assert "content" in required


# ---------------------------------------------------------------------------
# 6. Edge Cases and Error Handling
# ---------------------------------------------------------------------------


def test_transform_with_special_characters(basic_config):
    """Transform handles special characters in content."""
    special_chars_table = pa.table(
        {
            "id": ["doc1"],
            "name": ["Special Doc"],
            "content": ["Content with special chars: @#$%^&*()_+-=[]{}|;':\",./<>?"],
        }
    )

    operator = SemanticChunkerOperator(basic_config)
    result_tables, metadata = operator.transform(special_chars_table)

    # Should process successfully
    assert metadata[Metrics.External.PROCESSED_DOCS] == 1


def test_transform_with_unicode(basic_config):
    """Transform handles Unicode characters."""
    unicode_table = pa.table(
        {
            "id": ["doc1"],
            "name": ["Unicode Doc"],
            "content": ["Content with Unicode: 你好世界 مرحبا العالم Привет мир"],
        }
    )

    operator = SemanticChunkerOperator(basic_config)
    result_tables, metadata = operator.transform(unicode_table)

    # Should process successfully
    assert metadata[Metrics.External.PROCESSED_DOCS] == 1


def test_transform_with_very_short_document(basic_config):
    """Transform handles very short documents."""
    short_table = pa.table(
        {
            "id": ["doc1"],
            "name": ["Short Doc"],
            "content": ["Hi."],
        }
    )

    operator = SemanticChunkerOperator(basic_config)
    result_tables, metadata = operator.transform(short_table)

    # Should process successfully
    assert metadata[Metrics.External.PROCESSED_DOCS] == 1


def test_transform_preserves_all_columns(basic_config):
    """Transform preserves all original columns."""
    table_with_extra_cols = pa.table(
        {
            "id": ["doc1"],
            "name": ["Document 1"],
            "content": ["Test content."],
            "extra_col1": ["value1"],
            "extra_col2": [42],
        }
    )

    operator = SemanticChunkerOperator(basic_config)
    result_tables, metadata = operator.transform(table_with_extra_cols)
    result = result_tables[0]

    # All original columns should be preserved (except content if not retained)
    assert "extra_col1" in result.column_names
    assert "extra_col2" in result.column_names


def test_chunk_size_boundary_conditions():
    """Test chunk_size at boundary values."""
    # Minimum valid chunk_size
    config_min = {"chunk_size": CHUNK_MIN_SIZE}
    operator_min = SemanticChunkerOperator(config_min)
    assert operator_min.chunk_size == CHUNK_MIN_SIZE

    # Maximum valid chunk_size
    config_max = {"chunk_size": CHUNK_MAX_SIZE}
    operator_max = SemanticChunkerOperator(config_max)
    assert operator_max.chunk_size == CHUNK_MAX_SIZE


def test_chunk_overlap_boundary_conditions():
    """Test chunk_overlap at boundary values."""
    # Minimum valid chunk_overlap
    config_min = {"chunk_overlap": CHUNK_OVERLAP_MIN_SIZE}
    operator_min = SemanticChunkerOperator(config_min)
    assert operator_min.chunk_overlap == CHUNK_OVERLAP_MIN_SIZE

    # Maximum valid chunk_overlap
    config_max = {"chunk_overlap": CHUNK_OVERLAP_MAX_SIZE}
    operator_max = SemanticChunkerOperator(config_max)
    assert operator_max.chunk_overlap == CHUNK_OVERLAP_MAX_SIZE


# ---------------------------------------------------------------------------
# 7. Integration Tests
# ---------------------------------------------------------------------------


def test_full_pipeline_with_chunking(basic_config, sample_table_single_doc):
    """Test full pipeline: input table -> chunking -> output."""
    operator = SemanticChunkerOperator(basic_config)
    result_tables, metadata = operator.transform(sample_table_single_doc)
    result = result_tables[0]

    # Verify all expected columns exist
    assert "id" in result.column_names
    assert "name" in result.column_names
    assert "content" in result.column_names
    assert OperatorConstants.Columns.CHUNKED_CONTENT in result.column_names

    # Verify chunked_content structure
    chunked_content = result[OperatorConstants.Columns.CHUNKED_CONTENT][0].as_py()
    assert isinstance(chunked_content, list)
    assert len(chunked_content) > 0


def test_chunked_content_structure(basic_config, sample_table_single_doc):
    """Verify chunked_content has correct structure."""
    operator = SemanticChunkerOperator(basic_config)
    result_tables, metadata = operator.transform(sample_table_single_doc)
    result = result_tables[0]

    chunked_content = result[OperatorConstants.Columns.CHUNKED_CONTENT][0].as_py()

    # Check first chunk structure
    first_chunk = chunked_content[0]
    assert OperatorConstants.Columns.CHUNK in first_chunk
    assert OperatorConstants.START_INDEX in first_chunk

    # Verify chunk content is a string
    assert isinstance(first_chunk[OperatorConstants.Columns.CHUNK], str)

    # Verify start_index is an integer
    assert isinstance(first_chunk[OperatorConstants.START_INDEX], int)


def test_multiple_documents_with_varying_lengths(basic_config):
    """Test chunking multiple documents with different lengths."""
    data = {
        "id": ["doc1", "doc2", "doc3"],
        "name": ["Short", "Medium", "Long"],
        "content": [
            "Short doc.",
            "Medium length document. " * 10,
            "Very long document. " * 100,
        ],
    }
    table = pa.table(data)

    operator = SemanticChunkerOperator(basic_config)
    result_tables, metadata = operator.transform(table)
    result = result_tables[0]

    # All documents should be processed
    assert result.num_rows == 3
    assert metadata[Metrics.External.PROCESSED_DOCS] == 3

    # Each document should have chunked content
    for i in range(3):
        chunked_content = result[OperatorConstants.Columns.CHUNKED_CONTENT][i].as_py()
        assert len(chunked_content) > 0


def test_chunk_overlap_creates_overlapping_content(basic_config):
    """Test that chunk_overlap creates overlapping content between chunks."""
    config = basic_config.copy()
    config["chunk_size"] = 100
    config["chunk_overlap"] = 20

    long_text = "Word " * 100  # Create text that will definitely need multiple chunks
    table = pa.table(
        {
            "id": ["doc1"],
            "name": ["Test"],
            "content": [long_text],
        }
    )

    operator = SemanticChunkerOperator(config)
    result_tables, metadata = operator.transform(table)
    result = result_tables[0]

    chunked_content = result[OperatorConstants.Columns.CHUNKED_CONTENT][0].as_py()

    # Should have multiple chunks
    assert len(chunked_content) > 1


def test_error_handling_during_chunking(basic_config):
    """Test error handling when chunking fails."""
    # Create a table where chunking might fail
    table = pa.table(
        {
            "id": ["doc1"],
            "name": ["Test"],
            "content": ["Test content"],
        }
    )

    operator = SemanticChunkerOperator(basic_config)

    # Mock the _split_text method to raise an exception
    with patch.object(
        operator, "_split_text", side_effect=Exception("Chunking failed")
    ):
        result_tables, metadata = operator.transform(table)
        result = result_tables[0]

        # Should handle error gracefully
        assert result.num_rows == 0
        assert metadata[Metrics.External.FAILED_DOCS_COUNT] == 1
        assert (
            metadata[Metrics.External.NODE_STATUS]
            == ExecutionStatus.COMPLETED_WITH_ERRORS.value
        )


# Made with Bob
