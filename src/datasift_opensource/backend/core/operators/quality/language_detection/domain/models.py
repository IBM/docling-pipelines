"""Domain models for language detection.

This module contains the core domain models used in language detection operations.
Following hexagonal architecture, these models are independent of any specific
implementation or external service.
"""

from dataclasses import dataclass


@dataclass
class LanguageDetectionResult:
    """Result of language detection operation.

    Attributes:
        language_code: ISO 639-1 language code (e.g., 'en', 'fr', 'es')
        confidence: Confidence score between 0.0 and 1.0
    """

    language_code: str
    confidence: float
