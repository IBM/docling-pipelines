# Copyright IBM Corp. 2025
# SPDX-License-Identifier: Apache-2.0

"""
Unit tests for LLM clients.

Tests cover base client functionality, retry logic, and provider-specific implementations.
"""

import importlib.util
import os
from unittest.mock import MagicMock, Mock, patch

import pytest

from docpipe.exceptions.docpipe_exceptions import ConfigurationError
from docpipe.integrations.base_llm_client import BaseLLMClient, retry_with_backoff
from docpipe.integrations.huggingface.client import HuggingFaceLLMClient
from docpipe.integrations.litellm.client import LiteLLMLLMClient

# Check for optional dependencies
HAS_SENTENCE_TRANSFORMERS = importlib.util.find_spec("sentence_transformers") is not None
HAS_LITELLM = importlib.util.find_spec("litellm") is not None


class TestRetryWithBackoff:
    """Test retry decorator functionality."""

    def test_retry_success_first_attempt(self):
        """Test successful execution on first attempt."""
        mock_func = Mock(return_value="success")
        decorated = retry_with_backoff(max_retries=3)(mock_func)

        result = decorated()

        assert result == "success"
        assert mock_func.call_count == 1

    def test_retry_success_after_failures(self):
        """Test successful execution after retries."""
        mock_func = Mock(
            __name__="test_func",
            side_effect=[Exception("fail"), Exception("fail"), "success"],
        )
        decorated = retry_with_backoff(max_retries=3, initial_delay=0.01)(mock_func)

        result = decorated()

        assert result == "success"
        assert mock_func.call_count == 3

    def test_retry_all_attempts_fail(self):
        """Test failure after all retry attempts."""
        mock_func = Mock(__name__="test_func", side_effect=Exception("persistent failure"))
        decorated = retry_with_backoff(max_retries=3, initial_delay=0.01)(mock_func)

        with pytest.raises(Exception, match="persistent failure"):
            decorated()

        assert mock_func.call_count == 3


