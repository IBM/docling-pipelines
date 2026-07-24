"""Type definitions for document library domain.

This module defines TypedDict classes for type-safe configuration and responses
used throughout the document library domain layer.
"""

from typing import Any, TypedDict


class HealthCheckResult(TypedDict):
    """Health check result for repository components.

    Attributes:
        healthy: Whether the component is healthy and operational
        message: Human-readable status message
        details: Optional additional details about the health status
    """

    healthy: bool
    message: str
    details: dict[str, Any] | None


class RepositoryConfig(TypedDict, total=False):
    """Configuration for document library repository adapters.

    Attributes:
        database_path: Path to the database file (for file-based repositories)
        connection_string: Connection string for remote databases
        timeout: Connection timeout in seconds
        pool_size: Connection pool size for database connections
        additional_params: Additional adapter-specific parameters
    """

    database_path: str
    connection_string: str
    timeout: int
    pool_size: int
    additional_params: dict[str, Any]
