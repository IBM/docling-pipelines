#!/usr/bin/env python3
"""
Comprehensive unit tests for refactored EmbeddingsOperator using unified LLM adapters.

Tests cover:
- Initialization with litellm and watsonx providers
- Transform method with various scenarios
- Unified adapter integration
- Error handling
- Configuration validation
- Metadata validation
"""

from unittest.mock import Mock, patch

import pyarrow as pa
import pytest

from datasift.core.constants.constants import ExecutionStatus, Metrics
from datasift.core.constants.operator_constants import OperatorConstants
from datasift.core.operators.functional.embeddings import EmbeddingsOperator


# Test Fixtures
@pytest.fixture
def litellm_config():
    """Configuration for LiteLLM provider."""
    return {
        "provider": "litellm",
        "model_id": "text-embedding-3-small",
        "embeddings_column": "embeddings",
        "provider_config": {
            "api_key": "<test-api-key>",
        },
    }


@pytest.fixture
def watsonx_config():
    """Configuration for Watsonx provider."""
    return {
        "provider": "watsonx",
        "model_id": "ibm/slate-125m-english-rtrvr",
        "embeddings_column": "embeddings",
        "provider_config": {
            "api_key": "<test-api-key>",
            "api_base": "https://us-south.ml.cloud.ibm.com",
            "container_id": "test-project-id",
            "container_kind": "project",
        },
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
def sample_table_empty():
    """Empty PyArrow table."""
    data = {
        "id": [],
        "name": [],
        "content": [],
    }
    return pa.table(data)


@pytest.fixture
def mock_llm_adapter():
    """Mock LLM adapter for testing."""
    adapter = Mock()
    adapter.generate_embeddings_batch.return_value = [[0.1] * 384, [0.2] * 384, [0.3] * 384]
    adapter.get_embedding_dimension.return_value = 384
    adapter.validate.return_value = {"valid": True, "errors": [], "warnings": []}
    return adapter


# Initialization Tests
class TestEmbeddingsOperatorInitialization:
    """Test operator initialization with unified adapters."""

    @patch("datasift.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_init_with_litellm_provider(self, mock_factory, litellm_config, mock_llm_adapter):
        """Test initialization with LiteLLM provider."""
        mock_factory.return_value = mock_llm_adapter

        operator = EmbeddingsOperator(litellm_config)

        assert operator.provider == "litellm"
        assert operator.model_id == "text-embedding-3-small"
        assert operator.embeddings_column == "embeddings"
        mock_factory.assert_called_once_with(
            provider="litellm",
            model_id="text-embedding-3-small",
            provider_config={"api_key": "<test-api-key>"},
        )

    @patch("datasift.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_init_with_watsonx_provider(self, mock_factory, watsonx_config, mock_llm_adapter):
        """Test initialization with Watsonx provider."""
        mock_factory.return_value = mock_llm_adapter

        operator = EmbeddingsOperator(watsonx_config)

        assert operator.provider == "watsonx"
        assert operator.model_id == "ibm/slate-125m-english-rtrvr"
        mock_factory.assert_called_once_with(
            provider="watsonx",
            model_id="ibm/slate-125m-english-rtrvr",
            provider_config={
                "api_key": "<test-api-key>",
                "api_base": "https://us-south.ml.cloud.ibm.com",
                "container_id": "test-project-id",
                "container_kind": "project",
            },
        )

    @patch("datasift.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_init_with_default_values(self, mock_factory, mock_llm_adapter):
        """Test initialization with default values."""
        mock_factory.return_value = mock_llm_adapter

        config = {"model_id": "text-embedding-3-small"}
        operator = EmbeddingsOperator(config)

        assert operator.provider == "litellm"  # Default provider
        assert operator.model_id == "text-embedding-3-small"
        assert operator.embeddings_column == OperatorConstants.Columns.EMBEDDINGS_COLUMN_DEFAULT

    def test_init_with_invalid_provider(self):
        """Test initialization with invalid provider."""
        config = {
            "provider": "invalid_provider",
            "model_id": "test-model",
        }

        with pytest.raises(Exception) as exc_info:
            EmbeddingsOperator(config)

        assert "unsupported" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower()

    @patch("datasift.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_get_required_features(self, mock_factory, litellm_config, mock_llm_adapter):
        """Test get_required_features returns correct list."""
        mock_factory.return_value = mock_llm_adapter

        operator = EmbeddingsOperator(litellm_config)
        required = operator.get_required_features()

        assert "content" in required
        assert len(required) == 1

    @patch("datasift.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_adapter_validation_called_on_init(self, mock_factory, litellm_config, mock_llm_adapter):
        """Test that validate() is called during operator initialization."""
        mock_llm_adapter.validate.return_value = {"valid": True, "errors": [], "warnings": []}
        mock_factory.return_value = mock_llm_adapter

        _ = EmbeddingsOperator(litellm_config)

        # Verify adapter was created and validated
        mock_factory.assert_called_once()
        mock_llm_adapter.validate.assert_called_once()

    @patch("datasift.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_adapter_validation_failure_raises_error(self, mock_factory, litellm_config, mock_llm_adapter):
        """Test that validation failures raise DatasiftException."""
        from datasift.exceptions.datasift_exceptions import DatasiftException

        mock_llm_adapter.validate.return_value = {"valid": False, "errors": ["API key is required"], "warnings": []}
        mock_factory.return_value = mock_llm_adapter

        with pytest.raises(DatasiftException, match="API key is required"):
            EmbeddingsOperator(litellm_config)

    @patch("datasift.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_adapter_validation_with_warnings(self, mock_factory, litellm_config, mock_llm_adapter):
        """Test that warnings don't block operator initialization."""
        mock_llm_adapter.validate.return_value = {
            "valid": True,
            "errors": [],
            "warnings": ["Consider setting api_base for better performance"],
        }
        mock_factory.return_value = mock_llm_adapter

        operator = EmbeddingsOperator(litellm_config)

        # Operator should be created successfully
        assert operator is not None


# Metadata Tests
class TestEmbeddingsOperatorMetadata:
    """Test operator metadata methods."""

    @patch("datasift.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_get_metadata_structure(self, mock_factory, litellm_config, mock_llm_adapter):
        """Test get_metadata returns correct structure."""
        mock_factory.return_value = mock_llm_adapter

        operator = EmbeddingsOperator(litellm_config)
        metadata = operator.get_metadata()

        assert isinstance(metadata, dict)
        assert OperatorConstants.Misc.CATEGORY in metadata
        assert OperatorConstants.Config.FEATURES in metadata
        assert OperatorConstants.Config.ATTRIBUTES in metadata
        assert OperatorConstants.Misc.IS_OPERATOR_AVAILABLE in metadata
        assert metadata[OperatorConstants.Misc.IS_OPERATOR_AVAILABLE] is True

    @patch("datasift.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_get_metadata_features(self, mock_factory, litellm_config, mock_llm_adapter):
        """Test metadata includes correct features."""
        mock_factory.return_value = mock_llm_adapter

        operator = EmbeddingsOperator(litellm_config)
        metadata = operator.get_metadata()

        features = metadata[OperatorConstants.Config.FEATURES]

        assert OperatorConstants.Columns.EMBEDDINGS_COLUMN_DEFAULT in features
        assert OperatorConstants.Columns.DOC_ID_HASH_DEFAULT in features

        # Check embeddings feature details
        embeddings_feature = features[OperatorConstants.Columns.EMBEDDINGS_COLUMN_DEFAULT]
        assert embeddings_feature[OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB] is True
        assert embeddings_feature[OperatorConstants.Config.MANDATORY_FOR_VECTOR_DB] is True
        assert embeddings_feature[OperatorConstants.Misc.TYPE] == OperatorConstants.Types.TYPE_VECTOR

    @patch("datasift.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_metadata_includes_new_parameters(self, mock_factory, litellm_config, mock_llm_adapter):
        """Test metadata includes new parameter names (provider, model_id)."""
        mock_factory.return_value = mock_llm_adapter

        operator = EmbeddingsOperator(litellm_config)
        metadata = operator.get_metadata()

        attributes = metadata[OperatorConstants.Config.ATTRIBUTES]

        # Check new parameter names are present
        assert "provider" in attributes
        assert "model_id" in attributes

    @patch("datasift.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_metadata_label_is_generic(self, mock_factory, litellm_config, mock_llm_adapter):
        """Test that metadata label is generic (not provider-specific)."""
        mock_factory.return_value = mock_llm_adapter

        operator = EmbeddingsOperator(litellm_config)
        metadata = operator.get_metadata()

        assert metadata[OperatorConstants.Misc.LABEL] == "Embeddings"


# Validation Tests
class TestEmbeddingsOperatorValidation:
    """Test operator validation logic."""

    @patch("datasift.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_validate_valid_config(self, mock_factory, litellm_config, mock_llm_adapter):
        """Test validation with valid configuration."""
        mock_factory.return_value = mock_llm_adapter

        operator = EmbeddingsOperator(litellm_config)
        errors = []
        warnings = []
        available_features = ["content"]

        operator.validate(errors, warnings, available_features)

        assert len(errors) == 0

    @patch("datasift.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_validate_missing_content_feature(self, mock_factory, litellm_config, mock_llm_adapter):
        """Test validation with missing content feature."""
        mock_factory.return_value = mock_llm_adapter

        operator = EmbeddingsOperator(litellm_config)
        errors = []
        warnings = []
        available_features = []  # No content feature

        operator.validate(errors, warnings, available_features)

        assert len(errors) > 0
        # Handle ValidationMessage objects by converting to string
        error_msg = str(errors[0])
        assert "content" in error_msg.lower()

    @patch("datasift.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_validate_supported_providers(self, mock_factory, mock_llm_adapter):
        """Test validation accepts only litellm and watsonx providers."""
        mock_factory.return_value = mock_llm_adapter

        for provider in ["litellm", "watsonx"]:
            config = {
                "provider": provider,
                "model_id": "test-model",
            }
            operator = EmbeddingsOperator(config)
            errors = []
            warnings = []

            operator.validate(errors, warnings, ["content"])

            # Should not have provider-related errors
            assert not any("provider" in err.lower() for err in errors)


# Transform Method Tests
class TestEmbeddingsOperatorTransform:
    """Test the transform method with unified adapters."""

    @patch("datasift.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_transform_single_document(self, mock_factory, litellm_config, mock_llm_adapter, sample_table_single_doc):
        """Test transform with a single document."""
        mock_llm_adapter.generate_embeddings_batch.return_value = [[0.1] * 384]
        mock_factory.return_value = mock_llm_adapter

        operator = EmbeddingsOperator(litellm_config)
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

        # Verify adapter was called with keyword arguments
        mock_llm_adapter.generate_embeddings_batch.assert_called()
        call_args = mock_llm_adapter.generate_embeddings_batch.call_args
        assert "texts" in call_args.kwargs

    @patch("datasift.core.operators.functional.doc_id_hash.DocIdHashOperator.transform")
    @patch("datasift.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_transform_multiple_documents(
        self, mock_factory, mock_doc_hash_transform, litellm_config, mock_llm_adapter, sample_table_multiple_docs
    ):
        """Test transform with multiple documents."""

        # Mock the embedding adapter to return embeddings for each text
        def mock_batch_embeddings(texts):
            return [[0.1] * 384] * len(texts)

        mock_llm_adapter.generate_embeddings_batch.side_effect = mock_batch_embeddings
        mock_factory.return_value = mock_llm_adapter

        # Mock DocIdHashOperator to add doc_id_hash column
        table_with_hash = sample_table_multiple_docs.append_column("doc_id_hash", pa.array(["hash1", "hash2", "hash3"]))
        mock_doc_hash_transform.return_value = ([table_with_hash], {})

        operator = EmbeddingsOperator(litellm_config)
        result_tables, metadata = operator.transform(sample_table_multiple_docs)

        result_table = result_tables[0]

        # Check all documents were processed
        assert result_table.num_rows == 3
        assert "embeddings" in result_table.column_names

        # Check metadata
        assert metadata[Metrics.External.TOTAL_DOCS] == 3
        assert metadata[Metrics.External.PROCESSED_DOCS] == 3
        assert metadata[Metrics.External.FAILED_DOCS_COUNT] == 0

    @patch("datasift.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_transform_with_watsonx_provider(
        self, mock_factory, watsonx_config, mock_llm_adapter, sample_table_single_doc
    ):
        """Test transform with Watsonx provider."""
        mock_llm_adapter.generate_embeddings_batch.return_value = [[0.1] * 768]
        mock_llm_adapter.get_embedding_dimension.return_value = 768
        mock_factory.return_value = mock_llm_adapter

        operator = EmbeddingsOperator(watsonx_config)
        result_tables, metadata = operator.transform(sample_table_single_doc)

        result_table = result_tables[0]

        # Check embeddings were generated
        assert result_table.num_rows == 1
        assert "embeddings" in result_table.column_names
        assert metadata[Metrics.External.PROCESSED_DOCS] == 1

    @patch("datasift.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_transform_empty_table(self, mock_factory, litellm_config, mock_llm_adapter, sample_table_empty):
        """Test transform with an empty table."""
        mock_factory.return_value = mock_llm_adapter

        operator = EmbeddingsOperator(litellm_config)
        result_tables, metadata = operator.transform(sample_table_empty)

        result_table = result_tables[0]

        # Should handle empty table gracefully
        assert result_table.num_rows == 0
        assert metadata[Metrics.External.TOTAL_DOCS] == 0
        assert metadata[Metrics.External.PROCESSED_DOCS] == 0

    @patch("datasift.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_transform_missing_content_column(self, mock_factory, litellm_config, mock_llm_adapter):
        """Test transform with missing content column."""
        mock_factory.return_value = mock_llm_adapter

        # Create table without content column
        data = {
            "id": ["doc1"],
            "name": ["Document 1"],
        }
        table = pa.table(data)

        operator = EmbeddingsOperator(litellm_config)
        result_tables, metadata = operator.transform(table)

        result_table = result_tables[0]

        # Document should fail and be removed
        assert result_table.num_rows == 0
        assert metadata[Metrics.External.FAILED_DOCS_COUNT] == 1
        assert metadata[Metrics.External.NODE_STATUS] == ExecutionStatus.COMPLETED_WITH_ERRORS.value

    @patch("datasift.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_transform_preserves_existing_columns(self, mock_factory, litellm_config, mock_llm_adapter):
        """Test that transform preserves existing columns."""
        mock_llm_adapter.generate_embeddings_batch.return_value = [[0.1] * 384]
        mock_factory.return_value = mock_llm_adapter

        # Create table with extra columns
        data = {
            "id": ["doc1"],
            "name": ["Document 1"],
            "content": ["Test content"],
            "extra_column": ["extra_value"],
        }
        table = pa.table(data)

        operator = EmbeddingsOperator(litellm_config)
        result_tables, _metadata = operator.transform(table)

        result_table = result_tables[0]

        # Check all original columns are preserved
        assert "id" in result_table.column_names
        assert "name" in result_table.column_names
        assert "content" in result_table.column_names
        assert "extra_column" in result_table.column_names
        assert "embeddings" in result_table.column_names


# Document Hash Tests
class TestEmbeddingsDocumentHash:
    """Test document hash generation and preservation."""

    @patch("datasift.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_automatic_hash_generation(self, mock_factory, litellm_config, mock_llm_adapter, sample_table_single_doc):
        """Test automatic hash generation when missing."""
        mock_llm_adapter.generate_embeddings_batch.return_value = [[0.1] * 384]
        mock_factory.return_value = mock_llm_adapter

        operator = EmbeddingsOperator(litellm_config)
        result_tables, _metadata = operator.transform(sample_table_single_doc)

        result_table = result_tables[0]

        # Check hash column was added
        assert "doc_id_hash" in result_table.column_names
        doc_hash = result_table["doc_id_hash"][0].as_py()
        assert doc_hash is not None
        assert len(doc_hash) == 64  # SHA-256 hash length

    @patch("datasift.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_hash_preservation_when_present(self, mock_factory, litellm_config, mock_llm_adapter):
        """Test hash preservation when already present."""
        mock_llm_adapter.generate_embeddings_batch.return_value = [[0.1] * 384]
        mock_factory.return_value = mock_llm_adapter

        # Create table with existing hash
        existing_hash = "existing_hash_value_123"
        data = {
            "id": ["doc1"],
            "name": ["Document 1"],
            "content": ["Test content"],
            "doc_id_hash": [existing_hash],
        }
        table = pa.table(data)

        operator = EmbeddingsOperator(litellm_config)
        result_tables, _metadata = operator.transform(table)

        result_table = result_tables[0]

        # Hash should be preserved
        doc_hash = result_table["doc_id_hash"][0].as_py()
        assert doc_hash == existing_hash

    @patch("datasift.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_generate_document_hash_consistency(self, mock_factory, litellm_config, mock_llm_adapter):
        """Test that hash generation is consistent for same content."""
        mock_factory.return_value = mock_llm_adapter

        operator = EmbeddingsOperator(litellm_config)

        content = "Test document content"
        hash1 = operator._generate_document_hash(content)
        hash2 = operator._generate_document_hash(content)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hash length

    @patch("datasift.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_generate_document_hash_different_content(self, mock_factory, litellm_config, mock_llm_adapter):
        """Test that different content produces different hashes."""
        mock_factory.return_value = mock_llm_adapter

        operator = EmbeddingsOperator(litellm_config)

        hash1 = operator._generate_document_hash("Content 1")
        hash2 = operator._generate_document_hash("Content 2")

        assert hash1 != hash2


# Error Handling Tests
class TestEmbeddingsErrorHandling:
    """Test error handling with unified adapters."""

    @patch("datasift.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_adapter_error_handling(self, mock_factory, litellm_config, mock_llm_adapter, sample_table_single_doc):
        """Test handling of adapter errors."""
        mock_llm_adapter.generate_embeddings_batch.side_effect = Exception("API error")
        mock_factory.return_value = mock_llm_adapter

        operator = EmbeddingsOperator(litellm_config)
        result_tables, metadata = operator.transform(sample_table_single_doc)

        result_table = result_tables[0]

        # Document should fail and be removed
        assert result_table.num_rows == 0
        assert metadata[Metrics.External.FAILED_DOCS_COUNT] == 1
        assert metadata[Metrics.External.NODE_STATUS] == ExecutionStatus.COMPLETED_WITH_ERRORS.value

    @patch("datasift.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_per_document_error_tracking(
        self, mock_factory, litellm_config, mock_llm_adapter, sample_table_multiple_docs
    ):
        """Test per-document error tracking."""
        # Make second document fail
        call_count = [0]

        def mock_batch_embeddings(texts):
            call_count[0] += 1
            if call_count[0] == 2:
                raise Exception("Processing error")
            return [[0.1] * 384] * len(texts)

        mock_llm_adapter.generate_embeddings_batch.side_effect = mock_batch_embeddings
        mock_factory.return_value = mock_llm_adapter

        operator = EmbeddingsOperator(litellm_config)
        result_tables, metadata = operator.transform(sample_table_multiple_docs)

        result_table = result_tables[0]

        # Two documents should succeed, one should fail
        assert result_table.num_rows == 2
        assert metadata[Metrics.External.PROCESSED_DOCS] == 2
        assert metadata[Metrics.External.FAILED_DOCS_COUNT] == 1
        assert len(metadata[Metrics.External.FAILED_DOCS]) == 1

    @patch("datasift.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_graceful_failure_continues_processing(
        self, mock_factory, litellm_config, mock_llm_adapter, sample_table_multiple_docs
    ):
        """Test that processing continues after individual document failures."""
        # Make first document fail, others succeed
        call_count = [0]

        def mock_batch_embeddings(texts):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("First document error")
            return [[0.1] * 384] * len(texts)

        mock_llm_adapter.generate_embeddings_batch.side_effect = mock_batch_embeddings
        mock_factory.return_value = mock_llm_adapter

        operator = EmbeddingsOperator(litellm_config)
        result_tables, metadata = operator.transform(sample_table_multiple_docs)

        result_table = result_tables[0]

        # Should process remaining documents
        assert result_table.num_rows == 2
        assert metadata[Metrics.External.PROCESSED_DOCS] == 2
        assert metadata[Metrics.External.FAILED_DOCS_COUNT] == 1


# Metadata Validation Tests
class TestEmbeddingsMetadataValidation:
    """Test metadata structure and content validation."""

    @patch("datasift.core.operators.functional.doc_id_hash.DocIdHashOperator.transform")
    @patch("datasift.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_metadata_includes_processed_docs_count(
        self, mock_factory, mock_doc_hash_transform, litellm_config, mock_llm_adapter, sample_table_multiple_docs
    ):
        """Test metadata includes processed_docs count."""

        # Mock the embedding adapter to return embeddings for each text
        def mock_batch_embeddings(texts):
            return [[0.1] * 384] * len(texts)

        mock_llm_adapter.generate_embeddings_batch.side_effect = mock_batch_embeddings
        mock_factory.return_value = mock_llm_adapter

        # Mock DocIdHashOperator
        table_with_hash = sample_table_multiple_docs.append_column("doc_id_hash", pa.array(["hash1", "hash2", "hash3"]))
        mock_doc_hash_transform.return_value = ([table_with_hash], {})

        operator = EmbeddingsOperator(litellm_config)
        _result_tables, metadata = operator.transform(sample_table_multiple_docs)

        assert Metrics.External.PROCESSED_DOCS in metadata
        assert metadata[Metrics.External.PROCESSED_DOCS] == 3

    @patch("datasift.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_metadata_includes_failed_docs_count(
        self, mock_factory, litellm_config, mock_llm_adapter, sample_table_multiple_docs
    ):
        """Test metadata includes failed_docs count."""
        # Make one document fail
        call_count = [0]

        def mock_batch_embeddings(texts):
            call_count[0] += 1
            if call_count[0] == 2:
                raise Exception("Error")
            return [[0.1] * 384] * len(texts)

        mock_llm_adapter.generate_embeddings_batch.side_effect = mock_batch_embeddings
        mock_factory.return_value = mock_llm_adapter

        operator = EmbeddingsOperator(litellm_config)
        _result_tables, metadata = operator.transform(sample_table_multiple_docs)

        assert Metrics.External.FAILED_DOCS_COUNT in metadata
        assert metadata[Metrics.External.FAILED_DOCS_COUNT] == 1

    @patch("datasift.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_metadata_includes_node_status(
        self, mock_factory, litellm_config, mock_llm_adapter, sample_table_single_doc
    ):
        """Test metadata includes node_status."""
        mock_llm_adapter.generate_embeddings_batch.return_value = [[0.1] * 384]
        mock_factory.return_value = mock_llm_adapter

        operator = EmbeddingsOperator(litellm_config)
        _result_tables, metadata = operator.transform(sample_table_single_doc)

        assert Metrics.External.NODE_STATUS in metadata
        # Should be Completed when all succeed
        assert metadata[Metrics.External.NODE_STATUS] == ExecutionStatus.COMPLETED.value

    @patch("datasift.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_metadata_node_status_with_errors(
        self, mock_factory, litellm_config, mock_llm_adapter, sample_table_single_doc
    ):
        """Test node_status is COMPLETED_WITH_ERRORS when failures occur."""
        mock_llm_adapter.generate_embeddings_batch.side_effect = Exception("Error")
        mock_factory.return_value = mock_llm_adapter

        operator = EmbeddingsOperator(litellm_config)
        _result_tables, metadata = operator.transform(sample_table_single_doc)

        assert metadata[Metrics.External.NODE_STATUS] == ExecutionStatus.COMPLETED_WITH_ERRORS.value

    @patch("datasift.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_metadata_completeness(self, mock_factory, litellm_config, mock_llm_adapter, sample_table_single_doc):
        """Test that all required metadata fields are present."""
        mock_llm_adapter.generate_embeddings_batch.return_value = [[0.1] * 384]
        mock_factory.return_value = mock_llm_adapter

        operator = EmbeddingsOperator(litellm_config)
        _result_tables, metadata = operator.transform(sample_table_single_doc)

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


# Integration Tests
class TestEmbeddingsOperatorIntegration:
    """Integration-style tests combining multiple features."""

    @patch("datasift.core.operators.functional.doc_id_hash.DocIdHashOperator.transform")
    @patch("datasift.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_full_pipeline_with_hash_and_embeddings(
        self, mock_factory, mock_doc_hash_transform, litellm_config, mock_llm_adapter, sample_table_multiple_docs
    ):
        """Test full pipeline: generate embeddings and hashes."""

        # Mock the embedding adapter to return embeddings for each text
        def mock_batch_embeddings(texts):
            return [[0.1] * 384] * len(texts)

        mock_llm_adapter.generate_embeddings_batch.side_effect = mock_batch_embeddings
        mock_factory.return_value = mock_llm_adapter

        # Mock DocIdHashOperator
        table_with_hash = sample_table_multiple_docs.append_column("doc_id_hash", pa.array(["hash1", "hash2", "hash3"]))
        mock_doc_hash_transform.return_value = ([table_with_hash], {})

        operator = EmbeddingsOperator(litellm_config)
        result_tables, _metadata = operator.transform(sample_table_multiple_docs)

        result_table = result_tables[0]

        # Check both embeddings and hashes were added
        assert "embeddings" in result_table.column_names
        assert "doc_id_hash" in result_table.column_names

        # Verify all rows have both
        for i in range(result_table.num_rows):
            assert result_table["embeddings"][i].as_py() is not None
            assert result_table["doc_id_hash"][i].as_py() is not None

    @patch("datasift.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_mixed_success_and_failure_documents(self, mock_factory, litellm_config, mock_llm_adapter):
        """Test processing with mix of successful and failed documents."""
        # Make every other document fail
        call_count = [0]

        def mock_batch_embeddings(texts):
            call_count[0] += 1
            if call_count[0] % 2 == 0:
                raise Exception("Error")
            return [[0.1] * 384] * len(texts)

        mock_llm_adapter.generate_embeddings_batch.side_effect = mock_batch_embeddings
        mock_factory.return_value = mock_llm_adapter

        # Create table with 4 documents
        data = {
            "id": [f"doc{i}" for i in range(4)],
            "name": [f"Document {i}" for i in range(4)],
            "content": [f"Content {i}" for i in range(4)],
        }
        table = pa.table(data)

        operator = EmbeddingsOperator(litellm_config)
        result_tables, metadata = operator.transform(table)

        result_table = result_tables[0]

        # Should have 2 successful, 2 failed
        assert result_table.num_rows == 2
        assert metadata[Metrics.External.PROCESSED_DOCS] == 2
        assert metadata[Metrics.External.FAILED_DOCS_COUNT] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
