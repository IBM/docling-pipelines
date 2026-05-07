#!/usr/bin/env python3
"""
Unit tests for classification adapter factory.
Tests ClassificationAdapterFactory and adapter registration.
"""

from unittest.mock import patch

import pytest

from datasift.core.operators.quality.classification.adapters.outbound import (  # noqa: F401
    LiteLLMClassificationAdapter,
    OllamaClassificationAdapter,
    WatsonxClassificationAdapter,
)
from datasift.core.operators.quality.classification.adapters.outbound.factories.classification_adapter_factory import (
    ClassificationAdapterFactory,
)
from datasift.integrations.ollama.client import OllamaClient


@pytest.mark.unit
class TestClassificationAdapterFactory:
    """Test ClassificationAdapterFactory."""

    @patch.object(OllamaClient, "is_model_available", return_value=True)
    @patch.object(OllamaClient, "is_server_running", return_value=True)
    def test_create_ollama_adapter(self, mock_server, mock_model):
        """Test creating Ollama adapter."""
        adapter = ClassificationAdapterFactory.create(
            adapter_name="ollama",
            model_id="llama3.2",
        )

        assert adapter is not None
        assert hasattr(adapter, "classify_document")
        assert hasattr(adapter, "cleanup")
        assert adapter.ADAPTER_NAME == "ollama"

    def test_create_litellm_adapter(self):
        """Test creating LiteLLM adapter."""
        adapter = ClassificationAdapterFactory.create(
            adapter_name="litellm",
            model_id="gpt-4",
            api_key="",  # pragma: allowlist secret
        )

        assert adapter is not None
        assert hasattr(adapter, "classify_document")
        assert hasattr(adapter, "cleanup")
        assert adapter.ADAPTER_NAME == "litellm"

    def test_create_watsonx_adapter(self, monkeypatch):
        """Test creating Watsonx adapter."""
        # Set required environment variables
        monkeypatch.setenv("WATSONX_API_KEY", "test-key")
        monkeypatch.setenv("WATSONX_CONTAINER_ID", "test-project-id")

        adapter = ClassificationAdapterFactory.create(
            adapter_name="watsonx",
            model_id="ibm/granite-3-8b-instruct",
            api_base="https://us-south.ml.cloud.ibm.com",
            container_kind="project",
        )

        assert adapter is not None
        assert hasattr(adapter, "classify_document")
        assert hasattr(adapter, "cleanup")
        assert adapter.ADAPTER_NAME == "watsonx"

    def test_create_unsupported_adapter(self):
        """Test creating unsupported adapter raises error."""
        with pytest.raises(ValueError, match="Unknown classification adapter: 'unsupported_adapter'"):
            ClassificationAdapterFactory.create(
                adapter_name="unsupported_adapter",
                model_id="test-model",
            )

    def test_list_available_adapters(self):
        """Test listing available adapters."""
        adapters = ClassificationAdapterFactory.list_adapters()

        assert isinstance(adapters, list)
        assert len(adapters) >= 3  # At least ollama, litellm, watsonx
        assert "ollama" in adapters
        assert "litellm" in adapters
        assert "watsonx" in adapters

    @patch.object(OllamaClient, "is_model_available", return_value=True)
    @patch.object(OllamaClient, "is_server_running", return_value=True)
    def test_adapter_implements_port_interface(self, mock_server, mock_model):
        """Test that created adapters implement the port interface."""
        adapter = ClassificationAdapterFactory.create(
            adapter_name="ollama",
            model_id="llama3.2",
        )

        # Check that adapter has the required methods
        assert hasattr(adapter, "classify_document")
        assert hasattr(adapter, "cleanup")
        assert hasattr(adapter, "get_model_info")
        # Check adapter name
        assert adapter.ADAPTER_NAME == "ollama"

    @patch.object(OllamaClient, "is_model_available", return_value=True)
    @patch.object(OllamaClient, "is_server_running", return_value=True)
    def test_create_with_extra_kwargs(self, mock_server, mock_model):
        """Test creating adapter with extra kwargs (should be ignored)."""
        adapter = ClassificationAdapterFactory.create(
            adapter_name="ollama",
            model_id="llama3.2",
            extra_param="ignored",
            another_param=123,
        )

        assert adapter is not None
        assert adapter.ADAPTER_NAME == "ollama"


@pytest.mark.unit
class TestAdapterRegistration:
    """Test adapter registration decorator."""

    def test_register_classification_adapter_decorator(self):
        """Test that decorator registers adapters correctly."""
        # Check that existing adapters are registered
        adapters = ClassificationAdapterFactory.list_adapters()

        # Verify all expected adapters are registered
        assert "ollama" in adapters, "ollama adapter should be registered"
        assert "litellm" in adapters, "litellm adapter should be registered"
        assert "watsonx" in adapters, "watsonx adapter should be registered"

        # Verify we have exactly these three adapters
        assert len(adapters) == 3, f"Expected 3 adapters, found {len(adapters)}: {adapters}"
