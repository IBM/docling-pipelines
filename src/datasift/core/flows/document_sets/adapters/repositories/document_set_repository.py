"""Repository layer for DocumentSet CRUD operations.

This module provides the DocumentSetRepository class that handles all database
operations for document set metadata using the storage layer abstraction.
"""

import json
from datetime import datetime

import duckdb

from datasift.core.flows.document_sets.domain.models.data_card import DataCard
from datasift.core.flows.document_sets.domain.models.document_set import DocumentSet
from datasift.core.flows.document_sets.domain.models.storage_reference import StorageReference
from datasift.exceptions.datasift_exceptions import DatasiftException
from datasift.exceptions.error_codes import ErrorCode
from datasift.exceptions.error_messages import ValidationCodeMessages
from datasift.storage.duckdb_storage import DuckDBStorage
from datasift.utils.infrastructure.logging import get_logger

logger = get_logger(__name__)


class DocumentSetRepository:
    """Repository for DocumentSet metadata CRUD operations.

    Provides a high-level interface for managing document set metadata in the
    storage layer. Handles conversion between domain objects and database rows,
    JSON serialization/deserialization, and proper error handling.

    Note: Currently implemented for DuckDB storage. The storage parameter
    should be a DuckDBStorage instance.

    Attributes:
        storage: DuckDB storage backend implementation for database operations
    """

    def __init__(self, storage: DuckDBStorage) -> None:
        """Initialize the repository with a DuckDB storage backend.

        Args:
            storage: DuckDB storage backend implementation
        """
        self.storage = storage
        # Ensure metadata table exists
        self.storage.create_metadata_table()
        logger.info("DocumentSetRepository initialized")

    def create(self, document_set: DocumentSet) -> DocumentSet:
        """Create a new document set metadata entry.

        Validates the document set and inserts into the metadata table.
        Database uniqueness constraints will handle duplicate prevention.

        Args:
            document_set: DocumentSet domain object to create

        Returns:
            Created DocumentSet with timestamps set

        Raises:
            DocumentSetInvalidDataException: If validation fails
            Exception: If database operation fails (including constraint violations)
        """
        # Validate the document set
        document_set.validate()

        # Ensure ID is set
        if not document_set.id:
            raise DatasiftException(
                ValidationCodeMessages.DOCUMENT_SET_INVALID_DATA.format(details="Document set ID cannot be None"),
                status_code=400,
                error_code=ErrorCode.DOCUMENT_SET_INVALID_DATA,
            )

        # Prepare SQL insert statement
        insert_sql = """
        INSERT INTO document_sets (
            id, name, description, storage_backend, database_path, table_name,
            total_documents, total_size_bytes, total_pages,
            created_at, updated_at, metadata
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        # Serialize JSON fields
        metadata_json = json.dumps(document_set.metadata) if document_set.metadata else None

        # Execute insert
        with self.storage.connection_manager.get_connection(self.storage.database_path) as conn:
            conn.execute(
                insert_sql,
                [
                    document_set.id,
                    document_set.name,
                    document_set.description,
                    document_set.storage_backend,
                    document_set.database_path,
                    document_set.table_name,
                    document_set.total_documents,
                    document_set.total_size_bytes,
                    document_set.total_pages,
                    document_set.created_at,
                    document_set.updated_at,
                    metadata_json,
                ],
            )

        logger.info(f"Created document set: {document_set.id} (name: {document_set.name})")
        return document_set

    def update(self, document_set: DocumentSet) -> DocumentSet:
        """Update an existing document set metadata entry.

        Updates the document set and automatically updates the updated_at timestamp.

        Args:
            document_set: DocumentSet domain object with updated data

        Returns:
            Updated DocumentSet

        Raises:
            DocumentSetNotFoundException: If document set not found
            DocumentSetInvalidDataException: If validation fails
            Exception: If database operation fails
        """
        # Validate the document set
        document_set.validate()

        # Ensure ID is set
        if not document_set.id:
            raise DatasiftException(
                ValidationCodeMessages.DOCUMENT_SET_INVALID_DATA.format(details="Document set ID cannot be None"),
                status_code=400,
                error_code=ErrorCode.DOCUMENT_SET_INVALID_DATA,
            )

        # Update timestamp
        document_set.update_timestamp()

        # Prepare SQL update statement
        update_sql = """
        UPDATE document_sets
        SET name = ?, description = ?, storage_backend = ?, database_path = ?,
            table_name = ?, total_documents = ?, total_size_bytes = ?,
            total_pages = ?, updated_at = ?, metadata = ?
        WHERE id = ?
        """

        # Serialize JSON fields
        metadata_json = json.dumps(document_set.metadata) if document_set.metadata else None

        # Execute update and check affected rows
        with self.storage.connection_manager.get_connection(self.storage.database_path) as conn:
            result = conn.execute(
                update_sql,
                [
                    document_set.name,
                    document_set.description,
                    document_set.storage_backend,
                    document_set.database_path,
                    document_set.table_name,
                    document_set.total_documents,
                    document_set.total_size_bytes,
                    document_set.total_pages,
                    document_set.updated_at,
                    metadata_json,
                    document_set.id,
                ],
            )

            # Check if any rows were affected
            rows_affected = result.fetchone()
            if rows_affected is None or rows_affected[0] == 0:
                raise DatasiftException(
                    ValidationCodeMessages.DOCUMENT_SET_NOT_FOUND.value.format(document_set_id=document_set.id),
                    status_code=404,
                    error_code=ErrorCode.DOCUMENT_SET_NOT_FOUND,
                )

        logger.info(f"Updated document set: {document_set.id}")
        return document_set

    def save(self, document_set: DocumentSet) -> DocumentSet:
        """Save a document set (create or update based on existence).

        Performs a true upsert operation: tries to create, if constraint violation
        occurs (document already exists), updates instead.

        Args:
            document_set: DocumentSet domain object to save

        Returns:
            Saved DocumentSet

        Raises:
            DocumentSetInvalidDataException: If validation fails
            Exception: If database operation fails
        """
        # Ensure ID is set
        if not document_set.id:
            raise DatasiftException(
                ValidationCodeMessages.DOCUMENT_SET_INVALID_DATA.format(details="Document set ID cannot be None"),
                status_code=400,
                error_code=ErrorCode.DOCUMENT_SET_INVALID_DATA,
            )

        try:
            # Try to create first
            return self.create(document_set)
        except duckdb.ConstraintException:
            # Handle constraint violation (duplicate key)
            logger.debug(f"Document set {document_set.id} exists, updating instead")
            return self.update(document_set)

    def get_by_id(self, document_set_id: str) -> DocumentSet | None:
        """Retrieve a document set by ID.

        Args:
            document_set_id: Unique identifier of the document set

        Returns:
            DocumentSet if found, None otherwise

        Raises:
            Exception: If database operation fails
        """
        query = "SELECT * FROM document_sets WHERE id = ?"

        # Use read-only connection for in-memory databases
        read_only = self.storage.database_path != ":memory:"
        with self.storage.connection_manager.get_connection(self.storage.database_path, read_only=read_only) as conn:
            result = conn.execute(query, [document_set_id]).fetchone()

            if result is None:
                logger.debug(f"Document set not found: {document_set_id}")
                return None

            # Convert row to DocumentSet
            document_set = self._row_to_document_set(result)
            logger.debug(f"Retrieved document set: {document_set_id}")
            return document_set

    def get_by_name(self, name: str) -> DocumentSet | None:
        """Retrieve a document set by name.

        Args:
            name: Unique name of the document set

        Returns:
            DocumentSet if found, None otherwise

        Raises:
            Exception: If database operation fails
        """
        query = "SELECT * FROM document_sets WHERE name = ?"

        # Use read-only connection for in-memory databases
        read_only = self.storage.database_path != ":memory:"
        with self.storage.connection_manager.get_connection(self.storage.database_path, read_only=read_only) as conn:
            result = conn.execute(query, [name]).fetchone()

            if result is None:
                logger.debug(f"Document set not found by name: {name}")
                return None

            # Convert row to DocumentSet
            document_set = self._row_to_document_set(result)
            logger.debug(f"Retrieved document set by name: {name}")
            return document_set

    def list_all(self, limit: int | None = None, offset: int | None = None) -> list[DocumentSet]:
        """List all document sets with pagination support.

        Args:
            limit: Maximum number of document sets to return (None for all)
            offset: Number of document sets to skip (None for 0)

        Returns:
            List of DocumentSet objects

        Raises:
            Exception: If database operation fails
        """
        query = "SELECT * FROM document_sets ORDER BY created_at DESC"

        if limit is not None:
            query += f" LIMIT {limit}"
        if offset is not None:
            query += f" OFFSET {offset}"

        # Use read-only connection for in-memory databases
        read_only = self.storage.database_path != ":memory:"
        with self.storage.connection_manager.get_connection(self.storage.database_path, read_only=read_only) as conn:
            results = conn.execute(query).fetchall()

            # Convert rows to DocumentSet objects
            document_sets = [self._row_to_document_set(row) for row in results]

            logger.debug(f"Retrieved {len(document_sets)} document sets (limit={limit}, offset={offset})")
            return document_sets

    def exists(self, document_set_id: str) -> bool:
        """Check if a document set exists by ID.

        Args:
            document_set_id: Unique identifier to check

        Returns:
            True if document set exists, False otherwise

        Raises:
            Exception: If database operation fails
        """
        query = "SELECT COUNT(*) FROM document_sets WHERE id = ?"

        # Use read-only connection for in-memory databases
        read_only = self.storage.database_path != ":memory:"
        with self.storage.connection_manager.get_connection(self.storage.database_path, read_only=read_only) as conn:
            result = conn.execute(query, [document_set_id]).fetchone()
            exists = result[0] > 0 if result else False
            return exists

    def exists_by_name(self, name: str) -> bool:
        """Check if a document set exists by name.

        Args:
            name: Unique name to check

        Returns:
            True if document set exists, False otherwise

        Raises:
            Exception: If database operation fails
        """
        query = "SELECT COUNT(*) FROM document_sets WHERE name = ?"

        # Use read-only connection for in-memory databases
        read_only = self.storage.database_path != ":memory:"
        with self.storage.connection_manager.get_connection(self.storage.database_path, read_only=read_only) as conn:
            result = conn.execute(query, [name]).fetchone()
            exists = result[0] > 0 if result else False
            return exists

    def delete(self, document_set_id: str) -> bool:
        """Delete a document set metadata entry.

        Deletes the metadata entry from the document_sets table. Optionally,
        the caller can also delete the associated data table if needed.

        Args:
            document_set_id: Unique identifier of the document set to delete

        Returns:
            True if document set was deleted, False if not found

        Raises:
            Exception: If database operation fails
        """
        # Check if document set exists
        if not self.exists(document_set_id):
            logger.info(f"Document set not found for deletion: {document_set_id}")
            return False

        # Delete from metadata table
        delete_sql = "DELETE FROM document_sets WHERE id = ?"

        with self.storage.connection_manager.get_connection(self.storage.database_path) as conn:
            conn.execute(delete_sql, [document_set_id])

        logger.info(f"Deleted document set: {document_set_id}")
        return True

    def _row_to_document_set(self, row: tuple) -> DocumentSet:
        """Convert a database row to a DocumentSet domain object.

        Handles deserialization of JSON fields and datetime parsing.

        Args:
            row: Database row tuple

        Returns:
            DocumentSet domain object
        """
        # Extract fields from row
        (
            id_val,
            name,
            description,
            storage_backend,
            database_path,
            table_name,
            total_documents,
            total_size_bytes,
            total_pages,
            created_at,
            updated_at,
            metadata_json,
        ) = row

        # Deserialize JSON fields
        metadata = json.loads(metadata_json) if metadata_json else {}

        # Parse timestamps
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))

        # Create storage reference
        storage_reference = StorageReference(
            backend_type=storage_backend, database_path=database_path, table_name=table_name
        )

        # Extract data card from metadata if present
        data_card = None
        if "data_card" in metadata:
            data_card = DataCard.from_dict(metadata["data_card"])

        # Create and return DocumentSet
        return DocumentSet(
            id=id_val,
            name=name,
            description=description,
            storage_backend=storage_backend,
            database_path=database_path,
            table_name=table_name,
            total_documents=total_documents,
            total_size_bytes=total_size_bytes,
            total_pages=total_pages,
            created_at=created_at,
            updated_at=updated_at,
            metadata=metadata,
            storage_reference=storage_reference,
            data_card=data_card,
        )
