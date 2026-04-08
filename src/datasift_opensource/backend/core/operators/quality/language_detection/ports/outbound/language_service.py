"""Port interface for language detection services.

This port defines the contract that all language detection service adapters must implement.
It follows the hexagonal architecture pattern, keeping the interface minimal and
focused on business logic only.
"""

from abc import ABC, abstractmethod

from core.operators.quality.language_detection.domain.models import LanguageDetectionResult


class LanguageServicePort(ABC):
    """Port interface for language detection services.

    This interface defines the contract for language detection services.
    Adapters implementing this port handle provider-specific details while
    the operator depends only on this abstraction.

    Attributes:
        ADAPTER_NAME: Unique identifier for the adapter (e.g., 'langdetect', 'fasttext')
        ADAPTER_DISPLAY_NAME: Human-readable name for UI display
    """

    ADAPTER_NAME: str
    ADAPTER_DISPLAY_NAME: str

    @abstractmethod
    def detect_language(self, text: str) -> LanguageDetectionResult:
        """Detect language of the given text.

        Args:
            text: Input text to detect language for

        Returns:
            LanguageDetectionResult containing language code and confidence score

        Raises:
            ValueError: If text is empty or invalid
            Exception: If language detection fails
        """
        pass
