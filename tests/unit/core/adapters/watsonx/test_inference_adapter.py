"""Tests for WatsonX inference adapter."""

from unittest.mock import Mock, patch

import pytest

from datasift.core.adapters import WatsonXAdapter
from datasift.core.ports.llm_inference_port import LLMInferencePort


class TestWatsonXInferenceAdapter:
    """Test suite for WatsonXInferenceAdapter."""

    @pytest.fixture
    def mock_watsonx_client(self):
        """Create a mock WatsonX client."""
        with patch("datasift.core.adapters.watsonx.watsonx_adapter.WatsonXClient") as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            yield mock_client

    @pytest.fixture
    def adapter(self, mock_watsonx_client):
        """Create a WatsonX inference adapter instance."""
        return WatsonXAdapter(
            model_name="test-model",
            api_key="watsonx-test-credential",  # pragma: allowlist secret
            container_id="test-container",
            api_base="https://test.watsonx.ai",
            timeout=60,
        )

    def test_implements_llm_inference_port(self, adapter):
        """Test that adapter implements LLMInferencePort interface."""
        assert isinstance(adapter, LLMInferencePort)

    def test_initialization(self, mock_watsonx_client):
        """Test adapter initialization with all parameters."""
        adapter = WatsonXAdapter(
            model_name="granite-13b",
            api_key="watsonx-test-credential",  # pragma: allowlist secret
            container_id="test-project-id",
            api_base="https://us-south.ml.cloud.ibm.com",
            container_kind="project",
            timeout=120,
        )

        assert adapter.model_name == "granite-13b"
        assert adapter.client == mock_watsonx_client

    def test_initialization_minimal_params(self, mock_watsonx_client):
        """Test adapter initialization with minimal parameters."""
        adapter = WatsonXAdapter(model_name="test-model")

        assert adapter.model_name == "test-model"
        assert adapter.client == mock_watsonx_client

    def test_chat_success(self, adapter, mock_watsonx_client):
        """Test successful chat completion."""
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello!"},
        ]
        expected_response = "Hi there! How can I help you today?"

        mock_watsonx_client.chat.return_value = expected_response

        result = adapter.chat(messages=messages)

        assert result == expected_response
        mock_watsonx_client.chat.assert_called_once_with(messages=messages)

    def test_chat_with_kwargs(self, adapter, mock_watsonx_client):
        """Test chat completion with additional parameters."""
        messages = [{"role": "user", "content": "Test"}]
        expected_response = "Response"

        mock_watsonx_client.chat.return_value = expected_response

        result = adapter.chat(
            messages=messages,
            temperature=0.7,
            max_tokens=100,
            top_p=0.9,
        )

        assert result == expected_response
        mock_watsonx_client.chat.assert_called_once_with(
            messages=messages,
            temperature=0.7,
            max_tokens=100,
            top_p=0.9,
        )

    def test_chat_error_handling(self, adapter, mock_watsonx_client):
        """Test chat error handling."""
        messages = [{"role": "user", "content": "Test"}]
        mock_watsonx_client.chat.side_effect = Exception("API Error")

        with pytest.raises(Exception, match="API Error"):
            adapter.chat(messages=messages)

    def test_generate_success(self, adapter, mock_watsonx_client):
        """Test successful text generation."""
        prompt = "Write a short poem about AI"
        expected_response = "AI so bright, learning day and night"

        mock_watsonx_client.generate.return_value = expected_response

        result = adapter.generate(prompt=prompt)

        assert result == expected_response
        mock_watsonx_client.generate.assert_called_once_with(prompt=prompt)

    def test_generate_with_kwargs(self, adapter, mock_watsonx_client):
        """Test text generation with additional parameters."""
        prompt = "Test prompt"
        expected_response = "Generated text"

        mock_watsonx_client.generate.return_value = expected_response

        result = adapter.generate(
            prompt=prompt,
            temperature=0.5,
            max_tokens=200,
            stop_sequences=["END"],
        )

        assert result == expected_response
        mock_watsonx_client.generate.assert_called_once_with(
            prompt=prompt,
            temperature=0.5,
            max_tokens=200,
            stop_sequences=["END"],
        )

    def test_generate_error_handling(self, adapter, mock_watsonx_client):
        """Test generate error handling."""
        prompt = "Test"
        mock_watsonx_client.generate.side_effect = Exception("Generation failed")

        with pytest.raises(Exception, match="Generation failed"):
            adapter.generate(prompt=prompt)

    def test_chat_empty_messages(self, adapter, mock_watsonx_client):
        """Test chat with empty messages list."""
        messages = []
        mock_watsonx_client.chat.return_value = ""

        result = adapter.chat(messages=messages)

        assert result == ""
        mock_watsonx_client.chat.assert_called_once_with(messages=messages)

    def test_generate_empty_prompt(self, adapter, mock_watsonx_client):
        """Test generate with empty prompt."""
        prompt = ""
        mock_watsonx_client.generate.return_value = ""

        result = adapter.generate(prompt=prompt)

        assert result == ""
        mock_watsonx_client.generate.assert_called_once_with(prompt=prompt)

    def test_multiple_chat_calls(self, adapter, mock_watsonx_client):
        """Test multiple sequential chat calls."""
        messages1 = [{"role": "user", "content": "First"}]
        messages2 = [{"role": "user", "content": "Second"}]

        mock_watsonx_client.chat.side_effect = ["Response 1", "Response 2"]

        result1 = adapter.chat(messages=messages1)
        result2 = adapter.chat(messages=messages2)

        assert result1 == "Response 1"
        assert result2 == "Response 2"
        assert mock_watsonx_client.chat.call_count == 2

    def test_multiple_generate_calls(self, adapter, mock_watsonx_client):
        """Test multiple sequential generate calls."""
        mock_watsonx_client.generate.side_effect = ["Gen 1", "Gen 2", "Gen 3"]

        result1 = adapter.generate(prompt="Prompt 1")
        result2 = adapter.generate(prompt="Prompt 2")
        result3 = adapter.generate(prompt="Prompt 3")

        assert result1 == "Gen 1"
        assert result2 == "Gen 2"
        assert result3 == "Gen 3"
        assert mock_watsonx_client.generate.call_count == 3

    def test_client_initialization_parameters(self):
        """Test that client is initialized with correct parameters."""
        with patch("datasift.core.adapters.watsonx.watsonx_adapter.WatsonXClient") as mock_client_class:
            WatsonXAdapter(
                model_name="test-model",
                api_key="watsonx-test-credential",  # pragma: allowlist secret
                container_id="test-container-id",
                api_base="https://api.test.com",
                container_kind="space",
                timeout=90,
            )

            mock_client_class.assert_called_once_with(
                model_name="test-model",
                api_key="watsonx-test-credential",  # pragma: allowlist secret
                container_id="test-container-id",
                api_base="https://api.test.com",
                container_kind="space",
                timeout=90,
            )

    def test_adapter_preserves_model_name(self, adapter):
        """Test that adapter preserves the model name."""
        assert adapter.model_name == "test-model"

    @pytest.mark.parametrize(
        "messages,expected_call_count",
        [
            ([{"role": "user", "content": "Hi"}], 1),
            ([{"role": "system", "content": "System"}, {"role": "user", "content": "User"}], 1),
            ([], 1),
        ],
    )
    def test_chat_various_message_formats(self, adapter, mock_watsonx_client, messages, expected_call_count):
        """Test chat with various message formats."""
        mock_watsonx_client.chat.return_value = "Response"

        adapter.chat(messages=messages)

        assert mock_watsonx_client.chat.call_count == expected_call_count
        mock_watsonx_client.chat.assert_called_with(messages=messages)

    @pytest.mark.parametrize(
        "prompt,expected_call_count",
        [
            ("Short prompt", 1),
            ("A" * 1000, 1),  # Long prompt
            ("", 1),  # Empty prompt
        ],
    )
    def test_generate_various_prompt_lengths(self, adapter, mock_watsonx_client, prompt, expected_call_count):
        """Test generate with various prompt lengths."""
        mock_watsonx_client.generate.return_value = "Response"

        adapter.generate(prompt=prompt)

        assert mock_watsonx_client.generate.call_count == expected_call_count
        mock_watsonx_client.generate.assert_called_with(prompt=prompt)
