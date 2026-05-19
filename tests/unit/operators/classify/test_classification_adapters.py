#!/usr/bin/env python3
"""
Unit tests for classification adapters.
Tests Ollama, LiteLLM, and Watsonx adapters with mocking.
"""

import json
from unittest.mock import Mock, patch

import pytest

from datasift.core.operators.quality.classification.adapters.outbound.litellm_adapter import (
    LiteLLMClassificationAdapter,
)
from datasift.core.operators.quality.classification.adapters.outbound.ollama_adapter import (
    OllamaClassificationAdapter,
)
from datasift.core.operators.quality.classification.adapters.outbound.watsonx_adapter import (
    WatsonxClassificationAdapter,
)
from datasift.core.operators.quality.classification.domain.models import ClassificationRequest
from datasift.exceptions.datasift_exceptions import DatasiftException


@pytest.mark.unit
class TestOllamaAdapter:
    """Test OllamaClassificationAdapter."""

    @patch("datasift.integrations.ollama.client.OllamaClient.is_model_available", return_value=True)
    @patch("datasift.integrations.ollama.client.OllamaClient.is_server_running", return_value=True)
    def test_init_success(self, mock_server_running, mock_model_available):
        """Test successful initialization."""
        adapter = OllamaClassificationAdapter(model_id="llama3.2")
        assert adapter.model_id == "llama3.2"
        assert adapter.ADAPTER_NAME == "ollama"

    @patch("datasift.integrations.ollama.client.OllamaClient.is_model_available")
    @patch("datasift.integrations.ollama.client.OllamaClient.is_server_running")
    def test_init_with_default_model(self, mock_server_running, mock_model_available):
        """Test initialization uses default model when not provided."""
        mock_server_running.return_value = True
        mock_model_available.return_value = True

        adapter = OllamaClassificationAdapter(model_id=None)
        assert adapter.model_id == "granite4:latest"  # DEFAULT_OLLAMA_MODEL
        assert adapter.ADAPTER_NAME == "ollama"

    @patch(
        "datasift.core.operators.quality.classification.adapters.outbound.ollama_adapter.OllamaClient.run",
        return_value=json.dumps(
            {
                "document_type": "invoice",
                "confidence": 9,
                "reasoning": "Contains line items and totals",
            }
        ),
    )
    @patch("datasift.integrations.ollama.client.OllamaClient.is_model_available", return_value=True)
    @patch("datasift.integrations.ollama.client.OllamaClient.is_server_running", return_value=True)
    def test_classify_document_success(self, mock_server_running, mock_model_available, mock_run):
        """Test successful document classification."""
        adapter = OllamaClassificationAdapter(model_id="llama3.2")
        request = ClassificationRequest(
            content="Invoice #12345\nTotal: $1000",
            document_types=["invoice", "receipt"],
            max_content_length=10000,
        )

        # Execute
        response = adapter.classify_document(request=request)

        # Verify
        assert response.success is True
        assert response.document_type == "invoice"
        assert response.confidence == 9
        assert response.reasoning == "Contains line items and totals"
        assert response.error is None

    @patch("datasift.core.operators.quality.classification.adapters.outbound.ollama_adapter.OllamaClient")
    @patch("datasift.integrations.ollama.client.OllamaClient.is_model_available")
    @patch("datasift.integrations.ollama.client.OllamaClient.is_server_running")
    def test_classify_document_json_error(self, mock_server_running, mock_model_available, mock_ollama_client_class):
        """Test handling of invalid JSON response."""
        # Setup validation mocks
        mock_server_running.return_value = True
        mock_model_available.return_value = True

        # Setup OllamaClient instance mock with invalid JSON
        mock_client_instance = Mock()
        mock_ollama_client_class.return_value = mock_client_instance
        mock_client_instance.run.return_value = "This is not valid JSON at all!"

        adapter = OllamaClassificationAdapter(model_id="llama3.2")
        request = ClassificationRequest(
            content="Test content",
            document_types=["invoice"],
            max_content_length=10000,
        )

        response = adapter.classify_document(request=request)

        assert response.success is False
        assert response.document_type == "unknown"
        assert response.error is not None
        assert "JSON" in response.error or "Invalid" in response.error or "parse" in response.error.lower()

    @patch("datasift.integrations.ollama.client.OllamaClient.is_model_available")
    @patch("datasift.integrations.ollama.client.OllamaClient.is_server_running")
    def test_cleanup(self, mock_server_running, mock_model_available):
        """Test cleanup method."""
        mock_server_running.return_value = True
        mock_model_available.return_value = True
        adapter = OllamaClassificationAdapter(model_id="llama3.2")
        adapter.cleanup()  # Should not raise


