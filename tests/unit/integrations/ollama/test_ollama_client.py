"""Unit tests for OllamaClient.

All ollama package I/O is mocked — no real server or network calls.
"""

import json
import sys
from unittest.mock import Mock, patch

import pytest

# Pre-mock ollama to avoid import error in environments without it
if "ollama" not in sys.modules:
    mock_ollama = Mock()
    mock_ollama.Client = Mock()
    mock_ollama.GenerateResponse = Mock
    sys.modules["ollama"] = mock_ollama
    sys.modules["ollama._types"] = Mock()

from docpipe.integrations.ollama.client import (
    DEFAULT_TOKEN_LIMIT,
    OLLAMA_MODEL_TOKEN_LIMITS,
    InteractionMode,
    OllamaClient,
)


def _make_client(*, mode=InteractionMode.GENERATE, system_prompt=None, validate_model=False):
    """Construct OllamaClient with validation disabled to avoid real Ollama calls."""
    return OllamaClient(
        model_name="granite4",
        host="http://localhost:11434",
        mode=mode,
        system_prompt=system_prompt,
        validate_model=validate_model,
    )


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------


class TestOllamaClientInit:
    def test_defaults_set_correctly(self):
        client = _make_client()
        assert client.host == "http://localhost:11434"
        assert client.mode == InteractionMode.GENERATE
        assert client.system_prompt is None
        assert client.timeout is None

    def test_mode_accepts_string_value(self):
        client = OllamaClient(model_name="granite4", mode="chat", validate_model=False)
        assert client.mode == InteractionMode.CHAT

    def test_validate_model_called_when_enabled(self):
        with patch.object(OllamaClient, "_validate_model") as mock_validate:
            OllamaClient(model_name="granite4", validate_model=True)
            mock_validate.assert_called_once()

    def test_validate_model_not_called_when_disabled(self):
        with patch.object(OllamaClient, "_validate_model") as mock_validate:
            OllamaClient(model_name="granite4", validate_model=False)
            mock_validate.assert_not_called()


# ---------------------------------------------------------------------------
# _validate_model
# ---------------------------------------------------------------------------


class TestValidateModel:
    def _mock_list_response(self, model_names):
        """Build a mock models list response."""
        mock_response = Mock()
        mock_response.models = [Mock(model=name) for name in model_names]
        return mock_response

    def test_validates_successfully_when_model_present(self):
        client = _make_client()
        mock_client = Mock()
        mock_client.list.return_value = self._mock_list_response(["granite4"])

        with patch("ollama.Client", return_value=mock_client):
            client._validate_model()  # should not raise

    def test_raises_docpipe_exception_when_model_missing(self):
        from docpipe.exceptions.docpipe_exceptions import DocpipeException

        client = _make_client()
        mock_client = Mock()
        mock_client.list.return_value = self._mock_list_response(["llama3"])

        with patch("ollama.Client", return_value=mock_client):
            with pytest.raises(DocpipeException, match="not available"):
                client._validate_model()

    def test_raises_docpipe_exception_on_connection_error(self):
        from docpipe.exceptions.docpipe_exceptions import DocpipeException

        client = _make_client()
        mock_client = Mock()
        mock_client.list.side_effect = ConnectionError("refused")

        with patch("ollama.Client", return_value=mock_client):
            with pytest.raises(DocpipeException, match="Failed to connect"):
                client._validate_model()

    def test_warns_but_does_not_raise_on_generic_exception(self):
        client = _make_client()
        mock_client = Mock()
        mock_client.list.side_effect = RuntimeError("unexpected")

        with patch("ollama.Client", return_value=mock_client):
            client._validate_model()  # should not raise

    def test_raises_docpipe_exception_on_timeout_error(self):
        from docpipe.exceptions.docpipe_exceptions import DocpipeException

        client = _make_client()
        mock_client = Mock()
        mock_client.list.side_effect = TimeoutError("timed out")

        with patch("ollama.Client", return_value=mock_client):
            with pytest.raises(DocpipeException, match="Failed to connect"):
                client._validate_model()

    def test_handles_dict_models_response(self):
        client = _make_client()
        mock_client = Mock()
        mock_client.list.return_value = {"models": [Mock(model="granite4")]}

        with patch("ollama.Client", return_value=mock_client):
            client._validate_model()  # should not raise

    def test_handles_empty_models_list(self):
        from docpipe.exceptions.docpipe_exceptions import DocpipeException

        client = _make_client()
        mock_client = Mock()
        # Response with no .models attribute and not a dict → empty list
        mock_response = Mock(spec=[])
        mock_client.list.return_value = mock_response

        with patch("ollama.Client", return_value=mock_client):
            with pytest.raises(DocpipeException):
                client._validate_model()


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------


