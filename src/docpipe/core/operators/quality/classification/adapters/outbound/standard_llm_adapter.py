"""Standard LLM classification adapter.

Implements :class:`ClassificationPort` for the ``litellm`` and ``watsonx``
providers by handling the full LLM round-trip internally via
:class:`_LLMClassificationService`, a private helper that manages the LLM
interaction.

:class:`StandardLLMClassificationAdapter` owns its own config validation and
LLM adapter construction in :meth:`~StandardLLMClassificationAdapter.from_config`.
The factory is a pure dispatcher and never contains adapter-specific logic.
"""

from typing import Any, Self

from docpipe.core.adapters.llm_adapter_factory import LLMAdapterFactory
from docpipe.core.constants.constants import LLMConstants
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.quality.classification.domain.models import (
    ClassificationRequest,
    ClassificationResponse,
    build_classification_prompt,
)
from docpipe.core.operators.quality.classification.ports.outbound.classification_port import ClassificationPort
from docpipe.core.ports.llm_inference_port import LLMInferencePort
from docpipe.exceptions.docpipe_exceptions import DocpipeException
from docpipe.exceptions.error_codes import ErrorCode
from docpipe.utils.infrastructure.logging import get_logger
from docpipe.utils.llm.json_parser import parse_llm_json_response

logger = get_logger()


# ---------------------------------------------------------------------------
# Private implementation detail — not part of the public adapter contract
# ---------------------------------------------------------------------------


