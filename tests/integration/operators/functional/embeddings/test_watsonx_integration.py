#!/usr/bin/env python3
"""
Integration tests for Watsonx.ai embeddings.

These tests require real watsonx.ai credentials and make actual API calls.
Tests are skipped if credentials are not available.

Required environment variables:
- WATSONX_API_KEY: Watsonx.ai API key
- WATSONX_URL: Watsonx.ai API endpoint URL
- WATSONX_PROJECT_ID: Project ID for project container tests
- WATSONX_SPACE_ID: Space ID for space container tests (optional)
"""

import os
from typing import Any

import pyarrow as pa
import pytest

# Check for required credentials
WATSONX_API_KEY = os.getenv("WATSONX_API_KEY")
WATSONX_URL = os.getenv("WATSONX_URL")
WATSONX_PROJECT_ID = os.getenv("WATSONX_PROJECT_ID")
WATSONX_SPACE_ID = os.getenv("WATSONX_SPACE_ID")

# Skip all tests if credentials not available
pytestmark = pytest.mark.skipif(
    not all([WATSONX_API_KEY, WATSONX_URL, WATSONX_PROJECT_ID]),
    reason="Watsonx.ai credentials not available. Set WATSONX_API_KEY, WATSONX_URL, and WATSONX_PROJECT_ID",
)


@pytest.fixture
def project_config() -> dict[str, Any]:
    """Fixture providing project-based watsonx configuration."""
    return {
        "provider_config": {
            "api_key": WATSONX_API_KEY,
            "url": WATSONX_URL,
            "container_kind": "project",
            "container_id": WATSONX_PROJECT_ID,
            "batch_size": 800,
        }
    }


@pytest.fixture
def space_config() -> dict[str, Any]:
    """Fixture providing space-based watsonx configuration."""
    if not WATSONX_SPACE_ID:
        pytest.skip("WATSONX_SPACE_ID not set")

    return {
        "provider_config": {
            "api_key": WATSONX_API_KEY,
            "url": WATSONX_URL,
            "container_kind": "space",
            "container_id": WATSONX_SPACE_ID,
            "batch_size": 800,
        }
    }


@pytest.fixture
def sample_texts() -> list[str]:
    """Fixture providing sample texts for embedding."""
    return [
        "The quick brown fox jumps over the lazy dog.",
        "Machine learning is a subset of artificial intelligence.",
        "Python is a popular programming language for data science.",
        "Natural language processing enables computers to understand human language.",
        "Vector embeddings represent text as numerical vectors.",
    ]


