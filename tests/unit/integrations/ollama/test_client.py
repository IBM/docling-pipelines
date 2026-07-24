"""Tests for Ollama client."""

from unittest.mock import Mock, patch

import pytest

from docpipe.exceptions.docpipe_exceptions import DocpipeException
from docpipe.exceptions.error_codes import ErrorCode
from docpipe.integrations.ollama.client import (
    DEFAULT_TOKEN_LIMIT,
    OLLAMA_MODEL_TOKEN_LIMITS,
    InteractionMode,
    OllamaClient,
)

pytestmark = pytest.mark.requires_ollama


class TestInteractionMode:
    """Test InteractionMode enum."""

    def test_interaction_mode_values(self):
        """Test that InteractionMode has expected values."""
        assert InteractionMode.GENERATE.value == "generate"
        assert InteractionMode.CHAT.value == "chat"
        assert InteractionMode.EMBEDDINGS.value == "embeddings"

    def test_interaction_mode_from_string(self):
        """Test creating InteractionMode from string."""
        assert InteractionMode("generate") == InteractionMode.GENERATE
        assert InteractionMode("chat") == InteractionMode.CHAT
        assert InteractionMode("embeddings") == InteractionMode.EMBEDDINGS


class TestOllamaModelTokenLimits:
    """Test Ollama model token limits constants."""

    def test_token_limits_exist(self):
        """Test that token limits dictionary exists and has expected models."""
        assert isinstance(OLLAMA_MODEL_TOKEN_LIMITS, dict)
        assert "llama2" in OLLAMA_MODEL_TOKEN_LIMITS
        assert "llama3" in OLLAMA_MODEL_TOKEN_LIMITS
        assert "granite4" in OLLAMA_MODEL_TOKEN_LIMITS

    def test_token_limit_values(self):
        """Test specific token limit values."""
        assert OLLAMA_MODEL_TOKEN_LIMITS["llama2"] == 4096
        assert OLLAMA_MODEL_TOKEN_LIMITS["llama3.1"] == 128000
        assert OLLAMA_MODEL_TOKEN_LIMITS["granite4"] == 131072

    def test_default_token_limit(self):
        """Test default token limit constant."""
        assert DEFAULT_TOKEN_LIMIT == 4096


class TestOllamaClientInit:
    """Test OllamaClient initialization."""

    @patch("docpipe.integrations.ollama.client.OllamaClient._validate_model")
    def test_init_with_defaults(self, mock_validate):
        """Test initialization with default parameters."""
        client = OllamaClient(validate_model=False)

        assert client.model_name == "granite4"
        assert client.mode == InteractionMode.GENERATE
        assert client.system_prompt is None
        assert client.timeout is None
        mock_validate.assert_not_called()

    @patch("docpipe.integrations.ollama.client.OllamaClient._validate_model")
    def test_init_with_custom_params(self, mock_validate):
        """Test initialization with custom parameters."""
        client = OllamaClient(
            model_name="llama3",
            host="http://custom:11434",
            mode=InteractionMode.CHAT,
            system_prompt="You are a helpful assistant",
            timeout=30.0,
            max_concurrent_requests=16,
            validate_model=False,
        )

        assert client.model_name == "llama3"
        assert client.host == "http://custom:11434"
        assert client.mode == InteractionMode.CHAT
        assert client.system_prompt == "You are a helpful assistant"
        assert client.timeout == 30.0
        assert client.max_concurrent_requests == 16

    @patch("docpipe.integrations.ollama.client.OllamaClient._validate_model")
    def test_init_with_string_mode(self, mock_validate):
        """Test initialization with mode as string."""
        client = OllamaClient(mode=InteractionMode("chat"), validate_model=False)

        assert client.mode == InteractionMode.CHAT

    @patch("docpipe.integrations.ollama.client.OllamaClient._validate_model")
    def test_init_calls_validate_when_enabled(self, mock_validate):
        """Test that validation is called when validate_model=True."""
        _ = OllamaClient(validate_model=True)

        mock_validate.assert_called_once()


