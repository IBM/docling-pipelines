# Copyright IBM Corp. 2026
# SPDX-License-Identifier: Apache-2.0

"""WatsonX adapter for PII and HAP detection."""

from typing import Any

from pydantic import BaseModel

from docpipe.core.adapters.llm_adapter_factory import LLMAdapterFactory
from docpipe.core.constants.constants import LLMConstants
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.quality.pii_and_hap.adapters.outbound.factories.pii_and_hap_detection_factory import (
    register_pii_and_hap_detection_adapter,
)
from docpipe.core.operators.quality.pii_and_hap.adapters.outbound.watsonx.config import (
    ADAPTER_NAME,
    WatsonxPIIAndHAPConfig,
)
from docpipe.core.operators.quality.pii_and_hap.domain.models import (
    PIIHAPDetectionResponse,
    convert_detection_dicts_to_results,
)
from docpipe.core.operators.quality.pii_and_hap.ports.outbound.pii_and_hap_detection_port import (
    PIIAndHAPDetectionPort,
)
from docpipe.exceptions.docpipe_exceptions import DocpipeException
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger(__name__)


@register_pii_and_hap_detection_adapter
class WatsonxPIIAndHAPAdapter(PIIAndHAPDetectionPort):
    """PII/HAP detection adapter backed by the WatsonX specialised detection API.

    Uses ``TextDetectionPort`` (``/ml/v1/text/detection``) for native PII and HAP
    detection — no prompt engineering required.
    """

    ADAPTER_NAME = ADAPTER_NAME
    ADAPTER_DISPLAY_NAME = "WatsonX"

    def __init__(self, *, model_id: str, provider_config: dict[str, Any]) -> None:
        """Initialise the WatsonX PII/HAP adapter.

        Args:
            model_id: WatsonX model identifier.
            provider_config: Provider-specific config (api_key, url, container_kind, container_id, timeout).
        """
        self._model_id = model_id
        self._provider_config = provider_config
        self._adapter = LLMAdapterFactory.create_text_detection_adapter(
            provider="watsonx",
            model_id=model_id,
            provider_config=provider_config,
        )
        logger.info("Initialised WatsonxPIIAndHAPAdapter")

    @staticmethod
    def get_config_schema() -> type[BaseModel]:
        """Return the Pydantic config model class for this adapter."""
        return WatsonxPIIAndHAPConfig

    def validate(self) -> dict[str, Any]:
        """Validate WatsonX credentials and configuration.

        Returns:
            Validation result dict with ``valid``, ``errors``, and ``warnings`` keys.
        """
        required_keys = ["api_key", "url", "container_kind", "container_id"]
        missing = [k for k in required_keys if not self._provider_config.get(k)]
        if missing:
            return {
                LLMConstants.ValidationKeys.VALID: False,
                LLMConstants.ValidationKeys.ERRORS: [
                    f"WatsonX provider_config is missing required keys: {', '.join(missing)}"
                ],
                LLMConstants.ValidationKeys.WARNINGS: [],
            }
        return self._adapter.validate()

    def detect(self, *, payload: dict[str, Any]) -> PIIHAPDetectionResponse:
        """Detect PII/HAP using the WatsonX native text detection API.

        Args:
            payload: Dict with ``input`` (str) and ``detectors`` (dict).
                ``input`` is guaranteed non-empty by the calling service.

        Returns:
            PIIHAPDetectionResponse with all detected items.

        Raises:
            DocpipeException: If the WatsonX API call fails.
        """
        text = payload.get(OperatorConstants.PIIHAP.INPUT_FIELD, "")
        detectors = payload.get("detectors")
        result_dict = self._adapter.detect(text=text, detectors=detectors)

        if not result_dict.get("success", False):
            error_msg = result_dict.get("error", "Unknown error")
            raise DocpipeException(message=f"Text detection failed: {error_msg}", status_code=500)

        detection_results = convert_detection_dicts_to_results(result_dict.get("detections", []))
        return PIIHAPDetectionResponse(detections=detection_results, input_text=text)
