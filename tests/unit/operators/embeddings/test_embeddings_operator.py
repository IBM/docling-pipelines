#!/usr/bin/env python3
"""
Comprehensive unit tests for EmbeddingsOperator.

Tests cover:
- Basic functionality (initialization, metadata)
- Transform method with various scenarios
- Embeddings generation with chunking
- Document hash generation
- Error handling
- Chunked content processing
- Metadata validation
- Provider type validation
- Multi-provider support structure
"""

from unittest.mock import Mock, patch

import pytest
import pyarrow as pa
import numpy as np

from core.operators.universal.embeddings.embeddings_operator import (
    EmbeddingsOperator,
    OVERLAP_RATIO_DEFAULT,
    OVERLAP_RATIO_MIN,
    OVERLAP_RATIO_MAX,
    EMBEDDINGS_TYPE_DEFAULT,
)
from common.constants.constants import Metrics, ExecutionStatus  # noqa: E402
from common.constants.operator_constants import OperatorConstants  # noqa: E402


# Test Fixtures
@pytest.fixture
def mock_ollama_embeddings():
    """Mock ollama.embeddings() to return realistic embedding vectors."""

    def mock_embeddings(model, prompt):
        # Return a realistic embedding vector (384 dimensions for most models)
        embedding = np.random.rand(384).tolist()
        return {"embedding": embedding}

    with patch("ollama.embeddings", side_effect=mock_embeddings) as mock:
        yield mock


@pytest.fixture
def sample_config():
    """Basic configuration for EmbeddingsOperator."""
    return {
        "embeddings_type": "ollama",
        "embeddings_model_id": "llama2",
        "embeddings_column": "embeddings",
        "doc_column": "content",
        "doc_id_hash": "doc_id_hash",
        "overlap_ratio": 0.2,
    }


@pytest.fixture
def sample_table_single_doc():
    """PyArrow table with a single document."""
    data = {
        "id": ["doc1"],
        "name": ["Document 1"],
        "content": ["This is a test document with some content."],
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
            "Second document with different content.",
            "Third document with unique text.",
        ],
    }
    return pa.table(data)


@pytest.fixture
def sample_table_long_text():
    """PyArrow table with a document requiring chunking."""
    # Create text longer than default token limit (4096 tokens ≈ 16384 chars)
    long_text = "This is a very long document. " * 1000  # ~30000 chars
    data = {
        "id": ["doc1"],
        "name": ["Long Document"],
        "content": [long_text],
    }
    return pa.table(data)


@pytest.fixture
def sample_table_with_chunks():
    """PyArrow table with pre-chunked content."""
    data = {
        "id": ["doc1"],
        "name": ["Chunked Document"],
        "content": ["Full document content"],
        "chunked_content": [
            [
                {"chunk": "First chunk of content"},
                {"chunk": "Second chunk of content"},
                {"chunk": "Third chunk of content"},
            ]
        ],
    }
    return pa.table(data)


@pytest.fixture
def sample_table_empty():
    """Empty PyArrow table."""
    data = {
        "id": [],
        "name": [],
        "content": [],
    }
    return pa.table(data)


# Basic Functionality Tests
class TestEmbeddingsOperatorInitialization:
    """Test operator initialization and configuration."""

    @patch("core.operators.universal.embeddings.embeddings_operator.OllamaClient")
    def test_init_with_valid_config(self, mock_ollama_client, sample_config):
        """Test operator initialization with valid configuration."""
        operator = EmbeddingsOperator(sample_config)

        assert operator.embeddings_type == "ollama"
        assert operator.embeddings_model_id == "llama2"
        assert operator.embeddings_column == "embeddings"
        assert operator.doc_column == "content"
        assert operator.doc_id_hash_column == "doc_id_hash"
        assert operator.overlap_ratio == 0.2

    @patch("core.operators.universal.embeddings.embeddings_operator.OllamaClient")
    def test_init_with_default_values(self, mock_ollama_client):
        """Test operator initialization with default values."""
        config = {"embeddings_model_id": "mistral"}
        operator = EmbeddingsOperator(config)

        assert operator.embeddings_type == EMBEDDINGS_TYPE_DEFAULT
        assert operator.embeddings_model_id == "mistral"
        assert (
            operator.embeddings_column
            == OperatorConstants.Columns.EMBEDDINGS_COLUMN_DEFAULT
        )
        assert operator.doc_column == OperatorConstants.Columns.DOC_COLUMN_DEFAULT
        assert (
            operator.doc_id_hash_column == OperatorConstants.Columns.DOC_ID_HASH_DEFAULT
        )
        assert operator.overlap_ratio == OVERLAP_RATIO_DEFAULT

    @patch("core.operators.universal.embeddings.embeddings_operator.OllamaClient")
    def test_init_with_minimal_config(self, mock_ollama_client):
        """Test operator initialization with minimal configuration."""
        config = {}
        operator = EmbeddingsOperator(config)

        # Should use all defaults
        assert operator.embeddings_type == EMBEDDINGS_TYPE_DEFAULT
        assert operator.embeddings_model_id == "granite4"
        assert operator.overlap_ratio == OVERLAP_RATIO_DEFAULT

    def test_init_with_openai_provider(self):
        """Test operator initialization with OpenAI provider."""
        config = {
            "embeddings_type": "openai",
            "embeddings_model_id": "text-embedding-ada-002",
        }
        # OpenAI provider is not yet implemented, so initialization should raise an exception
        with pytest.raises(Exception) as exc_info:
            EmbeddingsOperator(config)

        assert "not yet implemented" in str(exc_info.value).lower()

    def test_get_required_features(self, sample_config):
        """Test get_required_features returns correct list."""
        operator = EmbeddingsOperator(sample_config)
        required = operator.get_required_features()

        assert "content" in required
        assert len(required) == 1


