"""DuckDB implementation of DocumentLibraryRepository.

Uses KeyValueStoragePort for all persistence — the same pattern as
DuckDBDocumentSetMetadataRepository. document_set_ids is stored as a JSON
array field inside each library record. No separate junction table is needed.
"""

from typing import Any

from docpipe.core.assets.document_libraries.domain.models.document_library import DocumentLibrary
from docpipe.core.assets.document_libraries.domain.ports.document_library_repository import (
    DocumentLibraryRepository,
)
from docpipe.core.assets.document_libraries.domain.types import HealthCheckResult
from docpipe.core.assets.document_libraries.factories.document_library_repository_factory import (
    DocumentLibraryRepositoryFactory,
)
from docpipe.exceptions.docpipe_exceptions import DocpipeException
from docpipe.exceptions.error_codes import ErrorCode
from docpipe.storage.interfaces.key_value_storage_port import KeyValueStoragePort
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger(__name__)


@DocumentLibraryRepositoryFactory.register(name="duckdb", display_name="DuckDB")
class DuckDBDocumentLibraryMetadataRepository(DocumentLibraryRepository):
    """DuckDB implementation of DocumentLibraryRepository using KeyValueStoragePort.

    Stores each DocumentLibrary as a single JSON record keyed by library_id.
    document_set_ids is stored as a plain list field inside the record —
    no separate junction table is required.

    This follows the same storage pattern as DuckDBDocumentSetMetadataRepository.
    """

    COLLECTION_NAME = "document_libraries"

    def __init__(self, *, key_value_storage: KeyValueStoragePort, database_path: str) -> None:
        """Initialize repository with injected KeyValueStorage.

        Args:
            key_value_storage: KeyValueStoragePort implementation (DuckDB-based)
            database_path: Path to DuckDB database file (for health check reporting)
        """
        self.storage = key_value_storage
        self._database_path = database_path
        logger.info("DuckDBDocumentLibraryMetadataRepository initialized with KeyValueStorage")

    # ── CRUD ────────────────────────────────────────────────────────────────

    def create(self, *, library: DocumentLibrary) -> DocumentLibrary:
        """Create a new document library.

        Args:
            library: DocumentLibrary entity to create

        Returns:
            The created library

        Raises:
            DocpipeException: If library with same ID or name already exists
            DocpipeException: If storage operation fails
        """
        try:
            if self.storage.record_exists(collection=self.COLLECTION_NAME, key=library.library_id):
                raise DocpipeException(
                    f"Library with ID '{library.library_id}' already exists",
                    status_code=409,
                    error_code=ErrorCode.DOCUMENT_LIBRARY_ALREADY_EXISTS,
                )

            if self.exists_by_name(name=library.name):
                raise DocpipeException(
                    f"Library with name '{library.name}' already exists",
                    status_code=409,
                    error_code=ErrorCode.DOCUMENT_LIBRARY_ALREADY_EXISTS,
                )

            self.storage.save_record(
                collection=self.COLLECTION_NAME,
                key=library.library_id,
                data=self._library_to_dict(library=library),
            )
            logger.info("Created library: %s", library.library_id)
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
        """
        try:
            data = self.storage.get_record(collection=self.COLLECTION_NAME, key=library_id)
            return self._dict_to_library(data=data) if data is not None else None
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
        """
        try:
            for record in self.storage.list_records(collection=self.COLLECTION_NAME):
                if record.get("name") == name:
                    return self._dict_to_library(data=record)
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
        """
        try:
            if not self.exists(library_id=library.library_id):
                raise DocpipeException(
                    f"Library {library.library_id} not found",
                    status_code=404,
                    error_code=ErrorCode.DOCUMENT_LIBRARY_NOT_FOUND,
                )

            self.storage.save_record(
                collection=self.COLLECTION_NAME,
                key=library.library_id,
                data=self._library_to_dict(library=library),
            )
            logger.info("Updated library: %s", library.library_id)
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
            True if deleted, False if not found
        """
        try:
            deleted = self.storage.delete_record(collection=self.COLLECTION_NAME, key=library_id)
            if deleted:
                logger.info("Deleted library: %s", library_id)
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
            limit: Maximum number to return (None for all)
            offset: Number to skip for pagination

        Returns:
            List of document libraries sorted by name
        """
        try:
            records = self.storage.list_records(collection=self.COLLECTION_NAME)
            records.sort(key=lambda r: r.get("name", ""))

            if offset is not None:
                records = records[offset:]
            if limit is not None:
                records = records[:limit]

            return [self._dict_to_library(data=r) for r in records]
        except Exception as e:
            raise DocpipeException(
                f"Failed to list libraries: {e}",
                status_code=500,
                error_code=ErrorCode.DOCUMENT_LIBRARY_STORAGE_ERROR,
            ) from e

    # ── EXISTENCE CHECKS ────────────────────────────────────────────────────

    def exists(self, *, library_id: str) -> bool:
        """Check if a document library exists by ID."""
        try:
            return self.storage.record_exists(collection=self.COLLECTION_NAME, key=library_id)
        except Exception as e:
            raise DocpipeException(
                f"Failed to check library existence: {e}",
                status_code=500,
                error_code=ErrorCode.DOCUMENT_LIBRARY_STORAGE_ERROR,
            ) from e

    def exists_by_name(self, *, name: str) -> bool:
        """Check if a document library with the given name exists."""
        try:
            return any(r.get("name") == name for r in self.storage.list_records(collection=self.COLLECTION_NAME))
        except Exception as e:
            raise DocpipeException(
                f"Failed to check library name existence: {e}",
                status_code=500,
                error_code=ErrorCode.DOCUMENT_LIBRARY_STORAGE_ERROR,
            ) from e

    # ── DOCUMENT SET RELATIONSHIP ────────────────────────────────────────────
    # document_set_ids is stored as a JSON array field inside the library record.
    # All relationship operations load the record, mutate the list, save it back.
    # No junction table, no direct SQL.

    def add_document_set_to_library(self, *, library_id: str, document_set_id: str) -> None:
        """Add a document set ID to the library's document_set_ids list.

        Loads the library record, appends the ID, and persists via update().
        """
        library = self._load_or_raise(library_id=library_id)
        library.add_document_set(document_set_id=document_set_id)
        self.update(library=library)
        logger.info("Added document set %s to library %s", document_set_id, library_id)

    def remove_document_set_from_library(self, *, library_id: str, document_set_id: str) -> None:
        """Remove a document set ID from the library's document_set_ids list.

        Loads the library record, removes the ID, and persists via update().
        """
        library = self._load_or_raise(library_id=library_id)
        library.remove_document_set(document_set_id=document_set_id)
        self.update(library=library)
        logger.info("Removed document set %s from library %s", document_set_id, library_id)

    def get_document_sets_for_library(self, *, library_id: str) -> list[str]:
        """Get all document set IDs for a library.

        Reads directly from the library record — no junction table query.
        """
        library = self._load_or_raise(library_id=library_id)
        return list(library.document_set_ids)

    def add_document_sets_bulk(self, *, library_id: str, document_set_ids: list[str]) -> None:
        """Add multiple document set IDs to a library in a single operation.

        Loads the library record once, extends the list, persists once.
        """
        if not document_set_ids:
            return
        library = self._load_or_raise(library_id=library_id)
        for doc_set_id in document_set_ids:
            library.add_document_set(document_set_id=doc_set_id)
        self.update(library=library)
        logger.info("Bulk added %d document sets to library %s", len(document_set_ids), library_id)

    def remove_document_sets_bulk(self, *, library_id: str, document_set_ids: list[str]) -> None:
        """Remove multiple document set IDs from a library in a single operation.

        Loads the library record once, removes each ID, persists once.
        """
        if not document_set_ids:
            return
        library = self._load_or_raise(library_id=library_id)
        for doc_set_id in document_set_ids:
            library.remove_document_set(document_set_id=doc_set_id)
        self.update(library=library)
        logger.info("Bulk removed %d document sets from library %s", len(document_set_ids), library_id)

    # ── COUNT / HEALTH ───────────────────────────────────────────────────────

    def count_all(self) -> int:
        """Count total number of document libraries."""
        try:
            return len(self.storage.list_records(collection=self.COLLECTION_NAME))
        except Exception as e:
            raise DocpipeException(
                f"Failed to count libraries: {e}",
                status_code=500,
                error_code=ErrorCode.DOCUMENT_LIBRARY_STORAGE_ERROR,
            ) from e

    def health_check(self) -> HealthCheckResult:
        """Check the health status of the repository."""
        try:
            collection_exists = self.storage.collection_exists(collection=self.COLLECTION_NAME)
            return HealthCheckResult(
                healthy=True,
                message="Repository is healthy",
                details={
                    "database_path": self._database_path,
                    "collection_exists": collection_exists,
                },
            )
        except Exception as e:
            return HealthCheckResult(
                healthy=False,
                message=f"Health check failed: {e}",
                details={"database_path": self._database_path, "error": str(e)},
            )

    @classmethod
    def validate_config(cls, *, config: dict[str, Any]) -> list[str]:
        """Validate repository configuration.

        Args:
            config: Configuration dictionary to validate

        Returns:
            List of validation error messages, empty if valid
        """
        errors = []
        if "database_path" not in config:
            errors.append("Missing required configuration: 'database_path'")
        elif not isinstance(config["database_path"], str):
            errors.append("Configuration 'database_path' must be a string")
        elif not config["database_path"]:
            errors.append("Configuration 'database_path' cannot be empty")
        return errors

    # ── PRIVATE HELPERS ──────────────────────────────────────────────────────

    def _load_or_raise(self, *, library_id: str) -> DocumentLibrary:
        """Load a library by ID or raise DocpipeException if not found."""
        library = self.get_by_id(library_id=library_id)
        if library is None:
            raise DocpipeException(
                f"Library {library_id} not found",
                status_code=404,
                error_code=ErrorCode.DOCUMENT_LIBRARY_NOT_FOUND,
            )
        return library

    def _library_to_dict(self, *, library: DocumentLibrary) -> dict[str, Any]:
        """Serialize a DocumentLibrary to a storage dictionary.

        document_set_ids is stored as a plain list — no junction table.
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
            "document_set_ids": library.document_set_ids or [],
        }

    def _dict_to_library(self, *, data: dict[str, Any]) -> DocumentLibrary:
        """Deserialize a storage dictionary to a DocumentLibrary.

        document_set_ids is read directly from the record.
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
            document_set_ids=data.get("document_set_ids", []),
        )
