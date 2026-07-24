""" "Domain models for PII and HAP detection.

This module contains the core domain models used in PII and HAP detection operations.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class DetectionResult:
    """Base result for PII/HAP detection operation.

    Attributes:
        detection: Type of detection (e.g., 'email', 'ssn', 'hate', 'abuse')
        detection_type: Category of detection (e.g., 'pii', 'hap')
        score: Confidence score between 0.0 and 1.0
        start: Start position in text
        end: End position in text
        text: Detected text snippet (optional, for display purposes)
        evidences: Additional evidence or context (optional)
    """

    detection: str
    detection_type: str
    score: float
    start: int
    end: int
    text: str | None = None
    evidences: list[dict[str, Any]] | None = None


@dataclass
class PIIHAPDetectionResponse:
    """Response containing all detections for a document.

    Attributes:
        detections: List of all detected PII/HAP instances
        input_text: Original input text (optional, for reference)
    """

    detections: list[DetectionResult]
    input_text: str | None = None


def convert_detection_dicts_to_results(detection_dicts: list[dict[str, Any]]) -> list[DetectionResult]:
    """Convert list of detection dictionaries to DetectionResult objects.

    Args:
        detection_dicts: List of dictionaries containing detection data

    Returns:
        List of DetectionResult objects
    """
    results = []
    for detection_dict in detection_dicts:
        detection = DetectionResult(
            detection=detection_dict.get("detection", ""),
            detection_type=detection_dict.get("detection_type", ""),
            score=detection_dict.get("score", 0.0),
            start=detection_dict.get("start", 0),
            end=detection_dict.get("end", 0),
            text=detection_dict.get("text"),
            evidences=detection_dict.get("evidences"),
        )
        results.append(detection)
    return results