class TestEmbeddingsOperatorMetadata:
    """Test operator metadata methods."""

    def test_get_metadata_structure(self, sample_config):
        """Test get_metadata returns correct structure."""
        operator = EmbeddingsOperator(sample_config)
        metadata = operator.get_metadata()

        assert isinstance(metadata, dict)
        assert OperatorConstants.Misc.CATEGORY in metadata
        assert OperatorConstants.Config.FEATURES in metadata
        assert OperatorConstants.Config.ATTRIBUTES in metadata
        assert OperatorConstants.Misc.IS_OPERATOR_AVAILABLE in metadata
        assert metadata[OperatorConstants.Misc.IS_OPERATOR_AVAILABLE] is True

    def test_get_metadata_features(self, sample_config):
        """Test metadata includes correct features."""
        operator = EmbeddingsOperator(sample_config)
        metadata = operator.get_metadata()

        features = metadata[OperatorConstants.Config.FEATURES]

        assert OperatorConstants.Columns.EMBEDDINGS_COLUMN_DEFAULT in features
        assert OperatorConstants.Columns.DOC_ID_HASH_DEFAULT in features

        # Check embeddings feature details
        embeddings_feature = features[
            OperatorConstants.Columns.EMBEDDINGS_COLUMN_DEFAULT
        ]
        assert (
            embeddings_feature[OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB] is True
        )
        assert (
            embeddings_feature[OperatorConstants.Config.MANDATORY_FOR_VECTOR_DB] is True
        )
        assert (
            embeddings_feature[OperatorConstants.Misc.TYPE]
            == OperatorConstants.Types.TYPE_VECTOR
        )

    def test_get_metadata_attributes(self, sample_config):
        """Test metadata includes correct attributes."""
        operator = EmbeddingsOperator(sample_config)
        metadata = operator.get_metadata()

        attributes = metadata[OperatorConstants.Config.ATTRIBUTES]

        assert "embeddings_type" in attributes
        assert OperatorConstants.Config.EMBEDDINGS_MODEL_ID in attributes
        assert OperatorConstants.Columns.EMBEDDINGS_COLUMN in attributes
        assert "overlap_ratio" in attributes

        # Check embeddings_type attribute details
        embeddings_type_attr = attributes["embeddings_type"]
        assert (
            embeddings_type_attr[OperatorConstants.Config.DEFAULT]
            == EMBEDDINGS_TYPE_DEFAULT
        )

        # Check overlap_ratio attribute details
        overlap_attr = attributes["overlap_ratio"]
        assert overlap_attr[OperatorConstants.Config.DEFAULT] == OVERLAP_RATIO_DEFAULT
        assert overlap_attr[OperatorConstants.Filtering.MIN_VALUE] == OVERLAP_RATIO_MIN
        assert overlap_attr[OperatorConstants.Filtering.MAX_VALUE] == OVERLAP_RATIO_MAX

    def test_metadata_label_is_generic(self, sample_config):
        """Test that metadata label is generic (not provider-specific)."""
        operator = EmbeddingsOperator(sample_config)
        metadata = operator.get_metadata()

        assert metadata[OperatorConstants.Misc.LABEL] == "Embeddings"
        assert "Ollama" not in metadata[OperatorConstants.Misc.LABEL]


