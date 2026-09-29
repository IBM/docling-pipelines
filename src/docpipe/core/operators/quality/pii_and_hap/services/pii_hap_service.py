# Copyright IBM Corp. 2026
# SPDX-License-Identifier: Apache-2.0

"""PII and HAP detection service.

Thin wrapper around a ``PIIAndHAPDetectionPort`` instance.  All provider-specific
logic lives in the adapter,
"""

from typing import Any

from docpipe.core.constants.constants import LLMConstants
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.quality.pii_and_hap.domain.models import PIIHAPDetectionResponse
from docpipe.core.operators.quality.pii_and_hap.ports.outbound.pii_and_hap_detection_port import (
    PIIAndHAPDetectionPort,
)
from docpipe.exceptions.docpipe_exceptions import DocpipeException
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger(__name__)


class PIIHAPService:
    """Service for PII and HAP detection.

    Accepts a fully-initialised ``PIIAndHAPDetectionPort`` adapter via constructor
    injection and delegates all detection work to it.  Validation is performed at
    construction time so credential errors surface before any documents are processed.
    """

    def __init__(self, *, adapter: PIIAndHAPDetectionPort) -> None:
        """Initialise the service with a pre-built adapter.

        Args:
            adapter: An initialised ``PIIAndHAPDetectionPort`` instance.

        Raises:
            DocpipeException: If adapter validation fails.
        """
        self.adapter = adapter
        self._validate_adapter()

    def _validate_adapter(self) -> None:
        """Validate adapter configuration on initialisation.

        Raises:
            DocpipeException: If validation reports errors.
        """
        result = self.adapter.validate()

        for warning in result.get(LLMConstants.ValidationKeys.WARNINGS, []):
            logger.warning("Adapter validation warning: %s", warning)

        if not result.get(LLMConstants.ValidationKeys.VALID, True):
            errors = result.get(LLMConstants.ValidationKeys.ERRORS, ["Unknown validation error"])
            raise DocpipeException(
                message=f"Adapter validation failed: {'; '.join(errors)}",
                status_code=400,
            )

    def detect_pii_hap(self, *, payload: dict[str, Any]) -> PIIHAPDetectionResponse:
        """Detect PII and HAP in the text carried by payload.

        Args:
            payload: Detection request payload containing:
                - input: Text to analyse
                - detectors: Dict of detector configurations

        Returns:
            PIIHAPDetectionResponse containing the list of detections.

        Raises:
            ValueError: If the payload is invalid.
            DocpipeException: If detection fails.
        """
        text = payload.get(OperatorConstants.PIIHAP.INPUT_FIELD, "")
        if not text:
            raise ValueError("Input text cannot be empty")

        try:
            return self.adapter.detect(payload=payload)
        except (ValueError, DocpipeException):
            raise
        except Exception as exc:
            logger.error("Error during PII/HAP detection: %s", exc)
            raise DocpipeException(message=f"PII/HAP detection failed: {exc!s}", status_code=500) from exc

    def cleanup(self) -> None:
        """Cleanup resources.  No-op; adapters manage their own lifecycle."""
