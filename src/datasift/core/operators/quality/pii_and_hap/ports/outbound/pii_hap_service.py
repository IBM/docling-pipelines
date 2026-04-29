# Copyright IBM Corp. 2025
# SPDX-License-Identifier: Apache-2.0

"""Port interface for PII and HAP detection services.

This port defines the contract that all PII/HAP detection service adapters must implement.
"""

from abc import ABC, abstractmethod
from typing import Any

from datasift.core.operators.quality.pii_and_hap.domain.models import PIIHAPDetectionResponse


class PIIHAPServicePort(ABC):
    """Port interface for PII and HAP detection services.

    This interface defines the contract for PII/HAP detection services.
    Adapters implementing this port handle provider-specific details while
    the operator depends only on this abstraction.

    Attributes:
        ADAPTER_NAME: Unique identifier for the adapter
        ADAPTER_DISPLAY_NAME: Human-readable name for UI display
    """

    ADAPTER_NAME: str
    ADAPTER_DISPLAY_NAME: str

    @abstractmethod
    def detect_pii_hap(self, payload: dict[str, Any]) -> PIIHAPDetectionResponse:
        """Detect PII and HAP in the given text.

        Args:
            payload: Detection request payload containing:
                - input: Text to analyze
                - detectors: Dictionary of detector configurations
                    - pii: PII detection config with threshold
                    - hap: HAP detection config with threshold

        Returns:
            PIIHAPDetectionResponse containing list of detections

        Raises:
            ValueError: If payload is invalid
            Exception: If detection fails
        """
        pass

    def cleanup(self) -> None:
        """Optional cleanup method for adapters that manage resources.

        This method is called by the operator's cleanup() to release any resources
        held by the adapter (e.g., models, connections). Adapters that don't manage
        resources can use the default no-op implementation.
        """
        # Default no-op implementation - subclasses can override if needed
        return
