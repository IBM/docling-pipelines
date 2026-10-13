"""Unit tests for StandardLLMClassificationAdapter."""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from docpipe.core.operators.quality.classification.adapters.outbound.standard_llm_adapter import (
    StandardLLMClassificationAdapter,
)
from docpipe.core.operators.quality.classification.domain.models import ClassificationResponse
from docpipe.core.ports.llm_inference_port import LLMInferencePort

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_BASE_CONFIG: dict[str, Any] = {
    "provider": "litellm",
    "provider_config": {
        "model_id": "openai/test-model",
        "api_base": "http://localhost:11434/v1",
        "api_key": "test",  # pragma: allowlist secret
    },
    "document_types": ["invoice", "receipt"],
    "confidence_threshold": 7.0,
}

_GOOD_RESPONSE = ClassificationResponse(
    document_type="invoice",
    confidence=9,
    reasoning="Contains line items and totals",
    success=True,
)


def _make_mock_llm_adapter() -> MagicMock:
    """Return a mock LLMInferencePort that passes validation."""
    mock = MagicMock(spec=LLMInferencePort)
    mock.validate.return_value = {"valid": True, "errors": [], "warnings": []}
    return mock


def _make_adapter(config: dict[str, Any] | None = None) -> StandardLLMClassificationAdapter:
    """Return an adapter with a mocked _LLMClassificationService."""
    cfg = config or _BASE_CONFIG
    mock_llm = _make_mock_llm_adapter()
    with patch(
        "docpipe.core.operators.quality.classification.adapters.outbound.standard_llm_adapter._LLMClassificationService"
    ) as mock_svc_cls:
        mock_svc = MagicMock()
        mock_svc.classify_document.return_value = _GOOD_RESPONSE
        mock_svc_cls.return_value = mock_svc
        adapter = StandardLLMClassificationAdapter(llm_adapter=mock_llm, config=cfg)
    adapter._service = mock_svc  # type: ignore[attr-defined]
    return adapter


# ---------------------------------------------------------------------------
# Tests — constructor / class attributes
# ---------------------------------------------------------------------------


class TestStandardLLMClassificationAdapterInit:
    def test_adapter_name(self) -> None:
        assert StandardLLMClassificationAdapter.ADAPTER_NAME == "standard"

    def test_provider_aliases(self) -> None:
        """PROVIDER_ALIASES declares the flow-JSON strings that resolve here."""
        assert "litellm" in StandardLLMClassificationAdapter.PROVIDER_ALIASES
        assert "watsonx" in StandardLLMClassificationAdapter.PROVIDER_ALIASES

    def test_stores_document_types(self) -> None:
        adapter = _make_adapter()
        assert adapter.document_types == ["invoice", "receipt"]

    def test_stores_confidence_threshold(self) -> None:
        adapter = _make_adapter()
        assert adapter.confidence_threshold == 7.0

    def test_requires_llm_adapter_parameter(self) -> None:
        """Constructor requires llm_adapter; passing it builds successfully."""
        mock_llm = _make_mock_llm_adapter()
        with patch(
            "docpipe.core.operators.quality.classification.adapters.outbound.standard_llm_adapter._LLMClassificationService"
        ):
            adapter = StandardLLMClassificationAdapter(llm_adapter=mock_llm, config=_BASE_CONFIG)
        assert adapter is not None


# ---------------------------------------------------------------------------
# Tests — from_config (canonical construction path)
# ---------------------------------------------------------------------------


