"""DuckDB implementation of DocumentLibraryRepository.

This adapter implements the repository port using DuckDB storage.
"""

import json
import time
from datetime import datetime

from docpipe.core.assets.document_libraries.adapters.storage.duckdb_storage import DuckDBStorage
from docpipe.core.assets.document_libraries.domain.models.document_library import DocumentLibrary
from docpipe.core.assets.document_libraries.domain.ports.document_library_repository import (
    DocumentLibraryRepository,
)
from docpipe.core.constants.constants import DocpipeConstants, DocumentLibraryConstants
from docpipe.exceptions.docpipe_exceptions import DocpipeException
from docpipe.exceptions.error_codes import ErrorCode
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger()


class DuckDBDocumentLibraryMetadataRepository(DocumentLibraryRepository):
    """DuckDB implementation of DocumentLibraryRepository for metadata persistence.

    Implements the repository port using DuckDB for persistence.
    Manages document library metadata and library-documentset relationships.
    Stores only metadata, not document content.
    """

    def __init__(self, *, storage: DuckDBStorage):
        """Initialize repository with DuckDB storage.

        Args:
            storage: DuckDB storage instance
        """
        self.storage = storage
        self.storage.initialize_tables()

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
            # Check if library with same name already exists
            if self.exists_by_name(name=library.name):
                raise DocpipeException(
                    f"Library with name '{library.name}' already exists",
                    status_code=409,
                    error_code=ErrorCode.DOCUMENT_LIBRARY_ALREADY_EXISTS,
                )

            # Insert library metadata
            query = f"""
                INSERT INTO {DocpipeConstants.DOCUMENT_LIBRARY_TABLE_NAME}
                (library_id, name, description, purpose, original_size, final_size, tags, created_by, href)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """

            # Serialize tags to JSON string if present
            tags_json = json.dumps(library.tags) if library.tags else None

            self.storage.execute_query(
                query=query,
                params=(
                    library.library_id,
                    library.name,
                    library.description,
                    library.purpose,
                    library.original_size,
                    library.final_size,
                    tags_json,
                    library.created_by,
                    library.href,
                ),
            )

            logger.info(msg=f"Created library: {library.library_id}")
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
            query = f"""
                SELECT library_id, name, description, purpose, original_size, final_size, tags, created_by, href
                FROM {DocpipeConstants.DOCUMENT_LIBRARY_TABLE_NAME}
                WHERE library_id = ?
            """

            row = self.storage.fetch_one(query=query, params=(library_id,))

            if row is None:
                return None

            # Get associated document set IDs
            doc_set_ids = self.get_document_sets_for_library(library_id=library_id)

            return self._row_to_library(row=row, document_set_ids=doc_set_ids)

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
            query = f"""
                SELECT library_id, name, description, purpose, original_size, final_size, tags, created_by, href
                FROM {DocpipeConstants.DOCUMENT_LIBRARY_TABLE_NAME}
                WHERE name = ?
            """

            row = self.storage.fetch_one(query=query, params=(name,))

            if row is None:
                return None

            # Get associated document set IDs
            library_id = row[0]
            doc_set_ids = self.get_document_sets_for_library(library_id=library_id)

            return self._row_to_library(row=row, document_set_ids=doc_set_ids)

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

            # Update library metadata
            query = f"""
                UPDATE {DocpipeConstants.DOCUMENT_LIBRARY_TABLE_NAME}
                SET name = ?,
                    description = ?,
                    purpose = ?,
                    original_size = ?,
                    final_size = ?,
                    tags = ?,
                    created_by = ?,
                    href = ?
                WHERE library_id = ?
            """

            # Serialize tags to JSON string if present
            tags_json = json.dumps(library.tags) if library.tags else None

            self.storage.execute_query(
                query=query,
                params=(
                    library.name,
                    library.description,
                    library.purpose,
                    library.original_size,
                    library.final_size,
                    tags_json,
                    library.created_by,
                    library.href,
                    library.library_id,
                ),
            )

            logger.info(msg=f"Updated library: {library.library_id}")
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

            # Delete library (CASCADE will delete junction table entries)
            query = f"""
                DELETE FROM {DocpipeConstants.DOCUMENT_LIBRARY_TABLE_NAME}
                WHERE library_id = ?
            """

            self.storage.execute_query(query=query, params=(library_id,))

            logger.info(msg=f"Deleted library: {library_id}")
            return True

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
            query = f"""
                SELECT library_id, name, description, purpose, original_size, final_size, tags, created_by, href
                FROM {DocpipeConstants.DOCUMENT_LIBRARY_TABLE_NAME}
                ORDER BY name ASC
            """

            if limit is not None:
                query += f" LIMIT {limit}"
            if offset is not None:
                query += f" OFFSET {offset}"

            rows = self.storage.fetch_all(query=query)

            libraries = []
            for row in rows:
                library_id = row[0]
                doc_set_ids = self.get_document_sets_for_library(library_id=library_id)
                library = self._row_to_library(row=row, document_set_ids=doc_set_ids)
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
            query = f"""
                SELECT COUNT(*) FROM {DocpipeConstants.DOCUMENT_LIBRARY_TABLE_NAME}
                WHERE library_id = ?
            """

            row = self.storage.fetch_one(query=query, params=(library_id,))
            return row[0] > 0 if row else False

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
            query = f"""
                SELECT COUNT(*) FROM {DocpipeConstants.DOCUMENT_LIBRARY_TABLE_NAME}
                WHERE name = ?
            """

            row = self.storage.fetch_one(query=query, params=(name,))
            return row[0] > 0 if row else False

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

            # Insert into junction table
            query = f"""
                INSERT INTO {DocpipeConstants.LIBRARY_DOCUMENTSET_JUNCTION_TABLE}
                (library_id, document_set_id, added_at)
                VALUES (?, ?, ?)
            """

            self.storage.execute_query(
                query=query,
                params=(library_id, document_set_id, datetime.utcnow()),
            )

            logger.info(msg=f"Added document set {document_set_id} to library {library_id}")

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

            # Delete from junction table
            query = f"""
                DELETE FROM {DocpipeConstants.LIBRARY_DOCUMENTSET_JUNCTION_TABLE}
                WHERE library_id = ? AND document_set_id = ?
            """

            self.storage.execute_query(
                query=query,
                params=(library_id, document_set_id),
            )

            logger.info(msg=f"Removed document set {document_set_id} from library {library_id}")

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
            List of document set IDs

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

            query = f"""
                SELECT document_set_id
                FROM {DocpipeConstants.LIBRARY_DOCUMENTSET_JUNCTION_TABLE}
                WHERE library_id = ?
                ORDER BY added_at
            """

            rows = self.storage.fetch_all(query=query, params=(library_id,))
            return [row[0] for row in rows]

        except DocpipeException:
            raise
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
            # INSERT INTO table (col1, col2, col3) VALUES (?, ?, ?), (?, ?, ?), ...
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
            self.storage.execute_query(query=query, params=tuple(params))
            duration = time.time() - start_time

            logger.info(
                msg=f"Bulk added {len(document_set_ids)} document sets to library {library_id} in {duration:.3f}s"
            )

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
            # DELETE FROM table WHERE library_id = ? AND document_set_id IN (?, ?, ?)
            placeholders = ", ".join(["?"] * len(document_set_ids))
            query = f"""
                DELETE FROM {DocpipeConstants.LIBRARY_DOCUMENTSET_JUNCTION_TABLE}
                WHERE library_id = ? AND document_set_id IN ({placeholders})
            """

            params = (library_id, *document_set_ids)

            # Execute query with performance tracking
            start_time = time.time()
            self.storage.execute_query(query=query, params=params)
            duration = time.time() - start_time

            logger.info(
                msg=f"Bulk removed {len(document_set_ids)} document sets from library {library_id} in {duration:.3f}s"
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
            query = f"""
                SELECT COUNT(*) FROM {DocpipeConstants.DOCUMENT_LIBRARY_TABLE_NAME}
            """

            row = self.storage.fetch_one(query=query)
            return row[0] if row else 0

        except Exception as e:
            raise DocpipeException(
                f"Failed to count libraries: {e}",
                status_code=500,
                error_code=ErrorCode.DOCUMENT_LIBRARY_STORAGE_ERROR,
            ) from e

    def _row_to_library(self, *, row: tuple, document_set_ids: list[str]) -> DocumentLibrary:
        """Convert database row to DocumentLibrary entity.

        Args:
            row: Database row tuple
            document_set_ids: List of associated document set IDs

        Returns:
            DocumentLibrary entity

        Row format: (library_id, name, description, purpose, original_size, final_size, tags, created_by, href)
        """
        # Deserialize tags from JSON string if present, otherwise use empty list
        tags_list: list[str] = json.loads(row[6]) if row[6] else []

        return DocumentLibrary(
            library_id=row[0],
            name=row[1],
            description=row[2],
            purpose=row[3],
            original_size=row[4],
            final_size=row[5],
            tags=tags_list,
            created_by=row[7],
            href=row[8],
            document_set_ids=document_set_ids,
        )
