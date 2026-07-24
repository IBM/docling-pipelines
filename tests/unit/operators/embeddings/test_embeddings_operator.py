#!/usr/bin/env python3
"""
Comprehensive unit tests for EmbeddingsOperator using unified LLM adapters.

Shared fixtures (litellm_config, watsonx_config, sample_table_*, mock_llm_adapter)
are defined in conftest.py and injected automatically by pytest.
"""

import json
from unittest.mock import patch

import pyarrow as pa
import pytest

from docpipe.core.constants.constants import ExecutionStatus, Metrics
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.functional.embeddings import EmbeddingsOperator


# Initialization Tests
class TestEmbeddingsOperatorInitialization:
    """Test operator initialization with unified adapters."""

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_init_with_litellm_provider(self, mock_factory, litellm_config, mock_llm_adapter):
        """Test initialization with LiteLLM provider."""
        mock_factory.return_value = mock_llm_adapter

        operator = EmbeddingsOperator(litellm_config)

        assert operator.provider == "litellm"
        assert operator.model_id == "openai/text-embedding-3-small"
        assert operator.embeddings_column == "embeddings"
        mock_factory.assert_called_once_with(
            provider="litellm",
            model_id="openai/text-embedding-3-small",
            provider_config={"model_id": "openai/text-embedding-3-small", "api_key": "<test-api-key>"},
        )

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
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
                "model_id": "ibm/slate-125m-english-rtrvr",
                "api_key": "<test-api-key>",
                "api_base": "https://us-south.ml.cloud.ibm.com",
                "container_id": "test-project-id",
                "container_kind": "project",
            },
        )

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_init_with_default_values(self, mock_factory, mock_llm_adapter):
        """Test initialization with default values."""
        mock_factory.return_value = mock_llm_adapter

        config = {"provider_config": {"model_id": "text-embedding-3-small"}}
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

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_get_required_features(self, mock_factory, litellm_config, mock_llm_adapter):
        """Test get_required_features returns correct list."""
        mock_factory.return_value = mock_llm_adapter

        operator = EmbeddingsOperator(litellm_config)
        required = operator.get_required_features()

        assert len(required) == 0

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_adapter_validation_called_on_init(self, mock_factory, litellm_config, mock_llm_adapter):
        """Test that validate() is called during operator initialization."""
        mock_llm_adapter.validate.return_value = {"valid": True, "errors": [], "warnings": []}
        mock_factory.return_value = mock_llm_adapter

        _ = EmbeddingsOperator(litellm_config)

        # Verify adapter was created and validated
        mock_factory.assert_called_once()
        mock_llm_adapter.validate.assert_called_once()

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_adapter_validation_failure_raises_error(self, mock_factory, litellm_config, mock_llm_adapter):
        """Test that validation failures raise DocpipeException."""
        from docpipe.exceptions.docpipe_exceptions import DocpipeException

        mock_llm_adapter.validate.return_value = {"valid": False, "errors": ["API key is required"], "warnings": []}
        mock_factory.return_value = mock_llm_adapter

        with pytest.raises(DocpipeException, match="API key is required"):
            EmbeddingsOperator(litellm_config)

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
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

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
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

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_get_metadata_features(self, mock_factory, litellm_config, mock_llm_adapter):
        """Test metadata includes correct features."""
        mock_factory.return_value = mock_llm_adapter

        operator = EmbeddingsOperator(litellm_config)
        metadata = operator.get_metadata()

        features = metadata[OperatorConstants.Config.FEATURES]

        assert OperatorConstants.Columns.EMBEDDINGS_COLUMN_DEFAULT in features

        # Check embeddings feature details
        embeddings_feature = features[OperatorConstants.Columns.EMBEDDINGS_COLUMN_DEFAULT]
        assert embeddings_feature[OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB] is True
        assert embeddings_feature[OperatorConstants.Config.MANDATORY_FOR_VECTOR_DB] is True
        assert embeddings_feature[OperatorConstants.Misc.TYPE] == OperatorConstants.Types.TYPE_VECTOR

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_metadata_includes_new_parameters(self, mock_factory, litellm_config, mock_llm_adapter):
        """Test metadata includes new parameter names (provider, model_id in provider_config)."""
        mock_factory.return_value = mock_llm_adapter

        operator = EmbeddingsOperator(litellm_config)
        metadata = operator.get_metadata()

        attributes = metadata[OperatorConstants.Config.ATTRIBUTES]

        # Check new parameter names are present
        assert "provider" in attributes
        # model_id is now nested in provider_config.properties
        assert "provider_config" in attributes
        assert "properties" in attributes["provider_config"]
        assert "model_id" in attributes["provider_config"]["properties"]

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_metadata_label_is_generic(self, mock_factory, litellm_config, mock_llm_adapter):
        """Test that metadata label is generic (not provider-specific)."""
        mock_factory.return_value = mock_llm_adapter

        operator = EmbeddingsOperator(litellm_config)
        metadata = operator.get_metadata()

        assert metadata[OperatorConstants.Misc.LABEL] == "Embeddings"


