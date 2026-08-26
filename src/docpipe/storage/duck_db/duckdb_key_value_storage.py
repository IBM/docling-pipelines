"""DuckDB storage implementation for key-value records."""

import json
import threading
from pathlib import Path
from typing import Any, ClassVar

import duckdb

from docpipe.core.job_management.adapters.config.flow_definition_snapshot_storage_factory import (
    register_flow_definition_snapshot_storage,
)
from docpipe.exceptions.docpipe_exceptions import DocpipeException
from docpipe.exceptions.error_codes import ErrorCode
from docpipe.storage.exceptions import StorageValidationError
from docpipe.storage.interfaces.key_value_storage_port import KeyValueStoragePort
from docpipe.utils.duckdb import DuckDBConnectionManager
from docpipe.utils.infrastructure.logging import get_logger

_IN_MEMORY_DB = ":memory:"


logger = get_logger(__name__)


@register_flow_definition_snapshot_storage
class DuckDBKeyValueStorage(KeyValueStoragePort):
    """
    Thread-safe singleton DuckDB storage implementation for key-value records.

    Stores records in collection-specific tables with JSON data column.
    Schema: (key VARCHAR PRIMARY KEY, data JSON, created_at TIMESTAMP, updated_at TIMESTAMP)

    Implements singleton pattern per database path to ensure only one instance
    exists for each unique database, preventing redundant initializations and
    connection overhead.

    Example:
        storage = DuckDBKeyValueStorage(database_path="data/assets.db")
        storage.save_record(
            collection="flows",
            key="flow-123",
            data={"name": "my_flow", "id": "flow-123"}
        )
        # Creates table 'flows' if not exists and inserts record
    """

    STORE_BACKEND = "duckdb"

    # Class-level cache for singleton instances per database path
    _instances: ClassVar[dict[str, "DuckDBKeyValueStorage"]] = {}
    _lock: ClassVar[threading.Lock] = threading.Lock()

    # Instance variable to track initialization state
    _initialized: bool

    def __new__(cls, *, database_path: str) -> "DuckDBKeyValueStorage":
        """
        Singleton pattern - one instance per database path.

        Args:
            database_path: Path to DuckDB database file

        Returns:
            Singleton instance for the given database path
        """
        # Normalize path for consistent lookup
        normalized_path = str(Path(database_path).resolve()) if database_path != _IN_MEMORY_DB else database_path

        with cls._lock:
            if normalized_path not in cls._instances:
                instance = super().__new__(cls)
                cls._instances[normalized_path] = instance
                # Mark as not initialized yet
                instance._initialized = False
            return cls._instances[normalized_path]

    def __init__(self, *, database_path: str):
        """
        Initialize DuckDB key-value storage.

        Only initializes once per database path due to singleton pattern.

        Args:
            database_path: Path to DuckDB database file
        """
        # Skip initialization if already initialized
        if self._initialized:
            return

        self.database_path = database_path
        db_path = Path(database_path)
        if database_path != _IN_MEMORY_DB:
            db_path.parent.mkdir(parents=True, exist_ok=True)

        self.connection_manager = DuckDBConnectionManager()
        self._initialized = True
        logger.info(f"Initialized DuckDBKeyValueStorage at: {database_path}")

    def _validate_collection(self, *, collection: str) -> None:
        """Validate collection name for security."""
        if not collection:
            raise StorageValidationError(message="Collection name cannot be empty")
        if not collection.replace("_", "").isalnum():
            raise StorageValidationError(
                message=f"Invalid collection name: {collection}. "
                "Must contain only alphanumeric characters and underscores."
            )

    def _validate_key(self, *, key: str) -> None:
        """Validate key for security."""
        if not key:
            raise StorageValidationError(message="Key cannot be empty")

    def _ensure_collection_table(self, *, collection: str) -> None:
        """
        Ensure collection table exists.

        Args:
            collection: Collection name (becomes table name)
        """
        self._validate_collection(collection=collection)

        create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS {collection} (
            key VARCHAR PRIMARY KEY,
            data JSON NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """

        try:
            with self.connection_manager.get_connection(self.database_path) as conn:
                conn.execute(create_table_sql)
                logger.debug(f"Ensured collection table exists: {collection}")
        except duckdb.Error as e:
            raise DocpipeException(
                f"Failed to create collection table {collection}: {e}",
                error_code=ErrorCode.STORAGE_ERROR,
            ) from e

    def save_record(self, *, collection: str, key: str, data: dict[str, Any]) -> None:
        """Save a record to a collection."""
        self._validate_key(key=key)
        self._ensure_collection_table(collection=collection)

        try:
            json_data = json.dumps(data)

            # Use INSERT OR REPLACE for upsert behavior
            insert_sql = f"""
            INSERT OR REPLACE INTO {collection} (key, data, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            """

            with self.connection_manager.get_connection(self.database_path) as conn:
                conn.execute(insert_sql, [key, json_data])
                logger.debug(f"Saved record: {collection}/{key}")

        except (TypeError, ValueError) as e:
            raise DocpipeException(
                f"Failed to serialize data for {collection}/{key}: {e}",
                error_code=ErrorCode.STORAGE_VALIDATION_ERROR,
            ) from e
        except duckdb.Error as e:
            raise DocpipeException(
                f"Failed to save record {collection}/{key}: {e}",
                error_code=ErrorCode.STORAGE_ERROR,
            ) from e

    def get_record(self, *, collection: str, key: str) -> dict[str, Any] | None:
        """Retrieve a record by key."""
        if not self.collection_exists(collection=collection):
            return None

        try:
            select_sql = f"SELECT data FROM {collection} WHERE key = ?"  # nosec B608 — collection name is an internal constant, not user-supplied input

            read_only = self.database_path != _IN_MEMORY_DB
            with self.connection_manager.get_connection(self.database_path, read_only=read_only) as conn:
                result = conn.execute(select_sql, [key]).fetchone()

                if result is None:
                    return None

                data = json.loads(result[0])
                logger.debug(f"Retrieved record: {collection}/{key}")
                return data

        except json.JSONDecodeError as e:
            raise DocpipeException(
                f"Corrupted data for {collection}/{key}: {e}",
                error_code=ErrorCode.STORAGE_ERROR,
            ) from e
        except duckdb.Error as e:
            raise DocpipeException(
                f"Failed to get record {collection}/{key}: {e}",
                error_code=ErrorCode.STORAGE_ERROR,
            ) from e

    def list_records(self, *, collection: str, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """List all records in a collection."""
        if not self.collection_exists(collection=collection):
            return []

        try:
            select_sql = f"SELECT data FROM {collection}"  # nosec B608 — collection name is an internal constant, not user-supplied input

            read_only = self.database_path != _IN_MEMORY_DB
            with self.connection_manager.get_connection(self.database_path, read_only=read_only) as conn:
                results = conn.execute(select_sql).fetchall()

                records = []
                for row in results:
                    try:
                        data = json.loads(row[0])
                        records.append(data)
                    except json.JSONDecodeError as e:
                        logger.warning(f"Skipping corrupted record in {collection}: {e}")
                        continue

                logger.debug(f"Listed {len(records)} records from {collection}")
                return records

        except duckdb.Error as e:
            raise DocpipeException(
                f"Failed to list records in {collection}: {e}",
                error_code=ErrorCode.STORAGE_ERROR,
            ) from e

    def delete_record(self, *, collection: str, key: str) -> bool:
        """Delete a record by key."""
        if not self.collection_exists(collection=collection):
            return False

        try:
            delete_sql = f"DELETE FROM {collection} WHERE key = ?"  # nosec B608 — collection name is an internal constant, not user-supplied input

            with self.connection_manager.get_connection(self.database_path) as conn:
                conn.execute(delete_sql, [key])
                # Check if record was deleted by verifying it no longer exists
                check_result = conn.execute(f"SELECT COUNT(*) FROM {collection} WHERE key = ?", [key]).fetchone()  # nosec B608 — collection name is an internal constant, not user-supplied input
                deleted = check_result[0] == 0 if check_result else False

                if deleted:
                    logger.debug(f"Deleted record: {collection}/{key}")

                return deleted

        except duckdb.Error as e:
            raise DocpipeException(
                f"Failed to delete record {collection}/{key}: {e}",
                error_code=ErrorCode.STORAGE_ERROR,
            ) from e

    def collection_exists(self, *, collection: str) -> bool:
        """Check if a collection exists."""
        try:
            check_sql = """
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_name = ?
            """

            read_only = self.database_path != _IN_MEMORY_DB
            with self.connection_manager.get_connection(self.database_path, read_only=read_only) as conn:
                result = conn.execute(check_sql, [collection]).fetchone()
                return result[0] > 0 if result else False

        except duckdb.Error:
            return False

    def record_exists(self, *, collection: str, key: str) -> bool:
        """Check if a record exists."""
        if not self.collection_exists(collection=collection):
            return False

        try:
            check_sql = f"SELECT COUNT(*) FROM {collection} WHERE key = ?"  # nosec B608 — collection name is an internal constant, not user-supplied input

            read_only = self.database_path != _IN_MEMORY_DB
            with self.connection_manager.get_connection(self.database_path, read_only=read_only) as conn:
                result = conn.execute(check_sql, [key]).fetchone()
                return result[0] > 0 if result else False

        except duckdb.Error:
            return False
