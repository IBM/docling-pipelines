"""Unit tests for TextDetectionPort abstract interface."""

from typing import Any

import pytest

from docpipe.core.constants.constants import LLMConstants
from docpipe.core.ports.text_detection_port import TextDetectionPort


class _ConcreteDetectionPort(TextDetectionPort):
    """Minimal concrete implementation for testing the base class."""

    def detect(self, *, text: str, detection_types: list[str] | None = None, **kwargs: Any) -> dict[str, Any]:
        return {"success": True, "detections": [], "error": None}


class _CustomValidationPort(TextDetectionPort):
    """Concrete implementation that overrides validate_detection."""

    def detect(self, *, text: str, detection_types: list[str] | None = None, **kwargs: Any) -> dict[str, Any]:
        return {"success": True, "detections": [], "error": None}

    def validate_detection(self) -> dict[str, Any]:
        return {
            LLMConstants.ValidationKeys.VALID: False,
            LLMConstants.ValidationKeys.CONTEXT: LLMConstants.ValidationContexts.DETECTION,
            LLMConstants.ValidationKeys.ERRORS: ["custom detection error"],
        }


# ---------------------------------------------------------------------------
# Default validate / validate_detection
# ---------------------------------------------------------------------------


def test_validate_returns_valid_true_by_default():
    port = _ConcreteDetectionPort()
    result = port.validate()
    assert result[LLMConstants.ValidationKeys.VALID] is True


def test_validate_context_is_detection():
    port = _ConcreteDetectionPort()
    result = port.validate()
    assert result[LLMConstants.ValidationKeys.CONTEXT] == LLMConstants.ValidationContexts.DETECTION


def test_validate_detection_returns_valid_result():
    port = _ConcreteDetectionPort()
    result = port.validate_detection()
    assert result[LLMConstants.ValidationKeys.VALID] is True
    assert result[LLMConstants.ValidationKeys.CONTEXT] == LLMConstants.ValidationContexts.DETECTION


def test_validate_delegates_to_validate_detection():
    """validate() must call validate_detection() and return its result."""
    port = _CustomValidationPort()
    result = port.validate()
    assert result[LLMConstants.ValidationKeys.VALID] is False
    assert LLMConstants.ValidationKeys.ERRORS in result


# ---------------------------------------------------------------------------
# Abstract method is enforced
# ---------------------------------------------------------------------------


def test_cannot_instantiate_abstract_class():
    with pytest.raises(TypeError):
        TextDetectionPort()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# Concrete detect behaviour
# ---------------------------------------------------------------------------


def test_detect_returns_expected_shape():
    port = _ConcreteDetectionPort()
    result = port.detect(text="some text")
    assert result["success"] is True
    assert isinstance(result["detections"], list)
    assert result["error"] is None


def test_detect_accepts_detection_types():
    port = _ConcreteDetectionPort()
    result = port.detect(text="text", detection_types=["PII"])
    assert result["success"] is True


def test_detect_accepts_extra_kwargs():
    port = _ConcreteDetectionPort()
    result = port.detect(text="text", model="custom-model", threshold=0.8)
    assert result["success"] is True
