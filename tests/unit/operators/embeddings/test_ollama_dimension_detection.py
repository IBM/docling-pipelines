"""Tests for Ollama adapter dimension detection functionality."""

from unittest.mock import Mock, patch

import pytest

from docpipe.core.operators.functional.embeddings.adapters.outbound.ollama_adapter import (
    OllamaLLMAdapter,
)
from docpipe.exceptions.docpipe_exceptions import ExternalServiceError
from docpipe.integrations.ollama.client import InteractionMode


class TestOllamaDimensionDetection:
    """Test suite for Ollama adapter dimension detection."""

    @pytest.fixture
    def mock_ollama_client(self):
        """Create a mock Ollama client."""
        with patch(
            "docpipe.core.operators.functional.embeddings.adapters.outbound.ollama_adapter.OllamaClient"
        ) as mock:
            yield mock

    def test_dimension_detection_success(self, mock_ollama_client):
        """Test successful dimension detection."""
        # Setup mock to return 768-dimensional embedding
        mock_client_instance = Mock()
        mock_client_instance.generate_embeddings.return_value = [0.1] * 768
        mock_ollama_client.return_value = mock_client_instance

        # Create adapter
        adapter = OllamaLLMAdapter(model_name="nomic-embed-text")

        # Get dimension (should trigger detection)
        dimension = adapter.get_embedding_dimension()

        # Verify
        assert dimension == 768
        mock_client_instance.generate_embeddings.assert_called_once_with("dimension detection")

    def test_dimension_caching(self, mock_ollama_client):
        """Test that dimension is cached after first detection."""
        # Setup mock
        mock_client_instance = Mock()
        mock_client_instance.generate_embeddings.return_value = [0.1] * 768
        mock_ollama_client.return_value = mock_client_instance

        # Create adapter
        adapter = OllamaLLMAdapter(model_name="nomic-embed-text")

        # Call get_embedding_dimension multiple times
        dim1 = adapter.get_embedding_dimension()
        dim2 = adapter.get_embedding_dimension()
        dim3 = adapter.get_embedding_dimension()

        # Verify dimension is correct
        assert dim1 == 768
        assert dim2 == 768
        assert dim3 == 768

        # Verify generate_embeddings was only called once (cached after first call)
        assert mock_client_instance.generate_embeddings.call_count == 1

    def test_dimension_detection_different_models(self, mock_ollama_client):
        """Test dimension detection with different model dimensions."""
        test_cases = [
            ("nomic-embed-text", 768),
            ("mxbai-embed-large", 1024),
            ("all-minilm", 384),
        ]

        for model_name, expected_dim in test_cases:
            # Setup mock for this model
            mock_client_instance = Mock()
            mock_client_instance.generate_embeddings.return_value = [0.1] * expected_dim
            mock_ollama_client.return_value = mock_client_instance

            # Create adapter
            adapter = OllamaLLMAdapter(model_name=model_name)

            # Get dimension
            dimension = adapter.get_embedding_dimension()

            # Verify
            assert dimension == expected_dim, f"Failed for model {model_name}"

    def test_dimension_detection_connection_error(self, mock_ollama_client):
        """Test dimension detection when Ollama server is not running."""
        # Setup mock to raise connection error
        mock_client_instance = Mock()
        mock_client_instance.generate_embeddings.side_effect = ConnectionError("Failed to connect to Ollama server")
        mock_ollama_client.return_value = mock_client_instance

        # Create adapter
        adapter = OllamaLLMAdapter(model_name="nomic-embed-text")

        # Get dimension should return None (graceful failure)
        dimension = adapter.get_embedding_dimension()

        # Verify
        assert dimension is None

    def test_dimension_detection_model_not_found(self, mock_ollama_client):
        """Test dimension detection when model is not available."""
        # Setup mock to raise model not found error
        mock_client_instance = Mock()
        mock_client_instance.generate_embeddings.side_effect = Exception("Model 'invalid-model' not found")
        mock_ollama_client.return_value = mock_client_instance

        # Create adapter
        adapter = OllamaLLMAdapter(model_name="invalid-model")

        # Get dimension should return None (graceful failure)
        dimension = adapter.get_embedding_dimension()

        # Verify
        assert dimension is None

    def test_dimension_detection_invalid_response(self, mock_ollama_client):
        """Test dimension detection with invalid embedding response."""
        # Setup mock to return invalid response
        mock_client_instance = Mock()
        mock_client_instance.generate_embeddings.return_value = None
        mock_ollama_client.return_value = mock_client_instance

        # Create adapter
        adapter = OllamaLLMAdapter(model_name="nomic-embed-text")

        # Get dimension should return None (graceful failure)
        dimension = adapter.get_embedding_dimension()

        # Verify
        assert dimension is None

    def test_dimension_detection_empty_list(self, mock_ollama_client):
        """Test dimension detection with empty embedding list."""
        # Setup mock to return empty list
        mock_client_instance = Mock()
        mock_client_instance.generate_embeddings.return_value = []
        mock_ollama_client.return_value = mock_client_instance

        # Create adapter
        adapter = OllamaLLMAdapter(model_name="nomic-embed-text")

        # Get dimension should return None (graceful failure)
        dimension = adapter.get_embedding_dimension()

        # Verify
        assert dimension is None

    def test_detect_dimension_method_directly(self, mock_ollama_client):
        """Test _detect_dimension method directly for error handling."""
        # Setup mock to return valid embedding
        mock_client_instance = Mock()
        mock_client_instance.generate_embeddings.return_value = [0.1] * 768
        mock_ollama_client.return_value = mock_client_instance

        # Create adapter
        adapter = OllamaLLMAdapter(model_name="nomic-embed-text")

        # Call _detect_dimension directly
        dimension = adapter._detect_dimension()

        # Verify
        assert dimension == 768

    def test_detect_dimension_connection_error_message(self, mock_ollama_client):
        """Test that connection errors provide helpful error messages."""
        # Setup mock to raise connection error
        mock_client_instance = Mock()
        mock_client_instance.generate_embeddings.side_effect = ConnectionError("Connection refused")
        mock_ollama_client.return_value = mock_client_instance

        # Create adapter
        adapter = OllamaLLMAdapter(model_name="nomic-embed-text")

        # Call _detect_dimension should raise ExternalServiceError with helpful message
        with pytest.raises(ExternalServiceError) as exc_info:
            adapter._detect_dimension()

        # Verify error message contains helpful information
        error_msg = str(exc_info.value)
        assert "Ensure Ollama server is running" in error_msg
        assert "ollama serve" in error_msg

    def test_detect_dimension_model_not_found_message(self, mock_ollama_client):
        """Test that model not found errors provide helpful error messages."""
        # Setup mock to raise model not found error
        mock_client_instance = Mock()
        mock_client_instance.generate_embeddings.side_effect = Exception("Model 'test-model' not found")
        mock_ollama_client.return_value = mock_client_instance

        # Create adapter
        adapter = OllamaLLMAdapter(model_name="test-model")

        # Call _detect_dimension should raise ExternalServiceError with helpful message
        with pytest.raises(ExternalServiceError) as exc_info:
            adapter._detect_dimension()

        # Verify error message contains helpful information
        error_msg = str(exc_info.value)
        assert "ollama pull test-model" in error_msg

    def test_dimension_detection_preserves_adapter_functionality(self, mock_ollama_client):
        """Test that dimension detection doesn't interfere with normal embedding generation."""
        # Setup mock
        mock_client_instance = Mock()
        mock_client_instance.generate_embeddings.return_value = [0.1] * 768
        mock_ollama_client.return_value = mock_client_instance

        # Create adapter
        adapter = OllamaLLMAdapter(model_name="nomic-embed-text")

        # Get dimension first
        dimension = adapter.get_embedding_dimension()
        assert dimension == 768

        # Now generate actual embeddings
        embeddings = adapter.generate_embeddings("test text")

        # Verify embeddings work correctly
        assert len(embeddings) == 768
        assert all(isinstance(x, float) for x in embeddings)

        # Verify generate_embeddings was called twice (once for detection, once for actual)
        assert mock_client_instance.generate_embeddings.call_count == 2

    def test_dimension_detection_thread_safety(self, mock_ollama_client):
        """Test that dimension caching is thread-safe (basic check)."""
        # Setup mock
        mock_client_instance = Mock()
        mock_client_instance.generate_embeddings.return_value = [0.1] * 768
        mock_ollama_client.return_value = mock_client_instance

        # Create adapter
        adapter = OllamaLLMAdapter(model_name="nomic-embed-text")

        # Simulate concurrent calls (in practice, would use threading)
        dimensions = [adapter.get_embedding_dimension() for _ in range(10)]

        # Verify all calls return same dimension
        assert all(d == 768 for d in dimensions)

        # Verify generate_embeddings was only called once (cached)
        assert mock_client_instance.generate_embeddings.call_count == 1


