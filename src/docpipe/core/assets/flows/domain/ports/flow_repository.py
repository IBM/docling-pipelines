"""Port interface for Flow repository.

This defines the contract that any Flow repository adapter must implement.
Following the hexagonal architecture pattern, this is a port in the domain layer.
"""

from abc import ABC, abstractmethod
from typing import Any

from docpipe.core.assets.flows.domain.models.flow import Flow


class FlowRepository(ABC):
    """Abstract repository interface for Flow persistence.

    This port defines the contract for storing and retrieving flows.
    Concrete implementations (adapters) will provide specific storage mechanisms
    (local filesystem, Git, PostgreSQL, etc.).
    """

    @abstractmethod
    def save(self, flow: Flow) -> Flow:
        """Save a flow to the repository.

        Args:
            flow: Flow entity to save

        Returns:
            The saved flow with updated metadata

        Raises:
            ValueError: If flow validation fails or flow_id is missing
            PermissionError: If write permission denied
            OSError: If file system operation fails
            TimeoutError: If lock cannot be acquired
        """
        pass

    @abstractmethod
    def find_by_id(self, flow_id: str) -> Flow | None:
        """Find a flow by its ID.

        Args:
            flow_id: Unique identifier of the flow

        Returns:
            Flow entity if found, None otherwise

        Raises:
            ValueError: If flow_id is invalid or data integrity error detected
            PermissionError: If read permission denied
            FileNotFoundError: If flow file does not exist
            OSError: If file system operation fails
            TimeoutError: If lock cannot be acquired
        """

    @abstractmethod
    def find_all(self) -> list[Flow]:
        """Retrieve all flows from the repository.

        Returns:
            List of all flows

        Raises:
            PermissionError: If read permission denied
            OSError: If file system operation fails
            TimeoutError: If lock cannot be acquired
        """
        pass

    @abstractmethod
    def delete(self, flow_id: str) -> bool:
        """Delete a flow by its ID.

        Args:
            flow_id: Unique identifier of the flow to delete

        Returns:
            True if flow was deleted, False if not found

        Raises:
            PermissionError: If write permission denied
            OSError: If file system operation fails
            TimeoutError: If lock cannot be acquired
        """
        pass

    @abstractmethod
    def exists(self, flow_id: str) -> bool:
        """Check if a flow exists in the repository.

        Args:
            flow_id: Unique identifier of the flow

        Returns:
            True if flow exists, False otherwise

        Raises:
            ValueError: If flow_id is invalid
            PermissionError: If read permission denied
            OSError: If file system operation fails
            TimeoutError: If lock cannot be acquired
        """

    @abstractmethod
    def bulk_delete(self, flow_ids: list[str], batch_size: int = 10, max_workers: int = 4) -> dict[str, Any]:
        """Delete multiple flows by their IDs in parallel.

        Args:
            flow_ids: List of unique identifiers of flows to delete
            batch_size: Number of flows per batch (reserved for future batching support)
            max_workers: Maximum number of parallel workers (default: 4)

        Returns:
            Dictionary containing:
                - deleted (list[str]): Successfully deleted flow_ids
                - failed (list[dict]): Failed deletions with flow_id and error
                - total_requested (int): Total number requested
                - total_deleted (int): Count of successful deletions
                - total_failed (int): Count of failed deletions

        Raises:
            ValueError: If flow_ids list is empty
            PermissionError: If write permission denied
            OSError: If file system operation fails
            TimeoutError: If lock cannot be acquired

        Note:
            Implementations should use parallel processing with per-file locks
            to enable concurrent deletions. The batch_size parameter is reserved
            for future batching support.
        """
        pass

    @abstractmethod
    def update(self, flow: Flow) -> Flow:
        """Update an existing flow.

        Implementations should ensure data consistency during updates.

        Args:
            flow: Flow entity with updated data

        Returns:
            Updated flow

        Raises:
            ValueError: If flow doesn't exist or flow_id is missing
            PermissionError: If write permission denied
            OSError: If file system operation fails
            TimeoutError: If lock cannot be acquired
        """
        pass
