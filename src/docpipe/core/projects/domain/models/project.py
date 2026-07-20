"""Project domain model.

A Project is a standalone organisational container that groups flows.
It is NOT a subclass of Asset — it has no pipeline definition, no container_id,
and no asset_type. It follows the same standalone Pydantic pattern as JobStats.
"""

import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger()


class Project(BaseModel):
    """Domain model for a Project entity.

    Projects are organisational containers for flows. Each flow can reference
    a project via its container_id field.

    Attributes:
        project_id: UUID, auto-generated on creation.
        name: Human-readable name. Required and must be unique.
        description: Optional free-text description.
        tags: List of categorisation tags; duplicates removed on write.
        created_on: UTC timestamp set on creation — immutable.
        modified_on: UTC timestamp updated on every write.
        created_by: User identifier of the creator — immutable after creation.
        modified_by: User identifier of the last modifier.
        href: Self-referential API link.
        flow_count: Number of flows linked to this project via container_id.
            NOT persisted — computed at read time by ProjectService.
    """

    project_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    created_on: datetime = Field(default_factory=lambda: datetime.now(UTC))
    modified_on: datetime = Field(default_factory=lambda: datetime.now(UTC))
    created_by: str | None = None
    modified_by: str | None = None
    href: str | None = None

    # Computed at read time — excluded from storage serialisation
    flow_count: int = Field(default=0, exclude=True)

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={datetime: lambda v: v.isoformat()},
    )

    def update_timestamp(self) -> None:
        """Update modified_on to current UTC time."""
        self.modified_on = datetime.now(UTC)

    def to_storage_dict(self) -> dict[str, Any]:
        """Serialise project for filesystem storage, excluding computed fields.

        Returns:
            Dictionary representation without flow_count.
        """
        data = self.model_dump(exclude={"flow_count"})
        # Serialise datetimes to ISO strings
        data["created_on"] = self.created_on.isoformat()
        data["modified_on"] = self.modified_on.isoformat()
        return data

    @classmethod
    def from_storage_dict(cls, data: dict[str, Any]) -> "Project":
        """Deserialise a project from a storage dictionary.

        Args:
            data: Dictionary loaded from JSON storage file.

        Returns:
            Project instance with flow_count defaulting to 0.
        """
        # Parse ISO datetime strings
        for ts_field in ("created_on", "modified_on"):
            value = data.get(ts_field)
            if isinstance(value, str):
                data[ts_field] = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return cls(**data)

    def to_json(self) -> str:
        """Serialise to JSON string for file storage.

        Returns:
            Indented JSON string without flow_count.
        """
        return json.dumps(self.to_storage_dict(), indent=2)
