# Copyright IBM Corp. 2025
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for WatsonX PII/HAP adapter."""

import pytest
from unittest.mock import patch

import core.operators.quality.pii_and_hap.adapters.outbound  # noqa: F401
from core.operators.quality.pii_and_hap.adapters.outbound.watsonx_adapter import (
    WatsonXAdapter,
)
from common.exceptions.datasift_exceptions import (
    DatasiftException,
    ExternalServiceError,
)


class TestWatsonXAdapter:
    """Test suite for WatsonX adapter."""

    @pytest.fixture
    def adapter_config(self):
        """Provide sample configuration for WatsonX adapter."""
        return {
            "api_key": "test-api-key",  # pragma: allowlist secret
            "url": "https://us-south.ml.cloud.ibm.com",
            "container_id": "test-project-id",
            "container_kind": "project",
            "timeout": 300,
        }

    @pytest.fixture
    def sample_payload(self):
        """Provide sample detection payload."""
        return {
            "input": "My email is john@example.com and phone is 555-1234",
            "detectors": {"pii": {"threshold": 0.5}, "hap": {"threshold": 0.8}},
        }

    def test_adapter_initialization(self, adapter_config):
        """Test WatsonX adapter initialization."""
        adapter = WatsonXAdapter(**adapter_config)

        assert adapter.api_key == "test-api-key"  # pragma: allowlist secret
        assert adapter.url == "https://us-south.ml.cloud.ibm.com"
        assert adapter.container_id == "test-project-id"
        assert adapter.container_kind == "project"
        assert adapter.timeout == 300

    def test_adapter_initialization_missing_api_key(self):
        """Test that missing API key raises ValueError."""
        with pytest.raises(ValueError, match="WatsonX API key is required"):
            WatsonXAdapter(
                api_key="",  # pragma: allowlist secret
                url="https://test.com",
                container_id="test",
                container_kind="project",
            )

    def test_adapter_initialization_missing_url(self):
        """Test that missing URL raises ValueError."""
        with pytest.raises(ValueError, match="WatsonX URL is required"):
            WatsonXAdapter(
                api_key="test-key",  # pragma: allowlist secret
                url="",
                container_id="test",
                container_kind="project",
            )

    @patch(
        "core.operators.quality.pii_and_hap.adapters.outbound.watsonx_adapter.WatsonxPipelineOptionsProvider._get_iam_access_token"
    )
    @patch(
        "core.operators.quality.pii_and_hap.adapters.outbound.watsonx_adapter.RestClient.call_rest_json"
    )
    def test_detect_pii_hap_success(
        self, mock_call_rest, mock_get_token, adapter_config, sample_payload
    ):
        """Test successful PII/HAP detection."""
        # Mock IAM token
        mock_get_token.return_value = "test-access-token"  # pragma: allowlist secret

        # Mock API response
        mock_call_rest.return_value = {
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

        adapter = WatsonXAdapter(**adapter_config)
        result = adapter.detect_pii_hap(sample_payload)

        assert result is not None
        assert hasattr(result, "detections")
        assert len(result.detections) == 1
        assert result.detections[0].detection == "email"
        assert result.detections[0].score == 0.95

    @patch(
        "core.operators.quality.pii_and_hap.adapters.outbound.watsonx_adapter.WatsonxPipelineOptionsProvider._get_iam_access_token"
    )
    @patch(
        "core.operators.quality.pii_and_hap.adapters.outbound.watsonx_adapter.RestClient.call_rest_json"
    )
    def test_detect_pii_hap_empty_input(
        self, mock_call_rest, mock_get_token, adapter_config
    ):
        """Test that empty input raises ValueError."""
        adapter = WatsonXAdapter(**adapter_config)

        with pytest.raises(ValueError, match="Input text cannot be empty"):
            adapter.detect_pii_hap({"input": "", "detectors": {}})

    @patch(
        "core.operators.quality.pii_and_hap.adapters.outbound.watsonx_adapter.WatsonxPipelineOptionsProvider._get_iam_access_token"
    )
    @patch(
        "core.operators.quality.pii_and_hap.adapters.outbound.watsonx_adapter.RestClient.call_rest_json"
    )
    def test_detect_pii_hap_api_error(
        self, mock_call_rest, mock_get_token, adapter_config, sample_payload
    ):
        """Test that API errors are properly handled."""
        mock_get_token.return_value = "test-access-token"  # pragma: allowlist secret

        # Simulate ExternalServiceError from RestClient
        mock_call_rest.side_effect = ExternalServiceError(
            message="API call failed", status_code=500
        )

        adapter = WatsonXAdapter(**adapter_config)

        with pytest.raises(
            DatasiftException, match="Failed to call WatsonX detection API"
        ):
            adapter.detect_pii_hap(sample_payload)

    def test_cleanup(self, adapter_config):
        """Test adapter cleanup method."""
        adapter = WatsonXAdapter(**adapter_config)
        adapter.cleanup()  # Should not raise any exception
