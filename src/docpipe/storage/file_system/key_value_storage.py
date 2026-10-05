"""Filesystem storage adapter implementing KeyValueStorage interface."""

import json
import threading
from pathlib import Path
from typing import Any, ClassVar

from docpipe.exceptions.docpipe_exceptions import DocpipeException
from docpipe.exceptions.error_codes import ErrorCode
from docpipe.storage.exceptions import StorageValidationError
from docpipe.storage.interfaces.key_value_storage import KeyValueStorage
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger(__name__)


class FileSystemStorage(KeyValueStorage):
    """
    Thread-safe singleton filesystem storage implementation.

    Stores records as JSON files: {base_dir}/{collection}/{key}.json

    Implements singleton pattern per base directory to ensure only one instance
    exists for each unique directory, preventing redundant file system access
    and improving consistency.

    Example:
        storage = FileSystemStorage(base_dir="data/assets")
        storage.save_record(
            collection="flows",
            key="flow-123",
            data={"name": "my_flow", "id": "flow-123"}
        )
        # Creates: data/assets/flows/flow-123.json
    """

    # Class-level cache for singleton instances per base directory
    _instances: ClassVar[dict[str, "FileSystemStorage"]] = {}
    _lock: ClassVar[threading.Lock] = threading.Lock()

    # Instance variable to track initialization state
    _initialized: bool

    def __new__(cls, *, base_dir: str) -> "FileSystemStorage":
        """
        Singleton pattern - one instance per base directory.

        Args:
            base_dir: Base directory for storage

        Returns:
            Singleton instance for the given base directory
        """
        # Normalize path for consistent lookup
        normalized_path = str(Path(base_dir).resolve())

        with cls._lock:
            if normalized_path not in cls._instances:
                instance = super().__new__(cls)
                cls._instances[normalized_path] = instance
                # Mark as not initialized yet
                instance._initialized = False
            return cls._instances[normalized_path]

    def __init__(self, *, base_dir: str):
        """
        Initialize filesystem storage.

        Only initializes once per base directory due to singleton pattern.

        Args:
            base_dir: Base directory for storage
        """
        # Skip initialization if already initialized
        if self._initialized:
            return

        self.base_dir = Path(base_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._initialized = True
        logger.info(f"Initialized FileSystemStorage at: {self.base_dir}")

    def _validate_collection_name(self, *, collection: str) -> None:
        """Validate collection name for security."""
        if not collection:
            raise StorageValidationError(message="Collection name cannot be empty")
        if ".." in collection or "/" in collection or "\\" in collection:
            raise StorageValidationError(
                message=f"Invalid collection name: {collection}. "
                "Collection names cannot contain path traversal characters"
            )

    def _validate_key(self, *, key: str) -> None:
        """Validate key for security."""
        if not key:
            raise StorageValidationError(message="Key cannot be empty")
        if ".." in key or "/" in key or "\\" in key:
            raise StorageValidationError(message=f"Invalid key: {key}. Keys cannot contain path traversal characters")

    def _get_collection_dir(self, *, collection: str) -> Path:
        """Get directory path for a collection."""
        self._validate_collection_name(collection=collection)
        return self.base_dir / collection

    def _get_record_path(self, *, collection: str, key: str) -> Path:
        """Get file path for a record."""
        self._validate_key(key=key)
        return self._get_collection_dir(collection=collection) / f"{key}.json"

    def save_record(self, *, collection: str, key: str, data: dict[str, Any]) -> None:
        """Save a record to a collection."""
        try:
            collection_dir = self._get_collection_dir(collection=collection)
            collection_dir.mkdir(parents=True, exist_ok=True)

            record_path = self._get_record_path(collection=collection, key=key)
            temp_path = record_path.with_suffix(".tmp")

            # Atomic write: write to temp file, then rename
            with temp_path.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)

            temp_path.replace(record_path)
            logger.debug(f"Saved record: {collection}/{key}")

        except StorageValidationError:
            # Re-raise validation errors without wrapping
            raise
        except Exception as e:
            raise DocpipeException(
                f"Failed to save record {collection}/{key}: {e}",
                error_code=ErrorCode.STORAGE_ERROR,
            ) from e

    def get_record(self, *, collection: str, key: str) -> dict[str, Any] | None:
        """Retrieve a record by key."""
        try:
            record_path = self._get_record_path(collection=collection, key=key)

            if not record_path.exists():
                return None

            with record_path.open(encoding="utf-8") as f:
                data = json.load(f)

            logger.debug(f"Retrieved record: {collection}/{key}")
            return data

        except json.JSONDecodeError as e:
            raise DocpipeException(
                f"Corrupted record {collection}/{key}: {e}",
                error_code=ErrorCode.STORAGE_ERROR,
            ) from e
        except Exception as e:
            raise DocpipeException(
                f"Failed to get record {collection}/{key}: {e}",
                error_code=ErrorCode.STORAGE_ERROR,
            ) from e

    def list_records(self, *, collection: str, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """List all records in a collection."""
        try:
            collection_dir = self._get_collection_dir(collection=collection)

            if not collection_dir.exists():
                return []

            records = []
            for record_file in collection_dir.glob("*.json"):
                try:
                    with record_file.open(encoding="utf-8") as f:
                        data = json.load(f)
                    records.append(data)
                except Exception as e:
                    logger.warning(f"Failed to read {record_file.name}: {e}")
                    continue

            logger.debug(f"Listed {len(records)} records from {collection}")
            return records

        except Exception as e:
            raise DocpipeException(
                f"Failed to list records in {collection}: {e}",
                error_code=ErrorCode.STORAGE_ERROR,
            ) from e

    def delete_record(self, *, collection: str, key: str) -> bool:
        """Delete a record by key."""
        try:
            record_path = self._get_record_path(collection=collection, key=key)

            if not record_path.exists():
                return False

            record_path.unlink()
            logger.debug(f"Deleted record: {collection}/{key}")
            return True

        except Exception as e:
            raise DocpipeException(
                f"Failed to delete record {collection}/{key}: {e}",
                error_code=ErrorCode.STORAGE_ERROR,
            ) from e

    def collection_exists(self, *, collection: str) -> bool:
        """Check if a collection exists."""
        collection_dir = self._get_collection_dir(collection=collection)
        return collection_dir.exists() and collection_dir.is_dir()

    def record_exists(self, *, collection: str, key: str) -> bool:
        """Check if a record exists."""
        record_path = self._get_record_path(collection=collection, key=key)
        return record_path.exists()