# Validation Tests
class TestEmbeddingsOperatorValidation:
    """Test operator validation logic."""

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_validate_valid_config(self, mock_factory, litellm_config, mock_llm_adapter):
        """Test validation with valid configuration."""
        mock_factory.return_value = mock_llm_adapter

        operator = EmbeddingsOperator(litellm_config)
        errors = []
        warnings = []
        available_features = ["content"]

        operator.validate(errors, warnings, available_features)

        assert len(errors) == 0

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_validate_missing_both_content_and_chunked_content(self, mock_factory, litellm_config, mock_llm_adapter):
        """Test validation with missing both content and chunked_content features."""
        mock_factory.return_value = mock_llm_adapter

        operator = EmbeddingsOperator(litellm_config)
        errors = []
        warnings = []
        available_features = []  # No content or chunked_content

        operator.validate(errors, warnings, available_features)

        assert len(errors) > 0
        error_msg = str(errors[0])
        assert "content" in error_msg.lower() or "chunked_content" in error_msg.lower()

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_validate_with_chunked_content_only(self, mock_factory, litellm_config, mock_llm_adapter):
        """Test validation passes with only chunked_content feature (no content)."""
        mock_factory.return_value = mock_llm_adapter

        operator = EmbeddingsOperator(litellm_config)
        errors = []
        warnings = []
        available_features = ["chunked_content"]  # Only chunked_content

        operator.validate(errors, warnings, available_features)

        # Should not have errors since chunked_content is available
        assert len(errors) == 0

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_validate_with_content_only(self, mock_factory, litellm_config, mock_llm_adapter):
        """Test validation passes with only content feature."""
        mock_factory.return_value = mock_llm_adapter

        operator = EmbeddingsOperator(litellm_config)
        errors = []
        warnings = []
        available_features = ["content"]  # Only content

        operator.validate(errors, warnings, available_features)

        # Should not have errors since content is available
        assert len(errors) == 0

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_validate_supported_providers(self, mock_factory, mock_llm_adapter):
        """Test validation accepts only litellm and watsonx providers."""
        mock_factory.return_value = mock_llm_adapter

        for provider in ["litellm", "watsonx"]:
            config = {
                "provider": provider,
                "provider_config": {
                    "model_id": "test-model",
                },
            }
            operator = EmbeddingsOperator(config)
            errors = []
            warnings = []

            operator.validate(errors, warnings, ["content"])

            # Should not have provider-related errors
            assert not any("provider" in err.lower() for err in errors)

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_validate_missing_chunker_warning(self, mock_factory, litellm_config, mock_llm_adapter):
        """Test validation warns when chunked_content feature is missing (no Chunker before Embeddings)."""
        mock_factory.return_value = mock_llm_adapter

        operator = EmbeddingsOperator(litellm_config)
        errors = []
        warnings = []
        available_features = ["content", "id", "name"]  # No chunked_content feature

        operator.validate(errors, warnings, available_features)

        # Should have no errors
        assert len(errors) == 0
        # Should have warning about missing Chunker
        assert len(warnings) > 0
        warning_msg = str(warnings[0])
        assert "chunker" in warning_msg.lower()

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_validate_with_chunker_no_warning(self, mock_factory, litellm_config, mock_llm_adapter):
        """Test validation passes without warning when chunked_content feature is present (Chunker before Embeddings)."""
        mock_factory.return_value = mock_llm_adapter

        operator = EmbeddingsOperator(litellm_config)
        errors = []
        warnings = []
        available_features = ["content", "id", "name", "chunked_content"]  # Has chunked_content

        operator.validate(errors, warnings, available_features)

        # Should have no errors
        assert len(errors) == 0
        # Should have no warnings about Chunker
        chunker_warnings = [w for w in warnings if "chunker" in str(w).lower()]
        assert len(chunker_warnings) == 0


