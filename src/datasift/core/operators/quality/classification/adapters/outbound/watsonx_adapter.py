"""Watsonx adapter for document classification."""

import json
import os
from threading import Lock
from typing import Any

from datasift.core.operators.quality.classification.adapters.outbound.factories.classification_adapter_factory import (
    register_classification_adapter,
)
from datasift.core.operators.quality.classification.domain.models import (
    ClassificationRequest,
    ClassificationResponse,
    build_classification_prompt,
)
from datasift.core.operators.quality.classification.ports.outbound.classification_service import (
    ClassificationServicePort,
)
from datasift.exceptions.datasift_exceptions import DatasiftException, ExternalServiceError
from datasift.exceptions.error_codes import ErrorCode
from datasift.integrations.docling.vlm_pipeline_options_provider import WatsonxPipelineOptionsProvider
from datasift.integrations.rest_client import RestClient, RestClientConfig, RestMethod
from datasift.utils.infrastructure.logging import get_logger

logger = get_logger()


@register_classification_adapter
class WatsonxClassificationAdapter(ClassificationServicePort):
    """Watsonx adapter for document classification.

    Security: api_key and container_id MUST be provided via environment variables only.
    Required environment variables: WATSONX_API_KEY, WATSONX_CONTAINER_ID
    Optional environment variables: WATSONX_API_BASE_URL, WATSONX_CONTAINER_KIND
    """

    ADAPTER_NAME = "watsonx"
    ADAPTER_DISPLAY_NAME = "IBM watsonx"

    def __init__(
        self,
        *,
        model_id: str | None = None,
        api_base: str | None = None,
        api_key: str | None = None,
        container_kind: str | None = None,
        container_id: str | None = None,
        request_timeout: int = 120,
        **kwargs: Any,
    ) -> None:
        # Security: api_key and container_id MUST come from environment variables only
        resolved_api_key = os.getenv("WATSONX_API_KEY")
        resolved_container_id = os.getenv("WATSONX_CONTAINER_ID")

        # Non-sensitive config: allow provider_config with env var fallback
        resolved_api_base = api_base or os.getenv("WATSONX_API_BASE_URL")
        resolved_container_kind = container_kind or os.getenv("WATSONX_CONTAINER_KIND")

        # Validation
        if not model_id:
            raise DatasiftException(
                error_code=ErrorCode.INVALID_CONFIGURATION,
                message="model_id is required for watsonx provider",
            )
        if not resolved_api_base:
            raise DatasiftException(
                error_code=ErrorCode.INVALID_CONFIGURATION,
                message="api_base is required for watsonx provider. Set via provider_config or WATSONX_API_BASE_URL environment variable",
            )
        if not resolved_api_key:
            raise DatasiftException(
                error_code=ErrorCode.INVALID_CONFIGURATION,
                message="api_key is required for watsonx provider. Must be set via WATSONX_API_KEY environment variable (not in provider_config for security)",
            )
        if not resolved_container_id:
            raise DatasiftException(
                error_code=ErrorCode.INVALID_CONFIGURATION,
                message="container_id is required for watsonx provider. Must be set via WATSONX_CONTAINER_ID environment variable (not in provider_config for security)",
            )
        if not resolved_container_kind:
            raise DatasiftException(
                error_code=ErrorCode.INVALID_CONFIGURATION,
                message="container_kind is required for watsonx provider. Set via provider_config or WATSONX_CONTAINER_KIND environment variable",
            )

        super().__init__(model_id=model_id, **kwargs)

        self.api_base: str = resolved_api_base
        self.api_key: str = resolved_api_key
        self.container_kind: str = resolved_container_kind
        self.container_id: str = resolved_container_id
        self.request_timeout = request_timeout
        self._access_token: str | None = None
        self._token_lock = Lock()

        self._rest_config = RestClientConfig(
            timeout=self.request_timeout,
            retry_max_attempts=3,
            retry_multiplier=2.0,
            retry_min_wait=1.0,
            retry_max_wait=10.0,
        )

        logger.info("Initialized WatsonxClassificationAdapter with model: %s", model_id)

    def _get_access_token(self) -> str:
        """Get or refresh IAM access token (thread-safe)."""
        with self._token_lock:
            if not self._access_token:
                self._access_token = WatsonxPipelineOptionsProvider._get_iam_access_token(api_key=self.api_key)

            if self._access_token is None:
                raise DatasiftException(
                    error_code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                    message="Failed to obtain Watsonx IAM access token",
                )

            return self._access_token

    def _get_rest_client(self) -> RestClient:
        """Get RestClient with fresh IAM token."""
        access_token = self._get_access_token()
        return RestClient(config=self._rest_config, auth_token=access_token)

    def _call_watsonx_api(self, *, payload: dict[str, Any]) -> dict[str, Any]:
        """Call Watsonx chat API with the given payload."""
        rest_client = self._get_rest_client()
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        chat_url = f"{self.api_base}/ml/v1/text/chat"
        params = {"version": "2023-10-25"}

        logger.debug("Calling Watsonx text chat API with model: %s", self.model_id)
        result = rest_client.call_rest_json(
            method=RestMethod.POST,
            endpoint=chat_url,
            json_data=payload,
            headers=headers,
            params=params,
            expected_status_codes=[200],
        )

        logger.debug("Watsonx API call completed successfully")
        return result

    def classify_document(self, *, request: ClassificationRequest) -> ClassificationResponse:
        """Classify a document using Watsonx."""
        try:
            prompt = build_classification_prompt(request=request)
            messages = [
                {
                    "role": "system",
                    "content": "You are a document classification expert. Always respond only with valid JSON.",
                },
                {"role": "user", "content": prompt},
            ]

            watsonx_messages = []
            for msg in messages:
                role = msg.get("role", "")
                content = msg.get("content", "")

                if role == "user":
                    watsonx_messages.append({"role": role, "content": [{"type": "text", "text": content}]})
                else:
                    watsonx_messages.append({"role": role, "content": content})

            payload = {
                "model_id": self.model_id,
                "messages": watsonx_messages,
                "max_tokens": 500,
                "temperature": 0.0,
                "time_limit": self.request_timeout * 1000,
            }

            if self.container_kind and self.container_id:
                payload[f"{self.container_kind}_id"] = self.container_id
            else:
                raise DatasiftException(
                    error_code=ErrorCode.INVALID_CONFIGURATION,
                    message="container_kind and container_id are required for watsonx provider",
                )

            result = self._call_watsonx_api(payload=payload)

            choices = result.get("choices", [])
            if not choices:
                logger.error("No choices in Watsonx chat API response")
                raise ValueError("No choices in Watsonx chat API response")

            message = choices[0].get("message", {})
            content = message.get("content", "")

            if not content:
                logger.error("Empty content in Watsonx chat API response")
                raise ValueError("Empty response from Watsonx chat API")

            logger.debug("Watsonx LLM response received (length=%d)", len(content) if content else 0)

            json_str = content
            if isinstance(content, str):
                start_idx = content.find("{")
                end_idx = content.rfind("}") + 1
                if start_idx != -1 and end_idx > start_idx:
                    json_str = content[start_idx:end_idx]
                    if json_str != content:
                        logger.debug("Extracted JSON from response (length=%d)", len(json_str))

            parsed_result = json.loads(json_str) if isinstance(json_str, str) else json_str

            if "document_type" not in parsed_result or "confidence" not in parsed_result:
                raise ValueError("Invalid response format from LLM - missing required fields")

            parsed_result["document_type"] = parsed_result["document_type"].lower().replace(" ", "_")

            # Handle float confidence values (e.g., "8.5") by converting to int
            try:
                confidence_value = float(parsed_result["confidence"])
                parsed_result["confidence"] = max(1, min(10, int(confidence_value)))
            except (ValueError, TypeError) as exc:
                raise ValueError(f"Invalid confidence value: {parsed_result['confidence']}") from exc

            logger.debug(
                "Classified document: type=%s, confidence=%d",
                parsed_result["document_type"],
                parsed_result["confidence"],
            )

            return ClassificationResponse(
                document_type=parsed_result["document_type"],
                confidence=parsed_result["confidence"],
                reasoning=parsed_result.get("reasoning", ""),
                success=True,
                error=None,
            )

        except json.JSONDecodeError as exc:
            logger.error(f"Failed to parse LLM response as JSON: {exc!s}")
            return ClassificationResponse(
                document_type="unknown",
                confidence=0,
                reasoning="",
                success=False,
                error=f"Invalid JSON response: {exc!s}",
            )
        except ExternalServiceError as exc:
            self._access_token = None
            logger.error(f"Watsonx classification failed: {exc!s}")
            return ClassificationResponse(
                document_type="unknown",
                confidence=0,
                reasoning="",
                success=False,
                error=f"Watsonx API call failed: {exc!s}",
            )
        except DatasiftException:
            raise
        except Exception as exc:
            logger.error(f"Watsonx classification failed: {exc!s}", exc_info=True)
            return ClassificationResponse(
                document_type="unknown",
                confidence=0,
                reasoning="",
                success=False,
                error=f"Watsonx API call failed: {exc!s}",
            )

    def get_model_info(self) -> dict[str, Any]:
        """Get model information (excludes sensitive container_id)."""
        return {
            "model_id": self.model_id,
            "adapter": self.ADAPTER_NAME,
            "api_base": self.api_base,
            "container_kind": self.container_kind,
        }