class TestOllamaClientValidateModel:
    """Test OllamaClient._validate_model method."""

    def test_validate_model_import_error(self):
        """Test validation when ollama package is not installed."""
        with patch("docpipe.integrations.ollama.client.OllamaClient._validate_model") as mock_validate:
            mock_validate.side_effect = ImportError("ollama package not installed")

            with pytest.raises(ImportError) as exc_info:
                OllamaClient(validate_model=True)

            assert "ollama package not installed" in str(exc_info.value)

    def test_validate_model_success(self):
        """Test successful model validation."""
        with patch("ollama.Client") as mock_client_class:
            # Mock the ollama client and response
            mock_client = Mock()
            mock_model = Mock()
            mock_model.model = "granite4:latest"
            mock_response = Mock()
            mock_response.models = [mock_model]

            mock_client.list.return_value = mock_response
            mock_client_class.return_value = mock_client

            # Should not raise
            client = OllamaClient(model_name="granite4", validate_model=True)
            assert client.model_name == "granite4"

    def test_validate_model_not_found(self):
        """Test validation when model is not available."""
        with patch("ollama.Client") as mock_client_class:
            mock_client = Mock()
            mock_model = Mock()
            mock_model.model = "llama3:latest"
            mock_response = Mock()
            mock_response.models = [mock_model]

            mock_client.list.return_value = mock_response
            mock_client_class.return_value = mock_client

            with pytest.raises(DocpipeException) as exc_info:
                OllamaClient(model_name="nonexistent", validate_model=True)

            assert exc_info.value.error_code == ErrorCode.OLLAMA_MODEL_NOT_FOUND
            assert "not available" in str(exc_info.value)

    def test_validate_model_connection_error(self):
        """Test validation when connection fails."""
        with patch("ollama.Client") as mock_client_class:
            mock_client = Mock()
            mock_client.list.side_effect = ConnectionError("Connection refused")
            mock_client_class.return_value = mock_client

            with pytest.raises(DocpipeException) as exc_info:
                OllamaClient(model_name="granite4", validate_model=True)

            assert exc_info.value.error_code == ErrorCode.OLLAMA_CONNECTION_FAILED
            assert "Failed to connect" in str(exc_info.value)

    def test_validate_model_dict_response(self):
        """Test validation with dict response format."""
        with patch("ollama.Client") as mock_client_class:
            mock_client = Mock()
            mock_response = {
                "models": [
                    {"model": "granite4:latest"},
                    {"model": "llama3:latest"},
                ]
            }
            mock_client.list.return_value = mock_response
            mock_client_class.return_value = mock_client

            client = OllamaClient(model_name="granite4", validate_model=True)
            assert client.model_name == "granite4"

    def test_validate_model_with_tag(self):
        """Test validation with model:tag format."""
        with patch("ollama.Client") as mock_client_class:
            mock_client = Mock()
            mock_model = Mock()
            mock_model.model = "granite4:latest"
            mock_response = Mock()
            mock_response.models = [mock_model]

            mock_client.list.return_value = mock_response
            mock_client_class.return_value = mock_client

            client = OllamaClient(model_name="granite4:custom", validate_model=True)
            assert client.model_name == "granite4:custom"