class _LLMClassificationService:
    """LLM-backed classification worker used exclusively by
    :class:`StandardLLMClassificationAdapter`.

    Accepts a pre-built :class:`~docpipe.core.ports.llm_inference_port.LLMInferencePort`
    injected by :meth:`StandardLLMClassificationAdapter.from_config`.  All
    provider validation and adapter construction belong in ``from_config``, not
    here.

    Attributes:
        llm_adapter: Active :class:`LLMInferencePort` instance.
        model_id: Model identifier (for logging/metadata only).
        provider_name: Provider name (for logging/metadata only).
        temperature: Sampling temperature forwarded to the LLM.
        max_tokens: Token budget forwarded to the LLM.
    """

    def __init__(
        self,
        *,
        llm_adapter: LLMInferencePort,
        temperature: float = 0.0,
        max_tokens: int = 500,
        model_id: str = "",
        provider_name: str = "",
    ) -> None:
        """Initialise the service with a pre-built LLM adapter.

        Args:
            llm_adapter: Pre-built :class:`LLMInferencePort` instance.
            temperature: Sampling temperature (default ``0.0``).
            max_tokens: Maximum tokens for LLM response (default ``500``).
            model_id: Model identifier stored for logging/metadata only.
            provider_name: Provider name stored for logging/metadata only.

        Raises:
            DocpipeException: When adapter validation fails.
        """
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.model_id = model_id
        self.provider_name = provider_name
        self.llm_adapter: LLMInferencePort = llm_adapter

        validation_result = self.llm_adapter.validate()
        if not validation_result.get(LLMConstants.ValidationKeys.VALID, False):
            errors = validation_result.get(LLMConstants.ValidationKeys.ERRORS, [])
            raise DocpipeException(
                error_code=ErrorCode.INVALID_CONFIGURATION,
                message=f"Injected adapter validation failed: {'; '.join(errors)}",
            )
        for warning in validation_result.get(LLMConstants.ValidationKeys.WARNINGS, []):
            logger.warning("Adapter configuration warning: %s", warning)

        logger.info(
            "_LLMClassificationService: initialised adapter=%s temperature=%s max_tokens=%s",
            type(llm_adapter).__name__,
            temperature,
            max_tokens,
        )

    def classify_document(self, *, request: ClassificationRequest) -> ClassificationResponse:
        """Classify a document and return a structured response.

        Args:
            request: :class:`ClassificationRequest` carrying content and
                document-type options.

        Returns:
            :class:`ClassificationResponse` with type, confidence, and
            reasoning populated.

        Raises:
            DocpipeException: When the LLM API call fails.
        """
        try:
            prompt = build_classification_prompt(request=request)
            messages = [
                {
                    "role": "system",
                    "content": "You are a document classification expert. Always respond only with valid JSON.",
                },
                {"role": "user", "content": prompt},
            ]

            total_len = sum(len(msg.get("content", "")) for msg in messages)
            logger.debug("_LLMClassificationService: total message content length=%s chars", total_len)
            logger.debug("_LLMClassificationService: calling LLM adapter")

            result_text = self.llm_adapter.chat(
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            logger.debug(
                "_LLMClassificationService: received response (len=%s)", len(result_text) if result_text else 0
            )

            if not result_text or result_text.strip() == "":
                raise ValueError("Empty response from LLM chat API")

            try:
                result = parse_llm_json_response(result_text, log_on_error=True)
            except DocpipeException as exc:
                raise ValueError(f"Invalid JSON response from LLM: {exc}") from exc

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

            result[OperatorConstants.Classification.FIELD_DOCUMENT_TYPE] = (
                result[OperatorConstants.Classification.FIELD_DOCUMENT_TYPE].lower().replace(" ", "_")
            )

            try:
                confidence_value = float(result[OperatorConstants.Classification.FIELD_CONFIDENCE])
                result[OperatorConstants.Classification.FIELD_CONFIDENCE] = max(1, min(10, int(confidence_value)))
            except (ValueError, TypeError) as exc:
                raise ValueError(
                    f"Invalid confidence value: {result[OperatorConstants.Classification.FIELD_CONFIDENCE]}"
                ) from exc

            logger.debug(
                "_LLMClassificationService: parsed result — type=%s confidence=%s",
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
            logger.error("_LLMClassificationService: failed to parse LLM response: %s", exc)
            return ClassificationResponse(
                document_type=OperatorConstants.Classification.UNKNOWN_TYPE,
                confidence=0,
                reasoning="",
                success=False,
                error=f"Invalid response format: {exc}",
            )
        except DocpipeException:
            raise
        except Exception as exc:
            logger.exception("_LLMClassificationService: LLM call failed: %s", exc)
            raise DocpipeException(
                error_code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                message=f"LLM API call failed: {exc}",
            ) from exc

    def get_model_info(self) -> dict[str, Any]:
        """Return model metadata as a plain dictionary."""
        return {
            "model_id": self.model_id,
            "provider": self.provider_name,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

    def cleanup(self) -> None:
        """Release LLM adapter resources."""
        logger.debug("_LLMClassificationService: cleanup complete")


# ---------------------------------------------------------------------------
# Public adapter
# ---------------------------------------------------------------------------


class StandardLLMClassificationAdapter(ClassificationPort):
    """Implements :class:`ClassificationPort` for ``litellm`` and ``watsonx``
    providers by delegating to :class:`_LLMClassificationService`.

    Config validation, LLM adapter construction, and provider normalisation all
    live in :meth:`from_config`, making the factory a pure dispatcher.

    Class attributes:
        ADAPTER_NAME: ``"standard"`` — the key under which this adapter is
            registered in :class:`ClassificationAdapterFactory`.
        ADAPTER_DISPLAY_NAME: Human-readable label.
    """

    ADAPTER_NAME = "standard"
    ADAPTER_DISPLAY_NAME = "Standard LLM Classifier"

    # Provider strings that map to this adapter via the factory alias table.
    # Listed here so tests and docs have a single source of truth.
    PROVIDER_ALIASES: frozenset[str] = frozenset({"litellm", "watsonx"})

    def __init__(self, *, llm_adapter: LLMInferencePort, config: dict[str, Any]) -> None:
        """Build the adapter with a pre-built LLM port.

        Prefer :meth:`from_config` over calling this constructor directly.
        The constructor assumes all validation has already been performed.

        Args:
            llm_adapter: Pre-built and validated :class:`LLMInferencePort`.
            config: Full operator config dictionary (used for document_types,
                confidence_threshold, temperature, max_tokens).
        """
        super().__init__(config=config)
        provider_config: dict[str, Any] = config.get(OperatorConstants.Config.PROVIDER_CONFIG, {})
        temperature: float = provider_config.get(OperatorConstants.LLM.TEMPERATURE, 0.0)
        max_tokens: int = provider_config.get(OperatorConstants.LLM.MAX_TOKENS, 500)
        model_id: str = provider_config.get(OperatorConstants.Config.MODEL_ID, "")
        provider: str = config.get(OperatorConstants.Config.PROVIDER, "").lower()

        self._service = _LLMClassificationService(
            llm_adapter=llm_adapter,
            temperature=temperature,
            max_tokens=max_tokens,
            model_id=model_id,
            provider_name=provider,
        )

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> Self:
        """Validate *config*, build the :class:`LLMInferencePort`, return a ready adapter.

        This is the canonical construction path used by
        :class:`~docpipe.core.operators.quality.classification.adapters.outbound.factories.classification_adapter_factory.ClassificationAdapterFactory`.
        All provider validation and LLM adapter construction happen here so
        that the factory remains a pure dispatcher.

        Args:
            config: Full operator config dictionary.  Must contain:

                * ``provider`` — one of ``"litellm"`` or ``"watsonx"`` (or the
                  ``"standard"`` alias).
                * ``provider_config`` — dict with at minimum ``model_id``.

        Returns:
            A ready :class:`StandardLLMClassificationAdapter` instance.

        Raises:
            ValueError: When ``provider_config`` or ``provider_config.model_id``
                is absent.
            ValueError: When :class:`~docpipe.core.adapters.llm_adapter_factory.LLMAdapterFactory`
                fails to build the inference adapter.
        """
        provider_config: dict[str, Any] = config.get(OperatorConstants.Config.PROVIDER_CONFIG) or {}
        if not provider_config:
            raise ValueError(
                "provider_config is required for StandardLLMClassificationAdapter. "
                "Must include at minimum: {'model_id': '...', 'api_base': '...'}"
            )

        model_id: str = provider_config.get(OperatorConstants.Config.MODEL_ID, "")
        if not model_id:
            raise ValueError("provider_config.model_id is required for StandardLLMClassificationAdapter")

        # Normalise provider — "standard" alias falls back to the default provider.
        raw_provider: str = config.get(OperatorConstants.Config.PROVIDER, "").lower()
        llm_provider = (
            raw_provider
            if raw_provider in LLMAdapterFactory.get_supported_providers(capability="inference")
            else OperatorConstants.Classification.DEFAULT_PROVIDER
        )

        logger.debug(
            "StandardLLMClassificationAdapter.from_config: building LLMInferencePort provider=%s model=%s",
            llm_provider,
            model_id,
        )
        try:
            llm_adapter = LLMAdapterFactory.create_inference_adapter(
                provider=llm_provider,
                model_id=model_id,
                provider_config=provider_config,
            )
        except Exception as exc:
            raise ValueError(f"Failed to create LLM inference adapter for provider '{llm_provider}': {exc}") from exc

        return cls(llm_adapter=llm_adapter, config=config)

    def classify_document(
        self,
        *,
        doc_name: str,
        binary_content: bytes | None,
        existing_text: str | None,
    ) -> ClassificationResponse:
        """Classify a document using :class:`_LLMClassificationService`.

        Uses *existing_text* directly.  When only *binary_content* is available
        the adapter falls back to Docling extraction — the operator normally
        provides ``existing_text`` so this path is a safety net.

        Args:
            doc_name: File name (used for Docling format detection when
                *existing_text* is absent).
            binary_content: Raw document bytes.  Required when *existing_text*
                is ``None``.
            existing_text: Pre-extracted text.  When given, Docling extraction
                is skipped entirely.

        Returns:
            :class:`ClassificationResponse` populated by
            :class:`_LLMClassificationService`.
        """
        if existing_text is not None:
            logger.debug(
                "StandardLLMAdapter: classifying %s using existing_text (len=%s)",
                doc_name,
                len(existing_text),
            )
            content = existing_text
        elif binary_content is not None:
            logger.debug(
                "StandardLLMAdapter: existing_text absent for %s, falling back to Docling extraction (binary_size=%s bytes)",
                doc_name,
                len(binary_content),
            )
            from docpipe.core.operators.operator_utils import OperatorUtils

            result = OperatorUtils.extract_content(file_path=doc_name, binary_content=binary_content)
            if result.get(OperatorConstants.Extraction.SUCCESS):
                content = result.get(OperatorConstants.Columns.DOC_COLUMN_DEFAULT, "")
                logger.debug(
                    "StandardLLMAdapter: Docling extraction succeeded for %s (content_len=%s)",
                    doc_name,
                    len(content),
                )
            else:
                logger.warning(
                    "StandardLLMAdapter: Docling extraction failed for %s: %s",
                    doc_name,
                    result.get(OperatorConstants.Extraction.ERROR, "Extraction failed"),
                )
                return ClassificationResponse(
                    document_type=OperatorConstants.Classification.UNKNOWN_TYPE,
                    confidence=0,
                    reasoning="",
                    success=False,
                    error=result.get(OperatorConstants.Extraction.ERROR, "Extraction failed"),
                )
        else:
            logger.warning(
                "StandardLLMAdapter: no content available for %s (both binary_content and existing_text are None)",
                doc_name,
            )
            return ClassificationResponse(
                document_type=OperatorConstants.Classification.UNKNOWN_TYPE,
                confidence=0,
                reasoning="",
                success=False,
                error="No content provided: both binary_content and existing_text are None",
            )

        request = ClassificationRequest(
            content=content,
            document_types=self.document_types,
            confidence_threshold=self.confidence_threshold,
        )
        logger.debug(
            "StandardLLMAdapter: invoking _LLMClassificationService for %s (content_len=%s, types=%s)",
            doc_name,
            len(content),
            len(self.document_types),
        )
        return self._service.classify_document(request=request)
