"""Ollama adapter for document classification."""

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
from datasift.integrations.ollama.client import InteractionMode, OllamaClient
from datasift.utils.infrastructure.logging import get_logger

logger = get_logger()

DEFAULT_OLLAMA_MODEL = "granite4:latest"


@register_classification_adapter
class OllamaClassificationAdapter(ClassificationServicePort):
    """Ollama adapter for document classification."""

    ADAPTER_NAME = "ollama"
    ADAPTER_DISPLAY_NAME = "Ollama"

    def __init__(self, *, model_id: str | None = None, **kwargs: Any) -> None:
        actual_model_id: str = model_id or DEFAULT_OLLAMA_MODEL
        super().__init__(model_id=actual_model_id, **kwargs)

        try:
            if not OllamaClient.is_server_running():
                raise DatasiftException(
                    error_code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                    message="Ollama server is not running. Start it with: ollama serve",
                )

            if not OllamaClient.is_model_available(model_name=actual_model_id):
                raise DatasiftException(
                    error_code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                    message=f"Model '{actual_model_id}' is not available in Ollama. Pull it with: ollama pull {actual_model_id}",
                )

            logger.info("Validated Ollama connection and model availability")
        except ImportError as exc:
            raise DatasiftException(
                error_code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                message="ollama package not installed. Install with: pip install ollama",
            ) from exc
        except DatasiftException:
            raise
        except Exception as exc:
            raise DatasiftException(
                error_code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                message=f"Could not validate Ollama setup: {exc!s}",
            ) from exc

        logger.info("Initialized OllamaClassificationAdapter with model: %s", model_id)

    def classify_document(self, *, request: ClassificationRequest) -> ClassificationResponse:
        """Classify a document using Ollama."""
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
            logger.debug(f"Total message content length: {total_content_length} characters")

            system_prompt = None
            user_content = ""

            for msg in messages:
                role = msg.get("role", "")
                content = msg.get("content", "")

                if role == "system":
                    system_prompt = content
                elif role == "user":
                    user_content = content

            # model_id is guaranteed to be str (set in __init__ with default)
            client = OllamaClient(
                model_name=self.model_id,  # type: ignore[arg-type]
                mode=InteractionMode.CHAT,
                system_prompt=system_prompt,
                validate_model=False,
            )

            logger.debug("Calling OllamaClient.run() for chat interaction")
            result_text = client.run(prompt=user_content)
            logger.debug("Successfully called OllamaClient.run()")

            if result_text:
                logger.debug(f"Received content length: {len(result_text)}")
                result = json.loads(result_text)
            else:
                logger.warning("No content in response, returning empty JSON")
                result = {}

            logger.debug(f"Result from LLM: {result}")

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

            logger.debug("Classified document: type=%s, confidence=%s", result["document_type"], result["confidence"])

            return ClassificationResponse(
                document_type=result["document_type"],
                confidence=result["confidence"],
                reasoning=result.get("reasoning", ""),
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
        except ValueError as exc:
            logger.error(f"Invalid response format from LLM: {exc!s}")
            return ClassificationResponse(
                document_type="unknown",
                confidence=0,
                reasoning="",
                success=False,
                error=f"Invalid response format: {exc!s}",
            )
        except Exception as exc:
            logger.error(f"Ollama classification failed: {exc!s}", exc_info=True)
            raise DatasiftException(
                error_code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                message=f"Ollama API call failed: {exc!s}",
            ) from exc

    def cleanup(self) -> None:
        """Release Ollama client resources."""
        logger.info("Released Ollama client resources")