class TestOllamaClientRun:
    """Test OllamaClient.run method."""

    def test_run_generate_mode_dict_response(self):
        """Test run in GENERATE mode with dict response."""
        with patch("ollama.Client") as mock_client_class:
            mock_client = Mock()
            mock_client.generate.return_value = {"response": "Generated text"}
            mock_client_class.return_value = mock_client

            client = OllamaClient(mode=InteractionMode.GENERATE, validate_model=False)
            result = client.run(prompt="Test prompt")

            assert result == "Generated text"
            mock_client.generate.assert_called_once_with(model="granite4", prompt="Test prompt")

    def test_run_generate_mode_object_response(self):
        """Test run in GENERATE mode with GenerateResponse object."""
        with patch("ollama.Client") as mock_client_class:
            mock_client = Mock()
            mock_response = Mock()
            mock_response.response = "Generated text"
            mock_client.generate.return_value = mock_response
            mock_client_class.return_value = mock_client

            client = OllamaClient(mode=InteractionMode.GENERATE, validate_model=False)
            result = client.run(prompt="Test prompt")

            assert result == "Generated text"

    def test_run_chat_mode_dict_response(self):
        """Test run in CHAT mode with dict response."""
        with patch("ollama.Client") as mock_client_class:
            mock_client = Mock()
            mock_client.chat.return_value = {"message": {"content": "Chat response"}}
            mock_client_class.return_value = mock_client

            client = OllamaClient(mode=InteractionMode.CHAT, validate_model=False)
            result = client.run(prompt="Test prompt")

            assert result == "Chat response"
            mock_client.chat.assert_called_once()

    def test_run_chat_mode_with_system_prompt(self):
        """Test run in CHAT mode with system prompt."""
        with patch("ollama.Client") as mock_client_class:
            mock_client = Mock()
            mock_client.chat.return_value = {"message": {"content": "Chat response"}}
            mock_client_class.return_value = mock_client

            client = OllamaClient(mode=InteractionMode.CHAT, system_prompt="You are helpful", validate_model=False)
            result = client.run(prompt="Test prompt")

            assert result == "Chat response"
            call_args = mock_client.chat.call_args
            messages = call_args[1]["messages"]
            assert len(messages) == 2
            assert messages[0]["role"] == "system"
            assert messages[0]["content"] == "You are helpful"
            assert messages[1]["role"] == "user"

    def test_run_chat_mode_object_response(self):
        """Test run in CHAT mode with ChatResponse object."""
        with patch("ollama.Client") as mock_client_class:
            mock_client = Mock()
            mock_message = Mock()
            mock_message.content = "Chat response"
            mock_response = Mock()
            mock_response.message = mock_message
            mock_client.chat.return_value = mock_response
            mock_client_class.return_value = mock_client

            client = OllamaClient(mode=InteractionMode.CHAT, validate_model=False)
            result = client.run(prompt="Test prompt")

            assert result == "Chat response"

    def test_run_connection_error(self):
        """Test run with connection error."""
        with patch("ollama.Client") as mock_client_class:
            mock_client = Mock()
            mock_client.generate.side_effect = ConnectionError("Connection failed")
            mock_client_class.return_value = mock_client

            client = OllamaClient(validate_model=False)

            with pytest.raises(DocpipeException) as exc_info:
                client.run(prompt="Test")

            assert exc_info.value.error_code == ErrorCode.OLLAMA_CONNECTION_FAILED

    def test_run_model_not_found_error(self):
        """Test run with model not found error."""
        with patch("ollama.Client") as mock_client_class:
            mock_client = Mock()
            mock_client.generate.side_effect = ValueError("Model not found")
            mock_client_class.return_value = mock_client

            client = OllamaClient(validate_model=False)

            with pytest.raises(DocpipeException) as exc_info:
                client.run(prompt="Test")

            assert exc_info.value.error_code == ErrorCode.OLLAMA_MODEL_NOT_FOUND

    def test_run_import_error(self):
        """Test run when ollama package is not available."""
        # Mock the import at the function level
        with patch.dict("sys.modules", {"ollama": None}):
            client = OllamaClient(validate_model=False)

            with pytest.raises(ImportError) as exc_info:
                client.run(prompt="Test")

            assert "ollama package not installed" in str(exc_info.value)

    def test_run_empty_response(self):
        """Test run with empty response."""
        with patch("ollama.Client") as mock_client_class:
            mock_client = Mock()
            mock_client.generate.return_value = {"response": ""}
            mock_client_class.return_value = mock_client

            client = OllamaClient(validate_model=False)
            result = client.run(prompt="Test")

            assert result == ""

    def test_run_unexpected_response_format(self):
        """Test run with unexpected response format."""
        with patch("ollama.Client") as mock_client_class:
            mock_client = Mock()
            mock_client.generate.return_value = "unexpected string"
            mock_client_class.return_value = mock_client

            client = OllamaClient(validate_model=False)
            result = client.run(prompt="Test")

            assert result == ""

    def test_run_chat_mode_dict_message(self):
        """Test run in CHAT mode with dict message in response object."""
        with patch("ollama.Client") as mock_client_class:
            mock_client = Mock()
            mock_response = Mock()
            mock_response.message = {"content": "Chat response"}
            mock_client.chat.return_value = mock_response
            mock_client_class.return_value = mock_client

            client = OllamaClient(mode=InteractionMode.CHAT, validate_model=False)
            result = client.run(prompt="Test")

            assert result == "Chat response"

    def test_run_timeout_error(self):
        """Test run with timeout error."""
        with patch("ollama.Client") as mock_client_class:
            mock_client = Mock()
            mock_client.generate.side_effect = TimeoutError("Request timeout")
            mock_client_class.return_value = mock_client

            client = OllamaClient(validate_model=False)

            with pytest.raises(DocpipeException) as exc_info:
                client.run(prompt="Test")

            assert exc_info.value.error_code == ErrorCode.OLLAMA_CONNECTION_FAILED

    def test_run_generic_exception(self):
        """Test run with generic exception."""
        with patch("ollama.Client") as mock_client_class:
            mock_client = Mock()
            mock_client.generate.side_effect = RuntimeError("Unexpected error")
            mock_client_class.return_value = mock_client

            client = OllamaClient(validate_model=False)

            with pytest.raises(RuntimeError):
                client.run(prompt="Test")


