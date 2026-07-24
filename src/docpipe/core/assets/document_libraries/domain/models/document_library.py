"""Document Library domain model.

This module contains the core domain model for Document Library,
representing a collection of Document Sets.
"""

import re
from dataclasses import dataclass, field
from uuid import uuid4

from docpipe.core.constants.constants import DocumentLibraryConstants
from docpipe.exceptions.docpipe_exceptions import DocpipeException
from docpipe.exceptions.error_codes import ErrorCode


@dataclass
class DocumentLibrary:
    """Domain model representing a Document Library.

    A Document Library is a collection of Document Sets that provides
    organizational structure.

    Attributes:
        library_id: Unique identifier for the library (UUID)
        name: Human-readable name (unique, required, max 256 chars)
        description: Optional description (max 1024 chars)
        purpose: Optional additional information (max 1024 chars)
        original_size: Optional input size in bytes
        final_size: Optional processed size in bytes
        tags: Optional list of tags
        created_by: Optional username of creator
        href: Optional hyperlink reference
        document_set_ids: List of document set IDs in this library
    """

    library_id: str
    name: str
    description: str | None = None
    purpose: str | None = None
    original_size: int | None = None
    final_size: int | None = None
    tags: list[str] = field(default_factory=list)
    created_by: str | None = None
    href: str | None = None
    document_set_ids: list[str] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        *,
        name: str,
        description: str | None = None,
        purpose: str | None = None,
        original_size: int | None = None,
        final_size: int | None = None,
        tags: list[str] | None = None,
        library_id: str | None = None,
        created_by: str | None = None,
        href: str | None = None,
    ) -> "DocumentLibrary":
        """Create a new DocumentLibrary instance.

        Args:
            name: Library name (required, max 256 chars)
            description: Optional description (max 1024 chars)
            purpose: Optional purpose/additional info (max 1024 chars)
            original_size: Optional input size in bytes
            final_size: Optional processed size in bytes
            tags: Optional list of tags
            library_id: Optional custom ID (generates UUID if not provided)
            created_by: Optional username of creator
            href: Optional hyperlink reference

        Returns:
            New DocumentLibrary instance

        Raises:
            DocumentLibraryInvalidDataException: If validation fails
        """
        library = cls(
            library_id=library_id or str(uuid4()),
            name=name,
            description=description,
            purpose=purpose,
            original_size=original_size,
            final_size=final_size,
            tags=tags or [],
            created_by=created_by,
            href=href,
            document_set_ids=[],
        )
        library.validate()
        return library

    def validate(self) -> None:  # NOSONAR python:S3776
        """Validate the document library data.

        Raises:
            DocpipeException: If validation fails
        """
        # Validate library_id
        if not self.library_id or not isinstance(self.library_id, str):
            raise DocpipeException(
                "Field 'library_id' must be a non-empty string",
                status_code=400,
                error_code=ErrorCode.DOCUMENT_LIBRARY_INVALID_DATA,
            )

        # Validate name
        if not self.name or not isinstance(self.name, str):
            raise DocpipeException(
                "Field 'name' must be a non-empty string",
                status_code=400,
                error_code=ErrorCode.DOCUMENT_LIBRARY_INVALID_DATA,
            )

        # Validate name: must start with alphabetic character
        if not self.name[0].isalpha():
            raise DocpipeException(
                "Field 'name' must start with an alphabetic character",
                status_code=400,
                error_code=ErrorCode.DOCUMENT_LIBRARY_INVALID_DATA,
            )

        # Validate name: must match pattern (letters, digits, spaces, underscores only)
        if not re.match(DocumentLibraryConstants.NAME_PATTERN, self.name):
            raise DocpipeException(
                "Field 'name' can only contain letters, digits, spaces, and underscores",
                status_code=400,
                error_code=ErrorCode.DOCUMENT_LIBRARY_INVALID_DATA,
            )

        if len(self.name) > DocumentLibraryConstants.MAX_NAME_LENGTH:
            raise DocpipeException(
                f"Field 'name' must not exceed {DocumentLibraryConstants.MAX_NAME_LENGTH} characters",
                status_code=400,
                error_code=ErrorCode.DOCUMENT_LIBRARY_INVALID_DATA,
            )

        # Validate description if provided
        if self.description is not None:
            if not isinstance(self.description, str):
                raise DocpipeException(
                    "Field 'description' must be a string",
                    status_code=400,
                    error_code=ErrorCode.DOCUMENT_LIBRARY_INVALID_DATA,
                )

            if len(self.description) > DocumentLibraryConstants.MAX_DESCRIPTION_LENGTH:
                raise DocpipeException(
                    f"Field 'description' must not exceed {DocumentLibraryConstants.MAX_DESCRIPTION_LENGTH} characters",
                    status_code=400,
                    error_code=ErrorCode.DOCUMENT_LIBRARY_INVALID_DATA,
                )

        # Validate purpose if provided
        if self.purpose is not None:
            if not isinstance(self.purpose, str):
                raise DocpipeException(
                    "Field 'purpose' must be a string",
                    status_code=400,
                    error_code=ErrorCode.DOCUMENT_LIBRARY_INVALID_DATA,
                )

            if len(self.purpose) > DocumentLibraryConstants.MAX_PURPOSE_LENGTH:
                raise DocpipeException(
                    f"Field 'purpose' must not exceed {DocumentLibraryConstants.MAX_PURPOSE_LENGTH} characters",
                    status_code=400,
                    error_code=ErrorCode.DOCUMENT_LIBRARY_INVALID_DATA,
                )

        # Validate original_size if provided
        if self.original_size is not None:
            if not isinstance(self.original_size, int) or self.original_size < 0:
                raise DocpipeException(
                    "Field 'original_size' must be a non-negative integer",
                    status_code=400,
                    error_code=ErrorCode.DOCUMENT_LIBRARY_INVALID_DATA,
                )
            if self.original_size > DocumentLibraryConstants.MAX_SAFE_INTEGER:
                raise DocpipeException(
                    f"Field 'original_size' must not exceed {DocumentLibraryConstants.MAX_SAFE_INTEGER} (MAX_SAFE_INTEGER)",
                    status_code=400,
                    error_code=ErrorCode.DOCUMENT_LIBRARY_INVALID_DATA,
                )

        # Validate final_size if provided
        if self.final_size is not None:
            if not isinstance(self.final_size, int) or self.final_size < 0:
                raise DocpipeException(
                    "Field 'final_size' must be a non-negative integer",
                    status_code=400,
                    error_code=ErrorCode.DOCUMENT_LIBRARY_INVALID_DATA,
                )
            if self.final_size > DocumentLibraryConstants.MAX_SAFE_INTEGER:
                raise DocpipeException(
                    f"Field 'final_size' must not exceed {DocumentLibraryConstants.MAX_SAFE_INTEGER} (MAX_SAFE_INTEGER)",
                    status_code=400,
                    error_code=ErrorCode.DOCUMENT_LIBRARY_INVALID_DATA,
                )

        # Validate tags if provided
        if not isinstance(self.tags, list):
            raise DocpipeException(
                "Field 'tags' must be a list",
                status_code=400,
                error_code=ErrorCode.DOCUMENT_LIBRARY_INVALID_DATA,
            )

        for tag in self.tags:
            if not isinstance(tag, str):
                raise DocpipeException(
                    "Field 'tags' - all tags must be strings",
                    status_code=400,
                    error_code=ErrorCode.DOCUMENT_LIBRARY_INVALID_DATA,
                )

        # Validate created_by if provided
        if self.created_by is not None:
            if not isinstance(self.created_by, str):
                raise DocpipeException(
                    "Field 'created_by' must be a string",
                    status_code=400,
                    error_code=ErrorCode.DOCUMENT_LIBRARY_INVALID_DATA,
                )
            if len(self.created_by) > DocumentLibraryConstants.MAX_CREATED_BY_LENGTH:
                raise DocpipeException(
                    f"Field 'created_by' must not exceed {DocumentLibraryConstants.MAX_CREATED_BY_LENGTH} characters",
                    status_code=400,
                    error_code=ErrorCode.DOCUMENT_LIBRARY_INVALID_DATA,
                )

        # Validate href if provided
        if self.href is not None:
            if not isinstance(self.href, str):
                raise DocpipeException(
                    "Field 'href' must be a string",
                    status_code=400,
                    error_code=ErrorCode.DOCUMENT_LIBRARY_INVALID_DATA,
                )
            if (
                len(self.href) < DocumentLibraryConstants.MIN_HREF_LENGTH
                or len(self.href) > DocumentLibraryConstants.MAX_HREF_LENGTH
            ):
                raise DocpipeException(
                    f"Field 'href' must be between {DocumentLibraryConstants.MIN_HREF_LENGTH} and {DocumentLibraryConstants.MAX_HREF_LENGTH} characters",
                    status_code=400,
                    error_code=ErrorCode.DOCUMENT_LIBRARY_INVALID_DATA,
                )

        # Validate document_set_ids
        if not isinstance(self.document_set_ids, list):
            raise DocpipeException(
                "Field 'document_set_ids' must be a list",
                status_code=400,
                error_code=ErrorCode.DOCUMENT_LIBRARY_INVALID_DATA,
            )

        for set_id in self.document_set_ids:
            if not isinstance(set_id, str) or not set_id:
                raise DocpipeException(
                    "Field 'document_set_ids' - all document set IDs must be non-empty strings",
                    status_code=400,
                    error_code=ErrorCode.DOCUMENT_LIBRARY_INVALID_DATA,
                )

    def add_document_set(self, *, document_set_id: str) -> None:
        """Add a document set to the library.

        Args:
            document_set_id: ID of the document set to add

        Raises:
            DocpipeException: If document_set_id is invalid or already exists
        """
        if not document_set_id or not isinstance(document_set_id, str):
            raise DocpipeException(
                "Field 'document_set_id' must be a non-empty string",
                status_code=400,
                error_code=ErrorCode.DOCUMENT_LIBRARY_INVALID_DATA,
            )

        if document_set_id in self.document_set_ids:
            raise DocpipeException(
                f"Document set {document_set_id} already exists in library",
                status_code=400,
                error_code=ErrorCode.DOCUMENT_LIBRARY_INVALID_DATA,
            )

        self.document_set_ids.append(document_set_id)

    def remove_document_set(self, *, document_set_id: str) -> None:
        """Remove a document set from the library.

        Args:
            document_set_id: ID of the document set to remove

        Raises:
            DocpipeException: If document_set_id doesn't exist in library
        """
        if document_set_id not in self.document_set_ids:
            raise DocpipeException(
                f"Document set {document_set_id} not found in library",
                status_code=404,
                error_code=ErrorCode.DOCUMENT_SET_NOT_FOUND,
            )

        self.document_set_ids.remove(document_set_id)

    def has_document_set(self, *, document_set_id: str) -> bool:
        """Check if a document set exists in the library.

        Args:
            document_set_id: ID of the document set to check

        Returns:
            True if document set exists in library, False otherwise
        """
        return document_set_id in self.document_set_ids

    def get_document_set_count(self) -> int:
        """Get the count of document sets in the library.

        Returns:
            Number of document sets
        """
        return len(self.document_set_ids)