class TestFromConfig:
    """from_config is the path the factory calls; test it end-to-end."""

    def test_returns_adapter_instance(self) -> None:
        """from_config returns a StandardLLMClassificationAdapter when config is valid."""
        mock_llm = _make_mock_llm_adapter()
        with (
            patch(
                "docpipe.core.operators.quality.classification.adapters.outbound.standard_llm_adapter.LLMAdapterFactory"
            ) as mock_factory_cls,
            patch(
                "docpipe.core.operators.quality.classification.adapters.outbound.standard_llm_adapter._LLMClassificationService"
            ),
        ):
            mock_factory_cls.create_inference_adapter.return_value = mock_llm
            mock_factory_cls.get_supported_providers.return_value = {"litellm", "watsonx"}
            adapter = StandardLLMClassificationAdapter.from_config(_BASE_CONFIG)
        assert isinstance(adapter, StandardLLMClassificationAdapter)

    def test_builds_llm_adapter_with_correct_provider(self) -> None:
        """from_config passes the resolved provider to LLMAdapterFactory."""
        mock_llm = _make_mock_llm_adapter()
        with (
            patch(
                "docpipe.core.operators.quality.classification.adapters.outbound.standard_llm_adapter.LLMAdapterFactory"
            ) as mock_factory_cls,
            patch(
                "docpipe.core.operators.quality.classification.adapters.outbound.standard_llm_adapter._LLMClassificationService"
            ),
        ):
            mock_factory_cls.create_inference_adapter.return_value = mock_llm
            mock_factory_cls.get_supported_providers.return_value = {"litellm", "watsonx"}
            StandardLLMClassificationAdapter.from_config(_BASE_CONFIG)

        mock_factory_cls.create_inference_adapter.assert_called_once_with(
            provider="litellm",
            model_id="openai/test-model",
            provider_config=_BASE_CONFIG["provider_config"],
        )

    def test_standard_alias_falls_back_to_litellm(self) -> None:
        """The 'standard' alias resolves to the DEFAULT_PROVIDER (litellm)."""
        config = {**_BASE_CONFIG, "provider": "standard"}
        mock_llm = _make_mock_llm_adapter()
        with (
            patch(
                "docpipe.core.operators.quality.classification.adapters.outbound.standard_llm_adapter.LLMAdapterFactory"
            ) as mock_factory_cls,
            patch(
                "docpipe.core.operators.quality.classification.adapters.outbound.standard_llm_adapter._LLMClassificationService"
            ),
        ):
            mock_factory_cls.create_inference_adapter.return_value = mock_llm
            # "standard" is NOT in INFERENCE_PROVIDERS, so fallback kicks in
            mock_factory_cls.get_supported_providers.return_value = {"litellm", "watsonx"}
            StandardLLMClassificationAdapter.from_config(config)

        call_kwargs = mock_factory_cls.create_inference_adapter.call_args.kwargs
        # Must NOT forward "standard" to LLMAdapterFactory — uses default provider
        assert call_kwargs["provider"] != "standard"

    def test_raises_when_provider_config_missing(self) -> None:
        config = {**_BASE_CONFIG, "provider_config": {}}
        with pytest.raises(ValueError, match="provider_config is required"):
            StandardLLMClassificationAdapter.from_config(config)

    def test_raises_when_model_id_missing(self) -> None:
        config = {
            **_BASE_CONFIG,
            "provider_config": {"api_base": "http://localhost:11434/v1"},
        }
        with pytest.raises(ValueError, match="model_id is required"):
            StandardLLMClassificationAdapter.from_config(config)

    def test_raises_when_llm_factory_fails(self) -> None:
        with (
            patch(
                "docpipe.core.operators.quality.classification.adapters.outbound.standard_llm_adapter.LLMAdapterFactory"
            ) as mock_factory_cls,
        ):
            mock_factory_cls.get_supported_providers.return_value = {"litellm", "watsonx"}
            mock_factory_cls.create_inference_adapter.side_effect = RuntimeError("connection refused")
            with pytest.raises(ValueError, match="Failed to create LLM inference adapter"):
                StandardLLMClassificationAdapter.from_config(_BASE_CONFIG)


# ---------------------------------------------------------------------------
# Tests — classify_document with existing_text
# ---------------------------------------------------------------------------


class TestClassifyDocumentWithExistingText:
    def test_delegates_to_service_when_existing_text_given(self) -> None:
        """When existing_text is supplied the service receives it directly."""
        adapter = _make_adapter()
        response = adapter.classify_document(
            doc_name="doc.pdf",
            binary_content=None,
            existing_text="Invoice total: $100",
        )
        assert response.success is True
        assert response.document_type == "invoice"
        adapter._service.classify_document.assert_called_once()  # type: ignore[attr-defined]

    def test_returns_valid_classification_response(self) -> None:
        adapter = _make_adapter()
        response = adapter.classify_document(
            doc_name="doc.pdf",
            binary_content=None,
            existing_text="Some document content",
        )
        assert isinstance(response, ClassificationResponse)
        assert response.success is True


# ---------------------------------------------------------------------------
# Tests — classify_document with binary_content
# ---------------------------------------------------------------------------


class TestClassifyDocumentWithBinaryContent:
    def test_calls_extract_content_when_no_existing_text(self) -> None:
        """When only binary_content is provided, OperatorUtils.extract_content is called."""
        adapter = _make_adapter()
        fake_extraction = {
            "success": True,
            "content": "Extracted markdown text",
        }
        with patch(
            "docpipe.core.operators.operator_utils.OperatorUtils.extract_content",
            return_value=fake_extraction,
        ) as mock_extract:
            response = adapter.classify_document(
                doc_name="doc.pdf",
                binary_content=b"%PDF-fake",
                existing_text=None,
            )
        mock_extract.assert_called_once_with(file_path="doc.pdf", binary_content=b"%PDF-fake")
        assert isinstance(response, ClassificationResponse)

    def test_returns_failure_when_extraction_fails(self) -> None:
        adapter = _make_adapter()
        fake_extraction = {"success": False, "error": "Unsupported format"}
        with patch(
            "docpipe.core.operators.operator_utils.OperatorUtils.extract_content",
            return_value=fake_extraction,
        ):
            response = adapter.classify_document(
                doc_name="doc.pdf",
                binary_content=b"bad-pdf",
                existing_text=None,
            )
        assert response.success is False
        assert "Extraction failed" in (response.error or "") or "Unsupported format" in (response.error or "")


# ---------------------------------------------------------------------------
# Tests — no content
# ---------------------------------------------------------------------------


class TestClassifyDocumentNoContent:
    def test_returns_failure_when_both_none(self) -> None:
        adapter = _make_adapter()
        response = adapter.classify_document(
            doc_name="doc.pdf",
            binary_content=None,
            existing_text=None,
        )
        assert response.success is False
        assert response.error is not None
        assert "None" in response.error
