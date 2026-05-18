"""Application service for document library management operations.

Provides CRUD operations for document libraries with validation, filtering, and pagination.
Orchestrates business logic between domain models and repository layer.
"""

import logging
from typing import ClassVar

from datasift.core.assets.document_libraries.domain.models.document_library import DocumentLibrary
from datasift.core.assets.document_libraries.domain.ports.document_library_repository import (
    DocumentLibraryRepository,
)
from datasift.exceptions.datasift_exceptions import DatasiftException
from datasift.exceptions.error_codes import ErrorCode

logger = logging.getLogger(__name__)


class DocumentLibraryService:
    """Application service for creating, retrieving, updating, and deleting document libraries.

    Uses dependency injection to receive a repository implementation.
    Orchestrates business logic and coordinates between domain and infrastructure layers.
    """

    # Fields that can be updated via partial updates
    UPDATABLE_FIELDS: ClassVar[set[str]] = {
        "name",
        "description",
        "purpose",
        "original_size",
        "final_size",
        "tags",
        "created_by",
        "href",
    }

    # Fields that cannot be modified after creation
    PROTECTED_FIELDS: ClassVar[set[str]] = {
        "library_id",
        "document_set_ids",
    }

    def __init__(self, *, repository: DocumentLibraryRepository):
        """Initialize the service with a document library repository.

        Args:
            repository: Repository implementation for persistence
        """
        self.repository = repository
        logger.debug(msg=f"DocumentLibraryService initialized with repository: {type(repository).__name__}")

    def _validate_library_id(self, *, library_id: str) -> str:
        """Validate that library_id is not None, empty, or whitespace.

        Args:
            library_id: The library identifier to validate

        Returns:
            The validated library_id

        Raises:
            DatasiftException: If library_id is invalid
        """
        if not library_id or not library_id.strip():
            raise DatasiftException(
                "library_id cannot be empty",
                status_code=400,
                error_code=ErrorCode.DOCUMENT_LIBRARY_INVALID_DATA,
            )
        return library_id

    def create_library(
        self,
        *,
        name: str,
        description: str | None = None,
        purpose: str | None = None,
        original_size: int | None = None,
        final_size: int | None = None,
        tags: list[str] | None = None,
        created_by: str | None = None,
        href: str | None = None,
    ) -> DocumentLibrary:
        """Create and store a new document library.

        Creates a new library with validation and duplicate prevention.
        Ensures libraries with duplicate names cannot be created.

        Args:
            name: Library name (required, max 256 chars, must be unique)
            description: Optional description (max 1024 chars)
            purpose: Optional additional information (max 1024 chars)
            original_size: Optional input size in bytes
            final_size: Optional processed size in bytes
            tags: Optional list of tags
            created_by: Optional username of creator
            href: Optional hyperlink reference

        Returns:
            The created library with generated metadata

        Raises:
            DocumentLibraryAlreadyExistsException: If library with same name exists
            DocumentLibraryInvalidDataException: If validation fails
            DocumentLibraryStorageException: If storage operation fails

        Example:
            >>> library = service.create_library(
            ...     name="Research Papers",
            ...     description="Collection of research documents",
            ...     purpose="Academic research",
            ...     tags=["research", "academic"]
            ... )
            >>> print(library.library_id)  # Auto-generated UUID
        """
        try:
            # Create domain entity (will validate and generate ID)
            library = DocumentLibrary.create(
                name=name,
                description=description,
                purpose=purpose,
                original_size=original_size,
                final_size=final_size,
                tags=tags or [],
                created_by=created_by,
                href=href,
            )

            logger.info(msg=f"Creating library with name: {library.name}")

            # Repository will check for duplicate names
            created_library = self.repository.create(library=library)

            logger.info(msg=f"Successfully created library {created_library.library_id} with name {created_library.name}")
            return created_library

        except DatasiftException:
            raise

    def get_library(self, *, library_id: str) -> DocumentLibrary:
        """Retrieve a document library by ID.

        Fetches a single library from the repository by its unique identifier.

        Args:
            library_id: Unique identifier of the library

        Returns:
            The requested library entity with all properties

        Raises:
            DocumentLibraryInvalidDataException: If library_id is invalid
            DocumentLibraryNotFoundException: If library doesn't exist
            DocumentLibraryStorageException: If retrieval fails

        Example:
            >>> library = service.get_library(library_id="abc-123")
            >>> print(f"Library: {library.name}")
            >>> print(f"Document sets: {len(library.document_set_ids)}")
        """
        self._validate_library_id(library_id=library_id)

        library = self.repository.get_by_id(library_id=library_id)

        if library is None:
            raise DatasiftException(
                f"Library {library_id} not found",
                status_code=404,
                error_code=ErrorCode.DOCUMENT_LIBRARY_NOT_FOUND,
            )

        logger.info(msg=f"Successfully retrieved library {library_id}")
        return library

    def get_library_by_name(self, *, name: str) -> DocumentLibrary:
        """Retrieve a document library by name.

        Args:
            name: Name of the library

        Returns:
            The requested library entity

        Raises:
            DocumentLibraryNotFoundException: If library doesn't exist
            DocumentLibraryStorageException: If retrieval fails

        Example:
            >>> library = service.get_library_by_name(name="Research Papers")
        """
        if not name or not name.strip():
            raise DatasiftException(
                "Library name cannot be empty",
                status_code=400,
                error_code=ErrorCode.DOCUMENT_LIBRARY_INVALID_DATA,
            )

        library = self.repository.get_by_name(name=name)

        if library is None:
            raise DatasiftException(
                f"Library with name '{name}' not found",
                status_code=404,
                error_code=ErrorCode.DOCUMENT_LIBRARY_NOT_FOUND,
            )

        logger.info(msg=f"Successfully retrieved library by name: {name}")
        return library

    def update_library(
        self,
        *,
        library_id: str,
        name: str | None = None,
        description: str | None = None,
        purpose: str | None = None,
        original_size: int | None = None,
        final_size: int | None = None,
        tags: list[str] | None = None,
        created_by: str | None = None,
        href: str | None = None,
    ) -> DocumentLibrary:
        """Update an existing document library.

        Performs partial update of library metadata. Only provided fields are updated.

        Args:
            library_id: ID of the library to update
            name: New name (optional, must be unique if provided)
            description: New description (optional)
            purpose: New purpose (optional)
            original_size: New original size (optional)
            final_size: New final size (optional)
            tags: New tags list (optional)
            created_by: New created_by (optional)
            href: New href (optional)

        Returns:
            The updated library

        Raises:
            DocumentLibraryNotFoundException: If library doesn't exist
            DocumentLibraryInvalidDataException: If validation fails
            DocumentLibraryStorageException: If update fails

        Example:
            >>> updated = service.update_library(
            ...     library_id="abc-123",
            ...     name="Updated Name",
            ...     description="New description",
            ...     tags=["updated", "tags"]
            ... )
        """
        self._validate_library_id(library_id=library_id)

        # Get existing library
        library = self.get_library(library_id=library_id)

        # Update fields if provided
        if name is not None:
            library.name = name
        if description is not None:
            library.description = description
        if purpose is not None:
            library.purpose = purpose
        if original_size is not None:
            library.original_size = original_size
        if final_size is not None:
            library.final_size = final_size
        if tags is not None:
            library.tags = tags
        if created_by is not None:
            library.created_by = created_by
        if href is not None:
            library.href = href

        # Validate updated library
        library.validate()

        # Save updates
        updated_library = self.repository.update(library=library)

        logger.info(msg=f"Successfully updated library {library_id}")
        return updated_library

    def delete_library(self, *, library_id: str) -> bool:
        """Delete a document library by ID.

        Removes the library and all its document set associations.
        The actual document sets are not deleted, only the relationships.

        Args:
            library_id: ID of the library to delete

        Returns:
            True if library was deleted, False if not found

        Raises:
            DocumentLibraryStorageException: If deletion fails

        Example:
            >>> deleted = service.delete_library(library_id="abc-123")
            >>> if deleted:
            ...     print("Library deleted successfully")
        """
        self._validate_library_id(library_id=library_id)

        deleted = self.repository.delete(library_id=library_id)

        if deleted:
            logger.info(msg=f"Successfully deleted library {library_id}")
        else:
            logger.warning(msg=f"Library {library_id} not found for deletion")

        return deleted

    def list_libraries(
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
            List of document libraries ordered by creation date (newest first)

        Raises:
            DocumentLibraryStorageException: If retrieval fails

        Example:
            >>> # Get all libraries
            >>> all_libs = service.list_libraries()
            >>>
            >>> # Get first page (10 items)
            >>> page1 = service.list_libraries(limit=10, offset=0)
            >>>
            >>> # Get second page
            >>> page2 = service.list_libraries(limit=10, offset=10)
        """
        libraries = self.repository.list_all(limit=limit, offset=offset)

        logger.info(msg=f"Retrieved {len(libraries)} libraries")
        return libraries

    def library_exists(self, *, library_id: str) -> bool:
        """Check if a document library exists.

        Lightweight existence check without loading full library data.

        Args:
            library_id: ID of the library to check

        Returns:
            True if library exists, False otherwise

        Raises:
            DocumentLibraryStorageException: If check fails

        Example:
            >>> if service.library_exists(library_id="abc-123"):
            ...     print("Library exists")
        """
        self._validate_library_id(library_id=library_id)
        return self.repository.exists(library_id=library_id)

    def library_exists_by_name(self, *, name: str) -> bool:
        """Check if a library with given name exists.

        Args:
            name: Name to check

        Returns:
            True if library with name exists, False otherwise

        Raises:
            DocumentLibraryStorageException: If check fails
        """
        if not name or not name.strip():
            return False
        return self.repository.exists_by_name(name=name)

    def add_document_set(self, *, library_id: str, document_set_id: str) -> DocumentLibrary:
        """Add a document set to a library.

        Creates a relationship between the library and document set.
        Updates the library's document_set_ids list.

        Args:
            library_id: ID of the library
            document_set_id: ID of the document set to add

        Returns:
            Updated library with new document set

        Raises:
            DocumentLibraryNotFoundException: If library doesn't exist
            DocumentLibraryInvalidDataException: If document set already in library
            DocumentLibraryStorageException: If operation fails

        Example:
            >>> library = service.add_document_set(
            ...     library_id="lib-123",
            ...     document_set_id="set-456"
            ... )
            >>> print(len(library.document_set_ids))  # Increased by 1
        """
        self._validate_library_id(library_id=library_id)

        # Get library and update domain model
        library = self.get_library(library_id=library_id)
        library.add_document_set(document_set_id=document_set_id)

        # Persist junction table entry
        self.repository.add_document_set_to_library(
            library_id=library_id,
            document_set_id=document_set_id,
        )

        logger.info(msg=f"Added document set {document_set_id} to library {library_id}")

        # Return updated library (re-fetch to get current state)
        return self.get_library(library_id=library_id)

    def remove_document_set(self, *, library_id: str, document_set_id: str) -> DocumentLibrary:
        """Remove a document set from a library.

        Removes the relationship between library and document set.
        The document set itself is not deleted, only the association.

        Args:
            library_id: ID of the library
            document_set_id: ID of the document set to remove

        Returns:
            Updated library without the document set

        Raises:
            DocumentLibraryNotFoundException: If library doesn't exist
            DocumentSetNotFoundException: If document set not in library
            DocumentLibraryStorageException: If operation fails

        Example:
            >>> library = service.remove_document_set(
            ...     library_id="lib-123",
            ...     document_set_id="set-456"
            ... )
        """
        self._validate_library_id(library_id=library_id)

        # Get library and update domain model
        library = self.get_library(library_id=library_id)
        library.remove_document_set(document_set_id=document_set_id)

        # Remove junction table entry
        self.repository.remove_document_set_from_library(
            library_id=library_id,
            document_set_id=document_set_id,
        )

        logger.info(msg=f"Removed document set {document_set_id} from library {library_id}")

        # Return updated library (re-fetch to get current state)
        return self.get_library(library_id=library_id)

    def add_document_sets_bulk(self, *, library_id: str, document_set_ids: list[str]) -> None:
        """Add multiple document sets to a library in bulk.

        Creates relationships between the library and multiple document sets.
        This is more efficient than calling add_document_set multiple times.

        Args:
            library_id: ID of the library
            document_set_ids: List of document set IDs to add

        Raises:
            DocumentLibraryNotFoundException: If library doesn't exist
            DocumentLibraryInvalidDataException: If any document set already in library
            DocumentLibraryStorageException: If operation fails

        Example:
            >>> service.add_document_sets_bulk(
            ...     library_id="lib-123",
            ...     document_set_ids=["set-1", "set-2", "set-3"]
            ... )
        """
        self._validate_library_id(library_id=library_id)

        if not document_set_ids:
            logger.warning(msg=f"No document sets provided for bulk add to library {library_id}")
            return

        # Get library to verify it exists
        library = self.get_library(library_id=library_id)

        # Add each document set
        for document_set_id in document_set_ids:
            try:
                library.add_document_set(document_set_id=document_set_id)
                self.repository.add_document_set_to_library(
                    library_id=library_id,
                    document_set_id=document_set_id,
                )
            except Exception:
                raise

        logger.info(msg=f"Added {len(document_set_ids)} document sets to library {library_id}")

    def remove_document_sets_bulk(self, *, library_id: str, document_set_ids: list[str]) -> None:
        """Remove multiple document sets from a library in bulk.

        Removes relationships between library and multiple document sets.
        The document sets themselves are not deleted, only the associations.

        Args:
            library_id: ID of the library
            document_set_ids: List of document set IDs to remove

        Raises:
            DocumentLibraryNotFoundException: If library doesn't exist
            DocumentSetNotFoundException: If any document set not in library
            DocumentLibraryStorageException: If operation fails

        Example:
            >>> service.remove_document_sets_bulk(
            ...     library_id="lib-123",
            ...     document_set_ids=["set-1", "set-2", "set-3"]
            ... )
        """
        self._validate_library_id(library_id=library_id)

        if not document_set_ids:
            logger.warning(msg=f"No document sets provided for bulk remove from library {library_id}")
            return

        # Get library to verify it exists
        library = self.get_library(library_id=library_id)

        # Remove each document set
        for document_set_id in document_set_ids:
            try:
                library.remove_document_set(document_set_id=document_set_id)
                self.repository.remove_document_set_from_library(
                    library_id=library_id,
                    document_set_id=document_set_id,
                )
            except Exception:
                raise

        logger.info(msg=f"Removed {len(document_set_ids)} document sets from library {library_id}")

    def get_document_sets(self, *, library_id: str) -> list[str]:
        """Get all document set IDs associated with a library.

        Args:
            library_id: ID of the library

        Returns:
            List of document set IDs

        Raises:
            DocumentLibraryNotFoundException: If library doesn't exist
            DocumentLibraryStorageException: If retrieval fails

        Example:
            >>> doc_sets = service.get_document_sets(library_id="lib-123")
            >>> print(f"Library has {len(doc_sets)} document sets")
        """
        self._validate_library_id(library_id=library_id)

        doc_sets = self.repository.get_document_sets_for_library(library_id=library_id)

        logger.info(msg=f"Retrieved {len(doc_sets)} document sets for library {library_id}")
        return doc_sets

    def count_libraries(self) -> int:
        """Count total number of document libraries.

        Returns:
            Total count of libraries

        Raises:
            DocumentLibraryStorageException: If count fails

        Example:
            >>> total = service.count_libraries()
            >>> print(f"Total libraries: {total}")
        """
        count = self.repository.count_all()
        logger.info(msg=f"Total libraries count: {count}")
        return count

