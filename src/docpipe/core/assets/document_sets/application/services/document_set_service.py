"""Application service for document set management operations.

Provides business logic orchestration for document sets, coordinating between
repository (metadata) and storage (data) layers.

Exception Handling:
    Service layer raises business logic exceptions (DocumentSetNotFoundException,
    DocumentSetAlreadyExistsException, DocumentSetInvalidDataException) directly.
    Infrastructure exceptions from repository/storage layers bubble up naturally
    and are handled by the error_handler middleware.
"""

import re
from uuid import uuid4

import pyarrow as pa

from docpipe.core.assets.document_sets.domain.models.document_set import DocumentSet
from docpipe.core.assets.document_sets.domain.ports import (
    DocumentSetDataStore,
    DocumentSetMetadataRepository,
)
from docpipe.exceptions.docpipe_exceptions import DocpipeException
from docpipe.exceptions.error_codes import ErrorCode
from docpipe.exceptions.error_messages import ValidationCodeMessages
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger(__name__)


class DocumentSetService:
    """Application service for document set business logic orchestration.

    Coordinates between repository (metadata) and storage (data) layers to provide
    high-level document set operations. Handles validation, transactions, and
    metric computation.

    Attributes:
        _metadata_repository: Repository port for document set metadata operations
        _data_store: Data store port for document data operations
    """

    def __init__(
        self,
        *,
        metadata_repository: DocumentSetMetadataRepository,
        data_store: DocumentSetDataStore,
    ) -> None:
        """Initialize the service with port dependencies.

        Args:
            metadata_repository: Repository port for document set metadata CRUD operations
            data_store: Data store port for document data operations
        """
        self._metadata_repository = metadata_repository
        self._data_store = data_store
        self.repository = metadata_repository
        self.data_store = data_store
        self.storage = getattr(data_store, "storage", None)
        logger.debug(
            "DocumentSetService initialized with metadata_repository: %s, data_store: %s",
            type(metadata_repository).__name__,
            type(data_store).__name__,
        )

    def create_document_set(
        self, *, name: str, description: str | None, database_path: str, metadata: dict | None = None
    ) -> DocumentSet:
        """Create or retrieve a document set (get-or-create pattern).

        Implements idempotent document set creation: if a document set with the
        given name already exists, it is returned. Otherwise, a new one is created.
        This makes the operation safe for use in pipelines where the same document
        set name may be used across multiple runs.

        Args:
            name: Unique name for the document set (must start with letter,
                 contain only letters/digits/spaces/underscores, ≤128 chars)
            description: Optional description (≤2000 chars)
            database_path: Path to the database file for storage
            metadata: Optional additional metadata as key-value pairs

        Returns:
            DocumentSet (existing or newly created) with ID and timestamps

        Raises:
            DocumentSetInvalidDataException: If validation fails (invalid name, etc.)
            Exception: If database operation fails

        Example:
            >>> service = DocumentSetService(repository, storage)
            >>> # First call creates the document set
            >>> doc_set = service.create_document_set(
            ...     name="My Documents",
            ...     description="Collection of research papers",
            ...     database_path="/data/documents.db",
            ...     metadata={"source": "research_portal"}
            ... )
            >>> # Second call with same name returns existing document set
            >>> same_doc_set = service.create_document_set(
            ...     name="My Documents",
            ...     description="Different description",  # Ignored
            ...     database_path="/data/documents.db"
            ... )
            >>> assert doc_set.id == same_doc_set.id
        """
        # First, try to get existing document set by name
        try:
            existing = self._metadata_repository.get_by_name(name=name)
            if existing:
                logger.info(
                    "Document set with name '%s' already exists (ID: %s), returning existing", name, existing.id
                )
                return existing
        except Exception:
            # If get_by_name fails for any reason, proceed to create
            pass

        # Validate database path for security
        validated_database_path = self._validate_database_path(database_path)

        # Generate unique ID
        document_set_id = str(uuid4())

        # Sanitize name to create table name
        table_name = self._sanitize_table_name(name)

        # Create document set domain object
        document_set = DocumentSet(
            id=document_set_id,
            name=name,
            description=description,
            database_path=validated_database_path,
            table_name=table_name,
            metadata=metadata or {},
        )

        # Validate before persistence
        try:
            document_set.validate()
        except Exception as exc:
            raise DocpipeException(
                ValidationCodeMessages.DOCUMENT_SET_INVALID_DATA.format(details=str(exc)),
                status_code=400,
                error_code=ErrorCode.DOCUMENT_SET_INVALID_DATA,
            ) from exc

        logger.info("Creating document set with name: %s", name)

        # Create metadata entry (may fail if race condition occurs)
        try:
            created_document_set = self._metadata_repository.create(document_set=document_set)
            logger.info(
                "Successfully created document set %s with name %s", created_document_set.id, created_document_set.name
            )
            return created_document_set
        except DocpipeException:
            # Re-raise DocpipeException as-is
            raise
        except Exception as e:
            # If creation fails due to duplicate (race condition), try to get by name again
            error_msg = str(e).lower()
            if "unique" in error_msg or "constraint" in error_msg or "duplicate" in error_msg:
                logger.info("Document set with name '%s' was created by another process, retrieving", name)
                existing = self._metadata_repository.get_by_name(name=name)
                if existing:
                    return existing
            # Wrap other exceptions in DocpipeException
            raise DocpipeException(
                ValidationCodeMessages.DOCUMENT_SET_STORAGE_ERROR.format(details=str(e)),
                status_code=500,
                error_code=ErrorCode.DOCUMENT_SET_STORAGE_ERROR,
            ) from e

    def update_document_set(
        self, *, document_set_id: str, description: str | None = None, metadata: dict | None = None
    ) -> DocumentSet:
        """Update document set metadata.

        Updates the description and/or metadata of an existing document set.
        The updated_at timestamp is updated automatically.

        Args:
            document_set_id: Unique identifier of the document set to update
            description: New description (None to keep existing)
            metadata: New metadata dict (None to keep existing)

        Returns:
            Updated DocumentSet with refreshed timestamp

        Raises:
            DocumentSetNotFoundException: If document set not found
            DocumentSetInvalidDataException: If validation fails
            Exception: If database operation fails

        Example:
            >>> updated = service.update_document_set(
            ...     document_set_id="abc-123",
            ...     description="Updated description",
            ...     metadata={"version": "2.0"}
            ... )
        """
        if not document_set_id or not document_set_id.strip():
            raise DocpipeException(
                "document_set_id cannot be empty", status_code=400, error_code=ErrorCode.DOCUMENT_SET_INVALID_DATA
            )

        # Retrieve existing document set
        existing = self._metadata_repository.get_by_id(document_set_id=document_set_id)
        if existing is None:
            raise DocpipeException(
                ValidationCodeMessages.DOCUMENT_SET_NOT_FOUND.format(document_set_id=document_set_id),
                status_code=404,
                error_code=ErrorCode.DOCUMENT_SET_NOT_FOUND,
            )

        # Update fields if provided
        if description is not None:
            existing.description = description
        if metadata is not None:
            existing.metadata = metadata

        # Validate after updates
        try:
            existing.validate()
        except Exception as exc:
            logger.error("Document set validation failed after update: %s", exc)
            raise DocpipeException(
                ValidationCodeMessages.DOCUMENT_SET_INVALID_DATA.format(details=str(exc)),
                status_code=400,
                error_code=ErrorCode.DOCUMENT_SET_INVALID_DATA,
            ) from exc

        # Update in repository
        updated_document_set = self._metadata_repository.update(document_set=existing)

        logger.info("Successfully updated document set %s", document_set_id)
        return updated_document_set

    def get_document_set(self, *, document_set_id: str) -> DocumentSet:
        """Retrieve a document set by ID.

        Args:
            document_set_id: Unique identifier of the document set

        Returns:
            DocumentSet with all metadata

        Raises:
            DocumentSetInvalidDataException: If document_set_id is empty
            DocumentSetNotFoundException: If document set not found
            Exception: If database operation fails

        Example:
            >>> doc_set = service.get_document_set("abc-123")
            >>> print(f"Name: {doc_set.name}, Documents: {doc_set.total_documents}")
        """
        if not document_set_id or not document_set_id.strip():
            raise DocpipeException(
                "document_set_id cannot be empty", status_code=400, error_code=ErrorCode.DOCUMENT_SET_INVALID_DATA
            )

        document_set = self._metadata_repository.get_by_id(document_set_id=document_set_id)

        if document_set is None:
            raise DocpipeException(
                ValidationCodeMessages.DOCUMENT_SET_NOT_FOUND.format(document_set_id=document_set_id),
                status_code=404,
                error_code=ErrorCode.DOCUMENT_SET_NOT_FOUND,
            )

        logger.info("Successfully retrieved document set %s", document_set_id)
        return document_set

    def document_set_exists(self, *, document_set_id: str) -> bool:
        """Check if a document set exists without loading full data.

        This is a lightweight existence check that avoids loading the full
        document set object, making it more efficient for validation purposes.

        Args:
            document_set_id: Unique identifier to check

        Returns:
            True if document set exists, False otherwise

        Example:
            >>> if service.document_set_exists(document_set_id="abc-123"):
            ...     print("Document set exists")
        """
        if not document_set_id or not document_set_id.strip():
            return False
        return self._metadata_repository.exists(document_set_id=document_set_id)

    def get_document_set_by_name(self, *, name: str) -> DocumentSet:
        """Retrieve a document set by name.

        Args:
            name: Unique name of the document set

        Returns:
            DocumentSet with all metadata

        Raises:
            DocumentSetInvalidDataException: If name is empty
            DocumentSetNotFoundException: If document set not found
            Exception: If database operation fails

        Example:
            >>> doc_set = service.get_document_set_by_name("My Documents")
            >>> print(f"ID: {doc_set.id}")
        """
        if not name or not name.strip():
            raise DocpipeException(
                "name cannot be empty", status_code=400, error_code=ErrorCode.DOCUMENT_SET_INVALID_DATA
            )

        document_set = self._metadata_repository.get_by_name(name=name)

        if document_set is None:
            raise DocpipeException(
                ValidationCodeMessages.DOCUMENT_SET_NOT_FOUND.format(document_set_id=name),
                status_code=404,
                error_code=ErrorCode.DOCUMENT_SET_NOT_FOUND,
            )

        logger.info("Successfully retrieved document set by name: %s", name)
        return document_set

    def list_document_sets(self, *, limit: int | None = None, offset: int | None = None) -> list[DocumentSet]:
        """List document sets with pagination.

        Args:
            limit: Maximum number of document sets to return (None for all)
            offset: Number of document sets to skip (None for 0)

        Returns:
            List of DocumentSet objects ordered by creation date (newest first)

        Raises:
            DocumentSetInvalidDataException: If limit/offset are invalid
            Exception: If database operation fails

        Example:
            >>> # Get first 10 document sets
            >>> doc_sets = service.list_document_sets(limit=10, offset=0)
            >>> for ds in doc_sets:
            ...     print(f"{ds.name}: {ds.total_documents} documents")
            >>>
            >>> # Get all document sets
            >>> all_doc_sets = service.list_document_sets()
        """
        if limit is not None and limit <= 0:
            raise DocpipeException("limit must be > 0", status_code=400, error_code=ErrorCode.DOCUMENT_SET_INVALID_DATA)
        if offset is not None and offset < 0:
            raise DocpipeException(
                "offset must be >= 0", status_code=400, error_code=ErrorCode.DOCUMENT_SET_INVALID_DATA
            )

        document_sets = self._metadata_repository.list_all()

        if offset is not None:
            document_sets = document_sets[offset:]
        if limit is not None:
            document_sets = document_sets[:limit]

        logger.info("Listed %d document sets (limit=%s, offset=%s)", len(document_sets), limit, offset)
        return document_sets

    def delete_document_set(self, *, document_set_id: str, delete_data: bool = True) -> bool:
        """Delete a document set and optionally its data table.

        Deletes the document set metadata entry. If delete_data is True, also
        drops the associated data table from the database.

        Args:
            document_set_id: Unique identifier of the document set to delete
            delete_data: If True, also delete the data table (default: True)

        Returns:
            True if document set was deleted successfully

        Raises:
            DocumentSetInvalidDataException: If document_set_id is empty
            DocumentSetNotFoundException: If document set not found
            Exception: If database operation fails

        Example:
            >>> # Delete document set and its data
            >>> service.delete_document_set("abc-123", delete_data=True)
            >>>
            >>> # Delete only metadata, preserve data table
            >>> service.delete_document_set("abc-123", delete_data=False)
        """
        if not document_set_id or not document_set_id.strip():
            raise DocpipeException(
                "document_set_id cannot be empty", status_code=400, error_code=ErrorCode.DOCUMENT_SET_INVALID_DATA
            )

        # Get document set to retrieve table name
        document_set = self.get_document_set(document_set_id=document_set_id)

        # Delete data table if requested
        if delete_data and self._data_store.table_exists(table_name=document_set.table_name):
            try:
                self._data_store.delete_document_set_data(table_name=document_set.table_name)
                logger.info("Deleted data table: %s", document_set.table_name)
            except Exception as e:
                logger.error("Failed to delete data table %s: %s", document_set.table_name, e)
                raise

        # Delete metadata entry
        deleted = self._metadata_repository.delete(document_set_id=document_set_id)

        if deleted:
            logger.info("Successfully deleted document set %s", document_set_id)
            return True
        else:
            logger.error("Document set %s not found for deletion", document_set_id)
            raise DocpipeException(
                ValidationCodeMessages.DOCUMENT_SET_NOT_FOUND.format(document_set_id=document_set_id),
                status_code=404,
                error_code=ErrorCode.DOCUMENT_SET_NOT_FOUND,
            )

    def store_data(self, *, document_set_id: str, data: pa.Table) -> DocumentSet:
        """Store PyArrow table data and update metrics.

        Stores the provided PyArrow table data in the document set's data table.
        Creates the table if it doesn't exist, or upserts data if it does.
        After storing, computes and updates metrics (document count, size, pages).

        Args:
            document_set_id: Unique identifier of the document set
            data: PyArrow table containing the data to store (must have 'id' column)

        Returns:
            Updated DocumentSet with refreshed metrics

        Raises:
            DocumentSetInvalidDataException: If data validation fails
            DocumentSetNotFoundException: If document set not found
            Exception: If storage operation fails

        Example:
            >>> import pyarrow as pa
            >>> data = pa.table({
            ...     'id': ['doc1', 'doc2'],
            ...     'content': ['text1', 'text2'],
            ...     'size': [100, 200]
            ... })
            >>> updated = service.store_data("abc-123", data)
            >>> print(f"Total documents: {updated.total_documents}")
        """
        if not document_set_id or not document_set_id.strip():
            raise DocpipeException(
                "document_set_id cannot be empty", status_code=400, error_code=ErrorCode.DOCUMENT_SET_INVALID_DATA
            )

        # Validate PyArrow table
        self._validate_pyarrow_table(data)

        # Get document set
        document_set = self.get_document_set(document_set_id=document_set_id)

        try:
            # Create table if it doesn't exist
            if not self._data_store.table_exists(table_name=document_set.table_name):
                self._data_store.create_data_table(table_name=document_set.table_name, schema=data.schema)
                logger.info("Created data table: %s", document_set.table_name)

            # Upsert data
            self._data_store.upsert_document_set_data(table_name=document_set.table_name, data=data)
            logger.info("Stored %d rows in table: %s", len(data), document_set.table_name)

            # Compute and update metrics
            updated_document_set = self.compute_and_update_metrics(document_set_id=document_set_id)

            logger.info("Successfully stored data and updated metrics for document set %s", document_set_id)
            return updated_document_set

        except Exception as e:
            logger.error("Failed to store data for document set %s: %s", document_set_id, e)
            raise

    def preview_data(self, *, document_set_id: str, limit: int = 100, offset: int = 0) -> pa.Table:
        """Preview stored data with pagination.

        Retrieves a subset of the stored data for preview purposes.

        Args:
            document_set_id: Unique identifier of the document set
            limit: Maximum number of rows to return (default: 100)
            offset: Number of rows to skip (default: 0)

        Returns:
            PyArrow table containing the requested data

        Raises:
            DocumentSetInvalidDataException: If parameters are invalid
            DocumentSetNotFoundException: If document set not found
            Exception: If read operation fails

        Example:
            >>> # Preview first 10 rows
            >>> preview = service.preview_data("abc-123", limit=10, offset=0)
            >>> print(f"Preview shape: {preview.num_rows} rows, {preview.num_columns} columns")
        """
        if not document_set_id or not document_set_id.strip():
            raise DocpipeException(
                "document_set_id cannot be empty", status_code=400, error_code=ErrorCode.DOCUMENT_SET_INVALID_DATA
            )

        if limit <= 0:
            raise DocpipeException("limit must be > 0", status_code=400, error_code=ErrorCode.DOCUMENT_SET_INVALID_DATA)

        if offset < 0:
            raise DocpipeException(
                "offset must be >= 0", status_code=400, error_code=ErrorCode.DOCUMENT_SET_INVALID_DATA
            )

        # Get document set
        document_set = self.get_document_set(document_set_id=document_set_id)

        # Check if table exists
        if not self._data_store.table_exists(table_name=document_set.table_name):
            logger.warning("Data table does not exist: %s", document_set.table_name)
            # Return empty table with no schema
            return pa.table({})

        # Read data with pagination
        data = self._data_store.get_document_set_data(table_name=document_set.table_name, limit=None)

        if offset > 0:
            data = data.slice(offset)
        if limit is not None:
            data = data.slice(0, limit)

        logger.info(
            "Retrieved %d rows from document set %s (limit=%d, offset=%d)", len(data), document_set_id, limit, offset
        )
        return data

    def compute_and_update_metrics(self, *, document_set_id: str) -> DocumentSet:
        """Recompute metrics from stored data and update metadata.

        Computes metrics (total_documents, total_size_bytes, total_pages) from
        the stored data table and updates the document set metadata.

        Args:
            document_set_id: Unique identifier of the document set

        Returns:
            Updated DocumentSet with refreshed metrics

        Raises:
            DocumentSetInvalidDataException: If document_set_id is empty
            DocumentSetNotFoundException: If document set not found
            Exception: If computation or update fails

        Example:
            >>> updated = service.compute_and_update_metrics("abc-123")
            >>> print(f"Documents: {updated.total_documents}")
            >>> print(f"Size: {updated.total_size_bytes} bytes")
            >>> print(f"Pages: {updated.total_pages}")
        """
        if not document_set_id or not document_set_id.strip():
            raise DocpipeException(
                "document_set_id cannot be empty", status_code=400, error_code=ErrorCode.DOCUMENT_SET_INVALID_DATA
            )

        # Get document set
        document_set = self.get_document_set(document_set_id=document_set_id)

        # Check if table exists
        if not self._data_store.table_exists(table_name=document_set.table_name):
            logger.warning("Data table does not exist for metrics computation: %s", document_set.table_name)
            # Set metrics to zero
            metrics = {"total_documents": 0, "total_size_bytes": 0, "total_pages": 0}
        else:
            # Compute metrics from stored data
            metrics = self._compute_metrics(table_name=document_set.table_name)

        # Update document set with computed metrics
        updated_document_set = self._update_statistics(document_set=document_set, metrics=metrics)

        # Persist updated metrics
        updated_document_set = self._metadata_repository.update(document_set=updated_document_set)

        logger.info("Computed and updated metrics for document set %s: %s", document_set_id, metrics)
        return updated_document_set

    def _validate_database_path(self, database_path: str) -> str:
        """Validate and normalize database path to prevent path traversal.

        Ensures the path is safe and doesn't contain path traversal attempts.
        Resolves the path to its absolute form to prevent directory traversal attacks.

        Args:
            database_path: Path to validate

        Returns:
            Validated and normalized absolute path

        Raises:
            DocumentSetInvalidDataException: If path is invalid or contains traversal attempts

        Example:
            >>> service._validate_database_path("data/docs.db")
            '/absolute/path/to/data/docs.db'
            >>> service._validate_database_path("../../../etc/passwd")  # Raises exception
        """
        from docpipe.utils.core.validation import validate_database_path

        try:
            return validate_database_path(database_path)
        except ValueError as exc:
            logger.warning("Database path validation failed: %s", exc)
            raise DocpipeException(
                ValidationCodeMessages.DOCUMENT_SET_INVALID_DATA.format(details=str(exc)),
                status_code=400,
                error_code=ErrorCode.DOCUMENT_SET_INVALID_DATA,
            ) from exc

    def _sanitize_table_name(self, name: str) -> str:
        """Convert document set name to valid table name.

        Converts to lowercase and replaces spaces with underscores.
        Removes any characters that are not alphanumeric or underscore.

        Args:
            name: Document set name to sanitize

        Returns:
            Sanitized table name (lowercase, underscores, alphanumeric only)

        Example:
            >>> service._sanitize_table_name("My Documents 2024")
            'my_documents_2024'
            >>> service._sanitize_table_name("Test-Data (v1)")
            'test_data_v1'
        """
        # Convert to lowercase
        sanitized = name.lower()

        # Replace spaces with underscores
        sanitized = sanitized.replace(" ", "_")

        # Remove any characters that are not alphanumeric or underscore
        sanitized = re.sub(r"[^a-z0-9_]", "", sanitized)

        # Ensure it starts with a letter (prepend 'tbl_' if it doesn't)
        if not sanitized or not sanitized[0].isalpha():
            sanitized = f"tbl_{sanitized}"

        return sanitized

    def _validate_pyarrow_table(self, data: pa.Table) -> None:
        """Validate PyArrow table has required columns.

        Ensures the table has an 'id' column which is required for upsert operations.

        Args:
            data: PyArrow table to validate

        Raises:
            DocumentSetInvalidDataException: If validation fails

        Example:
            >>> import pyarrow as pa
            >>> data = pa.table({'id': [1, 2], 'value': ['a', 'b']})
            >>> service._validate_pyarrow_table(data)  # OK
            >>>
            >>> bad_data = pa.table({'value': ['a', 'b']})
            >>> service._validate_pyarrow_table(bad_data)  # Raises exception
        """
        if data is None:
            raise DocpipeException(
                "Data cannot be None", status_code=400, error_code=ErrorCode.DOCUMENT_SET_INVALID_DATA
            )

        if not isinstance(data, pa.Table):
            raise DocpipeException(
                "Data must be a PyArrow Table", status_code=400, error_code=ErrorCode.DOCUMENT_SET_INVALID_DATA
            )

        if "id" not in data.schema.names:
            raise DocpipeException(
                "Data must contain an 'id' column for upsert operations",
                status_code=400,
                error_code=ErrorCode.DOCUMENT_SET_INVALID_DATA,
            )

        if len(data) == 0:
            logger.warning("Attempting to store empty PyArrow table")

    def _compute_metrics(self, *, table_name: str) -> dict[str, int]:
        """Compute aggregate metrics for a document set.

        Delegates to data store for efficient backend-specific computation.
        This avoids loading the entire table into memory.

        Args:
            table_name: Name of the table to compute metrics for

        Returns:
            Dictionary with keys: total_documents, total_size_bytes, total_pages

        Example:
            >>> metrics = service._compute_metrics(table_name="my_docs")
            >>> print(metrics)
            {'total_documents': 100, 'total_size_bytes': 1024000, 'total_pages': 500}
        """
        return self._data_store.get_table_metrics(table_name=table_name)

    def _update_statistics(self, *, document_set: DocumentSet, metrics: dict) -> DocumentSet:
        """Update document set with computed metrics.

        Updates the document set's statistics fields with the provided metrics.

        Args:
            document_set: DocumentSet to update
            metrics: Dictionary with keys: total_documents, total_size_bytes, total_pages

        Returns:
            Updated DocumentSet (not persisted)

        Example:
            >>> metrics = {
            ...     'total_documents': 100,
            ...     'total_size_bytes': 1024000,
            ...     'total_pages': 500
            ... }
            >>> updated = service._update_statistics(document_set=doc_set, metrics=metrics)
        """
        document_set.update_statistics(
            total_documents=metrics.get("total_documents", 0),
            total_size_bytes=metrics.get("total_size_bytes", 0),
            total_pages=metrics.get("total_pages", 0),
        )
        return document_set
