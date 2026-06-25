"""Tests for PIIHAPService."""

from unittest.mock import Mock, patch

import pytest

from docpipe.core.constants.constants import LLMConstants
from docpipe.core.operators.quality.pii_and_hap.domain.models import (
    DetectionResult,
    PIIHAPDetectionResponse,
)
from docpipe.core.operators.quality.pii_and_hap.services.pii_hap_service import PIIHAPService
from docpipe.core.ports.llm_inference_port import LLMInferencePort
from docpipe.core.ports.text_detection_port import TextDetectionPort
from docpipe.exceptions.docpipe_exceptions import DocpipeException


class TestPIIHAPService:
    """Test suite for PIIHAPService."""

    @pytest.fixture
    def watsonx_config(self):
        """Provide WatsonX configuration."""
        return {
            "api_key": "test-key",  # pragma: allowlist secret
            "project_id": "test-project",
            "container_id": "test-project",
            "url": "https://test.watsonx.ai",
        }

    @pytest.fixture
    def litellm_config(self):
        """Provide LiteLLM configuration."""
        return {
            "api_key": "test-key",  # pragma: allowlist secret
            "api_base": "http://localhost:11434/v1",
        }

    @pytest.fixture
    def mock_text_detection_adapter(self):
        """Create a mock TextDetectionPort adapter."""
        mock_adapter = Mock(spec=TextDetectionPort)
        mock_adapter.detect.return_value = {
            "success": True,
            "detections": [
                {
                    "detection": "EMAIL",
                    "detection_type": "pii",
                    "score": 0.95,
                    "start": 0,
                    "end": 20,
                    "text": "test@example.com",
                }
            ],
        }
        mock_adapter.validate.return_value = {
            LLMConstants.ValidationKeys.VALID: True,
            LLMConstants.ValidationKeys.CONTEXT: LLMConstants.ValidationContexts.DETECTION,
            LLMConstants.ValidationKeys.ERRORS: [],
            LLMConstants.ValidationKeys.WARNINGS: [],
        }
        return mock_adapter

    @pytest.fixture
    def mock_llm_inference_adapter(self):
        """Create a mock LLMInferencePort adapter."""
        mock_adapter = Mock(spec=LLMInferencePort)
        mock_adapter.generate.return_value = '{"detections": []}'
        mock_adapter.validate.return_value = {
            LLMConstants.ValidationKeys.VALID: True,
            LLMConstants.ValidationKeys.CONTEXT: LLMConstants.ValidationContexts.INFERENCE,
            LLMConstants.ValidationKeys.ERRORS: [],
            LLMConstants.ValidationKeys.WARNINGS: [],
        }
        return mock_adapter

    @pytest.fixture
    def watsonx_service(self, watsonx_config, mock_text_detection_adapter):
        """Create a PIIHAPService instance for WatsonX."""
        with patch(
            "docpipe.core.operators.quality.pii_and_hap.services.pii_hap_service.LLMAdapterFactory.create_text_detection_adapter",
            return_value=mock_text_detection_adapter,
        ):
            return PIIHAPService(
                provider="watsonx",
                model_id="",
                provider_config=watsonx_config,
            )

    @pytest.fixture
    def litellm_service(self, litellm_config, mock_llm_inference_adapter):
        """Create a PIIHAPService instance for LiteLLM."""
        with patch(
            "docpipe.core.operators.quality.pii_and_hap.services.pii_hap_service.LLMAdapterFactory.create_inference_adapter",
            return_value=mock_llm_inference_adapter,
        ):
            return PIIHAPService(
                provider="litellm",
                model_id="gpt-4",
                provider_config=litellm_config,
            )

    def test_initialization_watsonx(self, watsonx_config):
        """Test service initialization with WatsonX provider."""
        with patch(
            "docpipe.core.operators.quality.pii_and_hap.services.pii_hap_service.LLMAdapterFactory.create_text_detection_adapter"
        ) as mock_factory:
            mock_adapter = Mock(spec=TextDetectionPort)
            mock_adapter.validate.return_value = {
                LLMConstants.ValidationKeys.VALID: True,
                LLMConstants.ValidationKeys.CONTEXT: LLMConstants.ValidationContexts.DETECTION,
                LLMConstants.ValidationKeys.ERRORS: [],
                LLMConstants.ValidationKeys.WARNINGS: [],
            }
            mock_factory.return_value = mock_adapter

            service = PIIHAPService(
                provider="watsonx",
                model_id="test-model",
                provider_config=watsonx_config,
            )

            assert service.provider == "watsonx"
            assert service.model_id == "test-model"
            assert service.use_specialized_api is True
            mock_factory.assert_called_once_with(
                provider="watsonx",
                model_id="test-model",
                provider_config=watsonx_config,
            )

    def test_initialization_litellm(self, litellm_config):
        """Test service initialization with LiteLLM provider."""
        with patch(
            "docpipe.core.operators.quality.pii_and_hap.services.pii_hap_service.LLMAdapterFactory.create_inference_adapter"
        ) as mock_factory:
            mock_adapter = Mock(spec=LLMInferencePort)
            mock_adapter.validate.return_value = {
                LLMConstants.ValidationKeys.VALID: True,
                LLMConstants.ValidationKeys.CONTEXT: LLMConstants.ValidationContexts.INFERENCE,
                LLMConstants.ValidationKeys.ERRORS: [],
                LLMConstants.ValidationKeys.WARNINGS: [],
            }
            mock_factory.return_value = mock_adapter

            service = PIIHAPService(
                provider="litellm",
                model_id="gpt-4",
                provider_config=litellm_config,
            )

            assert service.provider == "litellm"
            assert service.model_id == "gpt-4"
            assert service.use_specialized_api is False
            mock_factory.assert_called_once_with(
                provider="litellm",
                model_id="gpt-4",
                provider_config=litellm_config,
            )

    def test_initialization_unsupported_provider(self):
        """Test initialization fails with unsupported provider."""
        with pytest.raises(ValueError, match="Unsupported provider: invalid"):
            PIIHAPService(
                provider="invalid",
                model_id="test-model",
                provider_config={},
            )

    def test_initialization_case_insensitive(self, watsonx_config):
        """Test provider name is case-insensitive."""
        with patch(
            "docpipe.core.operators.quality.pii_and_hap.services.pii_hap_service.LLMAdapterFactory.create_text_detection_adapter"
        ):
            service = PIIHAPService(
                provider="WATSONX",
                model_id="test",
                provider_config=watsonx_config,
            )
            assert service.provider == "watsonx"

    def test_initialization_without_config(self):
        """Test initialization without provider config."""
        with patch(
            "docpipe.core.operators.quality.pii_and_hap.services.pii_hap_service.LLMAdapterFactory.create_inference_adapter"
        ):
            service = PIIHAPService(
                provider="litellm",
                model_id="test",
            )
            assert service.provider_config == {}

    def test_detect_pii_hap_watsonx_success(self, watsonx_service, mock_text_detection_adapter):
        """Test successful PII/HAP detection with WatsonX."""
        payload = {
            "input": "Contact me at test@example.com",
            "detectors": {
                "pii": {"threshold": 0.5},
                "hap": {"threshold": 0.8},
            },
        }

        with patch(
            "docpipe.core.operators.quality.pii_and_hap.services.pii_hap_service.convert_detection_dicts_to_results"
        ) as mock_convert:
            mock_result = DetectionResult(
                detection="EMAIL",
                detection_type="pii",
                score=0.95,
                start=14,
                end=34,
                text="test@example.com",
            )
            mock_convert.return_value = [mock_result]

            response = watsonx_service.detect_pii_hap(payload=payload)

            assert isinstance(response, PIIHAPDetectionResponse)
            assert len(response.detections) == 1
            assert response.detections[0].detection == "EMAIL"
            mock_text_detection_adapter.detect.assert_called_once()

    def test_detect_pii_hap_empty_input(self, watsonx_service):
        """Test detection fails with empty input."""
        payload = {"input": ""}

        with pytest.raises(ValueError, match="Input text cannot be empty"):
            watsonx_service.detect_pii_hap(payload=payload)

    def test_detect_pii_hap_missing_input(self, watsonx_service):
        """Test detection fails with missing input."""
        payload = {}

        with pytest.raises(ValueError, match="Input text cannot be empty"):
            watsonx_service.detect_pii_hap(payload=payload)

    def test_detect_via_specialized_api_error(self, watsonx_service, mock_text_detection_adapter):
        """Test error handling in specialized API detection."""
        payload = {
            "input": "Test text",
            "detectors": {},
        }

        mock_text_detection_adapter.detect.return_value = {
            "success": False,
            "error": "API Error",
        }

        with pytest.raises(DocpipeException, match="Text detection failed: API Error"):
            watsonx_service.detect_pii_hap(payload=payload)

    def test_detect_via_specialized_api_exception(self, watsonx_service, mock_text_detection_adapter):
        """Test exception handling in specialized API detection."""
        payload = {
            "input": "Test text",
            "detectors": {},
        }

        mock_text_detection_adapter.detect.side_effect = Exception("Unexpected error")

        with pytest.raises(DocpipeException, match="PII/HAP detection failed"):
            watsonx_service.detect_pii_hap(payload=payload)

    def test_provider_attribute(self, watsonx_service, litellm_service):
        """Test provider attribute is set correctly."""
        assert watsonx_service.provider == "watsonx"
        assert litellm_service.provider == "litellm"

    def test_model_id_attribute(self, watsonx_service, litellm_service):
        """Test model_id attribute is set correctly."""
        assert watsonx_service.model_id == ""
        assert litellm_service.model_id == "gpt-4"

    def test_use_specialized_api_flag(self, watsonx_service, litellm_service):
        """Test use_specialized_api flag is set correctly."""
        assert watsonx_service.use_specialized_api is True
        assert litellm_service.use_specialized_api is False

    @pytest.mark.parametrize(
        "provider,expected_api_flag",
        [
            ("watsonx", True),
            ("litellm", False),
        ],
    )
    def test_various_providers(self, provider, expected_api_flag):
        """Test service with various providers."""
        with (
            patch(
                "docpipe.core.operators.quality.pii_and_hap.services.pii_hap_service.LLMAdapterFactory.create_text_detection_adapter"
            ),
            patch(
                "docpipe.core.operators.quality.pii_and_hap.services.pii_hap_service.LLMAdapterFactory.create_inference_adapter"
            ),
        ):
            service = PIIHAPService(
                provider=provider,
                model_id="test-model",
                provider_config={},
            )
            assert service.use_specialized_api == expected_api_flag

    def test_detect_with_custom_thresholds(self, watsonx_service, mock_text_detection_adapter):
        """Test detection with custom thresholds."""
        payload = {
            "input": "Test text",
            "detectors": {
                "pii": {"threshold": 0.7},
                "hap": {"threshold": 0.9},
            },
        }

        with patch(
            "docpipe.core.operators.quality.pii_and_hap.services.pii_hap_service.convert_detection_dicts_to_results",
            return_value=[],
        ):
            response = watsonx_service.detect_pii_hap(payload=payload)

            assert isinstance(response, PIIHAPDetectionResponse)
            # Verify thresholds were passed to the native detectors payload
            call_args = mock_text_detection_adapter.detect.call_args
            assert call_args[1]["detectors"]["hap"]["threshold"] == pytest.approx(0.9)
            assert call_args[1]["detectors"]["pii"]["threshold"] == pytest.approx(0.7)

    def test_detect_with_default_thresholds(self, watsonx_service, mock_text_detection_adapter):
        """Test detection uses default thresholds when not provided."""
        payload = {
            "input": "Test text",
            "detectors": {},
        }

        with patch(
            "docpipe.core.operators.quality.pii_and_hap.services.pii_hap_service.convert_detection_dicts_to_results",
            return_value=[],
        ):
            response = watsonx_service.detect_pii_hap(payload=payload)

            assert isinstance(response, PIIHAPDetectionResponse)
            # Verify empty detector config is forwarded and adapter defaults apply
            call_args = mock_text_detection_adapter.detect.call_args
            assert call_args[1]["detectors"] == {}

    def test_response_includes_input_text(self, watsonx_service, mock_text_detection_adapter):
        """Test response includes the input text."""
        payload = {
            "input": "Test input text",
            "detectors": {},
        }

        with patch(
            "docpipe.core.operators.quality.pii_and_hap.services.pii_hap_service.convert_detection_dicts_to_results",
            return_value=[],
        ):
            response = watsonx_service.detect_pii_hap(payload=payload)

            assert response.input_text == "Test input text"

    def test_multiple_detections(self, watsonx_service, mock_text_detection_adapter):
        """Test handling multiple detections."""
        payload = {
            "input": "Email: test@example.com, Phone: 123-456-7890",
            "detectors": {},
        }

        mock_text_detection_adapter.detect.return_value = {
            "success": True,
            "detections": [
                {"entity_type": "EMAIL", "score": 0.95, "start": 7, "end": 23, "text": "test@example.com"},
                {"entity_type": "PHONE", "score": 0.90, "start": 32, "end": 44, "text": "123-456-7890"},
            ],
        }

        with patch(
            "docpipe.core.operators.quality.pii_and_hap.services.pii_hap_service.convert_detection_dicts_to_results"
        ) as mock_convert:
            mock_convert.return_value = [
                DetectionResult(
                    detection="EMAIL", detection_type="pii", score=0.95, start=7, end=23, text="test@example.com"
                ),
                DetectionResult(
                    detection="PHONE", detection_type="pii", score=0.90, start=32, end=44, text="123-456-7890"
                ),
            ]

            response = watsonx_service.detect_pii_hap(payload=payload)

            assert len(response.detections) == 2
            assert response.detections[0].detection == "EMAIL"
            assert response.detections[1].detection == "PHONE"