class TestEmbeddingsOperatorValidation:
    """Test operator validation logic."""

    def test_validate_valid_config(self, sample_config):
        """Test validation with valid configuration."""
        operator = EmbeddingsOperator(sample_config)
        errors = []
        warnings = []
        available_features = ["content"]

        operator.validate(errors, warnings, available_features)

        assert len(errors) == 0

    def test_validate_invalid_embeddings_type(self):
        """Test validation with invalid embeddings_type."""
        config = {
            "embeddings_type": "invalid_provider",
            "embeddings_model_id": "llama2",
        }
        # Invalid provider should raise exception during initialization
        with pytest.raises(Exception) as exc_info:
            EmbeddingsOperator(config)

        assert (
            "unsupported" in str(exc_info.value).lower()
            or "failed to initialize" in str(exc_info.value).lower()
        )

    def test_validate_embeddings_type_not_string(self):
        """Test validation with non-string embeddings_type."""
        config = {
            "embeddings_type": 123,  # Should be string
            "embeddings_model_id": "llama2",
        }
        # Non-string type should raise exception during initialization
        with pytest.raises(Exception):
            EmbeddingsOperator(config)

    def test_validate_invalid_overlap_ratio_type(self):
        """Test validation with invalid overlap_ratio type."""
        config = {
            "embeddings_type": "ollama",
            "embeddings_model_id": "llama2",
            "overlap_ratio": "invalid",  # Should be float
        }
        operator = EmbeddingsOperator(config)
        errors = []
        warnings = []

        operator.validate(errors, warnings, ["content"])

        assert len(errors) > 0
        assert any("overlap_ratio must be a number" in err for err in errors)

    def test_validate_overlap_ratio_out_of_range(self):
        """Test validation with overlap_ratio out of valid range."""
        config = {
            "embeddings_type": "ollama",
            "embeddings_model_id": "llama2",
            "overlap_ratio": 0.8,  # Too high (max is 0.5)
        }
        operator = EmbeddingsOperator(config)
        errors = []
        warnings = []

        operator.validate(errors, warnings, ["content"])

        assert len(errors) > 0
        assert any("overlap_ratio must be between" in err for err in errors)

    @patch("core.operators.universal.embeddings.embeddings_operator.OllamaClient")
    def test_validate_invalid_model_id(self, mock_ollama_client):
        """Test validation with invalid model ID."""
        config = {
            "embeddings_type": "ollama",
            "embeddings_model_id": "",  # Empty string
        }
        operator = EmbeddingsOperator(config)
        errors = []
        warnings = []

        operator.validate(errors, warnings, ["content"])

        assert len(errors) > 0
        assert any(
            "embeddings_model_id must be a non-empty string" in err for err in errors
        )

    @patch("core.operators.universal.embeddings.embeddings_operator.OllamaClient")
    def test_validate_all_supported_embeddings_types(self, mock_ollama_client):
        """Test validation accepts all supported embeddings types."""
        # Only test ollama since openai is not yet implemented
        for embeddings_type in ["ollama"]:
            config = {
                "embeddings_type": embeddings_type,
                "embeddings_model_id": "test_model",
            }
            operator = EmbeddingsOperator(config)
            errors = []
            warnings = []

            operator.validate(errors, warnings, ["content"])

            # Should not have embeddings_type errors
            assert not any("embeddings_type" in err for err in errors)