class TestOllamaAdapterBackwardCompatibility:
    """Test that dimension detection doesn't break existing functionality."""

    @pytest.fixture
    def mock_ollama_client(self):
        """Create a mock Ollama client."""
        with patch(
            "docpipe.core.operators.functional.embeddings.adapters.outbound.ollama_adapter.OllamaClient"
        ) as mock:
            yield mock

    def test_generate_embeddings_still_works(self, mock_ollama_client):
        """Test that generate_embeddings method still works as before."""
        # Setup mock
        mock_client_instance = Mock()
        mock_client_instance.generate_embeddings.return_value = [0.1, 0.2, 0.3]
        mock_ollama_client.return_value = mock_client_instance

        # Create adapter
        adapter = OllamaLLMAdapter(model_name="nomic-embed-text")

        # Generate embeddings
        result = adapter.generate_embeddings("test text")

        # Verify
        assert result == [0.1, 0.2, 0.3]
        mock_client_instance.generate_embeddings.assert_called_with("test text")

    def test_get_model_token_limit_still_works(self, mock_ollama_client):
        """Test that get_model_token_limit method still works as before."""
        # Setup mock
        mock_client_instance = Mock()
        mock_ollama_client.return_value = mock_client_instance

        # Create adapter
        adapter = OllamaLLMAdapter(model_name="llama3.2")

        # Get token limit
        limit = adapter.get_model_token_limit()

        # Verify (llama3.2 should have a known limit or default to 4096)
        assert isinstance(limit, int)
        assert limit > 0

    def test_adapter_initialization_unchanged(self, mock_ollama_client):
        """Test that adapter initialization hasn't changed."""
        # Setup mock
        mock_client_instance = Mock()
        mock_ollama_client.return_value = mock_client_instance

        # Create adapter with various configurations
        adapter1 = OllamaLLMAdapter(model_name="nomic-embed-text")
        adapter2 = OllamaLLMAdapter(model_name="llama3.2", extra_param="value")

        # Verify adapters are created successfully
        assert adapter1.model_name == "nomic-embed-text"
        assert adapter2.model_name == "llama3.2"
        assert adapter1._cached_dimension is None  # Not detected yet
        assert adapter2._cached_dimension is None  # Not detected yet

    def test_adapter_passes_config_parameters_to_client(self, mock_ollama_client):
        """Test that adapter correctly passes host, timeout, and validate_model to OllamaClient."""
        # Setup mock
        mock_client_instance = Mock()
        mock_ollama_client.return_value = mock_client_instance

        # Create adapter with custom configuration
        adapter = OllamaLLMAdapter(
            model_name="nomic-embed-text",
            host="http://custom-host:11434",
            max_concurrent_requests=16,
            timeout=30.0,
            validate_model=False,
        )

        # Verify OllamaClient was called with correct parameters
        mock_ollama_client.assert_called_once()
        call_kwargs = mock_ollama_client.call_args[1]

        assert call_kwargs["model_name"] == "nomic-embed-text"
        assert call_kwargs["host"] == "http://custom-host:11434"
        assert call_kwargs["max_concurrent_requests"] == 16
        assert call_kwargs["timeout"] == 30.0
        assert call_kwargs["validate_model"] is False
        assert call_kwargs["mode"] == InteractionMode.EMBEDDINGS

        # Verify adapter is created successfully
        assert adapter.model_name == "nomic-embed-text"
