"""Document Library domain model.

This module contains the core domain model for Document Library,
representing a collection of Document Sets.

Now extends the unified Asset base class for consistency across all asset types
(Flow, DocumentSet, DocumentLibrary).
"""

import re
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from docpipe.core.assets.common.domain.models.asset import Asset
from docpipe.core.constants.asset_constants import AssetType
from docpipe.core.constants.constants import DocumentLibraryConstants
from docpipe.exceptions.docpipe_exceptions import DocpipeException
from docpipe.exceptions.error_codes import ErrorCode


@dataclass
class DocumentLibrary(Asset):
    """Domain model representing a Document Library extending unified Asset base class.

    A Document Library is a collection of Document Sets that provides
    organizational structure.

    Inherits from Asset:
        - asset_id: Unique identifier (aliased as library_id for backward compatibility)
        - name: Human-readable name (required)
        - description: Optional description

    DocumentLibrary-Specific Attributes:
        purpose: Optional additional information (max 1024 chars)
        original_size: Optional input size in bytes
        final_size: Optional processed size in bytes
        tags: Optional list of tags
        created_by: Optional username of creator
        href: Optional hyperlink reference
        document_set_ids: List of document set IDs in this library

    Backward Compatibility:
        The library_id property aliases asset_id to maintain compatibility
        with existing code. Both library_id and asset_id can be used
        interchangeably.
    """

    # DocumentLibrary-specific attributes (name and description inherited from Asset)
    purpose: str | None = None
    original_size: int | None = None
    final_size: int | None = None
    tags: list[str] = field(default_factory=list)
    created_by: str | None = None
    href: str | None = None
    document_set_ids: list[str] = field(default_factory=list)

    def __init__(
        self,
        *,
        asset_id: str | None = None,
        library_id: str | None = None,  # Backward compatibility
        name: str = "",
        description: str | None = None,
        purpose: str | None = None,
        original_size: int | None = None,
        final_size: int | None = None,
        tags: list[str] | None = None,
        created_by: str | None = None,
        href: str | None = None,
        document_set_ids: list[str] | None = None,
    ) -> None:
        """Initialize DocumentLibrary with backward compatibility for library_id parameter.

        Args:
            asset_id: Unique identifier (preferred)
            library_id: Unique identifier (backward compatibility, aliases asset_id)
            name: Library name
            description: Optional description
            purpose: Optional purpose/additional info
            original_size: Optional input size in bytes
            final_size: Optional processed size in bytes
            tags: Optional list of tags
            created_by: Optional username of creator
            href: Optional hyperlink reference
            document_set_ids: List of document set IDs in this library
        """
        # Handle backward compatibility: library_id parameter aliases asset_id
        if library_id is not None and asset_id is None:
            asset_id = library_id

        # Generate a UUID if neither was supplied
        if asset_id is None:
            asset_id = str(uuid4())

        # Initialize parent Asset fields
        self.asset_id = asset_id
        self.name = name
        self.description = description

        # Initialize DocumentLibrary-specific fields
        self.purpose = purpose
        self.original_size = original_size
        self.final_size = final_size
        self.tags = tags if tags is not None else []
        self.created_by = created_by
        self.href = href
        self.document_set_ids = document_set_ids if document_set_ids is not None else []

    # ── Backward-compatibility property ─────────────────────────────────────

    @property
    def library_id(self) -> str:
        """Backward compatibility: library_id aliases asset_id."""
        return self.asset_id  # type: ignore[return-value]

    @library_id.setter
    def library_id(self, value: str) -> None:
        """Backward compatibility: setting library_id sets asset_id."""
        self.asset_id = value

    # ── Asset abstract method implementations ────────────────────────────────

    @staticmethod
    def get_config_key() -> str:
        """Return YAML config key for document library repository lookup."""
        return "documentlibrary"

    @staticmethod
    def get_collection_name() -> str:
        """Return DuckDB collection name for document libraries."""
        return "document_libraries"

    def get_asset_type(self) -> AssetType:
        """Return the asset type for DocumentLibrary."""
        return AssetType.DOCUMENT_LIBRARY

    def update_timestamp(self) -> None:
        """No-op — DocumentLibrary has no timestamp field.

        Required by Asset ABC. DocumentLibrary does not track modification
        timestamps; this is a deliberate design choice matching the existing
        domain model.
        """

    def to_dict(self) -> dict[str, Any]:
        """Serialize DocumentLibrary to a storage dictionary.

        Includes both library_id and asset_id for backward compatibility,
        matching the Flow pattern so EE repositories that key on asset_id
        can round-trip correctly via from_dict().
        document_set_ids is stored as a plain list — no junction table.
        """
        return {
            "library_id": self.library_id,  # Backward compatibility
            "asset_id": self.asset_id,  # Unified architecture
            "name": self.name,
            "description": self.description,
            "purpose": self.purpose,
            "original_size": self.original_size,
            "final_size": self.final_size,
            "tags": self.tags or [],
            "created_by": self.created_by,
            "href": self.href,
            "document_set_ids": self.document_set_ids or [],
        }

    @classmethod
    def from_dict(cls, *, data: dict[str, Any]) -> "DocumentLibrary":
        """Deserialize a storage dictionary to a DocumentLibrary.

        Accepts both library_id and asset_id for backward compatibility.
        document_set_ids is read directly from the record.
        """
        # Support both library_id and asset_id keys
        library_id = data.get("library_id") or data.get("asset_id")
        return cls(
            library_id=library_id,
            name=data["name"],
            description=data.get("description"),
            purpose=data.get("purpose"),
            original_size=data.get("original_size"),
            final_size=data.get("final_size"),
            tags=data.get("tags", []),
            created_by=data.get("created_by"),
            href=data.get("href"),
            document_set_ids=data.get("document_set_ids", []),
        )

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
            library_id=library_id,
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

    def validate(self) -> None:
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
