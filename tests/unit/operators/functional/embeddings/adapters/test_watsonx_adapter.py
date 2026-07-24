#!/usr/bin/env python3
"""
Unit tests for WatsonxLLMAdapter.

Tests adapter registration, initialization, embedding generation,
and model validation with mocked watsonx.ai client.
"""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from docpipe.exceptions.docpipe_exceptions import ConfigurationError


@pytest.fixture
def valid_config() -> dict[str, Any]:
    """Fixture providing valid watsonx adapter configuration."""
    return {
        "provider_config": {
            "api_key": "test-api-key",  # pragma: allowlist secret
            "url": "https://us-south.ml.cloud.ibm.com",
            "container_kind": "project",
            "container_id": "test-project-id",
            "batch_size": 800,
        }
    }


@pytest.fixture
def mock_watsonx_client():
    """Fixture providing mocked WatsonxRestEmbeddingClient."""
    with patch(
        "docpipe.core.operators.functional.embeddings.adapters.outbound.watsonx_adapter.WatsonxRestEmbeddingClient"
    ) as mock_client_class:
        mock_instance = MagicMock()
        mock_instance.generate_embeddings.return_value = [0.1] * 768
        mock_instance.generate_embeddings_batch.return_value = [[0.1] * 768, [0.2] * 768]
        mock_client_class.return_value = mock_instance
        mock_client_class.get_model_token_limit.return_value = 8192
        mock_client_class.get_embedding_dimension.return_value = 768
        yield mock_client_class


@pytest.fixture
def mock_model_validator():
    """Fixture providing mocked model validator and dimension lookup."""
    with (
        patch(
            "docpipe.core.operators.functional.embeddings.adapters.outbound.watsonx_adapter.validate_model_id"
        ) as mock_validator,
        patch(
            "docpipe.core.operators.functional.embeddings.adapters.outbound.watsonx_adapter.get_model_dimension"
        ) as mock_dimension,
    ):
        mock_validator.return_value = True
        mock_dimension.return_value = 768
        yield {"validator": mock_validator, "dimension": mock_dimension}


@pytest.mark.unit
class TestWatsonxAdapterRegistration:
    """Test adapter registration with LLMAdapterFactory."""

    def test_adapter_registered_with_factory(self):
        """Test that WatsonxLLMAdapter is registered with the factory."""
        from docpipe.core.operators.functional.embeddings.adapters.outbound.factories.llm_adapter_factory import (
            LLMAdapterFactory,
        )

        available_adapters = LLMAdapterFactory.list_adapters()
        assert "watsonx" in available_adapters, "WatsonxLLMAdapter should be registered"

    def test_adapter_has_required_attributes(self):
        """Test that adapter defines required class attributes."""
        from docpipe.core.operators.functional.embeddings.adapters.outbound.watsonx_adapter import (
            WatsonxLLMAdapter,
        )

        assert hasattr(WatsonxLLMAdapter, "ADAPTER_NAME")
        assert WatsonxLLMAdapter.ADAPTER_NAME == "watsonx"
        assert hasattr(WatsonxLLMAdapter, "ADAPTER_DISPLAY_NAME")
        assert WatsonxLLMAdapter.ADAPTER_DISPLAY_NAME == "IBM watsonx.ai"