@pytest.mark.integration
class TestWatsonxAdapterIntegration:
    """Integration tests for WatsonxLLMAdapter with real API."""

    def test_adapter_initialization_with_project(self, *, project_config: dict[str, Any]):
        """Test adapter initialization with project container."""
        from docpipe.core.operators.functional.embeddings.adapters.outbound.watsonx_adapter import (
            WatsonxLLMAdapter,
        )

        adapter = WatsonxLLMAdapter(
            model_name="ibm/slate-125m-english-rtrvr",
            **project_config,
        )

        assert adapter is not None
        assert adapter.model_name == "ibm/slate-125m-english-rtrvr"
        assert adapter.container_kind == "project"

    def test_adapter_initialization_with_space(self, *, space_config: dict[str, Any]):
        """Test adapter initialization with space container."""
        from docpipe.core.operators.functional.embeddings.adapters.outbound.watsonx_adapter import (
            WatsonxLLMAdapter,
        )

        adapter = WatsonxLLMAdapter(
            model_name="ibm/slate-125m-english-rtrvr",
            **space_config,
        )

        assert adapter is not None
        assert adapter.model_name == "ibm/slate-125m-english-rtrvr"
        assert adapter.container_kind == "space"

    def test_generate_single_embedding(self, *, project_config: dict[str, Any]):
        """Test generating embedding for single text."""
        from docpipe.core.operators.functional.embeddings.adapters.outbound.watsonx_adapter import (
            WatsonxLLMAdapter,
        )

        adapter = WatsonxLLMAdapter(
            model_name="ibm/slate-125m-english-rtrvr",
            **project_config,
        )

        text = "This is a test sentence for embedding generation."
        embedding = adapter.generate_embeddings(text=text)

        assert isinstance(embedding, list)
        assert len(embedding) == 768  # slate-125m has 768 dimensions
        assert all(isinstance(x, float) for x in embedding)
        # Check that embeddings are not all zeros
        assert any(x != 0.0 for x in embedding)

    def test_generate_batch_embeddings(self, *, project_config: dict[str, Any], sample_texts: list[str]):
        """Test generating embeddings for batch of texts."""
        from docpipe.core.operators.functional.embeddings.adapters.outbound.watsonx_adapter import (
            WatsonxLLMAdapter,
        )

        adapter = WatsonxLLMAdapter(
            model_name="ibm/slate-125m-english-rtrvr",
            **project_config,
        )

        embeddings = adapter.generate_embeddings_batch(texts=sample_texts, batch_size=32)

        assert isinstance(embeddings, list)
        assert len(embeddings) == len(sample_texts)
        assert all(isinstance(emb, list) for emb in embeddings)
        assert all(len(emb) == 768 for emb in embeddings)
        # Check that embeddings are different for different texts
        assert embeddings[0] != embeddings[1]

    def test_model_validation_api_call(self, *, project_config: dict[str, Any]):
        """Test that model validation makes API call."""
        from docpipe.integrations.watsonx.model_validator import validate_model_id

        is_valid = validate_model_id(
            model_id="ibm/slate-125m-english-rtrvr",
            api_key=WATSONX_API_KEY,
            url=WATSONX_URL,
        )

        assert is_valid is True

    def test_invalid_model_validation(self, *, project_config: dict[str, Any]):
        """Test that invalid model is rejected."""
        from docpipe.core.operators.functional.embeddings.adapters.outbound.watsonx_adapter import (
            WatsonxLLMAdapter,
        )

        with pytest.raises(ValueError, match=r"Model.*not available"):
            WatsonxLLMAdapter(
                model_name="invalid/nonexistent-model",
                **project_config,
            )

    def test_get_model_token_limit(self, *, project_config: dict[str, Any]):
        """Test getting model token limit."""
        from docpipe.core.operators.functional.embeddings.adapters.outbound.watsonx_adapter import (
            WatsonxLLMAdapter,
        )

        adapter = WatsonxLLMAdapter(
            model_name="ibm/slate-125m-english-rtrvr",
            **project_config,
        )

        token_limit = adapter.get_model_token_limit()

        assert isinstance(token_limit, int)
        assert token_limit == 8192

    def test_get_embedding_dimension(self, *, project_config: dict[str, Any]):
        """Test getting embedding dimension."""
        from docpipe.core.operators.functional.embeddings.adapters.outbound.watsonx_adapter import (
            WatsonxLLMAdapter,
        )

        adapter = WatsonxLLMAdapter(
            model_name="ibm/slate-125m-english-rtrvr",
            **project_config,
        )

        dimension = adapter.get_embedding_dimension()

        assert isinstance(dimension, int)
        assert dimension == 768


