"""Port interface for document classification services.

This port defines the contract that all classification service adapters must implement.
It follows the hexagonal architecture pattern, keeping the interface minimal and
focused on business logic only.
"""

from abc import ABC, abstractmethod
from typing import Any

from datasift.core.operators.quality.classification.domain.models import (
    ClassificationRequest,
    ClassificationResponse,
)


class ClassificationServicePort(ABC):
    """Port interface for document classification services."""

    ADAPTER_NAME: str
    ADAPTER_DISPLAY_NAME: str

    def __init__(self, *, model_id: str | None = None, **kwargs: Any) -> None:
        """Initialize the classification service adapter."""
        self.model_id = model_id

    @abstractmethod
    def classify_document(self, *, request: ClassificationRequest) -> ClassificationResponse:
        """Classify a document using LLM."""
        pass

    def get_model_info(self) -> dict[str, Any]:
        """Get information about the model."""
        return {
            "model_id": self.model_id,
            "adapter": self.ADAPTER_NAME,
        }

    def cleanup(self) -> None:
        """Optional cleanup method for adapters that manage resources."""
        return
