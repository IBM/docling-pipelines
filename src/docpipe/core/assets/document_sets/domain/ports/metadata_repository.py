"""Metadata repository port interface for document sets.

This module defines the abstract interface for document set metadata persistence,
following hexagonal architecture principles. Adapters must implement this interface
to provide concrete storage implementations.
"""

from abc import ABC, abstractmethod
from typing import Any

from docpipe.core.assets.document_sets.domain.models.document_set import DocumentSet
from docpipe.core.assets.document_sets.domain.types import HealthCheckResult


class DocumentSetMetadataRepository(ABC):
    """Abstract interface for document set metadata persistence.

    This port defines the contract for storing and retrieving document set
    metadata. Adapters implementing this interface handle the actual persistence
    mechanism (e.g., DuckDB, PostgreSQL).

    All methods use keyword-only arguments.
    """

    @abstractmethod
    def create(self, *, document_set: DocumentSet) -> DocumentSet:
        """Create a new document set metadata entry.

        Args:
            document_set: The document set to create.

        Returns:
            The created document set with any generated fields populated.

        Raises:
            DocpipeException: If a document set with the same ID or name already exists,
                or if the repository is not accessible.
        """
        pass

    @abstractmethod
    def get_by_id(self, *, document_set_id: str) -> DocumentSet:
        """Retrieve a document set by its unique identifier.

        Args:
            document_set_id: The unique identifier of the document set.

        Returns:
            The document set with the specified ID.

        Raises:
            DocpipeException: If no document set exists with the given ID,
                or if the repository is not accessible.
        """
        pass

    @abstractmethod
    def get_by_name(self, *, name: str) -> DocumentSet:
        """Retrieve a document set by its name.

        Args:
            name: The name of the document set.

        Returns:
            The document set with the specified name.

        Raises:
            DocpipeException: If no document set exists with the given name,
                or if the repository is not accessible.
        """
        pass

    @abstractmethod
    def update(self, *, document_set: DocumentSet) -> DocumentSet:
        """Update an existing document set metadata entry.

        Args:
            document_set: The document set with updated fields.

        Returns:
            The updated document set.

        Raises:
            DocpipeException: If the document set does not exist, if the update
                would violate constraints, or if the repository is not accessible.
        """
        pass

    @abstractmethod
    def delete(self, *, document_set_id: str) -> bool:
        """Delete a document set metadata entry.

        Args:
            document_set_id: The unique identifier of the document set to delete.

        Returns:
            True if the document set was deleted, False if it did not exist.

        Raises:
            DocpipeException: If the repository is not accessible.
        """
        pass

    @abstractmethod
    def list_all(self) -> list[DocumentSet]:
        """List all document sets in the repository.

        Returns:
            A list of all document sets; empty list if none exist.

        Raises:
            DocpipeException: If the repository is not accessible.
        """
        pass

    @abstractmethod
    def exists(self, *, document_set_id: str) -> bool:
        """Check if a document set exists.

        Args:
            document_set_id: The unique identifier to check.

        Returns:
            True if a document set with the given ID exists, False otherwise.

        Raises:
            DocpipeException: If the repository is not accessible.
        """
        pass

    @abstractmethod
    def health_check(self) -> HealthCheckResult:
        """Check the health status of the repository.

        Returns:
            HealthCheckResult with healthy flag, message, and optional details.
            Must not raise; errors must be reflected in the result.
        """
        pass

    @classmethod
    @abstractmethod
    def validate_config(cls, *, config: dict[str, Any]) -> list[str]:
        """Validate repository configuration before instantiation.

        Args:
            config: Configuration dictionary to validate.

        Returns:
            List of validation error messages; empty if configuration is valid.
        """
        pass
