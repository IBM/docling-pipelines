"""Unit tests for DocumentClassifierOperator — factory wiring.

Tests verify that:
- ``provider="litellm"`` → factory is called correctly and operator holds the result
- Output columns are present and correct
- Validate() does not flag valid providers
"""

from typing import Any
from unittest.mock import MagicMock, patch

import pyarrow as pa

from docpipe.core.operators.quality.classification.adapters.outbound.standard_llm_adapter import (
    StandardLLMClassificationAdapter,
)
from docpipe.core.operators.quality.classification.domain.models import ClassificationResponse

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_LITELLM_CONFIG: dict[str, Any] = {
    "provider": "litellm",
    "provider_config": {
        "model_id": "openai/test-model",
        "api_base": "http://localhost:11434/v1",
        "api_key": "test",  # pragma: allowlist secret
    },
    "document_types": ["invoice", "report"],
}

_GOOD_RESPONSE = ClassificationResponse(
    document_type="invoice",
    confidence=9,
    reasoning="Has line items",
    success=True,
)


def _make_operator(config: dict[str, Any], mock_adapter: MagicMock):
    """Build a DocumentClassifierOperator with adapter replaced by *mock_adapter*."""
    from docpipe.core.operators.quality.classification.document_classifier import DocumentClassifierOperator

    with patch(
        "docpipe.core.operators.quality.classification.document_classifier.ClassificationAdapterFactory"
    ) as mock_factory:
        mock_factory.create_adapter.return_value = mock_adapter
        op = DocumentClassifierOperator(config=config)
    op.adapter = mock_adapter
    return op


# ---------------------------------------------------------------------------
# Tests — factory resolution
# ---------------------------------------------------------------------------


class TestOperatorFactoryWiring:
    def test_litellm_provider_uses_factory(self) -> None:
        """Factory is called when provider=litellm; operator holds its result."""
        mock_adapter = MagicMock(spec=StandardLLMClassificationAdapter)
        mock_adapter.classify_document.return_value = _GOOD_RESPONSE

        from docpipe.core.operators.quality.classification.document_classifier import DocumentClassifierOperator

        with patch(
            "docpipe.core.operators.quality.classification.document_classifier.ClassificationAdapterFactory"
        ) as mock_factory:
            mock_factory.create_adapter.return_value = mock_adapter
            op = DocumentClassifierOperator(config=_LITELLM_CONFIG)

        mock_factory.create_adapter.assert_called_once_with(provider="litellm", config=_LITELLM_CONFIG)
        assert op.adapter is mock_adapter


# ---------------------------------------------------------------------------
# Tests — output columns correct
# ---------------------------------------------------------------------------


class TestOutputColumns:
    def _run_transform(self, config: dict[str, Any]) -> pa.Table:
        """Run transform with a mocked adapter and return the output table."""
        mock_adapter = MagicMock()
        mock_adapter.classify_document.return_value = _GOOD_RESPONSE

        op = _make_operator(config, mock_adapter)

        table = pa.table(
            {
                "id": ["doc_1"],
                "name": ["test.pdf"],
                "content": ["Invoice total: $500"],
            }
        )

        output_tables, _ = op.transform(table)
        return output_tables[0]

    def test_document_type_column_present(self) -> None:
        result = self._run_transform(_LITELLM_CONFIG)
        assert "document_type" in result.column_names

    def test_confidence_column_present_when_enabled(self) -> None:
        config = {**_LITELLM_CONFIG, "include_confidence": True}
        result = self._run_transform(config)
        assert "document_type_confidence" in result.column_names

    def test_no_is_scanned_column_emitted(self) -> None:
        """is_scanned must never appear in the output table."""
        result = self._run_transform(_LITELLM_CONFIG)
        assert "is_scanned" not in result.column_names


# ---------------------------------------------------------------------------
# Tests — validate()
# ---------------------------------------------------------------------------


class TestValidate:
    def test_valid_provider_produces_no_provider_error(self) -> None:
        mock_adapter = MagicMock(spec=StandardLLMClassificationAdapter)

        from docpipe.core.operators.quality.classification.document_classifier import DocumentClassifierOperator

        with patch(
            "docpipe.core.operators.quality.classification.document_classifier.ClassificationAdapterFactory"
        ) as mock_factory:
            mock_factory.create_adapter.return_value = mock_adapter
            mock_factory.get_supported_providers.return_value = {"litellm", "watsonx", "standard"}
            op = DocumentClassifierOperator(config=_LITELLM_CONFIG)

            errors: list[str] = []
            warnings: list[str] = []
            op.validate(errors, warnings, ["content", "id", "name"])

        provider_errors = [e for e in errors if "provider" in e.lower() and "litellm" in e.lower()]
        assert provider_errors == [], "validate() should not flag 'litellm' as invalid provider"
