#!/usr/bin/env python3
"""
Extract Operator

A unified extraction operator that uses hexagonal architecture to support multiple
extraction strategies through a single interface. This operator delegates extraction
logic to specialized adapters based on the configured extraction modes.

Supported Text Extraction Modes:
    - docling_library: Local Docling extraction with tables, images, and optional VLM support
    - docling_serve: Remote extraction via Docling Serve API

Supported Entity Extraction Modes:
    - litellm: Multi-provider LLM extraction using LiteLLM (supports Ollama via OpenAI-compatible API)
    - watsonx: LLM-based entity extraction using IBM watsonx
    - docling: Template-based entity extraction using Docling templates
    - none: No entity extraction (default)

Architecture:
    This operator follows hexagonal architecture principles:
    - Operator (this file): Thin wrapper that handles configuration and delegation
    - Port (TextExtractionPort): Defines the extraction interface
    - Adapters: Implement specific extraction strategies
    - Factory: Creates appropriate adapter based on mode

Example Usage:
    # Standard text extraction only
    {
        "operator_type": "datasift.core.operators.extract.extract_operator.ExtractOperator",
        "operator_params": {
            "text_extraction_provider": "docling_library",
            "entity_extraction_provider": "none",
            "doc_column": "document",
            "extract_tables": true,
            "extract_images": false,
            "max_workers": 4
        }
    }

    # Text extraction with entity extraction (LiteLLM with Ollama)
    {
        "operator_type": "datasift.core.operators.extract.extract_operator.ExtractOperator",
        "operator_params": {
            "text_extraction_provider": "docling_library",
            "entity_extraction_provider": "litellm",
            "entity_model_id": "openai/granite4:latest",
            "entity_provider_config": {
                "api_base": "http://localhost:11434/v1",
                "api_key": "<ollama_key>"
            },
            "doc_column": "document",
            "max_workers": 4
        }
    }

    # VLM-enhanced text extraction (VLM is now a configuration option within docling_library)
    {
        "operator_type": "datasift.core.operators.extract.extract_operator.ExtractOperator",
        "operator_params": {
            "text_extraction_provider": "docling_library",
            "entity_extraction_provider": "none",
            "use_vlm_pipeline": true,
            "vlm_preset": "granite_docling",
            "vlm_engine_type": "transformers",
            "doc_column": "document",
            "max_workers": 2
        }
    }

    # Docling Serve text extraction
    {
        "operator_type": "datasift.core.operators.extract.extract_operator.ExtractOperator",
        "operator_params": {
            "text_extraction_provider": "docling_serve",
            "entity_extraction_provider": "none",
            "docling_serve_base_url": "http://localhost:5001",
            "docling_serve_timeout": 300,
            "doc_column": "document"
        }
    }
"""

import logging
import os
from typing import Any

import pyarrow as pa

from datasift.core.constants.constants import AttributeDataTypes, DatasiftConstants, Metrics
from datasift.core.constants.operator_constants import OperatorConstants
from datasift.core.operators.abstract_operator import AbstractOperator, OperatorCategory
from datasift.core.operators.extract.adapters.outbound.factories.entity_extraction_adapter_factory import (
    EntityExtractionAdapterFactory,
)
from datasift.core.operators.extract.adapters.outbound.factories.text_extraction_adapter_factory import (
    TextExtractionAdapterFactory,
)
from datasift.core.operators.extract.domain.models import (
    EntityExtractionMode,
    TextExtractionMode,
)
from datasift.core.operators.extract.ports.outbound.entity_extraction import EntityExtractionPort
from datasift.core.operators.extract.ports.outbound.text_extraction import TextExtractionPort
from datasift.core.operators.operator_utils import OperatorUtils
from datasift.exceptions.datasift_exceptions import FlowExecutionFailedException
from datasift.utils.infrastructure.logging import get_logger

logger: logging.Logger = get_logger()


