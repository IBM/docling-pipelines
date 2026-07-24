"""Pure Python domain model for DocumentSet.

This is a domain entity without framework dependencies (no Pydantic).
Represents the core business concept of a DocumentSet in the system.

Exception Handling:
The validate() method raises DocpipeException for validation failures,
ensuring consistent exception handling across the application layers.
"""

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from docpipe.exceptions.docpipe_exceptions import DocpipeException
from docpipe.exceptions.error_codes import ErrorCode
from docpipe.exceptions.error_messages import ValidationCodeMessages

from .data_card import DataCard
from .storage_reference import StorageReference


@dataclass
class DocumentSet:
    """Domain model for DocumentSet entity.

    Represents a collection of documents stored in a specific backend with
    associated metadata, statistics, and lineage information.

    Validation:
    The validate() method raises DocumentSetInvalidDataException for all validation
    failures, ensuring consistent exception handling across application layers.

    Attributes:
        id: Unique identifier (UUID)
        name: Unique name for the document set
        description: Optional description
        storage_backend: Storage backend type (default "duckdb")
        database_path: Path to the database file
        table_name: Name of the table storing documents
        total_documents: Total number of documents in the set
        total_size_bytes: Total size of all documents in bytes
        total_pages: Total number of pages across all documents
        created_at: Timestamp when the document set was created
        updated_at: Timestamp when the document set was last updated
        metadata: Optional additional metadata as key-value pairs
        storage_reference: Optional storage reference object
        data_card: Optional data card for lineage tracking
    """

    name: str
    database_path: str
    table_name: str
    id: str | None = None
    description: str | None = None
    storage_backend: str = "duckdb"
    total_documents: int = 0
    total_size_bytes: int = 0
    total_pages: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    storage_reference: StorageReference | None = None
    data_card: DataCard | None = None

    # Name validation pattern: starts with letter, contains letters/digits/spaces/underscores
    _NAME_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9_ ]*$")
    _MAX_NAME_LENGTH = 128
    _MAX_DESCRIPTION_LENGTH = 2000

    def __post_init__(self):
        """Post-initialization to set default values."""
        if self.id is None:
            self.id = str(uuid4())
        if self.created_at is None:
            self.created_at = datetime.now(UTC)
        if self.updated_at is None:
            self.updated_at = datetime.now(UTC)

        # Ensure metadata is a dict
        if self.metadata is None:
            self.metadata = {}

        # Create storage reference if not provided
        if self.storage_reference is None:
            self.storage_reference = StorageReference(
                backend_type=self.storage_backend,
                database_path=self.database_path,
                table_name=self.table_name,
            )

    def validate(self) -> None:
        """Validate the document set entity.

        Performs validation on name, description, and storage configuration.

        Validation Rules:
        - Name: Non-empty, starts with alphabetic character, contains only
          letters/digits/spaces/underscores, ≤128 characters
        - Description: ≤2000 characters (if provided)
        - Database path: Non-empty
        - Table name: Non-empty
        - Numeric fields: Non-negative

        Raises:
            DocpipeException: If validation fails. Includes specific
                error message and error code for targeted error handling.
        """
        # Validate name: must be non-empty
        if not self.name or len(self.name.strip()) == 0:
            raise DocpipeException(
                ValidationCodeMessages.DOCUMENT_SET_INVALID_DATA.value.format(
                    details="Document set name cannot be empty"
                ),
                error_code=ErrorCode.DOCUMENT_SET_INVALID_DATA,
            )

        # Validate name: must start with alphabetic character
        if not self.name[0].isalpha():
            raise DocpipeException(
                ValidationCodeMessages.DOCUMENT_SET_INVALID_DATA.value.format(
                    details="Document set name must start with an alphabetic character"
                ),
                error_code=ErrorCode.DOCUMENT_SET_INVALID_DATA,
            )

        # Validate name: must match pattern (letters, digits, spaces, underscores only)
        if not self._NAME_PATTERN.match(self.name):
            raise DocpipeException(
                ValidationCodeMessages.DOCUMENT_SET_INVALID_DATA.value.format(
                    details="Document set name can only contain letters, digits, spaces, and underscores"
                ),
                error_code=ErrorCode.DOCUMENT_SET_INVALID_DATA,
            )

        # Validate name: must be within length limit
        if len(self.name) > self._MAX_NAME_LENGTH:
            raise DocpipeException(
                ValidationCodeMessages.DOCUMENT_SET_INVALID_DATA.value.format(
                    details=f"Document set name cannot exceed {self._MAX_NAME_LENGTH} characters"
                ),
                error_code=ErrorCode.DOCUMENT_SET_INVALID_DATA,
            )

        # Validate description: optional but must be within length limit if provided
        if self.description and len(self.description) > self._MAX_DESCRIPTION_LENGTH:
            raise DocpipeException(
                ValidationCodeMessages.DOCUMENT_SET_INVALID_DATA.value.format(
                    details=f"Document set description cannot exceed {self._MAX_DESCRIPTION_LENGTH} characters"
                ),
                error_code=ErrorCode.DOCUMENT_SET_INVALID_DATA,
            )

        # Validate database path: must be non-empty
        if not self.database_path or len(self.database_path.strip()) == 0:
            raise DocpipeException(
                ValidationCodeMessages.DOCUMENT_SET_INVALID_DATA.value.format(details="Database path cannot be empty"),
                error_code=ErrorCode.DOCUMENT_SET_INVALID_DATA,
            )

        # Validate table name: must be non-empty
        if not self.table_name or len(self.table_name.strip()) == 0:
            raise DocpipeException(
                ValidationCodeMessages.DOCUMENT_SET_INVALID_DATA.value.format(details="Table name cannot be empty"),
                error_code=ErrorCode.DOCUMENT_SET_INVALID_DATA,
            )

        # Validate numeric fields: must be non-negative
        if self.total_documents < 0:
            raise DocpipeException(
                ValidationCodeMessages.DOCUMENT_SET_INVALID_DATA.value.format(
                    details="Total documents cannot be negative"
                ),
                error_code=ErrorCode.DOCUMENT_SET_INVALID_DATA,
            )

        if self.total_size_bytes < 0:
            raise DocpipeException(
                ValidationCodeMessages.DOCUMENT_SET_INVALID_DATA.value.format(
                    details="Total size bytes cannot be negative"
                ),
                error_code=ErrorCode.DOCUMENT_SET_INVALID_DATA,
            )

        if self.total_pages < 0:
            raise DocpipeException(
                ValidationCodeMessages.DOCUMENT_SET_INVALID_DATA.value.format(details="Total pages cannot be negative"),
                error_code=ErrorCode.DOCUMENT_SET_INVALID_DATA,
            )

    def update_timestamp(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now(UTC)

    def update_statistics(
        self, total_documents: int | None = None, total_size_bytes: int | None = None, total_pages: int | None = None
    ) -> None:
        """Update document set statistics.

        Args:
            total_documents: New total document count
            total_size_bytes: New total size in bytes
            total_pages: New total page count
        """
        if total_documents is not None:
            self.total_documents = total_documents
        if total_size_bytes is not None:
            self.total_size_bytes = total_size_bytes
        if total_pages is not None:
            self.total_pages = total_pages
        self.update_timestamp()

    def to_dict(self) -> dict[str, Any]:
        """Convert document set to dictionary representation.

        Returns:
            Dictionary representation of the document set
        """
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "storage_backend": self.storage_backend,
            "database_path": self.database_path,
            "table_name": self.table_name,
            "total_documents": self.total_documents,
            "total_size_bytes": self.total_size_bytes,
            "total_pages": self.total_pages,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "metadata": self.metadata,
            "storage_reference": self.storage_reference.to_dict() if self.storage_reference else None,
            "data_card": self.data_card.to_dict() if self.data_card else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DocumentSet":
        """Create DocumentSet from dictionary representation.

        Args:
            data: Dictionary containing document set data

        Returns:
            DocumentSet instance
        """
        # Parse datetime strings if present
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))

        updated_at = data.get("updated_at")
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))

        # Parse storage reference if present
        storage_reference = None
        if data.get("storage_reference"):
            storage_reference = StorageReference.from_dict(data["storage_reference"])

        # Parse data card if present
        data_card = None
        if data.get("data_card"):
            data_card = DataCard.from_dict(data["data_card"])

        return cls(
            id=data.get("id"),
            name=data["name"],
            description=data.get("description"),
            storage_backend=data.get("storage_backend", "duckdb"),
            database_path=data["database_path"],
            table_name=data["table_name"],
            total_documents=data.get("total_documents", 0),
            total_size_bytes=data.get("total_size_bytes", 0),
            total_pages=data.get("total_pages", 0),
            created_at=created_at,
            updated_at=updated_at,
            metadata=data.get("metadata", {}),
            storage_reference=storage_reference,
            data_card=data_card,
        )
