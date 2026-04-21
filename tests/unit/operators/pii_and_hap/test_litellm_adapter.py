# Copyright IBM Corp. 2025
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for LiteLLM PII/HAP adapter."""

import pytest
from unittest.mock import patch

import core.operators.quality.pii_and_hap.adapters.outbound  # noqa: F401
from core.operators.quality.pii_and_hap.adapters.outbound.litellm_adapter import (
    LiteLLMAdapter,
)
from common.exceptions.datasift_exceptions import DatasiftException


class TestLiteLLMAdapter:
    """Test suite for LiteLLM adapter."""

    @pytest.fixture
    def sample_payload(self):
        """Provide sample detection payload."""
        return {
            "input": "My email is john@example.com and phone is 555-1234",
            "detectors": {"pii": {"threshold": 0.5}, "hap": {"threshold": 0.8}},
        }

    @pytest.fixture
    def sample_detection_response(self):
        """Provide sample detection response."""
        return {
            "detections": [
                {
                    "detection": "email",
                    "detection_type": "pii",
                    "score": 0.95,
                    "start": 12,
                    "end": 29,
                    "text": "john@example.com",
                }
            ]
        }

    def test_adapter_initialization_with_model_name(self):
        """Test LiteLLM adapter initialization with model name."""
        adapter = LiteLLMAdapter(model_name="gpt-4")

        assert adapter.model_name == "gpt-4"
        assert adapter.api_key is None
        assert adapter.api_base is None

    def test_adapter_initialization_with_all_params(self):
        """Test LiteLLM adapter initialization with all parameters."""
        adapter = LiteLLMAdapter(
            model_name="gpt-4",
            api_key="test-key",  # pragma: allowlist secret
            api_base="https://api.openai.com/v1",
        )

        assert adapter.model_name == "gpt-4"
        assert adapter.api_key == "test-key"  # pragma: allowlist secret
        assert adapter.api_base == "https://api.openai.com/v1"

    def test_adapter_initialization_missing_model_name(self):
        """Test that missing model name raises ValueError."""
        with pytest.raises(ValueError, match="model_name is required"):
            LiteLLMAdapter(model_name="")

    def test_adapter_initialization_with_extra_config(self):
        """Test adapter initialization with extra configuration."""
        adapter = LiteLLMAdapter(
            model_name="gpt-4",
            temperature=0.7,
            max_tokens=1000,
        )

        assert adapter.model_name == "gpt-4"
        assert "temperature" in adapter.adapter_config
        assert adapter.adapter_config["temperature"] == 0.7

    @patch(
        "core.operators.quality.pii_and_hap.adapters.outbound.litellm_adapter.detect_pii_hap_litellm"
    )
    def test_detect_pii_hap_success(
        self, mock_detect, sample_payload, sample_detection_response
    ):
        """Test successful PII/HAP detection."""
        mock_detect.return_value = sample_detection_response

        adapter = LiteLLMAdapter(model_name="gpt-4")
        result = adapter.detect_pii_hap(sample_payload)

        assert result is not None
        assert hasattr(result, "detections")
        assert len(result.detections) == 1
        assert result.detections[0].detection == "email"
        assert result.detections[0].score == 0.95
        assert result.input_text == sample_payload["input"]

        # Verify the function was called with correct parameters
        mock_detect.assert_called_once_with(
            request_data=sample_payload,
            model_name="gpt-4",
            api_key=None,
            api_base=None,
        )

    @patch(
        "core.operators.quality.pii_and_hap.adapters.outbound.litellm_adapter.detect_pii_hap_litellm"
    )
    def test_detect_pii_hap_with_api_key(
        self, mock_detect, sample_payload, sample_detection_response
    ):
        """Test PII/HAP detection with API key."""
        mock_detect.return_value = sample_detection_response

        adapter = LiteLLMAdapter(
            model_name="gpt-4",
            api_key="test-key",  # pragma: allowlist secret
        )
        result = adapter.detect_pii_hap(sample_payload)

        assert result is not None
        mock_detect.assert_called_once_with(
            request_data=sample_payload,
            model_name="gpt-4",
            api_key="test-key",  # pragma: allowlist secret
            api_base=None,
        )

    @patch(
        "core.operators.quality.pii_and_hap.adapters.outbound.litellm_adapter.detect_pii_hap_litellm"
    )
    def test_detect_pii_hap_with_custom_base_url(
        self, mock_detect, sample_payload, sample_detection_response
    ):
        """Test PII/HAP detection with custom base URL."""
        mock_detect.return_value = sample_detection_response

        adapter = LiteLLMAdapter(
            model_name="gpt-4",
            api_base="https://custom.api.com/v1",
        )
        result = adapter.detect_pii_hap(sample_payload)

        assert result is not None
        # Verify the function was called with correct parameters
        call_kwargs = mock_detect.call_args.kwargs
        assert call_kwargs["model_name"] == "gpt-4"
        assert call_kwargs["api_base"] == "https://custom.api.com/v1"

    def test_detect_pii_hap_empty_input(self):
        """Test that empty input raises ValueError."""
        adapter = LiteLLMAdapter(model_name="gpt-4")

        with pytest.raises(ValueError, match="Input text cannot be empty"):
            adapter.detect_pii_hap({"input": "", "detectors": {}})

    @patch(
        "core.operators.quality.pii_and_hap.adapters.outbound.litellm_adapter.detect_pii_hap_litellm"
    )
    def test_detect_pii_hap_empty_detections(self, mock_detect, sample_payload):
        """Test handling of empty detections list."""
        mock_detect.return_value = {"detections": []}

        adapter = LiteLLMAdapter(model_name="gpt-4")
        result = adapter.detect_pii_hap(sample_payload)

        assert result is not None
        assert len(result.detections) == 0

    @patch(
        "core.operators.quality.pii_and_hap.adapters.outbound.litellm_adapter.detect_pii_hap_litellm"
    )
    def test_detect_pii_hap_multiple_detections(self, mock_detect, sample_payload):
        """Test handling of multiple detections."""
        mock_detect.return_value = {
            "detections": [
                {
                    "detection": "email",
                    "detection_type": "pii",
                    "score": 0.95,
                    "start": 12,
                    "end": 29,
                    "text": "john@example.com",
                },
                {
                    "detection": "phone",
                    "detection_type": "pii",
                    "score": 0.88,
                    "start": 44,
                    "end": 52,
                    "text": "555-1234",
                },
            ]
        }

        adapter = LiteLLMAdapter(model_name="gpt-4")
        result = adapter.detect_pii_hap(sample_payload)

        assert result is not None
        assert len(result.detections) == 2
        assert result.detections[0].detection == "email"
        assert result.detections[1].detection == "phone"

    @patch(
        "core.operators.quality.pii_and_hap.adapters.outbound.litellm_adapter.detect_pii_hap_litellm"
    )
    def test_detect_pii_hap_api_error(self, mock_detect, sample_payload):
        """Test that API errors are properly propagated."""
        mock_detect.side_effect = DatasiftException(
            message="LiteLLM API call failed", status_code=500
        )

        adapter = LiteLLMAdapter(model_name="gpt-4")

        with pytest.raises(DatasiftException, match="LiteLLM API call failed"):
            adapter.detect_pii_hap(sample_payload)

    @patch(
        "core.operators.quality.pii_and_hap.adapters.outbound.litellm_adapter.detect_pii_hap_litellm"
    )
    def test_detect_pii_hap_with_adapter_config(
        self, mock_detect, sample_payload, sample_detection_response
    ):
        """Test detection with additional adapter configuration."""
        mock_detect.return_value = sample_detection_response

        adapter = LiteLLMAdapter(
            model_name="gpt-4",
            temperature=0.5,
            max_tokens=2000,
        )
        result = adapter.detect_pii_hap(sample_payload)

        assert result is not None
        # Verify extra config is passed through
        call_kwargs = mock_detect.call_args.kwargs
        assert "temperature" in call_kwargs
        assert call_kwargs["temperature"] == 0.5

    def test_cleanup(self):
        """Test adapter cleanup method."""
        adapter = LiteLLMAdapter(model_name="gpt-4")
        adapter.cleanup()  # Should not raise any exception

    def test_adapter_name_constant(self):
        """Test that adapter name constant is correct."""
        assert LiteLLMAdapter.ADAPTER_NAME == "litellm"

    def test_adapter_display_name_constant(self):
        """Test that adapter display name constant is correct."""
        assert LiteLLMAdapter.ADAPTER_DISPLAY_NAME == "LiteLLM (Multi-Provider)"

    @patch(
        "core.operators.quality.pii_and_hap.adapters.outbound.litellm_adapter.detect_pii_hap_litellm"
    )
    def test_detect_pii_hap_anthropic_model(
        self, mock_detect, sample_payload, sample_detection_response
    ):
        """Test detection with Anthropic model."""
        mock_detect.return_value = sample_detection_response

        adapter = LiteLLMAdapter(model_name="claude-3-opus-20240229")
        result = adapter.detect_pii_hap(sample_payload)

        assert result is not None
        mock_detect.assert_called_once()
        assert mock_detect.call_args.kwargs["model_name"] == "claude-3-opus-20240229"

    @patch(
        "core.operators.quality.pii_and_hap.adapters.outbound.litellm_adapter.detect_pii_hap_litellm"
    )
    def test_detect_pii_hap_azure_model(
        self, mock_detect, sample_payload, sample_detection_response
    ):
        """Test detection with Azure OpenAI model."""
        mock_detect.return_value = sample_detection_response

        adapter = LiteLLMAdapter(
            model_name="azure/gpt-4-deployment",
            api_key="azure-key",  # pragma: allowlist secret
        )
        result = adapter.detect_pii_hap(sample_payload)

        assert result is not None
        mock_detect.assert_called_once()
        assert mock_detect.call_args.kwargs["model_name"] == "azure/gpt-4-deployment"
