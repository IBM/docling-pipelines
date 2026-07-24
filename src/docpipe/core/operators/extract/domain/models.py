"""Domain models for extract operators.

This module defines the core domain models for text and entity extraction operations
following hexagonal architecture principles. These models are framework-agnostic and
represent the business logic layer.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from docpipe.core.constants.operator_constants import OperatorConstants


class TextExtractionMode(StrEnum):
    """Text extraction providers."""

    DOCLING_LIBRARY = OperatorConstants.ExtractionModes.TEXT_MODE_DOCLING_LIBRARY
    DOCLING_SERVE = OperatorConstants.ExtractionModes.TEXT_MODE_DOCLING_SERVE


class EntityExtractionMode(StrEnum):
    """Entity extraction providers."""

    DOCLING = OperatorConstants.ExtractionModes.ENTITY_MODE_DOCLING
    LITELLM = OperatorConstants.ExtractionModes.ENTITY_MODE_LITELLM
    WATSONX = OperatorConstants.ExtractionModes.ENTITY_MODE_WATSONX
    NONE = OperatorConstants.ExtractionModes.ENTITY_MODE_NONE


@dataclass
class VlmConfig:
    """Configuration for Vision-Language Model extraction.

    Attributes:
        preset: VLM preset configuration name (e.g., "default", "high_quality")
        engine_type: VLM engine type (e.g., "openai", "anthropic")
        provider_config: Provider-specific configuration dictionary
    """

    preset: str = "default"
    engine_type: str = "openai"
    provider_config: dict[str, Any] = field(default_factory=dict)


@dataclass
class DoclingServeConfig:
    """Configuration for Docling Serve remote extraction.

    Attributes:
        url: Docling Serve API endpoint URL
        timeout: Request timeout in seconds
        max_retries: Maximum number of retry attempts
        additional_params: Additional API-specific parameters
    """

    url: str = "http://localhost:8080"
    timeout: int = 300
    max_retries: int = 3
    additional_params: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractionRequest:
    """Request for text extraction from a document.

    Contains document-specific parameters for extraction. Configuration settings
    (VLM settings, etc.) are passed to the adapter at initialization time, not per-request.

    Attributes:
        file_path: Path to the document file
        binary_content: Binary content of the document
        doc_id: Optional document identifier for tracking
        doc_name: Optional document name for logging
        metadata: Optional metadata dictionary for additional context
    """

    file_path: str
    binary_content: bytes
    doc_id: str | None = None
    doc_name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractionResult:
    """Response from text extraction operation.

    Contains the extracted content and metadata from a document extraction operation.

    Attributes:
        success: Indicates whether extraction was successful
        content: Extracted text content in markdown format (None if failed)
        tables: List of extracted tables as dictionaries
        images: List of extracted images with metadata
        structured_data: Structured data from template-based extraction
        metadata: Additional metadata about the extraction (page count, etc.)
        error: Error message if extraction failed (None if successful)

    Validation Rules:
        - If success=True, content should not be None
        - If success=False, error should contain a descriptive message
    """

    success: bool
    content: str | None = None
    tables: list[dict[str, Any]] = field(default_factory=list)
    images: list[dict[str, Any]] = field(default_factory=list)
    structured_data: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def __post_init__(self) -> None:
        """Validate the extraction result after initialization."""
        if self.success and self.content is None:
            raise ValueError("Successful extraction must have content")
        if not self.success and self.error is None:
            raise ValueError("Failed extraction must have an error message")


@dataclass
class EntityExtractionRequest:
    """Request for entity extraction from document content.

    Contains document-specific parameters for entity extraction. Configuration settings
    (model_name, temperature, max_tokens, etc.) are passed to the adapter at
    initialization time, not per-request.

    Attributes:
        content: Document text content to extract entities from
        doc_id: Document identifier for tracking
        doc_name: Document name for logging
        schema: Optional schema dictionary defining expected entity structure
        metadata: Optional metadata dictionary for additional context
    """

    content: str
    doc_id: str
    doc_name: str = ""
    schema: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EntityExtractionResult:
    """Response from entity extraction operation.

    Contains the extracted entities and metadata from an entity extraction operation.

    Attributes:
        success: Indicates whether extraction was successful
        entities: Extracted entities as a dictionary (None if failed)
        doc_id: Document identifier for tracking
        error: Error message if extraction failed (None if successful)
        metadata: Additional metadata about the extraction

    Validation Rules:
        - If success=True, entities should not be None
        - If success=False, error should contain a descriptive message
    """

    success: bool
    entities: dict[str, Any] | None = None
    doc_id: str = ""
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate the entity extraction result after initialization."""
        if self.success and self.entities is None:
            raise ValueError("Successful entity extraction must have entities")
        if not self.success and self.error is None:
            raise ValueError("Failed entity extraction must have an error message")
