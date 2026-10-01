# Copyright IBM Corp. 2026
# SPDX-License-Identifier: Apache-2.0

"""Port interface for PII and HAP detection adapters.

Defines the contract that all provider-specific PII/HAP detection adapters must satisfy.
"""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel

from docpipe.core.operators.quality.pii_and_hap.domain.models import PIIHAPDetectionResponse


class PIIAndHAPDetectionPort(ABC):
    """Unified interface for PII and HAP detection across all providers.

    Each provider adapter implements this port and fully encapsulates its own
    execution path behind the abstract methods below.

    Class attributes:
        ADAPTER_NAME: Unique identifier used for factory registration (e.g. 'watsonx').
        ADAPTER_DISPLAY_NAME: Human-readable name for UI display.
    """

    ADAPTER_NAME: str
    ADAPTER_DISPLAY_NAME: str

    @staticmethod
    @abstractmethod
    def get_config_schema() -> type[BaseModel]:
        """Return the Pydantic config model class for this adapter.

        Used by ``PIIAndHAPAnnotator._get_piihap_provider_schemas()`` to build
        the operator metadata schema without hard-coding adapter names.
        """
        ...

    @abstractmethod
    def detect(self, *, payload: dict[str, Any]) -> PIIHAPDetectionResponse:
        """Detect PII and HAP in the text carried by payload.

        The caller (``PIIHAPService``) guarantees that ``payload["input"]`` is a
        non-empty string before this method is called.  Adapters must not
        duplicate that guard.

        Args:
            payload: Detection request payload containing:
                - input: Non-empty text to analyse
                - detectors: Dict of detector configurations (e.g. pii, hap thresholds)

        Returns:
            PIIHAPDetectionResponse containing the list of detections.

        Raises:
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
