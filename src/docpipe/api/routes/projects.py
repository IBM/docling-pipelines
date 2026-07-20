"""Project management API routes.

Provides REST API endpoints for project CRUD operations:
POST   /api/v1/projects                  — create project
GET    /api/v1/projects                  — list projects (paginated)
GET    /api/v1/projects/{project_id}     — get project by ID
PUT    /api/v1/projects/{project_id}     — full replace
PATCH  /api/v1/projects/{project_id}     — partial update
DELETE /api/v1/projects/{project_id}     — delete project

Error handling is delegated to the service layer which raises typed
DocpipeException subclasses; the existing docpipe_exception_handler
middleware converts these to ErrorResponse DTOs automatically.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request

from docpipe.api.dependencies import get_project_service
from docpipe.api.dto.error_dto import ErrorResponse
from docpipe.api.dto.field_definitions import (
    LIMIT_MAX,
    LIMIT_MIN,
    NAME_MAX_LENGTH,
    NAME_MIN_LENGTH,
    OFFSET_MAX,
    OFFSET_MIN,
    TAG_MAX_LENGTH,
    TAG_MIN_LENGTH,
    TAG_PATTERN,
    UUID_LENGTH,
    UUID_PATTERN,
)
from docpipe.api.dto.mappers.project_mapper import ProjectMapper
from docpipe.api.dto.project_dto import (
    PaginatedProjectResponse,
    ProjectCreateRequest,
    ProjectPatchRequest,
    ProjectResponse,
    ProjectUpdateRequest,
)
from docpipe.core.projects.application.services.project_service import ProjectService
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger()

projects_router = APIRouter(prefix="/projects", tags=["Projects"])

# ── Path / query parameter type aliases ─────────────────────────────────

ProjectIdPath = Annotated[
    str,
    Path(
        description="Unique identifier for the project",
        min_length=UUID_LENGTH,
        max_length=UUID_LENGTH,
        pattern=UUID_PATTERN,
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    ),
]

_LimitQuery = Annotated[
    int,
    Query(
        description="Maximum number of projects to return",
        ge=LIMIT_MIN,
        le=LIMIT_MAX,
        examples=[100],
        json_schema_extra={"format": "int32"},
    ),
]

_OffsetQuery = Annotated[
    int,
    Query(
        description="Number of projects to skip",
        ge=OFFSET_MIN,
        le=OFFSET_MAX,
        examples=[0],
        json_schema_extra={"format": "int32"},
    ),
]

_NameQuery = Annotated[
    str | None,
    Query(
        description="Filter projects by name (partial match, case-insensitive)",
        min_length=NAME_MIN_LENGTH,
        max_length=NAME_MAX_LENGTH,
        examples=["invoice"],
    ),
]

_TagsQuery = Annotated[
    list[str] | None,
    Query(
        description="Filter projects by tags (returns projects with any of these tags)",
        examples=[["finance", "ml"]],
        json_schema_extra={
            "minItems": 0,
            "maxItems": 36,
            "items": {
                "type": "string",
                "minLength": TAG_MIN_LENGTH,
                "maxLength": TAG_MAX_LENGTH,
                "pattern": TAG_PATTERN,
            },
        },
    ),
]

ProjectServiceDep = Annotated[ProjectService, Depends(get_project_service)]


# ── Endpoints ───────────────────────────────────────────────────────────


@projects_router.post(
    "",
    response_model=ProjectResponse,
    status_code=201,
    operation_id="create_project",
    summary="Create a new project",
    responses={
        201: {"description": "Project created successfully"},
        400: {"model": ErrorResponse, "description": "Validation error"},
        409: {"model": ErrorResponse, "description": "Project name already exists"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def create_project(
    body: ProjectCreateRequest,
    service: ProjectServiceDep,
) -> ProjectResponse:
    """Create and persist a new project.

    Args:
        body: Validated project creation request.
        service: Injected ProjectService.

    Returns:
        The created project with flow_count=0.
    """
    logger.debug("Creating project: %s", body.name)
    domain = ProjectMapper.create_request_to_domain(body)
    created = service.create_project(project=domain)
    logger.info("Created project %s", created.project_id)
    return ProjectMapper.domain_to_dto(created)


@projects_router.get(
    "",
    response_model=PaginatedProjectResponse,
    operation_id="list_projects",
    summary="List projects with pagination and filtering",
    responses={
        200: {"description": "Projects retrieved successfully"},
        400: {"model": ErrorResponse, "description": "Invalid query parameters"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def list_projects(
    request: Request,
    service: ProjectServiceDep,
    limit: _LimitQuery = 100,
    offset: _OffsetQuery = 0,
    name: _NameQuery = None,
    tags: _TagsQuery = None,
) -> PaginatedProjectResponse:
    """Return a paginated list of projects with optional name/tag filtering.

    Args:
        request: FastAPI request (used to build pagination links).
        service: Injected ProjectService.
        limit: Max items per page.
        offset: Items to skip.
        name: Optional name substring filter.
        tags: Optional tag filter (any-match).

    Returns:
        Paginated project list with navigation links.
    """
    logger.debug("Listing projects: offset=%d limit=%d name=%s tags=%s", offset, limit, name, tags)
    projects = service.list_projects(skip=offset, limit=limit, name_filter=name, tags_filter=tags)
    total = service.count_projects(name_filter=name, tags_filter=tags)

    base_url = str(request.url).split("?")[0]
    name_param = f"&name={name}" if name else ""
    first_link = f"{base_url}?offset=0&limit={limit}{name_param}"
    next_link = (
        f"{base_url}?offset={offset + limit}&limit={limit}{name_param}" if (offset + len(projects)) < total else None
    )
    prev_link = f"{base_url}?offset={max(0, offset - limit)}&limit={limit}{name_param}" if offset > 0 else None

    logger.info("Listed %d projects (total=%d)", len(projects), total)
    return PaginatedProjectResponse(
        projects=[ProjectMapper.domain_to_dto(p) for p in projects],
        total_count=total,
        offset=offset,
        limit=limit,
        first=first_link,
        next=next_link,
        prev=prev_link,
    )


@projects_router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    operation_id="get_project",
    summary="Get project by ID",
    responses={
        200: {"description": "Project retrieved successfully"},
        400: {"model": ErrorResponse, "description": "Invalid project_id format"},
        404: {"model": ErrorResponse, "description": "Project not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def get_project(
    project_id: ProjectIdPath,
    service: ProjectServiceDep,
) -> ProjectResponse:
    """Retrieve a single project by its UUID.

    Args:
        project_id: UUID of the project (validated by path param).
        service: Injected ProjectService.

    Returns:
        Project with current flow_count.
    """
    logger.debug("Getting project: %s", project_id)
    project = service.get_project(project_id=project_id)
    logger.info("Retrieved project %s", project_id)
    return ProjectMapper.domain_to_dto(project)


@projects_router.put(
    "/{project_id}",
    response_model=ProjectResponse,
    operation_id="replace_project",
    summary="Fully replace a project",
    responses={
        200: {"description": "Project updated successfully"},
        400: {"model": ErrorResponse, "description": "Validation error or invalid project_id"},
        404: {"model": ErrorResponse, "description": "Project not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def replace_project(
    project_id: ProjectIdPath,
    body: ProjectUpdateRequest,
    service: ProjectServiceDep,
) -> ProjectResponse:
    """Fully replace a project's mutable fields.

    Immutable fields (project_id, created_on, created_by) are preserved from
    the existing record.

    Args:
        project_id: UUID of the project to update.
        body: Validated full-replace request body.
        service: Injected ProjectService.

    Returns:
        The updated project.
    """
    logger.debug("Replacing project: %s", project_id)
    existing = service.get_project(project_id=project_id)
    domain = ProjectMapper.update_request_to_domain(project_id=project_id, existing=existing, dto=body)
    updated = service.update_project(project=domain)
    logger.info("Replaced project %s", project_id)
    return ProjectMapper.domain_to_dto(updated)


@projects_router.patch(
    "/{project_id}",
    response_model=ProjectResponse,
    operation_id="update_project",
    summary="Partially update a project",
    responses={
        200: {"description": "Project partially updated successfully"},
        400: {"model": ErrorResponse, "description": "Validation error or invalid project_id"},
        404: {"model": ErrorResponse, "description": "Project not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def update_project(
    project_id: ProjectIdPath,
    body: ProjectPatchRequest,
    service: ProjectServiceDep,
) -> ProjectResponse:
    """Partially update a project — only provided fields are changed.

    Args:
        project_id: UUID of the project to update.
        body: Validated partial-update request body.
        service: Injected ProjectService.

    Returns:
        The updated project.
    """
    logger.debug("Partially updating project: %s", project_id)
    updated = service.partial_update_project(project_id=project_id, updates=body.model_dump(exclude_unset=True))
    logger.info("Partially updated project %s", project_id)
    return ProjectMapper.domain_to_dto(updated)


@projects_router.delete(
    "/{project_id}",
    status_code=204,
    operation_id="delete_project",
    summary="Delete a project",
    responses={
        204: {"description": "Project deleted successfully"},
        400: {"model": ErrorResponse, "description": "Invalid project_id format"},
        404: {"model": ErrorResponse, "description": "Project not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def delete_project(
    project_id: ProjectIdPath,
    service: ProjectServiceDep,
) -> None:
    """Delete a project and all flows linked to it via container_id.

    Cascade-deletes every flow whose container_id matches the project_id
    before removing the project record. Individual flow deletion failures
    are logged as warnings but do not block the project deletion.

    Args:
        project_id: UUID of the project to delete.
        service: Injected ProjectService.

    Returns:
        204 No Content on success.
    """
    logger.debug("Deleting project: %s", project_id)
    service.delete_project(project_id=project_id)
    logger.info("Deleted project %s", project_id)
    return None
