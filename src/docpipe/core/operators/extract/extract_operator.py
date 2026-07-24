#!/usr/bin/env python3
"""
Extract Operator

A unified extraction operator that uses hexagonal architecture to support multiple
extraction strategies through a single interface. This operator delegates extraction
logic to specialized adapters based on the configured extraction providers.

Supported Text Extraction Providers:
    - docling_library: Local Docling extraction with tables, images, and optional VLM support
    - docling_serve: Remote extraction via Docling Serve API

Supported Entity Extraction Providers:
    - litellm: Multi-provider LLM extraction using LiteLLM (supports Ollama via OpenAI-compatible API)
    - watsonx: LLM-based entity extraction using IBM watsonx
    - docling: Template-based entity extraction using Docling templates
    - none: No entity extraction (default)

Architecture:
    This operator follows hexagonal architecture principles:
    - Operator (this file): Thin wrapper that handles configuration and delegation
    - Port (TextExtractionPort): Defines the extraction interface
    - Adapters: Implement specific extraction strategies
    - Factory: Creates appropriate adapter based on provider

Example Usage:
    # Standard text extraction only
    {
        "operator_type": "docpipe.core.operators.extract.extract_operator.ExtractOperator",
        "operator_params": {
            "text_extraction": {
                "provider": "docling_library",
                "doc_column": "document"
            },
            "max_workers": 4
        }
    }

    # Text extraction with entity extraction (LiteLLM with Ollama)
    {
        "operator_type": "docpipe.core.operators.extract.extract_operator.ExtractOperator",
        "operator_params": {
            "text_extraction": {
                "provider": "docling_library",
                "doc_column": "document"
            },
            "entity_extraction": {
                "provider": "litellm",
                "provider_config": {
                    "model_id": "openai/granite4:latest",
                    "api_base": "http://localhost:11434/v1",
                    "api_key": "<ollama_key>",
                    "temperature": 0.0,
                    "max_tokens": 4096
                },
                "output_column": "entities",
                "max_doc_chars": 8000
            },
            "max_workers": 4
        }
    }

    # VLM-enhanced text extraction
    {
        "operator_type": "docpipe.core.operators.extract.extract_operator.ExtractOperator",
        "operator_params": {
            "text_extraction": {
                "provider": "docling_library",
                "doc_column": "document",
                "max_workers": 2,
                "provider_config": {
                    "vlm_pipeline": {
                        "preset": "granite_docling",
                        "engine": "api_ollama",
                        "engine_options": {
                            "api_base": "http://localhost:11434",
                            "model_id": "ibm/granite-docling:258m"
                        }
                    }
                }
            }
        }
    }

    # Docling Serve text extraction
    {
        "operator_type": "docpipe.core.operators.extract.extract_operator.ExtractOperator",
        "operator_params": {
            "text_extraction": {
                "provider": "docling_serve",
                "doc_column": "document",
                "provider_config": {
                    "base_url": "http://localhost:5001",
                    "timeout": 300,
                    "do_ocr": true
                }
            }
        }
    }
"""

import logging
import os
from typing import Any

import pyarrow as pa

