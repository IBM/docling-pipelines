"""Metadata repository port interface for document sets.

This module defines the abstract interface for document set metadata persistence,
following hexagonal architecture principles. Adapters must implement this interface
to provide concrete storage implementations.
"""

from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Any, Iterator

from docpipe.core.assets.document_sets.domain.models.document_set import DocumentSet
from docpipe.core.assets.document_sets.domain.types import HealthCheckResult


class DocumentSetMetadataRepository(ABC):
    """Abstract interface for document set metadata persistence.

    This port defines the contract for storing and retrieving document set metadata.
    Adapters implementing this interface handle the actual persistence mechanism
    (e.g., DuckDB, PostgreSQL, SQLite).

    All methods use keyword-only arguments for clarity and maintainability.
    Implementations must handle their own error conditions and raise appropriate
    exceptions as documented.
    """

    @abstractmethod
    def create(self, *, document_set: DocumentSet) -> DocumentSet:
        """Create a new document set metadata entry.

        Args:
            document_set: The document set to create

        Returns:
            The created document set with any generated fields populated

        Raises:
            ValueError: If a document set with the same ID or name already exists
            RuntimeError: If the repository is not accessible or configured
        """
        pass

    @abstractmethod
    def get_by_id(self, *, document_set_id: str) -> DocumentSet:
        """Retrieve a document set by its unique identifier.

        Args:
            document_set_id: The unique identifier of the document set

        Returns:
            The document set with the specified ID

        Raises:
            KeyError: If no document set exists with the given ID
            RuntimeError: If the repository is not accessible
        """
        pass

    @abstractmethod
    def get_by_name(self, *, name: str) -> DocumentSet:
        """Retrieve a document set by its name.

        Args:
            name: The name of the document set

        Returns:
            The document set with the specified name

        Raises:
            KeyError: If no document set exists with the given name
            RuntimeError: If the repository is not accessible
        """
        pass

    @abstractmethod
    def update(self, *, document_set: DocumentSet) -> DocumentSet:
        """Update an existing document set metadata entry.

        Args:
            document_set: The document set with updated fields

        Returns:
            The updated document set

        Raises:
            KeyError: If the document set does not exist
            ValueError: If the update would violate constraints (e.g., duplicate name)
            RuntimeError: If the repository is not accessible
        """
        pass

    @abstractmethod
    def delete(self, *, document_set_id: str) -> bool:
        """Delete a document set metadata entry.

        Args:
            document_set_id: The unique identifier of the document set to delete

        Returns:
            True if the document set was deleted, False if it did not exist

        Raises:
            RuntimeError: If the repository is not accessible
        """
        pass

    @abstractmethod
    def list_all(self) -> list[DocumentSet]:
        """List all document sets in the repository.

        Returns:
            A list of all document sets, empty list if none exist

        Raises:
            RuntimeError: If the repository is not accessible
        """
        pass

    @abstractmethod
    def exists(self, *, document_set_id: str) -> bool:
        """Check if a document set exists.

        Args:
            document_set_id: The unique identifier to check

        Returns:
            True if a document set with the given ID exists, False otherwise

        Raises:
            RuntimeError: If the repository is not accessible
        """
        pass

    @abstractmethod
    def health_check(self) -> HealthCheckResult:
        """Check the health status of the repository.

        Returns:
            A dictionary containing health status information with keys:
            - healthy: bool indicating if the repository is operational
            - message: str with status description
            - details: optional dict with additional diagnostic information

        Raises:
            No exceptions should be raised; errors should be reflected in the result
        """
        pass

    @classmethod
    @abstractmethod
    def validate_config(cls, *, config: dict[str, Any]) -> list[str]:
        """Validate repository configuration.

        This class method validates configuration before instantiation,
        allowing early detection of configuration errors.

        Args:
            config: Configuration dictionary to validate

        Returns:
            List of validation error messages, empty if configuration is valid
        """
        pass

    @abstractmethod
    def begin_transaction(self) -> None:
        """Begin a new transaction.

        Starts a transaction context for atomic operations. Must be followed
        by either commit_transaction or rollback_transaction.

        Raises:
            RuntimeError: If a transaction is already active or repository is not accessible
        """
        pass

    @abstractmethod
    def commit_transaction(self) -> None:
        """Commit the current transaction.

        Commits all changes made within the transaction context.

        Raises:
            RuntimeError: If no transaction is active or commit fails
        """
        pass

    @abstractmethod
    def rollback_transaction(self) -> None:
        """Rollback the current transaction.

        Reverts all changes made within the transaction context.

        Raises:
            RuntimeError: If no transaction is active
        """
        pass

    @contextmanager
    @abstractmethod
    def transaction(self) -> Iterator[None]:
        """Context manager for transaction handling.

        Provides a context manager that automatically handles transaction
        lifecycle with proper commit on success and rollback on exception.

        Example:
            with repository.transaction():
                repository.create(document_set=doc_set1)
                repository.create(document_set=doc_set2)
                # Both creates committed together, or both rolled back on error

        Yields:
            None

        Raises:
            RuntimeError: If transaction operations fail
        """
        pass
