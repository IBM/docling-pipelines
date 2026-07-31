"""Application service for document set management operations.

Provides business logic orchestration for document sets, coordinating between
the metadata repository and storage layers.

Extends AssetService[DocumentSet] to inherit common operations (get_by_id,
get_by_name, delete, exists, exists_by_name, list_all, count_all, health_check).
"""

import pyarrow as pa

from docpipe.core.assets.common.application.services.asset_service import AssetService
from docpipe.core.assets.common.domain.ports.asset_repository import AssetRepository
from docpipe.core.assets.document_sets.domain.models.document_set import DocumentSet
from docpipe.core.assets.document_sets.domain.ports import DocumentSetStorage
from docpipe.exceptions.docpipe_exceptions import DocpipeException
from docpipe.exceptions.error_codes import ErrorCode
from docpipe.exceptions.error_messages import ValidationCodeMessages
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger(__name__)


class DocumentSetService(AssetService[DocumentSet]):
    """Application service for document set business logic orchestration.

    Extends AssetService[DocumentSet] for unified architecture participation.
    Inherits: get_by_id, get_by_name, delete, exists, exists_by_name,
    list_all, count_all, health_check.

    Adds DocumentSet-specific operations for data management:
    create_document_set, update_document_set, store_data, preview_data,
    compute_and_update_metrics, delete_document_set (with data deletion).

    Attributes:
        _repository: Metadata repository port (AssetRepository[DocumentSet]).
        _storage: Storage port for PyArrow table data operations.
    """

    def __init__(
        self,
        *,
        metadata_repository: AssetRepository[DocumentSet],
        data_store: DocumentSetStorage,
    ) -> None:
        """Initialize the service with port dependencies.

        Args:
            metadata_repository: Repository port for document set metadata CRUD.
            data_store: Storage port for document data operations.
        """
        super().__init__(repository=metadata_repository)
        self._storage = data_store
        logger.debug(
            "DocumentSetService initialized with metadata_repository: %s, data_store: %s",
            type(metadata_repository).__name__,
            type(data_store).__name__,
        )

    def create_document_set(self, *, name: str, description: str | None, metadata: dict | None = None) -> DocumentSet:
        """Create or retrieve a document set (get-or-create pattern).

        Implements idempotent document set creation: if a document set with the
        given name already exists it is returned; otherwise a new one is created.
        The adapter derives the physical table name and database path internally.

        Args:
            name: Unique name for the document set.
            description: Optional description.
            metadata: Optional additional metadata as key-value pairs.

        Returns:
            DocumentSet (existing or newly created) with asset_id and timestamps.

        Raises:
            DocpipeException: If validation fails or a database operation fails.
        """
        existing = self._repository.find_by_name(name=name)
        if existing:
            logger.info(
                "Document set with name '%s' already exists (ID: %s), returning existing",
                name,
                existing.asset_id,
            )
            return existing

        from uuid import uuid4

        document_set = DocumentSet(
            asset_id=str(uuid4()),
            name=name,
            description=description,
            metadata=metadata or {},
        )
        document_set.validate()

        logger.info("Creating document set with name: %s", name)

        try:
            created = self._repository.save(asset=document_set)
            logger.info("Successfully created document set %s with name %s", created.asset_id, created.name)
            return created
        except DocpipeException as e:
            if e.status_code == 409:
                # Race condition: created by another process between check and save
                existing = self._repository.find_by_name(name=name)
                if existing:
                    return existing
            raise
        except Exception as e:
            raise DocpipeException(
                ValidationCodeMessages.DOCUMENT_SET_STORAGE_ERROR.format(details=str(e)),
                status_code=500,
                error_code=ErrorCode.DOCUMENT_SET_STORAGE_ERROR,
            ) from e

    def update_document_set(
        self, *, document_set_id: str, description: str | None = None, metadata: dict | None = None
    ) -> DocumentSet:
        """Update document set metadata.

        Args:
            document_set_id: Unique identifier of the document set to update.
            description: New description (None to keep existing).
            metadata: New metadata dict (None to keep existing).

        Returns:
            Updated DocumentSet with refreshed timestamp.

        Raises:
            DocpipeException: If the document set is not found or validation fails.
        """
        if not document_set_id or not document_set_id.strip():
            raise DocpipeException(
                "document_set_id cannot be empty", status_code=400, error_code=ErrorCode.DOCUMENT_SET_INVALID_DATA
            )

        existing = self._repository.find_by_id(asset_id=document_set_id)
        if existing is None:
            raise DocpipeException(
                ValidationCodeMessages.DOCUMENT_SET_NOT_FOUND.format(document_set_id=document_set_id),
                status_code=404,
                error_code=ErrorCode.DOCUMENT_SET_NOT_FOUND,
            )

        if description is not None:
            existing.description = description
        if metadata is not None:
            existing.metadata = metadata

        existing.validate()
        updated = self._repository.update(asset=existing)
        logger.info("Successfully updated document set %s", document_set_id)
        return updated

    def get_document_set(self, *, document_set_id: str) -> DocumentSet:
        """Retrieve a document set by ID.

        Args:
            document_set_id: Unique identifier of the document set.

        Returns:
            DocumentSet with all metadata.

        Raises:
            DocpipeException: If the document set is not found.
        """
        if not document_set_id or not document_set_id.strip():
            raise DocpipeException(
                "document_set_id cannot be empty", status_code=400, error_code=ErrorCode.DOCUMENT_SET_INVALID_DATA
            )

        document_set = self._repository.find_by_id(asset_id=document_set_id)
        if document_set is None:
            raise DocpipeException(
                ValidationCodeMessages.DOCUMENT_SET_NOT_FOUND.format(document_set_id=document_set_id),
                status_code=404,
                error_code=ErrorCode.DOCUMENT_SET_NOT_FOUND,
            )

        logger.info("Successfully retrieved document set %s", document_set_id)
        return document_set

    def list_document_sets(self, *, limit: int | None = None, offset: int | None = None) -> list[DocumentSet]:
        """List document sets with optional pagination.

        Args:
            limit: Maximum number of document sets to return (None for all).
            offset: Number of document sets to skip (None for 0).

        Returns:
            List of DocumentSet objects ordered by creation date (newest first).

        Raises:
            DocpipeException: If limit/offset are invalid.
        """
        if limit is not None and limit <= 0:
            raise DocpipeException("limit must be > 0", status_code=400, error_code=ErrorCode.DOCUMENT_SET_INVALID_DATA)
        if offset is not None and offset < 0:
            raise DocpipeException(
                "offset must be >= 0", status_code=400, error_code=ErrorCode.DOCUMENT_SET_INVALID_DATA
            )

        document_sets = self._repository.list_all(limit=limit, offset=offset)

        logger.info("Listed %d document sets (limit=%s, offset=%s)", len(document_sets), limit, offset)
        return document_sets

    def delete_document_set(self, *, document_set_id: str, delete_data: bool = True) -> bool:
        """Delete a document set and optionally its stored data.

        Args:
            document_set_id: Unique identifier of the document set to delete.
            delete_data: If True, also delete the backing data table (default: True).

        Returns:
            True if deleted successfully.

        Raises:
            DocpipeException: If the document set is not found.
        """
        if not document_set_id or not document_set_id.strip():
            raise DocpipeException(
                "document_set_id cannot be empty", status_code=400, error_code=ErrorCode.DOCUMENT_SET_INVALID_DATA
            )

        document_set = self.get_document_set(document_set_id=document_set_id)

        if (
            delete_data
            and document_set.storage_reference
            and self._storage.exists(storage_ref=document_set.storage_reference)
        ):
            try:
                self._storage.delete(storage_ref=document_set.storage_reference)
                logger.info("Deleted data for document set %s", document_set_id)
            except Exception as e:
                logger.error("Failed to delete data for document set %s: %s", document_set_id, e)
                raise

        deleted = self._repository.delete(asset_id=document_set_id)
        if deleted:
            logger.info("Successfully deleted document set %s", document_set_id)
            return True
        logger.error("Document set %s not found for deletion", document_set_id)
        raise DocpipeException(
            ValidationCodeMessages.DOCUMENT_SET_NOT_FOUND.format(document_set_id=document_set_id),
            status_code=404,
            error_code=ErrorCode.DOCUMENT_SET_NOT_FOUND,
        )

    def store_data(self, *, document_set_id: str, data: pa.Table) -> DocumentSet:
        """Store PyArrow table data and update metrics.

        Args:
            document_set_id: Unique identifier of the document set.
            data: PyArrow table to store. Must contain an ``id`` column.

        Returns:
            Updated DocumentSet with refreshed metrics.

        Raises:
            DocpipeException: If validation fails, the document set is not found,
                or the storage operation fails.
        """
        if not document_set_id or not document_set_id.strip():
            raise DocpipeException(
                "document_set_id cannot be empty", status_code=400, error_code=ErrorCode.DOCUMENT_SET_INVALID_DATA
            )

        self._validate_pyarrow_table(data)

        document_set = self.get_document_set(document_set_id=document_set_id)

        try:
            storage_ref = self._storage.store(doc_set_name=document_set.name, data=data)
            logger.info("Stored %d rows for document set %s", len(data), document_set_id)

            document_set.storage_reference = storage_ref
            self._repository.update(asset=document_set)

            updated = self.compute_and_update_metrics(document_set_id=document_set_id)
            logger.info("Successfully stored data and updated metrics for document set %s", document_set_id)
            return updated
        except Exception as e:
            logger.error("Failed to store data for document set %s: %s", document_set_id, e)
            raise

    def preview_data(self, *, document_set_id: str, limit: int = 100, offset: int = 0) -> pa.Table:
        """Preview stored data with pagination.

        Args:
            document_set_id: Unique identifier of the document set.
            limit: Maximum number of rows to return (default: 100).
            offset: Number of rows to skip (default: 0).

        Returns:
            PyArrow table containing the requested rows.

        Raises:
            DocpipeException: If parameters are invalid or the document set is not found.
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

        document_set = self.get_document_set(document_set_id=document_set_id)

        if not document_set.storage_reference or not self._storage.exists(storage_ref=document_set.storage_reference):
            logger.warning("Data does not exist for document set: %s", document_set_id)
            return pa.table({})

        data = self._storage.load(storage_ref=document_set.storage_reference, limit=None)

        if offset > 0:
            data = data.slice(offset)
        if limit is not None:
            data = data.slice(0, limit)

        logger.info(
            "Retrieved %d rows from document set %s (limit=%d, offset=%d)",
            len(data),
            document_set_id,
            limit,
            offset,
        )
        return data

    def compute_and_update_metrics(self, *, document_set_id: str) -> DocumentSet:
        """Recompute metrics from stored data and update metadata.

        Args:
            document_set_id: Unique identifier of the document set.

        Returns:
            Updated DocumentSet with refreshed metrics.

        Raises:
            DocpipeException: If the document set is not found.
        """
        if not document_set_id or not document_set_id.strip():
            raise DocpipeException(
                "document_set_id cannot be empty", status_code=400, error_code=ErrorCode.DOCUMENT_SET_INVALID_DATA
            )

        document_set = self.get_document_set(document_set_id=document_set_id)

        if not document_set.storage_reference or not self._storage.exists(storage_ref=document_set.storage_reference):
            logger.warning("Data does not exist for metrics computation: %s", document_set_id)
            metrics: dict[str, int] = {"total_documents": 0, "total_size_bytes": 0, "total_pages": 0}
        else:
            metrics = self._storage.get_metrics(storage_ref=document_set.storage_reference)

        document_set.update_statistics(
            total_documents=metrics.get("total_documents", 0),
            total_size_bytes=metrics.get("total_size_bytes", 0),
            total_pages=metrics.get("total_pages", 0),
        )
        updated = self._repository.update(asset=document_set)
        logger.info("Computed and updated metrics for document set %s: %s", document_set_id, metrics)
        return updated

    def _validate_pyarrow_table(self, data: pa.Table) -> None:
        """Validate that data is a non-None PyArrow Table with an id column."""
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
