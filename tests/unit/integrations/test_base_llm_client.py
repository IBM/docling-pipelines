"""Unit tests for BaseLLMClient and related helpers in base_llm_client.py."""

from unittest.mock import patch

import pytest

from docpipe.exceptions.docpipe_exceptions import ConfigurationError, DependencyError, ExternalServiceError
from docpipe.integrations.base_llm_client import (
    BaseLLMClient,
    require_package,
    retry_with_backoff,
)

# ---------------------------------------------------------------------------
# Minimal concrete subclass
# ---------------------------------------------------------------------------


class _FakeClient(BaseLLMClient):
    """Concrete subclass for testing BaseLLMClient."""

    @staticmethod
    def get_model_token_limit(model_name: str) -> int:
        return 4096

    @staticmethod
    def get_embedding_dimension(model_name: str) -> int:
        return 768

    def generate_embeddings(self, text: str) -> list[float]:
        return [0.1, 0.2]

    def generate_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2] for _ in texts]


# ---------------------------------------------------------------------------
# BaseLLMClient.__init__
# ---------------------------------------------------------------------------


def test_base_llm_client_stores_model_name():
    client = _FakeClient("my-model")
    assert client.model_name == "my-model"


def test_base_llm_client_stores_extra_kwargs():
    client = _FakeClient("my-model", temperature=0.7, max_tokens=100)
    assert client.config["temperature"] == 0.7
    assert client.config["max_tokens"] == 100


# ---------------------------------------------------------------------------
# sanitize_config
# ---------------------------------------------------------------------------


def test_sanitize_config_masks_sensitive_keys():
    config = {
        "api_key": "secret123",  # pragma: allowlist secret
        "token": "tok-abc",
        "model": "gpt-4",
        "base_url": "http://localhost",
    }
    sanitized = _FakeClient.sanitize_config(config)
    assert sanitized["api_key"] == "***REDACTED***"
    assert sanitized["token"] == "***REDACTED***"
    assert sanitized["model"] == "gpt-4"
    assert sanitized["base_url"] == "http://localhost"


def test_sanitize_config_masks_partial_key_match():
    config = {"my_password": "s3cr3t", "authorization_header": "Bearer xyz"}  # pragma: allowlist secret
    sanitized = _FakeClient.sanitize_config(config)
    assert sanitized["my_password"] == "***REDACTED***"
    assert sanitized["authorization_header"] == "***REDACTED***"


def test_sanitize_config_empty_dict():
    assert _FakeClient.sanitize_config({}) == {}


# ---------------------------------------------------------------------------
# validate_configuration
# ---------------------------------------------------------------------------


def test_validate_configuration_passes_with_model_name():
    client = _FakeClient("valid-model")
    client.validate_configuration()  # Should not raise


def test_validate_configuration_raises_when_model_name_empty():
    client = _FakeClient("")
    with pytest.raises(ConfigurationError, match="model_name is required"):
        client.validate_configuration()


# ---------------------------------------------------------------------------
# _validate_text_input
# ---------------------------------------------------------------------------


def test_validate_text_input_passes_for_non_empty_string():
    client = _FakeClient("model")
    client._validate_text_input("hello world")  # Should not raise


def test_validate_text_input_raises_for_empty_string():
    client = _FakeClient("model")
    with pytest.raises(ConfigurationError, match="non-empty string"):
        client._validate_text_input("")


def test_validate_text_input_raises_for_non_string():
    client = _FakeClient("model")
    with pytest.raises(ConfigurationError, match="non-empty string"):
        client._validate_text_input(123)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# _validate_embeddings_output
# ---------------------------------------------------------------------------


def test_validate_embeddings_output_passes_for_valid_list():
    client = _FakeClient("model")
    client._validate_embeddings_output([0.1, 0.2, 0.3])  # Should not raise


def test_validate_embeddings_output_raises_for_empty_list():
    client = _FakeClient("model")
    with pytest.raises(ExternalServiceError, match="non-empty list"):
        client._validate_embeddings_output([])


def test_validate_embeddings_output_raises_for_non_numeric_elements():
    client = _FakeClient("model")
    with pytest.raises(ExternalServiceError, match="numeric"):
        client._validate_embeddings_output(["a", "b"])  # type: ignore[list-item]


def test_validate_embeddings_output_raises_for_non_list():
    client = _FakeClient("model")
    with pytest.raises(ExternalServiceError, match="non-empty list"):
        client._validate_embeddings_output(None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# generate / chat raise NotImplementedError
# ---------------------------------------------------------------------------


def test_generate_raises_not_implemented():
    client = _FakeClient("model")
    with pytest.raises(NotImplementedError, match="does not support text generation"):
        client.generate("prompt")


def test_chat_raises_not_implemented():
    client = _FakeClient("model")
    with pytest.raises(NotImplementedError, match="does not support chat"):
        client.chat([{"role": "user", "content": "hi"}])


# ---------------------------------------------------------------------------
# require_package
# ---------------------------------------------------------------------------


def test_require_package_passes_for_installed_package():
    require_package("os", "built-in")  # Should not raise


def test_require_package_raises_dependency_error_for_missing_package():
    with pytest.raises(DependencyError, match="nonexistent_pkg_xyz"):
        require_package("nonexistent_pkg_xyz", "pip install nonexistent_pkg_xyz")


# ---------------------------------------------------------------------------
# retry_with_backoff decorator
# ---------------------------------------------------------------------------


def test_retry_with_backoff_succeeds_on_first_attempt():
    call_count = 0

    @retry_with_backoff(max_retries=3, initial_delay=0.0)
    def always_succeeds():
        nonlocal call_count
        call_count += 1
        return "ok"

    result = always_succeeds()
    assert result == "ok"
    assert call_count == 1


def test_retry_with_backoff_retries_and_eventually_succeeds():
    attempts = []

    @retry_with_backoff(max_retries=3, initial_delay=0.0, backoff_factor=1.0)
    def fails_twice():
        attempts.append(1)
        if len(attempts) < 3:
            raise ValueError("not yet")
        return "done"

    with patch("docpipe.integrations.base_llm_client.time.sleep"):
        result = fails_twice()

    assert result == "done"
    assert len(attempts) == 3


def test_retry_with_backoff_raises_after_max_retries():
    @retry_with_backoff(max_retries=2, initial_delay=0.0, backoff_factor=1.0, exceptions=(ValueError,))
    def always_fails():
        raise ValueError("always")

    with patch("docpipe.integrations.base_llm_client.time.sleep"):
        with pytest.raises(ValueError, match="always"):
            always_fails()


def test_retry_with_backoff_caps_delay_at_max_delay():
    """After the first retry the backoff should be capped at max_delay."""
    sleep_calls = []

    @retry_with_backoff(max_retries=3, initial_delay=1.0, backoff_factor=100.0, max_delay=5.0)
    def always_fails():
        raise RuntimeError("fail")

    with patch("docpipe.integrations.base_llm_client.time.sleep", side_effect=lambda d: sleep_calls.append(d)):
        with pytest.raises(RuntimeError):
            always_fails()

    # First sleep uses initial_delay (1.0); second sleep should be capped at 5.0
    assert len(sleep_calls) == 2
    assert sleep_calls[0] == 1.0
    assert sleep_calls[1] == 5.0


def test_retry_with_backoff_does_not_retry_non_matching_exception():
    """Exceptions not in the tuple should propagate immediately."""

    @retry_with_backoff(max_retries=3, initial_delay=0.0, exceptions=(ValueError,))
    def raises_type_error():
        raise TypeError("wrong type")

    with pytest.raises(TypeError, match="wrong type"):
        raises_type_error()