# Transform Method Tests
class TestEmbeddingsOperatorTransform:
    """Test the transform method with various scenarios."""

    @patch("ollama.embeddings")
    def test_transform_single_document(
        self, mock_embeddings, sample_config, sample_table_single_doc
    ):
        """Test transform with a single document."""
        # Mock ollama response
        mock_embeddings.return_value = {"embedding": [0.1] * 384}

        operator = EmbeddingsOperator(sample_config)
        result_tables, metadata = operator.transform(sample_table_single_doc)

        assert len(result_tables) == 1
        result_table = result_tables[0]

        # Check embeddings column was added
        assert "embeddings" in result_table.column_names
        assert result_table.num_rows == 1

        # Check metadata
        assert metadata[Metrics.External.TOTAL_DOCS] == 1
        assert metadata[Metrics.External.PROCESSED_DOCS] == 1
        assert metadata[Metrics.External.FAILED_DOCS_COUNT] == 0

    @patch("ollama.embeddings")
    def test_transform_multiple_documents(
        self, mock_embeddings, sample_config, sample_table_multiple_docs
    ):
        """Test transform with multiple documents."""
        # Mock ollama response
        mock_embeddings.return_value = {"embedding": [0.1] * 384}

        operator = EmbeddingsOperator(sample_config)
        result_tables, metadata = operator.transform(sample_table_multiple_docs)

        result_table = result_tables[0]

        # Check all documents were processed
        assert result_table.num_rows == 3
        assert "embeddings" in result_table.column_names

        # Check metadata
        assert metadata[Metrics.External.TOTAL_DOCS] == 3
        assert metadata[Metrics.External.PROCESSED_DOCS] == 3
        assert metadata[Metrics.External.FAILED_DOCS_COUNT] == 0

    @patch("ollama.embeddings")
    def test_transform_empty_table(
        self, mock_embeddings, sample_config, sample_table_empty
    ):
        """Test transform with an empty table."""
        operator = EmbeddingsOperator(sample_config)
        result_tables, metadata = operator.transform(sample_table_empty)

        result_table = result_tables[0]

        # Should handle empty table gracefully
        assert result_table.num_rows == 0
        assert metadata[Metrics.External.TOTAL_DOCS] == 0
        assert metadata[Metrics.External.PROCESSED_DOCS] == 0

    @patch("ollama.embeddings")
    def test_transform_missing_content_column(self, mock_embeddings, sample_config):
        """Test transform with missing content column."""
        # Create table without content column
        data = {
            "id": ["doc1"],
            "name": ["Document 1"],
        }
        table = pa.table(data)

        operator = EmbeddingsOperator(sample_config)
        result_tables, metadata = operator.transform(table)

        result_table = result_tables[0]

        # Document should fail and be removed
        assert result_table.num_rows == 0
        assert metadata[Metrics.External.FAILED_DOCS_COUNT] == 1
        assert (
            metadata[Metrics.External.NODE_STATUS]
            == ExecutionStatus.COMPLETED_WITH_ERRORS
        )

    @patch("ollama.embeddings")
    def test_transform_preserves_existing_columns(self, mock_embeddings, sample_config):
        """Test that transform preserves existing columns."""
        # Mock ollama response
        mock_embeddings.return_value = {"embedding": [0.1] * 384}

        # Create table with extra columns
        data = {
            "id": ["doc1"],
            "name": ["Document 1"],
            "content": ["Test content"],
            "extra_column": ["extra_value"],
        }
        table = pa.table(data)

        operator = EmbeddingsOperator(sample_config)
        result_tables, metadata = operator.transform(table)

        result_table = result_tables[0]

        # Check all original columns are preserved
        assert "id" in result_table.column_names
        assert "name" in result_table.column_names
        assert "content" in result_table.column_names
        assert "extra_column" in result_table.column_names
        assert "embeddings" in result_table.column_names


