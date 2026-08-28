"""ProjectRepository port — abstract interface for project persistence.

Implementations:
- LocalProjectRepository: filesystem JSON files (OSS default)
- Future: CamsProjectRepository, PostgresProjectRepository
"""

from abc import ABC, abstractmethod

from docpipe.core.projects.domain.models.project import Project


class ProjectRepository(ABC):
    """Abstract repository interface for Project persistence.

    Defines the contract all project storage adapters must implement.
    Intentionally kept minimal — only the operations required by
    ProjectService are declared here.
    """

    @abstractmethod
    def save(self, *, project: Project) -> Project:
        """Persist a new project.

        Args:
            project: Project instance to save.

        Returns:
            The saved project (same instance, timestamps may be updated).

        Raises:
            Exception: If the save operation fails.
        """

    @abstractmethod
    def get(self, *, project_id: str) -> Project | None:
        """Retrieve a project by ID.

        Args:
            project_id: UUID of the project.

        Returns:
            Project if found, None otherwise.
        """

    @abstractmethod
    def find_all(self) -> list[Project]:
        """Retrieve all projects.

        Returns:
            List of all stored projects (flow_count defaults to 0).
        """

    @abstractmethod
    def update(self, *, project: Project) -> Project:
        """Overwrite an existing project.

        Args:
            project: Project instance with updated data.

        Returns:
            The updated project.

        Raises:
            Exception: If the update operation fails.
        """

    @abstractmethod
    def delete(self, *, project_id: str) -> bool:
        """Delete a project by ID.

        Args:
            project_id: UUID of the project to delete.

        Returns:
            True if deleted, False if not found.
        """

    @abstractmethod
    def exists(self, *, project_id: str) -> bool:
        """Check whether a project exists by ID.

        Args:
            project_id: UUID of the project.

        Returns:
            True if the project exists.
        """

    @abstractmethod
    def exists_by_name(self, *, name: str) -> bool:
        """Check whether a project with the given name exists.

        Args:
            name: Project name to check.

        Returns:
            True if a project with this name exists.
        """
