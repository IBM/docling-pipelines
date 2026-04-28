"""Text extraction port interface.

This module defines the port interface for text extraction operations following
hexagonal architecture principles. The port contains the parallel processing
orchestration logic, while adapters implement the specific extraction mechanics.
"""

import json
import logging
from abc import ABC, abstractmethod
from concurrent.futures import Future, ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from typing import Any

import pyarrow as pa

from common.constants.constants import ExecutionStatus, Metrics
from common.constants.operator_constants import OperatorConstants
from common.util.data.transform import TransformUtils
from common.util.infrastructure.logging import get_logger
from core.operators.abstract_operator import AbstractOperator
from core.operators.functional.doc_id_hash import DocIdHashOperator
from core.operators.operator_utils import OperatorUtils

logger: logging.Logger = get_logger()


class TextExtractionPort(ABC):
    """Port interface for text extraction with parallel processing orchestration.

    The port acts as an orchestrator that manages:
    - Parallel processing framework (executor management)
    - Worker task submission and result fetching
    - Result aggregation and error handling
    - Progress tracking and metadata collection

    Adapters implement the specific extraction logic via the extract_single_document
    method, which is called by the port's parallel processing framework.

    Document Content Resolution:
        The port expects input tables with a 'path' column (primary) from local ingest
        operators. Document bytes are resolved from either:
        - 'path' column: File path to read bytes from (primary behavior)
        - 'binary_content' column: Pre-loaded bytes (backward compatibility fallback)

    Design Philosophy:
        Port = Orchestration + Parallel Processing
        Adapter = Specific Extraction Logic

    Attributes:
        ADAPTER_NAME: Short identifier for the adapter (e.g., "docling", "vlm")
        ADAPTER_DISPLAY_NAME: Human-readable adapter name (e.g., "Docling", "VLM")
        max_workers: Number of parallel workers for processing
        use_processes: Whether to use ProcessPoolExecutor (True) or ThreadPoolExecutor (False)
        doc_column: Column name for storing extracted document content
        extract_tables: Whether to extract tables from documents
        extract_images: Whether to extract images from documents
    """

    ADAPTER_NAME: str = "base"
    ADAPTER_DISPLAY_NAME: str = "Base Adapter"

    def __init__(self, *, config: dict[str, Any]) -> None:
        """Initialize the text extraction port with configuration.

        Args:
            config: Configuration dictionary containing:
                - max_workers: Number of parallel workers (default: 4)
                - use_processes: Use processes vs threads (default: False)
                - doc_column: Column name for extracted content (default: "doc_content")
                - extract_tables: Extract tables flag (default: True)
                - extract_images: Extract images flag (default: True)
                - Additional adapter-specific configuration
        """
        self.max_workers = config.get("max_workers", 4)
        self.use_processes = config.get("use_processes", False)
        self.doc_column = config.get("doc_column", OperatorConstants.Columns.DOC_COLUMN_DEFAULT)
        self.extract_tables = config.get("extract_tables", True)
        self.extract_images = config.get("extract_images", True)
        self.common_log_arguments = config.get("common_log_arguments", {})

        # Subclasses should initialize their adapter-specific configuration
        self._init_adapter_config(config=config)

    def _init_adapter_config(self, *, config: dict[str, Any]) -> None:
        """Initialize adapter-specific configuration.

        Subclasses should override this method to set up their specific configuration
        parameters (e.g., VLM settings, Docling Serve URL, template configuration).

        Args:
            config: Full configuration dictionary
        """
        # Default implementation does nothing - subclasses override as needed

    def transform(self, *, table: pa.Table, metadata: dict[str, Any]) -> tuple[list[pa.Table], dict[str, Any]]:
        """Orchestrate parallel extraction across documents.

        This method implements the parallel processing pattern:
        1. Validate input and check for existing features
        2. Prepare document tasks from PyArrow table
        3. Create executor (ProcessPoolExecutor or ThreadPoolExecutor)
        4. Submit tasks to workers via _submit_extraction_task
        5. Collect results using as_completed pattern
        6. Aggregate results and handle errors
        7. Add extracted content to table and generate document IDs
        8. Return transformed table with metadata

        Args:
            table: PyArrow table with document information containing columns:
                - id: Document ID
                - name: Document name/filename
                - path: Document path (optional)
                - binary_content: Binary content of the document (optional)
            metadata: Optional metadata dictionary to update

        Returns:
            Tuple of (list of transformed tables, metadata dictionary)
        """

        # Check if extraction features already exist
        if self._check_existing_features(table=table):
            metadata[OperatorConstants.Extraction.MESSAGE] = (
                f"{self.doc_column} already present. Moving to next operation"
            )
            return [table], metadata

        # Prepare document tasks
        doc_tasks: list[dict[str, Any]] = OperatorUtils.prepare_document_content_fetch(table=table)
        doc_contents: list[str] = [""] * table.num_rows
        doc_metadata_list: list[dict[str, Any]] = [{}] * table.num_rows
        doc_tables_list: list[list[dict[str, Any]]] = [[]] * table.num_rows
        doc_images_list: list[list[dict[str, Any]]] = [[]] * table.num_rows
        remove_row_idx: list[int] = []
        # Select executor type
        executor_class = ProcessPoolExecutor if self.use_processes else ThreadPoolExecutor

        logger.info(
            "Processing %s documents in parallel with %s workers using %s",
            len(doc_tasks),
            self.max_workers,
            self.ADAPTER_DISPLAY_NAME,
        )

        # Process documents in parallel
        with executor_class(max_workers=self.max_workers) as executor:
            future_to_task: dict[Future, dict[str, Any]] = {}

            # Submit all tasks
            for task in doc_tasks:
                if "error" in task:
                    AbstractOperator.record_failed_document(
                        metadata=metadata, doc_id=str(task["doc_id"]), doc_name=task["doc_name"], reason=task["error"]
                    )
                    continue

                future = self._submit_extraction_task(executor=executor, task=task)
                future_to_task[future] = task

            # Collect results as they complete
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                idx = task["idx"]

                try:
                    result = future.result()
                    self._process_extraction_result(
                        result=result,
                        task=task,
                        idx=idx,
                        doc_contents=doc_contents,
                        doc_metadata_list=doc_metadata_list,
                        doc_tables_list=doc_tables_list,
                        doc_images_list=doc_images_list,
                        remove_row_idx=remove_row_idx,
                        metadata=metadata,
                    )
                except Exception as e:
                    logger.error("Error processing document at index %s: %s", idx, e)
                    AbstractOperator.record_failed_document(
                        metadata=metadata, doc_id=str(task["doc_id"]), doc_name=task["doc_name"], reason=str(e)
                    )
        if remove_row_idx:
            table = OperatorUtils.remove_rows(table=table, remove_row_idx=remove_row_idx)
            doc_contents = [content for idx, content in enumerate(doc_contents) if idx not in remove_row_idx]
            doc_tables_list = [data for idx, data in enumerate(doc_tables_list) if idx not in remove_row_idx]
            doc_images_list = [data for idx, data in enumerate(doc_images_list) if idx not in remove_row_idx]

        # Add extracted content to table
        if doc_contents:
            table = TransformUtils.add_column(table=table, name=self.doc_column, content=doc_contents)

        if self.extract_tables:
            doc_tables_serialized = [json.dumps(data) if data else None for data in doc_tables_list]
            table = TransformUtils.add_column(
                table=table, name=OperatorConstants.Columns.TABLES, content=doc_tables_serialized
            )

        if self.extract_images:
            doc_images_serialized = [json.dumps(data) if data else None for data in doc_images_list]
            table = TransformUtils.add_column(
                table=table, name=OperatorConstants.Columns.IMAGES, content=doc_images_serialized
            )
        # Generate document hash IDs
        logger.info("Generating hash id and adding it to table")
        hash_operator = DocIdHashOperator({OperatorConstants.Columns.DOC_COLUMN: self.doc_column})
        table_list, _ = hash_operator.transform(table)
        table = table_list[0]

        # Set final status
        metadata[Metrics.External.NODE_STATUS] = (
            ExecutionStatus.COMPLETED_WITH_ERRORS.value
            if metadata[Metrics.External.FAILED_DOCS_COUNT] > 0
            else ExecutionStatus.COMPLETED.value
        )

        return [table], metadata

    def _submit_extraction_task(
        self, executor: ProcessPoolExecutor | ThreadPoolExecutor, task: dict[str, Any]
    ) -> Future:
        """Submit extraction task to executor.

        Document bytes in the task are resolved from either the 'path' column
        (primary behavior) or 'binary_content' column (backward compatibility)
        by the prepare_document_content_fetch() utility method.

        Args:
            executor: ProcessPoolExecutor or ThreadPoolExecutor instance
            task: Document task dictionary containing:
                - idx: Task index
                - doc_id: Document ID
                - doc_name: Document name/path
                - binary_content: Binary document content (resolved from path or binary_content column)

        Returns:
            Future object for result retrieval
        """
        # Submit task to executor
        return executor.submit(
            self.extract_single_document, file_path=task["doc_name"], binary_content=task["binary_content"]
        )

    @abstractmethod
    def extract_single_document(self, *, file_path: str, binary_content: bytes, **kwargs: Any) -> dict[str, Any]:
        """Extract content from a single document.

        This is the adapter-specific extraction logic that runs in parallel workers.
        Each adapter implements its own extraction mechanics here.

        Args:
            file_path: Path to the document (used for logging and file type detection)
            binary_content: Binary content of the document
            **kwargs: Adapter-specific parameters (e.g., vlm_config)

        Returns:
            Dictionary with extraction results:
            {
                "success": bool,                    # Extraction success indicator
                "doc_content": str,                 # Extracted text content (markdown)
                "metadata": dict,                   # Additional metadata (page_count, etc.)
                "error": str                        # Error message if failed
            }
        """
        pass

    def _process_extraction_result(
        self,
        result: dict[str, Any],
        task: dict[str, Any],
        idx: int,
        doc_contents: list[str],
        doc_metadata_list: list[dict[str, Any]],
        doc_tables_list: list[list[dict[str, Any]]],
        doc_images_list: list[list[dict[str, Any]]],
        remove_row_idx: list[int],
        metadata: dict[str, Any],
    ) -> None:
        """Process extraction result and update data structures.

        Handles both successful and failed extraction results by updating the
        appropriate lists and metadata in place.

        Args:
            result: Extraction result dictionary from extract_single_document
            task: Document task dictionary containing doc_id and doc_name
            idx: Index in the result lists
            doc_contents: List to store extracted document contents
            doc_metadata_list: List to store document metadata
            doc_tables_list: List to store extracted tables
            doc_images_list: List to store extracted images
            metadata: Metadata dictionary to update with processing stats
        """
        if result[OperatorConstants.Extraction.SUCCESS]:
            extracted_content = result.get(OperatorConstants.Columns.DOC_COLUMN_DEFAULT)
            if not extracted_content or (isinstance(extracted_content, str) and not extracted_content.strip()):
                AbstractOperator.record_skipped_document(
                    metadata=metadata,
                    doc_id=str(task["doc_id"]),
                    doc_name=task["doc_name"],
                    reason="Empty extracted content",
                )
                logger.warning(
                    "Skipping document %s due to empty extracted content",
                    task["doc_name"],
                    extra=self.common_log_arguments,
                )
                remove_row_idx.append(idx)
                return

            doc_contents[idx] = extracted_content
            doc_metadata_list[idx] = result.get(OperatorConstants.Metadata.METADATA, {})

            # Extract tables if present
            if OperatorConstants.Columns.TABLES in result:
                doc_tables_list[idx] = result[OperatorConstants.Columns.TABLES]

            # Extract images if present
            if OperatorConstants.Columns.IMAGES in result:
                doc_images_list[idx] = result[OperatorConstants.Columns.IMAGES]

            # Increment processed count
            metadata[Metrics.External.PROCESSED_DOCS] += 1
            return

        # Handle extraction failure
        AbstractOperator.record_failed_document(
            metadata=metadata,
            doc_id=str(task["doc_id"]),
            doc_name=task["doc_name"],
            reason=result.get(OperatorConstants.Extraction.ERROR, "Unknown error"),
        )
        logger.error(
            "Failed to extract content from %s: %s", task["doc_name"], result.get(OperatorConstants.Extraction.ERROR)
        )
        remove_row_idx.append(idx)

    def _check_existing_features(self, *, table: pa.Table) -> bool:
        """Check if requested extraction features already exist in the table.

        Args:
            table: PyArrow table to check

        Returns:
            True if all requested features exist, False otherwise
        """
        return self.doc_column in table.column_names
