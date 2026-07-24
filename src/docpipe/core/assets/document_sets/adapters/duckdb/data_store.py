"""DuckDB adapter for document set data store.

This module provides a DuckDB implementation of the DocumentSetDataStore
interface, handling PyArrow table data operations with SQL-based logic.
"""

from typing import Any

import pyarrow as pa

from docpipe.core.assets.document_sets.domain.ports.data_store import DocumentSetDataStore
from docpipe.core.assets.document_sets.domain.types import HealthCheckResult
from docpipe.core.assets.document_sets.factories.data_store_factory import DataStoreFactory
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.exceptions.docpipe_exceptions import DocpipeException
from docpipe.exceptions.error_codes import ErrorCode
from docpipe.storage.interfaces.table_storage import TableStorage
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger(__name__)


@DataStoreFactory.register(name=OperatorConstants.DocumentSet.ADAPTER_DUCKDB, display_name="DuckDB")
class DuckDBDocumentSetDataStore(DocumentSetDataStore):
    """DuckDB implementation of document set data store.

    Provides data persistence using DuckDB storage backend for PyArrow tables.
    Handles table creation, upsert operations, data retrieval, and table management.

    This adapter contains DuckDB-specific logic (SQL queries) while delegating
    generic storage operations to the TableStorage interface.

    Attributes:
        storage: TableStorage backend for database operations
    """

    def __init__(self, *, table_storage: TableStorage) -> None:
        """Initialize the DuckDB data store with injected storage.

        Args:
            table_storage: TableStorage implementation (DuckDB-based)
        """
        self.storage = table_storage
        logger.info("DuckDBDocumentSetDataStore initialized with injected TableStorage")

    def create_data_table(self, *, table_name: str, schema: pa.Schema) -> None:
        """Create a new data table with the specified schema.

        Args:
            table_name: Unique name for the data table
            schema: PyArrow schema defining the table structure

        Raises:
            ValueError: If a table with the same name already exists
            RuntimeError: If the data store is not accessible or configured
        """
        try:
            # Check if table already exists
            if self.storage.table_exists(table_name=table_name):
                raise DocpipeException(
                    f"Table '{table_name}' already exists",
                    status_code=409,
                    error_code=ErrorCode.DOCUMENT_SET_TABLE_ALREADY_EXISTS,
                )

            # Create the table using storage layer
            self.storage.create_table(table_name=table_name, schema=schema)
            logger.info(f"Created data table: {table_name}")
        except DocpipeException:
            raise
        except Exception as e:
            raise DocpipeException(
                f"Failed to create data table: {e!s}",
                status_code=500,
                error_code=ErrorCode.DOCUMENT_SET_DATA_STORE_ERROR,
            ) from e

    def upsert_document_set_data(self, *, table_name: str, data: pa.Table) -> None:
        """Insert or update document set data.

        Args:
            table_name: Name of the table to upsert data into
            data: PyArrow table containing the data to upsert

        Raises:
            KeyError: If the specified table does not exist
            ValueError: If the data schema does not match the table schema
            RuntimeError: If the data store is not accessible
        """
        try:
            # Check if table exists
            if not self.storage.table_exists(table_name=table_name):
                raise DocpipeException(
                    f"Table '{table_name}' does not exist",
                    status_code=404,
                    error_code=ErrorCode.DOCUMENT_SET_TABLE_NOT_FOUND,
                )

            # Validate that data has an 'id' column for upsert
            if "id" not in data.schema.names:
                raise DocpipeException(
                    "Data must contain an 'id' column for upsert",
                    status_code=400,
                    error_code=ErrorCode.DOCUMENT_SET_SCHEMA_MISMATCH,
                )

            # Upsert data using storage layer
            self.storage.upsert_data(table_name=table_name, data=data)
            logger.debug(f"Upserted {len(data)} rows into {table_name}")
        except DocpipeException:
            raise
        except Exception as e:
            raise DocpipeException(
                f"Failed to upsert data: {e!s}", status_code=500, error_code=ErrorCode.DOCUMENT_SET_DATA_STORE_ERROR
            ) from e

    def get_document_set_data(self, *, table_name: str, limit: int | None = None) -> pa.Table:
        """Retrieve document set data from a table.

        Args:
            table_name: Name of the table to retrieve data from
            limit: Maximum number of rows to return, None for all rows

        Returns:
            PyArrow table containing the requested data

        Raises:
            KeyError: If the specified table does not exist
            RuntimeError: If the data store is not accessible
        """
        try:
            # Check if table exists
            if not self.storage.table_exists(table_name=table_name):
                raise DocpipeException(
                    f"Table '{table_name}' does not exist",
                    status_code=404,
                    error_code=ErrorCode.DOCUMENT_SET_TABLE_NOT_FOUND,
                )

            # Read data using storage layer
            data = self.storage.read_data(table_name=table_name, limit=limit, offset=None)
            logger.debug(f"Retrieved {len(data)} rows from {table_name}")
            return data
        except DocpipeException:
            raise
        except Exception as e:
            raise DocpipeException(
                f"Failed to retrieve data: {e!s}",
                status_code=500,
                error_code=ErrorCode.DOCUMENT_SET_DATA_STORE_ERROR,
            ) from e

    def delete_document_set_data(self, *, table_name: str) -> bool:
        """Delete all data from a table and remove the table.

        Args:
            table_name: Name of the table to delete

        Returns:
            True if the table was deleted, False if it did not exist

        Raises:
            RuntimeError: If the data store is not accessible
        """
        try:
            # Check if table exists
            if not self.storage.table_exists(table_name=table_name):
                logger.info(f"Table not found for deletion: {table_name}")
                return False

            # Delete table using storage layer
            self.storage.delete_table(table_name=table_name)
            logger.info(f"Deleted data table: {table_name}")
            return True
        except DocpipeException:
            raise
        except Exception as e:
            raise DocpipeException(
                f"Failed to delete table: {e!s}", status_code=500, error_code=ErrorCode.DOCUMENT_SET_DATA_STORE_ERROR
            ) from e

    def table_exists(self, *, table_name: str) -> bool:
        """Check if a table exists in the data store.

        Args:
            table_name: Name of the table to check

        Returns:
            True if the table exists, False otherwise

        Raises:
            RuntimeError: If the data store is not accessible
        """
        try:
            return self.storage.table_exists(table_name=table_name)
        except DocpipeException:
            raise
        except Exception as e:
            raise DocpipeException(
                f"Failed to check table existence: {e!s}",
                status_code=500,
                error_code=ErrorCode.DOCUMENT_SET_DATA_STORE_ERROR,
            ) from e

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
        try:
            # Check if table exists
            if not self.storage.table_exists(table_name=table_name):
                raise DocpipeException(
                    f"Table '{table_name}' does not exist",
                    status_code=404,
                    error_code=ErrorCode.DOCUMENT_SET_TABLE_NOT_FOUND,
                )

            # Get row count using storage layer
            count = self.storage.get_row_count(table_name=table_name)
            logger.debug(f"Table {table_name} has {count} rows")
            return count
        except DocpipeException:
            raise
        except Exception as e:
            raise DocpipeException(
                f"Failed to get row count: {e!s}",
                status_code=500,
                error_code=ErrorCode.DOCUMENT_SET_DATA_STORE_ERROR,
            ) from e

    def get_table_metrics(self, *, table_name: str) -> dict[str, int]:
        """Get aggregate metrics using SQL aggregation (DuckDB-specific logic).

        This method contains DuckDB-specific SQL logic for efficient metric computation.
        The SQL query is executed via the generic storage layer execute_query method.

        Args:
            table_name: Name of the table to compute metrics for

        Returns:
            Dictionary containing:
                - total_documents: Total number of documents
                - total_size_bytes: Sum of all document sizes
                - total_pages: Sum of all pages processed (0 if column doesn't exist)

        Raises:
            KeyError: If the specified table does not exist
            RuntimeError: If the data store is not accessible
        """
        try:
            # Check if table exists
            if not self.storage.table_exists(table_name=table_name):
                raise DocpipeException(
                    f"Table '{table_name}' does not exist",
                    status_code=404,
                    error_code=ErrorCode.DOCUMENT_SET_TABLE_NOT_FOUND,
                )

            # Query to get column names from the table
            column_query = f"""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = '{table_name}'
            """
            column_result = self.storage.execute_query(query=column_query)
            column_names = [row["column_name"] for row in column_result.to_pylist()]

            # Build SQL query dynamically based on available columns
            # Always include total_documents count
            select_clauses = ["COUNT(*) AS total_documents"]

            # Add size aggregation if column exists
            if "size" in column_names:
                select_clauses.append("COALESCE(SUM(size), 0) AS total_size_bytes")
            else:
                select_clauses.append("0 AS total_size_bytes")

            # Add pages_processed aggregation if column exists
            if "pages_processed" in column_names:
                select_clauses.append("COALESCE(SUM(pages_processed), 0) AS total_pages")
            else:
                select_clauses.append("0 AS total_pages")

            # DuckDB-specific SQL aggregation query
            # This SQL logic stays in the adapter, not in the storage layer
            query = f"""
                SELECT
                    {", ".join(select_clauses)}
                FROM {table_name}
            """

            # Execute via generic storage interface
            result_table = self.storage.execute_query(query=query)

            if len(result_table) == 0:
                raise DocpipeException(
                    f"Failed to retrieve metrics for table '{table_name}'",
                    status_code=500,
                    error_code=ErrorCode.DOCUMENT_SET_DATA_STORE_ERROR,
                )

            # Extract first row from PyArrow table
            result = result_table.to_pylist()[0]

            metrics = {
                "total_documents": int(result["total_documents"]),
                "total_size_bytes": int(result["total_size_bytes"]),
                "total_pages": int(result["total_pages"]),
            }

            logger.debug(f"Computed metrics for {table_name}: {metrics}")
            return metrics
        except DocpipeException:
            raise
        except Exception as e:
            raise DocpipeException(
                f"Failed to compute table metrics: {e!s}",
                status_code=500,
                error_code=ErrorCode.DOCUMENT_SET_DATA_STORE_ERROR,
            ) from e

    def health_check(self) -> HealthCheckResult:
        """Check the health status of the data store.

        Returns:
            A dictionary containing health status information
        """
        try:
            # Test database connectivity via storage layer
            self.storage.execute_query(query=OperatorConstants.DocumentSet.QUERY_CONNECTIVITY_TEST)

            return HealthCheckResult(
                healthy=True,
                message="Data store is healthy",
                details={
                    OperatorConstants.DocumentSet.DATABASE_PATH: getattr(self.storage, "database_path", "unknown")
                },
            )
        except Exception as e:
            return HealthCheckResult(
                healthy=False,
                message=f"Health check failed: {e}",
                details={
                    OperatorConstants.DocumentSet.DATABASE_PATH: getattr(self.storage, "database_path", "unknown"),
                    OperatorConstants.DocumentSet.META_ERROR: str(e),
                },
            )

    @classmethod
    def validate_config(cls, *, config: dict[str, Any]) -> list[str]:
        """Validate data store configuration.

        Args:
            config: Configuration dictionary to validate

        Returns:
            List of validation error messages, empty if configuration is valid
        """
        errors = []

        # Validate database_path
        db_path_key = OperatorConstants.DocumentSet.DATABASE_PATH
        if db_path_key not in config:
            errors.append(f"Missing required configuration: '{db_path_key}'")
        elif not isinstance(config[db_path_key], str):
            errors.append(f"Configuration '{db_path_key}' must be a string")
        elif not config[db_path_key]:
            errors.append(f"Configuration '{db_path_key}' cannot be empty")

        return errors


DuckDBDataStore = DuckDBDocumentSetDataStore
