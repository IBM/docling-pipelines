"""Pure Python domain model for Flow.

This is a domain entity without framework dependencies (no Pydantic).
Represents the core business concept of a Flow in the system.

Exception Handling:
The validate() method raises FlowInvalidDataException for validation failures,
ensuring consistent exception handling across the application layers.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from docpipe.exceptions.docpipe_exceptions import FlowInvalidDataException


@dataclass
class Flow:
    """Domain model for Flow entity.

    Represents a flow definition that can be stored and executed.
    This is a pure Python class without external dependencies.

    Validation:
    The validate() method raises FlowInvalidDataException for all validation
    failures, ensuring consistent exception handling across application layers.
    """

    name: str
    definition: dict[str, Any]
    container_kind: str | None = None
    container_id: str | None = None
    flow_id: str | None = None
    description: str | None = None
    tags: list[str] = field(default_factory=list)
    is_hidden: bool | None = False
    flow_version: str | None = "2.0"
    created_on: datetime | None = None
    modified_on: datetime | None = None
    job_id: str | None = None
    created_by: str | None = None
    modified_by: str | None = None
    href: str | None = None

    def __post_init__(self):
        """Post-initialization to set default values."""
        if self.flow_id is None:
            self.flow_id = str(uuid4())
        if self.created_on is None:
            self.created_on = datetime.now(UTC)
        if self.modified_on is None:
            self.modified_on = datetime.now(UTC)

        # Ensure tags is a list
        if self.tags is None:
            self.tags = []

    def validate(self) -> None:
        """Validate the flow entity.

        Performs validation on flow name, description, and definition structure.

        Validation Rules:
        - Name: Non-empty, ≤255 characters
        - Description: ≤2000 characters (if provided)
        - Definition: Non-empty dictionary in Elyra pipeline format

        Expected definition format (Elyra pipeline):
        {
            "doc_type": "pipeline",
            "version": "3.0",
            "json_schema": "https://api.dataplatform.ibm.com/schemas/...",
            "id": "<uuid>",
            "primary_pipeline": "<uuid>",
            "pipelines": [
                {
                    "id": "<uuid>",
                    "nodes": [...],
                    "app_data": {
                        "ds_flow": {...},
                        "ui_data": {...}
                    }
                }
            ],
            "schemas": []
        }

        Raises:
            FlowInvalidDataException: If validation fails. Includes specific error
                message and field_name for targeted error handling.
        """
        # Validate name: must be non-empty and within length limit
        if not self.name or len(self.name.strip()) == 0:
            raise FlowInvalidDataException(message="Flow name cannot be empty", field_name="name")
        if len(self.name) > 255:
            raise FlowInvalidDataException(message="Flow name cannot exceed 255 characters", field_name="name")

        # Validate description: optional but must be within length limit if provided
        if self.description and len(self.description) > 2000:
            raise FlowInvalidDataException(
                message="Flow description cannot exceed 2000 characters", field_name="description"
            )

        # Validate definition: must be a non-empty dictionary
        if not isinstance(self.definition, dict):
            raise FlowInvalidDataException(message="Flow definition must be a dictionary", field_name="definition")

        if len(self.definition) == 0:
            raise FlowInvalidDataException(message="Flow definition cannot be empty", field_name="definition")

    def update_timestamp(self) -> None:
        """Update the modified_on timestamp."""
        self.modified_on = datetime.now(UTC)

    def to_dict(self) -> dict[str, Any]:
        """Convert flow to dictionary representation.

        Returns:
            Dictionary representation of the flow
        """
        return {
            "flow_id": self.flow_id,
            "container_kind": self.container_kind,
            "container_id": self.container_id,
            "name": self.name,
            "description": self.description,
            "definition": self.definition,
            "tags": self.tags,
            "is_hidden": self.is_hidden,
            "flow_version": self.flow_version,
            "created_on": self.created_on.isoformat() if self.created_on else None,
            "modified_on": self.modified_on.isoformat() if self.modified_on else None,
            "job_id": self.job_id,
            "created_by": self.created_by,
            "modified_by": self.modified_by,
            "href": self.href,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Flow":
        """Create Flow from dictionary representation.

        Args:
            data: Dictionary containing flow data

        Returns:
            Flow instance
        """
        # Parse datetime strings if present
        created_on = data.get("created_on")
        if isinstance(created_on, str):
            created_on = datetime.fromisoformat(created_on.replace("Z", "+00:00"))

        modified_on = data.get("modified_on")
        if isinstance(modified_on, str):
            modified_on = datetime.fromisoformat(modified_on.replace("Z", "+00:00"))

        return cls(
            flow_id=data.get("flow_id"),
            container_kind=data.get("container_kind"),
            container_id=data.get("container_id"),
            name=data["name"],
            description=data.get("description"),
            definition=data["definition"],
            tags=data.get("tags", []),
            is_hidden=data.get("is_hidden", False),
            flow_version=data.get("flow_version", "2.0"),
            created_on=created_on,
            modified_on=modified_on,
            job_id=data.get("job_id"),
            created_by=data.get("created_by"),
            modified_by=data.get("modified_by"),
            href=data.get("href"),
        )