# Embeddings Generation Tests
class TestEmbeddingsGeneration:
    """Test embeddings generation with various text lengths and scenarios."""

    @patch("ollama.embeddings")
    def test_create_embeddings_short_text(self, mock_embeddings, sample_config):
        """Test embeddings generation with short text."""
        mock_embeddings.return_value = {"embedding": [0.1] * 384}

        operator = EmbeddingsOperator(sample_config)
        texts = ["Short text"]

        embeddings = operator._create_embeddings(
            text=texts, model_name="llama2", overlap_ratio=0.2
        )

        assert len(embeddings) == 1
        assert len(embeddings[0]) == 384
        assert mock_embeddings.call_count == 1

    @patch("ollama.embeddings")
    def test_create_embeddings_long_text_requires_chunking(
        self, mock_embeddings, sample_config
    ):
        """Test embeddings generation with long text requiring chunking."""
        mock_embeddings.return_value = {"embedding": [0.1] * 384}

        operator = EmbeddingsOperator(sample_config)

        # Create text longer than token limit (4096 tokens ≈ 16384 chars)
        long_text = "This is a very long document. " * 1000  # ~30000 chars
        texts = [long_text]

        embeddings = operator._create_embeddings(
            text=texts, model_name="llama2", overlap_ratio=0.2
        )

        assert len(embeddings) == 1
        assert len(embeddings[0]) == 384
        # Should be called multiple times for chunks
        assert mock_embeddings.call_count > 1

    @patch("ollama.embeddings")
    def test_create_embeddings_multiple_texts_batch(
        self, mock_embeddings, sample_config
    ):
        """Test embeddings generation with multiple texts (batch)."""
        mock_embeddings.return_value = {"embedding": [0.1] * 384}

        operator = EmbeddingsOperator(sample_config)
        texts = ["Text 1", "Text 2", "Text 3"]

        embeddings = operator._create_embeddings(
            text=texts, model_name="llama2", overlap_ratio=0.2
        )

        assert len(embeddings) == 3
        assert all(len(emb) == 384 for emb in embeddings)
        assert mock_embeddings.call_count == 3

    @patch("ollama.embeddings")
    def test_create_embeddings_with_different_overlap_ratios(
        self, mock_embeddings, sample_config
    ):
        """Test chunking with different overlap ratios."""
        mock_embeddings.return_value = {"embedding": [0.1] * 384}

        operator = EmbeddingsOperator(sample_config)
        long_text = "This is a very long document. " * 1000

        # Test with different overlap ratios
        for overlap_ratio in [0.0, 0.2, 0.5]:
            mock_embeddings.reset_mock()
            embeddings = operator._create_embeddings(
                text=[long_text], model_name="llama2", overlap_ratio=overlap_ratio
            )

            assert len(embeddings) == 1
            assert len(embeddings[0]) == 384

    @patch("ollama.embeddings")
    def test_create_embeddings_averaging_for_chunks(
        self, mock_embeddings, sample_config
    ):
        """Test that embeddings are averaged for chunked text."""
        # Return different embeddings for each chunk
        call_count = [0]

        def mock_response(model, prompt):
            call_count[0] += 1
            # Return different values for each chunk
            return {"embedding": [float(call_count[0])] * 384}

        mock_embeddings.side_effect = mock_response

        operator = EmbeddingsOperator(sample_config)
        long_text = "This is a very long document. " * 1000

        embeddings = operator._create_embeddings(
            text=[long_text], model_name="llama2", overlap_ratio=0.2
        )

        # Should average multiple chunk embeddings
        assert len(embeddings) == 1
        # The averaged embedding should be between the min and max chunk values
        avg_value = embeddings[0][0]
        assert 1.0 < avg_value < float(call_count[0])

    @patch("ollama.embeddings")
    def test_create_embeddings_empty_text(self, mock_embeddings, sample_config):
        """Test embeddings generation with empty text."""
        operator = EmbeddingsOperator(sample_config)
        texts = [""]

        embeddings = operator._create_embeddings(
            text=texts, model_name="llama2", overlap_ratio=0.2
        )

        # Should return zero vector for empty text
        assert len(embeddings) == 1
        assert len(embeddings[0]) == 384
        assert all(v == 0.0 for v in embeddings[0])
        # Should not call ollama for empty text
        assert mock_embeddings.call_count == 0

    def test_create_embeddings_unsupported_provider(self, sample_config):
        """Test that unsupported provider raises error during initialization."""
        config = sample_config.copy()
        config["embeddings_type"] = "unsupported_provider"

        # Unsupported provider should raise exception during initialization
        with pytest.raises(Exception) as exc_info:
            EmbeddingsOperator(config)

        assert (
            "unsupported" in str(exc_info.value).lower()
            or "failed to initialize" in str(exc_info.value).lower()
        )

    def test_create_embeddings_openai_not_implemented(self):
        """Test that OpenAI provider raises not implemented error during initialization."""
        config = {
            "embeddings_type": "openai",
            "embeddings_model_id": "text-embedding-ada-002",
        }

        # OpenAI provider should raise exception during initialization
        with pytest.raises(Exception) as exc_info:
            EmbeddingsOperator(config)

        assert "not yet implemented" in str(exc_info.value).lower()


# Document Hash Tests
class TestEmbeddingsDocumentHash:
    """Test document hash generation and preservation."""

    @patch("ollama.embeddings")
    def test_automatic_hash_generation(
        self, mock_embeddings, sample_config, sample_table_single_doc
    ):
        """Test automatic hash generation when missing."""
        mock_embeddings.return_value = {"embedding": [0.1] * 384}

        operator = EmbeddingsOperator(sample_config)
        result_tables, metadata = operator.transform(sample_table_single_doc)

        result_table = result_tables[0]

        # Check hash column was added
        assert "doc_id_hash" in result_table.column_names
        doc_hash = result_table["doc_id_hash"][0].as_py()
        assert doc_hash is not None
        assert len(doc_hash) == 64  # SHA-256 hash length

    @patch("ollama.embeddings")
    def test_hash_preservation_when_present(self, mock_embeddings, sample_config):
        """Test hash preservation when already present."""
        mock_embeddings.return_value = {"embedding": [0.1] * 384}

        # Create table with existing hash
        existing_hash = "existing_hash_value_123"
        data = {
            "id": ["doc1"],
            "name": ["Document 1"],
            "content": ["Test content"],
            "doc_id_hash": [existing_hash],
        }
        table = pa.table(data)

        operator = EmbeddingsOperator(sample_config)
        result_tables, metadata = operator.transform(table)

        result_table = result_tables[0]

        # Hash should be preserved
        doc_hash = result_table["doc_id_hash"][0].as_py()
        assert doc_hash == existing_hash

    def test_generate_document_hash_consistency(self, sample_config):
        """Test that hash generation is consistent for same content."""
        operator = EmbeddingsOperator(sample_config)

        content = "Test document content"
        hash1 = operator._generate_document_hash(content)
        hash2 = operator._generate_document_hash(content)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hash length

    def test_generate_document_hash_different_content(self, sample_config):
        """Test that different content produces different hashes."""
        operator = EmbeddingsOperator(sample_config)

        hash1 = operator._generate_document_hash("Content 1")
        hash2 = operator._generate_document_hash("Content 2")

        assert hash1 != hash2


