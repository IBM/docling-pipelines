"""
Integration tests for embeddings operator with Ollama client.

These tests require:
1. Ollama service to be running (ollama serve)
2. A model to be available (e.g., ollama pull granite4 or llama2)
"""

import pyarrow as pa
import pytest
import requests

from docpipe.core.operators.functional.embeddings.embeddings_operator import (
    EmbeddingsOperator,
)
from docpipe.exceptions.docpipe_exceptions import DocpipeException


def is_ollama_running():
    """Check if Ollama service is running."""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        return response.status_code == 200
    except (requests.ConnectionError, requests.Timeout):
        return False


def get_available_models():
    """Get list of available Ollama models."""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        if response.status_code == 200:
            data = response.json()
            return [model["name"] for model in data.get("models", [])]
        return []
    except (requests.ConnectionError, requests.Timeout):
        return []


# Skip all tests if Ollama is not running
pytestmark = pytest.mark.skipif(
    not is_ollama_running(),
    reason="Ollama is not running. Start Ollama to run integration tests.",
)


@pytest.fixture
def available_model():
    """Get an available model for testing."""
    models = get_available_models()
    if not models:
        pytest.skip("No Ollama models available. Pull a model first (e.g., ollama pull granite4)")
    # Prefer smaller models for faster tests
    preferred_models = ["granite4", "llama2", "mistral", "phi"]
    for model in preferred_models:
        for available in models:
            if model in available.lower():
                return available
    # Return first available model if no preferred model found
    return models[0]


@pytest.fixture
def sample_config(available_model):
    """Sample configuration for embeddings operator."""
    return {
        "embeddings_type": "ollama",
        "embeddings_model_id": available_model,
        "embeddings_column": "embeddings",
        "doc_column": "content",
    }


@pytest.fixture
def sample_table_single_doc():
    """Sample PyArrow table with a single document."""
    data = {
        "content": ["This is a test document for embeddings generation."],
        "doc_id_hash": ["doc1"],
    }
    return pa.table(data)


@pytest.fixture
def sample_table_multiple_docs():
    """Sample PyArrow table with multiple documents."""
    data = {
        "content": [
            "First document about machine learning.",
            "Second document about natural language processing.",
            "Third document about data science.",
        ],
        "doc_id_hash": ["doc1", "doc2", "doc3"],
    }
    return pa.table(data)


