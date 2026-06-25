"""DuckDB implementation of DocumentLibraryRepository.

This adapter implements the repository port using a hybrid approach:
- KeyValueStorage for library metadata (following Document Sets pattern)
- Direct SQL for junction table operations (relational data)
"""

import time
from datetime import datetime
from typing import Any

from docpipe.core.assets.document_libraries.domain.models.document_library import DocumentLibrary
from docpipe.core.assets.document_libraries.domain.ports.document_library_repository import (
    DocumentLibraryRepository,
)
from docpipe.core.assets.document_libraries.domain.types import HealthCheckResult
from docpipe.core.assets.document_libraries.factories.document_library_repository_factory import (
    DocumentLibraryRepositoryFactory,
)
from docpipe.core.constants.constants import DocpipeConstants, DocumentLibraryConstants
from docpipe.exceptions.docpipe_exceptions import DocpipeException
from docpipe.exceptions.error_codes import ErrorCode
from docpipe.storage.interfaces.key_value_storage import KeyValueStorage
from docpipe.utils.duckdb.connection_manager import DuckDBConnectionManager
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger(__name__)


@DocumentLibraryRepositoryFactory.register(name="duckdb", display_name="DuckDB")
class DuckDBDocumentLibraryMetadataRepository(DocumentLibraryRepository):
    """DuckDB implementation of DocumentLibraryRepository for metadata persistence.

    Hybrid approach:
    - Uses KeyValueStorage for library metadata (simple CRUD)
    - Uses direct SQL for junction table operations (relational, bulk operations)

    This follows the Document Sets pattern while accommodating relational requirements.
    """

    COLLECTION_NAME = "document_libraries"

    def __init__(self, *, key_value_storage: KeyValueStorage, database_path: str) -> None:
        """Initialize repository with injected storage.

        Args:
            key_value_storage: KeyValueStorage implementation (DuckDB-based)
            database_path: Path to DuckDB database file (for junction table and health checks)
        """
        self.storage = key_value_storage
        self._database_path = database_path
        self._connection_manager = DuckDBConnectionManager()
        self._initialize_junction_table()
        logger.info("DuckDBDocumentLibraryMetadataRepository initialized with KeyValueStorage")

    def _initialize_junction_table(self) -> None:
        """Initialize junction table for library-documentset relationships.

        This table is managed separately from KeyValueStorage as it's relational data.
        """
        try:
            with self._connection_manager.get_connection(database_path=self._database_path) as conn:
                # Create junction table if it doesn't exist
                conn.execute(f"""
                    CREATE TABLE IF NOT EXISTS {DocpipeConstants.LIBRARY_DOCUMENTSET_JUNCTION_TABLE} (
                        library_id VARCHAR NOT NULL,
                        document_set_id VARCHAR NOT NULL,
                        added_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (library_id, document_set_id)
                    )
                """)

                # Create indexes for better query performance
                conn.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_junction_library
                    ON {DocpipeConstants.LIBRARY_DOCUMENTSET_JUNCTION_TABLE}(library_id)
                """)

                conn.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_junction_docset
                    ON {DocpipeConstants.LIBRARY_DOCUMENTSET_JUNCTION_TABLE}(document_set_id)
                """)

                logger.debug("Junction table initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize junction table: {e}")
            raise DocpipeException(
                f"Failed to initialize junction table: {e}",
                status_code=500,
                error_code=ErrorCode.DOCUMENT_LIBRARY_STORAGE_ERROR,
            ) from e

    def create(self, *, library: DocumentLibrary) -> DocumentLibrary:
        """Create a new document library.

        Args:
            library: DocumentLibrary entity to create

        Returns:
            The created library

        Raises:
            DocpipeException: If library with same name exists
            DocpipeException: If storage operation fails
        """
        try:
            # Check if library with same ID already exists
            if self.storage.record_exists(collection=self.COLLECTION_NAME, key=library.library_id):
                raise DocpipeException(
                    f"Library with ID '{library.library_id}' already exists",
                    status_code=409,
                    error_code=ErrorCode.DOCUMENT_LIBRARY_ALREADY_EXISTS,
                )

            # Check if library with same name already exists
            if self.exists_by_name(name=library.name):
                raise DocpipeException(
                    f"Library with name '{library.name}' already exists",
                    status_code=409,
                    error_code=ErrorCode.DOCUMENT_LIBRARY_ALREADY_EXISTS,
                )

            # Convert to dict and save using KeyValueStorage
            data = self._library_to_dict(library=library)
            self.storage.save_record(collection=self.COLLECTION_NAME, key=library.library_id, data=data)

            logger.info(f"Created library: {library.library_id}")
            return library

        except DocpipeException:
            raise
        except Exception as e:
            raise DocpipeException(
                f"Failed to create library: {e}",
                status_code=500,
                error_code=ErrorCode.DOCUMENT_LIBRARY_STORAGE_ERROR,
            ) from e

    def get_by_id(self, *, library_id: str) -> DocumentLibrary | None:
        """Retrieve a document library by its ID.

        Args:
            library_id: Unique identifier of the library

        Returns:
            DocumentLibrary entity if found, None otherwise

        Raises:
            DocpipeException: If storage operation fails
        """
        try:
            data = self.storage.get_record(collection=self.COLLECTION_NAME, key=library_id)

            if data is None:
                return None

            # Get associated document set IDs from junction table
            doc_set_ids = self.get_document_sets_for_library(library_id=library_id)

            return self._dict_to_library(data=data, document_set_ids=doc_set_ids)

        except Exception as e:
            raise DocpipeException(
                f"Failed to get library by ID: {e}",
                status_code=500,
                error_code=ErrorCode.DOCUMENT_LIBRARY_STORAGE_ERROR,
            ) from e

    def get_by_name(self, *, name: str) -> DocumentLibrary | None:
        """Retrieve a document library by its name.

        Args:
            name: Name of the library

        Returns:
            DocumentLibrary entity if found, None otherwise

        Raises:
            DocpipeException: If storage operation fails
        """
        try:
            # List all records and find by name
            all_records = self.storage.list_records(collection=self.COLLECTION_NAME)

            for data in all_records:
                if data.get("name") == name:
                    library_id = data.get("library_id")
                    if library_id:
                        doc_set_ids = self.get_document_sets_for_library(library_id=library_id)
                        return self._dict_to_library(data=data, document_set_ids=doc_set_ids)

            return None

        except Exception as e:
            raise DocpipeException(
                f"Failed to get library by name: {e}",
                status_code=500,
                error_code=ErrorCode.DOCUMENT_LIBRARY_STORAGE_ERROR,
            ) from e

    def update(self, *, library: DocumentLibrary) -> DocumentLibrary:
        """Update an existing document library.

        Args:
            library: DocumentLibrary entity with updated data

        Returns:
            Updated library

        Raises:
            DocpipeException: If library doesn't exist
            DocpipeException: If storage operation fails
        """
        try:
            # Check if library exists
            if not self.exists(library_id=library.library_id):
                raise DocpipeException(
                    f"Library {library.library_id} not found",
                    status_code=404,
                    error_code=ErrorCode.DOCUMENT_LIBRARY_NOT_FOUND,
                )

            # Convert to dict and save (upsert)
            data = self._library_to_dict(library=library)
            self.storage.save_record(collection=self.COLLECTION_NAME, key=library.library_id, data=data)

            logger.info(f"Updated library: {library.library_id}")
            return library

        except DocpipeException:
            raise
        except Exception as e:
            raise DocpipeException(
                f"Failed to update library: {e}",
                status_code=500,
                error_code=ErrorCode.DOCUMENT_LIBRARY_STORAGE_ERROR,
            ) from e

    def delete(self, *, library_id: str) -> bool:
        """Delete a document library by its ID.

        Args:
            library_id: Unique identifier of the library to delete

        Returns:
            True if library was deleted, False if not found

        Raises:
            DocpipeException: If storage operation fails
        """
        try:
            # Check if library exists
            if not self.exists(library_id=library_id):
                return False

            # Delete from KeyValueStorage
            deleted = self.storage.delete_record(collection=self.COLLECTION_NAME, key=library_id)

            # Delete junction table entries
            if deleted:
                with self._connection_manager.get_connection(database_path=self._database_path) as conn:
                    conn.execute(
                        f"DELETE FROM {DocpipeConstants.LIBRARY_DOCUMENTSET_JUNCTION_TABLE} WHERE library_id = ?",
                        (library_id,),
                    )

            logger.info(f"Deleted library: {library_id}")
            return deleted

        except Exception as e:
            raise DocpipeException(
                f"Failed to delete library: {e}",
                status_code=500,
                error_code=ErrorCode.DOCUMENT_LIBRARY_STORAGE_ERROR,
            ) from e

    def list_all(
        self,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[DocumentLibrary]:
        """Retrieve all document libraries with optional pagination.

        Args:
            limit: Maximum number of libraries to return (None for all)
            offset: Number of libraries to skip (for pagination)

        Returns:
            List of document libraries

        Raises:
            DocpipeException: If storage operation fails
        """
        try:
            all_records = self.storage.list_records(collection=self.COLLECTION_NAME)

            # Sort by name
            all_records.sort(key=lambda x: x.get("name", ""))

            # Apply pagination
            if offset is not None:
                all_records = all_records[offset:]
            if limit is not None:
                all_records = all_records[:limit]

            libraries = []
            for data in all_records:
                library_id = data.get("library_id")
                if library_id:
                    doc_set_ids = self.get_document_sets_for_library(library_id=library_id)
                    library = self._dict_to_library(data=data, document_set_ids=doc_set_ids)
                    libraries.append(library)

            return libraries

        except Exception as e:
            raise DocpipeException(
                f"Failed to list libraries: {e}",
                status_code=500,
                error_code=ErrorCode.DOCUMENT_LIBRARY_STORAGE_ERROR,
            ) from e

    def exists(self, *, library_id: str) -> bool:
        """Check if a document library exists.

        Args:
            library_id: Unique identifier of the library

        Returns:
            True if library exists, False otherwise

        Raises:
            DocpipeException: If storage operation fails
        """
        try:
            return self.storage.record_exists(collection=self.COLLECTION_NAME, key=library_id)
        except Exception as e:
            raise DocpipeException(
                f"Failed to check library existence: {e}",
                status_code=500,
                error_code=ErrorCode.DOCUMENT_LIBRARY_STORAGE_ERROR,
            ) from e

    def exists_by_name(self, *, name: str) -> bool:
        """Check if a document library with given name exists.

        Args:
            name: Name of the library

        Returns:
            True if library with name exists, False otherwise

        Raises:
            DocpipeException: If storage operation fails
        """
        try:
            all_records = self.storage.list_records(collection=self.COLLECTION_NAME)
            return any(record.get("name") == name for record in all_records)
        except Exception as e:
            raise DocpipeException(
                f"Failed to check library name existence: {e}",
                status_code=500,
                error_code=ErrorCode.DOCUMENT_LIBRARY_STORAGE_ERROR,
            ) from e

    def add_document_set_to_library(
        self,
        *,
        library_id: str,
        document_set_id: str,
    ) -> None:
        """Add a document set to a library (junction table operation).

        Args:
            library_id: ID of the library
            document_set_id: ID of the document set to add

        Raises:
            DocpipeException: If library doesn't exist
            DocpipeException: If storage operation fails
        """
        try:
            # Check if library exists
            if not self.exists(library_id=library_id):
                raise DocpipeException(
                    f"Library {library_id} not found",
                    status_code=404,
                    error_code=ErrorCode.DOCUMENT_LIBRARY_NOT_FOUND,
                )

            # Insert into junction table using direct SQL
            with self._connection_manager.get_connection(database_path=self._database_path) as conn:
                conn.execute(
                    f"""
                    INSERT INTO {DocpipeConstants.LIBRARY_DOCUMENTSET_JUNCTION_TABLE}
                    (library_id, document_set_id, added_at)
                    VALUES (?, ?, ?)
                    """,
                    (library_id, document_set_id, datetime.utcnow()),
                )

            logger.info(f"Added document set {document_set_id} to library {library_id}")

        except DocpipeException:
            raise
        except Exception as e:
            raise DocpipeException(
                f"Failed to add document set to library: {e}",
                status_code=500,
                error_code=ErrorCode.DOCUMENT_LIBRARY_STORAGE_ERROR,
            ) from e

    def remove_document_set_from_library(
        self,
        *,
        library_id: str,
        document_set_id: str,
    ) -> None:
        """Remove a document set from a library (junction table operation).

        Args:
            library_id: ID of the library
            document_set_id: ID of the document set to remove

        Raises:
            DocpipeException: If library doesn't exist
            DocpipeException: If document set not in library
            DocpipeException: If storage operation fails
        """
        try:
            # Check if library exists
            if not self.exists(library_id=library_id):
                raise DocpipeException(
                    f"Library {library_id} not found",
                    status_code=404,
                    error_code=ErrorCode.DOCUMENT_LIBRARY_NOT_FOUND,
                )

            # Check if document set is in library
            doc_sets = self.get_document_sets_for_library(library_id=library_id)
            if document_set_id not in doc_sets:
                raise DocpipeException(
                    f"Document set {document_set_id} not found in library {library_id}",
                    status_code=404,
                    error_code=ErrorCode.DOCUMENT_SET_NOT_FOUND,
                )

            # Delete from junction table using direct SQL
            with self._connection_manager.get_connection(database_path=self._database_path) as conn:
                conn.execute(
                    f"""
                    DELETE FROM {DocpipeConstants.LIBRARY_DOCUMENTSET_JUNCTION_TABLE}
                    WHERE library_id = ? AND document_set_id = ?
                    """,
                    (library_id, document_set_id),
                )

            logger.info(f"Removed document set {document_set_id} from library {library_id}")

        except DocpipeException:
            raise
        except Exception as e:
            raise DocpipeException(
                f"Failed to remove document set from library: {e}",
                status_code=500,
                error_code=ErrorCode.DOCUMENT_LIBRARY_STORAGE_ERROR,
            ) from e

    def get_document_sets_for_library(
        self,
        *,
        library_id: str,
    ) -> list[str]:
        """Get all document set IDs associated with a library.

        Args:
            library_id: ID of the library

        Returns:
            List of document set IDs (empty list if library doesn't exist or has no sets)

        Raises:
            DocpipeException: If storage operation fails
        """
        try:
            # Don't check if library exists - just return empty list if no junction entries
            # This avoids circular dependency during library retrieval

            # Query junction table using direct SQL
            with self._connection_manager.get_connection(database_path=self._database_path) as conn:
                result = conn.execute(
                    f"""
                    SELECT document_set_id
                    FROM {DocpipeConstants.LIBRARY_DOCUMENTSET_JUNCTION_TABLE}
                    WHERE library_id = ?
                    ORDER BY added_at
                    """,
                    (library_id,),
                ).fetchall()

                return [row[0] for row in result]

        except Exception as e:
            raise DocpipeException(
                f"Failed to get document sets for library: {e}",
                status_code=500,
                error_code=ErrorCode.DOCUMENT_LIBRARY_STORAGE_ERROR,
            ) from e

    def add_document_sets_bulk(
        self,
        *,
        library_id: str,
        document_set_ids: list[str],
    ) -> None:
        """Add multiple document sets to a library in a single database operation.

        Uses a single INSERT statement with multiple VALUES for efficiency.

        Args:
            library_id: ID of the library
            document_set_ids: List of document set IDs to add

        Raises:
            DocpipeException: If library doesn't exist
            DocpipeException: If storage operation fails
        """
        try:
            # Check if library exists
            if not self.exists(library_id=library_id):
                raise DocpipeException(
                    f"Library {library_id} not found",
                    status_code=404,
                    error_code=ErrorCode.DOCUMENT_LIBRARY_NOT_FOUND,
                )

            if not document_set_ids:
                return

            # Validate bulk operation size
            if len(document_set_ids) > DocumentLibraryConstants.MAX_BULK_OPERATION_SIZE:
                raise DocpipeException(
                    f"Bulk operation size ({len(document_set_ids)}) exceeds maximum allowed "
                    f"({DocumentLibraryConstants.MAX_BULK_OPERATION_SIZE})",
                    status_code=400,
                    error_code=ErrorCode.DOCUMENT_LIBRARY_INVALID_DATA,
                )

            # Build single INSERT with multiple VALUES
            placeholders = ", ".join(["(?, ?, ?)"] * len(document_set_ids))
            query = f"""
                INSERT INTO {DocpipeConstants.LIBRARY_DOCUMENTSET_JUNCTION_TABLE}
                (library_id, document_set_id, added_at)
                VALUES {placeholders}
            """

            # Flatten params: (lib_id, doc_set_id, timestamp) for each document set
            timestamp = datetime.utcnow()
            params = []
            for doc_set_id in document_set_ids:
                params.extend([library_id, doc_set_id, timestamp])

            # Execute query with performance tracking
            start_time = time.time()
            with self._connection_manager.get_connection(database_path=self._database_path) as conn:
                conn.execute(query, tuple(params))
            duration = time.time() - start_time

            logger.info(f"Bulk added {len(document_set_ids)} document sets to library {library_id} in {duration:.3f}s")

        except DocpipeException:
            raise
        except Exception as e:
            raise DocpipeException(
                f"Failed to bulk add document sets to library: {e}",
                status_code=500,
                error_code=ErrorCode.DOCUMENT_LIBRARY_STORAGE_ERROR,
            ) from e

    def remove_document_sets_bulk(
        self,
        *,
        library_id: str,
        document_set_ids: list[str],
    ) -> None:
        """Remove multiple document sets from a library in a single database operation.

        Uses a single DELETE statement with IN clause for efficiency.

        Args:
            library_id: ID of the library
            document_set_ids: List of document set IDs to remove

        Raises:
            DocpipeException: If library doesn't exist
            DocpipeException: If storage operation fails
        """
        try:
            # Check if library exists
            if not self.exists(library_id=library_id):
                raise DocpipeException(
                    f"Library {library_id} not found",
                    status_code=404,
                    error_code=ErrorCode.DOCUMENT_LIBRARY_NOT_FOUND,
                )

            if not document_set_ids:
                return

            # Validate bulk operation size
            if len(document_set_ids) > DocumentLibraryConstants.MAX_BULK_OPERATION_SIZE:
                raise DocpipeException(
                    f"Bulk operation size ({len(document_set_ids)}) exceeds maximum allowed "
                    f"({DocumentLibraryConstants.MAX_BULK_OPERATION_SIZE})",
                    status_code=400,
                    error_code=ErrorCode.DOCUMENT_LIBRARY_INVALID_DATA,
                )

            # Build single DELETE with IN clause
            placeholders = ", ".join(["?"] * len(document_set_ids))
            query = f"""
                DELETE FROM {DocpipeConstants.LIBRARY_DOCUMENTSET_JUNCTION_TABLE}
                WHERE library_id = ? AND document_set_id IN ({placeholders})
            """

            params = (library_id, *document_set_ids)

            # Execute query with performance tracking
            start_time = time.time()
            with self._connection_manager.get_connection(database_path=self._database_path) as conn:
                conn.execute(query, params)
            duration = time.time() - start_time

            logger.info(
                f"Bulk removed {len(document_set_ids)} document sets from library {library_id} in {duration:.3f}s"
            )

        except DocpipeException:
            raise
        except Exception as e:
            raise DocpipeException(
                f"Failed to bulk remove document sets from library: {e}",
                status_code=500,
                error_code=ErrorCode.DOCUMENT_LIBRARY_STORAGE_ERROR,
            ) from e

    def count_all(self) -> int:
        """Count total number of document libraries.

        Returns:
            Total count of libraries

        Raises:
            DocpipeException: If storage operation fails
        """
        try:
            all_records = self.storage.list_records(collection=self.COLLECTION_NAME)
            return len(all_records)
        except Exception as e:
            raise DocpipeException(
                f"Failed to count libraries: {e}",
                status_code=500,
                error_code=ErrorCode.DOCUMENT_LIBRARY_STORAGE_ERROR,
            ) from e

    def health_check(self) -> HealthCheckResult:
        """Check the health status of the repository.

        Returns:
            A dictionary containing health status information

        Raises:
            No exceptions should be raised; errors should be reflected in the result
        """
        try:
            # Test KeyValueStorage connectivity
            collection_exists = self.storage.collection_exists(collection=self.COLLECTION_NAME)

            # Test junction table connectivity
            with self._connection_manager.get_connection(database_path=self._database_path) as conn:
                conn.execute(f"SELECT COUNT(*) FROM {DocpipeConstants.LIBRARY_DOCUMENTSET_JUNCTION_TABLE}").fetchone()

            return HealthCheckResult(
                healthy=True,
                message="Repository is healthy",
                details={
                    "database_path": self._database_path,
                    "collection_exists": collection_exists,
                    "junction_table_accessible": True,
                },
            )
        except Exception as e:
            return HealthCheckResult(
                healthy=False,
                message=f"Health check failed: {e}",
                details={
                    "database_path": self._database_path,
                    "error": str(e),
                },
            )

    @classmethod
    def validate_config(cls, *, config: dict[str, Any]) -> list[str]:
        """Validate repository configuration.

        Args:
            config: Configuration dictionary to validate

        Returns:
            List of validation error messages, empty if configuration is valid
        """
        errors = []

        # Validate database_path
        if "database_path" not in config:
            errors.append("Missing required configuration: 'database_path'")
        elif not isinstance(config["database_path"], str):
            errors.append("Configuration 'database_path' must be a string")
        elif not config["database_path"]:
            errors.append("Configuration 'database_path' cannot be empty")

        return errors

    def _library_to_dict(self, *, library: DocumentLibrary) -> dict[str, Any]:
        """Convert a DocumentLibrary domain object to a dictionary.

        Args:
            library: DocumentLibrary domain object

        Returns:
            Dictionary representation suitable for storage
        """
        return {
            "library_id": library.library_id,
            "name": library.name,
            "description": library.description,
            "purpose": library.purpose,
            "original_size": library.original_size,
            "final_size": library.final_size,
            "tags": library.tags or [],
            "created_by": library.created_by,
            "href": library.href,
        }

    def _dict_to_library(self, *, data: dict[str, Any], document_set_ids: list[str]) -> DocumentLibrary:
        """Convert a dictionary to a DocumentLibrary domain object.

        Args:
            data: Dictionary from storage
            document_set_ids: List of associated document set IDs

        Returns:
            DocumentLibrary domain object
        """
        return DocumentLibrary(
            library_id=data["library_id"],
            name=data["name"],
            description=data.get("description"),
            purpose=data.get("purpose"),
            original_size=data.get("original_size"),
            final_size=data.get("final_size"),
            tags=data.get("tags", []),
            created_by=data.get("created_by"),
            href=data.get("href"),
            document_set_ids=document_set_ids,
        )
