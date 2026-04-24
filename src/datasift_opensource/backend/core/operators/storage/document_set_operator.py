"""Document Set Operator for storing PyArrow table data with metadata tracking.

This operator stores PyArrow table data in a document set using DuckDB storage,
with automatic metrics computation and support for incremental updates with
soft-delete cleanup.
"""

from typing import Any

import pyarrow as pa

from common.constants.constants import DatasiftConstants, ExecutionStatus, Metrics
from common.constants.operator_constants import OperatorConstants
from common.exceptions.datasift_exceptions import (
    DatasiftException,
    FlowExecutionFailedException,
    FlowValidationException,
)
from common.util.data.incremental_update import IncrementalUpdateUtil
from common.util.infrastructure.logging import get_logger
from core.assets_management.document_sets.adapters.repositories.document_set_repository import (
    DocumentSetRepository,
)
from core.assets_management.document_sets.application.services.document_set_service import (
    DocumentSetService,
)
from core.operators.abstract_operator import AbstractOperator, OperatorCategory
from storage.duckdb_storage import DuckDBStorage

logger = get_logger()


class DocumentSetOperator(AbstractOperator):
    """Operator for storing PyArrow table data in document sets.

    This operator provides persistent storage for pipeline data using the document set
    infrastructure. It handles:
    - Creating or updating document sets
    - Storing PyArrow table data with schema evolution
    - Computing and tracking metrics (document count, size, pages)
    - Handling incremental updates with soft-delete cleanup
    - Pass-through of original data for downstream operators

    The operator uses dependency injection for services and follows the enterprise
    pattern with proper separation of concerns between storage, repository, and
    service layers.

    Attributes:
        short_name: Operator identifier for logging and metadata
        category: Operator category (Storage)
    """

    short_name: str = "document_set"
    category: OperatorCategory = OperatorCategory.Storage

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize the Document Set operator.

        Args:
            config: Configuration dictionary containing:
                - document_set_name (required): Name of the document set
                - description (optional): Description of the document set
                - metadata (optional): Additional metadata as JSON
                - retain_deleted_docs (optional): Whether to retain soft-deleted documents
                - document_set_id (optional): Existing document set ID for updates

        Note:
            database_path is no longer configurable - always uses the default path
            from DatasiftConstants.DOCUMENT_SET_DEFAULT_DB_PATH
        """
        super().__init__(config)

        try:
            # Extract configuration parameters
            document_set_name = config.get("document_set_name")
            if not document_set_name:
                raise FlowValidationException("document_set_name is required in operator configuration")

            self.document_set_name: str = document_set_name
            self.description: str | None = config.get("description")
            self.metadata_config: dict | None = config.get("metadata")
            self.retain_deleted_docs: bool = config.get("retain_deleted_docs", False)
            self.document_set_id: str | None = config.get("document_set_id")

            # Use provided database path or default
            db_path = config.get("database_path") or DatasiftConstants.DOCUMENT_SET_DEFAULT_DB_PATH
            self.database_path: str = self._validate_database_path(db_path)

            # Validate database path and log warnings
            DuckDBStorage.validate_database_path(self.database_path)

            # Initialize services (dependency injection)
            self.storage: DuckDBStorage = DuckDBStorage(self.database_path)
            self.repository: DocumentSetRepository = DocumentSetRepository(self.storage)
            self.service: DocumentSetService = DocumentSetService(self.repository, self.storage)

            # Initialize incremental update utility for soft-delete handling
            self.incremental_util: IncrementalUpdateUtil | None = None
            if not self.retain_deleted_docs:
                try:
                    self.incremental_util = IncrementalUpdateUtil()
                except Exception as e:
                    logger.warning(
                        f"Failed to initialize IncrementalUpdateUtil: {e}. Soft-delete cleanup will be skipped.",
                        extra=self.common_log_arguments,
                    )

            logger.info(
                f"Initialized DocumentSetOperator for document set: {self.document_set_name}",
                extra=self.common_log_arguments,
            )
        except FlowValidationException:
            raise
        except DatasiftException as e:
            raise FlowValidationException(f"Invalid operator configuration: {e}") from e
        except Exception as e:
            raise FlowValidationException(f"Failed to initialize DocumentSetOperator: {e}") from e

    def get_metadata(self) -> dict[str, Any]:
        """Return operator metadata for flow validation and documentation.

        Returns:
            Dictionary containing operator metadata including parameters schema
        """
        return {
            "name": "DocumentSetOperator",
            "category": self.category.value,
            "description": "Stores PyArrow table data in a document set with metadata tracking",
            "parameters": {
                "document_set_name": {"type": "string", "required": True, "description": "Name of the document set"},
                "description": {"type": "string", "required": False, "description": "Description of the document set"},
                "metadata": {"type": "object", "required": False, "description": "Additional metadata as JSON"},
                "retain_deleted_docs": {
                    "type": "boolean",
                    "required": False,
                    "default": False,
                    "description": "Whether to retain soft-deleted documents",
                },
                "document_set_id": {
                    "type": "string",
                    "required": False,
                    "description": "Existing document set ID for updates",
                },
            },
        }

    def get_required_features(self) -> list[str]:
        """Return list of required columns in the input table.

        Returns:
            List containing required column names
        """
        return [OperatorConstants.Columns.ID]

    def transform(self, table: pa.Table, file_name: str | None = None) -> tuple[list[pa.Table], dict[str, Any]]:
        """Transform the input table by storing it in a document set.

        This method:
        1. Validates the input table has required columns
        2. Creates or retrieves the document set
        3. Stores the data with automatic schema evolution
        4. Handles soft-delete cleanup if enabled
        5. Computes and updates metrics
        6. Returns the original table unchanged (pass-through)

        Args:
            table: PyArrow table containing the data to store
            file_name: Optional file name (unused, for interface compatibility)

        Returns:
            Tuple of:
                - List containing the original table (pass-through)
                - Metadata dictionary with storage info and metrics
        """
        # Initialize metadata
        metadata: dict[str, Any] = self.create_base_metadata(
            total_docs_count=table.num_rows, node_status=ExecutionStatus.COMPLETED.value
        )

        # Add storage-specific metadata
        metadata["document_set_name"] = self.document_set_name
        metadata["database_path"] = self.database_path

        # Handle empty table
        if table.num_rows == 0:
            logger.warning("Empty table provided to DocumentSetOperator", extra=self.common_log_arguments)
            metadata["stored_documents"] = 0
            return [table], metadata

        # Validate required columns
        if OperatorConstants.Columns.ID not in table.column_names:
            error_msg = f"Required column '{OperatorConstants.Columns.ID}' not found in table"
            metadata[Metrics.External.NODE_STATUS] = ExecutionStatus.FAILED.value
            metadata["error"] = error_msg
            return [table], metadata

        try:
            # Step 1: Create or retrieve document set
            doc_set_id = self._get_or_create_document_set()
            metadata["document_set_id"] = doc_set_id

            logger.info(
                f"Using document set: {self.document_set_name} (ID: {doc_set_id})", extra=self.common_log_arguments
            )

            # Step 2: Store data (creates table, upserts data, computes metrics)
            logger.info(f"Storing {table.num_rows} rows in document set", extra=self.common_log_arguments)

            updated_doc_set = self.service.store_data(doc_set_id, table)

            # Step 3: Handle soft-delete cleanup if enabled
            if not self.retain_deleted_docs and self.incremental_util:
                deleted_count = self._handle_soft_deletes(doc_set_id, updated_doc_set.table_name)
                metadata["deleted_documents"] = deleted_count
            else:
                metadata["deleted_documents"] = 0

            # Step 4: Update metadata with computed metrics
            metadata["stored_documents"] = updated_doc_set.total_documents
            metadata["total_size_bytes"] = updated_doc_set.total_size_bytes
            metadata["total_pages"] = updated_doc_set.total_pages
            metadata["table_name"] = updated_doc_set.table_name
            metadata[Metrics.External.PROCESSED_DOCS] = table.num_rows

            logger.info(
                f"Successfully stored data in document set. "
                f"Total documents: {updated_doc_set.total_documents}, "
                f"Size: {updated_doc_set.total_size_bytes} bytes, "
                f"Pages: {updated_doc_set.total_pages}",
                extra=self.common_log_arguments,
            )

        except DatasiftException as e:
            metadata[Metrics.External.NODE_STATUS] = ExecutionStatus.FAILED.value
            metadata["error"] = str(e)
            raise FlowExecutionFailedException(f"Document set operation failed: {e}") from e
        except Exception as e:
            metadata[Metrics.External.NODE_STATUS] = ExecutionStatus.FAILED.value
            metadata["error"] = str(e)
            raise FlowExecutionFailedException(f"Unexpected error in document set operator: {e}") from e

        # Return original table unchanged (pass-through)
        return [table], metadata

    def _get_or_create_document_set(self) -> str:
        """Get existing document set or create a new one.

        The service layer handles the get-or-create logic, making this operation
        idempotent. If a document set with the given name exists, it will be used.
        Otherwise, a new one will be created.

        Returns:
            Document set ID

        Raises:
            DocumentSetNotFoundException: If updating and ID not found
            DocumentSetInvalidDataException: If validation fails
        """
        # If document_set_id provided, update existing
        if self.document_set_id:
            logger.info(f"Updating existing document set: {self.document_set_id}", extra=self.common_log_arguments)
            doc_set = self.service.update_document_set(
                document_set_id=self.document_set_id, description=self.description, metadata=self.metadata_config
            )
            return doc_set.id or ""

        # Use create_document_set which implements get-or-create pattern
        logger.info(f"Getting or creating document set: {self.document_set_name}", extra=self.common_log_arguments)
        doc_set = self.service.create_document_set(
            name=self.document_set_name,
            description=self.description,
            database_path=self.database_path,
            metadata=self.metadata_config,
        )
        return doc_set.id or ""

    def _handle_soft_deletes(self, doc_set_id: str, table_name: str) -> int:
        """Handle soft-deleted documents by removing them from storage.

        Args:
            doc_set_id: Document set ID
            table_name: Name of the data table

        Returns:
            Number of documents deleted
        """
        try:
            # Get soft-deleted IDs from incremental update utility
            # This would typically come from tracking deleted rows in the pipeline
            deleted_ids = self._get_soft_deleted_ids()

            if not deleted_ids:
                logger.debug("No soft-deleted documents to clean up", extra=self.common_log_arguments)
                return 0

            # Delete rows from storage
            deleted_count = self.storage.delete_rows(table_name, deleted_ids)

            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} soft-deleted documents", extra=self.common_log_arguments)

                # Recompute metrics after deletion
                self.service.compute_and_update_metrics(doc_set_id)

            return deleted_count

        except Exception as e:
            logger.warning(
                f"Failed to handle soft-deletes: {e}. Continuing without cleanup.", extra=self.common_log_arguments
            )
            return 0

    def _validate_database_path(self, database_path: str) -> str:
        """Validate and normalize database path to prevent path traversal.

        Args:
            database_path: Path to validate

        Returns:
            Validated and normalized absolute path

        Raises:
            FlowValidationException: If path is invalid or contains traversal attempts
        """
        from common.util.core.validation import validate_database_path

        try:
            return validate_database_path(database_path)
        except ValueError as exc:
            logger.warning(f"Database path validation failed: {exc}", extra=self.common_log_arguments)
            raise FlowValidationException(f"Invalid database path: {exc}") from exc
        except Exception as exc:
            logger.warning(f"Database path validation failed: {exc}", extra=self.common_log_arguments)
            raise FlowValidationException(f"Failed to validate database path: {exc}") from exc

    def _get_soft_deleted_ids(self) -> list[str]:
        """Get list of soft-deleted document IDs from incremental update tracking.

        Returns:
            List of document IDs that were soft-deleted
        """
        # This would integrate with the incremental update utility
        # to get IDs of documents that were deleted in this run
        # For now, return empty list as this requires integration
        # with the deleted rows tracker
        return []
