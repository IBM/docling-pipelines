# Copyright IBM Corp. 2025
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for PII/HAP adapter factory."""

import pytest

import core.operators.quality.pii_and_hap.adapters.outbound  # noqa: F401
from core.operators.quality.pii_and_hap.adapters.outbound.factories.pii_hap_adapter_factory import (
    PIIHAPAdapterFactory,
)
from core.operators.quality.pii_and_hap.adapters.outbound.ollama_adapter import (
    OllamaAdapter,
)
from core.operators.quality.pii_and_hap.adapters.outbound.litellm_adapter import (
    LiteLLMAdapter,
)
from core.operators.quality.pii_and_hap.adapters.outbound.watsonx_adapter import (
    WatsonXAdapter,
)


class TestPIIHAPAdapterFactory:
    """Test suite for PIIHAPAdapterFactory."""

    def test_create_ollama_adapter(self):
        """Test creating Ollama adapter."""
        adapter = PIIHAPAdapterFactory.create("ollama", model_name="granite4")

        assert isinstance(adapter, OllamaAdapter)

    def test_create_openai_adapter(self):
        """Test creating OpenAI adapter."""
        adapter = PIIHAPAdapterFactory.create(
            "litellm",
            model_name="gpt-4",
            base_url="http://localhost:8000/v1",
            api_key="test-key",  # pragma: allowlist secret
        )

        assert isinstance(adapter, LiteLLMAdapter)

    def test_create_watsonx_adapter(self):
        """Test creating WatsonX adapter."""
        adapter = PIIHAPAdapterFactory.create(
            "watsonx",
            api_key="test-api-key",  # pragma: allowlist secret
            url="https://us-south.ml.cloud.ibm.com",
            container_id="test-project-id",
            container_kind="project",
        )

        assert isinstance(adapter, WatsonXAdapter)

    def test_create_adapter_unknown_provider(self):
        """Test that unknown provider raises ValueError."""
        with pytest.raises(ValueError, match="Unknown PII/HAP detection adapter"):
            PIIHAPAdapterFactory.create("unknown_provider")

    def test_create_adapter_missing_required_config(self):
        """Test that missing required config raises TypeError."""
        with pytest.raises(TypeError):
            PIIHAPAdapterFactory.create("watsonx")  # Missing required params

    def test_list_adapters(self):
        """Test listing all registered adapters."""
        adapters = PIIHAPAdapterFactory.list_adapters()

        assert isinstance(adapters, list)
        assert "ollama" in adapters
        assert "litellm" in adapters
        assert "watsonx" in adapters

    def test_adapter_registry_contains_all_providers(self):
        """Test that adapter registry contains all expected providers."""
        expected_providers = ["ollama", "litellm", "watsonx"]

        for provider in expected_providers:
            assert provider in PIIHAPAdapterFactory._registry
