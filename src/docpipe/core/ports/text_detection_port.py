"""Generic interface for text detection APIs.

This port defines the contract for specialized text detection services,
such as WatsonX's PII/HAP detection API. It is designed to be reusable
for other detection scenarios (toxicity, sentiment, content moderation, etc.).
"""

from abc import ABC, abstractmethod
from typing import Any

from docpipe.core.constants.constants import LLMConstants


class TextDetectionPort(ABC):
    """Generic interface for text detection operations.

    This port is implemented by provider-specific adapters for specialized
    detection APIs that are not compatible with standard LLM chat interfaces.

    Examples:
        - WatsonX PII/HAP detection (/ml/v1/text/detection)
        - Future: Toxicity detection, sentiment analysis, content moderation
    """

    @abstractmethod
    def detect(self, *, text: str, detection_types: list[str] | None = None, **kwargs: Any) -> dict[str, Any]:
        """Perform text detection.

        Args:
            text: Input text to analyze
            detection_types: Optional list of detection types to perform
            **kwargs: Provider-specific parameters

        Returns:
            Detection results dict with structure:
            {
                "success": bool,
                "detections": list[dict],  # List of detected items
                "error": str | None
            }

        Raises:
            Exception: Provider-specific errors
        """
        pass

    def validate(self) -> dict[str, Any]:
        """Template method for validation.

        This method defines the validation algorithm structure by calling
        the hook method validate_detection(). Subclasses override the hook
        method to provide specific validation logic.

        Returns:
            Validation result dictionary from validate_detection()
        """
        return self.validate_detection()

    def validate_detection(self) -> dict[str, Any]:
        """Hook method for detection validation.

        Default implementation returns a valid result. Subclasses should
        override this method to provide specific validation logic.

        Returns:
            Dictionary with validation result:
                - valid: bool indicating if validation passed
                - context: str indicating validation context ("detection")
                - message: Optional str with additional information
        """
        return {
            LLMConstants.ValidationKeys.VALID: True,
            LLMConstants.ValidationKeys.CONTEXT: LLMConstants.ValidationContexts.DETECTION,
        }
