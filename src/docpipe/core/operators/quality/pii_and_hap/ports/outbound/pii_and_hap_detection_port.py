# Copyright IBM Corp. 2026
# SPDX-License-Identifier: Apache-2.0

"""Port interface for PII and HAP detection adapters.

Defines the contract that all provider-specific PII/HAP detection adapters must satisfy.
"""

from abc import ABC, abstractmethod
from typing import Any

from docpipe.core.operators.quality.pii_and_hap.domain.models import PIIHAPDetectionResponse


class PIIAndHAPDetectionPort(ABC):
    """Unified interface for PII and HAP detection across all providers.

    Each provider adapter implements this port and fully encapsulates its own
    execution path behind the two abstract methods below.

    Class attributes:
        ADAPTER_NAME: Unique identifier used for factory registration (e.g. 'watsonx').
        ADAPTER_DISPLAY_NAME: Human-readable name for UI display.
    """

    ADAPTER_NAME: str
    ADAPTER_DISPLAY_NAME: str

    @abstractmethod
    def detect(self, *, payload: dict[str, Any]) -> PIIHAPDetectionResponse:
        """Detect PII and HAP in the text carried by payload.

        Args:
            payload: Detection request payload containing:
                - input: Text to analyse
                - detectors: Dict of detector configurations (e.g. pii, hap thresholds)

        Returns:
            PIIHAPDetectionResponse containing the list of detections.

        Raises:
            ValueError: If the payload is invalid (e.g. empty input).
            DocpipeException: If detection fails at the provider level.
        """
        ...

    @abstractmethod
    def validate(self) -> dict[str, Any]:
        """Validate adapter configuration before any documents are processed.

        Called during service initialisation so credential or config errors surface
        at startup (fail-fast) rather than mid-run.

        Returns:
            Validation result dictionary with at minimum:
                - valid (bool): True if configuration is valid.
                - errors (list[str]): Error messages when valid is False.
                - warnings (list[str]): Non-fatal warnings.
        """
        ...
