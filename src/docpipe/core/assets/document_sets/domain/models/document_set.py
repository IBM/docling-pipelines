"""Pure Python domain model for DocumentSet.

This is a domain entity without framework dependencies (no Pydantic).
Represents the core business concept of a DocumentSet in the system.

Now extends the unified Asset base class for consistency across all asset types.

Exception Handling:
The validate() method raises AssetInvalidDataException for validation failures,
ensuring consistent exception handling across the application layers.
"""

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, ClassVar

from docpipe.core.assets.common.domain.models.asset import Asset
from docpipe.core.constants.asset_constants import AssetType
from docpipe.exceptions.docpipe_exceptions import AssetInvalidDataException

from .data_card import DataCard


@dataclass
class DocumentSet(Asset):
    """Domain model for DocumentSet entity extending unified Asset base class.

    Represents a collection of documents with associated metadata, statistics,
    and lineage information.

    Inherits from Asset:
        - asset_id: Unique identifier for this document set
        - name: Human-readable name (required)
        - description: Optional description

    DocumentSet-Specific Attributes:
        - storage_backend: Hint for which backend type to use (default "duckdb")
        - total_documents/total_size_bytes/total_pages: Statistics
        - created_at/updated_at: Timestamps
        - metadata: Optional additional metadata as key-value pairs
        - data_card: Optional data card for lineage tracking

    Validation:
        validate() raises AssetInvalidDataException for all validation failures.
    """

    # DocumentSet-specific attributes
    storage_backend: str = "duckdb"
    total_documents: int = 0
    total_size_bytes: int = 0
    total_pages: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    data_card: DataCard | None = None

    # Name validation pattern: starts with letter, letters/digits/spaces/underscores
    _NAME_PATTERN: ClassVar[re.Pattern[str]] = re.compile(r"^[a-zA-Z][a-zA-Z0-9_ ]*$")
    _MAX_NAME_LENGTH: ClassVar[int] = 128

    @property
    def id(self) -> str | None:
        """Backward compatibility: id aliases asset_id."""
        return self.asset_id

    @id.setter
    def id(self, value: str | None) -> None:
        """Backward compatibility: setting id sets asset_id."""
        self.asset_id = value

    def __post_init__(self) -> None:
        """Post-initialization to set default values."""
        super().__post_init__()
        if self.created_at is None:
            self.created_at = datetime.now(UTC)
        if self.updated_at is None:
            self.updated_at = datetime.now(UTC)
        if self.metadata is None:
            self.metadata = {}

    @staticmethod
    def get_config_key() -> str:
        """Return YAML config key for document set repository lookup."""
        return "documentset"

    @staticmethod
    def get_collection_name() -> str:
        """Return DuckDB collection name for document sets."""
        return "document_sets"

    def get_asset_type(self) -> AssetType:
        """Return the asset type identifier.

        Returns:
            AssetType: AssetType.DOCUMENT_SET
        """
        return AssetType.DOCUMENT_SET

    def validate(self) -> None:
        """Validate the document set entity.

        Calls parent Asset.validate() first for common field validation, then
        performs DocumentSet-specific validation.

        Raises:
            AssetInvalidDataException: If validation fails.
        """
        super().validate()

        if not self.name[0].isalpha():
            raise AssetInvalidDataException(
                message="Document set name must start with an alphabetic character",
                field_name="name",
            )

        if not self._NAME_PATTERN.match(self.name):
            raise AssetInvalidDataException(
                message="Document set name can only contain letters, digits, spaces, and underscores",
                field_name="name",
            )

        if len(self.name) > self._MAX_NAME_LENGTH:
            raise AssetInvalidDataException(
                message=f"Document set name cannot exceed {self._MAX_NAME_LENGTH} characters",
                field_name="name",
            )

        if self.total_documents < 0:
            raise AssetInvalidDataException(
                message="Total documents cannot be negative",
                field_name="total_documents",
            )

        if self.total_size_bytes < 0:
            raise AssetInvalidDataException(
                message="Total size bytes cannot be negative",
                field_name="total_size_bytes",
            )

        if self.total_pages < 0:
            raise AssetInvalidDataException(
                message="Total pages cannot be negative",
                field_name="total_pages",
            )

    def update_timestamp(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now(UTC)

    def get_created_at(self) -> datetime | None:
        """Return the creation timestamp for sorting in the generic repository."""
        return self.created_at

    def get_updated_at(self) -> datetime | None:
        """Return the last-modified timestamp for sorting in the generic repository."""
        return self.updated_at

    def update_statistics(
        self,
        *,
        total_documents: int | None = None,
        total_size_bytes: int | None = None,
        total_pages: int | None = None,
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
        """Convert document set to dictionary representation."""
        return {
            "asset_id": self.asset_id,
            "asset_type": self.get_asset_type().value,
            "name": self.name,
            "description": self.description,
            "storage_backend": self.storage_backend,
            "total_documents": self.total_documents,
            "total_size_bytes": self.total_size_bytes,
            "total_pages": self.total_pages,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "metadata": self.metadata,
            "data_card": self.data_card.to_dict() if self.data_card else None,
        }

    @classmethod
    def from_dict(cls, *, data: dict[str, Any]) -> "DocumentSet":
        """Create DocumentSet from dictionary representation.

        Accepts both asset_id and id keys for backward compatibility.
        """
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))

        updated_at = data.get("updated_at")
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))

        data_card = None
        if data.get("data_card"):
            data_card = DataCard.from_dict(data["data_card"])

        # Support both asset_id and id for backward compatibility
        asset_id = data.get("asset_id") or data.get("id")

        return cls(
            asset_id=asset_id,
            name=data["name"],
            description=data.get("description"),
            storage_backend=data.get("storage_backend", "duckdb"),
            total_documents=data.get("total_documents", 0),
            total_size_bytes=data.get("total_size_bytes", 0),
            total_pages=data.get("total_pages", 0),
            created_at=created_at,
            updated_at=updated_at,
            metadata=data.get("metadata", {}),
            data_card=data_card,
        )