@pytest.mark.integration
class TestWatsonxEmbeddingsOperatorIntegration:
    """Integration tests for EmbeddingsOperator with watsonx provider."""

    def test_embeddings_operator_with_watsonx(self, *, project_config: dict[str, Any], sample_texts: list[str]):
        """Test EmbeddingsOperator end-to-end with watsonx provider."""
        from docpipe.core.operators.functional.embeddings.embeddings_operator import (
            EmbeddingsOperator,
        )

        # Create PyArrow table with sample texts
        table = pa.table(
            {
                "id": [f"doc_{i}" for i in range(len(sample_texts))],
                "text": sample_texts,
            }
        )

        # Initialize operator with watsonx provider
        operator = EmbeddingsOperator(
            provider="watsonx",
            model_name="ibm/slate-125m-english-rtrvr",
            text_column="text",
            embedding_column="embeddings",
            **project_config,
        )

        # Execute operator
        result_table = operator.execute(data=table)

        # Verify results
        assert result_table is not None
        assert "embeddings" in result_table.column_names
        assert result_table.num_rows == len(sample_texts)

        # Check embeddings
        embeddings = result_table["embeddings"].to_pylist()
        assert len(embeddings) == len(sample_texts)
        assert all(isinstance(emb, list) for emb in embeddings)
        assert all(len(emb) == 768 for emb in embeddings)

    def test_embeddings_operator_batch_processing(self, *, project_config: dict[str, Any]):
        """Test batch processing with large dataset."""
        from docpipe.core.operators.functional.embeddings.embeddings_operator import (
            EmbeddingsOperator,
        )

        # Create larger dataset (more than batch_size)
        num_texts = 1000
        texts = [f"Sample text number {i} for testing batch processing." for i in range(num_texts)]

        table = pa.table(
            {
                "id": [f"doc_{i}" for i in range(num_texts)],
                "text": texts,
            }
        )

        # Initialize operator with batch_size=800
        operator = EmbeddingsOperator(
            provider="watsonx",
            model_name="ibm/slate-125m-english-rtrvr",
            text_column="text",
            embedding_column="embeddings",
            **project_config,
        )

        # Execute operator
        result_table = operator.execute(data=table)

        # Verify all texts were processed
        assert result_table.num_rows == num_texts
        embeddings = result_table["embeddings"].to_pylist()
        assert len(embeddings) == num_texts
        assert all(len(emb) == 768 for emb in embeddings)


@pytest.mark.integration
class TestWatsonxModelVariants:
    """Integration tests for different watsonx models."""

    def test_slate_30m_model(self, *, project_config: dict[str, Any]):
        """Test with slate-30m model (384 dimensions)."""
        from docpipe.core.operators.functional.embeddings.adapters.outbound.watsonx_adapter import (
            WatsonxLLMAdapter,
        )

        adapter = WatsonxLLMAdapter(
            model_name="ibm/slate-30m-english-rtrvr",
            **project_config,
        )

        text = "Test text for slate-30m model."
        embedding = adapter.generate_embeddings(text=text)

        assert isinstance(embedding, list)
        assert len(embedding) == 384  # slate-30m has 384 dimensions
        assert all(isinstance(x, float) for x in embedding)

    def test_slate_125m_model(self, *, project_config: dict[str, Any]):
        """Test with slate-125m model (768 dimensions)."""
        from docpipe.core.operators.functional.embeddings.adapters.outbound.watsonx_adapter import (
            WatsonxLLMAdapter,
        )

        adapter = WatsonxLLMAdapter(
            model_name="ibm/slate-125m-english-rtrvr",
            **project_config,
        )

        text = "Test text for slate-125m model."
        embedding = adapter.generate_embeddings(text=text)

        assert isinstance(embedding, list)
        assert len(embedding) == 768  # slate-125m has 768 dimensions
        assert all(isinstance(x, float) for x in embedding)


@pytest.mark.integration
class TestWatsonxErrorHandling:
    """Integration tests for error handling scenarios."""

    def test_empty_text_handling(self, *, project_config: dict[str, Any]):
        """Test handling of empty text."""
        from docpipe.core.operators.functional.embeddings.adapters.outbound.watsonx_adapter import (
            WatsonxLLMAdapter,
        )
        from docpipe.exceptions.docpipe_exceptions import ConfigurationError

        adapter = WatsonxLLMAdapter(
            model_name="ibm/slate-125m-english-rtrvr",
            **project_config,
        )

        with pytest.raises(ConfigurationError):
            adapter.generate_embeddings(text="")

    def test_long_text_truncation(self, *, project_config: dict[str, Any]):
        """Test automatic truncation of long texts."""
        from docpipe.core.operators.functional.embeddings.adapters.outbound.watsonx_adapter import (
            WatsonxLLMAdapter,
        )

        adapter = WatsonxLLMAdapter(
            model_name="ibm/slate-125m-english-rtrvr",
            **project_config,
        )

        # Create text longer than token limit (8192 tokens)
        long_text = " ".join(["word"] * 10000)

        # Should not raise error due to automatic truncation
        embedding = adapter.generate_embeddings(text=long_text)

        assert isinstance(embedding, list)
        assert len(embedding) == 768