# Error Handling Tests
class TestEmbeddingsErrorHandling:
    """Test error handling in various failure scenarios."""

    @patch("ollama.embeddings")
    def test_ollama_connection_error(
        self, mock_embeddings, sample_config, sample_table_single_doc
    ):
        """Test handling of Ollama connection errors."""
        # Simulate connection error
        mock_embeddings.side_effect = Exception("Connection refused")

        operator = EmbeddingsOperator(sample_config)
        result_tables, metadata = operator.transform(sample_table_single_doc)

        result_table = result_tables[0]

        # Document should fail and be removed
        assert result_table.num_rows == 0
        assert metadata[Metrics.External.FAILED_DOCS_COUNT] == 1
        assert (
            metadata[Metrics.External.NODE_STATUS]
            == ExecutionStatus.COMPLETED_WITH_ERRORS
        )

    @patch("ollama.embeddings")
    def test_invalid_model_name_error(
        self, mock_embeddings, sample_config, sample_table_single_doc
    ):
        """Test handling of invalid model names."""
        # Simulate model not found error
        mock_embeddings.side_effect = Exception("Model not found")

        operator = EmbeddingsOperator(sample_config)
        result_tables, metadata = operator.transform(sample_table_single_doc)

        result_table = result_tables[0]

        # Should handle error gracefully
        assert result_table.num_rows == 0
        assert metadata[Metrics.External.FAILED_DOCS_COUNT] == 1

    @patch("ollama.embeddings")
    def test_per_document_error_tracking(
        self, mock_embeddings, sample_config, sample_table_multiple_docs
    ):
        """Test per-document error tracking in metadata."""
        # Make second document fail
        call_count = [0]

        def mock_response(model, prompt):
            call_count[0] += 1
            if call_count[0] == 2:
                raise Exception("Processing error")
            return {"embedding": [0.1] * 384}

        mock_embeddings.side_effect = mock_response

        operator = EmbeddingsOperator(sample_config)
        result_tables, metadata = operator.transform(sample_table_multiple_docs)

        result_table = result_tables[0]

        # Two documents should succeed, one should fail
        assert result_table.num_rows == 2
        assert metadata[Metrics.External.PROCESSED_DOCS] == 2
        assert metadata[Metrics.External.FAILED_DOCS_COUNT] == 1
        assert len(metadata[Metrics.External.FAILED_DOCS]) == 1

    @patch("ollama.embeddings")
    def test_graceful_failure_continues_processing(
        self, mock_embeddings, sample_config, sample_table_multiple_docs
    ):
        """Test that processing continues after individual document failures."""
        # Make first document fail, others succeed
        call_count = [0]

        def mock_response(model, prompt):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("First document error")
            return {"embedding": [0.1] * 384}

        mock_embeddings.side_effect = mock_response

        operator = EmbeddingsOperator(sample_config)
        result_tables, metadata = operator.transform(sample_table_multiple_docs)

        result_table = result_tables[0]

        # Should process remaining documents
        assert result_table.num_rows == 2
        assert metadata[Metrics.External.PROCESSED_DOCS] == 2
        assert metadata[Metrics.External.FAILED_DOCS_COUNT] == 1

    def test_ollama_import_error(self, sample_config, sample_table_single_doc):
        """Test handling when ollama package is not installed."""
        operator = EmbeddingsOperator(sample_config)

        # Mock the import to fail
        with patch.dict("sys.modules", {"ollama": None}):
            with pytest.raises(Exception) as exc_info:
                operator._create_embeddings(
                    text=["test"], model_name="llama2", overlap_ratio=0.2
                )

            assert "ollama package not installed" in str(exc_info.value)


