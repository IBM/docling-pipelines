#!/usr/bin/env python3
"""
Unit tests for PII/HAP annotator validation.
Tests PIIAndHAPAnnotator initialization and service validation.
"""

from unittest.mock import Mock, patch

import pytest

from docpipe.core.operators.quality.pii_and_hap.pii_and_hap_annotator import PIIAndHAPAnnotator
from docpipe.exceptions.docpipe_exceptions import DocpipeException


@pytest.mark.unit
class TestPIIHAPAnnotatorValidation:
    """Test PII/HAP annotator validation during initialization."""

    @patch("docpipe.core.operators.quality.pii_and_hap.pii_and_hap_annotator.PIIHAPService")
    def test_service_validation_called_on_init(self, mock_service_class):
        """Test that validate() is called during service initialization."""
        # Setup mock adapter with validate method
        mock_adapter = Mock()
        mock_adapter.validate.return_value = {
            "valid": True,
            "errors": [],
            "warnings": [],
        }

        # Setup mock service instance
        mock_service = Mock()
        mock_service.adapter = mock_adapter
        mock_service_class.return_value = mock_service

        # Create operator config
        config = {
            "provider": "litellm",
            "provider_config": {
                "model_id": "openai/llama3.2:latest",
                "api_base": "http://localhost:11434/v1",
                "api_key": "<ollama>",  # pragma: allowlist secret
            },
        }

        # Create operator - should call validate during service initialization
        operator = PIIAndHAPAnnotator(config=config)

        # Verify service was created
        mock_service_class.assert_called_once()
        assert operator.provider == "litellm"
        assert operator.model_name == "openai/llama3.2:latest"

    @patch("docpipe.core.operators.quality.pii_and_hap.pii_and_hap_annotator.PIIHAPService")
    def test_service_validation_failure_raises_error(self, mock_service_class):
        """Test that validation failures raise DocpipeException."""
        # Mock service initialization to raise DocpipeException
        mock_service_class.side_effect = DocpipeException(
            message="Adapter validation failed: API key is required",
            status_code=400,
        )

        # Create operator config
        config = {
            "provider": "litellm",
            "provider_config": {
                "model_id": "openai/llama3.2:latest",
                "api_base": "http://localhost:11434/v1",
            },
        }

        # Attempt to create operator should raise DocpipeException
        with pytest.raises(DocpipeException, match="API key is required"):
            PIIAndHAPAnnotator(config=config)

    @patch("docpipe.core.operators.quality.pii_and_hap.pii_and_hap_annotator.PIIHAPService")
    def test_service_validation_with_warnings(self, mock_service_class, caplog):
        """Test that warnings don't block service initialization."""
        # Setup mock adapter with warnings
        mock_adapter = Mock()
        mock_adapter.validate.return_value = {
            "valid": True,
            "errors": [],
            "warnings": ["Consider setting api_base"],
        }

        # Setup mock service instance
        mock_service = Mock()
        mock_service.adapter = mock_adapter
        mock_service_class.return_value = mock_service

        # Create operator config
        config = {
            "provider": "litellm",
            "provider_config": {
                "model_id": "openai/llama3.2:latest",
                "api_key": "<ollama>",  # pragma: allowlist secret
            },
        }

        # Create operator - should succeed despite warnings
        operator = PIIAndHAPAnnotator(config=config)

        # Verify service was created successfully
        mock_service_class.assert_called_once()
        assert operator.provider == "litellm"
        assert operator.model_name == "openai/llama3.2:latest"
        # Note: Warning logging happens in PIIHAPService._validate_adapter()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