@pytest.mark.unit
class TestWatsonxAdapterInitialization:
    """Test adapter initialization with various configurations."""

    def test_init_with_valid_config(self, *, valid_config: dict[str, Any], mock_watsonx_client, mock_model_validator):
        """Test successful initialization with valid configuration."""
        from docpipe.core.operators.functional.embeddings.adapters.outbound.watsonx_adapter import (
            WatsonxLLMAdapter,
        )

        # Mock get_session_info to return None for job_run_id
        with patch(
            "docpipe.core.operators.functional.embeddings.adapters.outbound.watsonx_adapter.get_session_info"
        ) as mock_session_info:
            mock_session_info.return_value = None

            adapter = WatsonxLLMAdapter(model_name="ibm/slate-125m-english-rtrvr", **valid_config)

            assert adapter.model_name == "ibm/slate-125m-english-rtrvr"
            assert adapter.api_key == "test-api-key"
            assert adapter.url == "https://us-south.ml.cloud.ibm.com"
            assert adapter.container_kind == "project"
            assert adapter.container_id == "test-project-id"
            assert adapter.client is not None

            # Verify model validation was called
            mock_model_validator["validator"].assert_called_once_with(
                model_id="ibm/slate-125m-english-rtrvr",
                api_key="test-api-key",
                url="https://us-south.ml.cloud.ibm.com",
            )

            # Verify client was initialized with correct parameters
            # Use ANY for job_run_id since it comes from get_session_info()
            mock_watsonx_client.assert_called_once_with(
                api_key="test-api-key",
                url="https://us-south.ml.cloud.ibm.com",
                container_kind="project",
                container_id="test-project-id",
                model_name="ibm/slate-125m-english-rtrvr",
                batch_size=800,
                job_run_id=None,
                enable_rate_limiting=False,
            )

    def test_init_with_missing_api_key(self, *, mock_model_validator):
        """Test initialization fails with missing api_key."""
        from docpipe.core.operators.functional.embeddings.adapters.outbound.watsonx_adapter import (
            WatsonxLLMAdapter,
        )

        config = {
            "provider_config": {
                "url": "https://us-south.ml.cloud.ibm.com",
                "container_kind": "project",
                "container_id": "test-project-id",
            }
        }

        with pytest.raises(ConfigurationError, match=r"Missing required configuration parameter.*api_key"):
            WatsonxLLMAdapter(model_name="ibm/slate-125m-english-rtrvr", **config)

    def test_init_with_missing_url(self, *, mock_model_validator):
        """Test initialization fails with missing url."""
        from docpipe.core.operators.functional.embeddings.adapters.outbound.watsonx_adapter import (
            WatsonxLLMAdapter,
        )

        config = {
            "provider_config": {
                "api_key": "test-api-key",
                "container_kind": "project",
                "container_id": "test-project-id",
            }
        }

        with pytest.raises(ConfigurationError, match=r"Missing required configuration parameter.*url"):
            WatsonxLLMAdapter(model_name="ibm/slate-125m-english-rtrvr", **config)

    def test_init_with_missing_container_kind(self, *, mock_model_validator):
        """Test initialization fails with missing container_kind."""
        from docpipe.core.operators.functional.embeddings.adapters.outbound.watsonx_adapter import (
            WatsonxLLMAdapter,
        )

        config = {
            "provider_config": {
                "api_key": "test-api-key",
                "url": "https://us-south.ml.cloud.ibm.com",
                "container_id": "test-project-id",
            }
        }

        with pytest.raises(ConfigurationError, match=r"Missing required configuration parameter.*container_kind"):
            WatsonxLLMAdapter(model_name="ibm/slate-125m-english-rtrvr", **config)

    def test_init_with_missing_container_id(self, *, mock_model_validator):
        """Test initialization fails with missing container_id."""
        from docpipe.core.operators.functional.embeddings.adapters.outbound.watsonx_adapter import (
            WatsonxLLMAdapter,
        )

        config = {
            "provider_config": {
                "api_key": "test-api-key",
                "url": "https://us-south.ml.cloud.ibm.com",
                "container_kind": "project",
            }
        }

        with pytest.raises(ConfigurationError, match=r"Missing required configuration parameter.*container_id"):
            WatsonxLLMAdapter(model_name="ibm/slate-125m-english-rtrvr", **config)

    def test_init_with_invalid_model(self, *, valid_config: dict[str, Any], mock_watsonx_client):
        """Test initialization fails with invalid model."""
        from docpipe.core.operators.functional.embeddings.adapters.outbound.watsonx_adapter import (
            WatsonxLLMAdapter,
        )

        with patch(
            "docpipe.core.operators.functional.embeddings.adapters.outbound.watsonx_adapter.validate_model_id"
        ) as mock_validator:
            mock_validator.return_value = False

            with pytest.raises(ValueError, match=r"Model.*not available"):
                WatsonxLLMAdapter(model_name="invalid-model", **valid_config)

    def test_init_with_default_batch_size(self, *, mock_watsonx_client, mock_model_validator):
        """Test initialization uses default batch size when not specified."""
        from docpipe.core.operators.functional.embeddings.adapters.outbound.watsonx_adapter import (
            WatsonxLLMAdapter,
        )

        config = {
            "provider_config": {
                "api_key": "test-api-key",  # pragma: allowlist secret
                "url": "https://us-south.ml.cloud.ibm.com",
                "container_kind": "project",
                "container_id": "test-project-id",
            }
        }

        WatsonxLLMAdapter(model_name="ibm/slate-125m-english-rtrvr", **config)

        # Verify client was initialized with default batch_size=800
        mock_watsonx_client.assert_called_once()
        call_kwargs = mock_watsonx_client.call_args.kwargs
        assert call_kwargs["batch_size"] == 800

    def test_init_with_enable_rate_limiting_true(self, *, mock_watsonx_client, mock_model_validator):
        """Test initialization with enable_rate_limiting=True."""
        from docpipe.core.operators.functional.embeddings.adapters.outbound.watsonx_adapter import (
            WatsonxLLMAdapter,
        )

        config = {
            "provider_config": {
                "api_key": "test-api-key",  # pragma: allowlist secret
                "url": "https://us-south.ml.cloud.ibm.com",
                "container_kind": "project",
                "container_id": "test-project-id",
                "enable_rate_limiting": True,
            }
        }

        WatsonxLLMAdapter(model_name="ibm/slate-125m-english-rtrvr", **config)

        # Verify client was initialized with enable_rate_limiting=True
        mock_watsonx_client.assert_called_once()
        call_kwargs = mock_watsonx_client.call_args.kwargs
        assert call_kwargs["enable_rate_limiting"] is True

    def test_init_with_enable_rate_limiting_false(self, *, mock_watsonx_client, mock_model_validator):
        """Test initialization with enable_rate_limiting=False."""
        from docpipe.core.operators.functional.embeddings.adapters.outbound.watsonx_adapter import (
            WatsonxLLMAdapter,
        )

        config = {
            "provider_config": {
                "api_key": "test-api-key",  # pragma: allowlist secret
                "url": "https://us-south.ml.cloud.ibm.com",
                "container_kind": "project",
                "container_id": "test-project-id",
                "enable_rate_limiting": False,
            }
        }

        WatsonxLLMAdapter(model_name="ibm/slate-125m-english-rtrvr", **config)

        # Verify client was initialized with enable_rate_limiting=False
        mock_watsonx_client.assert_called_once()
        call_kwargs = mock_watsonx_client.call_args.kwargs
        assert call_kwargs["enable_rate_limiting"] is False

    def test_init_with_enable_rate_limiting_default(self, *, mock_watsonx_client, mock_model_validator):
        """Test initialization defaults to enable_rate_limiting=False when not specified."""
        from docpipe.core.operators.functional.embeddings.adapters.outbound.watsonx_adapter import (
            WatsonxLLMAdapter,
        )

        config = {
            "provider_config": {
                "api_key": "test-api-key",  # pragma: allowlist secret
                "url": "https://us-south.ml.cloud.ibm.com",
                "container_kind": "project",
                "container_id": "test-project-id",
            }
        }

        WatsonxLLMAdapter(model_name="ibm/slate-125m-english-rtrvr", **config)

        # Verify client was initialized with default enable_rate_limiting=False
        mock_watsonx_client.assert_called_once()
        call_kwargs = mock_watsonx_client.call_args.kwargs
        assert call_kwargs["enable_rate_limiting"] is False


