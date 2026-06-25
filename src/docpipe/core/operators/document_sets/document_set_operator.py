"""Document Set Operator for storing PyArrow table data with metadata tracking.

This operator stores PyArrow table data in a document set using DuckDB storage,
with automatic metrics computation and support for incremental updates with
soft-delete cleanup.
"""

# Import to trigger adapter registration
from typing import Any

import pyarrow as pa

from docpipe.core.assets.document_sets import adapters  # noqa: F401
from docpipe.core.assets.document_sets.application.services.document_set_service import DocumentSetService
from docpipe.core.assets.document_sets.factories import DataStoreFactory, MetadataRepositoryFactory
from docpipe.core.constants.constants import DocpipeConstants, ExecutionStatus, Metrics
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.abstract_operator import AbstractOperator, OperatorCategory
from docpipe.exceptions.docpipe_exceptions import (
    DocpipeException,
    FlowExecutionFailedException,
    FlowValidationException,
)
from docpipe.storage.duck_db.table_storage import DuckDBTableStorage
from docpipe.utils.infrastructure.logging import get_logger

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
    owner = DocpipeConstants.OWNER_DOCPIPE

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize the Document Set operator.

        Args:
            config: Configuration dictionary containing:
                - document_set_name (required): Name of the document set
                - description (optional): Description of the document set
                - metadata (optional): Additional metadata as JSON
                - document_set_id (optional): Existing document set ID for updates
                - data_backend (optional): Data store backend (default: "duckdb")
                - database_path (optional): Database path (default: from constants)

        Note:
            metadata_backend is NO LONGER supported - use global_config.storage_type
            Storage type for metadata is passed via operator params from orchestrator
        """
        super().__init__(config)

        try:
            # Extract configuration parameters
            document_set_name = config.get(OperatorConstants.DocumentSet.DOCUMENT_SET_NAME)
            if not document_set_name:
                raise FlowValidationException(f"{OperatorConstants.DocumentSet.DOCUMENT_SET_NAME} is required")

            self.document_set_name: str = document_set_name
            self.description: str | None = config.get(OperatorConstants.Config.DESCRIPTION)
            self.metadata_config: dict | None = config.get(OperatorConstants.Metadata.METADATA)
            self.document_set_id: str | None = config.get(OperatorConstants.DocumentSet.DOCUMENT_SET_ID)

            # Database path
            db_path = (
                config.get(OperatorConstants.DocumentSet.DATABASE_PATH) or DocpipeConstants.DOCUMENT_SET_DEFAULT_DB_PATH
            )
            self.database_path: str = self._validate_database_path(database_path=db_path)

            # Validate database path
            DuckDBTableStorage.validate_database_path(db_path=self.database_path)

            # Storage type will be set in transform() from params
            self.storage_type: str | None = None

            # Data backend from operator config (operator-specific)
            self.data_backend: str = config.get(
                OperatorConstants.DocumentSet.DATA_BACKEND, DocpipeConstants.DEFAULT_STORAGE_TYPE
            )

            logger.info(
                f"Initialized DocumentSetOperator for: {self.document_set_name}",
                extra=self.common_log_arguments,
            )
        except FlowValidationException:
            raise
        except DocpipeException as e:
            raise FlowValidationException(f"Invalid operator configuration: {e}") from e
        except Exception as e:
            raise FlowValidationException(f"Failed to initialize DocumentSetOperator: {e}") from e

    @staticmethod
    def get_metadata() -> dict[str, Any]:
        """Return operator metadata for flow validation and documentation."""
        return {
            OperatorConstants.Misc.IS_OPERATOR_AVAILABLE: (DocumentSetOperator.is_available()),
            OperatorConstants.Misc.CATEGORY: DocumentSetOperator.category.value,
            OperatorConstants.Misc.LABEL: "Document Set",
            OperatorConstants.Config.DESCRIPTION: (
                "Stores PyArrow table data in a document set with metadata tracking"
            ),
            OperatorConstants.Config.PARAMETERS: {
                "document_set_name": {
                    OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_STRING,
                    OperatorConstants.Config.REQUIRED: True,
                    OperatorConstants.Config.DESCRIPTION: "Name of the document set",
                },
                OperatorConstants.Config.DESCRIPTION: {
                    OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_STRING,
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DESCRIPTION: ("Description of the document set"),
                },
                OperatorConstants.Metadata.METADATA: {
                    OperatorConstants.Misc.TYPE: "object",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DESCRIPTION: "Additional metadata as JSON",
                },
                "document_set_id": {
                    OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_STRING,
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DESCRIPTION: ("Existing document set ID for updates"),
                },
                "data_backend": {
                    OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_STRING,
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: "duckdb",
                    OperatorConstants.Config.DESCRIPTION: (
                        "Data store backend (default: duckdb). Metadata backend uses global_config.storage_type"
                    ),
                },
                "database_path": {
                    OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_STRING,
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DESCRIPTION: ("Database path (default: from constants)"),
                },
            },
        }

    @staticmethod
    def get_required_features() -> list[str]:
        """Return list of required columns in the input table.

        Returns:
            List containing required column names
        """
        return [OperatorConstants.Columns.ID]

    def transform(self, table: pa.Table, file_name: str | None = None) -> tuple[list[pa.Table], dict[str, Any]]:
        """Transform the input table by storing it in a document set.

        This method:
        1. Extracts storage type from operator params (set by orchestrator)
        2. Creates metadata repository using global storage type
        3. Creates data store using operator-specific data_backend
        4. Stores data with automatic schema evolution
        5. Returns original table unchanged (pass-through)

        Args:
            table: PyArrow table containing the data to store
            file_name: Optional file name (unused, for interface compatibility)

        Returns:
            Tuple of:
                - List containing the original table (pass-through)
                - Metadata dictionary with storage info and metrics
        """
        # Extract storage type from config (set by orchestrator)
        self.storage_type = self.config.get(DocpipeConstants.STORAGE_TYPE, DocpipeConstants.DEFAULT_STORAGE_TYPE)

        logger.info(
            f"Using storage type: {self.storage_type} for metadata, {self.data_backend} for data",
            extra=self.common_log_arguments,
        )

        # Create metadata repository using global storage type
        metadata_repo_config: dict[str, Any] = {
            OperatorConstants.DocumentSet.DATABASE_PATH: self.database_path,
        }

        metadata_repository = MetadataRepositoryFactory.create(
            adapter_name=self.storage_type,  # Use global storage type
            config=metadata_repo_config,
        )

        # Create data store using operator-specific backend
        data_store_config: dict[str, Any] = {
            OperatorConstants.DocumentSet.DATABASE_PATH: self.database_path,
        }

        data_store = DataStoreFactory.create(
            adapter_name=self.data_backend,  # Use operator config
            config=data_store_config,
        )

        # Create service with port interfaces
        service = DocumentSetService(
            metadata_repository=metadata_repository,
            data_store=data_store,
        )

        # Initialize metadata
        metadata: dict[str, Any] = self.create_base_metadata(
            total_docs_count=table.num_rows, node_status=ExecutionStatus.COMPLETED.value
        )

        # Add storage-specific metadata
        metadata[OperatorConstants.DocumentSet.META_DOCUMENT_SET_NAME] = self.document_set_name
        metadata[OperatorConstants.DocumentSet.META_DATABASE_PATH] = self.database_path
        metadata["metadata_storage_type"] = self.storage_type
        metadata["data_storage_type"] = self.data_backend

        # Handle empty table
        if table.num_rows == 0:
            logger.warning("Empty table provided to DocumentSetOperator", extra=self.common_log_arguments)
            metadata[OperatorConstants.DocumentSet.META_STORED_DOCUMENTS] = 0
            return [table], metadata

        # Validate required columns
        if OperatorConstants.Columns.ID not in table.column_names:
            error_msg = f"Required column '{OperatorConstants.Columns.ID}' not found"
            metadata[Metrics.External.NODE_STATUS] = ExecutionStatus.FAILED.value
            metadata[OperatorConstants.DocumentSet.META_ERROR] = error_msg
            return [table], metadata

        try:
            # Get or create document set
            doc_set_id = self._get_or_create_document_set(service=service)
            metadata[OperatorConstants.DocumentSet.META_DOCUMENT_SET_ID] = doc_set_id

            logger.info(
                f"Using document set: {self.document_set_name} (ID: {doc_set_id})", extra=self.common_log_arguments
            )

            # Store data
            logger.info(f"Storing {table.num_rows} rows in document set", extra=self.common_log_arguments)

            updated_doc_set = service.store_data(document_set_id=doc_set_id, data=table)

            # Update metadata with computed metrics
            metadata[OperatorConstants.DocumentSet.META_STORED_DOCUMENTS] = updated_doc_set.total_documents
            metadata[OperatorConstants.DocumentSet.META_TOTAL_SIZE_BYTES] = updated_doc_set.total_size_bytes
            metadata[OperatorConstants.DocumentSet.META_TOTAL_PAGES] = updated_doc_set.total_pages
            metadata[OperatorConstants.DocumentSet.META_TABLE_NAME] = updated_doc_set.table_name
            metadata[Metrics.External.PROCESSED_DOCS] = table.num_rows

            logger.info(
                f"Successfully stored data. "
                f"Total documents: {updated_doc_set.total_documents}, "
                f"Size: {updated_doc_set.total_size_bytes} bytes, "
                f"Pages: {updated_doc_set.total_pages}",
                extra=self.common_log_arguments,
            )

        except DocpipeException as e:
            metadata[Metrics.External.NODE_STATUS] = ExecutionStatus.FAILED.value
            metadata[OperatorConstants.DocumentSet.META_ERROR] = str(e)
            raise FlowExecutionFailedException(f"Document set operation failed: {e}") from e
        except Exception as e:
            metadata[Metrics.External.NODE_STATUS] = ExecutionStatus.FAILED.value
            metadata[OperatorConstants.DocumentSet.META_ERROR] = str(e)
            raise FlowExecutionFailedException(f"Unexpected error in document set operator: {e}") from e

        # Return original table unchanged (pass-through)
        return [table], metadata

    def _get_or_create_document_set(self, *, service: DocumentSetService) -> str:
        """Get existing document set or create a new one.

        Args:
            service: Document set service instance

        Returns:
            Document set ID
        """
        if self.document_set_id:
            logger.info(f"Updating existing document set: {self.document_set_id}", extra=self.common_log_arguments)
            doc_set = service.update_document_set(
                document_set_id=self.document_set_id, description=self.description, metadata=self.metadata_config
            )
            return doc_set.id or ""

        logger.info(f"Getting or creating document set: {self.document_set_name}", extra=self.common_log_arguments)
        doc_set = service.create_document_set(
            name=self.document_set_name,
            description=self.description,
            database_path=self.database_path,
            metadata=self.metadata_config,
        )
        return doc_set.id or ""

    def _validate_database_path(self, *, database_path: str) -> str:
        """Validate and normalize database path to prevent path traversal.

        Args:
            database_path: Path to validate

        Returns:
            Validated and normalized absolute path

        Raises:
            FlowValidationException: If path is invalid or contains traversal attempts
        """
        from docpipe.utils.core.validation import validate_database_path

        try:
            return validate_database_path(database_path)
        except ValueError as exc:
            logger.warning(f"Database path validation failed: {exc}", extra=self.common_log_arguments)
            raise FlowValidationException(f"Invalid database path: {exc}") from exc
        except Exception as exc:
            logger.warning(f"Database path validation failed: {exc}", extra=self.common_log_arguments)
            raise FlowValidationException(f"Failed to validate database path: {exc}") from exc