from docpipe.core.constants.constants import (
    AttributeDataTypes,
    DoclingClientConfigConstants,
    DocpipeConstants,
    Metrics,
)
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.abstract_operator import AbstractOperator, OperatorCategory
from docpipe.core.operators.extract.adapters.outbound.factories.entity_extraction_adapter_factory import (
    EntityExtractionAdapterFactory,
)
from docpipe.core.operators.extract.adapters.outbound.factories.text_extraction_adapter_factory import (
    TextExtractionAdapterFactory,
)
from docpipe.core.operators.extract.domain.models import (
    EntityExtractionMode,
    TextExtractionMode,
)
from docpipe.core.operators.extract.ports.outbound.entity_extraction import EntityExtractionPort
from docpipe.core.operators.extract.ports.outbound.text_extraction import TextExtractionPort
from docpipe.core.operators.operator_utils import OperatorUtils
from docpipe.exceptions.docpipe_exceptions import FlowExecutionFailedException
from docpipe.utils.infrastructure.logging import get_logger
from docpipe.utils.operators.config_validation import validate_config_from_metadata

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
        text_extraction (dict): Text extraction configuration
            - provider (str): Provider for text extraction (docling_library, docling_serve)
            - provider_config (dict): Provider-specific configuration
        entity_extraction (dict): Entity extraction configuration
            - provider (str): Provider for entity extraction (litellm, watsonx, docling, none)
            - provider_config (dict): Provider-specific configuration
        doc_column (str): Column name for storing extracted content
        expand_extracted_data (bool): Whether to expand entity data into columns (entity extraction only)
    """

    short_name = OperatorConstants.Operators.EXTRACT_OPERATOR
    category = OperatorCategory.Extract
    owner = DocpipeConstants.OWNER_DOCPIPE

    def __init__(self, *, config: dict[str, Any]):  # NOSONAR python:S3776
        """Initialize the unified extract operator.

        Parses the extraction provider, builds adapter-specific configuration,
        and creates the appropriate adapter using the factory.

        Args:
            config: Configuration dictionary with nested structure:
                - text_extraction: Nested object containing:
                    - provider: Text provider ("docling_library", "docling_serve")
                    - provider_config: Provider-specific configuration
                        - additional_formats: List of additional output formats
                          Options: 'html', 'json', 'text', 'doctags', 'doclang'
                    - doc_column: Column name for extracted content
                - entity_extraction: Optional nested object containing:
                    - provider: Entity provider ("litellm", "watsonx", "docling")
                    - provider_config: Provider-specific configuration (model_id, api_base, etc.)
                    - output_column: Column name for extracted entities
                    - max_doc_chars: Maximum document characters
                    - custom_schema: Schema dictionary for structured extraction
                    - expand_extracted_data: Expand entity data flag
                - max_workers: Number of parallel workers (default: auto-detect)
                - use_processes: Use processes vs threads (default: False)

        Raises:
            FlowExecutionFailedException: If extraction_mode is invalid or configuration is incomplete
        """
        super().__init__(config)

        # Extract text_extraction nested config and store for later use
        self.text_extraction_config = config.get(OperatorConstants.Config.TEXT_EXTRACTION, {})
        if not self.text_extraction_config:
            raise FlowExecutionFailedException(
                f"Missing required '{OperatorConstants.Config.TEXT_EXTRACTION}' configuration object"
            )

        # Parse text extraction provider
        text_mode_str = self.text_extraction_config.get(
            OperatorConstants.Config.PROVIDER,
            OperatorConstants.ExtractionModes.TEXT_MODE_DOCLING_LIBRARY,
        )
        try:
            self.text_extraction_mode = TextExtractionMode(text_mode_str)
        except ValueError as e:
            supported_modes = [mode.value for mode in TextExtractionMode]
            raise FlowExecutionFailedException(
                f"Invalid text_extraction.provider '{text_mode_str}'. Supported providers: {supported_modes}"
            ) from e

        # Extract entity_extraction nested config (optional)
        entity_extraction_config = config.get(OperatorConstants.Config.ENTITY_EXTRACTION)

        # Parse entity extraction mode
        if entity_extraction_config:
            entity_mode_str = entity_extraction_config.get(OperatorConstants.Config.PROVIDER)
            if not entity_mode_str:
                raise FlowExecutionFailedException(
                    "entity_extraction.provider is required when entity_extraction is present"
                )
            try:
                self.entity_extraction_mode = EntityExtractionMode(entity_mode_str)
            except ValueError as e:
                supported_modes = [mode.value for mode in EntityExtractionMode]
                raise FlowExecutionFailedException(
                    f"Invalid entity_extraction.provider '{entity_mode_str}'. Supported providers: {supported_modes}"
                ) from e
        else:
            self.entity_extraction_mode = EntityExtractionMode.NONE

        # Extract common parameters from text_extraction
        self.doc_column = self.text_extraction_config.get(
            OperatorConstants.Columns.DOC_COLUMN, OperatorConstants.Columns.DOC_COLUMN_DEFAULT
        )

        # Extract entity extraction parameters
        if entity_extraction_config:
            self.output_column = entity_extraction_config.get(
                OperatorConstants.Columns.OUTPUT_COLUMN, OperatorConstants.Misc.ENTITIES
            )
            self.expand_extracted_data = entity_extraction_config.get(
                OperatorConstants.Config.EXPAND_EXTRACTED_DATA, False
            )
        else:
            self.output_column = OperatorConstants.Misc.ENTITIES
            self.expand_extracted_data = False

        # Auto-detect optimal workers based on CPU count
        default_text_workers = OperatorUtils.get_optimal_workers(is_cpu_intensive=False)
        default_entity_workers = OperatorUtils.get_optimal_workers(is_cpu_intensive=True)
        text_max_workers = config.get(OperatorConstants.Config.MAX_WORKERS, default_text_workers)
        entity_max_workers = config.get(OperatorConstants.Config.MAX_WORKERS, default_entity_workers)
        use_processes = config.get(OperatorConstants.Config.USE_PROCESSES, False)

        # Prepare global config for job tracking and other global settings
        # Include ingest_source for on-demand binary fetching from cloud sources
        global_config = {
            OperatorConstants.Config.COMMON_LOG_ARGUMENTS: config.get(
                OperatorConstants.Config.COMMON_LOG_ARGUMENTS, {}
            ),
            DocpipeConstants.JOB_RUN_ID: config.get(DocpipeConstants.JOB_RUN_ID),
            DocpipeConstants.NODE_ID: config.get(DocpipeConstants.NODE_ID),
            DocpipeConstants.NODE_NAME: config.get(DocpipeConstants.NODE_NAME),
            DocpipeConstants.BATCH_ID: config.get(DocpipeConstants.BATCH_ID),
        }

        # Preserve ingest_source from config if present (for cloud source binary fetching)
        if OperatorConstants.Config.INGEST_SOURCE in config:
            global_config[OperatorConstants.Config.INGEST_SOURCE] = config[OperatorConstants.Config.INGEST_SOURCE]

        # Create text extraction adapter - pass nested config directly
        try:
            self.text_adapter: TextExtractionPort = TextExtractionAdapterFactory.create_adapter(
                mode=self.text_extraction_mode,
                text_extraction_config=self.text_extraction_config,
                global_config=global_config,
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

        # Create entity extraction adapter if enabled - pass nested config directly
        self.entity_adapter: EntityExtractionPort | None = None
        if self.entity_extraction_mode != EntityExtractionMode.NONE and entity_extraction_config:
            try:
                self.entity_adapter = EntityExtractionAdapterFactory.create_adapter(
                    mode=self.entity_extraction_mode,
                    entity_extraction_config=entity_extraction_config,
                    global_config=global_config,
                    doc_column=self.doc_column,
                    max_workers=entity_max_workers,
                )
                if self.entity_adapter:
                    logger.info(
                        "Created %s adapter for entity extraction provider: %s",
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
        total_pages = pc.sum(pages_column).as_py()  # type: ignore[attr-defined]

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

    def transform(  # NOSONAR python:S3776
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
        this operator will reuse it for docling_library text extraction provider, skipping re-extraction.

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

        if DocpipeConstants.TEMP_CONTENT_COLUMN in table.column_names:
            # Reuse prefetched content only when using docling_library provider with no provider_config
            provider_config = self.text_extraction_config.get(OperatorConstants.Config.PROVIDER_CONFIG, {})
            can_reuse_prefetched_content = (
                self.text_extraction_mode == TextExtractionMode.DOCLING_LIBRARY and not provider_config
            )

            if can_reuse_prefetched_content:
                logger.info(
                    f"Reusing pre-fetched content from '{DocpipeConstants.TEMP_CONTENT_COLUMN}' for "
                    f"{self.text_extraction_mode.value} (no provider_config)"
                )

                column_names = list(table.column_names)
                temp_idx = column_names.index(DocpipeConstants.TEMP_CONTENT_COLUMN)
                column_names[temp_idx] = self.doc_column

                # Also rename _temp_pages_processed if present
                if DocpipeConstants.TEMP_PAGES_PROCESSED_COLUMN in table.column_names:
                    temp_pages_idx = column_names.index(DocpipeConstants.TEMP_PAGES_PROCESSED_COLUMN)
                    column_names[temp_pages_idx] = OperatorConstants.Columns.PAGES_PROCESSED
                    logger.info(
                        f"Renaming '{DocpipeConstants.TEMP_PAGES_PROCESSED_COLUMN}' to "
                        f"'{OperatorConstants.Columns.PAGES_PROCESSED}'"
                    )

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
                reason = []
                if self.text_extraction_mode != TextExtractionMode.DOCLING_LIBRARY:
                    reason.append(f"text_mode={self.text_extraction_mode.value}")
                if provider_config:
                    reason.append("provider_config is set")
                reason_str = ", ".join(reason) if reason else "unknown reason"

                logger.info(
                    f"Pre-fetched content found but not reusable ({reason_str}). "
                    f"Dropping temporary columns and performing fresh extraction."
                )
                # Drop both temp columns if present
                columns_to_drop = []
                if DocpipeConstants.TEMP_CONTENT_COLUMN in table.column_names:
                    columns_to_drop.append(DocpipeConstants.TEMP_CONTENT_COLUMN)
                if DocpipeConstants.TEMP_PAGES_PROCESSED_COLUMN in table.column_names:
                    columns_to_drop.append(DocpipeConstants.TEMP_PAGES_PROCESSED_COLUMN)

                if columns_to_drop:
                    table = table.drop(columns_to_drop)

        result_tables: list[pa.Table] = []
        text_metadata: dict[str, Any] = {}
        entity_metadata: dict[str, Any] | None = None

        try:
            # Step 1: Text extraction (skip if content was reused)
            if content_reused:
                # Content already present in doc_column, skip text extraction
                # But we still need to generate doc_hash_id if not present
                from docpipe.core.operators.functional.doc_id_hash import DocIdHashOperator

                if OperatorConstants.Columns.DOC_ID_HASH_DEFAULT not in table.column_names:
                    logger.info("Generating hash id for reused content")
                    hash_operator = DocIdHashOperator({OperatorConstants.Columns.DOC_COLUMN: self.doc_column})
                    table_list, _ = hash_operator.transform(table)
                    table = table_list[0]

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
                # Note: result_tables[0] already has failed docs removed by text extraction
                entity_base_metadata = self.create_base_metadata(total_docs_count=result_tables[0].num_rows)
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

    def validate(self, errors: list[str], warnings: list[str], available_features: list[str]) -> None:
        """Validate operator configuration against metadata.

        Args:
            errors: List to append validation errors
            warnings: List to append validation warnings
            available_features: List of available input features
        """
        super().validate(errors, warnings, available_features)

        # Get metadata and extract ATTRIBUTES for validation
        metadata = self.get_metadata()
        attributes = metadata.get(OperatorConstants.Config.ATTRIBUTES, {})

        # Validate configuration against metadata
        validate_config_from_metadata(config=self.config, attributes=attributes, errors=errors)

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
            OperatorConstants.Columns.CONTENT_DOCLANG: {
                OperatorConstants.Misc.NAME: "DocLang Content",
                OperatorConstants.Config.DESCRIPTION: "DocLang format of extracted content (optional, if 'doclang' in additional_formats)",
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
            OperatorConstants.Misc.SDK: True,
            OperatorConstants.Misc.CATEGORY: ExtractOperator.category.value,
            OperatorConstants.Misc.LABEL: "Document Extractor",
            OperatorConstants.Config.DESCRIPTION: "Extract text and entities from documents (PDF, DOCX, PPTX, images, audio, etc.) using Docling.",
            OperatorConstants.Config.FEATURES: metadata_features,
            OperatorConstants.Misc.IS_OPERATOR_AVAILABLE: ExtractOperator.is_available(),
            OperatorConstants.Config.ATTRIBUTES: {
                # Text extraction configuration (nested)
                OperatorConstants.Config.TEXT_EXTRACTION: {
                    OperatorConstants.Misc.NAME: "Text Extraction Configuration",
                    OperatorConstants.Config.DESCRIPTION: "Configuration for text extraction from documents",
                    OperatorConstants.Config.REQUIRED: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.JSON,
                    OperatorConstants.Config.PROPERTIES: {
                        OperatorConstants.Config.PROVIDER: {
                            OperatorConstants.Misc.NAME: "Text Extraction Provider",
                            OperatorConstants.Config.DESCRIPTION: (
                                f"Text extraction strategy: '{OperatorConstants.ExtractionModes.TEXT_MODE_DOCLING_LIBRARY}' (local Docling with optional VLM), "
                                f"or '{OperatorConstants.ExtractionModes.TEXT_MODE_DOCLING_SERVE}' (remote API)"
                            ),
                            OperatorConstants.Config.REQUIRED: True,
                            OperatorConstants.Config.DEFAULT: OperatorConstants.ExtractionModes.TEXT_MODE_DOCLING_LIBRARY,
                            OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                        },
                        OperatorConstants.Config.PROVIDER_CONFIG: {
                            OperatorConstants.Misc.NAME: "Provider Configuration",
                            OperatorConstants.Config.DESCRIPTION: "Provider-specific configuration for text extraction (docling_serve: base_url, api_key, timeout, etc.)",
                            OperatorConstants.Config.REQUIRED: False,
                            OperatorConstants.Misc.TYPE: AttributeDataTypes.JSON,
                            OperatorConstants.Config.PROPERTIES: {
                                OperatorConstants.Config.VLM_PIPELINE: {
                                    OperatorConstants.Misc.NAME: "VLM Pipeline Configuration",
                                    OperatorConstants.Config.DESCRIPTION: "Vision-Language Model pipeline configuration for enhanced extraction (docling_library provider only). Provide empty dict {} to enable with defaults, or omit to disable.",
                                    OperatorConstants.Config.REQUIRED: False,
                                    OperatorConstants.Misc.TYPE: AttributeDataTypes.JSON,
                                    OperatorConstants.Config.PROPERTIES: {
                                        OperatorConstants.Config.PRESET: {
                                            OperatorConstants.Misc.NAME: "VLM Preset",
                                            OperatorConstants.Config.DESCRIPTION: "VLM preset name (e.g., 'fast', 'granite_docling')",
                                            OperatorConstants.Config.REQUIRED: False,
                                            OperatorConstants.Config.DEFAULT: "fast",
                                            OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                                        },
                                        OperatorConstants.Config.ENGINE: {
                                            OperatorConstants.Misc.NAME: "VLM Engine",
                                            OperatorConstants.Config.DESCRIPTION: "VLM engine: 'transformers' (local), 'mlx' (macOS), 'ollama', or other API providers",
                                            OperatorConstants.Config.REQUIRED: False,
                                            OperatorConstants.Config.DEFAULT: "transformers",
                                            OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                                        },
                                        OperatorConstants.Config.ENGINE_OPTIONS: {
                                            OperatorConstants.Misc.NAME: "Engine Options",
                                            OperatorConstants.Config.DESCRIPTION: "Engine-specific configuration (api_base, model_id, api_key, etc.)",
                                            OperatorConstants.Config.REQUIRED: False,
                                            OperatorConstants.Config.DEFAULT: None,
                                            OperatorConstants.Misc.TYPE: AttributeDataTypes.JSON,
                                        },
                                    },
                                },
                                OperatorConstants.Config.ASR_PIPELINE: {
                                    OperatorConstants.Misc.NAME: "ASR Pipeline Configuration",
                                    OperatorConstants.Config.DESCRIPTION: "Automatic Speech Recognition pipeline configuration for audio/video extraction (docling_library provider only). Provide empty dict {} to enable with defaults, or omit to disable.",
                                    OperatorConstants.Config.REQUIRED: False,
                                    OperatorConstants.Misc.TYPE: AttributeDataTypes.JSON,
                                    OperatorConstants.Config.PROPERTIES: {
                                        OperatorConstants.Config.MODEL_ID: {
                                            OperatorConstants.Misc.NAME: "ASR Model Name",
                                            OperatorConstants.Config.DESCRIPTION: (
                                                "ASR model name (e.g., whisper_turbo, whisper_small, whisper_medium). "
                                                "Valid values: whisper_tiny, whisper_small, whisper_medium, whisper_base, "
                                                "whisper_large, whisper_turbo, and their _mlx/_native variants"
                                            ),
                                            OperatorConstants.Config.REQUIRED: False,
                                            OperatorConstants.Config.DEFAULT: OperatorConstants.Config.ASR_MODEL_DEFAULT,
                                            OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                                        },
                                    },
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
                            },
                        },
                        OperatorConstants.Columns.DOC_COLUMN: {
                            OperatorConstants.Misc.NAME: "Document Column",
                            OperatorConstants.Config.DESCRIPTION: "Name of the column to store extracted document content",
                            OperatorConstants.Config.REQUIRED: False,
                            OperatorConstants.Config.DEFAULT: OperatorConstants.Columns.DOC_COLUMN_DEFAULT,
                            OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                        },
                    },
                },
                # Entity extraction configuration (nested)
                OperatorConstants.Config.ENTITY_EXTRACTION: {
                    OperatorConstants.Misc.NAME: "Entity Extraction Configuration",
                    OperatorConstants.Config.DESCRIPTION: "Configuration for entity extraction from documents (optional)",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.JSON,
                    OperatorConstants.Config.PROPERTIES: {
                        OperatorConstants.Config.PROVIDER: {
                            OperatorConstants.Misc.NAME: "Entity Extraction Provider",
                            OperatorConstants.Config.DESCRIPTION: (
                                f"Entity extraction strategy: '{OperatorConstants.ExtractionModes.ENTITY_MODE_LITELLM}' (LiteLLM multi-provider), "
                                f"'{OperatorConstants.ExtractionModes.ENTITY_MODE_WATSONX}' (IBM watsonx), "
                                f"'{OperatorConstants.ExtractionModes.ENTITY_MODE_DOCLING}' (template-based), "
                                f"or '{OperatorConstants.ExtractionModes.ENTITY_MODE_NONE}' (no entity extraction)"
                            ),
                            OperatorConstants.Config.REQUIRED: True,
                            OperatorConstants.Config.DEFAULT: OperatorConstants.ExtractionModes.ENTITY_MODE_NONE,
                            OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                        },
                        OperatorConstants.Config.PROVIDER_CONFIG: {
                            OperatorConstants.Misc.NAME: "Provider Configuration",
                            OperatorConstants.Config.DESCRIPTION: "Provider-specific configuration for entity extraction (model_id, api_base, api_key, temperature, max_tokens, etc.)",
                            OperatorConstants.Config.REQUIRED: False,
                            OperatorConstants.Misc.TYPE: AttributeDataTypes.JSON,
                            OperatorConstants.Config.PROPERTIES: {
                                OperatorConstants.Config.MODEL_ID: {
                                    OperatorConstants.Misc.NAME: "Model ID",
                                    OperatorConstants.Config.DESCRIPTION: "LLM model identifier for entity extraction (e.g., 'ollama/llama3.2', 'openai/gpt-4')",
                                    OperatorConstants.Config.REQUIRED: False,
                                    OperatorConstants.Config.DEFAULT: "llama3.2",
                                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                                },
                                OperatorConstants.Config.API_BASE: {
                                    OperatorConstants.Misc.NAME: "API Base URL",
                                    OperatorConstants.Config.DESCRIPTION: "Base URL for the LLM API endpoint",
                                    OperatorConstants.Config.REQUIRED: False,
                                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                                },
                                OperatorConstants.Config.API_KEY: {
                                    OperatorConstants.Misc.NAME: "API Key",
                                    OperatorConstants.Config.DESCRIPTION: "API key for authentication (if required by provider)",
                                    OperatorConstants.Config.REQUIRED: False,
                                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                                },
                                OperatorConstants.LLM.TEMPERATURE: {
                                    OperatorConstants.Misc.NAME: "Temperature",
                                    OperatorConstants.Config.DESCRIPTION: "Sampling temperature for entity extraction LLM (0.0-1.0)",
                                    OperatorConstants.Config.REQUIRED: False,
                                    OperatorConstants.Config.DEFAULT: 0.0,
                                    OperatorConstants.Misc.TYPE: AttributeDataTypes.FLOAT,
                                },
                                OperatorConstants.LLM.MAX_TOKENS: {
                                    OperatorConstants.Misc.NAME: "Max Tokens",
                                    OperatorConstants.Config.DESCRIPTION: "Maximum tokens for entity extraction LLM response",
                                    OperatorConstants.Config.REQUIRED: False,
                                    OperatorConstants.Config.DEFAULT: 4096,
                                    OperatorConstants.Misc.TYPE: AttributeDataTypes.INTEGER,
                                },
                                DoclingClientConfigConstants.VLM_PIPELINE: {
                                    OperatorConstants.Misc.NAME: "VLM Pipeline",
                                    OperatorConstants.Config.DESCRIPTION: (
                                        "Custom VLM model configuration for Docling entity extraction (docling provider only). "
                                        "Requires model_type='inline' and inline_model with repo_id (HuggingFace model). "
                                        "Note: Only inline models supported; API models not supported by DocumentExtractor."
                                    ),
                                    OperatorConstants.Config.REQUIRED: False,
                                    OperatorConstants.Misc.TYPE: AttributeDataTypes.JSON,
                                },
                            },
                        },
                        OperatorConstants.Columns.OUTPUT_COLUMN: {
                            OperatorConstants.Misc.NAME: "Output Column",
                            OperatorConstants.Config.DESCRIPTION: "Name of the column to store extracted entities",
                            OperatorConstants.Config.REQUIRED: False,
                            OperatorConstants.Config.DEFAULT: OperatorConstants.Misc.ENTITIES,
                            OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                        },
                        OperatorConstants.ExtractionModes.ENTITY_MAX_DOC_CHARS: {
                            OperatorConstants.Misc.NAME: "Max Document Characters",
                            OperatorConstants.Config.DESCRIPTION: "Maximum characters to pass for entity extraction",
                            OperatorConstants.Config.REQUIRED: False,
                            OperatorConstants.Config.DEFAULT: 8000,
                            OperatorConstants.Misc.TYPE: AttributeDataTypes.INTEGER,
                        },
                        OperatorConstants.Config.CUSTOM_SCHEMA: {
                            OperatorConstants.Misc.NAME: "Custom Extraction Schema",
                            OperatorConstants.Config.DESCRIPTION: "Schema dictionary for structured entity extraction",
                            OperatorConstants.Config.REQUIRED: False,
                            OperatorConstants.Config.DEFAULT: None,
                            OperatorConstants.Misc.TYPE: AttributeDataTypes.JSON,
                        },
                        OperatorConstants.Config.EXPAND_EXTRACTED_DATA: {
                            OperatorConstants.Misc.NAME: "Expand Extracted Data",
                            OperatorConstants.Config.DESCRIPTION: "Whether to expand entity data JSON into individual columns",
                            OperatorConstants.Config.REQUIRED: False,
                            OperatorConstants.Config.DEFAULT: False,
                            OperatorConstants.Misc.TYPE: AttributeDataTypes.BOOLEAN,
                        },
                    },
                },
                # Performance configuration
                OperatorConstants.Config.MAX_WORKERS: {
                    OperatorConstants.Misc.NAME: "Max Workers",
                    OperatorConstants.Config.DESCRIPTION: "Maximum number of parallel workers for extraction (auto-detects based on CPU count if not specified)",
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
            },
        }
