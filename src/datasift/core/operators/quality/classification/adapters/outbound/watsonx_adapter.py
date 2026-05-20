"""Watsonx adapter for document classification."""

import json
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
from datasift.integrations.watsonx.client import WatsonXClient
from datasift.utils.infrastructure.logging import get_logger

logger = get_logger()


@register_classification_adapter
class WatsonxClassificationAdapter(ClassificationServicePort):
    """Watsonx adapter for document classification.

    Credentials can be provided via provider_config or environment variables.
    Parameters: api_key, container_id, api_base, container_kind
    Environment variables: WATSONX_API_KEY, WATSONX_CONTAINER_ID, WATSONX_API_BASE_URL, WATSONX_CONTAINER_KIND
    """

    ADAPTER_NAME = "watsonx"
    ADAPTER_DISPLAY_NAME = "IBM watsonx"

    def __init__(
        self,
        *,
        model_id: str | None = None,
        api_key: str | None = None,
        container_id: str | None = None,
        api_base: str | None = None,
        container_kind: str | None = None,
        request_timeout: int = 120,
        **kwargs: Any,
    ) -> None:
        """
        Initialize WatsonX classification adapter.

        Args:
            model_id: WatsonX model ID (required)
            api_key: IBM Cloud API key (falls back to WATSONX_API_KEY env var)
            container_id: Project or space ID (falls back to WATSONX_CONTAINER_ID env var)
            api_base: API base URL (falls back to WATSONX_API_BASE_URL env var)
            container_kind: Container type - "project" or "space" (falls back to WATSONX_CONTAINER_KIND env var)
            request_timeout: Request timeout in seconds (default: 120)
            **kwargs: Additional configuration parameters

        Security Note:
            Credentials can be provided via parameters or environment variables:
            - api_key parameter or WATSONX_API_KEY env var
            - container_id parameter or WATSONX_CONTAINER_ID env var
        """
        if not model_id:
            raise DatasiftException(
                error_code=ErrorCode.INVALID_CONFIGURATION,
                message="model_id is required for watsonx provider",
            )

        if not container_kind:
            raise DatasiftException(
                error_code=ErrorCode.INVALID_CONFIGURATION,
                message="container_kind is required for watsonx provider",
            )

        super().__init__(model_id=model_id, **kwargs)

        # Store api_base as instance attribute for test compatibility
        self.api_base = api_base

        # Initialize WatsonX client (handles all authentication and API calls)
        try:
            self.client = WatsonXClient(
                model_name=model_id,
                api_key=api_key,
                container_id=container_id,
                api_base=api_base,
                container_kind=container_kind,
                timeout=request_timeout,
            )
        except Exception as exc:
            # Check if it's an API key error and provide consistent error message
            error_msg = str(exc)
            if "WATSONX_API_KEY" in error_msg:
                raise DatasiftException(
                    error_code=ErrorCode.INVALID_CONFIGURATION,
                    message="api_key is required for watsonx provider",
                ) from exc
            raise DatasiftException(
                error_code=ErrorCode.INVALID_CONFIGURATION,
                message=f"Failed to initialize WatsonX client: {exc}",
            ) from exc

        logger.info("Initialized WatsonxClassificationAdapter with model: %s", model_id)

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

            # Use WatsonX client for chat completion
            content = self.client.chat(
                messages=messages,
                max_tokens=500,
                temperature=0.0,
            )

            logger.debug("WatsonX LLM response received (length=%d)", len(content) if content else 0)

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
        """Get model information."""
        return {
            "model_id": self.model_id,
            "adapter": self.ADAPTER_NAME,
            "api_base": self.client.api_base,
            "container_kind": self.client.container_kind,
        }