class TestRun:
    def test_generate_mode_with_dict_response(self):
        client = _make_client(mode=InteractionMode.GENERATE)
        mock_client = Mock()
        mock_client.generate.return_value = {"response": "hello"}

        with patch("ollama.Client", return_value=mock_client):
            result = client.run(prompt="hi")

        assert result == "hello"

    def test_generate_mode_with_object_response(self):
        client = _make_client(mode=InteractionMode.GENERATE)
        mock_client = Mock()
        mock_response = Mock(spec=["response"])
        mock_response.response = "world"
        mock_client.generate.return_value = mock_response

        with patch("ollama.Client", return_value=mock_client):
            result = client.run(prompt="hi")

        assert result == "world"

    def test_generate_mode_unexpected_response_returns_empty(self):
        client = _make_client(mode=InteractionMode.GENERATE)
        mock_client = Mock()
        mock_client.generate.return_value = 42  # unexpected type

        with patch("ollama.Client", return_value=mock_client):
            result = client.run(prompt="hi")

        assert result == ""

    def test_chat_mode_with_dict_response(self):
        client = _make_client(mode=InteractionMode.CHAT)
        mock_client = Mock()
        mock_client.chat.return_value = {"message": {"content": "chat reply"}}

        with patch("ollama.Client", return_value=mock_client):
            result = client.run(prompt="hi")

        assert result == "chat reply"

    def test_chat_mode_with_object_response(self):
        client = _make_client(mode=InteractionMode.CHAT)
        mock_client = Mock()
        mock_msg = Mock()
        mock_msg.content = "object reply"
        mock_response = Mock(spec=["message"])
        mock_response.message = mock_msg
        mock_client.chat.return_value = mock_response

        with patch("ollama.Client", return_value=mock_client):
            result = client.run(prompt="hi")

        assert result == "object reply"

    def test_chat_mode_with_system_prompt(self):
        client = _make_client(mode=InteractionMode.CHAT, system_prompt="You are helpful.")
        mock_client = Mock()
        mock_client.chat.return_value = {"message": {"content": "ok"}}

        with patch("ollama.Client", return_value=mock_client):
            result = client.run(prompt="hi")

        assert result == "ok"
        call_messages = mock_client.chat.call_args[1]["messages"]
        assert call_messages[0]["role"] == "system"

    def test_chat_mode_message_dict_content(self):
        client = _make_client(mode=InteractionMode.CHAT)
        mock_client = Mock()
        mock_response = Mock(spec=["message"])
        mock_response.message = {"content": "dict msg content"}
        mock_client.chat.return_value = mock_response

        with patch("ollama.Client", return_value=mock_client):
            result = client.run(prompt="hi")

        assert result == "dict msg content"

    def test_chat_mode_no_message_returns_empty(self):
        client = _make_client(mode=InteractionMode.CHAT)
        mock_client = Mock()
        mock_client.chat.return_value = {}  # dict, no "message" key

        with patch("ollama.Client", return_value=mock_client):
            result = client.run(prompt="hi")

        assert result == ""

    def test_raises_docpipe_exception_on_connection_error(self):
        from docpipe.exceptions.docpipe_exceptions import DocpipeException

        client = _make_client()
        mock_client = Mock()
        mock_client.generate.side_effect = ConnectionError("refused")

        with patch("ollama.Client", return_value=mock_client):
            with pytest.raises(DocpipeException, match="Failed to connect"):
                client.run(prompt="hi")

    def test_raises_docpipe_exception_on_value_error(self):
        from docpipe.exceptions.docpipe_exceptions import DocpipeException

        client = _make_client()
        mock_client = Mock()
        mock_client.generate.side_effect = ValueError("bad model")

        with patch("ollama.Client", return_value=mock_client):
            with pytest.raises(DocpipeException, match="not found or invalid"):
                client.run(prompt="hi")

    def test_re_raises_unexpected_exception(self):
        client = _make_client()
        mock_client = Mock()
        mock_client.generate.side_effect = RuntimeError("boom")

        with patch("ollama.Client", return_value=mock_client):
            with pytest.raises(RuntimeError, match="boom"):
                client.run(prompt="hi")

    def test_chat_mode_no_message_attr_returns_empty(self):
        # Response object has neither .message attr nor is it a dict
        client = _make_client(mode=InteractionMode.CHAT)
        mock_client = Mock()
        mock_client.chat.return_value = Mock(spec=[])  # no .message attribute

        with patch("ollama.Client", return_value=mock_client):
            result = client.run(prompt="hi")

        assert result == ""

    def test_run_raises_timeout_error_as_docpipe_exception(self):
        from docpipe.exceptions.docpipe_exceptions import DocpipeException

        client = _make_client()
        mock_client = Mock()
        mock_client.generate.side_effect = TimeoutError("timed out")

        with patch("ollama.Client", return_value=mock_client):
            with pytest.raises(DocpipeException, match="Failed to connect"):
                client.run(prompt="hi")


