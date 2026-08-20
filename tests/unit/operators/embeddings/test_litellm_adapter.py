"""Unit tests for LiteLLMLLMAdapter covering all uncovered lines."""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_client():
    with patch("docpipe.core.operators.functional.embeddings.adapters.outbound.litellm_adapter.LiteLLMLLMClient") as m:
        instance = MagicMock()
        instance.generate_embeddings.return_value = [0.1, 0.2, 0.3]
        instance.generate_embeddings_batch.return_value = [[0.1, 0.2], [0.3, 0.4]]
        m.return_value = instance
        yield m, instance


@pytest.fixture
def adapter(mock_client):
    from docpipe.core.operators.functional.embeddings.adapters.outbound.litellm_adapter import LiteLLMLLMAdapter

    return LiteLLMLLMAdapter(model_name="text-embedding-3-small")


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_adapter_init_sets_model_name(mock_client):
    from docpipe.core.operators.functional.embeddings.adapters.outbound.litellm_adapter import LiteLLMLLMAdapter

    a = LiteLLMLLMAdapter(model_name="text-embedding-3-small", api_key="sk-test", api_base="http://custom/v1")
    assert a.model_name == "text-embedding-3-small"


@pytest.mark.unit
def test_adapter_init_passes_batch_size(mock_client):
    _, _ = mock_client
    from docpipe.core.operators.functional.embeddings.adapters.outbound.litellm_adapter import LiteLLMLLMAdapter

    LiteLLMLLMAdapter(model_name="text-embedding-3-small", batch_size=64)
    # Client was instantiated with correct batch_size
    mock_client[0].assert_called_once()
    call_kwargs = mock_client[0].call_args.kwargs
    assert call_kwargs.get("batch_size") == 64


# ---------------------------------------------------------------------------
# generate_embeddings
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_generate_embeddings_delegates_to_client(adapter, mock_client):
    _, instance = mock_client
    result = adapter.generate_embeddings("hello")
    instance.generate_embeddings.assert_called_once_with("hello")
    assert result == [0.1, 0.2, 0.3]


# ---------------------------------------------------------------------------
# generate_embeddings_batch
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_generate_embeddings_batch_delegates_to_client(adapter, mock_client):
    _, instance = mock_client
    result = adapter.generate_embeddings_batch(["hello", "world"])
    instance.generate_embeddings_batch.assert_called_once_with(["hello", "world"])
    assert len(result) == 2


# ---------------------------------------------------------------------------
# get_model_token_limit
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_get_model_token_limit(adapter):
    with patch(
        "docpipe.core.operators.functional.embeddings.adapters.outbound.litellm_adapter.LiteLLMLLMClient.get_model_token_limit",
        return_value=8191,
    ):
        limit = adapter.get_model_token_limit()
    assert limit == 8191


# ---------------------------------------------------------------------------
# get_embedding_dimension
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_get_embedding_dimension_returns_value_on_success(adapter):
    with patch(
        "docpipe.core.operators.functional.embeddings.adapters.outbound.litellm_adapter.LiteLLMLLMClient.get_embedding_dimension",
        return_value=1536,
    ):
        dim = adapter.get_embedding_dimension()
    assert dim == 1536


@pytest.mark.unit
def test_get_embedding_dimension_returns_none_on_exception(adapter):
    with patch(
        "docpipe.core.operators.functional.embeddings.adapters.outbound.litellm_adapter.LiteLLMLLMClient.get_embedding_dimension",
        side_effect=Exception("unknown model"),
    ):
        dim = adapter.get_embedding_dimension()
    assert dim is None


# ---------------------------------------------------------------------------
# get_config_schema
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_get_config_schema_returns_llm_provider_config(adapter):
    from docpipe.core.operators.shared.llm_provider_config import LLMProviderConfig

    schema = adapter.get_config_schema()
    assert schema is LLMProviderConfig


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_litellm_llm_adapter_registered():
    from docpipe.core.operators.functional.embeddings.adapters.outbound.factories.llm_adapter_factory import (
        LLMAdapterFactory,
    )

    assert "litellm" in LLMAdapterFactory._registry
