# Copyright IBM Corp. 2026
# SPDX-License-Identifier: Apache-2.0

"""Tests for PIIHAPService."""

from unittest.mock import MagicMock

import pytest

from docpipe.core.constants.constants import LLMConstants
from docpipe.core.operators.quality.pii_and_hap.domain.models import (
    DetectionResult,
    PIIHAPDetectionResponse,
)
from docpipe.core.operators.quality.pii_and_hap.ports.outbound.pii_and_hap_detection_port import (
    PIIAndHAPDetectionPort,
)
from docpipe.core.operators.quality.pii_and_hap.services.pii_hap_service import PIIHAPService
from docpipe.exceptions.docpipe_exceptions import DocpipeException

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_valid_adapter(**overrides) -> MagicMock:
    """Return a mock PIIAndHAPDetectionPort that passes validation by default."""
    mock = MagicMock(spec=PIIAndHAPDetectionPort)
    mock.validate.return_value = {
        LLMConstants.ValidationKeys.VALID: True,
        LLMConstants.ValidationKeys.ERRORS: [],
        LLMConstants.ValidationKeys.WARNINGS: [],
    }
    for k, v in overrides.items():
        setattr(mock, k, v)
    return mock


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def valid_adapter():
    return _make_valid_adapter()


@pytest.fixture
def service(valid_adapter):
    return PIIHAPService(adapter=valid_adapter)


# ---------------------------------------------------------------------------
# __init__ / validation
# ---------------------------------------------------------------------------


def test_init_calls_validate_on_adapter(valid_adapter):
    PIIHAPService(adapter=valid_adapter)
    valid_adapter.validate.assert_called_once()


def test_init_logs_warnings_from_adapter():
    adapter = _make_valid_adapter()
    adapter.validate.return_value = {
        LLMConstants.ValidationKeys.VALID: True,
        LLMConstants.ValidationKeys.ERRORS: [],
        LLMConstants.ValidationKeys.WARNINGS: ["Missing optional field"],
    }
    # Should not raise — warnings are logged only
    service = PIIHAPService(adapter=adapter)
    assert service._adapter is adapter


def test_init_raises_docpipe_exception_when_validation_fails():
    adapter = _make_valid_adapter()
    adapter.validate.return_value = {
        LLMConstants.ValidationKeys.VALID: False,
        LLMConstants.ValidationKeys.ERRORS: ["bad api key"],
        LLMConstants.ValidationKeys.WARNINGS: [],
    }
    with pytest.raises(DocpipeException, match="Adapter validation failed"):
        PIIHAPService(adapter=adapter)


def test_init_stores_adapter(service, valid_adapter):
    assert service._adapter is valid_adapter


# ---------------------------------------------------------------------------
# detect_pii_hap()
# ---------------------------------------------------------------------------


def test_detect_pii_hap_delegates_to_adapter(service, valid_adapter):
    expected = PIIHAPDetectionResponse(detections=[], input_text="hello")
    valid_adapter.detect.return_value = expected

    result = service.detect_pii_hap(payload={"input": "hello", "detectors": {}})

    assert result is expected
    valid_adapter.detect.assert_called_once_with(payload={"input": "hello", "detectors": {}})


def test_detect_pii_hap_raises_on_empty_input(service):
    with pytest.raises(ValueError, match="Input text cannot be empty"):
        service.detect_pii_hap(payload={"input": ""})


def test_detect_pii_hap_raises_on_missing_input(service):
    with pytest.raises(ValueError, match="Input text cannot be empty"):
        service.detect_pii_hap(payload={})


def test_detect_pii_hap_re_raises_docpipe_exception(service, valid_adapter):
    valid_adapter.detect.side_effect = DocpipeException(message="provider error", status_code=500)
    with pytest.raises(DocpipeException, match="provider error"):
        service.detect_pii_hap(payload={"input": "text", "detectors": {}})


def test_detect_pii_hap_wraps_unexpected_exception(service, valid_adapter):
    valid_adapter.detect.side_effect = RuntimeError("invalid")
    with pytest.raises(DocpipeException, match="PII/HAP detection failed"):
        service.detect_pii_hap(payload={"input": "text", "detectors": {}})


def test_detect_pii_hap_returns_detection_results(service, valid_adapter):
    result = DetectionResult(detection="EmailAddress", detection_type="pii", score=0.9, start=0, end=15)
    valid_adapter.detect.return_value = PIIHAPDetectionResponse(detections=[result], input_text="test@example.com")

    response = service.detect_pii_hap(payload={"input": "test@example.com", "detectors": {}})
    assert len(response.detections) == 1
    assert response.detections[0].detection == "EmailAddress"


# ---------------------------------------------------------------------------
# cleanup()
# ---------------------------------------------------------------------------


def test_cleanup_is_noop(service):
    service.cleanup()  # should not raise
