"""DuckDB adapter for document set metadata repository.

This module provides a DuckDB implementation of the DocumentSetMetadataRepository
interface, handling CRUD operations for document set metadata using KeyValueStorage.
"""

from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterator

from docpipe.core.assets.document_sets.domain.models.data_card import DataCard
from docpipe.core.assets.document_sets.domain.models.document_set import DocumentSet
from docpipe.core.assets.document_sets.domain.models.storage_reference import StorageReference
from docpipe.core.assets.document_sets.domain.ports.metadata_repository import DocumentSetMetadataRepository
from docpipe.core.assets.document_sets.domain.types import HealthCheckResult
from docpipe.core.assets.document_sets.factories.metadata_repository_factory import MetadataRepositoryFactory
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.exceptions.docpipe_exceptions import DocpipeException
from docpipe.exceptions.error_codes import ErrorCode
from docpipe.storage.interfaces.key_value_storage import KeyValueStorage
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger(__name__)


@MetadataRepositoryFactory.register(name=OperatorConstants.DocumentSet.ADAPTER_DUCKDB, display_name="DuckDB")
class DuckDBDocumentSetMetadataRepository(DocumentSetMetadataRepository):
    """DuckDB implementation of document set metadata repository.

    Provides metadata persistence using KeyValueStorage backend. Handles
    conversion between domain objects and dictionaries, proper serialization,
    and error handling.

    Attributes:
        storage: KeyValueStorage backend for database operations
        _transaction_active: Flag indicating if a transaction is active (not supported in KeyValueStorage)
        _database_path: Path to database for health check reporting
    """

    COLLECTION_NAME = "document_sets"

    def __init__(self, *, key_value_storage: KeyValueStorage, database_path: str) -> None:
        """Initialize the DuckDB metadata repository with injected storage.

        Args:
            key_value_storage: KeyValueStorage implementation (DuckDB-based)
            database_path: Path to DuckDB database file (for health check reporting)
        """
        self.storage = key_value_storage
        self._database_path = database_path
        self._transaction_active = False
        logger.info("DuckDBDocumentSetMetadataRepository initialized with injected KeyValueStorage")

    def create(self, *, document_set: DocumentSet) -> DocumentSet:
        """Create a new document set metadata entry.

        Args:
            document_set: The document set to create

        Returns:
            The created document set with timestamps set

        Raises:
            ValueError: If a document set with the same ID or name already exists
            RuntimeError: If the repository is not accessible or configured
        """
        # Validate the document set
        document_set.validate()

        # Ensure ID is set
        if not document_set.id:
            raise DocpipeException(
                "Document set ID cannot be None", status_code=400, error_code=ErrorCode.DOCUMENT_SET_INVALID_DATA
            )

        try:
            # Check if document set already exists
            if self.storage.record_exists(collection=self.COLLECTION_NAME, key=document_set.id):
                raise DocpipeException(
                    f"Document set with ID '{document_set.id}' already exists",
                    status_code=409,
                    error_code=ErrorCode.DOCUMENT_SET_ALREADY_EXISTS,
                )

            # Check if name already exists
            all_records = self.storage.list_records(collection=self.COLLECTION_NAME)
            for record in all_records:
                if record.get("name") == document_set.name:
                    raise DocpipeException(
                        f"Document set with name '{document_set.name}' already exists",
                        status_code=409,
                        error_code=ErrorCode.DOCUMENT_SET_ALREADY_EXISTS,
                    )

            # Convert to dict and save
            data = self._document_set_to_dict(document_set=document_set)
            self.storage.save_record(collection=self.COLLECTION_NAME, key=document_set.id, data=data)

            logger.info(f"Created document set: {document_set.id} (name: {document_set.name})")
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
            document_set_id: The unique identifier of the document set

        Returns:
            The document set with the specified ID

        Raises:
            KeyError: If no document set exists with the given ID
            RuntimeError: If the repository is not accessible
        """
        try:
            data = self.storage.get_record(collection=self.COLLECTION_NAME, key=document_set_id)

            if data is None:
                raise DocpipeException(
                    f"Document set not found: {document_set_id}",
                    status_code=404,
                    error_code=ErrorCode.DOCUMENT_SET_NOT_FOUND,
                )

            # Convert dict to DocumentSet
            document_set = self._dict_to_document_set(data=data)
            logger.debug(f"Retrieved document set: {document_set_id}")
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
            name: The name of the document set

        Returns:
            The document set with the specified name

        Raises:
            KeyError: If no document set exists with the given name
            RuntimeError: If the repository is not accessible
        """
        try:
            # List all records and find by name
            all_records = self.storage.list_records(collection=self.COLLECTION_NAME)

            for data in all_records:
                if data.get("name") == name:
                    document_set = self._dict_to_document_set(data=data)
                    logger.debug(f"Retrieved document set by name: {name}")
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
            document_set: The document set with updated fields

        Returns:
            The updated document set

        Raises:
            KeyError: If the document set does not exist
            ValueError: If the update would violate constraints (e.g., duplicate name)
            RuntimeError: If the repository is not accessible
        """
        # Validate the document set
        document_set.validate()

        # Ensure ID is set
        if not document_set.id:
            raise DocpipeException(
                "Document set ID cannot be None", status_code=400, error_code=ErrorCode.DOCUMENT_SET_INVALID_DATA
            )

        try:
            # Check if document set exists
            if not self.storage.record_exists(collection=self.COLLECTION_NAME, key=document_set.id):
                raise DocpipeException(
                    f"Document set not found: {document_set.id}",
                    status_code=404,
                    error_code=ErrorCode.DOCUMENT_SET_NOT_FOUND,
                )

            # Check if name conflicts with another document set
            all_records = self.storage.list_records(collection=self.COLLECTION_NAME)
            for record in all_records:
                if record.get("name") == document_set.name and record.get("id") != document_set.id:
                    raise DocpipeException(
                        f"Update would violate constraints: name '{document_set.name}' already exists",
                        status_code=409,
                        error_code=ErrorCode.DOCUMENT_SET_CONSTRAINT_VIOLATION,
                    )

            # Update timestamp
            document_set.update_timestamp()

            # Convert to dict and save (upsert)
            data = self._document_set_to_dict(document_set=document_set)
            self.storage.save_record(collection=self.COLLECTION_NAME, key=document_set.id, data=data)

            logger.info(f"Updated document set: {document_set.id}")
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
            document_set_id: The unique identifier of the document set to delete

        Returns:
            True if the document set was deleted, False if it did not exist

        Raises:
            RuntimeError: If the repository is not accessible
        """
        try:
            deleted = self.storage.delete_record(collection=self.COLLECTION_NAME, key=document_set_id)

            if deleted:
                logger.info(f"Deleted document set: {document_set_id}")
            else:
                logger.info(f"Document set not found for deletion: {document_set_id}")

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
            A list of all document sets, empty list if none exist

        Raises:
            RuntimeError: If the repository is not accessible
        """
        try:
            all_records = self.storage.list_records(collection=self.COLLECTION_NAME)

            # Convert dicts to DocumentSet objects
            document_sets = [self._dict_to_document_set(data=record) for record in all_records]

            # Sort by created_at descending (handle None values)
            document_sets.sort(key=lambda ds: ds.created_at or datetime.min, reverse=True)

            logger.debug(f"Retrieved {len(document_sets)} document sets")
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
            document_set_id: The unique identifier to check

        Returns:
            True if a document set with the given ID exists, False otherwise

        Raises:
            RuntimeError: If the repository is not accessible
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
            A dictionary containing health status information
        """
        try:
            # Test storage connectivity by checking if collection exists
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
            config: Configuration dictionary to validate

        Returns:
            List of validation error messages, empty if configuration is valid
        """
        errors = []

        # Validate database_path
        db_path_key = OperatorConstants.DocumentSet.DATABASE_PATH
        if db_path_key not in config:
            errors.append(f"Missing required configuration: '{db_path_key}'")
        elif not isinstance(config[db_path_key], str):
            errors.append(f"Configuration '{db_path_key}' must be a string")
        elif not config[db_path_key]:
            errors.append(f"Configuration '{db_path_key}' cannot be empty")

        return errors

    def begin_transaction(self) -> None:
        """Begin a new transaction.

        Note: Transactions are not supported in KeyValueStorage.
        This method is a no-op for compatibility.

        Raises:
            DocpipeException: If a transaction is already active
        """
        if self._transaction_active:
            raise DocpipeException(
                "Transaction already in progress", status_code=400, error_code=ErrorCode.DOCUMENT_SET_TRANSACTION_FAILED
            )
        self._transaction_active = True
        logger.debug("Transaction started (no-op in KeyValueStorage)")

    def commit_transaction(self) -> None:
        """Commit the current transaction.

        Note: Transactions are not supported in KeyValueStorage.
        This method is a no-op for compatibility.

        Raises:
            DocpipeException: If no transaction is active
        """
        if not self._transaction_active:
            raise DocpipeException(
                "No active transaction to commit", status_code=400, error_code=ErrorCode.DOCUMENT_SET_TRANSACTION_FAILED
            )
        self._transaction_active = False
        logger.debug("Transaction committed (no-op in KeyValueStorage)")

    def rollback_transaction(self) -> None:
        """Rollback the current transaction.

        Note: Transactions are not supported in KeyValueStorage.
        This method is a no-op for compatibility.

        Raises:
            DocpipeException: If no transaction is active
        """
        if not self._transaction_active:
            raise DocpipeException(
                "No active transaction to rollback",
                status_code=400,
                error_code=ErrorCode.DOCUMENT_SET_TRANSACTION_FAILED,
            )
        self._transaction_active = False
        logger.debug("Transaction rolled back (no-op in KeyValueStorage)")

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """Context manager for transaction handling.

        Note: Transactions are not supported in KeyValueStorage.
        This is a no-op for compatibility.

        Yields:
            None
        """
        self.begin_transaction()
        try:
            yield
            self.commit_transaction()
        except Exception:
            self.rollback_transaction()
            raise

    def _document_set_to_dict(self, *, document_set: DocumentSet) -> dict[str, Any]:
        """Convert a DocumentSet domain object to a dictionary.

        Args:
            document_set: DocumentSet domain object

        Returns:
            Dictionary representation suitable for storage
        """
        return {
            "id": document_set.id,
            "name": document_set.name,
            "description": document_set.description,
            "storage_backend": document_set.storage_backend,
            "database_path": document_set.database_path,
            "table_name": document_set.table_name,
            "total_documents": document_set.total_documents,
            "total_size_bytes": document_set.total_size_bytes,
            "total_pages": document_set.total_pages,
            "created_at": document_set.created_at.isoformat() if document_set.created_at else None,
            "updated_at": document_set.updated_at.isoformat() if document_set.updated_at else None,
            "metadata": document_set.metadata or {},
        }

    def _dict_to_document_set(self, *, data: dict[str, Any]) -> DocumentSet:
        """Convert a dictionary to a DocumentSet domain object.

        Args:
            data: Dictionary from storage

        Returns:
            DocumentSet domain object
        """
        # Parse timestamps
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))

        updated_at = data.get("updated_at")
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))

        # Get metadata
        metadata = data.get("metadata", {})

        # Create storage reference
        storage_reference = StorageReference(
            backend_type=data["storage_backend"], database_path=data["database_path"], table_name=data["table_name"]
        )

        # Extract data card from metadata if present
        data_card = None
        if "data_card" in metadata:
            data_card = DataCard.from_dict(metadata["data_card"])

        # Create and return DocumentSet
        return DocumentSet(
            id=data["id"],
            name=data["name"],
            description=data.get("description"),
            storage_backend=data["storage_backend"],
            database_path=data["database_path"],
            table_name=data["table_name"],
            total_documents=data.get("total_documents", 0),
            total_size_bytes=data.get("total_size_bytes", 0),
            total_pages=data.get("total_pages", 0),
            created_at=created_at,
            updated_at=updated_at,
            metadata=metadata,
            storage_reference=storage_reference,
            data_card=data_card,
        )


DuckDBMetadataRepository = DuckDBDocumentSetMetadataRepository
