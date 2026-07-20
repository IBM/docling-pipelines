"""ProjectService — application service for project CRUD operations.

Coordinates between:
- ProjectRepository: persistence of project entities
- AssetRepository[Flow]: read-only access for flow_count computation
- FlowService: cascade-deletion of flows on project delete
"""

from typing import ClassVar

from docpipe.core.assets.common.domain.ports.asset_repository import AssetRepository
from docpipe.core.assets.flows.application.services.flow_service import FlowService
from docpipe.core.assets.flows.domain.models.flow import Flow
from docpipe.core.projects.domain.models.project import Project
from docpipe.core.projects.domain.ports.project_repository import ProjectRepository
from docpipe.exceptions.docpipe_exceptions import (
    ProjectAlreadyExistsException,
    ProjectInvalidDataException,
    ProjectNotFoundException,
)
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger()


class ProjectService:
    """CRUD service for Project entities with flow_count enrichment.

    Responsibilities:
    - Create, read, update, delete projects via the ProjectStore port
    - Enrich every returned Project with the current flow_count by scanning
      the flow repository for flows whose container_id matches the project_id
    - Enforce name uniqueness and field-level validation
    - Protect immutable fields (project_id, created_on, created_by)

    Args:
        store: ProjectStore implementation for persistence.
        flow_repository: Read-only flow repository used to compute flow_count.
    """

    UPDATABLE_FIELDS: ClassVar[set[str]] = {
        "name",
        "description",
        "tags",
        "modified_by",
        "href",
    }
    PROTECTED_FIELDS: ClassVar[set[str]] = {"project_id", "created_on", "created_by"}

    def __init__(
        self,
        *,
        repository: ProjectRepository,
        flow_repository: AssetRepository[Flow],
        flow_service: FlowService,
    ) -> None:
        self._repository = repository
        self._flow_repository = flow_repository
        self._flow_service = flow_service
        logger.debug("ProjectService initialised with repository: %s", type(repository).__name__)

    # ── CREATE ───────────────────────────────────────────────────────

    def create_project(self, *, project: Project) -> Project:
        """Create and persist a new project.

        Args:
            project: Project instance to create. project_id is auto-generated
                if not provided.

        Returns:
            The created project with flow_count=0.

        Raises:
            ProjectInvalidDataException: If name is empty or exceeds 255 chars.
            ProjectAlreadyExistsException: If a project with the same name exists.
        """
        self._validate_name(project.name)

        if self._repository.exists_by_name(name=project.name):
            logger.warning("Attempted to create duplicate project name: %s", project.name)
            raise ProjectAlreadyExistsException(project_name=project.name)

        saved = self._repository.save(project=project)
        saved.flow_count = 0  # brand-new project has no flows
        logger.info("Created project %s (%s)", saved.project_id, saved.name)
        return saved

    # ── GET ──────────────────────────────────────────────────────────

    def get_project(self, *, project_id: str) -> Project:
        """Retrieve a project by ID, enriched with flow_count.

        Args:
            project_id: UUID of the project.

        Returns:
            Project with current flow_count.

        Raises:
            ProjectNotFoundException: If no project with this ID exists.
        """
        project = self._repository.get(project_id=project_id)
        if project is None:
            raise ProjectNotFoundException(project_id=project_id)
        project.flow_count = self._count_flows_for(project_id=project_id)
        logger.debug("Retrieved project %s", project_id)
        return project

    # ── LIST ─────────────────────────────────────────────────────────

    def list_projects(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        name_filter: str | None = None,
        tags_filter: list[str] | None = None,
    ) -> list[Project]:
        """List projects with optional filtering and pagination.

        Args:
            skip: Number of items to skip (offset).
            limit: Maximum number of items to return.
            name_filter: Case-insensitive substring match on project name.
            tags_filter: Return projects that have at least one of these tags.

        Returns:
            Paginated list of projects, each enriched with flow_count.
        """
        projects = self._filter(self._repository.find_all(), name_filter, tags_filter)
        page = projects[skip : skip + limit]
        # Load flows once for the entire page instead of once per project.
        all_flows = self._flow_repository.find_all()
        for project in page:
            project.flow_count = sum(1 for f in all_flows if f.container_id == project.project_id)
        logger.debug("Listed %d projects (skip=%d, limit=%d)", len(page), skip, limit)
        return page

    def count_projects(
        self,
        *,
        name_filter: str | None = None,
        tags_filter: list[str] | None = None,
    ) -> int:
        """Count projects after applying filters (no pagination).

        Used to populate total_count in paginated list responses.

        Args:
            name_filter: Case-insensitive substring match on project name.
            tags_filter: Return projects that have at least one of these tags.

        Returns:
            Total number of matching projects.
        """
        return len(self._filter(self._repository.find_all(), name_filter, tags_filter))

    # ── FULL UPDATE ──────────────────────────────────────────────────

    def update_project(self, *, project: Project) -> Project:
        """Fully replace a project's mutable fields.

        Args:
            project: Project with updated data. Must carry the existing project_id.

        Returns:
            The updated project enriched with flow_count.

        Raises:
            ProjectNotFoundException: If no project with this ID exists.
        """
        if not self._repository.exists(project_id=project.project_id):
            raise ProjectNotFoundException(project_id=project.project_id)
        project.update_timestamp()
        updated = self._repository.update(project=project)
        updated.flow_count = self._count_flows_for(project_id=updated.project_id)
        logger.info("Updated project %s", updated.project_id)
        return updated

    # ── PARTIAL UPDATE ────────────────────────────────────────────────

    def partial_update_project(self, *, project_id: str, updates: dict) -> Project:
        """Apply a partial update, modifying only the provided fields.

        Protected fields (project_id, created_on, created_by) are silently
        stripped from updates before being applied.

        Args:
            project_id: UUID of the project to update.
            updates: Dictionary of fields to update (from PATCH body).

        Returns:
            The updated project enriched with flow_count.

        Raises:
            ProjectNotFoundException: If no project with this ID exists.
            ProjectInvalidDataException: If an updated name fails validation.
        """
        existing = self.get_project(project_id=project_id)  # raises 404 if missing

        # Strip immutable fields silently
        for field in self.PROTECTED_FIELDS:
            updates.pop(field, None)

        # Validate name if it is being updated
        if "name" in updates:
            self._validate_name(updates["name"])

        # Apply only allowed fields
        for key, value in updates.items():
            if key in self.UPDATABLE_FIELDS:
                setattr(existing, key, value)

        existing.update_timestamp()
        updated = self._repository.update(project=existing)
        updated.flow_count = self._count_flows_for(project_id=updated.project_id)
        logger.info("Partially updated project %s", updated.project_id)
        return updated

    # ── DELETE ───────────────────────────────────────────────────────

    def delete_project(self, *, project_id: str) -> None:
        """Delete a project and cascade-delete all flows linked to it.

        Finds all flows whose container_id matches project_id and bulk-deletes
        them before removing the project record. Individual flow deletion
        failures are logged as warnings but do not block the project deletion.

        Args:
            project_id: UUID of the project to delete.

        Raises:
            ProjectNotFoundException: If no project with this ID exists.
        """
        if not self._repository.exists(project_id=project_id):
            raise ProjectNotFoundException(project_id=project_id)

        # Cascade: delete all flows linked to this project
        flow_ids = [f.asset_id for f in self._flow_repository.find_all() if f.container_id == project_id and f.asset_id]
        if flow_ids:
            result = self._flow_service.bulk_delete_flows(flow_ids=flow_ids)
            if result.get("total_failed", 0):
                logger.warning(
                    "Deleted project %s but %d linked flow(s) could not be removed: %s",
                    project_id,
                    result["total_failed"],
                    [f["flow_id"] for f in result.get("failed", [])],
                )
            else:
                logger.info(
                    "Cascade-deleted %d flow(s) for project %s",
                    result["total_deleted"],
                    project_id,
                )

        self._repository.delete(project_id=project_id)
        logger.info("Deleted project %s", project_id)

    # ── PRIVATE ──────────────────────────────────────────────────────

    def _count_flows_for(self, *, project_id: str | None) -> int:
        """Count flows whose container_id matches this project_id."""
        if not project_id:
            return 0
        return sum(1 for f in self._flow_repository.find_all() if f.container_id == project_id)

    @staticmethod
    def _validate_name(name: str | None) -> None:
        """Validate project name: non-empty and <= 255 chars."""
        if not name or not name.strip():
            raise ProjectInvalidDataException("Project name cannot be empty", field_name="name")
        if len(name) > 255:
            raise ProjectInvalidDataException("Project name cannot exceed 255 characters", field_name="name")

    @staticmethod
    def _filter(
        projects: list[Project],
        name_filter: str | None,
        tags_filter: list[str] | None,
    ) -> list[Project]:
        """Apply name and tag filters to a project list."""
        if name_filter:
            name_lower = name_filter.lower()
            projects = [p for p in projects if name_lower in p.name.lower()]
        if tags_filter:
            projects = [p for p in projects if any(t in p.tags for t in tags_filter)]
        return projects