# ---------------------------------------------------------------------------
# _parse_json_response
# ---------------------------------------------------------------------------


class TestParseJsonResponse:
    def setup_method(self):
        self.client = _make_client()

    def test_returns_none_for_empty_string(self):
        assert self.client._parse_json_response("") is None

    def test_returns_none_for_whitespace(self):
        assert self.client._parse_json_response("   ") is None

    def test_parses_direct_json(self):
        result = self.client._parse_json_response('{"key": "value"}')
        assert result == {"key": "value"}

    def test_parses_json_in_markdown_code_block(self):
        raw = '```json\n{"key": "value"}\n```'
        result = self.client._parse_json_response(raw)
        assert result == {"key": "value"}

    def test_parses_json_from_mixed_content(self):
        raw = 'Some text before {"key": "value"} and after'
        result = self.client._parse_json_response(raw)
        assert result == {"key": "value"}

    def test_parses_json_array_wrapped_in_detections(self):
        # The array branch fires when: direct parse fails, no markdown block matches,
        # no '{' appears before '[' in the text, so the '{' finder returns nothing
        # and the '[' finder picks up the array and wraps it in {"detections": ...}.
        raw = "detections: [1, 2, 3]"
        result = self.client._parse_json_response(raw)
        assert result == {"detections": [1, 2, 3]}

    def test_returns_none_for_unparseable_content(self):
        result = self.client._parse_json_response("not json at all")
        assert result is None


# ---------------------------------------------------------------------------
# run_json
# ---------------------------------------------------------------------------


class TestRunJson:
    def test_returns_parsed_json_on_first_attempt(self):
        client = _make_client()
        with patch.object(client, "run", return_value='{"detections": []}'):
            result = client.run_json(prompt="test")
        assert result == {"detections": []}

    def test_retries_and_succeeds_on_second_attempt(self):
        client = _make_client()
        responses = iter(["not json", '{"detections": []}'])
        with patch.object(client, "run", side_effect=lambda **kw: next(responses)):
            result = client.run_json(prompt="test", retries=2)
        assert result == {"detections": []}

    def test_raises_json_decode_error_after_all_retries(self):
        client = _make_client()
        with patch.object(client, "run", return_value="not json"):
            with pytest.raises(json.JSONDecodeError):
                client.run_json(prompt="test", retries=2)


# ---------------------------------------------------------------------------
# Static / class methods
# ---------------------------------------------------------------------------


