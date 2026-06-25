"""Port interface for Document Library repository.

This defines the contract that any Document Library repository adapter must implement.
Following the hexagonal architecture pattern, this is a port in the domain layer.
"""

from abc import ABC, abstractmethod
from typing import Any

from docpipe.core.assets.document_libraries.domain.models.document_library import DocumentLibrary
from docpipe.core.assets.document_libraries.domain.types import HealthCheckResult


class DocumentLibraryRepository(ABC):
    """Abstract repository interface for Document Library persistence.

    This port defines the contract for storing and retrieving document libraries.
    Concrete implementations (adapters) will provide specific storage mechanisms
    (DuckDB, PostgreSQL, etc.).
    """

    @abstractmethod
    def create(self, *, library: DocumentLibrary) -> DocumentLibrary:
        """Create a new document library.

        Args:
            library: DocumentLibrary entity to create

        Returns:
            The created library with updated metadata

        Raises:
            DocumentLibraryAlreadyExistsException: If library with same name exists
            DocumentLibraryStorageException: If storage operation fails
        """
        pass

    @abstractmethod
    def get_by_id(self, *, library_id: str) -> DocumentLibrary | None:
        """Retrieve a document library by its ID.

        Args:
            library_id: Unique identifier of the library

        Returns:
            DocumentLibrary entity if found, None otherwise

        Raises:
            DocumentLibraryStorageException: If storage operation fails
        """
        pass

    @abstractmethod
    def get_by_name(self, *, name: str) -> DocumentLibrary | None:
        """Retrieve a document library by its name.

        Args:
            name: Name of the library

        Returns:
            DocumentLibrary entity if found, None otherwise

        Raises:
            DocumentLibraryStorageException: If storage operation fails
        """
        pass

    @abstractmethod
    def update(self, *, library: DocumentLibrary) -> DocumentLibrary:
        """Update an existing document library.

        Args:
            library: DocumentLibrary entity with updated data

        Returns:
            Updated library

        Raises:
            DocumentLibraryNotFoundException: If library doesn't exist
            DocumentLibraryStorageException: If storage operation fails
        """
        pass

    @abstractmethod
    def delete(self, *, library_id: str) -> bool:
        """Delete a document library by its ID.

        Args:
            library_id: Unique identifier of the library to delete

        Returns:
            True if library was deleted, False if not found

        Raises:
            DocumentLibraryStorageException: If storage operation fails
        """
        pass

    @abstractmethod
    def list_all(
        self,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[DocumentLibrary]:
        """Retrieve all document libraries with optional pagination.

        Args:
            limit: Maximum number of libraries to return (None for all)
            offset: Number of libraries to skip (for pagination)

        Returns:
            List of document libraries

        Raises:
            DocumentLibraryStorageException: If storage operation fails
        """
        pass

    @abstractmethod
    def exists(self, *, library_id: str) -> bool:
        """Check if a document library exists.

        Args:
            library_id: Unique identifier of the library

        Returns:
            True if library exists, False otherwise

        Raises:
            DocumentLibraryStorageException: If storage operation fails
        """
        pass

    @abstractmethod
    def exists_by_name(self, *, name: str) -> bool:
        """Check if a document library with given name exists.

        Args:
            name: Name of the library

        Returns:
            True if library with name exists, False otherwise

        Raises:
            DocumentLibraryStorageException: If storage operation fails
        """
        pass

    @abstractmethod
    def add_document_set_to_library(
        self,
        *,
        library_id: str,
        document_set_id: str,
    ) -> None:
        """Add a document set to a library (junction table operation).

        Args:
            library_id: ID of the library
            document_set_id: ID of the document set to add

        Raises:
            DocumentLibraryNotFoundException: If library doesn't exist
            DocumentLibraryStorageException: If storage operation fails
        """
        pass

    @abstractmethod
    def remove_document_set_from_library(
        self,
        *,
        library_id: str,
        document_set_id: str,
    ) -> None:
        """Remove a document set from a library (junction table operation).

        Args:
            library_id: ID of the library
            document_set_id: ID of the document set to remove

        Raises:
            DocumentLibraryNotFoundException: If library doesn't exist
            DocumentSetNotFoundException: If document set not in library
            DocumentLibraryStorageException: If storage operation fails
        """
        pass

    @abstractmethod
    def get_document_sets_for_library(
        self,
        *,
        library_id: str,
    ) -> list[str]:
        """Get all document set IDs associated with a library.

        Args:
            library_id: ID of the library

        Returns:
            List of document set IDs

        Raises:
            DocumentLibraryNotFoundException: If library doesn't exist
            DocumentLibraryStorageException: If storage operation fails
        """
        pass

    @abstractmethod
    def add_document_sets_bulk(
        self,
        *,
        library_id: str,
        document_set_ids: list[str],
    ) -> None:
        """Add multiple document sets to a library in a single database operation.

        This method should execute a single INSERT statement with multiple values,
        rather than N separate INSERT statements.

        Args:
            library_id: ID of the library
            document_set_ids: List of document set IDs to add

        Raises:
            DocumentLibraryNotFoundException: If library doesn't exist
            DocumentLibraryStorageException: If storage operation fails
        """
        pass

    @abstractmethod
    def remove_document_sets_bulk(
        self,
        *,
        library_id: str,
        document_set_ids: list[str],
    ) -> None:
        """Remove multiple document sets from a library in a single database operation.

        This method should execute a single DELETE statement with IN clause,
        rather than N separate DELETE statements.

        Args:
            library_id: ID of the library
            document_set_ids: List of document set IDs to remove

        Raises:
            DocumentLibraryNotFoundException: If library doesn't exist
            DocumentLibraryStorageException: If storage operation fails
        """
        pass

    @abstractmethod
    def count_all(self) -> int:
        """Count total number of document libraries.

        Returns:
            Total count of libraries

        Raises:
            DocumentLibraryStorageException: If storage operation fails
        """
        pass

    @abstractmethod
    def health_check(self) -> HealthCheckResult:
        """Check the health status of the repository.

        Returns:
            A dictionary containing health status information with keys:
            - healthy: bool indicating if the repository is operational
            - message: str with status description
            - details: optional dict with additional diagnostic information

        Raises:
            No exceptions should be raised; errors should be reflected in the result
        """
        pass

    @classmethod
    @abstractmethod
    def validate_config(cls, *, config: dict[str, Any]) -> list[str]:
        """Validate repository configuration.

            This class method validates configuration before instantiation,
            allowing early detection of configuration errors.

        Args:
            config: Configuration dictionary to validate

        Returns:
            List of validation error messages, empty if configuration is valid
        """

    pass
