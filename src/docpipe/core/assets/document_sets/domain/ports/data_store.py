"""Data store port interface for document sets.

This module defines the abstract interface for document set data persistence,
following hexagonal architecture principles. Adapters must implement this interface
to provide concrete storage implementations for PyArrow table data.
"""

from abc import ABC, abstractmethod
from typing import Any

import pyarrow as pa

from docpipe.core.assets.document_sets.domain.types import HealthCheckResult


class DocumentSetDataStore(ABC):
    """Abstract interface for document set data persistence.

    This port defines the contract for storing and retrieving document set data
    as PyArrow tables. Adapters implementing this interface handle the actual
    storage mechanism (e.g., DuckDB, Parquet files, Arrow IPC).

    All methods use keyword-only arguments for clarity and maintainability.
    Implementations must handle their own error conditions and raise appropriate
    exceptions as documented.
    """

    @abstractmethod
    def create_data_table(self, *, table_name: str, schema: pa.Schema) -> None:
        """Create a new data table with the specified schema.

        Creates a new table structure for storing document set data. The table
        name should be unique within the data store.

        Args:
            table_name: Unique name for the data table
            schema: PyArrow schema defining the table structure

        Raises:
            ValueError: If a table with the same name already exists
            RuntimeError: If the data store is not accessible or configured
        """
        pass

    @abstractmethod
    def upsert_document_set_data(self, *, table_name: str, data: pa.Table) -> None:
        """Insert or update document set data.

        Upserts data into the specified table. If records with matching primary
        keys exist, they are updated; otherwise, new records are inserted.

        Args:
            table_name: Name of the table to upsert data into
            data: PyArrow table containing the data to upsert

        Raises:
            KeyError: If the specified table does not exist
            ValueError: If the data schema does not match the table schema
            RuntimeError: If the data store is not accessible
        """
        pass

    @abstractmethod
    def get_document_set_data(self, *, table_name: str, limit: int | None = None) -> pa.Table:
        """Retrieve document set data from a table.

        Retrieves all or a limited number of rows from the specified table.

        Args:
            table_name: Name of the table to retrieve data from
            limit: Maximum number of rows to return, None for all rows

        Returns:
            PyArrow table containing the requested data

        Raises:
            KeyError: If the specified table does not exist
            RuntimeError: If the data store is not accessible
        """
        pass

    @abstractmethod
    def delete_document_set_data(self, *, table_name: str) -> bool:
        """Delete all data from a table and remove the table.

        Removes the table and all its data from the data store.

        Args:
            table_name: Name of the table to delete

        Returns:
            True if the table was deleted, False if it did not exist

        Raises:
            RuntimeError: If the data store is not accessible
        """
        pass

    @abstractmethod
    def table_exists(self, *, table_name: str) -> bool:
        """Check if a table exists in the data store.

        Args:
            table_name: Name of the table to check

        Returns:
            True if the table exists, False otherwise

        Raises:
            RuntimeError: If the data store is not accessible
        """
        pass

    @abstractmethod
    def get_row_count(self, *, table_name: str) -> int:
        """Get the number of rows in a table.

        Args:
            table_name: Name of the table to count rows in

        Returns:
            Number of rows in the table

        Raises:
            KeyError: If the specified table does not exist
            RuntimeError: If the data store is not accessible
        """

    @abstractmethod
    def get_table_metrics(self, *, table_name: str) -> dict[str, int]:
        """Get aggregate metrics for a table.

        Computes aggregate metrics efficiently at the storage layer
        without materializing the entire table into memory.

        Args:
            table_name: Name of the table to compute metrics for

        Returns:
            Dictionary containing:
                - total_documents: Total number of documents
                - total_size_bytes: Sum of all document sizes
                - total_pages: Sum of all pages processed

        Raises:
            KeyError: If the specified table does not exist
            RuntimeError: If the data store is not accessible
        """
        pass

    @abstractmethod
    def health_check(self) -> HealthCheckResult:
        """Check the health status of the data store.

        Returns:
            A dictionary containing health status information with keys:
            - healthy: bool indicating if the data store is operational
            - message: str with status description
            - details: optional dict with additional diagnostic information

        Raises:
            No exceptions should be raised; errors should be reflected in the result
        """
        pass

    @classmethod
    @abstractmethod
    def validate_config(cls, *, config: dict[str, Any]) -> list[str]:
        """Validate data store configuration.

        This class method validates configuration before instantiation,
        allowing early detection of configuration errors.

        Args:
            config: Configuration dictionary to validate

        Returns:
            List of validation error messages, empty if configuration is valid
        """
        pass