class TestStaticMethods:
    def test_is_installed_returns_true_when_ollama_found(self):
        mock_result = Mock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            assert OllamaClient.is_installed() is True

    def test_is_installed_returns_false_when_not_found(self):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            assert OllamaClient.is_installed() is False

    def test_is_server_running_returns_true_when_list_succeeds(self):
        mock_client = Mock()
        mock_client.list.return_value = Mock()
        with patch("ollama.Client", return_value=mock_client):
            assert OllamaClient.is_server_running() is True

    def test_is_server_running_returns_false_on_exception(self):
        mock_client = Mock()
        mock_client.list.side_effect = ConnectionError("refused")
        with patch("ollama.Client", return_value=mock_client):
            assert OllamaClient.is_server_running() is False

    def test_is_model_available_returns_true_when_model_found(self):
        mock_client = Mock()
        mock_model = Mock()
        mock_model.model = "granite4:latest"
        mock_response = Mock()
        mock_response.models = [mock_model]
        mock_client.list.return_value = mock_response
        with patch("ollama.Client", return_value=mock_client):
            assert OllamaClient.is_model_available("granite4") is True

    def test_is_model_available_returns_false_when_model_missing(self):
        mock_client = Mock()
        mock_response = Mock()
        mock_response.models = []
        mock_client.list.return_value = mock_response
        with patch("ollama.Client", return_value=mock_client):
            assert OllamaClient.is_model_available("granite4") is False

    def test_is_model_available_returns_false_on_exception(self):
        mock_client = Mock()
        mock_client.list.side_effect = RuntimeError("error")
        with patch("ollama.Client", return_value=mock_client):
            assert OllamaClient.is_model_available("granite4") is False

    def test_get_model_token_limit_known_model(self):
        limit = OllamaClient.get_model_token_limit("llama3")
        assert limit == OLLAMA_MODEL_TOKEN_LIMITS["llama3"]

    def test_get_model_token_limit_unknown_model(self):
        assert OllamaClient.get_model_token_limit("unknown-model-xyz") == DEFAULT_TOKEN_LIMIT

    def test_get_model_token_limit_strips_tag(self):
        assert OllamaClient.get_model_token_limit("llama3:latest") == OLLAMA_MODEL_TOKEN_LIMITS["llama3"]

    def test_get_embedding_dimension_returns_zero(self):
        assert OllamaClient.get_embedding_dimension("any-model") == 0

    def test_pull_model_returns_true_on_success(self):
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.stdout = iter([])
        with patch("subprocess.Popen", return_value=mock_process):
            assert OllamaClient.pull_model("granite4", show_progress=False) is True

    def test_pull_model_returns_false_on_nonzero_exit(self):
        mock_process = Mock()
        mock_process.returncode = 1
        mock_process.stdout = iter([])
        with patch("subprocess.Popen", return_value=mock_process):
            assert OllamaClient.pull_model("granite4", show_progress=False) is False

    def test_pull_model_returns_false_on_exception(self):
        with patch("subprocess.Popen", side_effect=OSError("no ollama")):
            assert OllamaClient.pull_model("granite4") is False

    def test_pull_model_show_progress_streams_stdout(self):
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.stdout = iter(["pulling...\n", "done\n"])
        with patch("subprocess.Popen", return_value=mock_process):
            assert OllamaClient.pull_model("granite4", show_progress=True) is True

    def test_is_model_available_with_dict_response(self):
        mock_client = Mock()
        mock_client.list.return_value = {"models": [{"name": "granite4:latest"}]}
        with patch("ollama.Client", return_value=mock_client):
            assert OllamaClient.is_model_available("granite4") is True

    def test_is_model_available_with_raw_list_fallback(self):
        # Response with no .models attr and not a dict → treated as iterable directly
        mock_client = Mock()
        mock_model = Mock()
        mock_model.model = "granite4"
        # spec=[] ensures no .models attribute, not a dict
        raw_list_response = [mock_model]
        mock_client.list.return_value = raw_list_response
        with patch("ollama.Client", return_value=mock_client):
            assert OllamaClient.is_model_available("granite4") is True

    def test_is_server_running_uses_default_host_when_none(self):
        mock_client = Mock()
        mock_client.list.return_value = Mock()
        with patch("ollama.Client", return_value=mock_client):
            assert OllamaClient.is_server_running(host=None) is True

    def test_is_installed_returns_false_on_timeout(self):
        import subprocess

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="ollama", timeout=5)):
            assert OllamaClient.is_installed() is False


# ---------------------------------------------------------------------------
# generate / chat wrappers
# ---------------------------------------------------------------------------


class TestGenerateAndChatWrappers:
    def test_generate_delegates_to_run(self):
        client = _make_client()
        with patch.object(client, "run", return_value="generated") as mock_run:
            result = client.generate("hello")
        assert result == "generated"
        mock_run.assert_called_once_with(prompt="hello")

    def test_chat_switches_to_chat_mode_and_restores(self):
        client = _make_client(mode=InteractionMode.GENERATE)
        with patch.object(client, "run", return_value="reply"):
            result = client.chat([{"role": "user", "content": "hi"}])
        assert result == "reply"
        assert client.mode == InteractionMode.GENERATE  # restored

    def test_chat_skips_system_role_messages(self):
        client = _make_client(mode=InteractionMode.GENERATE)
        with patch.object(client, "run", return_value="reply") as mock_run:
            client.chat([{"role": "system", "content": "sys"}, {"role": "user", "content": "hello"}])
        # Only user content should be in prompt
        assert "hello" in mock_run.call_args[1]["prompt"]
        assert "sys" not in mock_run.call_args[1]["prompt"]


