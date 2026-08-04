"""Project domain model.

A Project is a standalone organisational container that groups flows.
It is NOT a subclass of Asset — it has no pipeline definition, no container_id,
and no asset_type.

Used by:
    POST   /api/v1/projects
    GET    /api/v1/projects
    GET    /api/v1/projects/{project_id}
    PUT    /api/v1/projects/{project_id}
    PATCH  /api/v1/projects/{project_id}
    DELETE /api/v1/projects/{project_id}
    GET    /api/v1/projects/{project_id}/flows
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


@dataclass
class Project:
    """A Project groups flows under a single organisational unit.

    Each flow references a project by storing the project's UUID in its
    container_id field.  ProjectService uses this relationship to compute
    flow_count and to cascade-delete flows when a project is removed.

    Attributes:
        name: Human-readable display name. Must be unique across all projects.
        project_id: UUID assigned at creation. Immutable after first save.
        description: Optional free-text description.
        tags: Categorisation tags. Duplicates are removed before persistence.
        created_on: UTC timestamp recorded at creation. Never updated.
        modified_on: UTC timestamp refreshed on every write via update_timestamp().
        created_by: Identifier of the user who created the project. Immutable.
        modified_by: Identifier of the user who last modified the project.
        href: Self-link to the project resource returned in API responses.
        flow_count: Number of flows whose container_id matches this project_id.
            Computed by ProjectService at read time — never written to storage.
    """

    name: str
    project_id: str = field(default_factory=lambda: str(uuid4()))
    description: str | None = None
    tags: list[str] = field(default_factory=list)
    created_on: datetime = field(default_factory=lambda: datetime.now(UTC))
    modified_on: datetime = field(default_factory=lambda: datetime.now(UTC))
    created_by: str | None = None
    modified_by: str | None = None
    href: str | None = None
    # Computed at read time — not persisted to storage
    flow_count: int = 0

    def update_timestamp(self) -> None:
        """Update modified_on to current UTC time."""
        self.modified_on = datetime.now(UTC)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dictionary of all persisted fields.

        Called by the persistence adapter when writing a project to storage.
        flow_count is excluded — it is derived at read time and never stored.

        Returns:
            Dictionary of all persisted project fields with datetime values
            serialised to ISO 8601 strings.
        """
        return {
            "project_id": self.project_id,
            "name": self.name,
            "description": self.description,
            "tags": self.tags,
            "created_on": self.created_on.isoformat(),
            "modified_on": self.modified_on.isoformat(),
            "created_by": self.created_by,
            "modified_by": self.modified_by,
            "href": self.href,
        }

    @classmethod
    def from_dict(cls, *, data: dict[str, Any]) -> "Project":
        """Reconstruct a Project from a persisted dictionary.

        Called by the persistence adapter when reading a project from storage.
        ISO 8601 datetime strings are parsed back to timezone-aware datetime
        objects. flow_count is not stored, so it defaults to 0 on load and is
        computed by ProjectService before the project is returned to the caller.

        Args:
            data: Dictionary loaded from JSON storage, as written by to_dict().

        Returns:
            Project instance ready for use by the application layer.
        """
        parsed: dict[str, Any] = dict(data)
        for ts_field in ("created_on", "modified_on"):
            value = parsed.get(ts_field)
            if isinstance(value, str):
                parsed[ts_field] = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return cls(**parsed)
