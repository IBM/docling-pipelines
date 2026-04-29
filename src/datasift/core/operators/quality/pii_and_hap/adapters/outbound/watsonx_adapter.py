# Copyright IBM Corp. 2025
# SPDX-License-Identifier: Apache-2.0

"""WatsonX.ai adapter for PII and HAP detection.
This adapter uses WatsonX.ai's native /ml/v1/text/detection API endpoint.
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
from datasift.core.operators.quality.pii_and_hap.ports.outbound.pii_hap_service import PIIHAPServicePort
from datasift.exceptions.datasift_exceptions import DatasiftException, ExternalServiceError
from datasift.integrations.docling.vlm_pipeline_options_provider import WatsonxPipelineOptionsProvider
from datasift.integrations.rest_client import RestClient, RestClientConfig, RestMethod
from datasift.utils.infrastructure.logging import get_logger

logger = get_logger(__name__)


@register_pii_hap_adapter
class WatsonXAdapter(PIIHAPServicePort):
    """Adapter for IBM WatsonX.ai PII and HAP detection."""

    ADAPTER_NAME = "watsonx"
    ADAPTER_DISPLAY_NAME = "IBM WatsonX.ai"

    def __init__(
        self,
        api_key: str,
        url: str,
        container_kind: str | None = None,
        container_id: str | None = None,
        timeout: int = 300,
        **adapter_config: Any,
    ) -> None:
        """Initialize WatsonX adapter.

        Args:
            api_key: WatsonX.ai API key (IBM Cloud API key)
            url: WatsonX.ai API base URL
            container_kind: Container type ('project' or 'space' or 'catalog')
            container_id: Container ID (project_id or space_id or catalog_id)
            timeout: Request timeout in seconds (default: 300)
            **adapter_config: Additional configuration (model_name ignored)

        Raises:
            ValueError: If required parameters are missing or IAM token exchange fails
        """
        if not api_key:
            raise ValueError("WatsonX API key is required")
        if not url:
            raise ValueError("WatsonX URL is required")

        self.api_key = api_key
        self.url = url
        self.container_kind = container_kind
        self.container_id = container_id
        self.timeout = timeout
        self._access_token: str | None = None

        logger.info(f"Initialized WatsonX adapter with URL: {self.url}")

    def detect_pii_hap(self, payload: dict[str, Any]) -> PIIHAPDetectionResponse:
        """Detect PII and HAP using WatsonX.ai detection API.

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
            # Call WatsonX detection API with the payload directly
            detections = self._call_watsonx_detection_api(payload)

            # Convert to domain models
            detection_results = convert_detection_dicts_to_results(detections)

            return PIIHAPDetectionResponse(detections=detection_results, input_text=text)

        except DatasiftException:
            raise
        except Exception as exc:
            logger.error(f"Error during WatsonX PII/HAP detection: {exc}")
            raise DatasiftException(message=f"WatsonX PII/HAP detection failed: {exc!s}", status_code=500) from exc

    def _get_access_token(self) -> str:
        """Get or refresh IAM access token."""
        if not self._access_token:
            self._access_token = WatsonxPipelineOptionsProvider._get_iam_access_token(api_key=self.api_key)
        return self._access_token

    def _call_watsonx_detection_api(self, payload: dict[str, Any]) -> list[dict[str, Any]]:

        # Build detection URL
        detection_url = f"{self.url}/ml/v1/text/detection"

        # Add version parameter only
        params = {"version": "2024-07-29"}

        # Get fresh IAM access token
        access_token = self._get_access_token()

        # Add container information (project or space or catalog) to the payload
        if self.container_kind or self.container_id:
            payload[f"{self.container_kind}_id"] = self.container_id
        else:
            raise ValueError("container id/ container kind is required for WatsonX detection API")

        # Configure RestClient with retry logic
        config = RestClientConfig(
            timeout=self.timeout,
            retry_max_attempts=3,
            retry_multiplier=2.0,
            retry_min_wait=1.0,
            retry_max_wait=10.0,
        )

        # Create RestClient with IAM token
        client = RestClient(config=config, auth_token=access_token)

        try:
            logger.info(f"Calling WatsonX detection API: {self.url}/ml/v1/text/detection")

            # Make API call using RestClient
            result = client.call_rest_json(
                method=RestMethod.POST,
                endpoint=detection_url,
                json_data=payload,
                params=params,
                expected_status_codes=[200],
            )

            detections = result.get(OperatorConstants.PIIHAP.DETECTIONS_FIELD, [])
            logger.info(f"WatsonX detection API returned {len(detections)} detections")
            return detections

        except ExternalServiceError as exc:
            # Refresh token for next attempt
            self._access_token = None
            logger.error(f"WatsonX detection API call failed: {exc}")
            raise DatasiftException(
                message=f"Failed to call WatsonX detection API: {exc!s}",
                status_code=exc.status_code or 500,
            ) from exc

    def cleanup(self) -> None:
        """Release WatsonX client resources."""
        logger.info("Released WatsonX client resources")
