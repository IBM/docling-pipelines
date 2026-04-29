"""Data card domain model for Document Sets.

This model captures lineage and provenance information for document sets,
tracking the flow, job, and operators that created or modified the data.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DataCard:
    """Data card for document set lineage and provenance.

    Captures metadata about the data processing pipeline that created or
    modified a document set, including flow information, job execution details,
    and operator lineage.

    Attributes:
        flow_id: Optional unique identifier of the flow that created this data
        flow_name: Optional name of the flow
        job_id: Optional unique identifier of the job execution
        job_run_id: Optional unique identifier of the specific job run
        operators: Optional list of operator names used in the pipeline
        lineage_metadata: Optional additional lineage metadata as key-value pairs
    """

    flow_id: str | None = None
    flow_name: str | None = None
    job_id: str | None = None
    job_run_id: str | None = None
    operators: list[str] = field(default_factory=list)
    lineage_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert data card to dictionary representation.

        Returns:
            Dictionary representation of the data card
        """
        return {
            "flow_id": self.flow_id,
            "flow_name": self.flow_name,
            "job_id": self.job_id,
            "job_run_id": self.job_run_id,
            "operators": self.operators,
            "lineage_metadata": self.lineage_metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DataCard":
        """Create DataCard from dictionary representation.

        Args:
            data: Dictionary containing data card information

        Returns:
            DataCard instance
        """
        return cls(
            flow_id=data.get("flow_id"),
            flow_name=data.get("flow_name"),
            job_id=data.get("job_id"),
            job_run_id=data.get("job_run_id"),
            operators=data.get("operators", []),
            lineage_metadata=data.get("lineage_metadata", {}),
        )
