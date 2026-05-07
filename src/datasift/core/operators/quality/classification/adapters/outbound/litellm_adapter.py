"""LiteLLM adapter for document classification."""

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
from datasift.exceptions.datasift_exceptions import DatasiftException
from datasift.exceptions.error_codes import ErrorCode
from datasift.integrations.litellm.client import LiteLLMLLMClient
from datasift.utils.infrastructure.logging import get_logger

logger = get_logger(__name__)


@register_classification_adapter
class LiteLLMClassificationAdapter(ClassificationServicePort):
    """LiteLLM-based document classification adapter."""

    ADAPTER_NAME = "litellm"
    ADAPTER_DISPLAY_NAME = "LiteLLM (Multi-Provider)"

    def __init__(
        self,
        *,
        model_id: str | None = None,
        api_key: str | None = None,
        api_base: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 1000,
        **kwargs: Any,
    ) -> None:
        if not model_id:
            raise ValueError("model_id is required for LiteLLM adapter")

        super().__init__(model_id=model_id, **kwargs)

        self.api_key = api_key
        self.api_base = api_base
        self.temperature = temperature
        self.max_tokens = max_tokens

        try:
            self.litellm_client = LiteLLMLLMClient(
                model_name=model_id,
                api_key=api_key,
                api_base=api_base,
            )
            logger.info(
                "Initialized LiteLLMClassificationAdapter with model=%s, temperature=%s, max_tokens=%s",
                model_id,
                temperature,
                max_tokens,
            )
        except Exception as exc:
            raise DatasiftException(
                error_code=ErrorCode.INVALID_CONFIGURATION,
                message=f"Failed to initialize LiteLLM client: {exc!s}",
            ) from exc

    def classify_document(self, *, request: ClassificationRequest) -> ClassificationResponse:
        """Classify a document using LiteLLM."""
        try:
            prompt = build_classification_prompt(request=request)
            messages = [
                {
                    "role": "system",
                    "content": "You are a document classification expert. Always respond only with valid JSON.",
                },
                {"role": "user", "content": prompt},
            ]

            total_content_length = sum(len(msg.get("content", "")) for msg in messages)
            logger.debug("Total message content length: %d characters", total_content_length)

            logger.debug("Calling LiteLLM chat API for classification")
            result_text = self.litellm_client.chat(
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            logger.debug("Successfully received response from LiteLLM")

            if not result_text or result_text.strip() == "":
                logger.error("Empty or whitespace-only response from LiteLLM")
                raise ValueError("Empty response from LiteLLM chat API")

            logger.debug("Received content length: %d", len(result_text))

            # Try to parse as JSON directly first
            json_text = result_text.strip()
            try:
                result = json.loads(json_text)
            except json.JSONDecodeError as e:
                # Extract JSON between { and } if present
                logger.info("Direct JSON parsing failed: %s", str(e))
                logger.debug("Raw response: %s", result_text[:500])

                if "{" in json_text and "}" in json_text:
                    start_idx = json_text.find("{")
                    end_idx = json_text.rfind("}") + 1
                    json_text = json_text[start_idx:end_idx]
                    logger.info("Extracted JSON from response")
                    result = json.loads(json_text)
                else:
                    raise ValueError(f"Invalid JSON response: {e!s}") from e

            logger.debug("Result from LLM: %s", result)

            if "document_type" not in result or "confidence" not in result:
                raise ValueError("Invalid response format from LLM - missing required fields")

            if result["document_type"] is None or result["confidence"] is None:
                raise ValueError("Invalid response format from LLM - null values in required fields")

            result["document_type"] = result["document_type"].lower().replace(" ", "_")

            # Handle float confidence values (e.g., "8.5") by converting to int
            try:
                confidence_value = float(result["confidence"])
                result["confidence"] = max(1, min(10, int(confidence_value)))
            except (ValueError, TypeError) as exc:
                raise ValueError(f"Invalid confidence value: {result['confidence']}") from exc

            logger.debug(
                "Classified document: type=%s, confidence=%d",
                result["document_type"],
                result["confidence"],
            )

            return ClassificationResponse(
                document_type=result["document_type"],
                confidence=result["confidence"],
                reasoning=result.get("reasoning", ""),
                success=True,
                error=None,
            )

        except json.JSONDecodeError as exc:
            logger.error("Failed to parse LLM response as JSON: %s", exc)
            return ClassificationResponse(
                document_type="unknown",
                confidence=0,
                reasoning="",
                success=False,
                error=f"Invalid JSON response: {exc!s}",
            )
        except ValueError as exc:
            logger.error("Invalid response format from LLM: %s", exc)
            return ClassificationResponse(
                document_type="unknown",
                confidence=0,
                reasoning="",
                success=False,
                error=f"Invalid response format: {exc!s}",
            )
        except Exception as exc:
            logger.error("LiteLLM classification failed: %s", exc, exc_info=True)
            raise DatasiftException(
                error_code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                message=f"LiteLLM API call failed: {exc!s}",
            ) from exc

    def cleanup(self) -> None:
        """Release LiteLLM client resources."""
        logger.debug("LiteLLM classification adapter cleanup complete")