class TestOllamaClientEdgeCases:
    """Test edge cases and error handling."""

    def test_validate_model_empty_model_list(self):
        """Test validation with empty model list."""
        with patch("ollama.Client") as mock_client_class:
            mock_client = Mock()
            mock_response = Mock()
            mock_response.models = []
            mock_client.list.return_value = mock_response
            mock_client_class.return_value = mock_client

            with pytest.raises(DocpipeException) as exc_info:
                OllamaClient(model_name="granite4", validate_model=True)

            assert "not available" in str(exc_info.value)

    def test_validate_model_unexpected_response(self):
        """Test validation with unexpected response format."""
        with patch("ollama.Client") as mock_client_class:
            mock_client = Mock()
            # Return unexpected format that will cause exception in validation
            mock_client.list.side_effect = Exception("Unexpected error")
            mock_client_class.return_value = mock_client

            # Should not raise during init, just log warning
            # The _validate_model catches generic exceptions and logs them
            client = OllamaClient(model_name="granite4", validate_model=True)
            assert client.model_name == "granite4"

    def test_run_none_response_content(self):
        """Test run when response content is None."""
        with patch("ollama.Client") as mock_client_class:
            mock_client = Mock()
            mock_response = Mock()
            mock_response.response = None
            mock_client.generate.return_value = mock_response
            mock_client_class.return_value = mock_client

            client = OllamaClient(validate_model=False)
            result = client.run(prompt="Test")

            assert result == ""

    def test_run_chat_none_content(self):
        """Test run in CHAT mode when content is None."""
        with patch("ollama.Client") as mock_client_class:
            mock_client = Mock()
            mock_message = Mock()
            mock_message.content = None
            mock_response = Mock()
            mock_response.message = mock_message
            mock_client.chat.return_value = mock_response
            mock_client_class.return_value = mock_client

            client = OllamaClient(mode=InteractionMode.CHAT, validate_model=False)
            result = client.run(prompt="Test")

            assert result == ""