# ---------------------------------------------------------------------------
# generate_embeddings
# ---------------------------------------------------------------------------


class TestGenerateEmbeddings:
    def test_returns_embedding_from_dict_response(self):
        client = _make_client()
        mock_client = Mock()
        mock_client.embeddings.return_value = {"embedding": [0.1, 0.2, 0.3]}

        with patch("ollama.Client", return_value=mock_client):
            result = client.generate_embeddings("hello world")

        assert result == [0.1, 0.2, 0.3]

    def test_returns_embedding_from_object_response(self):
        client = _make_client()
        mock_client = Mock()
        mock_response = Mock()
        mock_response.embedding = [0.4, 0.5, 0.6]
        mock_client.embeddings.return_value = mock_response

        with patch("ollama.Client", return_value=mock_client):
            result = client.generate_embeddings("hello world")

        assert result == [0.4, 0.5, 0.6]

    def test_raises_on_unexpected_response_type(self):
        from docpipe.exceptions.docpipe_exceptions import DocpipeException

        client = _make_client()
        mock_client = Mock()
        mock_client.embeddings.return_value = Mock(spec=[])  # no .embedding attr, not a dict

        with patch("ollama.Client", return_value=mock_client):
            with pytest.raises(DocpipeException, match="Unexpected response type"):
                client.generate_embeddings("hello world")

    def test_raises_on_empty_embedding(self):
        from docpipe.exceptions.docpipe_exceptions import DocpipeException

        client = _make_client()
        mock_client = Mock()
        mock_client.embeddings.return_value = {"embedding": []}

        with patch("ollama.Client", return_value=mock_client):
            with pytest.raises(DocpipeException, match="Empty or missing embedding"):
                client.generate_embeddings("hello world")

    def test_raises_on_none_embedding(self):
        from docpipe.exceptions.docpipe_exceptions import DocpipeException

        client = _make_client()
        mock_client = Mock()
        mock_client.embeddings.return_value = {"embedding": None}

        with patch("ollama.Client", return_value=mock_client):
            with pytest.raises(DocpipeException, match="Empty or missing embedding"):
                client.generate_embeddings("hello world")

    def test_raises_docpipe_exception_on_connection_error(self):
        from docpipe.exceptions.docpipe_exceptions import DocpipeException

        client = _make_client()
        mock_client = Mock()
        mock_client.embeddings.side_effect = ConnectionError("refused")

        with patch("ollama.Client", return_value=mock_client):
            with pytest.raises(DocpipeException, match="Failed to connect to Ollama server during embedding"):
                client.generate_embeddings("hello world")

    def test_raises_docpipe_exception_on_value_error(self):
        from docpipe.exceptions.docpipe_exceptions import DocpipeException

        client = _make_client()
        mock_client = Mock()
        mock_client.embeddings.side_effect = ValueError("bad value")

        with patch("ollama.Client", return_value=mock_client):
            with pytest.raises(DocpipeException, match="Invalid response from Ollama API"):
                client.generate_embeddings("hello world")

    def test_raises_docpipe_exception_on_unexpected_error(self):
        from docpipe.exceptions.docpipe_exceptions import DocpipeException

        client = _make_client()
        mock_client = Mock()
        mock_client.embeddings.side_effect = RuntimeError("unexpected")

        with patch("ollama.Client", return_value=mock_client):
            with pytest.raises(DocpipeException, match="Unexpected error during embedding generation"):
                client.generate_embeddings("hello world")

    def test_raises_configuration_error_on_empty_text(self):
        from docpipe.exceptions.docpipe_exceptions import ConfigurationError

        client = _make_client()
        with pytest.raises(ConfigurationError):
            client.generate_embeddings("")


# ---------------------------------------------------------------------------
# generate_embeddings_batch
# ---------------------------------------------------------------------------


