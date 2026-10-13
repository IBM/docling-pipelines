#!/usr/bin/env python3
"""Unit tests for _LLMClassificationService (injected-adapter path).

The factory-path (provider_name + model_id) has moved to
ClassificationAdapterFactory.  These tests cover the service when a pre-built
LLMInferencePort is injected directly, which is the only construction path
that _LLMClassificationService now supports.
"""

import json
from unittest.mock import Mock, patch

import pytest

from docpipe.core.constants.constants import LLMConstants
from docpipe.core.operators.quality.classification.adapters.outbound.standard_llm_adapter import (
    _LLMClassificationService,
)
from docpipe.core.operators.quality.classification.domain.models import ClassificationRequest
from docpipe.exceptions.docpipe_exceptions import DocpipeException


def _make_valid_llm_adapter(response_text: str = "") -> Mock:
    mock = Mock()
    mock.validate.return_value = {
        LLMConstants.ValidationKeys.VALID: True,
        LLMConstants.ValidationKeys.ERRORS: [],
        LLMConstants.ValidationKeys.WARNINGS: [],
    }
    mock.chat.return_value = response_text
    return mock


@pytest.mark.unit
class TestLLMClassificationServiceInjectedAdapter:
    """Tests for _LLMClassificationService with a pre-built LLMInferencePort."""

    def test_init_with_injected_adapter(self) -> None:
        adapter = _make_valid_llm_adapter()
        service = _LLMClassificationService(llm_adapter=adapter)
        assert service.llm_adapter is adapter

    def test_init_stores_temperature_and_max_tokens(self) -> None:
        adapter = _make_valid_llm_adapter()
        service = _LLMClassificationService(llm_adapter=adapter, temperature=0.5, max_tokens=1000)
        assert service.temperature == 0.5
        assert service.max_tokens == 1000

    def test_validate_called_on_init(self) -> None:
        adapter = _make_valid_llm_adapter()
        _LLMClassificationService(llm_adapter=adapter)
        adapter.validate.assert_called_once()

    def test_validation_failure_raises(self) -> None:
        adapter = Mock()
        adapter.validate.return_value = {
            LLMConstants.ValidationKeys.VALID: False,
            LLMConstants.ValidationKeys.ERRORS: ["Missing API key"],
            LLMConstants.ValidationKeys.WARNINGS: [],
        }
        with pytest.raises(DocpipeException, match="validation failed"):
            _LLMClassificationService(llm_adapter=adapter)

    def test_injected_adapter_bypasses_factory(self) -> None:
        """_LLMClassificationService no longer imports LLMAdapterFactory at all;
        it relies entirely on the pre-built adapter passed in."""
        adapter = _make_valid_llm_adapter()
        # If service were to call LLMAdapterFactory, the adapter's validate would
        # not be the only call.  We verify the injected adapter is used directly.
        service = _LLMClassificationService(llm_adapter=adapter)
        # validate() called once during __init__ — no extra calls mean no factory was invoked
        adapter.validate.assert_called_once()
        assert service.llm_adapter is adapter

    def test_classify_document_success(self) -> None:
        response_json = json.dumps({"document_type": "invoice", "confidence": 9, "reasoning": "Has line items"})
        adapter = _make_valid_llm_adapter(response_json)
        service = _LLMClassificationService(llm_adapter=adapter)

        request = ClassificationRequest(content="Invoice content", document_types=["invoice", "receipt"])
        response = service.classify_document(request=request)

        assert response.success is True
        assert response.document_type == "invoice"
        assert response.confidence == 9
        assert response.reasoning == "Has line items"

    def test_classify_document_invalid_json_returns_failure(self) -> None:
        adapter = _make_valid_llm_adapter("Not valid JSON")
        service = _LLMClassificationService(llm_adapter=adapter)

        request = ClassificationRequest(content="Test content", document_types=["invoice"])
        response = service.classify_document(request=request)

        assert response.success is False
        assert response.document_type == "unknown"
        assert response.error is not None

    def test_classify_document_missing_fields_returns_failure(self) -> None:
        adapter = _make_valid_llm_adapter(json.dumps({"some_field": "value"}))
        service = _LLMClassificationService(llm_adapter=adapter)

        request = ClassificationRequest(content="Test", document_types=["invoice"])
        response = service.classify_document(request=request)

        assert response.success is False

    def test_classify_document_embedded_json(self) -> None:
        text = 'Here is the result: {"document_type": "report", "confidence": 7, "reasoning": "test"}'
        adapter = _make_valid_llm_adapter(text)
        service = _LLMClassificationService(llm_adapter=adapter)

        request = ClassificationRequest(content="Content", document_types=["report"])
        response = service.classify_document(request=request)

        assert response.success is True
        assert response.document_type == "report"
        assert response.confidence == 7

    def test_get_model_info(self) -> None:
        adapter = _make_valid_llm_adapter()
        service = _LLMClassificationService(
            llm_adapter=adapter,
            model_id="my-model",
            provider_name="gateway",
            temperature=0.3,
            max_tokens=800,
        )
        info = service.get_model_info()
        assert info["model_id"] == "my-model"
        assert info["provider"] == "gateway"
        assert info["temperature"] == 0.3
        assert info["max_tokens"] == 800

    def test_cleanup_does_not_raise(self) -> None:
        adapter = _make_valid_llm_adapter()
        service = _LLMClassificationService(llm_adapter=adapter)
        service.cleanup()  # must not raise


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
