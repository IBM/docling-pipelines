"""DuckDB storage implementation for Document Library.

This module provides DuckDB-based storage for document library metadata.
Only stores metadata in two tables:
1. document_libraries - Library metadata
2. library_documentset_junction - Many-to-many relationships
"""

from pathlib import Path

import duckdb

from docpipe.core.constants.constants import DocpipeConstants, DocumentLibraryConstants
from docpipe.exceptions.docpipe_exceptions import DocpipeException
from docpipe.exceptions.error_codes import ErrorCode
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger()


class DuckDBStorage:
    """DuckDB storage manager for Document Library.

    Manages database connection and table creation for document library metadata.
    This class only handles metadata storage - no actual document data.
    """

    def __init__(self, *, db_path: str | None = None):
        """Initialize DuckDB storage.

        Args:
            db_path: Path to DuckDB database file (uses default if not provided)
        """
        self.db_path = db_path or DocpipeConstants.DOCUMENT_LIBRARY_DEFAULT_DB_PATH
        self._ensure_db_directory()
        self._connection: duckdb.DuckDBPyConnection | None = None

    def _ensure_db_directory(self) -> None:
        """Ensure the database directory exists."""
        try:
            db_dir = Path(self.db_path).parent
            db_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(msg=f"Failed to create database directory: {e}")
            raise DocpipeException(
                f"Failed to create database directory: {e}",
                status_code=500,
                error_code=ErrorCode.DOCUMENT_LIBRARY_STORAGE_ERROR,
            ) from e

    def connect(self) -> duckdb.DuckDBPyConnection:
        """Get or create database connection.

        Returns:
            DuckDB connection

        Raises:
            DocumentLibraryStorageException: If connection fails
        """
        if self._connection is None:
            try:
                self._connection = duckdb.connect(database=self.db_path)
                logger.info(msg=f"Connected to DuckDB at {self.db_path}")
            except Exception as e:
                logger.error(msg=f"Failed to connect to DuckDB: {e}")
                raise DocpipeException(
                    f"Failed to connect to DuckDB: {e}",
                    status_code=500,
                    error_code=ErrorCode.DOCUMENT_LIBRARY_STORAGE_ERROR,
                ) from e
        return self._connection

    def close(self) -> None:
        """Close database connection."""
        if self._connection is not None:
            try:
                self._connection.close()
                self._connection = None
                logger.info(msg="Closed DuckDB connection")
            except Exception as e:
                logger.warning(msg=f"Error closing DuckDB connection: {e}")

    def initialize_tables(self) -> None:
        """Create document library tables if they don't exist.

        Creates two tables:
        1. document_libraries - Stores library metadata
        2. library_documentset_junction - Stores library-to-documentset relationships

        Schema includes:
        - library_id, name, description (core fields)
        - purpose, original_size, final_size, tags (additional fields)
        - created_by, href (additional fields)

        Raises:
            DocumentLibraryStorageException: If table creation fails
        """
        conn = self.connect()

        try:
            # Create document_libraries table (metadata only)
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {DocpipeConstants.DOCUMENT_LIBRARY_TABLE_NAME} (
                    library_id VARCHAR({DocumentLibraryConstants.MAX_NAME_LENGTH}) PRIMARY KEY,
                    name VARCHAR({DocumentLibraryConstants.MAX_NAME_LENGTH}) NOT NULL UNIQUE,
                    description VARCHAR({DocumentLibraryConstants.MAX_DESCRIPTION_LENGTH}),
                    purpose VARCHAR({DocumentLibraryConstants.MAX_PURPOSE_LENGTH}),
                    original_size VARCHAR,
                    final_size VARCHAR,
                    tags VARCHAR,
                    created_by VARCHAR({DocumentLibraryConstants.MAX_CREATED_BY_LENGTH}),
                    href VARCHAR({DocumentLibraryConstants.MAX_HREF_LENGTH})
                )
            """)

            # Create junction table for many-to-many relationship
            # Note: DuckDB does not support ON DELETE CASCADE, so we handle deletion manually in the repository
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {DocpipeConstants.LIBRARY_DOCUMENTSET_JUNCTION_TABLE} (
                    library_id VARCHAR NOT NULL,
                    document_set_id VARCHAR NOT NULL,
                    added_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (library_id, document_set_id),
                    FOREIGN KEY (library_id) REFERENCES {DocpipeConstants.DOCUMENT_LIBRARY_TABLE_NAME}(library_id)
                )
            """)

            # Create indexes for better query performance
            conn.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_library_name
                ON {DocpipeConstants.DOCUMENT_LIBRARY_TABLE_NAME}(name)
            """)

            conn.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_junction_library
                ON {DocpipeConstants.LIBRARY_DOCUMENTSET_JUNCTION_TABLE}(library_id)
            """)

            conn.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_junction_docset
                ON {DocpipeConstants.LIBRARY_DOCUMENTSET_JUNCTION_TABLE}(document_set_id)
            """)

            logger.info(msg="Document library tables initialized successfully")

        except Exception as e:
            logger.error(msg=f"Failed to initialize tables: {e}")
            raise DocpipeException(
                f"Failed to initialize tables: {e}",
                status_code=500,
                error_code=ErrorCode.DOCUMENT_LIBRARY_STORAGE_ERROR,
            ) from e

    def execute_query(self, *, query: str, params: tuple | None = None) -> duckdb.DuckDBPyConnection:
        """Execute a SQL query.

        Args:
            query: SQL query to execute
            params: Optional query parameters

        Returns:
            Query result

        Raises:
            DocumentLibraryStorageException: If query execution fails
        """
        conn = self.connect()

        try:
            if params:
                return conn.execute(query, params)
            return conn.execute(query)
        except Exception as e:
            logger.error(msg=f"Query execution failed: {e}")
            raise DocpipeException(
                f"Query execution failed: {e}",
                status_code=500,
                error_code=ErrorCode.DOCUMENT_LIBRARY_STORAGE_ERROR,
            ) from e

    def fetch_one(self, *, query: str, params: tuple | None = None) -> tuple | None:
        """Execute query and fetch one result.

        Args:
            query: SQL query to execute
            params: Optional query parameters

        Returns:
            Single result row or None

        Raises:
            DocumentLibraryStorageException: If query execution fails
        """
        result = self.execute_query(query=query, params=params)
        return result.fetchone()

    def fetch_all(self, *, query: str, params: tuple | None = None) -> list[tuple]:
        """Execute query and fetch all results.

        Args:
            query: SQL query to execute
            params: Optional query parameters

        Returns:
            List of result rows

        Raises:
            DocumentLibraryStorageException: If query execution fails
        """
        result = self.execute_query(query=query, params=params)
        return result.fetchall()

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        self.initialize_tables()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