class TestBaseLLMClient:
    """Test base LLM client functionality."""

    def test_abstract_methods_raise_not_implemented(self):
        """Test that abstract methods must be implemented."""

        class TestClient(BaseLLMClient):
            def generate_embeddings(self, text: str):
                return [0.1, 0.2]

            def generate_embeddings_batch(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
                return [[0.1, 0.2] for _ in texts]

            @staticmethod
            def get_model_token_limit(model_name: str) -> int:
                return 1000

            @staticmethod
            def get_embedding_dimension(model_name: str) -> int:
                return 768

        client = TestClient(model_name="test-model")
        embeddings = client.generate_embeddings("test")
        assert embeddings == [0.1, 0.2]

    def test_generate_not_supported(self):
        """Test that generate raises NotImplementedError by default."""

        class TestClient(BaseLLMClient):
            def generate_embeddings(self, text: str):
                return [0.1, 0.2]

            def generate_embeddings_batch(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
                return [[0.1, 0.2] for _ in texts]

            @staticmethod
            def get_model_token_limit(model_name: str) -> int:
                return 1000

            @staticmethod
            def get_embedding_dimension(model_name: str) -> int:
                return 768

        client = TestClient(model_name="test-model")

        with pytest.raises(NotImplementedError, match="does not support text generation"):
            client.generate("test prompt")

    def test_chat_not_supported(self):
        """Test that chat raises NotImplementedError by default."""

        class TestClient(BaseLLMClient):
            def generate_embeddings(self, text: str):
                return [0.1, 0.2]

            def generate_embeddings_batch(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
                return [[0.1, 0.2] for _ in texts]

            @staticmethod
            def get_model_token_limit(model_name: str) -> int:
                return 1000

            @staticmethod
            def get_embedding_dimension(model_name: str) -> int:
                return 768

        client = TestClient(model_name="test-model")

        with pytest.raises(NotImplementedError, match="does not support chat"):
            client.chat([{"role": "user", "content": "test"}])

    def test_validate_text_input(self):
        """Test text input validation."""

        class TestClient(BaseLLMClient):
            def generate_embeddings(self, text: str):
                self._validate_text_input(text)
                return [0.1, 0.2]

            def generate_embeddings_batch(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
                return [[0.1, 0.2] for _ in texts]

            @staticmethod
            def get_model_token_limit(model_name: str) -> int:
                return 1000

            @staticmethod
            def get_embedding_dimension(model_name: str) -> int:
                return 768

        client = TestClient(model_name="test-model")

        with pytest.raises(ConfigurationError, match="must be a non-empty string"):
            client.generate_embeddings("")

        with pytest.raises(ConfigurationError, match="must be a non-empty string"):
            client.generate_embeddings(None)  # type: ignore


@pytest.mark.skipif(not HAS_SENTENCE_TRANSFORMERS, reason="sentence-transformers package not installed")
class TestHuggingFaceLLMClient:
    """Test HuggingFace LLM client."""

    @patch("sentence_transformers.SentenceTransformer")
    def test_initialization_local_mode(self, mock_st):
        """Test client initialization in local mode."""
        client = HuggingFaceLLMClient(model_name="sentence-transformers/all-MiniLM-L6-v2", use_local=True)

        assert client.model_name == "sentence-transformers/all-MiniLM-L6-v2"
        assert client.use_local is True
        mock_st.assert_called_once()

    def test_initialization_api_mode_without_token_raises_error(self):
        """Test that API mode without token raises ConfigurationError."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ConfigurationError, match="HuggingFace API token required"):
                HuggingFaceLLMClient(model_name="sentence-transformers/all-MiniLM-L6-v2", use_local=False)

    @patch("sentence_transformers.SentenceTransformer")
    def test_generate_embeddings_local(self, mock_st):
        """Test local embeddings generation."""
        import numpy as np

        # Clear the model cache before test
        HuggingFaceLLMClient._loaded_models.clear()

        mock_model = MagicMock()
        # Create a proper numpy array mock
        mock_array = np.array([0.1, 0.2, 0.3])
        mock_model.encode.return_value = mock_array
        mock_st.return_value = mock_model

        client = HuggingFaceLLMClient(model_name="sentence-transformers/all-MiniLM-L6-v2", use_local=True)

        embeddings = client.generate_embeddings("test text")

        assert embeddings == [0.1, 0.2, 0.3]
        mock_model.encode.assert_called_once()

    def test_get_model_token_limit(self):
        """Test token limit retrieval."""
        assert HuggingFaceLLMClient.get_model_token_limit("sentence-transformers/all-MiniLM-L6-v2") == 512
        assert HuggingFaceLLMClient.get_model_token_limit("unknown-model") == 512

    def test_get_embedding_dimension(self):
        """Test embedding dimension retrieval."""
        assert HuggingFaceLLMClient.get_embedding_dimension("sentence-transformers/all-MiniLM-L6-v2") == 384
        assert HuggingFaceLLMClient.get_embedding_dimension("unknown-model") == 384


@pytest.mark.skipif(not HAS_LITELLM, reason="litellm package not installed")
class TestLiteLLMLLMClient:
    """Test LiteLLM client."""

    @patch("litellm.embedding")
    @patch("litellm.completion")
    def test_initialization(self, mock_completion, mock_embedding):
        """Test client initialization."""
        with patch("litellm.api_base", None):
            client = LiteLLMLLMClient(
                model_name="gpt-4",
                api_key="test-key",  # pragma: allowlist secret
            )

            assert client.model_name == "gpt-4"
            assert client.api_key == "test-key"  # pragma: allowlist secret

    @patch("litellm.embedding")
    def test_generate_embeddings(self, mock_embedding):
        """Test embeddings generation."""
        mock_response = MagicMock()
        mock_response.data = [{"embedding": [0.1, 0.2, 0.3]}]
        mock_embedding.return_value = mock_response

        client = LiteLLMLLMClient(model_name="text-embedding-ada-002")

        embeddings = client.generate_embeddings("test text")

        assert embeddings == [0.1, 0.2, 0.3]
        mock_embedding.assert_called_once()

    @patch("litellm.completion")
    def test_chat(self, mock_completion):
        """Test chat completion."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="response text"))]
        mock_completion.return_value = mock_response

        client = LiteLLMLLMClient(model_name="gpt-4")

        messages = [{"role": "user", "content": "test"}]
        response = client.chat(messages)

        assert response == "response text"
        mock_completion.assert_called_once()

    def test_get_model_token_limit(self):
        """Test token limit retrieval."""
        assert LiteLLMLLMClient.get_model_token_limit("gpt-4") == 8192
        assert LiteLLMLLMClient.get_model_token_limit("unknown-model") == 8191


class TestLiteLLMAPIKeyValidation:
    """Test API key validation for LiteLLM client."""

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_api_key_raises_error(self):
        """Test that missing API key raises ConfigurationError."""
        with pytest.raises(ConfigurationError, match="API key required"):
            LiteLLMLLMClient(model_name="text-embedding-3-small")

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})  # pragma: allowlist secret
    @patch("litellm.embedding")
    def test_env_var_api_key_works(self, mock_embedding):
        """Test that environment variable API key works."""
        client = LiteLLMLLMClient(model_name="text-embedding-3-small")
        assert client is not None
        assert client.model_name == "text-embedding-3-small"

    @patch("litellm.embedding")
    def test_param_api_key_works(self, mock_embedding):
        """Test that parameter API key works (with security warning logged)."""
        client = LiteLLMLLMClient(
            model_name="text-embedding-3-small",
            api_key="test-key",  # pragma: allowlist secret
        )
        assert client is not None
        assert client.api_key == "test-key"  # pragma: allowlist secret

    @patch.dict(os.environ, {"OPENAI_API_KEY": "env-key"})  # pragma: allowlist secret
    @patch("litellm.embedding")
    def test_env_var_with_param_works(self, mock_embedding):
        """Test that providing both env var and param works (param shows warning)."""
        client = LiteLLMLLMClient(
            model_name="text-embedding-3-small",
            api_key="param-key",  # pragma: allowlist secret
        )
        assert client is not None
        assert client.api_key == "param-key"  # pragma: allowlist secret

    @patch.dict(os.environ, {"COHERE_API_KEY": "test-key"})  # pragma: allowlist secret
    @patch("litellm.embedding")
    def test_cohere_provider_validation(self, mock_embedding):
        """Test validation for Cohere provider."""
        client = LiteLLMLLMClient(model_name="embed-english-v3.0")
        assert client is not None

    @patch.dict(os.environ, {}, clear=True)
    def test_cohere_missing_key_raises_error(self):
        """Test that missing Cohere API key raises error."""
        with pytest.raises(ConfigurationError, match="COHERE_API_KEY"):
            LiteLLMLLMClient(model_name="embed-english-v3.0")

    @patch.dict(
        os.environ,
        {"ANTHROPIC_API_KEY": "test-key"},  # pragma: allowlist secret
    )
    @patch("litellm.completion")
    def test_anthropic_provider_validation(self, mock_completion):
        """Test validation for Anthropic provider."""
        client = LiteLLMLLMClient(model_name="claude-3-opus")
        assert client is not None

    @patch.dict(os.environ, {}, clear=True)
    def test_anthropic_missing_key_raises_error(self):
        """Test that missing Anthropic API key raises error."""
        with pytest.raises(ConfigurationError, match="ANTHROPIC_API_KEY"):
            LiteLLMLLMClient(model_name="claude-3-opus")

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})  # pragma: allowlist secret
    @patch("litellm.embedding")
    def test_provider_prefix_extraction(self, mock_embedding):
        """Test provider extraction from model name with prefix."""
        client = LiteLLMLLMClient(model_name="openai/text-embedding-3-small")
        assert client is not None
