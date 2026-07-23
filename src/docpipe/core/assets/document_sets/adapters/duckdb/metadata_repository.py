"""DuckDB adapter for document set metadata repository.

This module provides a DuckDB implementation of the DocumentSetMetadataRepository
interface, handling CRUD operations for document set metadata using KeyValueStorage.

On create(), the adapter derives table_name from the document set name via
sanitize_table_name() and persists it inside the StorageReference stored
alongside the document set record. Callers never supply table_name directly.
"""

from datetime import datetime
from typing import Any

from docpipe.core.assets.document_sets.adapters.duckdb.duckdb_utils import sanitize_table_name
from docpipe.core.assets.document_sets.domain.models.data_card import DataCard
from docpipe.core.assets.document_sets.domain.models.document_set import DocumentSet
from docpipe.core.assets.document_sets.domain.models.storage_reference import StorageReference
from docpipe.core.assets.document_sets.domain.ports.metadata_repository import DocumentSetMetadataRepository
from docpipe.core.assets.document_sets.domain.types import HealthCheckResult
from docpipe.core.assets.document_sets.factories.metadata_repository_factory import MetadataRepositoryFactory
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.exceptions.docpipe_exceptions import DocpipeException
from docpipe.exceptions.error_codes import ErrorCode
from docpipe.storage.interfaces.key_value_storage_port import KeyValueStoragePort
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger(__name__)