@pytest.mark.unit
class TestWatsonxAdapterContainerKind:
    """Test container_kind validation (project and space)."""

    def test_init_with_project_container(self, *, mock_watsonx_client, mock_model_validator):
        """Test initialization with project container kind."""
        from docpipe.core.operators.functional.embeddings.adapters.outbound.watsonx_adapter import (
            WatsonxLLMAdapter,
        )

        config = {
            "provider_config": {
                "api_key": "test-api-key",
                "url": "https://us-south.ml.cloud.ibm.com",
                "container_kind": "project",
                "container_id": "test-project-id",
            }
        }

        adapter = WatsonxLLMAdapter(model_name="ibm/slate-125m-english-rtrvr", **config)

        assert adapter.container_kind == "project"
        assert adapter.container_id == "test-project-id"

    def test_init_with_space_container(self, *, mock_watsonx_client, mock_model_validator):
        """Test initialization with space container kind."""
        from docpipe.core.operators.functional.embeddings.adapters.outbound.watsonx_adapter import (
            WatsonxLLMAdapter,
        )

        config = {
            "provider_config": {
                "api_key": "test-api-key",
                "url": "https://us-south.ml.cloud.ibm.com",
                "container_kind": "space",
                "container_id": "test-space-id",
            }
        }

        adapter = WatsonxLLMAdapter(model_name="ibm/slate-125m-english-rtrvr", **config)

        assert adapter.container_kind == "space"
        assert adapter.container_id == "test-space-id"


