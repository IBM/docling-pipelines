"""DuckDB storage implementation for PyArrow tables."""

import re
from pathlib import Path

import duckdb
import pyarrow as pa

from datasift.exceptions.datasift_exceptions import DatasiftException
from datasift.exceptions.error_codes import ErrorCode
from datasift.exceptions.error_messages import ValidationCodeMessages
from datasift.storage.base_storage import BaseStorage
from datasift.utils.duckdb import DuckDBConnectionManager
from datasift.utils.infrastructure.logging import get_logger

logger = get_logger(__name__)


class DuckDBStorage(BaseStorage):
    """
    DuckDB storage implementation for PyArrow tables.

    Provides a general-purpose storage layer for persisting PyArrow tables
    in DuckDB with support for schema evolution, upserts, and metrics.
    Can be used for any data storage needs, not just document sets.
    """

    @classmethod
    def validate_database_path(cls, db_path: str) -> None:
        """
        Validate database path and log warnings if issues detected.

        Args:
            db_path: Path to DuckDB database file

        Logs:
            - INFO: Database path being used
            - WARNING: If multiple database files detected in project
            - WARNING: If database directory doesn't exist
        """
        from pathlib import Path

        # Log the database path being used
        logger.info(f"Using DuckDB database at: {db_path}")

        # Skip validation for in-memory databases
        if db_path == ":memory:":
            return

        # Check if database directory exists
        db_dir = Path(db_path).parent
        if not db_dir.exists():
            logger.warning(f"Database directory does not exist: {db_dir}")
            logger.info("Directory will be created on first write")

        # Check for multiple database files in project
        try:
            db_file_path = Path(db_path).resolve()
            # Assuming data/duckdb/file.db structure, go up 2 levels to project root
            project_root = db_file_path.parents[2] if len(db_file_path.parents) >= 3 else db_file_path.parent

            # Search for document_sets.duckdb files
            db_files = list(project_root.rglob("document_sets.duckdb"))

            if len(db_files) > 1:
                logger.warning("Multiple document set database files detected in project:")
                for db_file in db_files:
                    logger.warning(f"  - {db_file}")
                logger.warning(f"This may cause data inconsistency. Consider consolidating to: {db_path}")
        except Exception as e:
            # Don't fail on validation errors, just log
            logger.debug(f"Could not check for multiple database files: {e}")

    def __init__(self, database_path: str) -> None:
        """
        Initialize DuckDB storage.

        Args:
            database_path: Path to DuckDB database file
        """
        # Validate and log database path
        self.validate_database_path(database_path)

        db_path = Path(database_path)
        if database_path != ":memory:":
            db_path.parent.mkdir(parents=True, exist_ok=True)

        self.database_path = database_path
        self.connection_manager = DuckDBConnectionManager()
        logger.info(f"Initialized DuckDB storage at: {database_path}")

    def _validate_table_name(self, table_name: str) -> None:
        """
        Validate table name to prevent SQL injection.

        Args:
            table_name: Name of the table to validate
        """
        if not table_name or not isinstance(table_name, str):
            raise DatasiftException(
                "Table name cannot be empty", status_code=400, error_code=ErrorCode.DOCUMENT_SET_INVALID_DATA
            )

        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", table_name):
            raise DatasiftException(
                ValidationCodeMessages.DOCUMENT_SET_INVALID_DATA.format(
                    details=(
                        f"Invalid table name: {table_name}. Must start with letter or underscore "
                        "and contain only alphanumeric characters and underscores."
                    )
                ),
                status_code=400,
                error_code=ErrorCode.DOCUMENT_SET_INVALID_DATA,
            )

    def _validate_column_name(self, column_name: str) -> None:
        """
        Validate column name to prevent SQL injection.

        Args:
            column_name: Name of the column to validate
        """
        if not column_name or not isinstance(column_name, str):
            raise DatasiftException(
                "Column name cannot be empty", status_code=400, error_code=ErrorCode.DOCUMENT_SET_INVALID_DATA
            )

        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", column_name):
            raise DatasiftException(
                ValidationCodeMessages.DOCUMENT_SET_INVALID_DATA.format(
                    details=(
                        f"Invalid column name: {column_name}. Must start with letter or underscore "
                        "and contain only alphanumeric characters and underscores."
                    )
                ),
                status_code=400,
                error_code=ErrorCode.DOCUMENT_SET_INVALID_DATA,
            )

    def _quote_identifier(self, identifier: str) -> str:
        """
        Quote SQL identifier for safe interpolation.

        Args:
            identifier: SQL identifier to quote

        Returns:
            Quoted identifier safe for SQL interpolation
        """
        return f'"{identifier}"'

    def create_metadata_table(self) -> None:
        """Create the document_sets metadata table."""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS document_sets (
            id VARCHAR PRIMARY KEY,
            name VARCHAR UNIQUE NOT NULL,
            description VARCHAR,
            storage_backend VARCHAR DEFAULT 'duckdb',
            database_path VARCHAR NOT NULL,
            table_name VARCHAR NOT NULL,
            total_documents INTEGER DEFAULT 0,
            total_size_bytes BIGINT DEFAULT 0,
            total_pages INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            metadata JSON
        )
        """

        try:
            with self.connection_manager.get_connection(self.database_path) as conn:
                conn.execute(create_table_sql)
                logger.info("Created document_sets metadata table")
        except DatasiftException:
            raise
        except duckdb.Error as e:
            raise DatasiftException(
                ValidationCodeMessages.DOCUMENT_SET_STORAGE_ERROR.value.format(
                    details=f"Failed to create metadata table: {e}"
                ),
                error_code=ErrorCode.DOCUMENT_SET_STORAGE_ERROR,
            ) from e
        except Exception as e:
            raise DatasiftException(
                ValidationCodeMessages.DOCUMENT_SET_STORAGE_ERROR.value.format(
                    details=f"Unexpected error creating metadata table: {e}"
                ),
                error_code=ErrorCode.DOCUMENT_SET_STORAGE_ERROR,
            ) from e

    def create_data_table(self, table_name: str, schema: pa.Schema) -> None:
        """
        Create a data table from PyArrow schema.

        Args:
            table_name: Name of the table to create
            schema: PyArrow schema defining the table structure
        """
        self._validate_table_name(table_name)

        try:
            columns = []
            for field in schema:
                col_name = field.name
                self._validate_column_name(col_name)
                quoted_col = self._quote_identifier(col_name)
                duckdb_type = self._pyarrow_to_duckdb_type(field.type)

                if col_name == "id":
                    columns.append(f"{quoted_col} {duckdb_type} PRIMARY KEY")
                else:
                    columns.append(f"{quoted_col} {duckdb_type}")

            create_table_sql = f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                {", ".join(columns)}
            )
            """

            with self.connection_manager.get_connection(self.database_path) as conn:
                conn.execute(create_table_sql)
                logger.info(f"Created data table: {table_name}")
        except DatasiftException:
            raise
        except duckdb.Error as e:
            raise DatasiftException(
                ValidationCodeMessages.DOCUMENT_SET_STORAGE_ERROR.value.format(
                    details=f"Failed to create table {table_name}: {e}"
                ),
                error_code=ErrorCode.DOCUMENT_SET_STORAGE_ERROR,
            ) from e
        except Exception as e:
            raise DatasiftException(
                ValidationCodeMessages.DOCUMENT_SET_STORAGE_ERROR.value.format(
                    details=f"Unexpected error creating table {table_name}: {e}"
                ),
                error_code=ErrorCode.DOCUMENT_SET_STORAGE_ERROR,
            ) from e

    def upsert_data(self, table_name: str, data: pa.Table) -> None:
        """
        Insert or update rows in a data table by id column.

        Args:
            table_name: Name of the table to upsert into
            data: PyArrow table containing the data to upsert
        """
        self._validate_table_name(table_name)
        if not self.table_exists(table_name):
            raise DatasiftException(
                ValidationCodeMessages.DOCUMENT_SET_TABLE_ERROR.value.format(
                    details=f"Table {table_name} does not exist"
                ),
                status_code=400,
                error_code=ErrorCode.DOCUMENT_SET_STORAGE_ERROR,
            )

        if "id" not in data.schema.names:
            raise DatasiftException(
                ValidationCodeMessages.DOCUMENT_SET_INVALID_DATA.value.format(
                    details="Data must contain an 'id' column for upsert"
                ),
                status_code=400,
                error_code=ErrorCode.DOCUMENT_SET_INVALID_DATA,
            )

        try:
            self._handle_schema_evolution(table_name, data.schema)

            with self.connection_manager.get_connection(self.database_path) as conn:
                conn.register("temp_data", data)

                for col_name in data.schema.names:
                    self._validate_column_name(col_name)

                quoted_columns = [self._quote_identifier(col) for col in data.schema.names]
                column_names = ", ".join(quoted_columns)

                upsert_sql = f"""
                INSERT OR REPLACE INTO {table_name} ({column_names})
                SELECT {column_names} FROM temp_data
                """

                conn.execute(upsert_sql)
                conn.unregister("temp_data")

                logger.debug(f"Upserted {len(data)} rows into {table_name}")
        except DatasiftException:
            raise
        except duckdb.Error as e:
            raise DatasiftException(
                ValidationCodeMessages.DOCUMENT_SET_STORAGE_ERROR.value.format(
                    details=f"Failed to upsert data into {table_name}: {e}"
                ),
                error_code=ErrorCode.DOCUMENT_SET_STORAGE_ERROR,
            ) from e
        except Exception as e:
            raise DatasiftException(
                ValidationCodeMessages.DOCUMENT_SET_STORAGE_ERROR.value.format(
                    details=f"Unexpected error upserting data into {table_name}: {e}"
                ),
                error_code=ErrorCode.DOCUMENT_SET_STORAGE_ERROR,
            ) from e

    def read_data(self, table_name: str, limit: int | None = None, offset: int | None = None) -> pa.Table:
        """
        Read data from a table with pagination support.

        Args:
            table_name: Name of the table to read from
            limit: Maximum number of rows to return
            offset: Number of rows to skip

        Returns:
            PyArrow table containing the requested data
        """
        self._validate_table_name(table_name)
        if not self.table_exists(table_name):
            raise DatasiftException(
                ValidationCodeMessages.DOCUMENT_SET_TABLE_ERROR.value.format(
                    details=f"Table {table_name} does not exist"
                ),
                status_code=400,
                error_code=ErrorCode.DOCUMENT_SET_STORAGE_ERROR,
            )

        try:
            query = f"SELECT * FROM {table_name}"

            if limit is not None:
                query += f" LIMIT {limit}"
            if offset is not None:
                query += f" OFFSET {offset}"

            read_only = self.database_path != ":memory:"
            with self.connection_manager.get_connection(self.database_path, read_only=read_only) as conn:
                result = conn.execute(query).fetch_arrow_table()
                logger.debug(f"Read {len(result)} rows from {table_name} (limit={limit}, offset={offset})")
                return result
        except DatasiftException:
            raise
        except duckdb.Error as e:
            raise DatasiftException(
                ValidationCodeMessages.DOCUMENT_SET_STORAGE_ERROR.value.format(
                    details=f"Failed to read data from {table_name}: {e}"
                ),
                error_code=ErrorCode.DOCUMENT_SET_STORAGE_ERROR,
            ) from e
        except Exception as e:
            raise DatasiftException(
                ValidationCodeMessages.DOCUMENT_SET_STORAGE_ERROR.value.format(
                    details=f"Unexpected error reading data from {table_name}: {e}"
                ),
                error_code=ErrorCode.DOCUMENT_SET_STORAGE_ERROR,
            ) from e

    def compute_metrics(self, table_name: str) -> dict:
        """
        Calculate metrics from stored data.

        Args:
            table_name: Name of the table to compute metrics for

        Returns:
            Dictionary with total_documents, total_size_bytes, total_pages
        """
        self._validate_table_name(table_name)
        if not self.table_exists(table_name):
            raise DatasiftException(
                ValidationCodeMessages.DOCUMENT_SET_TABLE_ERROR.value.format(
                    details=f"Table {table_name} does not exist"
                ),
                status_code=400,
                error_code=ErrorCode.DOCUMENT_SET_STORAGE_ERROR,
            )

        try:
            read_only = self.database_path != ":memory:"
            with self.connection_manager.get_connection(self.database_path, read_only=read_only) as conn:
                schema_query = f"DESCRIBE {table_name}"
                schema_result = conn.execute(schema_query).fetchall()
                columns = [row[0] for row in schema_result]

                count_query = f"SELECT COUNT(*) as total FROM {table_name}"
                count_result = conn.execute(count_query).fetchone()
                total_documents = count_result[0] if count_result else 0

                total_size_bytes = 0
                if "size" in columns:
                    size_query = f"SELECT COALESCE(SUM(size), 0) as total FROM {table_name}"
                    size_result = conn.execute(size_query).fetchone()
                    total_size_bytes = size_result[0] if size_result else 0

                total_pages = 0
                if "pages_processed" in columns:
                    pages_query = f"SELECT COALESCE(SUM(pages_processed), 0) as total FROM {table_name}"
                    pages_result = conn.execute(pages_query).fetchone()
                    total_pages = pages_result[0] if pages_result else 0

                metrics = {
                    "total_documents": total_documents,
                    "total_size_bytes": total_size_bytes,
                    "total_pages": total_pages,
                }

                logger.debug(f"Computed metrics for {table_name}: {metrics}")
                return metrics
        except DatasiftException:
            raise
        except duckdb.Error as e:
            raise DatasiftException(
                ValidationCodeMessages.DOCUMENT_SET_STORAGE_ERROR.value.format(
                    details=f"Failed to compute metrics for {table_name}: {e}"
                ),
                error_code=ErrorCode.DOCUMENT_SET_STORAGE_ERROR,
            ) from e
        except Exception as e:
            raise DatasiftException(
                ValidationCodeMessages.DOCUMENT_SET_STORAGE_ERROR.value.format(
                    details=f"Unexpected error computing metrics for {table_name}: {e}"
                ),
                error_code=ErrorCode.DOCUMENT_SET_STORAGE_ERROR,
            ) from e

    def delete_rows(self, table_name: str, ids: list[str]) -> int:
        """
        Delete rows from a table by id list.

        Args:
            table_name: Name of the table to delete from
            ids: List of id values to delete

        Returns:
            Number of rows deleted
        """
        self._validate_table_name(table_name)
        if not self.table_exists(table_name):
            raise DatasiftException(
                ValidationCodeMessages.DOCUMENT_SET_TABLE_ERROR.value.format(
                    details=f"Table {table_name} does not exist"
                ),
                status_code=400,
                error_code=ErrorCode.DOCUMENT_SET_STORAGE_ERROR,
            )

        if not ids:
            return 0

        try:
            with self.connection_manager.get_connection(self.database_path) as conn:
                placeholders = ", ".join(["?" for _ in ids])
                count_sql = f"SELECT COUNT(*) FROM {table_name} WHERE id IN ({placeholders})"
                count_result = conn.execute(count_sql, ids).fetchone()
                rows_to_delete = count_result[0] if count_result else 0

                delete_sql = f"DELETE FROM {table_name} WHERE id IN ({placeholders})"
                conn.execute(delete_sql, ids)

                logger.debug(f"Deleted {rows_to_delete} rows from {table_name}")
                return rows_to_delete
        except DatasiftException:
            raise
        except duckdb.Error as e:
            raise DatasiftException(
                ValidationCodeMessages.DOCUMENT_SET_STORAGE_ERROR.value.format(
                    details=f"Failed to delete rows from {table_name}: {e}"
                ),
                error_code=ErrorCode.DOCUMENT_SET_STORAGE_ERROR,
            ) from e
        except Exception as e:
            raise DatasiftException(
                ValidationCodeMessages.DOCUMENT_SET_STORAGE_ERROR.value.format(
                    details=f"Unexpected error deleting rows from {table_name}: {e}"
                ),
                error_code=ErrorCode.DOCUMENT_SET_STORAGE_ERROR,
            ) from e

    def delete_table(self, table_name: str) -> None:
        """
        Delete a data table.

        Args:
            table_name: Name of the table to delete
        """
        self._validate_table_name(table_name)
        if not self.table_exists(table_name):
            raise DatasiftException(
                ValidationCodeMessages.DOCUMENT_SET_TABLE_ERROR.value.format(
                    details=f"Table {table_name} does not exist"
                ),
                status_code=400,
                error_code=ErrorCode.DOCUMENT_SET_STORAGE_ERROR,
            )

        try:
            with self.connection_manager.get_connection(self.database_path) as conn:
                conn.execute(f"DROP TABLE IF EXISTS {table_name}")
                logger.info(f"Deleted table: {table_name}")
        except DatasiftException:
            raise
        except duckdb.Error as e:
            raise DatasiftException(
                ValidationCodeMessages.DOCUMENT_SET_STORAGE_ERROR.value.format(
                    details=f"Failed to delete table {table_name}: {e}"
                ),
                error_code=ErrorCode.DOCUMENT_SET_STORAGE_ERROR,
            ) from e
        except Exception as e:
            raise DatasiftException(
                ValidationCodeMessages.DOCUMENT_SET_STORAGE_ERROR.value.format(
                    details=f"Unexpected error deleting table {table_name}: {e}"
                ),
                error_code=ErrorCode.DOCUMENT_SET_STORAGE_ERROR,
            ) from e

    def table_exists(self, table_name: str) -> bool:
        """
        Check if a table exists.

        Args:
            table_name: Name of the table to check

        Returns:
            True if table exists, False otherwise
        """
        self._validate_table_name(table_name)
        try:
            read_only = self.database_path != ":memory:"
            with self.connection_manager.get_connection(self.database_path, read_only=read_only) as conn:
                query = """
                SELECT COUNT(*) FROM information_schema.tables
                WHERE table_name = ?
                """
                result = conn.execute(query, [table_name]).fetchone()
                return result[0] > 0 if result else False
        except Exception as e:
            logger.error(f"Failed to check if table {table_name} exists: {e}")
            return False

    def get_table_schema(self, table_name: str) -> pa.Schema:
        """
        Get the current schema of a table.

        Args:
            table_name: Name of the table

        Returns:
            PyArrow schema of the table
        """
        self._validate_table_name(table_name)
        if not self.table_exists(table_name):
            raise DatasiftException(
                ValidationCodeMessages.DOCUMENT_SET_TABLE_ERROR.value.format(
                    details=f"Table {table_name} does not exist"
                ),
                status_code=400,
                error_code=ErrorCode.DOCUMENT_SET_STORAGE_ERROR,
            )

        try:
            read_only = self.database_path != ":memory:"
            with self.connection_manager.get_connection(self.database_path, read_only=read_only) as conn:
                query = f"SELECT * FROM {table_name} LIMIT 1"
                result = conn.execute(query).fetch_arrow_table()
                return result.schema
        except DatasiftException:
            raise
        except duckdb.Error as e:
            raise DatasiftException(
                ValidationCodeMessages.DOCUMENT_SET_STORAGE_ERROR.value.format(
                    details=f"Failed to get schema for {table_name}: {e}"
                ),
                error_code=ErrorCode.DOCUMENT_SET_STORAGE_ERROR,
            ) from e
        except Exception as e:
            raise DatasiftException(
                ValidationCodeMessages.DOCUMENT_SET_STORAGE_ERROR.value.format(
                    details=f"Unexpected error getting schema for {table_name}: {e}"
                ),
                error_code=ErrorCode.DOCUMENT_SET_STORAGE_ERROR,
            ) from e

    def _pyarrow_to_duckdb_type(self, pa_type: pa.DataType) -> str:
        """
        Convert PyArrow type to DuckDB type.

        Args:
            pa_type: PyArrow data type

        Returns:
            DuckDB type string
        """
        if pa.types.is_string(pa_type) or pa.types.is_large_string(pa_type):
            return "VARCHAR"
        elif pa.types.is_int64(pa_type):
            return "BIGINT"
        elif pa.types.is_int32(pa_type):
            return "INTEGER"
        elif pa.types.is_int16(pa_type):
            return "SMALLINT"
        elif pa.types.is_int8(pa_type):
            return "TINYINT"
        elif pa.types.is_float64(pa_type):
            return "DOUBLE"
        elif pa.types.is_float32(pa_type):
            return "FLOAT"
        elif pa.types.is_boolean(pa_type):
            return "BOOLEAN"
        elif pa.types.is_binary(pa_type) or pa.types.is_large_binary(pa_type):
            return "BLOB"
        elif pa.types.is_timestamp(pa_type):
            return "TIMESTAMP"
        elif pa.types.is_date(pa_type):
            return "DATE"
        elif pa.types.is_time(pa_type):
            return "TIME"
        elif pa.types.is_list(pa_type) or pa.types.is_large_list(pa_type):
            return "JSON"
        elif pa.types.is_struct(pa_type):
            return "JSON"
        elif pa.types.is_map(pa_type):
            return "JSON"
        else:
            logger.warning(f"Unknown PyArrow type {pa_type}, defaulting to VARCHAR")
            return "VARCHAR"

    def _handle_schema_evolution(self, table_name: str, new_schema: pa.Schema) -> None:
        """
        Handle schema evolution by adding new columns if needed.

        Args:
            table_name: Name of the table
            new_schema: New PyArrow schema with potential new columns
        """
        current_schema = self.get_table_schema(table_name)
        current_columns = set(current_schema.names)
        new_columns = set(new_schema.names)

        columns_to_add = new_columns - current_columns

        if columns_to_add:
            with self.connection_manager.get_connection(self.database_path) as conn:
                for col_name in columns_to_add:
                    self._validate_column_name(col_name)
                    quoted_col = self._quote_identifier(col_name)

                    field = new_schema.field(col_name)
                    duckdb_type = self._pyarrow_to_duckdb_type(field.type)

                    alter_sql = f"ALTER TABLE {table_name} ADD COLUMN {quoted_col} {duckdb_type}"
                    conn.execute(alter_sql)
                    logger.info(f"Added column {col_name} to {table_name}")