class TestGenerateEmbeddingsBatch:
    def test_returns_embeddings_for_all_texts(self):
        client = _make_client()
        mock_client = Mock()
        mock_client.embeddings.side_effect = [
            {"embedding": [0.1, 0.2]},
            {"embedding": [0.3, 0.4]},
        ]

        with patch("ollama.Client", return_value=mock_client):
            result = client.generate_embeddings_batch(["text one", "text two"])

        assert len(result) == 2
        assert [0.1, 0.2] in result
        assert [0.3, 0.4] in result

    def test_raises_configuration_error_on_empty_list(self):
        from docpipe.exceptions.docpipe_exceptions import ConfigurationError

        client = _make_client()
        with pytest.raises(ConfigurationError, match="non-empty list"):
            client.generate_embeddings_batch([])

    def test_raises_configuration_error_on_non_list_input(self):
        from docpipe.exceptions.docpipe_exceptions import ConfigurationError

        client = _make_client()
        with pytest.raises(ConfigurationError, match="non-empty list"):
            client.generate_embeddings_batch("not a list")  # type: ignore[arg-type]

    def test_raises_configuration_error_on_empty_string_in_list(self):
        from docpipe.exceptions.docpipe_exceptions import ConfigurationError

        client = _make_client()
        with pytest.raises(ConfigurationError, match="non-empty strings"):
            client.generate_embeddings_batch(["valid", ""])

    def test_raises_docpipe_exception_when_single_embedding_fails(self):
        from docpipe.exceptions.docpipe_exceptions import DocpipeException

        client = _make_client()
        mock_client = Mock()
        mock_client.embeddings.side_effect = RuntimeError("embedding failed")

        with patch("ollama.Client", return_value=mock_client):
            with pytest.raises(DocpipeException, match="Batch embedding generation failed"):
                client.generate_embeddings_batch(["text one"])

    def test_raises_docpipe_exception_on_connection_error(self):
        from docpipe.exceptions.docpipe_exceptions import DocpipeException

        client = _make_client()
        mock_client = Mock()
        mock_client.embeddings.side_effect = ConnectionError("refused")

        with patch("ollama.Client", return_value=mock_client):
            with pytest.raises(DocpipeException):
                client.generate_embeddings_batch(["text one"])

    def test_raises_docpipe_exception_on_unexpected_response_type(self):
        from docpipe.exceptions.docpipe_exceptions import DocpipeException

        client = _make_client()
        mock_client = Mock()
        mock_client.embeddings.return_value = Mock(spec=[])  # no .embedding, not a dict

        with patch("ollama.Client", return_value=mock_client):
            with pytest.raises(DocpipeException):
                client.generate_embeddings_batch(["text one"])

    def test_raises_docpipe_exception_on_empty_embedding_in_batch(self):
        from docpipe.exceptions.docpipe_exceptions import DocpipeException

        client = _make_client()
        mock_client = Mock()
        mock_client.embeddings.return_value = {"embedding": []}

        with patch("ollama.Client", return_value=mock_client):
            with pytest.raises(DocpipeException):
                client.generate_embeddings_batch(["text one"])


# ---------------------------------------------------------------------------
# _ensure_server_running / _ensure_model_available / ensure_ready
# ---------------------------------------------------------------------------