class ExtractOperator(AbstractOperator):
    """Unified extraction operator using hexagonal architecture.

    This operator provides a single interface for multiple extraction strategies,
    delegating the actual extraction work to specialized adapters. The operator
    handles configuration parsing and adapter creation, while the adapter handles
    the extraction logic and parallel processing.

    Attributes:
        short_name: Operator identifier ("extract_operator")
        category: Operator category (OperatorCategory.EXTRACT)
        text_extraction_mode: Selected text extraction provider (basic, vlm, docling_serve)
        entity_extraction_mode: Selected entity extraction provider (litellm, watsonx, docling, none)
        text_adapter: Text extraction adapter instance
        entity_adapter: Entity extraction adapter instance (None if mode is "none")
        doc_column: Column name for storing extracted content
        expand_extracted_data: Whether to expand entity data into columns (entity extraction only)
    """

    short_name = OperatorConstants.Operators.EXTRACT_OPERATOR
    category = OperatorCategory.Extract
    owner = DatasiftConstants.OWNER_DATASIFT

    def __init__(self, *, config: dict[str, Any]):
        """Initialize the unified extract operator.

        Parses the extraction mode, builds adapter-specific configuration,
        and creates the appropriate adapter using the factory.

        Args:
            config: Configuration dictionary containing:
                Common extraction parameters:
                - max_workers: Number of parallel workers (default: 4)
                - use_processes: Use processes vs threads (default: False)
                - text_extraction_provider: Text provider selection ("docling_library", "docling_serve")
                - entity_extraction_provider: Entity provider selection ("litellm", "watsonx", "docling", "none")

                Common Text extraction parameters:
                - doc_column: Column name for extracted content (default: "doc_content")
                - extract_tables: Extract tables flag (default: True)
                - extract_images: Extract images flag (default: True)

                Common Entity extraction parameters:
                - output_column: Column name for extracted content (default: "extracted_content")
                - custom_schema: Schema dictionary for structured extraction
                - expand_extracted_data: Expand entity data flag for entity extraction only (default: False)

                VLM mode parameters:
                - vlm_preset: VLM preset name (default: "granite_docling")
                - vlm_engine_type: VLM engine type (default: None)
                - vlm_provider_config: Provider-specific configuration (default: None)

                Docling Serve mode parameters:
                - docling_serve_base_url: Docling Serve API URL (default: "http://localhost:5001")
                - docling_serve_api_key: Optional API key
                - docling_serve_timeout: Request timeout in seconds (default: 300)
                - docling_serve_poll_interval: Polling interval in seconds (default: 2)
                - docling_serve_max_retries: Maximum retry attempts (default: 3)
                - docling_serve_do_ocr: Enable OCR (default: True)
                - docling_serve_ocr_engine: OCR engine name (default: "easyocr")
                - docling_serve_ocr_languages: List of OCR languages (default: None)
                - docling_serve_pdf_backend: PDF backend (default: "dlparse_v2")
                - docling_serve_table_mode: Table extraction mode (default: "accurate")
                - docling_serve_image_export_mode: Image export mode (default: "placeholder")

                LiteLLM entity extraction parameters:
                - entity_model_id: LLM model identifier (e.g., "openai/granite4:latest")
                - entity_temperature: Sampling temperature 0.0-1.0 (default: 0.0)
                - entity_max_tokens: Maximum response tokens (default: 4096)
                - entity_max_doc_chars: Maximum document characters to send to LLM (default: 8000)
                - entity_provider_config: Provider-specific configuration (api_base, api_key, etc.)

                Watsonx entity extraction parameters:
                - entity_model_id: Watsonx model identifier
                - entity_temperature: Sampling temperature (default: 0.0)
                - entity_max_tokens: Maximum tokens in response (default: 4096)
                - entity_max_doc_chars: Maximum document characters (default: 8000)
                - entity_provider_config: Watsonx-specific configuration (container_kind, container_id, etc.)

                Docling entity extraction parameters:
                - No additional parameters required (uses template-based extraction)

        Raises:
            FlowExecutionFailedException: If extraction_mode is invalid or configuration is incomplete
        """
        super().__init__(config)

        # Parse text extraction mode (with backward compatibility)
        text_mode_str = config.get(
            OperatorConstants.ExtractionModes.TEXT_EXTRACTION_MODE,
            OperatorConstants.ExtractionModes.TEXT_MODE_DOCLING_LIBRARY,
        )
        try:
            self.text_extraction_mode = TextExtractionMode(text_mode_str)
        except ValueError as e:
            supported_modes = [mode.value for mode in TextExtractionMode]
            raise FlowExecutionFailedException(
                f"Invalid text_extraction_provider '{text_mode_str}'. Supported providers: {supported_modes}"
            ) from e

        # Parse entity extraction mode
        entity_mode_str = config.get(
            OperatorConstants.ExtractionModes.ENTITY_EXTRACTION_MODE, OperatorConstants.ExtractionModes.ENTITY_MODE_NONE
        )
        try:
            self.entity_extraction_mode = EntityExtractionMode(entity_mode_str)
        except ValueError as e:
            supported_modes = [mode.value for mode in EntityExtractionMode]
            raise FlowExecutionFailedException(
                f"Invalid entity_extraction_provider '{entity_mode_str}'. Supported providers: {supported_modes}"
            ) from e

        # Common parameters
        self.doc_column = config.get(OperatorConstants.Columns.DOC_COLUMN, OperatorConstants.Columns.DOC_COLUMN_DEFAULT)
        self.output_column = config.get(OperatorConstants.Columns.OUTPUT_COLUMN, OperatorConstants.Misc.ENTITIES)
        self.expand_extracted_data = config.get(OperatorConstants.Config.EXPAND_EXTRACTED_DATA, False)
        self.extract_tables = config.get(OperatorConstants.Config.EXTRACT_TABLES, False)
        self.extract_images = config.get(OperatorConstants.Config.EXTRACT_IMAGES, False)
        # Auto-detect optimal workers based on CPU count
        default_text_workers = OperatorUtils.get_optimal_workers(is_cpu_intensive=False)
        default_entity_workers = OperatorUtils.get_optimal_workers(is_cpu_intensive=True)
        text_max_workers = config.get(OperatorConstants.Config.MAX_WORKERS, default_text_workers)
        entity_max_workers = config.get(OperatorConstants.Config.MAX_WORKERS, default_entity_workers)
        use_processes = config.get(OperatorConstants.Config.USE_PROCESSES, False)

        # Create text extraction adapter
        try:
            self.text_adapter: TextExtractionPort = TextExtractionAdapterFactory.create_adapter(
                mode=self.text_extraction_mode,
                operator_config=config,
                max_workers=text_max_workers,
                use_processes=use_processes,
            )
            logger.info(
                "Created %s adapter for text extraction mode: %s",
                self.text_adapter.ADAPTER_DISPLAY_NAME,
                self.text_extraction_mode.value,
            )
        except Exception as e:
            logger.error("Failed to create text extraction adapter: %s", e)
            raise FlowExecutionFailedException(
                f"Failed to initialize text extraction adapter for provider '{self.text_extraction_mode.value}': {e}"
            ) from e

        # Create entity extraction adapter if enabled
        self.entity_adapter: EntityExtractionPort | None = None
        if self.entity_extraction_mode != EntityExtractionMode.NONE:
            try:
                self.entity_adapter = EntityExtractionAdapterFactory.create_adapter(
                    mode=self.entity_extraction_mode, operator_config=config, max_workers=entity_max_workers
                )
                if self.entity_adapter:
                    logger.info(
                        "Created %s adapter for entity extraction mode: %s",
                        self.entity_adapter.ADAPTER_DISPLAY_NAME,
                        self.entity_extraction_mode.value,
                    )
            except Exception as e:
                logger.error("Failed to create entity extraction adapter: %s", e)
                raise FlowExecutionFailedException(
                    f"Failed to initialize entity extraction adapter for provider '{self.entity_extraction_mode.value}': {e}"
                ) from e

    def _extract_doc_ids(self, *, doc_list: list[dict[str, Any]]) -> set[str]:
        """Extract document IDs from a document list.

        Args:
            doc_list: List of document dictionaries

        Returns:
            Set of normalized document IDs
        """
        doc_ids: set[str] = set()
        for doc in doc_list:
            if not isinstance(doc, dict):
                continue

            doc_id = doc.get(OperatorConstants.Columns.ID) or doc.get(OperatorConstants.Columns.DOC_ID_COLUMN)
            if doc_id is not None:
                doc_ids.add(str(doc_id))

        return doc_ids

    def _find_document_by_id(self, *, doc_list: list[dict[str, Any]], doc_id: str) -> dict[str, Any] | None:
        """Find a document by ID from the original list.

        Args:
            doc_list: List of document dictionaries
            doc_id: Normalized document ID to find

        Returns:
            Matching document dictionary, if present
        """
        for doc in doc_list:
            if not isinstance(doc, dict):
                continue

            current_doc_id = doc.get(OperatorConstants.Columns.ID) or doc.get(OperatorConstants.Columns.DOC_ID_COLUMN)
            if current_doc_id is not None and str(current_doc_id) == doc_id:
                return doc

        return None

    def _merge_document_maps(
        self,
        *,
        text_doc_ids: set[str],
        entity_doc_ids: set[str],
        text_doc_list: list[dict[str, Any]],
        entity_doc_list: list[dict[str, Any]],
        default_reason: str,
    ) -> dict[str, dict[str, Any]]:
        """Merge documents from text and entity extraction stages.

        When the same document appears in both stages, their reasons are combined.

        Args:
            text_doc_ids: Document IDs from text extraction stage
            entity_doc_ids: Document IDs from entity extraction stage
            text_doc_list: Original text extraction document list
            entity_doc_list: Original entity extraction document list
            default_reason: Default reason to use if none is provided

        Returns:
            Merged document map with combined reasons where applicable
        """
        merged_map: dict[str, dict[str, Any]] = {}
        shared_doc_ids = text_doc_ids & entity_doc_ids

        for doc_id in shared_doc_ids:
            text_doc = self._find_document_by_id(doc_list=text_doc_list, doc_id=doc_id)
            entity_doc = self._find_document_by_id(doc_list=entity_doc_list, doc_id=doc_id)
            if text_doc is None or entity_doc is None:
                continue

            text_reason = text_doc.get(OperatorConstants.Misc.REASON, default_reason)
            entity_reason = entity_doc.get(OperatorConstants.Misc.REASON, default_reason)
            merged_map[doc_id] = {
                **text_doc,
                OperatorConstants.Misc.REASON: f"Text extraction: {text_reason} | Entity extraction: {entity_reason}",
            }

        for doc_id in text_doc_ids - shared_doc_ids:
            text_doc = self._find_document_by_id(doc_list=text_doc_list, doc_id=doc_id)
            if text_doc is not None:
                merged_map[doc_id] = text_doc

        for doc_id in entity_doc_ids - shared_doc_ids:
            entity_doc = self._find_document_by_id(doc_list=entity_doc_list, doc_id=doc_id)
            if entity_doc is not None:
                merged_map[doc_id] = entity_doc

        return merged_map

    def _consolidate_metadata(
        self, *, text_metadata: dict[str, Any], entity_metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Consolidate metadata from text and entity extraction.

        A document is considered processed only if it succeeded in both text and entity
        extraction stages. If it failed or was skipped in either stage, it's marked
        accordingly in the consolidated metadata.

        This method uses a hybrid approach:
        1. Builds ID-to-document mappings for efficient lookup
        2. Merges failure/skip reasons when same document fails in both stages
        3. Calculates final processed count: total - (failed + skipped)

        Args:
            text_metadata: Metadata dictionary from text extraction adapter
            entity_metadata: Metadata dictionary from entity extraction adapter (None if disabled)

        Returns:
            Consolidated metadata dictionary with accurate counts and merged document lists
        """
        # If no entity extraction, return text metadata as-is
        if entity_metadata is None:
            return text_metadata

        text_failed_docs = text_metadata.get(Metrics.External.FAILED_DOCS, [])
        text_skipped_docs = text_metadata.get(Metrics.External.SKIPPED_DOCS, [])
        entity_failed_docs = entity_metadata.get(Metrics.External.FAILED_DOCS, [])
        entity_skipped_docs = entity_metadata.get(Metrics.External.SKIPPED_DOCS, [])

        merged_failed_map = self._merge_document_maps(
            text_doc_ids=self._extract_doc_ids(doc_list=text_failed_docs),
            entity_doc_ids=self._extract_doc_ids(doc_list=entity_failed_docs),
            text_doc_list=text_failed_docs,
            entity_doc_list=entity_failed_docs,
            default_reason=OperatorConstants.Extraction.ERROR,
        )

        merged_skipped_map = self._merge_document_maps(
            text_doc_ids=self._extract_doc_ids(doc_list=text_skipped_docs),
            entity_doc_ids=self._extract_doc_ids(doc_list=entity_skipped_docs),
            text_doc_list=text_skipped_docs,
            entity_doc_list=entity_skipped_docs,
            default_reason="Unknown reason",
        )

        # Calculate final processed count
        # Processed = total - (failed + skipped)
        total_docs = text_metadata.get(Metrics.External.TOTAL_DOCS, 0)
        failed_or_skipped_count = len(merged_failed_map) + len(merged_skipped_map)
        processed_count = total_docs - failed_or_skipped_count

        # Determine final execution status
        final_status = OperatorUtils.determine_execution_status(
            processed_count=processed_count,
            failed_count=len(merged_failed_map),
            skipped_count=len(merged_skipped_map),
        )

        # Return consolidated metadata
        return {
            Metrics.External.TOTAL_DOCS: total_docs,
            Metrics.External.PROCESSED_DOCS: processed_count,
            Metrics.External.FAILED_DOCS_COUNT: len(merged_failed_map),
            Metrics.External.FAILED_DOCS: list(merged_failed_map.values()),
            Metrics.External.SKIPPED_DOCS_COUNT: len(merged_skipped_map),
            Metrics.External.SKIPPED_DOCS: list(merged_skipped_map.values()),
            Metrics.External.NODE_STATUS: final_status,
        }

    @staticmethod
    def _add_page_statistics(*, metadata: dict[str, Any], table: pa.Table) -> dict[str, Any]:
        """Add page statistics by format to metadata using PyArrow vectorized operations.

        Args:
            metadata: Existing metadata dictionary
            table: PyArrow table containing 'name' and 'pages_processed' columns

        Returns:
            Updated metadata with page_type_stats and total_pages_converted statistics
        """
        import pyarrow.compute as pc

        if OperatorConstants.Columns.PAGES_PROCESSED not in table.column_names:
            logger.warning("Pages processed column not found in table, skipping page statistics")
            return metadata

        if OperatorConstants.Columns.NAME not in table.column_names:
            logger.warning("Name column not found in table, skipping page statistics")
            return metadata

        # Use PyArrow compute for total pages calculation
        pages_column = table.column(OperatorConstants.Columns.PAGES_PROCESSED)
        total_pages = pc.sum(pages_column).as_py()

        # For page_type_stats, we still need to iterate since we need to group by file extension
        # This is more efficient than converting entire table to pylist
        name_column = table.column(OperatorConstants.Columns.NAME)
        page_type_stats: dict[str, int] = {}

        for i in range(table.num_rows):
            name = name_column[i].as_py()
            pages = pages_column[i].as_py()

            # Extract file extension from name
            if name and isinstance(name, str):
                _, ext = os.path.splitext(name)
                format_key = ext.lower()[1:] if ext else OperatorConstants.Misc.UNKNOWN
            else:
                format_key = OperatorConstants.Misc.UNKNOWN

            # Accumulate page counts by format
            page_type_stats[format_key] = page_type_stats.get(format_key, 0) + pages

        # Add to metadata
        metadata[OperatorConstants.Metadata.PAGE_TYPE_STATS] = page_type_stats
        metadata[OperatorConstants.Metadata.TOTAL_PAGES_PROCESSED] = total_pages
        logger.info("Page statistics by format: %s, total pages: %d", page_type_stats, total_pages)

        return metadata

    @staticmethod
    def _drop_binary_content_column(*, tables: list[pa.Table]) -> list[pa.Table]:
        """Drop binary_content column from tables if present.

        After extraction is complete, the binary_content column is no longer needed
        and can be dropped to reduce memory usage and table size.

        Args:
            tables: List of PyArrow tables to process

        Returns:
            List of tables with binary_content column removed (if it existed)
        """
        result_tables = []

        for idx, table in enumerate(tables):
            if OperatorConstants.Columns.BINARY_CONTENT in table.column_names:
                # Log columns before dropping
                logger.info("Table %d BEFORE dropping binary_content - Columns: %s", idx, table.column_names)

                # Drop binary_content column in-place for memory efficiency
                table_without_binary = table.drop([OperatorConstants.Columns.BINARY_CONTENT])
                result_tables.append(table_without_binary)

                # Log columns after dropping
                logger.info(
                    "Table %d AFTER dropping binary_content - Columns: %s (dropped from %d rows)",
                    idx,
                    table_without_binary.column_names,
                    table.num_rows,
                )
            else:
                logger.info(
                    "Table %d - No binary_content column present; extraction uses on-demand binary fetch and populates "
                    "'content'. Columns: %s",
                    idx,
                    table.column_names,
                )
                result_tables.append(table)

        return result_tables

    def transform(
        self, table: pa.Table, file_name: str | None = None, metadata: dict[str, Any] | None = None
    ) -> tuple[list[pa.Table], dict[str, Any]]:
        """Transform documents using text and entity extraction adapters.

        This method orchestrates both text and entity extraction:
        1. First performs text extraction using text_adapter
        2. Then performs entity extraction using entity_adapter (if enabled)

        Text extraction reads document bytes from file paths provided by ingest operators.
        The extraction utilities resolve bytes from either the 'path' column (primary)
        or 'binary_content' column (backward compatibility fallback).

        Content Reuse:
        If document_classifier pre-fetched content and stored it in '_temp_content_for_extract',
        this operator will reuse it for docling_library text extraction mode, skipping re-extraction.

        Args:
            table: PyArrow table with document information containing columns:
                - id: Document ID
                - name: Document name/filename
                - path: File path to document (primary input from local ingest)
                - binary_content: Pre-loaded binary content (optional, for backward compatibility)
                - document_type: Document type for template selection (optional)
                - _temp_content_for_extract: Pre-fetched content from document_classifier (optional)
            file_name: Optional file name for logging
            metadata: Optional metadata dictionary to update

        Returns:
            Tuple of (list of transformed tables, metadata dictionary)

        Raises:
            FlowExecutionFailedException: If extraction fails
        """

        logger.info(
            "Starting extraction: text_mode='%s', entity_mode='%s' for %s documents",
            self.text_extraction_mode.value,
            self.entity_extraction_mode.value,
            table.num_rows,
        )
        if metadata is None:
            metadata = self.create_base_metadata(total_docs_count=table.num_rows)

        if table.num_rows == 0:
            # Add page metadata fields with zero/empty values for empty tables
            metadata[OperatorConstants.Metadata.PAGE_TYPE_STATS] = {}
            metadata[OperatorConstants.Metadata.TOTAL_PAGES_PROCESSED] = 0
            return [table], metadata

        # Check for pre-fetched content from document_classifier (hybrid approach)
        content_reused = False

        if DatasiftConstants.TEMP_CONTENT_COLUMN in table.column_names:
            can_reuse_prefetched_content = (
                self.text_extraction_mode == TextExtractionMode.DOCLING_LIBRARY
                and not self.extract_tables
                and not self.extract_images
            )

            if can_reuse_prefetched_content:
                logger.info(
                    f"Reusing pre-fetched content from '{DatasiftConstants.TEMP_CONTENT_COLUMN}' for "
                    f"{self.text_extraction_mode.value} with extract_tables={self.extract_tables} "
                    f"and extract_images={self.extract_images}"
                )

                column_names = list(table.column_names)
                temp_idx = column_names.index(DatasiftConstants.TEMP_CONTENT_COLUMN)
                column_names[temp_idx] = self.doc_column

                table = pa.table(
                    {
                        name: table.column(old_name)
                        for old_name, name in zip(table.column_names, column_names, strict=True)
                    },
                    schema=pa.schema(
                        [
                            (name, table.schema.field(old_name).type)
                            for old_name, name in zip(table.column_names, column_names, strict=True)
                        ]
                    ),
                )

                content_reused = True
                logger.info(f"Content reuse successful: skipping text extraction for {table.num_rows} documents")
            else:
                logger.info(
                    f"Pre-fetched content found but not reusable for text_mode={self.text_extraction_mode.value}, "
                    f"extract_tables={self.extract_tables}, extract_images={self.extract_images}. "
                    f"Dropping '{DatasiftConstants.TEMP_CONTENT_COLUMN}' and performing fresh extraction."
                )
                table = table.drop([DatasiftConstants.TEMP_CONTENT_COLUMN])

        result_tables: list[pa.Table] = []
        text_metadata: dict[str, Any] = {}
        entity_metadata: dict[str, Any] | None = None

        try:
            # Special case: if text_mode is docling_library and entity_mode is docling,
            # entity_mode docling can get content as well (combined extraction)
            if (
                self.text_extraction_mode == TextExtractionMode.DOCLING_LIBRARY
                and self.entity_extraction_mode == EntityExtractionMode.DOCLING
            ):
                logger.info("Starting combined text and entity extraction")
                if self.entity_adapter:
                    result_tables, result_metadata = self.entity_adapter.transform(table=table, metadata=metadata)
                else:
                    raise FlowExecutionFailedException("Entity adapter not initialized for combined extraction")

                # Add page statistics to metadata
                result_metadata = self._add_page_statistics(metadata=result_metadata, table=result_tables[0])

                # Drop binary_content column after extraction is complete
                result_tables = self._drop_binary_content_column(tables=result_tables)

                logger.info(
                    "Extraction completed: %s/%s documents processed",
                    result_metadata.get(Metrics.External.PROCESSED_DOCS, 0),
                    result_metadata.get(Metrics.External.TOTAL_DOCS, table.num_rows),
                )
                return result_tables, result_metadata

            # Step 1: Text extraction (skip if content was reused)
            if content_reused:
                # Content already present in doc_column, skip text extraction
                result_tables = [table]
                text_metadata = metadata.copy()
                text_metadata[Metrics.External.PROCESSED_DOCS] = table.num_rows
                logger.info(
                    "Skipped text extraction: reused pre-fetched content for %s documents",
                    table.num_rows,
                )
            else:
                # Perform normal text extraction
                result_tables, text_metadata = self.text_adapter.transform(table=table, metadata=metadata)

                logger.info(
                    "Text extraction completed: %s/%s documents processed",
                    text_metadata.get(Metrics.External.PROCESSED_DOCS, 0),
                    text_metadata.get(Metrics.External.TOTAL_DOCS, table.num_rows),
                )

            # Step 2: Entity extraction (if enabled)
            if self.entity_adapter is not None:
                logger.info("Starting entity extraction on extracted text")
                # Reset metadata for entity extraction to track independently
                entity_base_metadata = self.create_base_metadata(total_docs_count=table.num_rows)
                result_tables, entity_metadata = self.entity_adapter.transform(
                    table=result_tables[0], metadata=entity_base_metadata
                )

                logger.info(
                    "Entity extraction completed: %s/%s documents processed",
                    entity_metadata.get(Metrics.External.PROCESSED_DOCS, 0),
                    entity_metadata.get(Metrics.External.TOTAL_DOCS, table.num_rows),
                )

            # Step 3: Consolidate metadata from both stages
            consolidated_metadata = self._consolidate_metadata(
                text_metadata=text_metadata, entity_metadata=entity_metadata
            )

            # Step 4: Add page statistics to metadata
            consolidated_metadata = self._add_page_statistics(metadata=consolidated_metadata, table=result_tables[0])

            # Step 5: Drop binary_content column after extraction is complete
            result_tables = self._drop_binary_content_column(tables=result_tables)

            logger.info(
                "Final extraction results: %s/%s documents processed, %s failed, %s skipped",
                consolidated_metadata.get(Metrics.External.PROCESSED_DOCS, 0),
                consolidated_metadata.get(Metrics.External.TOTAL_DOCS, table.num_rows),
                consolidated_metadata.get(Metrics.External.FAILED_DOCS_COUNT, 0),
                consolidated_metadata.get(Metrics.External.SKIPPED_DOCS_COUNT, 0),
            )

            return result_tables, consolidated_metadata

        except FlowExecutionFailedException:
            # Re-raise flow execution exceptions as-is
            raise
        except Exception as e:
            logger.error("Extraction failed: %s", e)
            raise FlowExecutionFailedException(
                f"Extraction failed (text_provider='{self.text_extraction_mode.value}', "
                f"entity_provider='{self.entity_extraction_mode.value}'): {e}"
            ) from e

    @staticmethod
    def get_metadata() -> dict[str, Any]:
        """Get metadata about the operator including features and attributes.

        Returns comprehensive metadata describing the operator's capabilities,
        configuration parameters, and output features. This metadata is used
        for flow validation and UI generation.

        Returns:
            Dictionary containing operator metadata with:
                - category: Operator category
                - features: Output features/columns produced
                - is_operator_available: Availability status
                - attributes: Configuration parameters with descriptions
        """
        metadata_features = {
            OperatorConstants.Columns.DOC_COLUMN_DEFAULT: {
                OperatorConstants.Misc.NAME: "Document Content",
                OperatorConstants.Config.DESCRIPTION: "The markdown content extracted from the document (always present)",
                OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: True,
                OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_STRING,
                OperatorConstants.Misc.TAGS: [OperatorConstants.Misc.MANDATORY],
            },
            OperatorConstants.Columns.CONTENT_HTML: {
                OperatorConstants.Misc.NAME: "HTML Content",
                OperatorConstants.Config.DESCRIPTION: "HTML format of extracted content (optional, if 'html' in additional_formats)",
                OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: True,
                OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_STRING,
                OperatorConstants.Misc.TAGS: [],
            },
            OperatorConstants.Columns.CONTENT_JSON: {
                OperatorConstants.Misc.NAME: "JSON Content",
                OperatorConstants.Config.DESCRIPTION: "JSON format of extracted content (optional, if 'json' in additional_formats)",
                OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: True,
                OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_STRING,
                OperatorConstants.Misc.TAGS: [],
            },
            OperatorConstants.Columns.CONTENT_TEXT: {
                OperatorConstants.Misc.NAME: "Text Content",
                OperatorConstants.Config.DESCRIPTION: "Plain text format of extracted content (optional, if 'text' in additional_formats)",
                OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: True,
                OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_STRING,
                OperatorConstants.Misc.TAGS: [],
            },
            OperatorConstants.Columns.CONTENT_DOCTAGS: {
                OperatorConstants.Misc.NAME: "DocTags Content",
                OperatorConstants.Config.DESCRIPTION: "DocTags format of extracted content (optional, if 'doctags' in additional_formats)",
                OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: True,
                OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_STRING,
                OperatorConstants.Misc.TAGS: [],
            },
            OperatorConstants.Columns.DOC_ID_HASH_DEFAULT: {
                OperatorConstants.Misc.NAME: "Hash ID",
                OperatorConstants.Config.DESCRIPTION: "Hash ID of the document row",
                OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: True,
                OperatorConstants.Config.MANDATORY_FOR_VECTOR_DB: True,
                OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_STRING,
                OperatorConstants.Misc.IS_PRIMARY: True,
                OperatorConstants.Misc.TAGS: [OperatorConstants.Misc.MANDATORY, OperatorConstants.Misc.PRIMARY],
            },
            OperatorConstants.Misc.ENTITIES: {
                OperatorConstants.Misc.NAME: "Entities",
                OperatorConstants.Config.DESCRIPTION: "Extracted entities from document content (when entity extraction is enabled)",
                OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: True,
                OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_STRING,
                OperatorConstants.Misc.TAGS: [],
            },
            OperatorConstants.Columns.TABLES: {
                OperatorConstants.Misc.NAME: "Tables",
                OperatorConstants.Config.DESCRIPTION: "Extracted tables from document (when extract_tables is enabled)",
                OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: True,
                OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_STRING,
                OperatorConstants.Misc.TAGS: [],
            },
            OperatorConstants.Columns.IMAGES: {
                OperatorConstants.Misc.NAME: "Images",
                OperatorConstants.Config.DESCRIPTION: "Extracted images from document (when extract_images is enabled)",
                OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: True,
                OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_STRING,
                OperatorConstants.Misc.TAGS: [],
            },
            OperatorConstants.Columns.PAGES_PROCESSED: {
                OperatorConstants.Misc.NAME: "Pages Processed",
                OperatorConstants.Config.DESCRIPTION: "Estimated page count based on content length (3000 chars per page)",
                OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: False,
                OperatorConstants.Misc.TYPE: OperatorConstants.Types.TYPE_INT32,
                OperatorConstants.Misc.TAGS: [],
            },
        }

        return {
            OperatorConstants.Misc.CATEGORY: ExtractOperator.category.value,
            OperatorConstants.Config.FEATURES: metadata_features,
            OperatorConstants.Misc.IS_OPERATOR_AVAILABLE: ExtractOperator.is_available(),
            OperatorConstants.Config.ATTRIBUTES: {
                OperatorConstants.ExtractionModes.TEXT_EXTRACTION_MODE: {
                    OperatorConstants.Misc.NAME: "Text Extraction Mode",
                    OperatorConstants.Config.DESCRIPTION: (
                        f"Text extraction strategy: '{OperatorConstants.ExtractionModes.TEXT_MODE_DOCLING_LIBRARY}' (local Docling with optional VLM), "
                        f"or '{OperatorConstants.ExtractionModes.TEXT_MODE_DOCLING_SERVE}' (remote API)"
                    ),
                    OperatorConstants.Config.REQUIRED: True,
                    OperatorConstants.Config.DEFAULT: OperatorConstants.ExtractionModes.TEXT_MODE_DOCLING_LIBRARY,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                OperatorConstants.ExtractionModes.ENTITY_EXTRACTION_MODE: {
                    OperatorConstants.Misc.NAME: "Entity Extraction Mode",
                    OperatorConstants.Config.DESCRIPTION: (
                        f"Entity extraction strategy: '{OperatorConstants.ExtractionModes.ENTITY_MODE_LITELLM}' (LiteLLM multi-provider), "
                        f"'{OperatorConstants.ExtractionModes.ENTITY_MODE_WATSONX}' (IBM watsonx), "
                        f"'{OperatorConstants.ExtractionModes.ENTITY_MODE_DOCLING}' (template-based), "
                        f"or '{OperatorConstants.ExtractionModes.ENTITY_MODE_NONE}' (no entity extraction)"
                    ),
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: OperatorConstants.ExtractionModes.ENTITY_MODE_NONE,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                OperatorConstants.ExtractionModes.ENTITY_MODEL_NAME: {
                    OperatorConstants.Misc.NAME: "Model Name",
                    OperatorConstants.Config.DESCRIPTION: (
                        "LLM model name for entity extraction (litellm: 'openai/granite4:latest', watsonx: model identifier)"
                    ),
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: "llama3.2",
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                OperatorConstants.ExtractionModes.ENTITY_TEMPERATURE: {
                    OperatorConstants.Misc.NAME: "Temperature",
                    OperatorConstants.Config.DESCRIPTION: "Sampling temperature for entity extraction LLM (0.0-1.0)",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: 0.0,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.FLOAT,
                },
                OperatorConstants.ExtractionModes.ENTITY_MAX_TOKENS: {
                    OperatorConstants.Misc.NAME: "Max Tokens",
                    OperatorConstants.Config.DESCRIPTION: "Maximum tokens for entity extraction LLM response",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: 4096,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.INTEGER,
                },
                OperatorConstants.ExtractionModes.ENTITY_MAX_DOC_CHARS: {
                    OperatorConstants.Misc.NAME: "Max doc chars",
                    OperatorConstants.Config.DESCRIPTION: "Maximum chars to pass for entity extraction",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: 8000,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.INTEGER,
                },
                "entity_provider_config": {
                    OperatorConstants.Misc.NAME: "Entity Provider Configuration",
                    OperatorConstants.Config.DESCRIPTION: "Provider-specific configuration for entity extraction (e.g., {'api_key': 'xxx', 'api_base': 'http://...'})",  # pragma: allowlist secret
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: None,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.JSON,
                },
                OperatorConstants.Columns.DOC_COLUMN: {
                    OperatorConstants.Misc.NAME: "Document Column",
                    OperatorConstants.Config.DESCRIPTION: "Name of the column to store document content",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: OperatorConstants.Columns.DOC_COLUMN_DEFAULT,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                OperatorConstants.Columns.OUTPUT_COLUMN: {
                    OperatorConstants.Misc.NAME: "Output Column",
                    OperatorConstants.Config.DESCRIPTION: "Name of the column to store extracted entities (entity extraction only)",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: OperatorConstants.Misc.ENTITIES,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                OperatorConstants.Config.EXTRACT_TABLES: {
                    OperatorConstants.Misc.NAME: "Extract Tables",
                    OperatorConstants.Config.DESCRIPTION: "Whether to extract tables from documents",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.BOOLEAN,
                },
                OperatorConstants.Config.EXTRACT_IMAGES: {
                    OperatorConstants.Misc.NAME: "Extract Images",
                    OperatorConstants.Config.DESCRIPTION: "Whether to extract images from documents",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.BOOLEAN,
                },
                OperatorConstants.Extraction.ADDITIONAL_FORMATS: {
                    OperatorConstants.Misc.NAME: "Additional Output Formats",
                    OperatorConstants.Config.DESCRIPTION: (
                        "List of additional output formats to generate beyond the mandatory markdown format. "
                        "Markdown format is ALWAYS generated (creates doc_content column). "
                        "Additional options: "
                        "'html' (creates content_html column), "
                        "'json' (creates content_json column), "
                        "'text' (creates content_text column), "
                        "'doctags' (creates content_doctags column). "
                        "Example: ['html', 'json'] will generate markdown + HTML + JSON formats"
                    ),
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: [],
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.JSON,
                    OperatorConstants.Config.VALID_VALUES: OperatorConstants.Extraction.VALID_OUTPUT_FORMATS,
                },
                OperatorConstants.Config.EXPAND_EXTRACTED_DATA: {
                    OperatorConstants.Misc.NAME: "Expand Extracted Data",
                    OperatorConstants.Config.DESCRIPTION: "Whether to expand entity data JSON into individual columns (applies to entity extraction only)",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: False,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.BOOLEAN,
                },
                OperatorConstants.Config.MAX_WORKERS: {
                    OperatorConstants.Misc.NAME: "Max Workers",
                    OperatorConstants.Config.DESCRIPTION: "Maximum number of parallel workers for extraction",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: "auto (CPU-based)",
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.INTEGER,
                },
                OperatorConstants.Config.USE_PROCESSES: {
                    OperatorConstants.Misc.NAME: "Use Processes",
                    OperatorConstants.Config.DESCRIPTION: "Use ProcessPoolExecutor instead of ThreadPoolExecutor for CPU-intensive tasks",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: False,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.BOOLEAN,
                },
                OperatorConstants.Config.CUSTOM_SCHEMA: {
                    OperatorConstants.Misc.NAME: "Extraction Schema",
                    OperatorConstants.Config.DESCRIPTION: "Schema dictionary for structured extraction",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: None,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.JSON,
                },
                # VLM configuration (now part of docling_library mode)
                OperatorConstants.Config.USE_VLM_PIPELINE: {
                    OperatorConstants.Misc.NAME: "Use VLM Pipeline",
                    OperatorConstants.Config.DESCRIPTION: "Enable Vision-Language Model for enhanced extraction (docling_library mode only)",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: False,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.BOOLEAN,
                },
                OperatorConstants.Config.VLM_PRESET: {
                    OperatorConstants.Misc.NAME: "VLM Preset",
                    OperatorConstants.Config.DESCRIPTION: "VLM preset name for document processing (when use_vlm_pipeline=true, e.g., 'granite_docling')",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: "granite_docling",
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                OperatorConstants.Config.VLM_ENGINE_TYPE: {
                    OperatorConstants.Misc.NAME: "VLM Engine Type",
                    OperatorConstants.Config.DESCRIPTION: "VLM engine: 'transformers' (local, default), 'mlx' (macOS optimized), or 'api' (remote API)",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: None,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                OperatorConstants.Config.VLM_PROVIDER_CONFIG: {
                    OperatorConstants.Misc.NAME: "VLM Provider Configuration",
                    OperatorConstants.Config.DESCRIPTION: (
                        "Provider-specific configuration dict (when use_vlm_pipeline=true). "
                        "Required keys vary by engine type. "
                        "Watsonx: {'api_key', 'container_id', 'model_id', 'api_base_url'}. "
                        "Ollama/LMStudio: {'api_base_url'}. "
                        "OpenAI: {'api_key', 'api_base_url'}"
                    ),
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: None,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.JSON,
                },
                # Docling Serve mode parameters
                "docling_serve_base_url": {
                    OperatorConstants.Misc.NAME: "Docling Serve Base URL",
                    OperatorConstants.Config.DESCRIPTION: "Base URL for the docling-serve service (docling_serve mode only)",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: "http://localhost:5001",
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                "docling_serve_api_key": {
                    OperatorConstants.Misc.NAME: "Docling Serve API Key",
                    OperatorConstants.Config.DESCRIPTION: "Optional API key sent as X-API-KEY when calling docling-serve",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: None,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                "docling_serve_timeout": {
                    OperatorConstants.Misc.NAME: "Docling Serve Timeout",
                    OperatorConstants.Config.DESCRIPTION: "Request timeout in seconds for docling-serve operations",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: 300,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.INTEGER,
                },
                "docling_serve_poll_interval": {
                    OperatorConstants.Misc.NAME: "Docling Serve Poll Interval",
                    OperatorConstants.Config.DESCRIPTION: "Polling interval in seconds when waiting for docling-serve task completion",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: 2,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.INTEGER,
                },
                "docling_serve_max_retries": {
                    OperatorConstants.Misc.NAME: "Docling Serve Max Retries",
                    OperatorConstants.Config.DESCRIPTION: "Maximum retry attempts for docling-serve status polling",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: 3,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.INTEGER,
                },
                "docling_serve_do_ocr": {
                    OperatorConstants.Misc.NAME: "Docling Serve OCR Enabled",
                    OperatorConstants.Config.DESCRIPTION: "Whether OCR should be enabled when processing documents with docling-serve",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.BOOLEAN,
                },
                "docling_serve_ocr_engine": {
                    OperatorConstants.Misc.NAME: "Docling Serve OCR Engine",
                    OperatorConstants.Config.DESCRIPTION: "OCR engine name passed to docling-serve",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: "easyocr",
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                "docling_serve_ocr_languages": {
                    OperatorConstants.Misc.NAME: "Docling Serve OCR Languages",
                    OperatorConstants.Config.DESCRIPTION: "List of OCR languages passed to docling-serve",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: None,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.JSON,
                },
                "docling_serve_pdf_backend": {
                    OperatorConstants.Misc.NAME: "Docling Serve PDF Backend",
                    OperatorConstants.Config.DESCRIPTION: "PDF backend to use in docling-serve",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: "dlparse_v2",
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                "docling_serve_table_mode": {
                    OperatorConstants.Misc.NAME: "Docling Serve Table Mode",
                    OperatorConstants.Config.DESCRIPTION: "Table structure extraction mode for docling-serve",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: "fast",
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                "docling_serve_image_export_mode": {
                    OperatorConstants.Misc.NAME: "Docling Serve Image Export Mode",
                    OperatorConstants.Config.DESCRIPTION: "Image export mode passed to docling-serve",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: "placeholder",
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
            },
        }
