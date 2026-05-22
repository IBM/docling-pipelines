"""
Domain model for incremental metadata records.

This module defines the core data structure for tracking document processing
metadata in incremental workflows.
"""

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class IncrementalMetadataRecord:
    """
    Domain model representing metadata for a single document in incremental processing.

    Attributes:
        job_id: Unique identifier for the job
        doc_id: Unique identifier for the document
        name: Optional document name or path
        modified_time: Optional timestamp of last modification (epoch milliseconds)
        job_run_id: Optional identifier for the specific job run
        deleted: Flag indicating if document has been soft-deleted
    """

    job_id: str
    doc_id: str
    name: str | None = None
    modified_time: int | None = None
    job_run_id: str | None = None
    deleted: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert record to dictionary representation."""
        return {
            "job_id": self.job_id,
            "doc_id": self.doc_id,
            "name": self.name,
            "modified_time": self.modified_time,
            "job_run_id": self.job_run_id,
            "deleted": self.deleted,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IncrementalMetadataRecord":
        """Create record from dictionary representation."""
        return cls(
            job_id=data["job_id"],
            doc_id=data["doc_id"],
            name=data.get("name"),
            modified_time=data.get("modified_time"),
            job_run_id=data.get("job_run_id"),
            deleted=data.get("deleted", False),
        )
