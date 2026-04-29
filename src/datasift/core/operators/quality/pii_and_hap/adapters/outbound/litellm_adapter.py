"""LiteLLM adapter for PII and HAP detection.

This adapter provides a unified interface to 100+ LLM providers including:
- OpenAI (gpt-4, gpt-3.5-turbo)
- Anthropic (claude-3-opus, claude-3-sonnet)
- Azure OpenAI (azure/deployment-name)
- Cohere (command, command-light)
- AWS Bedrock (bedrock/anthropic.claude-v2)
- Google Vertex AI (vertex_ai/gemini-pro)
- And many more...

Example Usage:
    # OpenAI
    adapter = LiteLLMAdapter(model_name="gpt-4")

    # Anthropic
    adapter = LiteLLMAdapter(model_name="claude-3-opus-20240229")

    # Azure OpenAI
    adapter = LiteLLMAdapter(
        model_name="azure/gpt-4-deployment",
        api_key="your-azure-key" # pragma: allowlist secret
    )
"""

from typing import Any

from datasift.core.constants.operator_constants import OperatorConstants
from datasift.core.operators.quality.pii_and_hap.adapters.outbound.factories.pii_hap_adapter_factory import (
    register_pii_hap_adapter,
)
from datasift.core.operators.quality.pii_and_hap.domain.models import (
    PIIHAPDetectionResponse,
    convert_detection_dicts_to_results,
)
from datasift.core.operators.quality.pii_and_hap.local_pii_hap_detect import detect_pii_hap_litellm
from datasift.core.operators.quality.pii_and_hap.ports.outbound.pii_hap_service import PIIHAPServicePort
from datasift.exceptions.datasift_exceptions import DatasiftException
from datasift.utils.infrastructure.logging import get_logger

logger = get_logger(__name__)


@register_pii_hap_adapter
class LiteLLMAdapter(PIIHAPServicePort):
    """Adapter for LiteLLM-based PII and HAP detection."""

    ADAPTER_NAME = "litellm"
    ADAPTER_DISPLAY_NAME = "LiteLLM (Multi-Provider)"

    def __init__(
        self,
        *,
        model_name: str,
        api_key: str | None = None,
        api_base: str | None = None,
        **adapter_config: Any,
    ) -> None:

        if not model_name:
            raise ValueError("model_name is required for LiteLLM adapter")

        self.model_name = model_name
        self.api_key = api_key
        self.api_base = api_base
        self.adapter_config = adapter_config

        logger.info(f"Initialized LiteLLM adapter with model: {model_name}")

    def detect_pii_hap(self, payload: dict[str, Any]) -> PIIHAPDetectionResponse:
        """Detect PII and HAP using LiteLLM.

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
            result = detect_pii_hap_litellm(
                request_data=payload,
                model_name=self.model_name,
                api_key=self.api_key,
                api_base=self.api_base,
                **self.adapter_config,
            )

            # Convert to domain models
            detection_dicts = result.get(OperatorConstants.PIIHAP.DETECTIONS_FIELD, [])
            detection_results = convert_detection_dicts_to_results(detection_dicts)

            return PIIHAPDetectionResponse(detections=detection_results, input_text=text)
        except Exception as exc:
            logger.error(f"Error during LiteLLM PII/HAP detection: {exc}")
            raise DatasiftException(message=f"LiteLLM PII/HAP detection failed: {exc!s}", status_code=500) from exc

    def cleanup(self) -> None:
        """Release LiteLLM client resources."""
        logger.info("LiteLLM adapter cleanup complete")
