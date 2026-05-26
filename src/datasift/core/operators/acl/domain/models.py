"""Domain models for ACL extraction.

This module defines the core domain models for ACL (Access Control List) extraction,
following hexagonal architecture principles. These models are provider-agnostic and
represent the business logic layer.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ACLRequest:
    """Request to extract effective ACL for a resource.

    This model represents a request to extract access control information for a
    specific resource. It includes resource identification, provider information,
    credentials, and resolution options.

    Attributes:
        resource_id: Unique identifier for the resource
        resource_path: Full path to the resource
        resource_type: Type of resource (e.g., "file", "folder", "site")
        provider: Provider name (e.g., "sharepoint", "s3", "google_drive")
        provider_metadata: Provider-specific metadata
        credentials: Authentication credentials
        connection_params: Connection parameters for the provider
        resolve_inheritance: Whether to recursively resolve inheritance
        expand_groups: Whether to expand groups to individual users
        normalize_identities: Whether to normalize identities to canonical form
    """

    resource_id: str
    resource_path: str
    resource_type: str
    provider: str
    provider_metadata: dict[str, Any] = field(default_factory=dict)
    credentials: dict[str, Any] = field(default_factory=dict)
    connection_params: dict[str, Any] = field(default_factory=dict)
    resolve_inheritance: bool = True
    expand_groups: bool = True
    normalize_identities: bool = True


@dataclass
class ACLResponse:
    """Response containing resolved effective ACL.

    This model represents the result of ACL extraction, containing the effective
    allowed users after resolving inheritance, expanding groups, and normalizing
    identities. Only allowed_users is exposed as a column in the PyArrow table;
    other fields are used internally during processing.

    Attributes:
        resource_id: Unique identifier for the resource
        resource_path: Full path to the resource
        allowed_users: Set of normalized user identities with access (CORE OUTPUT)
        denied_users: Set of explicitly denied users (provider-dependent, internal only)
        inheritance_chain: List of resource IDs in inheritance chain (internal only)
        has_unique_permissions: Whether resource has unique permissions
        resolution_metadata: Metadata about the resolution process (internal only)
        extraction_success: Whether extraction succeeded
        extraction_error: Error message if extraction failed
        extraction_warnings: List of warnings during extraction
    """

    resource_id: str
    resource_path: str
    allowed_users: set[str]
    denied_users: set[str] | None = None
    inheritance_chain: list[str] = field(default_factory=list)
    has_unique_permissions: bool = False
    resolution_metadata: dict[str, Any] = field(default_factory=dict)
    extraction_success: bool = True
    extraction_error: str | None = None
    extraction_warnings: list[str] = field(default_factory=list)

    def get_all_users(self) -> set[str]:
        """Get all users (allowed + denied if present).

        Returns:
            Set of all user identities (allowed and denied)
        """
        users = self.allowed_users.copy()
        if self.denied_users:
            users.update(self.denied_users)
        return users


@dataclass
class ACLExtractionResult:
    """Result of batch ACL extraction operation.

    This model represents the result of extracting ACLs for multiple resources
    in a batch operation. It includes successful extractions, failures, and
    aggregate statistics.

    Attributes:
        successful_extractions: List of successful ACL responses
        failed_extractions: List of failed resource IDs with error messages
        total_resources: Total number of resources processed
        success_count: Number of successful extractions
        failure_count: Number of failed extractions
        processing_time_seconds: Total processing time in seconds
        cache_statistics: Statistics about cache usage during extraction
    """

    successful_extractions: list[ACLResponse] = field(default_factory=list)
    failed_extractions: list[dict[str, str]] = field(default_factory=list)
    total_resources: int = 0
    success_count: int = 0
    failure_count: int = 0
    processing_time_seconds: float = 0.0
    cache_statistics: dict[str, Any] = field(default_factory=dict)


@dataclass
class RawPermission:
    """Internal representation of raw permission (adapter-specific).

    This model is used internally by adapters to represent raw permissions
    before they are processed into the provider-agnostic ACLResponse format.
    It includes provider-specific details like roles and inheritance information.

    Note: This model is NOT exposed in the public API or PyArrow output.

    Attributes:
        principal_id: Unique identifier for the principal (user/group)
        principal_type: Type of principal ("user", "group", "link", etc.)
        principal_name: Human-readable name of the principal
        role: Role assigned to the principal (internal only, not exposed)
        permission_type: Type of permission (internal only, not exposed)
        is_inherited: Whether permission is inherited from parent
        inherited_from: Resource ID from which permission is inherited
        metadata: Provider-specific metadata
    """

    principal_id: str
    principal_type: str
    principal_name: str | None = None
    role: str | None = None
    permission_type: str | None = None
    is_inherited: bool = False
    inherited_from: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
