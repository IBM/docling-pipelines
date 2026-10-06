"""Simplified classification service using LLM adapters directly.

This service consolidates the classification logic without the hexagonal architecture
overhead, directly using LLMAdapterFactory to create provider-specific adapters.
"""

from typing import Any

from docpipe.core.adapters.llm_adapter_factory import LLMAdapterFactory
from docpipe.core.constants.constants import LLMConstants
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.quality.classification.domain.models import (
    ClassificationRequest,
    ClassificationResponse,
    build_classification_prompt,
)
from docpipe.core.ports.document_class_provider import DocumentClassProvider, StaticDocumentClassProvider
from docpipe.core.ports.llm_inference_port import LLMInferencePort
from docpipe.exceptions.docpipe_exceptions import DocpipeException
from docpipe.exceptions.error_codes import ErrorCode
from docpipe.utils.infrastructure.logging import get_logger
from docpipe.utils.llm.json_parser import parse_llm_json_response

logger = get_logger(__name__)


class ClassificationService:
    """Simplified classification service using LLM adapters directly.

    This service replaces the port/adapter architecture with direct usage of
    LLMAdapterFactory, similar to how the test file uses it.

    Supports watsonx and litellm providers, or any pre-built ``LLMInferencePort``
    adapter injected via ``llm_adapter``.

    Attributes:
        llm_adapter: LLM inference adapter instance
        document_class_provider: Provider for resolving document class metadata
        provider_name: Provider name ('watsonx' or 'litellm'), empty string when
            a pre-built adapter is injected
        model_id: Model identifier
        temperature: Temperature for LLM generation
        max_tokens: Maximum tokens for LLM response
    """

    def __init__(
        self,
        *,
        model_id: str | None = None,
        provider_name: str | None = None,
        provider_config: dict[str, Any] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 500,
        llm_adapter: LLMInferencePort | None = None,
        document_class_provider: DocumentClassProvider | None = None,
    ) -> None:
        """Initialize classification service.

        At least one of ``llm_adapter`` or ``provider_name`` must be supplied:

        * When ``llm_adapter`` is given it is used directly and the factory is
          **not** called.  ``model_id`` and ``provider_name`` are then optional
          (they are stored only for informational purposes via ``get_model_info``).
        * When only ``provider_name`` is given the existing
          ``LLMAdapterFactory`` path is used (requires ``model_id``).

        Args:
            model_id: Model identifier for the provider.  Required when
                ``llm_adapter`` is not provided.
            provider_name: Provider name ('watsonx' or 'litellm').  Required
                when ``llm_adapter`` is not provided.
            provider_config: Provider-specific configuration dictionary.
            temperature: Temperature for LLM generation (default: 0.0).
            max_tokens: Maximum tokens for LLM response (default: 500).
            llm_adapter: Pre-built ``LLMInferencePort`` instance.  When
                supplied, ``model_id`` / ``provider_name`` / ``provider_config``
                are ignored for adapter construction.
            document_class_provider: Provider for resolving document class
                metadata (types, schemas, Docling templates).  Defaults to
                ``StaticDocumentClassProvider`` which reads from local JSON files.

        Raises:
            DocpipeException: If neither ``llm_adapter`` nor a valid
                ``provider_name`` + ``model_id`` pair is supplied, or if
                adapter initialisation fails.
        """
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.provider_config = provider_config or {}
        self.document_class_provider: DocumentClassProvider = (
            document_class_provider if document_class_provider is not None else StaticDocumentClassProvider()
        )

        if llm_adapter is not None:
            # Fast path: caller supplies a ready-made adapter (e.g. ModelGatewayLLMAdapter).
            # Validate before accepting so a misconfigured adapter is caught at construction
            # time rather than mid-batch inside classify_document().
            self.llm_adapter: LLMInferencePort = llm_adapter
            self.model_id = model_id or ""
            self.provider_name = provider_name or ""
            validation_result = self.llm_adapter.validate()
            if not validation_result.get(LLMConstants.ValidationKeys.VALID, False):
                errors = validation_result.get(LLMConstants.ValidationKeys.ERRORS, [])
                raise DocpipeException(
                    error_code=ErrorCode.INVALID_CONFIGURATION,
                    message=f"Injected adapter validation failed: {'; '.join(errors)}",
                )
            warnings = validation_result.get(LLMConstants.ValidationKeys.WARNINGS, [])
            if warnings:
                for warning in warnings:
                    logger.warning("Adapter configuration warning: %s", warning)
            logger.info(
                "Initialized ClassificationService with injected adapter=%s, temperature=%s, max_tokens=%s",
                type(llm_adapter).__name__,
                temperature,
                max_tokens,
            )
            return

        # Factory path: build adapter from provider_name + model_id.
        if not model_id:
            raise DocpipeException(
                error_code=ErrorCode.INVALID_CONFIGURATION,
                message=f"{OperatorConstants.Config.MODEL_ID} is required for classification service",
            )
        if not provider_name:
            raise DocpipeException(
                error_code=ErrorCode.INVALID_CONFIGURATION,
                message=f"{OperatorConstants.Config.PROVIDER} is required when llm_adapter is not provided",
            )

        provider_name = provider_name.lower()
        if provider_name not in {
            OperatorConstants.Classification.PROVIDER_WATSONX,
            OperatorConstants.Classification.PROVIDER_LITELLM,
        }:
            raise DocpipeException(
                error_code=ErrorCode.INVALID_CONFIGURATION,
                message=f"Unsupported {OperatorConstants.Config.PROVIDER}: {provider_name}. "
                f"Supported providers: {OperatorConstants.Classification.PROVIDER_WATSONX}, "
                f"{OperatorConstants.Classification.PROVIDER_LITELLM}",
            )

        self.model_id = model_id
        self.provider_name = provider_name

        # Create LLM inference adapter using factory
        try:
            self.llm_adapter = LLMAdapterFactory.create_inference_adapter(
                provider=provider_name,
                model_id=model_id,
                provider_config=self.provider_config,
            )

            # Validate adapter configuration
            validation_result = self.llm_adapter.validate()
            if not validation_result.get(LLMConstants.ValidationKeys.VALID, False):
                errors = validation_result.get(LLMConstants.ValidationKeys.ERRORS, [])
                warnings = validation_result.get(LLMConstants.ValidationKeys.WARNINGS, [])
                error_msg = f"Adapter validation failed for provider '{provider_name}'"
                if errors:
                    error_msg += f": {'; '.join(errors)}"
                if warnings:
                    for warning in warnings:
                        logger.warning("Adapter configuration warning: %s", warning)
                raise DocpipeException(
                    error_code=ErrorCode.INVALID_CONFIGURATION,
                    message=error_msg,
                )

            # Log any warnings from validation
            warnings = validation_result.get(LLMConstants.ValidationKeys.WARNINGS, [])
            if warnings:
                for warning in warnings:
                    logger.warning("Adapter configuration warning: %s", warning)

            logger.info(
                "Initialized ClassificationService with provider=%s, model=%s, temperature=%s, max_tokens=%s",
                provider_name,
                model_id,
                temperature,
                max_tokens,
            )
        except DocpipeException:
            raise
        except Exception as exc:
            raise DocpipeException(
                error_code=ErrorCode.INVALID_CONFIGURATION,
                message=f"Failed to initialize {provider_name} adapter: {exc!s}",
            ) from exc

    def classify_document(self, *, request: ClassificationRequest) -> ClassificationResponse:
        """Classify a document using the LLM adapter.

        Args:
            request: Classification request with content and document types

        Returns:
            ClassificationResponse with document type, confidence, and reasoning

        Raises:
            DocpipeException: If LLM API call fails
        """
        try:
            # Build classification prompt using domain logic
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

            # Call LLM adapter for chat completion
            logger.debug("Calling LLM adapter for classification")
            result_text = self.llm_adapter.chat(
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            logger.debug("Successfully received response from LLM adapter")

            if not result_text or result_text.strip() == "":
                logger.error("Empty or whitespace-only response from LLM")
                raise ValueError("Empty response from LLM chat API")

            logger.debug("Received content length: %d", len(result_text))

            # Parse JSON response using shared utility
            try:
                result = parse_llm_json_response(result_text, log_on_error=True)
            except DocpipeException as exc:
                # Convert DocpipeException to ValueError for consistent error handling
                raise ValueError(f"Invalid JSON response from LLM: {exc!s}") from exc

            # Validate required fields
            if (
                OperatorConstants.Classification.FIELD_DOCUMENT_TYPE not in result
                or OperatorConstants.Classification.FIELD_CONFIDENCE not in result
            ):
                raise ValueError("Invalid response format from LLM - missing required fields")

            if (
                result[OperatorConstants.Classification.FIELD_DOCUMENT_TYPE] is None
                or result[OperatorConstants.Classification.FIELD_CONFIDENCE] is None
            ):
                raise ValueError("Invalid response format from LLM - null values in required fields")

            # Normalize document type
            result[OperatorConstants.Classification.FIELD_DOCUMENT_TYPE] = (
                result[OperatorConstants.Classification.FIELD_DOCUMENT_TYPE].lower().replace(" ", "_")
            )

            # Normalize confidence to integer 1-10
            try:
                confidence_value = float(result[OperatorConstants.Classification.FIELD_CONFIDENCE])
                result[OperatorConstants.Classification.FIELD_CONFIDENCE] = max(1, min(10, int(confidence_value)))
            except (ValueError, TypeError) as exc:
                raise ValueError(
                    f"Invalid confidence value: {result[OperatorConstants.Classification.FIELD_CONFIDENCE]}"
                ) from exc

            logger.debug(
                "Classified document: type=%s, confidence=%d",
                result[OperatorConstants.Classification.FIELD_DOCUMENT_TYPE],
                result[OperatorConstants.Classification.FIELD_CONFIDENCE],
            )

            return ClassificationResponse(
                document_type=result[OperatorConstants.Classification.FIELD_DOCUMENT_TYPE],
                confidence=result[OperatorConstants.Classification.FIELD_CONFIDENCE],
                reasoning=result.get(OperatorConstants.Classification.FIELD_REASONING, ""),
                success=True,
                error=None,
            )

        except ValueError as exc:
            logger.error("Failed to parse LLM response: %s", exc)
            return ClassificationResponse(
                document_type=OperatorConstants.Classification.UNKNOWN_TYPE,
                confidence=0,
                reasoning="",
                success=False,
                error=f"Invalid response format: {exc!s}",
            )
        except DocpipeException:
            raise
        except Exception as exc:
            logger.error("LLM classification failed: %s", exc, exc_info=True)
            raise DocpipeException(
                error_code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                message=f"LLM API call failed: {exc!s}",
            ) from exc

    def get_model_info(self) -> dict[str, Any]:
        """Get model information.

        Returns:
            Dictionary with model_id, provider, temperature, and max_tokens
        """
        return {
            "model_id": self.model_id,
            "provider": self.provider_name,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

    def cleanup(self) -> None:
        """Release LLM adapter resources."""
        logger.debug("Classification service cleanup complete")
