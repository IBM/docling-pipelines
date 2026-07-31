"""Pure Python domain model for Flow.

This is a domain entity without framework dependencies (no Pydantic).
Represents the core business concept of a Flow in the system.

Now extends the unified Asset base class for consistency across all asset types.

Exception Handling:
The validate() method raises AssetInvalidDataException for validation failures,
ensuring consistent exception handling across the application layers.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from docpipe.core.assets.common.domain.models.asset import Asset
from docpipe.core.constants.asset_constants import AssetType
from docpipe.exceptions.docpipe_exceptions import AssetInvalidDataException


@dataclass
class Flow(Asset):
    """Domain model for Flow entity extending unified Asset base class.

    Represents a flow definition that can be stored and executed.
    This is a pure Python class without external dependencies.

    Inherits from Asset:
        - asset_id: Unique identifier (aliased as flow_id for backward compatibility)
        - name: Flow name
        - description: Optional description

    Flow-Specific Attributes:
        - definition: Flow definition dictionary (Elyra pipeline format)
        - tags: List of tags for categorization
        - created_on/modified_on: Timestamps
        - created_by/modified_by: User tracking
        - href: API endpoint reference
        - container_kind/container_id: Container information
        - flow_version: Flow format version
        - is_hidden: Visibility flag
        - job_id: Associated job identifier

    Backward Compatibility:
        The flow_id property aliases asset_id to maintain compatibility with
        existing code. Both flow_id and asset_id can be used interchangeably.

    Validation:
        The validate() method raises FlowInvalidDataException for all validation
        failures, ensuring consistent exception handling across application layers.
    """

    # Flow-specific attributes
    definition: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    created_on: datetime | None = None
    modified_on: datetime | None = None
    created_by: str | None = None
    modified_by: str | None = None
    href: str | None = None
    container_kind: str | None = None
    container_id: str | None = None
    flow_version: str | None = "2.0"
    is_hidden: bool | None = False
    job_id: str | None = None

    @property
    def flow_id(self) -> str | None:
        """Backward compatibility: flow_id aliases asset_id.

        Returns:
            str | None: The asset_id value
        """
        return self.asset_id

    @flow_id.setter
    def flow_id(self, value: str | None) -> None:
        """Backward compatibility: setting flow_id sets asset_id.

        Args:
            value: The flow ID value to set
        """
        self.asset_id = value

    def __post_init__(self):
        """Post-initialization to set default values."""
        super().__post_init__()
        if self.created_on is None:
            self.created_on = datetime.now(UTC)
        if self.modified_on is None:
            self.modified_on = datetime.now(UTC)

        # Ensure tags is a list
        if self.tags is None:
            self.tags = []

    @staticmethod
    def get_config_key() -> str:
        """Return YAML config key for flow repository lookup."""
        return "flow"

    @staticmethod
    def get_collection_name() -> str:
        """Return DuckDB collection name — flows use local filesystem, not DuckDB."""
        return "flows"

    def get_asset_type(self) -> AssetType:
        """Return the asset type identifier.

        Returns:
            AssetType: AssetType.FLOW
        """
        return AssetType.FLOW

    def validate(self) -> None:
        """Validate the flow entity.

        Calls parent Asset.validate() first for common validation,
        then performs Flow-specific validation.

        Validation Rules:
        - Name: Non-empty, ≤255 characters (validated by Asset base class)
        - Description: ≤2000 characters if provided (validated by Asset base class)
        - Definition: Non-empty dictionary in Elyra pipeline format

        Expected definition format (Elyra pipeline):
        {
            "doc_type": "pipeline",
            "version": "3.0",
            "json_schema": "https://api.dataplatform.ibm.com/schemas/...",
            "id": "<uuid>",
            "primary_pipeline": "<uuid>",
            "pipelines": [
                {
                    "id": "<uuid>",
                    "nodes": [...],
                    "app_data": {
                        "ds_flow": {...},
                        "ui_data": {...}
                    }
                }
            ],
            "schemas": []
        }

        Raises:
            AssetInvalidDataException: If validation fails. Includes specific error
                message and field_name for targeted error handling.
        """
        # Call parent validation for common fields (name, description)
        # AssetInvalidDataException will bubble up naturally
        super().validate()

        # Flow-specific validation: definition must be a non-empty dictionary
        if not isinstance(self.definition, dict):
            raise AssetInvalidDataException(message="Flow definition must be a dictionary", field_name="definition")

        if not self.definition:
            raise AssetInvalidDataException(message="Flow definition cannot be empty", field_name="definition")

    def update_timestamp(self) -> None:
        """Update the modified_on timestamp."""
        self.modified_on = datetime.now(UTC)

    def get_created_at(self) -> datetime | None:
        """Return the creation timestamp for sorting in the generic repository."""
        return self.created_on

    def get_updated_at(self) -> datetime | None:
        """Return the last-modified timestamp for sorting in the generic repository."""
        return self.modified_on

    def to_dict(self) -> dict[str, Any]:
        """Convert flow to dictionary representation.

        Includes both flow_id and asset_id for backward compatibility.

        Returns:
            Dictionary representation of the flow
        """
        return {
            "flow_id": self.flow_id,  # Backward compatibility
            "asset_id": self.asset_id,  # Unified architecture
            "asset_type": self.get_asset_type().value,  # Convert enum to string
            "container_kind": self.container_kind,
            "container_id": self.container_id,
            "name": self.name,
            "description": self.description,
            "definition": self.definition,
            "tags": self.tags,
            "is_hidden": self.is_hidden,
            "flow_version": self.flow_version,
            "created_on": self.created_on.isoformat() if self.created_on else None,
            "modified_on": self.modified_on.isoformat() if self.modified_on else None,
            "job_id": self.job_id,
            "created_by": self.created_by,
            "modified_by": self.modified_by,
            "href": self.href,
        }

    @classmethod
    def from_dict(cls, *, data: dict[str, Any]) -> "Flow":
        """Create Flow from dictionary representation.

        Accepts both flow_id and asset_id for backward compatibility.

        Args:
            data: Dictionary containing flow data

        Returns:
            Flow instance
        """
        # Parse datetime strings if present
        created_on = data.get("created_on")
        if isinstance(created_on, str):
            created_on = datetime.fromisoformat(created_on.replace("Z", "+00:00"))

        modified_on = data.get("modified_on")
        if isinstance(modified_on, str):
            modified_on = datetime.fromisoformat(modified_on.replace("Z", "+00:00"))

        # Support both flow_id and asset_id for backward compatibility
        asset_id = data.get("asset_id") or data.get("flow_id")

        return cls(
            asset_id=asset_id,
            container_kind=data.get("container_kind"),
            container_id=data.get("container_id"),
            name=data["name"],
            description=data.get("description"),
            definition=data.get("definition", {}),
            tags=data.get("tags", []),
            is_hidden=data.get("is_hidden", False),
            flow_version=data.get("flow_version", "2.0"),
            created_on=created_on,
            modified_on=modified_on,
            job_id=data.get("job_id"),
            created_by=data.get("created_by"),
            modified_by=data.get("modified_by"),
            href=data.get("href"),
        )
