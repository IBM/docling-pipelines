#!/usr/bin/env python3
"""
Unit tests for simplified classification service.
Tests ClassificationService with both watsonx and litellm providers.
"""

import json
from unittest.mock import Mock, patch

import pytest

from docpipe.core.constants.constants import LLMConstants
from docpipe.core.operators.quality.classification.classification_service import ClassificationService
from docpipe.core.operators.quality.classification.domain.models import ClassificationRequest
from docpipe.exceptions.docpipe_exceptions import DocpipeException


@pytest.mark.unit
class TestClassificationService:
    """Test simplified classification service."""

    def test_init_with_litellm(self):
        """Test successful initialization with litellm provider."""
        service = ClassificationService(
            model_id="openai/llama3.2:latest",
            provider_name="litellm",
            provider_config={
                "api_base": "http://localhost:11434/v1",
                "api_key": "<ollama>",  # pragma: allowlist secret
            },
        )
        assert service.model_id == "openai/llama3.2:latest"
        model_info = service.get_model_info()
        assert model_info["provider"] == "litellm"

    def test_init_with_watsonx(self, monkeypatch):
        """Test successful initialization with watsonx provider."""
        # Set required environment variables
        monkeypatch.setenv("WATSONX_API_KEY", "test-key")
        monkeypatch.setenv("WATSONX_CONTAINER_ID", "test-project-id")

        service = ClassificationService(
            model_id="ibm/granite-3-8b-instruct",
            provider_name="watsonx",
            provider_config={
                "api_base": "https://us-south.ml.cloud.ibm.com",
                "container_kind": "project",
            },
        )
        assert service.model_id == "ibm/granite-3-8b-instruct"
        model_info = service.get_model_info()
        assert model_info["provider"] == "watsonx"

    def test_init_missing_model_id(self):
        """Test initialization fails without model_id when using factory path."""
        with pytest.raises(DocpipeException, match="model_id"):
            ClassificationService(
                model_id=None,
                provider_name="litellm",
            )

    def test_init_unsupported_provider(self):
        """Test initialization fails with unsupported provider."""
        with pytest.raises(DocpipeException, match=r"Unsupported provider.*ollama"):
            ClassificationService(
                model_id="test-model",
                provider_name="ollama",
            )

    def test_init_invalid_provider(self):
        """Test initialization fails with invalid provider."""
        with pytest.raises(DocpipeException, match="Unsupported provider"):
            ClassificationService(
                model_id="test-model",
                provider_name="invalid_provider",
            )

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_inference_adapter")
    def test_classify_document_success_litellm(self, mock_create_adapter):
        """Test successful document classification with litellm."""
        # Setup mock LLM adapter
        mock_llm_adapter = Mock()
        mock_llm_adapter.chat.return_value = json.dumps(
            {
                "document_type": "invoice",
                "confidence": 9,
                "reasoning": "Contains invoice details",
            }
        )
        mock_llm_adapter.validate.return_value = {
            LLMConstants.ValidationKeys.VALID: True,
            LLMConstants.ValidationKeys.CONTEXT: LLMConstants.ValidationContexts.INFERENCE,
            LLMConstants.ValidationKeys.ERRORS: [],
            LLMConstants.ValidationKeys.WARNINGS: [],
        }
        mock_create_adapter.return_value = mock_llm_adapter

        # Create service and request
        service = ClassificationService(
            model_id="openai/llama3",
            provider_name="litellm",
            provider_config={
                "api_base": "http://localhost:11434/v1",
                "api_key": "<ollama>",  # pragma: allowlist secret
            },
        )
        request = ClassificationRequest(
            content="Invoice content",
            document_types=["invoice", "receipt"],
            max_content_length=10000,
        )

        # Execute
        response = service.classify_document(request=request)

        # Verify
        assert response.success is True
        assert response.document_type == "invoice"
        assert response.confidence == 9
        assert response.reasoning == "Contains invoice details"
        assert response.error is None

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_inference_adapter")
    def test_classify_document_success_watsonx(self, mock_create_adapter, monkeypatch):
        """Test successful document classification with watsonx."""
        # Set required environment variables
        monkeypatch.setenv("WATSONX_API_KEY", "test-key")
        monkeypatch.setenv("WATSONX_CONTAINER_ID", "test-project-id")

        # Setup mock LLM adapter
        mock_llm_adapter = Mock()
        mock_llm_adapter.chat.return_value = json.dumps(
            {
                "document_type": "contract",
                "confidence": 8,
                "reasoning": "Legal agreement terms",
            }
        )
        mock_llm_adapter.validate.return_value = {
            LLMConstants.ValidationKeys.VALID: True,
            LLMConstants.ValidationKeys.CONTEXT: LLMConstants.ValidationContexts.INFERENCE,
            LLMConstants.ValidationKeys.ERRORS: [],
            LLMConstants.ValidationKeys.WARNINGS: [],
        }
        mock_create_adapter.return_value = mock_llm_adapter

        # Create service and request
        service = ClassificationService(
            model_id="ibm/granite-3-8b-instruct",
            provider_name="watsonx",
            provider_config={
                "api_base": "https://us-south.ml.cloud.ibm.com",
                "container_kind": "project",
            },
        )
        request = ClassificationRequest(
            content="Contract content",
            document_types=["invoice", "contract"],
            max_content_length=10000,
        )

        # Execute
        response = service.classify_document(request=request)

        # Verify
        assert response.success is True
        assert response.document_type == "contract"
        assert response.confidence == 8
        assert response.error is None

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_inference_adapter")
    def test_classify_document_invalid_json(self, mock_create_adapter):
        """Test handling of invalid JSON response."""
        # Setup mock to return invalid JSON
        mock_llm_adapter = Mock()
        mock_llm_adapter.chat.return_value = "Not valid JSON"
        mock_llm_adapter.validate.return_value = {
            LLMConstants.ValidationKeys.VALID: True,
            LLMConstants.ValidationKeys.CONTEXT: LLMConstants.ValidationContexts.INFERENCE,
            LLMConstants.ValidationKeys.ERRORS: [],
            LLMConstants.ValidationKeys.WARNINGS: [],
        }
        mock_create_adapter.return_value = mock_llm_adapter

        service = ClassificationService(
            model_id="openai/llama3",
            provider_name="litellm",
            provider_config={
                "api_base": "http://localhost:11434/v1",
                "api_key": "<ollama>",  # pragma: allowlist secret
            },
        )
        request = ClassificationRequest(
            content="Test content",
            document_types=["invoice", "receipt"],
            max_content_length=10000,
        )

        response = service.classify_document(request=request)

        # Verify error response
        assert response.success is False
        assert response.document_type == "unknown"
        assert response.confidence == 0
        assert response.error is not None
        assert "Invalid JSON response" in response.error

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_inference_adapter")
    def test_classify_document_missing_fields(self, mock_create_adapter):
        """Test handling of response with missing required fields."""
        # Setup mock to return JSON without required fields
        mock_llm_adapter = Mock()
        mock_llm_adapter.chat.return_value = json.dumps({"some_field": "value"})
        mock_llm_adapter.validate.return_value = {
            LLMConstants.ValidationKeys.VALID: True,
            LLMConstants.ValidationKeys.CONTEXT: LLMConstants.ValidationContexts.INFERENCE,
            LLMConstants.ValidationKeys.ERRORS: [],
            LLMConstants.ValidationKeys.WARNINGS: [],
        }
        mock_create_adapter.return_value = mock_llm_adapter

        service = ClassificationService(
            model_id="openai/llama3",
            provider_name="litellm",
            provider_config={
                "api_base": "http://localhost:11434/v1",
                "api_key": "<ollama>",  # pragma: allowlist secret
            },
        )
        request = ClassificationRequest(
            content="Test content",
            document_types=["invoice"],
            max_content_length=10000,
        )

        response = service.classify_document(request=request)

        # Verify error response
        assert response.success is False
        assert response.document_type == "unknown"
        assert response.error is not None

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_inference_adapter")
    def test_classify_document_embedded_json(self, mock_create_adapter):
        """Test extraction of JSON from text response."""
        # Setup mock to return JSON embedded in text
        mock_llm_adapter = Mock()
        mock_llm_adapter.chat.return_value = (
            'Here is the result: {"document_type": "report", "confidence": 7, "reasoning": "test"}'
        )
        mock_llm_adapter.validate.return_value = {
            LLMConstants.ValidationKeys.VALID: True,
            LLMConstants.ValidationKeys.CONTEXT: LLMConstants.ValidationContexts.INFERENCE,
            LLMConstants.ValidationKeys.ERRORS: [],
            LLMConstants.ValidationKeys.WARNINGS: [],
        }
        mock_create_adapter.return_value = mock_llm_adapter

        service = ClassificationService(
            model_id="openai/llama3",
            provider_name="litellm",
            provider_config={
                "api_base": "http://localhost:11434/v1",
                "api_key": "<ollama>",  # pragma: allowlist secret
            },
        )
        request = ClassificationRequest(
            content="Test content",
            document_types=["report"],
            max_content_length=10000,
        )

        response = service.classify_document(request=request)

        # Verify successful extraction
        assert response.success is True
        assert response.document_type == "report"
        assert response.confidence == 7

    def test_get_model_info_litellm(self):
        """Test get_model_info method with litellm."""
        service = ClassificationService(
            model_id="openai/llama3",
            provider_name="litellm",
            provider_config={
                "api_base": "http://localhost:11434/v1",
                "api_key": "<ollama>",  # pragma: allowlist secret
            },
            temperature=0.5,
            max_tokens=1000,
        )

        info = service.get_model_info()

        assert info["model_id"] == "openai/llama3"
        assert info["provider"] == "litellm"
        assert info["temperature"] == 0.5
        assert info["max_tokens"] == 1000

    def test_get_model_info_watsonx(self, monkeypatch):
        """Test get_model_info method with watsonx."""
        # Set required environment variables
        monkeypatch.setenv("WATSONX_API_KEY", "test-key")
        monkeypatch.setenv("WATSONX_CONTAINER_ID", "test-project-id")

        service = ClassificationService(
            model_id="ibm/granite-3-8b-instruct",
            provider_name="watsonx",
            provider_config={
                "api_base": "https://us-south.ml.cloud.ibm.com",
                "container_kind": "project",
            },
        )

        info = service.get_model_info()

        assert info["model_id"] == "ibm/granite-3-8b-instruct"
        assert info["provider"] == "watsonx"

    def test_cleanup(self):
        """Test cleanup method."""
        service = ClassificationService(
            model_id="openai/llama3",
            provider_name="litellm",
            provider_config={
                "api_base": "http://localhost:11434/v1",
                "api_key": "<ollama>",  # pragma: allowlist secret
            },
        )
        service.cleanup()  # Should not raise

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_inference_adapter")
    def test_adapter_validation_called_on_init(self, mock_create_adapter):
        """Test that adapter validation is called during service initialization."""
        # Setup mock adapter with validate method
        mock_llm_adapter = Mock()
        mock_llm_adapter.validate.return_value = {
            "valid": True,
            "context": "inference",
            "provider": "ollama",
            "errors": [],
            "warnings": [],
        }
        mock_create_adapter.return_value = mock_llm_adapter

        # Create service
        service = ClassificationService(
            model_id="openai/llama3",
            provider_name="litellm",
            provider_config={
                "api_base": "http://localhost:11434/v1",
                "api_key": "<ollama>",  # pragma: allowlist secret
            },
        )

        # Verify validate was called
        mock_llm_adapter.validate.assert_called_once()
        assert service.model_id == "openai/llama3"

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_inference_adapter")
    def test_adapter_validation_failure_raises_error(self, mock_create_adapter):
        """Test that adapter validation failure raises DocpipeException."""
        # Setup mock adapter with failing validation
        mock_llm_adapter = Mock()
        mock_llm_adapter.validate.return_value = {
            "valid": False,
            "context": "inference",
            "provider": "ollama",
            "errors": ["API key validation failed: Missing API key"],
            "warnings": [],
        }
        mock_create_adapter.return_value = mock_llm_adapter

        # Attempt to create service should raise exception
        with pytest.raises(DocpipeException, match="Adapter validation failed"):
            ClassificationService(
                model_id="openai/llama3",
                provider_name="litellm",
                provider_config={
                    "api_base": "http://localhost:11434/v1",
                },
            )

    @patch("docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory.create_inference_adapter")
    def test_adapter_validation_with_warnings(self, mock_create_adapter):
        """Test that adapter validation with warnings still succeeds."""
        # Setup mock adapter with warnings
        mock_llm_adapter = Mock()
        mock_llm_adapter.validate.return_value = {
            "valid": True,
            "context": "inference",
            "provider": "ollama",
            "errors": [],
            "warnings": [
                "Ollama typically requires api_base. If you encounter connection issues, ensure api_base is configured."
            ],
        }
        mock_create_adapter.return_value = mock_llm_adapter

        # Create service - should succeed despite warnings
        service = ClassificationService(
            model_id="openai/llama3",
            provider_name="litellm",
            provider_config={
                "api_key": "<ollama>",  # pragma: allowlist secret
            },
        )

        # Verify validate was called and service was created successfully
        mock_llm_adapter.validate.assert_called_once()
        assert service.model_id == "openai/llama3"