# Transform Method Tests
class TestEmbeddingsOperatorTransform:
    """Test the transform method with unified adapters."""

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
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

    @patch("docpipe.core.operators.functional.doc_id_hash.DocIdHashOperator.transform")
    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
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

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
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

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
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

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
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

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
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

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
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

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
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

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_generate_document_hash_consistency(self, mock_factory, litellm_config, mock_llm_adapter):
        """Test that hash generation is consistent for same content."""
        mock_factory.return_value = mock_llm_adapter

        operator = EmbeddingsOperator(litellm_config)

        content = "Test document content"
        hash1 = operator._generate_document_hash(content)
        hash2 = operator._generate_document_hash(content)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hash length

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
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

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
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

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
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

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
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

    @patch("docpipe.core.operators.functional.doc_id_hash.DocIdHashOperator.transform")
    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
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

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
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

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
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

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_metadata_node_status_with_errors(
        self, mock_factory, litellm_config, mock_llm_adapter, sample_table_single_doc
    ):
        """Test node_status is COMPLETED_WITH_ERRORS when failures occur."""
        mock_llm_adapter.generate_embeddings_batch.side_effect = Exception("Error")
        mock_factory.return_value = mock_llm_adapter

        operator = EmbeddingsOperator(litellm_config)
        _result_tables, metadata = operator.transform(sample_table_single_doc)

        assert metadata[Metrics.External.NODE_STATUS] == ExecutionStatus.COMPLETED_WITH_ERRORS.value

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
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


