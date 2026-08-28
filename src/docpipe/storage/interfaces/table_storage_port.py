"""Table storage port — interface for PyArrow table storage."""

from abc import ABC, abstractmethod
from typing import Any

import pyarrow as pa


class TableStoragePort(ABC):
    """
    Interface for PyArrow table storage.

    Used for storing document set data as PyArrow tables.
    Provides operations for creating tables, upserting data, and querying.

    docling-pipelines implementations: DuckDBTableStorage
    """

    @abstractmethod
    def create_table(self, *, table_name: str, schema: pa.Schema) -> None:
        """
        Create a new table with the specified schema.

        Args:
            table_name: Unique name for the table
            schema: PyArrow schema defining the table structure

        Raises:
            ValueError: If a table with the same name already exists
            RuntimeError: If storage operation fails
        """
        ...

    @abstractmethod
    def upsert_data(self, *, table_name: str, data: pa.Table) -> None:
        """
        Insert or update data in a table.

        Args:
            table_name: Name of the table to upsert data into
            data: PyArrow table containing the data to upsert

        Raises:
            KeyError: If the specified table does not exist
            ValueError: If the data schema does not match the table schema
            RuntimeError: If storage operation fails
        """
        ...

    @abstractmethod
    def read_data(self, *, table_name: str, limit: int | None = None, offset: int | None = None) -> pa.Table:
        """
        Read data from a table.

        Args:
            table_name: Name of the table to read from
            limit: Maximum number of rows to return
            offset: Number of rows to skip

        Returns:
            PyArrow table containing the requested data

        Raises:
            KeyError: If the specified table does not exist
            RuntimeError: If storage operation fails
        """
        ...

    @abstractmethod
    def delete_table(self, *, table_name: str) -> bool:
        """
        Delete a table and all its data.

        Args:
            table_name: Name of the table to delete

        Returns:
            True if table was deleted, False if it did not exist

        Raises:
            RuntimeError: If storage operation fails
        """
        ...

    @abstractmethod
    def table_exists(self, *, table_name: str) -> bool:
        """
        Check if a table exists.

        Args:
            table_name: Name of the table to check

        Returns:
            True if table exists, False otherwise
        """
        ...

    @abstractmethod
    def get_row_count(self, *, table_name: str) -> int:
        """
        Get the number of rows in a table.

        Args:
            table_name: Name of the table

        Returns:
            Number of rows in the table

        Raises:
            KeyError: If the specified table does not exist
            RuntimeError: If storage operation fails
        """
        ...

    @abstractmethod
    def execute_query(self, *, query: str, params: list[Any] | None = None) -> pa.Table:
        """
        Execute a SQL query and return results as PyArrow table.

        Args:
            query: SQL query to execute
            params: Optional query parameters

        Returns:
            Query results as PyArrow table

        Raises:
            RuntimeError: If query execution fails
        """
        ...
