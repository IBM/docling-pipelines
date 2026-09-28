"""Custom operator domain models."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from docpipe.exceptions.docpipe_exceptions import CustomOperatorInvalidDataException


class CustomOperatorStatus(StrEnum):
    """Lifecycle status of a custom operator."""

    VALIDATED = "validated"
    INVALID = "invalid"
    PENDING = "pending"


@dataclass
class CustomOperator:
    """Domain model representing a custom operator."""

    name: str
    description: str
    short_name: str
    status: CustomOperatorStatus
    message: str
    operator_file: str
    id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        """Validate model invariants."""
        if not self.name or not self.name.strip():
            raise CustomOperatorInvalidDataException(message="Operator name cannot be empty", field_name="name")
        if not self.short_name or not self.short_name.strip():
            raise CustomOperatorInvalidDataException(
                message="Operator short_name cannot be empty", field_name="short_name"
            )
        if not self.operator_file or not self.operator_file.strip():
            raise CustomOperatorInvalidDataException(
                message="Operator file name cannot be empty", field_name="operator_file"
            )
        try:
            CustomOperatorStatus(self.status)
        except ValueError as e:
            raise CustomOperatorInvalidDataException(
                message=f"Invalid operator status: {self.status}", field_name="status"
            ) from e

    def to_dict(self) -> dict[str, Any]:
        """Convert custom operator to dictionary representation for JSON persistence."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "short_name": self.short_name,
            "status": str(self.status.value if isinstance(self.status, CustomOperatorStatus) else self.status),
            "message": self.message,
            "operator_file": self.operator_file,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, *, data: dict[str, Any]) -> "CustomOperator":
        """Create CustomOperator instance from dictionary data."""
        created_at_raw = data.get("created_at")
        updated_at_raw = data.get("updated_at")

        created_at = datetime.fromisoformat(created_at_raw) if isinstance(created_at_raw, str) else created_at_raw
        updated_at = datetime.fromisoformat(updated_at_raw) if isinstance(updated_at_raw, str) else updated_at_raw

        status_raw = data.get("status", CustomOperatorStatus.PENDING)
        try:
            status = CustomOperatorStatus(status_raw)
        except ValueError:
            status = CustomOperatorStatus.INVALID

        return cls(
            id=data.get("id"),
            name=data.get("name", ""),
            description=data.get("description", ""),
            short_name=data.get("short_name", ""),
            status=status,
            message=data.get("message", ""),
            operator_file=data.get("operator_file", ""),
            created_at=created_at,
            updated_at=updated_at,
            metadata=data.get("metadata", {}),
        )