@pytest.mark.unit
class TestClassificationServiceProviderInjection:
    """Tests for DocumentClassProvider and llm_adapter injection into ClassificationService."""

    def test_defaults_to_static_provider_when_none_given(self):
        """When no document_class_provider is given, StaticDocumentClassProvider is used."""
        from docpipe.core.ports.document_class_provider import StaticDocumentClassProvider

        mock_adapter = Mock()
        mock_adapter.validate.return_value = {"valid": True, "errors": [], "warnings": []}

        service = ClassificationService(llm_adapter=mock_adapter)

        assert isinstance(service.document_class_provider, StaticDocumentClassProvider)

    def test_stores_injected_document_class_provider(self):
        """An explicitly injected document_class_provider is stored on the service."""
        from unittest.mock import MagicMock

        from docpipe.core.ports.document_class_provider import DocumentClassProvider

        mock_adapter = Mock()
        mock_adapter.validate.return_value = {"valid": True, "errors": [], "warnings": []}
        custom_provider = MagicMock(spec=DocumentClassProvider)

        service = ClassificationService(llm_adapter=mock_adapter, document_class_provider=custom_provider)

        assert service.document_class_provider is custom_provider

    @patch("docpipe.core.operators.quality.classification.classification_service.LLMAdapterFactory")
    def test_injected_llm_adapter_bypasses_factory(self, mock_factory):
        """When llm_adapter is provided, LLMAdapterFactory.create_inference_adapter is not called."""
        mock_adapter = Mock()
        mock_adapter.validate.return_value = {"valid": True, "errors": [], "warnings": []}

        ClassificationService(llm_adapter=mock_adapter)

        mock_factory.create_inference_adapter.assert_not_called()

    def test_injected_adapter_is_used_as_llm_adapter(self):
        """The injected llm_adapter is stored as service.llm_adapter."""
        mock_adapter = Mock()
        mock_adapter.validate.return_value = {"valid": True, "errors": [], "warnings": []}

        service = ClassificationService(llm_adapter=mock_adapter)

        assert service.llm_adapter is mock_adapter

    def test_injected_adapter_model_id_and_provider_stored(self):
        """Optional model_id and provider_name are stored for reference when adapter is injected."""
        mock_adapter = Mock()
        mock_adapter.validate.return_value = {"valid": True, "errors": [], "warnings": []}

        service = ClassificationService(llm_adapter=mock_adapter, model_id="my-model", provider_name="gateway")

        assert service.model_id == "my-model"
        assert service.provider_name == "gateway"

    def test_injected_adapter_defaults_empty_model_id_and_provider(self):
        """model_id and provider_name default to empty string when adapter is injected without them."""
        mock_adapter = Mock()
        mock_adapter.validate.return_value = {"valid": True, "errors": [], "warnings": []}

        service = ClassificationService(llm_adapter=mock_adapter)

        assert service.model_id == ""
        assert service.provider_name == ""

    def test_factory_path_requires_provider_name(self):
        """Without llm_adapter, a missing provider_name raises DocpipeException."""
        with pytest.raises(DocpipeException, match="provider"):
            ClassificationService(model_id="some-model")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