class TestEmbeddingsOperatorInternalMethods:
    """Test internal helpers and edge-case branches."""

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_validate_rejects_invalid_field_types_and_values(self, mock_factory, mock_llm_adapter):
        mock_factory.return_value = mock_llm_adapter

        operator = EmbeddingsOperator(
            {
                "provider": "litellm",
                "provider_config": {"model_id": "openai/test-model"},
            }
        )
        operator.provider = 123
        operator.overlap_ratio = "bad"
        operator.token_limit = "bad"
        operator.provider_config = "bad"

        errors = []
        warnings = []
        operator.validate(errors, warnings, ["content"])

        assert any("provider must be a string" in err for err in errors)
        assert any("overlap_ratio must be a number" in err for err in errors)
        assert any("token_limit must be an integer" in err for err in errors)
        assert any("provider_config must be a dictionary" in err for err in errors)

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.get_supported_providers")
    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_validate_rejects_invalid_provider_and_provider_config_fields(
        self, mock_factory, mock_supported_providers, mock_llm_adapter
    ):
        mock_factory.return_value = mock_llm_adapter
        mock_supported_providers.return_value = ["litellm", "watsonx"]

        operator = EmbeddingsOperator(
            {
                "provider": "litellm",
                "provider_config": {"model_id": "openai/test-model"},
            }
        )
        operator.provider = "unsupported"
        operator.overlap_ratio = 0.7
        operator.token_limit = 0
        operator.provider_config = {
            "model_id": "",
            "max_concurrent_requests": "two",
            "batch_size": 0,
        }

        errors = []
        warnings = []
        operator.validate(errors, warnings, ["content", "chunked_content"])

        assert any("provider must be one of" in err for err in errors)
        assert any("overlap_ratio must be between" in err for err in errors)
        assert any("token_limit must be positive" in err for err in errors)
        assert any("provider_config.model_id is required" in err for err in errors)
        assert any("provider_config.max_concurrent_requests must be an integer" in err for err in errors)
        assert any("provider_config.batch_size must be positive" in err for err in errors)

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_validate_rejects_non_positive_max_concurrent_requests(self, mock_factory, mock_llm_adapter):
        mock_factory.return_value = mock_llm_adapter

        operator = EmbeddingsOperator(
            {
                "provider_config": {
                    "model_id": "openai/test-model",
                    "max_concurrent_requests": 0,
                    "batch_size": "large",
                },
            }
        )

        errors = []
        warnings = []
        operator.validate(errors, warnings, ["content", "chunked_content"])

        assert any("provider_config.max_concurrent_requests must be positive" in err for err in errors)
        assert any("provider_config.batch_size must be an integer" in err for err in errors)

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_build_chunk_text_for_embedding_handles_empty_and_summary(self, mock_factory, mock_llm_adapter):
        mock_factory.return_value = mock_llm_adapter
        operator = EmbeddingsOperator({"provider_config": {"model_id": "openai/test-model"}})

        assert operator._build_chunk_text_for_embedding({"chunk": ""}) == ""
        assert (
            operator._build_chunk_text_for_embedding({"chunk": "body", "summary": "brief"})
            == "abstract: brief\ncontent: body"
        )

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_handle_embedding_error_context_length_message(self, mock_factory, mock_llm_adapter):
        mock_factory.return_value = mock_llm_adapter
        operator = EmbeddingsOperator({"provider_config": {"model_id": "openai/test-model"}})

        with pytest.raises(Exception) as exc_info:
            operator._handle_embedding_error(Exception("Input length exceeds the context length"), "openai/test-model")

        assert "context length" in str(exc_info.value).lower()
        assert "Chunking operator" in str(exc_info.value)

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_create_embeddings_chunks_long_text_and_returns_zero_vector_for_empty(self, mock_factory, mock_llm_adapter):
        mock_factory.return_value = mock_llm_adapter
        mock_llm_adapter.generate_embeddings_batch.side_effect = [
            [[1.0, 1.0]],
            [[2.0, 4.0], [4.0, 6.0]],
        ]

        operator = EmbeddingsOperator(
            {
                "provider_config": {"model_id": "openai/test-model"},
                "token_limit": 2,
                "overlap_ratio": 0.0,
            }
        )

        result = operator._create_embeddings(
            ["small", "", "abcdefghijklmno"], operator.model_id, operator.overlap_ratio
        )

        assert result[0] == [1.0, 1.0]
        assert result[1] == [0.0] * 384
        assert result[2] == [3.0, 5.0]
        assert mock_llm_adapter.generate_embeddings_batch.call_args_list[0].kwargs["texts"] == ["small"]
        assert mock_llm_adapter.generate_embeddings_batch.call_args_list[1].kwargs["texts"] == ["abcdefgh", "ijklmno"]

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_parse_chunked_content_handles_memmap_json_list_and_invalid_types(self, mock_factory, mock_llm_adapter):
        mock_factory.return_value = mock_llm_adapter
        operator = EmbeddingsOperator({"provider_config": {"model_id": "openai/test-model"}})

        memmap_table = pa.table(
            {
                "chunked_content": [{"chunks_memmap_file": "/tmp/chunks.bin"}],
            }
        )
        with patch(
            "docpipe.utils.core.memmap_file_utils.load_chunks_from_file",
            return_value=[{"chunk": "alpha", "summary": "sum"}, "beta", 42],
        ) as mock_load:
            texts = operator._parse_chunked_content(memmap_table, 0, "doc-1")
        mock_load.assert_called_once_with(filepath="/tmp/chunks.bin")
        assert texts == ["abstract: sum\ncontent: alpha", "beta"]

        json_table = pa.table({"chunked_content": [json.dumps([{"chunk": "gamma"}, "delta"])]})
        assert operator._parse_chunked_content(json_table, 0, "doc-2") == ["gamma", "delta"]

        with pytest.raises(Exception, match="Chunked content is empty"):
            operator._parse_chunked_content(pa.table({"chunked_content": [None]}), 0, "doc-empty")

        with pytest.raises(Exception, match="Invalid chunked_content JSON format"):
            operator._parse_chunked_content(pa.table({"chunked_content": ["not-json"]}), 0, "doc-bad-json")

        with pytest.raises(Exception, match="Unexpected chunked_content type"):
            operator._parse_chunked_content(pa.table({"chunked_content": [123]}), 0, "doc-bad-type")

        with pytest.raises(Exception, match="No valid text chunks found after parsing"):
            operator._parse_chunked_content(pa.table({"chunked_content": [[{"chunk": ""}, None]]}), 0, "doc-no-text")

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_get_full_document_content_and_update_doc_hash_column_edge_cases(self, mock_factory, mock_llm_adapter):
        mock_factory.return_value = mock_llm_adapter
        operator = EmbeddingsOperator({"provider_config": {"model_id": "openai/test-model"}})

        with pytest.raises(Exception, match="is empty or missing"):
            operator._get_full_document_content(pa.table({"content": [""]}), 0)

        table = pa.table({"id": ["1"], "doc_id_hash": ["old"]})
        unchanged = operator._update_doc_hash_column(table, [])
        assert unchanged.equals(table)

        updated = operator._update_doc_hash_column(table, ["new"])
        assert updated["doc_id_hash"][0].as_py() == "new"
        assert updated.num_columns == table.num_columns

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_process_single_document_returns_single_embedding_or_chunk_list(self, mock_factory, mock_llm_adapter):
        mock_factory.return_value = mock_llm_adapter
        operator = EmbeddingsOperator({"provider_config": {"model_id": "openai/test-model"}})

        full_doc_table = pa.table({"name": ["Doc A"], "content": ["body"]})
        with (
            patch.object(operator, "_get_full_document_content", return_value=["body"]) as mock_content,
            patch.object(operator, "_create_embeddings", return_value=[[0.1, 0.2]]) as mock_create,
        ):
            embeddings, doc_hash = operator._process_single_document(full_doc_table, 0, False, ["hash-a"])
        mock_content.assert_called_once()
        mock_create.assert_called_once()
        assert embeddings == [0.1, 0.2]
        assert doc_hash == "hash-a"

        chunked_table = pa.table({"name": ["Doc B"], "chunked_content": [[{"chunk": "first"}]]})
        with (
            patch.object(operator, "_parse_chunked_content", return_value=["chunk-1", "chunk-2"]) as mock_parse,
            patch.object(operator, "_create_embeddings", return_value=[[1.0, 1.0], [2.0, 2.0]]) as mock_create,
        ):
            embeddings, doc_hash = operator._process_single_document(chunked_table, 0, True, ["hash-b"])
        mock_parse.assert_called_once()
        mock_create.assert_called_once()
        assert embeddings == [[1.0, 1.0], [2.0, 2.0]]
        assert doc_hash == "hash-b"

    @patch("docpipe.core.operators.functional.doc_id_hash.DocIdHashOperator.transform")
    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_transform_handles_doc_hash_generation_failure(
        self, mock_factory, mock_doc_hash_transform, mock_llm_adapter
    ):
        mock_factory.return_value = mock_llm_adapter
        mock_doc_hash_transform.side_effect = RuntimeError("hash generation failed")
        table = pa.table({"id": ["doc1"], "name": ["Doc 1"], "content": ["body"]})

        operator = EmbeddingsOperator(
            {"provider_config": {"model_id": "openai/test-model"}, "job_id": "job-1", "job_run_id": "run-1"}
        )
        result_tables, metadata = operator.transform(table)

        assert result_tables[0].num_rows == 0
        assert metadata[Metrics.External.FAILED_DOCS_COUNT] == 1
        assert "hash generation failed" in metadata[Metrics.External.FAILED_DOCS][0]["reason"]

    @patch("docpipe.core.operators.functional.embeddings.embeddings_operator.write_content_to_file")
    @patch("docpipe.core.operators.functional.embeddings.embeddings_operator.get_data_path")
    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
    def test_transform_stores_chunk_embeddings_in_memmap_when_chunks_are_file_backed(
        self,
        mock_factory,
        mock_get_data_path,
        mock_write_content_to_file,
        mock_llm_adapter,
    ):
        mock_factory.return_value = mock_llm_adapter
        mock_get_data_path.return_value = "/tmp/embeddings"
        mock_llm_adapter.generate_embeddings_batch.side_effect = [
            [[1.0, 1.0]],
            [[2.0, 2.0]],
        ]

        table = pa.table(
            {
                "id": ["doc/1"],
                "name": ["Doc 1"],
                "content": ["source body"],
                "doc_id_hash": ["hash-1"],
                "chunked_content": [{"chunks_memmap_file": "/tmp/chunks.bin"}],
            }
        )

        operator = EmbeddingsOperator(
            {"provider_config": {"model_id": "openai/test-model"}, "job_id": "job-1", "job_run_id": "run-1"}
        )
        with (
            patch.object(operator, "_process_single_document", return_value=([[1.0, 1.0], [2.0, 2.0]], "hash-1")),
            patch("docpipe.core.operators.operator_utils.sanitize_doc_id_for_filename", return_value="doc_1"),
        ):
            result_tables, metadata = operator.transform(table)

        result_table = result_tables[0]
        stored_value = result_table["embeddings"][0].as_py()
        assert stored_value == {"embeddings_memmap_file": "/tmp/embeddings/doc_1_embeddings.bin"}
        mock_get_data_path.assert_called_once()
        mock_write_content_to_file.assert_called_once_with(
            content_list=[[1.0, 1.0], [2.0, 2.0]], filepath="/tmp/embeddings/doc_1_embeddings.bin"
        )
        assert metadata[Metrics.External.PROCESSED_DOCS] == 1


# Integration Tests
class TestEmbeddingsOperatorIntegration:
    """Integration-style tests combining multiple features."""

    @patch("docpipe.core.operators.functional.doc_id_hash.DocIdHashOperator.transform")
    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
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

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_embedding_adapter")
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
