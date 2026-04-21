"""Ollama adapter for PII and HAP detection.

This adapter wraps the Ollama client to provide PII/HAP detection
"""

from typing import Any

from common.constants.operator_constants import OperatorConstants
from common.exceptions.datasift_exceptions import DatasiftException
from common.util.infrastructure.logging import get_logger
from core.operators.quality.pii_and_hap.adapters.outbound.factories.pii_hap_adapter_factory import (
    register_pii_hap_adapter,
)
from core.operators.quality.pii_and_hap.domain.models import (
    PIIHAPDetectionResponse,
    convert_detection_dicts_to_results,
)
from core.operators.quality.pii_and_hap.local_pii_hap_detect import detect_pii_hap_ollama
from core.operators.quality.pii_and_hap.ports.outbound.pii_hap_service import PIIHAPServicePort

logger = get_logger(__name__)


@register_pii_hap_adapter
class OllamaAdapter(PIIHAPServicePort):
    """Adapter for Ollama-based PII and HAP detection."""

    ADAPTER_NAME = "ollama"
    ADAPTER_DISPLAY_NAME = "Ollama LLM"

    def __init__(self, model_name: str = OperatorConstants.PIIHAP.DEFAULT_MODEL_NAME, **adapter_config: Any) -> None:
        """Initialize Ollama adapter.

        Args:
            model_name: Name of the Ollama model to use (default: granite4)
            **adapter_config: Additional configuration (currently unused)
        """
        self.model_name = model_name
        logger.info(f"Initialized OllamaAdapter with model: {model_name}")

    def detect_pii_hap(self, payload: dict[str, Any]) -> PIIHAPDetectionResponse:
        """Detect PII and HAP using Ollama model.

        Args:
            payload: Detection request payload containing:
                - input: Text to analyze
                - detectors: Dict with 'hap' and 'pii' threshold configurations

        Returns:
            PIIHAPDetectionResponse containing list of detections

        Raises:
            ValueError: If payload is invalid
            DatasiftException: If detection fails
        """
        text = payload.get(OperatorConstants.PIIHAP.INPUT_FIELD, "")
        if not text:
            raise ValueError("Input text cannot be empty")

        try:
            # Call shared Ollama detection function
            result = detect_pii_hap_ollama(request_data=payload, model_name=self.model_name)

            # Convert raw result to domain models
            detection_dicts = result.get(OperatorConstants.PIIHAP.DETECTIONS_FIELD, [])
            detections = convert_detection_dicts_to_results(detection_dicts)

            return PIIHAPDetectionResponse(detections=detections, input_text=text)
        except Exception as exc:
            logger.error(f"Error during Ollama PII/HAP detection: {exc}")
            raise DatasiftException(message=f"PII/HAP detection failed: {exc!s}", status_code=500) from exc

    def cleanup(self) -> None:
        """Release Ollama client resources."""
        logger.info("Released Ollama client resources")
