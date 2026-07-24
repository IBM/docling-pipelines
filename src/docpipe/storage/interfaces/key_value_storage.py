"""Key-value storage interface for JSON-serializable records."""

from abc import ABC, abstractmethod
from typing import Any


class KeyValueStorage(ABC):
    """
    Interface for key-value storage of JSON-serializable records.

    Used for storing asset metadata like flows and document set metadata.
    Collections represent logical groupings (e.g., "flows", "document_sets").
    Records are stored as dictionaries with a unique key.

    Implementations: FileSystemStorage, DuckDBStorage
    """

    @abstractmethod
    def save_record(self, *, collection: str, key: str, data: dict[str, Any]) -> None:
        """
        Save a record to a collection.

        Args:
            collection: Logical collection name (e.g., "flows")
            key: Unique identifier for the record
            data: Record data as dictionary

        Raises:
            ValueError: If collection or key is invalid
            RuntimeError: If storage operation fails
        """
        pass

    @abstractmethod
    def get_record(self, *, collection: str, key: str) -> dict[str, Any] | None:
        """
        Retrieve a record by key.

        Args:
            collection: Logical collection name
            key: Unique identifier for the record

        Returns:
            Record data as dictionary, or None if not found

        Raises:
            ValueError: If collection or key is invalid
            RuntimeError: If storage operation fails
        """
        pass

    @abstractmethod
    def list_records(self, *, collection: str, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """
        List all records in a collection.

        Args:
            collection: Logical collection name
            filters: Optional filters to apply (implementation-specific)

        Returns:
            List of record dictionaries

        Raises:
            ValueError: If collection is invalid
            RuntimeError: If storage operation fails
        """
        pass

    @abstractmethod
    def delete_record(self, *, collection: str, key: str) -> bool:
        """
        Delete a record by key.

        Args:
            collection: Logical collection name
            key: Unique identifier for the record

        Returns:
            True if record was deleted, False if not found

        Raises:
            ValueError: If collection or key is invalid
            RuntimeError: If storage operation fails
        """
        pass

    @abstractmethod
    def collection_exists(self, *, collection: str) -> bool:
        """
        Check if a collection exists.

        Args:
            collection: Logical collection name

        Returns:
            True if collection exists, False otherwise
        """
        pass

    @abstractmethod
    def record_exists(self, *, collection: str, key: str) -> bool:
        """
        Check if a record exists.

        Args:
            collection: Logical collection name
            key: Unique identifier for the record

        Returns:
            True if record exists, False otherwise
        """
        pass
