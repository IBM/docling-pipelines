"""Generic flow repository using KeyValueStorage interface."""

from typing import Any

from datasift.core.assets.flows.domain.models.flow import Flow
from datasift.core.assets.flows.domain.ports.flow_repository import FlowRepository
from datasift.exceptions.datasift_exceptions import (
    FlowInvalidDataException,
    FlowNotFoundException,
    FlowStorageException,
)
from datasift.storage import KeyValueStorage
from datasift.utils.infrastructure.logging import get_logger

logger = get_logger(__name__)


class StorageFlowRepository(FlowRepository):
    """
    Generic flow repository using KeyValueStorage.

    Works with any storage backend (DuckDB, filesystem, etc.) that implements KeyValueStorage.
    Stores flows in the 'flows' collection with flow_id as key.

    Example:
        from datasift.storage import StorageFactory

        # DuckDB backend
        storage = StorageFactory.create_key_value_storage(
            storage_type="duckdb",
            database_path="data/assets.db"
        )
        repository = StorageFlowRepository(storage=storage)

        # Filesystem backend
        storage = StorageFactory.create_key_value_storage(
            storage_type="filesystem",
            base_dir="data/flows"
        )
        repository = StorageFlowRepository(storage=storage)
    """

    COLLECTION_NAME = "flows"

    def __init__(self, *, storage: KeyValueStorage):
        """
        Initialize flow repository.

        Args:
            storage: Storage implementation (must implement KeyValueStorage)
        """
        self.storage = storage
        logger.info(f"Initialized StorageFlowRepository with storage: {type(storage).__name__}")

    def save(self, flow: Flow) -> Flow:
        """Save a flow to storage."""
        if flow.flow_id is None:
            raise FlowInvalidDataException(message="Flow ID is required for saving", field_name="flow_id")

        try:
            flow_data = flow.to_dict()
            self.storage.save_record(collection=self.COLLECTION_NAME, key=flow.flow_id, data=flow_data)
            logger.info(f"Saved flow: {flow.flow_id}")
            return flow
        except FlowInvalidDataException:
            # Re-raise FlowInvalidDataException as-is
            raise
        except (PermissionError, OSError) as e:
            raise FlowStorageException(
                message=f"Storage error while saving flow {flow.flow_id}: {e}", operation="save", flow_id=flow.flow_id
            ) from e
        except Exception as e:
            raise FlowStorageException(
                message=f"Unexpected error while saving flow {flow.flow_id}: {e}",
                operation="save",
                flow_id=flow.flow_id,
            ) from e

    def find_by_id(self, flow_id: str) -> Flow | None:
        """Retrieve a flow by ID."""
        try:
            flow_data = self.storage.get_record(collection=self.COLLECTION_NAME, key=flow_id)

            if flow_data is None:
                return None

            flow = Flow.from_dict(data=flow_data)
            logger.debug(f"Retrieved flow: {flow_id}")
            return flow

        except FlowInvalidDataException:
            # Re-raise validation errors as-is
            raise
        except (PermissionError, OSError) as e:
            raise FlowStorageException(
                message=f"Storage error while retrieving flow {flow_id}: {e}", operation="find_by_id", flow_id=flow_id
            ) from e
        except Exception as e:
            raise FlowStorageException(
                message=f"Unexpected error while retrieving flow {flow_id}: {e}",
                operation="find_by_id",
                flow_id=flow_id,
            ) from e

    def find_all(self, filters: dict[str, Any] | None = None) -> list[Flow]:
        """List all flows."""
        try:
            flow_records = self.storage.list_records(collection=self.COLLECTION_NAME)

            flows = []
            for flow_data in flow_records:
                try:
                    flow = Flow.from_dict(data=flow_data)
                    flows.append(flow)
                except FlowInvalidDataException as e:
                    logger.warning(f"Skipping invalid flow record: {e}")
                    continue
                except Exception as e:
                    logger.warning(f"Skipping flow record due to unexpected error: {e}")
                    continue

            logger.debug(f"Listed {len(flows)} flows")
            return flows

        except (PermissionError, OSError) as e:
            raise FlowStorageException(
                message=f"Storage error while listing flows: {e}", operation="find_all", flow_id=None
            ) from e
        except Exception as e:
            raise FlowStorageException(
                message=f"Unexpected error while listing flows: {e}", operation="find_all", flow_id=None
            ) from e

    def delete(self, flow_id: str) -> bool:
        """Delete a flow by ID."""
        try:
            deleted = self.storage.delete_record(collection=self.COLLECTION_NAME, key=flow_id)

            if deleted:
                logger.info(f"Deleted flow: {flow_id}")
            else:
                logger.warning(f"Flow not found for deletion: {flow_id}")

            return deleted

        except (PermissionError, OSError) as e:
            raise FlowStorageException(
                message=f"Storage error while deleting flow {flow_id}: {e}", operation="delete", flow_id=flow_id
            ) from e
        except Exception as e:
            raise FlowStorageException(
                message=f"Unexpected error while deleting flow {flow_id}: {e}", operation="delete", flow_id=flow_id
            ) from e

    def exists(self, flow_id: str) -> bool:
        """Check if a flow exists."""
        try:
            return self.storage.record_exists(collection=self.COLLECTION_NAME, key=flow_id)
        except Exception as e:
            logger.warning(f"Error checking flow existence {flow_id}: {e}")
            return False

    def bulk_delete(self, flow_ids: list[str], batch_size: int = 10, max_workers: int = 4) -> dict[str, Any]:
        """Delete multiple flows by their IDs.

        Note: This implementation processes deletions sequentially.
        The batch_size and max_workers parameters are accepted for interface compatibility
        but are not used in this implementation.
        """
        if not flow_ids:
            raise FlowInvalidDataException(message="flow_ids list cannot be empty", field_name="flow_ids")

        deleted = []
        failed = []

        for flow_id in flow_ids:
            try:
                if self.delete(flow_id=flow_id):
                    deleted.append(flow_id)
                else:
                    failed.append({"flow_id": flow_id, "error": f"Flow {flow_id} not found"})
            except FlowStorageException as e:
                # Catch storage exceptions and record them
                failed.append({"flow_id": flow_id, "error": str(e)})
                logger.warning(f"Storage error deleting flow {flow_id}: {e}")
            except Exception as e:
                # Catch any other unexpected exceptions
                failed.append({"flow_id": flow_id, "error": str(e)})
                logger.warning(f"Unexpected error deleting flow {flow_id}: {e}")

        result = {
            "deleted": deleted,
            "failed": failed,
            "total_requested": len(flow_ids),
            "total_deleted": len(deleted),
            "total_failed": len(failed),
        }

        logger.info(
            f"Bulk delete completed: {result['total_deleted']} deleted, "
            f"{result['total_failed']} failed out of {result['total_requested']} requested"
        )

        return result

    def update(self, flow: Flow) -> Flow:
        """Update an existing flow."""
        if flow.flow_id is None:
            raise FlowInvalidDataException(message="Flow ID is required for updating", field_name="flow_id")

        try:
            if not self.exists(flow_id=flow.flow_id):
                raise FlowNotFoundException(message=f"Flow not found: {flow.flow_id}", flow_id=flow.flow_id)

            # Update timestamp
            flow.update_timestamp()

            # save_record handles upsert
            flow_data = flow.to_dict()
            self.storage.save_record(collection=self.COLLECTION_NAME, key=flow.flow_id, data=flow_data)
            logger.info(f"Updated flow: {flow.flow_id}")
            return flow

        except (FlowNotFoundException, FlowInvalidDataException):
            # Re-raise flow-specific exceptions as-is
            raise
        except (PermissionError, OSError) as e:
            raise FlowStorageException(
                message=f"Storage error while updating flow {flow.flow_id}: {e}",
                operation="update",
                flow_id=flow.flow_id,
            ) from e
        except Exception as e:
            raise FlowStorageException(
                message=f"Unexpected error while updating flow {flow.flow_id}: {e}",
                operation="update",
                flow_id=flow.flow_id,
            ) from e


# Made with Bob
