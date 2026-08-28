"""AttachmentRef value object for the common asset domain.

Represents a storage pointer for an asset attachment, decoupled from the
asset metadata record.  The common fields (``name``, ``attachment_id``,
``created_at``) are readable by the service and operator layers.
Adapter-specific coordinates live in ``details`` and are opaque to the
service layer — only the adapter that created the ref reads them.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AttachmentRef:
    """Backend-agnostic storage coordinate for an asset attachment.

    Attributes:
        backend_type: Identifies the storage backend, e.g. ``"duckdb"``.
        name: Logical name of the attachment (e.g. the DuckDB table name).
        details: Adapter-specific coordinates.  Only the adapter that created
                 this ref reads ``details``; the service and operator layers
                 never access it directly.
        attachment_id: Optional server-assigned attachment ID.  ``None`` for
                       adapters where the asset_id is the primary key.
        created_at: Optional ISO-8601 creation timestamp set by the adapter.
    """

    backend_type: str
    name: str
    details: dict[str, Any] = field(default_factory=dict)
    attachment_id: str | None = None
    created_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dictionary.

        Returns:
            Dictionary representation of all fields.
        """
        return {
            "backend_type": self.backend_type,
            "name": self.name,
            "details": self.details,
            "attachment_id": self.attachment_id,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AttachmentRef":
        """Reconstruct an ``AttachmentRef`` from a serialised dictionary.

        Args:
            data: Dictionary produced by ``to_dict()``.

        Returns:
            Reconstructed ``AttachmentRef`` instance.
        """
        return cls(
            backend_type=str(data["backend_type"]),
            name=str(data["name"]),
            details=data.get("details") or {},
            attachment_id=data.get("attachment_id"),
            created_at=data.get("created_at"),
        )