@pytest.mark.unit
class TestLiteLLMAdapter:
    """Test LiteLLMClassificationAdapter."""

    def test_init_success(self):
        """Test successful initialization."""
        adapter: LiteLLMClassificationAdapter = LiteLLMClassificationAdapter(
            model_id="gpt-4",
            api_key="",  # pragma: allowlist secret
        )
        assert adapter.model_id == "gpt-4"
        assert adapter.ADAPTER_NAME == "litellm"

    def test_init_with_api_base(self):
        """Test initialization with custom API base."""
        adapter = LiteLLMClassificationAdapter(
            model_id="openai/llama3",
            api_key="",  # pragma: allowlist secret
            api_base="http://localhost:11434/v1",
        )
        assert adapter.model_id == "openai/llama3"
        assert adapter.api_base == "http://localhost:11434/v1"

    def test_init_missing_model_id(self):
        """Test initialization fails without model_id."""
        with pytest.raises(ValueError, match="model_id is required"):
            LiteLLMClassificationAdapter(
                model_id=None,
                api_key="test-key",  # pragma: allowlist secret
            )

    @patch("datasift.integrations.litellm.client.LiteLLMLLMClient.chat")
    def test_classify_document_success(self, mock_chat):
        """Test successful document classification."""
        # Setup mock
        mock_chat.return_value = json.dumps(
            {
                "document_type": "invoice",
                "confidence": 8,
                "reasoning": "Contains invoice details",
            }
        )

        # Create adapter and request
        adapter: LiteLLMClassificationAdapter = LiteLLMClassificationAdapter(
            model_id="gpt-4",
            api_key="test-key",  # pragma: allowlist secret
        )
        request = ClassificationRequest(
            content="Invoice content",
            document_types=["invoice", "receipt"],
            max_content_length=10000,
        )

        # Execute
        response = adapter.classify_document(request=request)

        # Verify
        assert response.success is True
        assert response.document_type == "invoice"
        assert response.confidence == 8
        assert response.error is None

    @patch("datasift.integrations.litellm.client.LiteLLMLLMClient.chat")
    def test_classify_document_error_handling(self, mock_chat):
        """Test error handling when LLM returns invalid JSON."""
        # Setup mock to return invalid JSON
        mock_chat.return_value = "Not valid JSON"

        adapter: LiteLLMClassificationAdapter = LiteLLMClassificationAdapter(
            model_id="gpt-4",
            api_key="test-key",  # pragma: allowlist secret
        )
        request = ClassificationRequest(
            content="Test content",
            document_types=["invoice", "receipt"],
            max_content_length=10000,
        )

        response = adapter.classify_document(request=request)

        # Verify error response
        assert response.success is False, f"Expected success=False, got {response.success}"
        assert response.document_type == "unknown"
        assert response.confidence == 0
        assert response.error is not None
        assert "Invalid JSON response" in response.error


@pytest.mark.unit
class TestWatsonxAdapter:
    """Test WatsonxClassificationAdapter."""

    def test_init_success(self, monkeypatch):
        """Test successful initialization."""
        # Set required environment variables
        monkeypatch.setenv("WATSONX_API_KEY", "test-key")
        monkeypatch.setenv("WATSONX_CONTAINER_ID", "test-project-id")

        adapter = WatsonxClassificationAdapter(
            model_id="ibm/granite-3-8b-instruct",
            api_base="https://us-south.ml.cloud.ibm.com",
            container_kind="project",
        )
        assert adapter.model_id == "ibm/granite-3-8b-instruct"
        assert adapter.api_base == "https://us-south.ml.cloud.ibm.com"
        assert adapter.ADAPTER_NAME == "watsonx"

    def test_init_missing_parameters(self, monkeypatch):
        """Test initialization fails without required parameters."""
        # Set required environment variables
        monkeypatch.setenv("WATSONX_API_KEY", "test-key")
        monkeypatch.setenv("WATSONX_CONTAINER_ID", "test-project-id")

        with pytest.raises(DatasiftException, match="model_id is required"):
            WatsonxClassificationAdapter(
                model_id=None,
                api_base="https://us-south.ml.cloud.ibm.com",
                container_kind="project",
            )

        with pytest.raises(DatasiftException, match="container_kind is required"):
            WatsonxClassificationAdapter(
                model_id="ibm/granite-3-8b-instruct",
                api_base="https://us-south.ml.cloud.ibm.com",
                container_kind=None,
            )

    @patch("datasift.utils.infrastructure.iam_token_manager.IAMTokenManager.get_token")
    @patch("datasift.integrations.rest_client.RestClient.call_rest_json")
    def test_classify_document_success(self, mock_call_rest_json, mock_get_token, monkeypatch):
        """Test successful document classification."""
        # Set required environment variables
        monkeypatch.setenv("WATSONX_API_KEY", "test-key")
        monkeypatch.setenv("WATSONX_CONTAINER_ID", "test-project-id")

        # Mock IAM token
        mock_get_token.return_value = "mock-token"

        # Mock classification response
        mock_call_rest_json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "document_type": "contract",
                                "confidence": 9,
                                "reasoning": "Legal agreement terms",
                            }
                        )
                    }
                }
            ]
        }

        # Create adapter and request
        adapter: WatsonxClassificationAdapter = WatsonxClassificationAdapter(
            model_id="ibm/granite-3-8b-instruct",
            api_base="https://us-south.ml.cloud.ibm.com",
            container_kind="project",
        )
        request = ClassificationRequest(
            content="Contract content",
            document_types=["invoice", "contract"],
            max_content_length=10000,
        )

        # Execute
        response = adapter.classify_document(request=request)

        # Verify
        assert response.success is True
        assert response.document_type == "contract"
        assert response.confidence == 9
        assert response.error is None

    def test_get_model_info(self, monkeypatch):
        """Test get_model_info method."""
        # Set required environment variables
        monkeypatch.setenv("WATSONX_API_KEY", "test-key")
        monkeypatch.setenv("WATSONX_CONTAINER_ID", "test-project-id")

        adapter: WatsonxClassificationAdapter = WatsonxClassificationAdapter(
            model_id="ibm/granite-3-8b-instruct",
            api_base="https://us-south.ml.cloud.ibm.com",
            container_kind="project",
        )

        info = adapter.get_model_info()

        assert info["model_id"] == "ibm/granite-3-8b-instruct"
        assert info["adapter"] == "watsonx"
        assert info["api_base"] == "https://us-south.ml.cloud.ibm.com"
