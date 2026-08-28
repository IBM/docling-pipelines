"""DuckDB adapter for AttachmentRepository.

Persists AttachmentRef records as JSON in the DuckDB KV store under the
collection ``"document_set_attachments"``.
"""

from typing import Any

from docpipe.core.assets.common.domain.models.attachment_ref import AttachmentRef
from docpipe.core.assets.common.domain.ports.attachment_repository import AttachmentRepository
from docpipe.core.assets.common.factories.attachment_repository_factory import AttachmentRepositoryFactory
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.exceptions.docpipe_exceptions import DocpipeException
from docpipe.exceptions.error_codes import ErrorCode
from docpipe.storage import StorageFactory
from docpipe.storage.interfaces.key_value_storage_port import KeyValueStoragePort
from docpipe.utils.infrastructure.logging import get_logger

logger = get_logger(__name__)


@AttachmentRepositoryFactory.register(name=OperatorConstants.DocumentSet.ADAPTER_DUCKDB, display_name="DuckDB")
class DuckDBAttachmentRepository(AttachmentRepository):
    """DuckDB implementation of the AttachmentRepository port.

    Stores each AttachmentRef as a single KV record keyed by asset_id under
    the ``document_set_attachments`` collection.

    Attributes:
        COLLECTION_NAME: KV collection name; must differ from ``"document_sets"``
            to avoid key collisions.
        _storage: KeyValueStoragePort backend for DuckDB operations.
        _database_path: Path to the DuckDB file.
    """

    COLLECTION_NAME = "document_set_attachments"

    def __init__(self, *, key_value_storage: KeyValueStoragePort, database_path: str) -> None:
        """Initialise with injected storage.

        Args:
            key_value_storage: KeyValueStoragePort implementation.
            database_path: Path to the DuckDB database file.
        """
        self._storage = key_value_storage
        self._database_path = database_path
        logger.info("DuckDBAttachmentRepository initialised with database_path: %s", database_path)

    @classmethod
    def create(cls, *, config: dict[str, Any]) -> "DuckDBAttachmentRepository":
        """Instantiate with DuckDB KV storage wired from config.

        Args:
            config: Must contain a non-empty ``database_path`` string.

        Returns:
            Fully initialised ``DuckDBAttachmentRepository``.

        Raises:
            DocpipeException: If storage creation fails.
        """
        try:
            database_path = config["database_path"]
            key_value_storage = StorageFactory.create_key_value_storage(
                storage_type=OperatorConstants.DocumentSet.ADAPTER_DUCKDB,
                database_path=database_path,
            )
            return cls(key_value_storage=key_value_storage, database_path=database_path)
        except DocpipeException:
            raise
        except Exception as e:
            raise DocpipeException(
                f"Failed to initialise DuckDBAttachmentRepository: {e!s}",
                status_code=500,
                error_code=ErrorCode.DOCUMENT_SET_REPOSITORY_ERROR,
            ) from e

    def save(self, *, asset_id: str, data: AttachmentRef) -> None:
        """Persist an AttachmentRef for the given asset.

        Args:
            asset_id: Unique identifier of the owning asset.
            data: AttachmentRef to persist.

        Raises:
            DocpipeException: If the write fails.
        """
        try:
            self._storage.save_record(
                collection=self.COLLECTION_NAME,
                key=asset_id,
                data=data.to_dict(),
            )
            logger.debug("Saved attachment ref for asset: %s", asset_id)
        except DocpipeException:
            raise
        except Exception as e:
            raise DocpipeException(
                f"Failed to save attachment ref for asset '{asset_id}': {e!s}",
                status_code=500,
                error_code=ErrorCode.DOCUMENT_SET_REPOSITORY_ERROR,
            ) from e

    def get(self, *, asset_id: str) -> AttachmentRef | None:
        """Retrieve the AttachmentRef for the given asset.

        Args:
            asset_id: Unique identifier of the owning asset.

        Returns:
            The persisted AttachmentRef, or None if no record exists.

        Raises:
            DocpipeException: If the read fails.
        """
        try:
            raw = self._storage.get_record(collection=self.COLLECTION_NAME, key=asset_id)
            if raw is None:
                return None
            return AttachmentRef.from_dict(raw)
        except DocpipeException:
            raise
        except Exception as e:
            raise DocpipeException(
                f"Failed to get attachment ref for asset '{asset_id}': {e!s}",
                status_code=500,
                error_code=ErrorCode.DOCUMENT_SET_REPOSITORY_ERROR,
            ) from e

    def delete(self, *, asset_id: str) -> bool:
        """Delete the AttachmentRef record for the given asset.

        Args:
            asset_id: Unique identifier of the owning asset.

        Returns:
            True if the record existed and was deleted, False if it was absent.

        Raises:
            DocpipeException: If the deletion fails.
        """
        try:
            deleted = self._storage.delete_record(collection=self.COLLECTION_NAME, key=asset_id)
            if deleted:
                logger.debug("Deleted attachment ref for asset: %s", asset_id)
            return deleted
        except DocpipeException:
            raise
        except Exception as e:
            raise DocpipeException(
                f"Failed to delete attachment ref for asset '{asset_id}': {e!s}",
                status_code=500,
                error_code=ErrorCode.DOCUMENT_SET_REPOSITORY_ERROR,
            ) from e

    def exists(self, *, asset_id: str) -> bool:
        """Check whether an AttachmentRef record exists for the given asset.

        Args:
            asset_id: Unique identifier of the owning asset.

        Returns:
            True if a record exists, False otherwise.

        Raises:
            DocpipeException: If the check fails.
        """
        try:
            return self._storage.record_exists(collection=self.COLLECTION_NAME, key=asset_id)
        except DocpipeException:
            raise
        except Exception as e:
            raise DocpipeException(
                f"Failed to check attachment ref existence for asset '{asset_id}': {e!s}",
                status_code=500,
                error_code=ErrorCode.DOCUMENT_SET_REPOSITORY_ERROR,
            ) from e

    @classmethod
    def validate_config(cls, *, config: dict[str, Any]) -> list[str]:
        """Validate DuckDB attachment repository configuration.

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
