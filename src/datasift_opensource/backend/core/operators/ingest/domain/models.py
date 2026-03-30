"""Domain models for ingest operations."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class DocumentACL:
    """Access Control List information for a document."""

    allowed_users: list[str] | None = None
    allowed_groups: list[str] | None = None

    def __post_init__(self):
        if self.allowed_users is None:
            self.allowed_users = []
        if self.allowed_groups is None:
            self.allowed_groups = []


@dataclass
class Document:
    """
    Domain model representing a document from any source.

    This is the core domain entity that all connectors must produce.
    It is technology-agnostic and represents the business concept of a document.
    """

    # Required fields
    id: str
    name: str
    content: bytes
    source_url: str

    # Timestamps
    modified_time: datetime | None = None
    created_time: datetime | None = None

    # Access control
    acl: DocumentACL | None = None

    # Additional metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    # File information
    mimetype: str | None = None
    size: int | None = None
    extension: str | None = None

    def __post_init__(self):
        """Initialize computed fields."""
        if self.size is None and self.content:
            self.size = len(self.content)

        if self.extension is None and self.name:
            import os

            self.extension = os.path.splitext(self.name)[1].lower()

        if self.acl is None:
            self.acl = DocumentACL()


@dataclass
class FileMetadata:
    """Metadata about a file from a source."""

    path: str
    name: str
    size: int
    modified_time: datetime | None = None
    created_time: datetime | None = None
    mimetype: str | None = None
    extension: str | None = None
    is_directory: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class IngestionResult:
    """Result of an ingestion operation."""

    total_documents: int = 0
    processed_documents: int = 0
    failed_documents: int = 0
    skipped_documents: int = 0

    failed_doc_ids: list[str] = field(default_factory=list)
    skipped_doc_ids: list[str] = field(default_factory=list)

    errors: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)

    metadata: dict[str, Any] = field(default_factory=dict)

    def add_error(self, doc_id: str, doc_name: str, error: str):
        """Record a failed document."""
        self.failed_documents += 1
        self.failed_doc_ids.append(doc_id)
        self.errors.append({"doc_id": doc_id, "doc_name": doc_name, "error": error})

    def add_warning(self, doc_id: str, doc_name: str, warning: str):
        """Record a warning for a document."""
        self.warnings.append({"doc_id": doc_id, "doc_name": doc_name, "warning": warning})

    def add_skipped(self, doc_id: str, doc_name: str, reason: str):
        """Record a skipped document."""
        self.skipped_documents += 1
        self.skipped_doc_ids.append(doc_id)
        self.warnings.append({"doc_id": doc_id, "doc_name": doc_name, "reason": reason})

    def increment_processed(self):
        """Increment processed document count."""
        self.processed_documents += 1

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_documents == 0:
            return 0.0
        return (self.processed_documents / self.total_documents) * 100.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "total_documents": self.total_documents,
            "processed_documents": self.processed_documents,
            "failed_documents": self.failed_documents,
            "skipped_documents": self.skipped_documents,
            "success_rate": self.success_rate,
            "failed_doc_ids": self.failed_doc_ids,
            "skipped_doc_ids": self.skipped_doc_ids,
            "errors": self.errors,
            "warnings": self.warnings,
            "metadata": self.metadata,
        }
