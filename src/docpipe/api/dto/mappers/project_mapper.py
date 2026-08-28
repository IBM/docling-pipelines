"""ProjectMapper — bidirectional conversion between Project DTOs and domain model."""

from docpipe.api.dto.project_dto import (
    ProjectCreateRequest,
    ProjectResponse,
    ProjectUpdateRequest,
)
from docpipe.core.projects.domain.models.project import Project


class ProjectMapper:
    """Static mapper for converting between Project DTOs and the domain model.

    Keeps conversion logic out of the route handler (thin router pattern),
    consistent with FlowMapper.
    """

    @staticmethod
    def create_request_to_domain(dto: ProjectCreateRequest) -> Project:
        """Convert a ProjectCreateRequest DTO to a Project domain model.

        Args:
            dto: Validated inbound create request.

        Returns:
            Project instance with auto-generated project_id and timestamps.
        """
        return Project(
            name=dto.name,
            description=dto.description,
            tags=dto.tags or [],
            created_by=dto.created_by,
        )

    @staticmethod
    def update_request_to_domain(
        *,
        project_id: str,
        existing: Project,
        dto: ProjectUpdateRequest,
    ) -> Project:
        """Convert a ProjectUpdateRequest DTO into a full-replace Project.

        Preserves immutable fields (project_id, created_on, created_by) from
        the existing domain model.

        Args:
            project_id: UUID of the project being updated.
            existing: Current domain model loaded from storage.
            dto: Validated inbound update request.

        Returns:
            Project instance ready to be passed to ProjectService.update_project().
        """
        return Project(
            project_id=project_id,
            name=dto.name,
            description=dto.description,
            tags=dto.tags or [],
            created_on=existing.created_on,
            created_by=existing.created_by,
            modified_by=dto.modified_by,
        )

    @staticmethod
    def domain_to_dto(domain: Project) -> ProjectResponse:
        """Convert a Project domain model to a ProjectResponse DTO.

        Args:
            domain: Project domain model (flow_count must already be populated
                by ProjectService before calling this method).

        Returns:
            ProjectResponse DTO ready for serialisation.
        """
        return ProjectResponse(
            project_id=domain.project_id,
            name=domain.name,
            description=domain.description,
            tags=domain.tags,
            flow_count=domain.flow_count,
            created_on=domain.created_on,
            modified_on=domain.modified_on,
            created_by=domain.created_by,
            modified_by=domain.modified_by,
            href=domain.href,
        )