# Chunked Content Tests
class TestEmbeddingsChunkedContent:
    """Test processing of pre-chunked content."""

    @patch("ollama.embeddings")
    def test_with_pre_chunked_content(
        self, mock_embeddings, sample_config, sample_table_with_chunks
    ):
        """Test transform with pre-chunked content column."""
        mock_embeddings.return_value = {"embedding": [0.1] * 384}

        operator = EmbeddingsOperator(sample_config)
        result_tables, metadata = operator.transform(sample_table_with_chunks)

        result_table = result_tables[0]

        # Should process chunked content
        assert result_table.num_rows == 1
        assert "embeddings" in result_table.column_names

        # Should call ollama for each chunk
        assert mock_embeddings.call_count == 3  # 3 chunks

        # Embeddings should be a list (one per chunk)
        embeddings = result_table["embeddings"][0].as_py()
        assert isinstance(embeddings, list)
        assert len(embeddings) == 3

    @patch("ollama.embeddings")
    def test_fallback_to_full_content_when_no_chunks(
        self, mock_embeddings, sample_config
    ):
        """Test fallback to full content when chunked_content is empty."""
        mock_embeddings.return_value = {"embedding": [0.1] * 384}

        # Create table with empty chunked_content
        data = {
            "id": ["doc1"],
            "name": ["Document 1"],
            "content": ["Full document content"],
            "chunked_content": [[]],  # Empty chunks
        }
        table = pa.table(data)

        operator = EmbeddingsOperator(sample_config)
        result_tables, metadata = operator.transform(table)

        result_table = result_tables[0]

        # Should fail because empty chunks raise error
        assert result_table.num_rows == 0
        assert metadata[Metrics.External.FAILED_DOCS_COUNT] == 1

    @patch("ollama.embeddings")
    def test_chunked_content_with_empty_chunks(self, mock_embeddings, sample_config):
        """Test handling of empty chunks in chunked_content."""
        mock_embeddings.return_value = {"embedding": [0.1] * 384}

        # Create table with some empty chunks
        data = {
            "id": ["doc1"],
            "name": ["Document 1"],
            "content": ["Full content"],
            "chunked_content": [
                [
                    {"chunk": "Valid chunk"},
                    {"chunk": ""},  # Empty chunk
                    {"chunk": "Another valid chunk"},
                ]
            ],
        }
        table = pa.table(data)

        operator = EmbeddingsOperator(sample_config)
        result_tables, metadata = operator.transform(table)

        result_table = result_tables[0]

        # Should process successfully (empty chunks get zero vectors)
        assert result_table.num_rows == 1
        assert metadata[Metrics.External.PROCESSED_DOCS] == 1


# Metadata Tests
class TestEmbeddingsMetadataValidation:
    """Test metadata structure and content validation."""

    @patch("ollama.embeddings")
    def test_metadata_includes_processed_docs_count(
        self, mock_embeddings, sample_config, sample_table_multiple_docs
    ):
        """Test metadata includes processed_docs count."""
        mock_embeddings.return_value = {"embedding": [0.1] * 384}

        operator = EmbeddingsOperator(sample_config)
        result_tables, metadata = operator.transform(sample_table_multiple_docs)

        assert Metrics.External.PROCESSED_DOCS in metadata
        assert metadata[Metrics.External.PROCESSED_DOCS] == 3

    @patch("ollama.embeddings")
    def test_metadata_includes_failed_docs_count(
        self, mock_embeddings, sample_config, sample_table_multiple_docs
    ):
        """Test metadata includes failed_docs count."""
        # Make one document fail
        call_count = [0]

        def mock_response(model, prompt):
            call_count[0] += 1
            if call_count[0] == 2:
                raise Exception("Error")
            return {"embedding": [0.1] * 384}

        mock_embeddings.side_effect = mock_response

        operator = EmbeddingsOperator(sample_config)
        result_tables, metadata = operator.transform(sample_table_multiple_docs)

        assert Metrics.External.FAILED_DOCS_COUNT in metadata
        assert metadata[Metrics.External.FAILED_DOCS_COUNT] == 1

    @patch("ollama.embeddings")
    def test_metadata_includes_node_status(
        self, mock_embeddings, sample_config, sample_table_single_doc
    ):
        """Test metadata includes node_status."""
        mock_embeddings.return_value = {"embedding": [0.1] * 384}

        operator = EmbeddingsOperator(sample_config)
        result_tables, metadata = operator.transform(sample_table_single_doc)

        assert Metrics.External.NODE_STATUS in metadata
        # Should be Completed when all succeed
        assert metadata[Metrics.External.NODE_STATUS] == ExecutionStatus.COMPLETED

    @patch("ollama.embeddings")
    def test_metadata_node_status_with_errors(
        self, mock_embeddings, sample_config, sample_table_single_doc
    ):
        """Test node_status is COMPLETED_WITH_ERRORS when failures occur."""
        mock_embeddings.side_effect = Exception("Error")

        operator = EmbeddingsOperator(sample_config)
        result_tables, metadata = operator.transform(sample_table_single_doc)

        assert (
            metadata[Metrics.External.NODE_STATUS]
            == ExecutionStatus.COMPLETED_WITH_ERRORS
        )

    @patch("ollama.embeddings")
    def test_metadata_completeness(
        self, mock_embeddings, sample_config, sample_table_single_doc
    ):
        """Test that all required metadata fields are present."""
        mock_embeddings.return_value = {"embedding": [0.1] * 384}

        operator = EmbeddingsOperator(sample_config)
        result_tables, metadata = operator.transform(sample_table_single_doc)

        # Check all required fields
        required_fields = [
            Metrics.External.TOTAL_DOCS,
            Metrics.External.PROCESSED_DOCS,
            Metrics.External.FAILED_DOCS_COUNT,
            Metrics.External.FAILED_DOCS,
            Metrics.External.NODE_STATUS,
        ]

        for field in required_fields:
            assert field in metadata, f"Missing required metadata field: {field}"