class TestEnsureMethods:
    def test_ensure_server_running_returns_true_when_already_running(self):
        with patch.object(OllamaClient, "is_server_running", return_value=True):
            ok, msg = OllamaClient._ensure_server_running(auto_start=False)
        assert ok is True
        assert msg == ""

    def test_ensure_server_running_returns_error_when_not_running_no_auto_start(self):
        with patch.object(OllamaClient, "is_server_running", return_value=False):
            ok, msg = OllamaClient._ensure_server_running(auto_start=False)
        assert ok is False
        assert "not running" in msg

    def test_ensure_server_running_starts_server_when_auto_start_true(self):
        with (
            patch.object(OllamaClient, "is_server_running", return_value=False),
            patch.object(OllamaClient, "start_server", return_value=True),
        ):
            ok, _msg = OllamaClient._ensure_server_running(auto_start=True)
        assert ok is True

    def test_ensure_server_running_returns_error_when_start_fails(self):
        with (
            patch.object(OllamaClient, "is_server_running", return_value=False),
            patch.object(OllamaClient, "start_server", return_value=False),
        ):
            ok, msg = OllamaClient._ensure_server_running(auto_start=True)
        assert ok is False
        assert "Failed to start" in msg

    def test_ensure_model_available_returns_true_when_model_present(self):
        with patch.object(OllamaClient, "is_model_available", return_value=True):
            ok, msg = OllamaClient._ensure_model_available("granite4", auto_pull=False)
        assert ok is True
        assert msg == ""

    def test_ensure_model_available_returns_error_when_missing_no_auto_pull(self):
        with patch.object(OllamaClient, "is_model_available", return_value=False):
            ok, msg = OllamaClient._ensure_model_available("granite4", auto_pull=False)
        assert ok is False
        assert "not available" in msg

    def test_ensure_model_available_pulls_when_auto_pull_true(self):
        with (
            patch.object(OllamaClient, "is_model_available", return_value=False),
            patch.object(OllamaClient, "pull_model", return_value=True),
        ):
            ok, _msg = OllamaClient._ensure_model_available("granite4", auto_pull=True)
        assert ok is True

    def test_ensure_model_available_returns_error_when_pull_fails(self):
        with (
            patch.object(OllamaClient, "is_model_available", return_value=False),
            patch.object(OllamaClient, "pull_model", return_value=False),
        ):
            ok, msg = OllamaClient._ensure_model_available("granite4", auto_pull=True)
        assert ok is False
        assert "Failed to pull" in msg

    def test_ensure_ready_returns_false_when_not_installed(self):
        with patch.object(OllamaClient, "is_installed", return_value=False):
            ok, msg = OllamaClient.ensure_ready("granite4")
        assert ok is False
        assert "not installed" in msg

    def test_ensure_ready_returns_false_when_server_not_running(self):
        with (
            patch.object(OllamaClient, "is_installed", return_value=True),
            patch.object(OllamaClient, "_ensure_server_running", return_value=(False, "server down")),
        ):
            ok, msg = OllamaClient.ensure_ready("granite4")
        assert ok is False
        assert msg == "server down"

    def test_ensure_ready_returns_false_when_model_not_available(self):
        with (
            patch.object(OllamaClient, "is_installed", return_value=True),
            patch.object(OllamaClient, "_ensure_server_running", return_value=(True, "")),
            patch.object(OllamaClient, "_ensure_model_available", return_value=(False, "model missing")),
        ):
            ok, msg = OllamaClient.ensure_ready("granite4")
        assert ok is False
        assert msg == "model missing"

    def test_ensure_ready_returns_true_when_all_checks_pass(self):
        with (
            patch.object(OllamaClient, "is_installed", return_value=True),
            patch.object(OllamaClient, "_ensure_server_running", return_value=(True, "")),
            patch.object(OllamaClient, "_ensure_model_available", return_value=(True, "")),
        ):
            ok, msg = OllamaClient.ensure_ready("granite4")
        assert ok is True
        assert "granite4" in msg


# ---------------------------------------------------------------------------
# start_server
# ---------------------------------------------------------------------------


class TestStartServer:
    def test_returns_true_when_server_starts_successfully(self):
        mock_process = Mock()
        with (
            patch("subprocess.Popen", return_value=mock_process),
            patch("platform.system", return_value="Linux"),
            patch("time.sleep"),
            patch.object(OllamaClient, "is_server_running", side_effect=[True]),
        ):
            result = OllamaClient.start_server(wait_timeout=3)
        assert result is True

    def test_returns_false_when_server_does_not_start_in_time(self):
        mock_process = Mock()
        with (
            patch("subprocess.Popen", return_value=mock_process),
            patch("platform.system", return_value="Linux"),
            patch("time.sleep"),
            patch.object(OllamaClient, "is_server_running", return_value=False),
        ):
            result = OllamaClient.start_server(wait_timeout=2)
        assert result is False

    def test_returns_false_on_exception(self):
        with patch("subprocess.Popen", side_effect=OSError("popen failed")):
            result = OllamaClient.start_server(wait_timeout=1)
        assert result is False

    def test_windows_path_uses_cmd(self):
        mock_process = Mock()
        with (
            patch("subprocess.Popen", return_value=mock_process) as mock_popen,
            patch("platform.system", return_value="Windows"),
            patch("time.sleep"),
            patch.object(OllamaClient, "is_server_running", return_value=True),
        ):
            OllamaClient.start_server(wait_timeout=1)
        args = mock_popen.call_args[0][0]
        assert "cmd" in args