@pytest.mark.unit
class TestWatsonxAdapterEmbeddings:
    """Test embedding generation methods."""

    def test_generate_embeddings(self, *, valid_config: dict[str, Any], mock_watsonx_client, mock_model_validator):
        """Test single text embedding generation."""
        from docpipe.core.operators.functional.embeddings.adapters.outbound.watsonx_adapter import (
            WatsonxLLMAdapter,
        )

        adapter = WatsonxLLMAdapter(model_name="ibm/slate-125m-english-rtrvr", **valid_config)

        result = adapter.generate_embeddings(text="test text")

        assert isinstance(result, list)
        assert len(result) == 768
        assert all(isinstance(x, float) for x in result)
        adapter.client.generate_embeddings.assert_called_once_with("test text")

    def test_generate_embeddings_batch(
        self, *, valid_config: dict[str, Any], mock_watsonx_client, mock_model_validator
    ):
        """Test batch embedding generation."""
        from docpipe.core.operators.functional.embeddings.adapters.outbound.watsonx_adapter import (
            WatsonxLLMAdapter,
        )

        adapter = WatsonxLLMAdapter(model_name="ibm/slate-125m-english-rtrvr", **valid_config)

        texts = ["text 1", "text 2"]
        result = adapter.generate_embeddings_batch(texts=texts)

        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(emb, list) for emb in result)
        adapter.client.generate_embeddings_batch.assert_called_once_with(texts)


@pytest.mark.unit
class TestWatsonxAdapterModelInfo:
    """Test model information methods."""

    def test_get_model_token_limit(self, *, valid_config: dict[str, Any], mock_watsonx_client, mock_model_validator):
        """Test getting model token limit."""
        from docpipe.core.operators.functional.embeddings.adapters.outbound.watsonx_adapter import (
            WatsonxLLMAdapter,
        )

        adapter = WatsonxLLMAdapter(model_name="ibm/slate-125m-english-rtrvr", **valid_config)

        # Mock the instance method _get_truncate_tokens to return 8192
        adapter.client._get_truncate_tokens = MagicMock(return_value=8192)

        token_limit = adapter.get_model_token_limit()

        assert token_limit == 8192
        adapter.client._get_truncate_tokens.assert_called_once()

    def test_get_embedding_dimension(self, *, valid_config: dict[str, Any], mock_watsonx_client, mock_model_validator):
        """Test getting embedding dimension."""
        from docpipe.core.operators.functional.embeddings.adapters.outbound.watsonx_adapter import (
            WatsonxLLMAdapter,
        )

        adapter = WatsonxLLMAdapter(model_name="ibm/slate-125m-english-rtrvr", **valid_config)

        dimension = adapter.get_embedding_dimension()

        assert dimension == 768
        mock_model_validator["dimension"].assert_called_once_with(
            model_id="ibm/slate-125m-english-rtrvr", api_key="test-api-key", url="https://us-south.ml.cloud.ibm.com"
        )

    def test_get_embedding_dimension_returns_none_for_zero(
        self, *, valid_config: dict[str, Any], mock_watsonx_client, mock_model_validator
    ):
        """Test that get_embedding_dimension returns None when dimension is 0."""
        from docpipe.core.operators.functional.embeddings.adapters.outbound.watsonx_adapter import (
            WatsonxLLMAdapter,
        )

        mock_model_validator["dimension"].return_value = 0

        adapter = WatsonxLLMAdapter(model_name="unknown-model", **valid_config)

        dimension = adapter.get_embedding_dimension()

        assert dimension is None


@pytest.mark.unit
class TestWatsonxAdapterFactoryIntegration:
    """Test adapter creation through factory."""

    def test_create_adapter_through_factory(
        self, *, valid_config: dict[str, Any], mock_watsonx_client, mock_model_validator
    ):
        """Test creating adapter instance through LLMAdapterFactory."""
        from docpipe.core.operators.functional.embeddings.adapters.outbound.factories.llm_adapter_factory import (
            LLMAdapterFactory,
        )

        adapter = LLMAdapterFactory.create(
            adapter_name="watsonx",
            model_name="ibm/slate-125m-english-rtrvr",
            **valid_config,
        )

        assert adapter is not None
        assert adapter.model_name == "ibm/slate-125m-english-rtrvr"
        assert hasattr(adapter, "generate_embeddings")
        assert hasattr(adapter, "generate_embeddings_batch")