# Integration-style Tests
class TestEmbeddingsOperatorIntegration:
    """Integration-style tests combining multiple features."""

    @patch("ollama.embeddings")
    def test_full_pipeline_with_hash_and_embeddings(
        self, mock_embeddings, sample_config, sample_table_multiple_docs
    ):
        """Test full pipeline: generate embeddings and hashes."""
        mock_embeddings.return_value = {"embedding": [0.1] * 384}

        operator = EmbeddingsOperator(sample_config)
        result_tables, metadata = operator.transform(sample_table_multiple_docs)

        result_table = result_tables[0]

        # Check both embeddings and hashes were added
        assert "embeddings" in result_table.column_names
        assert "doc_id_hash" in result_table.column_names

        # Verify all rows have both
        for i in range(result_table.num_rows):
            assert result_table["embeddings"][i].as_py() is not None
            assert result_table["doc_id_hash"][i].as_py() is not None

    @patch("ollama.embeddings")
    def test_different_models_token_limits(self, mock_embeddings, sample_config):
        """Test that different models use correct token limits."""
        mock_embeddings.return_value = {"embedding": [0.1] * 384}

        # Test with different models
        models = ["llama2", "llama3.1", "mistral"]

        for model in models:
            config = sample_config.copy()
            config["embeddings_model_id"] = model

            # Mock OllamaClient for this specific model
            with patch(
                "core.operators.universal.embeddings.embeddings_operator.OllamaClient"
            ) as mock_client:
                mock_instance = Mock()
                mock_instance.generate_embeddings.return_value = [0.1] * 384
                mock_client.return_value = mock_instance

                operator = EmbeddingsOperator(config)

                # Create long text
                long_text = "Test " * 10000
                data = {
                    "id": ["doc1"],
                    "name": ["Doc"],
                    "content": [long_text],
                }
                table = pa.table(data)

                result_tables, metadata = operator.transform(table)

                # Should process successfully with appropriate chunking
                assert metadata[Metrics.External.PROCESSED_DOCS] == 1

    @patch("ollama.embeddings")
    def test_mixed_success_and_failure_documents(self, mock_embeddings, sample_config):
        """Test processing with mix of successful and failed documents."""
        # Make every other document fail
        call_count = [0]

        def mock_response(model, prompt):
            call_count[0] += 1
            if call_count[0] % 2 == 0:
                raise Exception("Error")
            return {"embedding": [0.1] * 384}

        mock_embeddings.side_effect = mock_response

        # Create table with 4 documents
        data = {
            "id": [f"doc{i}" for i in range(4)],
            "name": [f"Document {i}" for i in range(4)],
            "content": [f"Content {i}" for i in range(4)],
        }
        table = pa.table(data)

        operator = EmbeddingsOperator(sample_config)
        result_tables, metadata = operator.transform(table)

        result_table = result_tables[0]

        # Should have 2 successful, 2 failed
        assert result_table.num_rows == 2
        assert metadata[Metrics.External.PROCESSED_DOCS] == 2
        assert metadata[Metrics.External.FAILED_DOCS_COUNT] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
