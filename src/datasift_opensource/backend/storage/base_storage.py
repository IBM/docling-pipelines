"""Abstract base class for storage implementations."""

from abc import ABC, abstractmethod

import pyarrow as pa


class BaseStorage(ABC):
    """
    Abstract base class for storage backends.

    Defines the interface for storing and managing PyArrow table data
    across different storage implementations.
    """

    @abstractmethod
    def create_metadata_table(self) -> None:
        """
        Create the document_sets metadata table.

        The metadata table stores information about each document set including:
        - id: Unique identifier
        - name: Human-readable name (unique)
        - description: Optional description
        - storage_backend: Type of storage (e.g., 'duckdb')
        - database_path: Path to the database file
        - table_name: Name of the data table
        - total_documents: Count of documents
        - total_size_bytes: Total size in bytes
        - total_pages: Total number of pages
        - created_at: Creation timestamp
        - updated_at: Last update timestamp
        - metadata: Additional JSON metadata

        Raises:
            Exception: If table creation fails
        """

    @abstractmethod
    def create_data_table(self, table_name: str, schema: pa.Schema) -> None:
        """
        Create a data table from PyArrow schema.

        Args:
            table_name: Name of the table to create
            schema: PyArrow schema defining the table structure

        Raises:
            ValueError: If table_name is invalid
            Exception: If table creation fails
        """

    @abstractmethod
    def upsert_data(self, table_name: str, data: pa.Table) -> None:
        """
        Insert or update rows in a data table by id column.

        Performs an upsert operation: inserts new rows or updates existing
        rows based on the 'id' column. The data table must have an 'id' column.

        Args:
            table_name: Name of the table to upsert into
            data: PyArrow table containing the data to upsert

        Raises:
            ValueError: If table doesn't exist or data lacks 'id' column
            Exception: If upsert operation fails
        """

    @abstractmethod
    def read_data(self, table_name: str, limit: int | None = None, offset: int | None = None) -> pa.Table:
        """
        Read data from a table with pagination support.

        Args:
            table_name: Name of the table to read from
            limit: Maximum number of rows to return (None for all)
            offset: Number of rows to skip (None for 0)

        Returns:
            PyArrow table containing the requested data

        Raises:
            ValueError: If table doesn't exist
            Exception: If read operation fails
        """

    @abstractmethod
    def compute_metrics(self, table_name: str) -> dict:
        """
        Calculate metrics from stored data.

        Computes:
        - total_documents: Count of rows
        - total_size_bytes: Sum of 'size' column if exists, else 0
        - total_pages: Sum of 'pages_processed' column if exists, else 0

        Args:
            table_name: Name of the table to compute metrics for

        Returns:
            Dictionary with keys: total_documents, total_size_bytes, total_pages

        Raises:
            ValueError: If table doesn't exist
            Exception: If computation fails
        """

    @abstractmethod
    def delete_rows(self, table_name: str, ids: list[str]) -> int:
        """
        Delete rows from a table by id list.

        Args:
            table_name: Name of the table to delete from
            ids: List of id values to delete

        Returns:
            Number of rows deleted

        Raises:
            ValueError: If table doesn't exist
            Exception: If delete operation fails
        """

    @abstractmethod
    def delete_table(self, table_name: str) -> None:
        """
        Delete a data table.

        Args:
            table_name: Name of the table to delete

        Raises:
            ValueError: If table doesn't exist
            Exception: If delete operation fails
        """

    @abstractmethod
    def table_exists(self, table_name: str) -> bool:
        """
        Check if a table exists.

        Args:
            table_name: Name of the table to check

        Returns:
            True if table exists, False otherwise
        """

    @abstractmethod
    def get_table_schema(self, table_name: str) -> pa.Schema:
        """
        Get the current schema of a table.

        Args:
            table_name: Name of the table

        Returns:
            PyArrow schema of the table

        Raises:
            ValueError: If table doesn't exist
            Exception: If schema retrieval fails
        """