@MetadataRepositoryFactory.register(name=OperatorConstants.DocumentSet.ADAPTER_DUCKDB, display_name="DuckDB")
class DuckDBDocumentSetMetadataRepository(DocumentSetMetadataRepository):
    """DuckDB implementation of document set metadata repository.

    Provides metadata persistence using KeyValueStorage backend. On create(),
    derives the physical table_name from the document set name and persists it
    as part of the StorageReference — callers never supply it.

    Attributes:
        storage: KeyValueStorage backend for database operations.
        _transaction_active: Flag indicating if a transaction is active (not supported in KeyValueStorage)
        _database_path: Path to the DuckDB database file.
    """

    COLLECTION_NAME = "document_sets"

    def __init__(self, *, key_value_storage: KeyValueStoragePort, database_path: str) -> None:
        """Initialize the DuckDB metadata repository with injected storage.

        Args:
            key_value_storage: KeyValueStorage implementation (DuckDB-based).
            database_path: Path to DuckDB database file.
        """
        self.storage = key_value_storage
        self._database_path = database_path
        logger.info("DuckDBDocumentSetMetadataRepository initialized with database_path: %s", database_path)

    def create(self, *, document_set: DocumentSet) -> DocumentSet:
        """Create a new document set metadata entry.

        Derives the physical table_name from document_set.name, builds a
        StorageReference, and attaches it to the document set before persisting.

        Args:
            document_set: The document set to create.

        Returns:
            The created document set with storage_reference populated.

        Raises:
            DocpipeException: If a document set with the same ID or name already exists.
        """
        document_set.validate()

        if not document_set.asset_id:
            raise DocpipeException(
                "Document set asset_id cannot be None",
                status_code=400,
                error_code=ErrorCode.DOCUMENT_SET_INVALID_DATA,
            )

        # Derive and attach StorageReference if not already set by a prior call
        if document_set.storage_reference is None:
            document_set.storage_reference = StorageReference(
                backend_type=OperatorConstants.DocumentSet.ADAPTER_DUCKDB,
                database_path=self._database_path,
                table_name=sanitize_table_name(document_set.name),
            )

        try:
            if self.storage.record_exists(collection=self.COLLECTION_NAME, key=document_set.asset_id):
                raise DocpipeException(
                    f"Document set with ID '{document_set.asset_id}' already exists",
                    status_code=409,
                    error_code=ErrorCode.DOCUMENT_SET_ALREADY_EXISTS,
                )

            all_records = self.storage.list_records(collection=self.COLLECTION_NAME)
            for record in all_records:
                if record.get("name") == document_set.name:
                    raise DocpipeException(
                        f"Document set with name '{document_set.name}' already exists",
                        status_code=409,
                        error_code=ErrorCode.DOCUMENT_SET_ALREADY_EXISTS,
                    )

            data = self._to_dict(document_set=document_set)
            self.storage.save_record(collection=self.COLLECTION_NAME, key=document_set.asset_id, data=data)
            logger.info("Created document set: %s (name: %s)", document_set.asset_id, document_set.name)
            return document_set
        except DocpipeException:
            raise
        except Exception as e:
            raise DocpipeException(
                f"Failed to create document set: {e!s}",
                status_code=500,
                error_code=ErrorCode.DOCUMENT_SET_REPOSITORY_ERROR,
            ) from e

    def get_by_id(self, *, document_set_id: str) -> DocumentSet:
        """Retrieve a document set by its unique identifier.

        Args:
            document_set_id: The unique identifier of the document set.

        Returns:
            The document set with the specified ID.

        Raises:
            DocpipeException: If no document set exists with the given ID.
        """
        try:
            data = self.storage.get_record(collection=self.COLLECTION_NAME, key=document_set_id)
            if data is None:
                raise DocpipeException(
                    f"Document set not found: {document_set_id}",
                    status_code=404,
                    error_code=ErrorCode.DOCUMENT_SET_NOT_FOUND,
                )
            document_set = self._from_dict(data=data)
            logger.debug("Retrieved document set: %s", document_set_id)
            return document_set
        except DocpipeException:
            raise
        except Exception as e:
            raise DocpipeException(
                f"Failed to retrieve document set: {e!s}",
                status_code=500,
                error_code=ErrorCode.DOCUMENT_SET_REPOSITORY_ERROR,
            ) from e

    def get_by_name(self, *, name: str) -> DocumentSet:
        """Retrieve a document set by its name.

        Args:
            name: The name of the document set.

        Returns:
            The document set with the specified name.

        Raises:
            DocpipeException: If no document set exists with the given name.
        """
        try:
            all_records = self.storage.list_records(collection=self.COLLECTION_NAME)
            for data in all_records:
                if data.get("name") == name:
                    document_set = self._from_dict(data=data)
                    logger.debug("Retrieved document set by name: %s", name)
                    return document_set
            raise DocpipeException(
                f"Document set not found by name: {name}",
                status_code=404,
                error_code=ErrorCode.DOCUMENT_SET_NOT_FOUND,
            )
        except DocpipeException:
            raise
        except Exception as e:
            raise DocpipeException(
                f"Failed to retrieve document set by name: {e!s}",
                status_code=500,
                error_code=ErrorCode.DOCUMENT_SET_REPOSITORY_ERROR,
            ) from e

    def update(self, *, document_set: DocumentSet) -> DocumentSet:
        """Update an existing document set metadata entry.

        Args:
            document_set: The document set with updated fields.

        Returns:
            The updated document set.

        Raises:
            DocpipeException: If the document set does not exist or the update
                would violate a name uniqueness constraint.
        """
        document_set.validate()

        if not document_set.asset_id:
            raise DocpipeException(
                "Document set asset_id cannot be None",
                status_code=400,
                error_code=ErrorCode.DOCUMENT_SET_INVALID_DATA,
            )

        try:
            if not self.storage.record_exists(collection=self.COLLECTION_NAME, key=document_set.asset_id):
                raise DocpipeException(
                    f"Document set not found: {document_set.asset_id}",
                    status_code=404,
                    error_code=ErrorCode.DOCUMENT_SET_NOT_FOUND,
                )

            all_records = self.storage.list_records(collection=self.COLLECTION_NAME)
            for record in all_records:
                if record.get("name") == document_set.name and record.get("asset_id") != document_set.asset_id:
                    raise DocpipeException(
                        f"Update would violate constraints: name '{document_set.name}' already exists",
                        status_code=409,
                        error_code=ErrorCode.DOCUMENT_SET_CONSTRAINT_VIOLATION,
                    )

            document_set.update_timestamp()
            data = self._to_dict(document_set=document_set)
            self.storage.save_record(collection=self.COLLECTION_NAME, key=document_set.asset_id, data=data)
            logger.info("Updated document set: %s", document_set.asset_id)
            return document_set
        except DocpipeException:
            raise
        except Exception as e:
            raise DocpipeException(
                f"Failed to update document set: {e!s}",
                status_code=500,
                error_code=ErrorCode.DOCUMENT_SET_REPOSITORY_ERROR,
            ) from e

    def delete(self, *, document_set_id: str) -> bool:
        """Delete a document set metadata entry.

        Args:
            document_set_id: The unique identifier of the document set to delete.

        Returns:
            True if the document set was deleted, False if it did not exist.

        Raises:
            DocpipeException: If the deletion fails.
        """
        try:
            deleted = self.storage.delete_record(collection=self.COLLECTION_NAME, key=document_set_id)
            if deleted:
                logger.info("Deleted document set: %s", document_set_id)
            else:
                logger.info("Document set not found for deletion: %s", document_set_id)
            return deleted
        except DocpipeException:
            raise
        except Exception as e:
            raise DocpipeException(
                f"Failed to delete document set: {e!s}",
                status_code=500,
                error_code=ErrorCode.DOCUMENT_SET_REPOSITORY_ERROR,
            ) from e

    def list_all(self) -> list[DocumentSet]:
        """List all document sets in the repository.

        Returns:
            A list of all document sets ordered by creation date (newest first).

        Raises:
            DocpipeException: If the listing fails.
        """
        try:
            all_records = self.storage.list_records(collection=self.COLLECTION_NAME)
            document_sets = [self._from_dict(data=record) for record in all_records]
            document_sets.sort(key=lambda ds: ds.created_at or datetime.min, reverse=True)
            logger.debug("Retrieved %d document sets", len(document_sets))
            return document_sets
        except DocpipeException:
            raise
        except Exception as e:
            raise DocpipeException(
                f"Failed to list document sets: {e!s}",
                status_code=500,
                error_code=ErrorCode.DOCUMENT_SET_REPOSITORY_ERROR,
            ) from e

    def exists(self, *, document_set_id: str) -> bool:
        """Check if a document set exists.

        Args:
            document_set_id: The unique identifier to check.

        Returns:
            True if a document set with the given ID exists, False otherwise.

        Raises:
            DocpipeException: If the check fails.
        """
        try:
            return self.storage.record_exists(collection=self.COLLECTION_NAME, key=document_set_id)
        except DocpipeException:
            raise
        except Exception as e:
            raise DocpipeException(
                f"Failed to check document set existence: {e!s}",
                status_code=500,
                error_code=ErrorCode.DOCUMENT_SET_REPOSITORY_ERROR,
            ) from e

    def health_check(self) -> HealthCheckResult:
        """Check the health status of the repository.

        Returns:
            HealthCheckResult indicating whether the repository is reachable.
        """
        try:
            exists = self.storage.collection_exists(collection=self.COLLECTION_NAME)
            return HealthCheckResult(
                healthy=True,
                message="Repository is healthy",
                details={OperatorConstants.DocumentSet.DATABASE_PATH: self._database_path, "collection_exists": exists},
            )
        except Exception as e:
            return HealthCheckResult(
                healthy=False,
                message=f"Health check failed: {e}",
                details={
                    OperatorConstants.DocumentSet.DATABASE_PATH: self._database_path,
                    OperatorConstants.DocumentSet.META_ERROR: str(e),
                },
            )

    @classmethod
    def validate_config(cls, *, config: dict[str, Any]) -> list[str]:
        """Validate repository configuration.

        Args:
            config: Must contain a non-empty ``database_path`` string.

        Returns:
            List of validation error messages; empty if configuration is valid.
        """
        errors = []
        db_path_key = OperatorConstants.DocumentSet.DATABASE_PATH
        if db_path_key not in config:
            errors.append(f"Missing required configuration: '{db_path_key}'")
        elif not isinstance(config[db_path_key], str):
            errors.append(f"Configuration '{db_path_key}' must be a string")
        elif not config[db_path_key]:
            errors.append(f"Configuration '{db_path_key}' cannot be empty")
        return errors

    # ------------------------------------------------------------------
    # Internal serialisation helpers
    # ------------------------------------------------------------------

    def _to_dict(self, *, document_set: DocumentSet) -> dict[str, Any]:
        """Serialise a DocumentSet to a storable dictionary."""
        return {
            "asset_id": document_set.asset_id,
            "name": document_set.name,
            "description": document_set.description,
            "storage_backend": document_set.storage_backend,
            "total_documents": document_set.total_documents,
            "total_size_bytes": document_set.total_size_bytes,
            "total_pages": document_set.total_pages,
            "created_at": document_set.created_at.isoformat() if document_set.created_at else None,
            "updated_at": document_set.updated_at.isoformat() if document_set.updated_at else None,
            "metadata": document_set.metadata or {},
            "storage_reference": document_set.storage_reference.to_dict() if document_set.storage_reference else None,
        }

    def _from_dict(self, *, data: dict[str, Any]) -> DocumentSet:
        """Deserialise a dictionary from storage into a DocumentSet."""
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))

        updated_at = data.get("updated_at")
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))

        storage_reference = None
        if data.get("storage_reference"):
            storage_reference = StorageReference.from_dict(data["storage_reference"])

        data_card = None
        if data.get("data_card"):
            data_card = DataCard.from_dict(data["data_card"])

        return DocumentSet(
            asset_id=data.get("asset_id"),
            name=data["name"],
            description=data.get("description"),
            storage_backend=data.get("storage_backend", "duckdb"),
            total_documents=data.get("total_documents", 0),
            total_size_bytes=data.get("total_size_bytes", 0),
            total_pages=data.get("total_pages", 0),
            created_at=created_at,
            updated_at=updated_at,
            metadata=data.get("metadata", {}),
            storage_reference=storage_reference,
            data_card=data_card,
        )