class TestEmbeddingsOllamaIntegration:
    """Integration tests for embeddings generation with real Ollama service."""

    def test_generate_embeddings_single_document(self, sample_config, sample_table_single_doc):
        """Test generating embeddings for a single document."""
        operator = EmbeddingsOperator(sample_config)
        result_tables, metadata = operator.transform(sample_table_single_doc)

        assert len(result_tables) == 1
        result_table = result_tables[0]

        # Check embeddings column was added
        assert "embeddings" in result_table.column_names
        assert result_table.num_rows == 1

        # Check embedding is not empty
        embedding = result_table["embeddings"][0].as_py()
        assert embedding is not None
        assert len(embedding) > 0
        assert all(isinstance(v, float) for v in embedding)

        # Check metadata
        assert metadata["processed_docs"] == 1
        assert metadata["failed_docs_count"] == 0
        assert metadata["node_status"] == "Completed"

    def test_generate_embeddings_multiple_documents(self, sample_config, sample_table_multiple_docs):
        """Test generating embeddings for multiple documents."""
        operator = EmbeddingsOperator(sample_config)
        result_tables, metadata = operator.transform(sample_table_multiple_docs)

        assert len(result_tables) == 1
        result_table = result_tables[0]

        # Check embeddings column was added
        assert "embeddings" in result_table.column_names
        assert result_table.num_rows == 3

        # Check all embeddings are not empty
        for i in range(result_table.num_rows):
            embedding = result_table["embeddings"][i].as_py()
            assert embedding is not None
            assert len(embedding) > 0
            assert all(isinstance(v, float) for v in embedding)

        # Check metadata
        assert metadata["processed_docs"] == 3
        assert metadata["failed_docs_count"] == 0
        assert metadata["node_status"] == "Completed"

    def test_empty_embedding_raises_error(self, sample_config):
        """Test that empty content is handled gracefully."""
        # Empty content should be skipped and marked as failed
        operator = EmbeddingsOperator(sample_config)

        # Create a table with empty content
        data = {
            "content": [""],
            "doc_id_hash": ["doc1"],
        }
        table = pa.table(data)

        # Transform should handle empty content gracefully
        _result_tables, metadata = operator.transform(table)

        # Check that the document was marked as failed
        assert metadata["processed_docs"] == 0
        assert metadata["failed_docs_count"] == 1
        assert metadata["node_status"] == "CompletedWithErrors"

    def test_embeddings_consistency(self, sample_config):
        """Test that same text produces consistent embeddings."""
        operator = EmbeddingsOperator(sample_config)

        text = "This is a test for embedding consistency."
        data = {
            "content": [text, text],
            "doc_id_hash": ["doc1", "doc2"],
        }
        table = pa.table(data)

        result_tables, _metadata = operator.transform(table)
        result_table = result_tables[0]

        # Get both embeddings
        embedding1 = result_table["embeddings"][0].as_py()
        embedding2 = result_table["embeddings"][1].as_py()

        # They should be identical or very similar
        assert len(embedding1) == len(embedding2)
        # Check if embeddings are very similar (allowing for small numerical differences)
        differences = sum(abs(a - b) for a, b in zip(embedding1, embedding2, strict=True))
        avg_difference = differences / len(embedding1)
        assert avg_difference < 0.01, "Embeddings for same text should be nearly identical"

    def test_long_text_chunking(self, sample_config):
        """Test embeddings generation with long text requiring chunking."""
        operator = EmbeddingsOperator(sample_config)

        # Create a long text that will require chunking
        long_text = " ".join(["This is a test sentence."] * 200)
        data = {
            "content": [long_text],
            "doc_id_hash": ["doc1"],
        }
        table = pa.table(data)

        result_tables, metadata = operator.transform(table)
        result_table = result_tables[0]

        # Check embedding was generated successfully
        embedding = result_table["embeddings"][0].as_py()
        assert embedding is not None
        assert len(embedding) > 0
        assert all(isinstance(v, float) for v in embedding)

        # Check metadata
        assert metadata["processed_docs"] == 1
        assert metadata["failed_docs_count"] == 0


class TestOllamaClientIntegration:
    """Integration tests specifically for OllamaClient."""

    def test_ollama_client_generate_embeddings(self, available_model):
        """Test OllamaClient.generate_embeddings() directly."""
        from docpipe.integrations.ollama.client import OllamaClient

        client = OllamaClient(model_name=available_model)

        # Test with normal text
        embedding = client.generate_embeddings("This is a test.")
        assert embedding is not None
        assert len(embedding) > 0
        assert all(isinstance(v, float) for v in embedding)

    def test_ollama_client_empty_response_raises_error(self, available_model):
        """Test that OllamaClient raises error for empty embeddings."""
        from unittest.mock import patch

        from docpipe.integrations.ollama.client import OllamaClient

        client = OllamaClient(model_name=available_model)

        # Mock ollama.embeddings to return empty embedding
        with patch("ollama.embeddings") as mock_embeddings:
            mock_embeddings.return_value = {"embedding": []}

            with pytest.raises(DocpipeException) as exc_info:
                client.generate_embeddings("test")

            assert "Empty or missing embedding" in str(exc_info.value)
            assert available_model in str(exc_info.value)

    def test_ollama_client_missing_embedding_key_raises_error(self, available_model):
        """Test that OllamaClient raises error when embedding key is missing."""
        from unittest.mock import patch

        from docpipe.integrations.ollama.client import OllamaClient

        client = OllamaClient(model_name=available_model)

        # Mock ollama.embeddings to return response without embedding key
        with patch("ollama.embeddings") as mock_embeddings:
            mock_embeddings.return_value = {"some_other_key": "value"}

            with pytest.raises(DocpipeException) as exc_info:
                client.generate_embeddings("test")

            assert "Empty or missing embedding" in str(exc_info.value)


if __name__ == "__main__":
    if is_ollama_running():
        models = get_available_models()
        print("\n" + "=" * 60)
        print("Running Ollama integration tests")
        print(f"Available models: {', '.join(models) if models else 'None'}")
        print("=" * 60 + "\n")
        pytest.main([__file__, "-v"])
    else:
        print("\n" + "=" * 60)
        print("Ollama is not running. Start Ollama to run integration tests:")
        print("  ollama serve")
        print("  ollama pull granite4  # or another model")
        print("=" * 60 + "\n")
