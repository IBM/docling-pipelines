"""Entity extraction port interface.

This module defines the port interface for entity extraction operations following
hexagonal architecture principles. The port contains the parallel processing
orchestration logic, while adapters implement the specific extraction mechanics.
"""

import json
import logging
from abc import ABC, abstractmethod
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from typing import Any

import pyarrow as pa

from common.constants.constants import ExecutionStatus, Metrics
from common.constants.operator_constants import OperatorConstants
from common.util.data.transform import TransformUtils
from common.util.document_class_utils import DocumentClassUtils
from common.util.infrastructure.logging import get_logger
from core.operators.abstract_operator import AbstractOperator
from core.operators.functional.doc_id_hash import DocIdHashOperator

logger: logging.Logger = get_logger()


class EntityExtractionPort(ABC):
    """Port interface for entity extraction with parallel processing orchestration.

    The port acts as an orchestrator that manages:
    - Parallel processing framework (executor management)
    - Worker task submission and result fetching
    - Result aggregation and error handling
    - Progress tracking and metadata collection

    Adapters implement the specific extraction logic via the extract_entities_single
    method, which is called by the port's parallel processing framework.

    Design Philosophy:
        Port = Orchestration + Parallel Processing
        Adapter = Specific Extraction Logic

    Attributes:
        ADAPTER_NAME: Short identifier for the adapter (e.g., "ollama", "docling", "litellm")
        ADAPTER_DISPLAY_NAME: Human-readable adapter name (e.g., "Ollama", "Docling", "LiteLLM")
        max_workers: Number of parallel workers for processing
        doc_column: Column name containing document text
        output_column: Column name for storing extracted entities
        expand_extracted_data: Whether to expand entities into individual columns
    """

    ADAPTER_NAME: str = "base"
    ADAPTER_DISPLAY_NAME: str = "Base Adapter"

    def __init__(self, *, config: dict[str, Any]) -> None:
        """Initialize the entity extraction port with configuration.

        Args:
            config: Configuration dictionary containing:
                - max_workers: Number of parallel workers (default: 4)
                - doc_column: Column name for document text (default: "doc_content")
                - output_column: Column name for entities (default: "entities")
                - expand_extracted_data: Expand entities into columns (default: False)
                - Additional adapter-specific configuration
        """
        self.max_workers = config.get(OperatorConstants.Config.MAX_WORKERS, 4)
        self.doc_column = config.get(OperatorConstants.Columns.DOC_COLUMN, OperatorConstants.Columns.DOC_COLUMN_DEFAULT)
        self.output_column = config.get(OperatorConstants.Columns.OUTPUT_COLUMN, OperatorConstants.Misc.ENTITIES)
        self.expand_extracted_data = config.get(OperatorConstants.Config.EXPAND_EXTRACTED_DATA, False)
        self.doc_id_hash_column = config.get(
            OperatorConstants.Columns.DOC_ID_HASH, OperatorConstants.Columns.DOC_ID_HASH_DEFAULT
        )
        self.custom_schema = config.get(OperatorConstants.Config.CUSTOM_SCHEMA, {})
        self.common_log_arguments = config.get("common_log_arguments", {})
        # Validate configuration before initializing adapter-specific config
        self.validate(config=config)
        # Subclasses should initialize their adapter-specific configuration
        self._init_adapter_config(config=config)

    def validate(self, *, config: dict[str, Any]) -> None:
        """Validate adapter configuration.

        Subclasses should override this method to implement adapter-specific
        validation logic. The base implementation does nothing.

        Args:
            config: Full configuration dictionary

        Raises:
            ValueError: If configuration is invalid
        """
        # Validate boolean flags if present
        expand_extracted_data = config.get(OperatorConstants.Config.EXPAND_EXTRACTED_DATA)
        if expand_extracted_data is not None and not isinstance(expand_extracted_data, bool):
            raise ValueError("Entity extraction 'expand_extracted_data' must be a boolean")

    def _init_adapter_config(self, *, config: dict[str, Any]) -> None:
        """Initialize adapter-specific configuration.

        Subclasses should override this method to set up their specific configuration
        parameters (e.g., Ollama model settings, template configuration).

        Args:
            config: Full configuration dictionary
        """
        pass

    def _prepare_document_tasks(
        self, table: pa.Table, document_types: list[str], metadata: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Prepare document tasks for parallel processing.

        This method iterates through the table rows and creates a list of task
        dictionaries containing document information needed for entity extraction.
        Documents with empty content are skipped and recorded in metadata.

        Args:
            table: PyArrow table containing document data
            document_types: List of document types corresponding to table rows
            metadata: Metadata dictionary for recording skipped documents

        Returns:
            List of task dictionaries, each containing:
                - idx: Row index in the table
                - doc_id: Document identifier
                - doc_name: Document name
                - content: Document content from self.doc_column
                - document_type: Document type (if available)
        """
        doc_tasks: list[dict[str, Any]] = []

        for row_idx in range(table.num_rows):
            row = {col: table.column(col)[row_idx].as_py() for col in table.column_names}
            doc_id_value = row.get(OperatorConstants.Columns.ID)
            if doc_id_value is None:
                doc_id_value = row.get(OperatorConstants.Columns.PATH, f"doc_{row_idx}")
            doc_id = str(doc_id_value)
            doc_name = str(row.get(OperatorConstants.Columns.NAME, f"doc_{row_idx}"))
            content = row.get(self.doc_column) or ""

            if not content:
                AbstractOperator.record_skipped_document(
                    metadata=metadata,
                    doc_id=doc_id,
                    doc_name=doc_name,
                    reason=f"Column '{self.doc_column}' is empty or missing.",
                )
                continue

            doc_tasks.append(
                {
                    "idx": row_idx,
                    "doc_id": doc_id,
                    "doc_name": doc_name,
                    "content": content,
                    "document_type": document_types[row_idx] if document_types else None,
                }
            )

        return doc_tasks

    def transform(self, *, table: pa.Table, metadata: dict[str, Any]) -> tuple[list[pa.Table], dict[str, Any]]:
        """Orchestrate parallel entity extraction across documents.

        This method implements the parallel processing pattern:
        1. Validate input and prepare document tasks
        2. Load schemas/templates if using schema-based extraction
        3. Create ThreadPoolExecutor for parallel processing
        4. Submit tasks to workers via _submit_extraction_task
        5. Collect results using as_completed pattern
        6. Aggregate results and handle errors
        7. Add extracted entities to table
        8. Optionally expand entities into individual columns
        9. Generate document hash IDs
        10. Return transformed table with metadata

        Args:
            table: PyArrow table with document information containing columns:
                - id: Document ID
                - name: Document name/filename
                - doc_content: Document text content
                - document_type: Document type for schema selection (optional)
            metadata: Optional metadata dictionary to update

        Returns:
            Tuple of (list of transformed tables, metadata dictionary)
        """
        # Prepare schemas and document tasks
        document_types, schema_templates = self._prepare_schemas(table=table)
        doc_tasks = self._prepare_document_tasks(table, document_types, metadata)
        entities_list: list[dict[str, Any]] = [{}] * table.num_rows
        content_list: dict[str, Any] = {}

        logger.info(
            "Processing %s documents in parallel with %s workers using %s",
            len(doc_tasks),
            self.max_workers,
            self.ADAPTER_DISPLAY_NAME,
        )

        # Process documents in parallel and collect results
        self._process_documents_parallel(doc_tasks, schema_templates, entities_list, metadata, content_list)

        # Add entities to table and finalize
        table = self._finalize_table(table=table, entities_list=entities_list, content_list=content_list)
        metadata = self._set_execution_status(metadata=metadata)

        return [table], metadata

    def _prepare_schemas(self, *, table: pa.Table) -> tuple[list[str], dict[str, dict]]:
        """Prepare document types and load schema templates.

        Args:
            table: PyArrow table containing document data

        Returns:
            Tuple of (document_types list, schema_templates dict)
        """
        document_types: list[str] = []
        schema_templates: dict[str, dict] = {}

        if OperatorConstants.Columns.DOCUMENT_TYPE in table.column_names:
            document_types = table.column(OperatorConstants.Columns.DOCUMENT_TYPE).to_pylist()
            self._load_schema_templates(document_types=document_types, schema_templates=schema_templates)
            if not schema_templates:
                logger.warning("No schemas could be loaded from document_type column, using default schema")

        return document_types, schema_templates

    def _process_documents_parallel(
        self,
        doc_tasks: list[dict[str, Any]],
        schema_templates: dict[str, dict],
        entities_list: list[dict[str, Any]],
        metadata: dict[str, Any],
        content_list: dict[str, Any] | None = None,
    ) -> None:
        """Process documents in parallel using ThreadPoolExecutor.

        Args:
            doc_tasks: List of document task dictionaries
            schema_templates: Cache of loaded schemas by document type
            entities_list: List to populate with extracted entities
            metadata: Metadata dictionary for tracking results
            content_list: Dictionary to populate with extracted content
        """

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_task: dict[Future, dict[str, Any]] = {}

            # Submit all tasks
            for task in doc_tasks:
                future = self._submit_extraction_task(executor=executor, task=task, schema_templates=schema_templates)
                future_to_task[future] = task

            # Collect results as they complete
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                self._handle_extraction_result(future, task, entities_list, metadata, content_list)

    def _handle_extraction_result(
        self,
        future: Future,
        task: dict[str, Any],
        entities_list: list[dict[str, Any]],
        metadata: dict[str, Any],
        content_list: dict[str, Any] | None = None,
    ) -> None:
        """Handle the result of a single extraction task.

        Args:
            future: Future object containing extraction result
            task: Task dictionary with document information
            entities_list: List to populate with extracted entities
            metadata: Metadata dictionary for tracking results
            content_list: Dictionary to populate with extracted content
        """
        idx = task["idx"]

        try:
            result = future.result()

            if result[OperatorConstants.Extraction.SUCCESS]:
                entities_list[idx] = result[OperatorConstants.Misc.ENTITIES]
                if content_list is not None and result.get(OperatorConstants.Columns.DOC_COLUMN, None):
                    content_list[idx] = result[OperatorConstants.Columns.DOC_COLUMN]
                # Increment processed count
                metadata[Metrics.External.PROCESSED_DOCS] += 1
                return

            # Handle extraction failure
            self._record_extraction_failure(task=task, error=result.get("error", "Unknown error"), metadata=metadata)

        except Exception as e:
            logger.error("Error processing document at index %s: %s", idx, e)
            self._record_extraction_failure(task=task, error=str(e), metadata=metadata)

    def _record_extraction_failure(self, *, task: dict[str, Any], error: str, metadata: dict[str, Any]) -> None:
        """Record a failed extraction in metadata.

        Args:
            task: Task dictionary with document information
            error: Error message describing the failure
            metadata: Metadata dictionary for tracking results
        """
        AbstractOperator.record_failed_document(
            metadata=metadata, doc_id=task["doc_id"], doc_name=task["doc_name"], reason=error
        )
        logger.error("Failed to extract entities from %s: %s", task["doc_name"], error)

    def _finalize_table(
        self, *, table: pa.Table, entities_list: list[dict[str, Any]], content_list: dict[str, Any] | None = None
    ) -> pa.Table:
        """Add entities column and hash IDs to table.

        Args:
            table: PyArrow table to finalize
            entities_list: List of extracted entities

        Returns:
            Finalized PyArrow table with entities and hash columns
        """
        # Optionally expand entities into individual columns
        if self.expand_extracted_data and entities_list:
            table = self._expand_entities_columns(table=table, entities_list=entities_list)

        # check table doesn't already have content column then add it
        if self.doc_column not in table.column_names:
            content_col_list: list[str] = [""] * table.num_rows
            if content_list:
                for idx_key, content in content_list.items():
                    content_col_list[int(idx_key)] = content
            table = TransformUtils.add_column(table=table, name=self.doc_column, content=content_col_list)

        # Add entities column - convert to JSON strings for PyArrow compatibility
        entities_json_list: list[str] = [json.dumps(entity) if entity else "{}" for entity in entities_list]
        table = TransformUtils.add_column(table=table, name=self.output_column, content=entities_json_list)

        # Ensure doc_id_hash column exists
        if self.doc_id_hash_column not in table.column_names:
            logger.info("Generating hash id and adding it to table")
            hash_operator = DocIdHashOperator(
                {
                    OperatorConstants.Columns.DOC_COLUMN: self.doc_column,
                    OperatorConstants.Columns.DOC_ID_HASH: self.doc_id_hash_column,
                }
            )
            table_list, _ = hash_operator.transform(table)
            table = table_list[0]

        return table

    def _set_execution_status(self, *, metadata: dict[str, Any]) -> dict[str, Any]:
        """Determine and set the final execution status in metadata.

        Args:
            metadata: Metadata dictionary to update

        Returns:
            Updated metadata dictionary
        """
        execution_status = ExecutionStatus.COMPLETED.value

        # Check failed docs first (higher priority)
        if metadata[Metrics.External.FAILED_DOCS_COUNT] > 0:
            execution_status = ExecutionStatus.COMPLETED_WITH_ERRORS.value
        elif metadata[Metrics.External.SKIPPED_DOCS_COUNT] > 0:
            execution_status = ExecutionStatus.COMPLETED_WITH_WARNINGS.value

        metadata[Metrics.External.NODE_STATUS] = execution_status
        return metadata

    def _submit_extraction_task(
        self, executor: ThreadPoolExecutor, task: dict[str, Any], schema_templates: dict[str, dict]
    ) -> Future:
        """Submit extraction task to executor.

        This method determines the appropriate schema (if using schema-based extraction)
        and submits the task to the executor by calling the adapter's extract_entities_single
        method.

        Args:
            executor: ThreadPoolExecutor instance
            task: Document task dictionary containing:
                - idx: Task index
                - doc_id: Document ID
                - doc_name: Document name
                - content: Document text content
                - document_type: Document type for schema selection
            schema_templates: Cache of loaded schemas by document type

        Returns:
            Future object for result retrieval
        """
        # Determine schema if using schema-based extraction
        schema_to_use = self.custom_schema
        if schema_templates:
            doc_type = task.get("document_type")
            if doc_type and doc_type in schema_templates:
                schema_to_use = schema_templates[doc_type]
                logger.debug("Using schema for document type '%s' for %s", doc_type, task["doc_name"])
        content = task.get("content", task.get("binary_content", b""))
        return executor.submit(
            self.extract_entities_single,
            doc_id=task["doc_id"],
            doc_name=task["doc_name"],
            content=content,
            schema=schema_to_use,
        )
        # Submit task to executor

    @abstractmethod
    def extract_entities_single(
        self, *, doc_id: str, doc_name: str, content: str | bytes, schema: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Extract entities from a single document.

        This is the adapter-specific extraction logic that runs in parallel workers.
        Each adapter implements its own extraction mechanics here.

        Args:
            doc_id: Document identifier
            doc_name: Document name for logging
            content: Document text content
            schema: Optional schema dictionary for structured extraction
            **kwargs: Adapter-specific parameters

        Returns:
            Dictionary with extraction results:
            {
                "success": bool,              # Extraction success indicator
                "entities": dict,             # Extracted entities as dictionary
                "error": str | None           # Error message if failed
            }
        """
        pass

    def validate_loaded_schemas(self, *, document_types: list[str], schema_templates: dict[str, dict]) -> None:
        """Validate which schemas were successfully loaded

        Args:
            document_types: List of document types to load schemas for
            schema_templates: Dictionary to populate with loaded schemas
        """
        unique_doc_types = {dt for dt in document_types if dt}
        missing_schemas = unique_doc_types - set(schema_templates.keys())
        if missing_schemas:
            logger.warning(
                "Could not load schemas for document types: %s. These documents will use the default schema instead.",
                missing_schemas,
            )
        if schema_templates:
            logger.info("Successfully loaded schemas for: %s", list(schema_templates.keys()))

    def _load_schema_templates(self, *, document_types: list[str], schema_templates: dict[str, dict]) -> None:
        """Load schema templates for given document types.

        Args:
            document_types: List of document types to load schemas for
            schema_templates: Dictionary to populate with loaded schemas
        """
        loaded_schemas = DocumentClassUtils.get_schema_templates(document_types)
        schema_templates.update(loaded_schemas)

    def _expand_entities_columns(self, *, table: pa.Table, entities_list: list[dict[str, Any]]) -> pa.Table:
        """Expand entity dict into individual columns, one per entity key.

        Args:
            table: PyArrow table to add columns to
            entities_list: List of entity dictionaries

        Returns:
            PyArrow table with expanded entity columns
        """
        # Collect all unique keys
        all_keys: set[str] = set()
        for entity in entities_list:
            if entity and isinstance(entity, dict):
                all_keys.update(entity.keys())

        if not all_keys:
            return table

        logger.info("Expanding entities into %s columns: %s", len(all_keys), sorted(all_keys))

        # Create one column per key
        for key in sorted(all_keys):
            column_values = [
                (entity[key] if (entity and isinstance(entity, dict) and key in entity) else None)
                for entity in entities_list
            ]
            # Convert values to strings for PyArrow compatibility
            column_values = [str(val) if val is not None else None for val in column_values]
            table = TransformUtils.add_column(table, name=f"entity_{key}", content=column_values)

        return table

    # ========================================================================
    # LLM-Based Entity Extraction Helper Methods
    # ========================================================================
    # These methods provide common utilities for LLM-based entity extraction
    # adapters (Ollama, LiteLLM, etc.). They handle prompt building, schema
    # processing, and JSON parsing with repair logic.
    # ========================================================================

    def _build_schema_prompt(self, *, content: str, schema: dict[str, Any]) -> str:
        """Build prompt for schema-based extraction.

        Args:
            content: Document text content
            schema: Schema dictionary with fields/columns

        Returns:
            Formatted user prompt string
        """
        # Extract schema metadata
        schema_name = schema.get("document_type", "") or schema.get("table", "")
        schema_desc_text = schema.get("document_description", "") or schema.get("description", "")

        # Build schema description using helper functions
        schema_desc = self._build_schema_description(schema=schema)

        # Build JSON template
        json_template = self._build_json_template(schema=schema)

        return (
            f"Extract entities from the following document text.\n\n"
            f"Document Type: {schema_name}\n"
            f"Description: {schema_desc_text}\n\n"
            f"Schema fields to extract:\n{schema_desc}\n\n"
            f"Return your answer as a JSON object matching this template exactly:\n"
            f"{json.dumps(json_template, indent=2)}\n\n"
            f"Document text:\n{content}"
        )

    def _build_schema_description(self, *, schema: dict[str, Any]) -> str:
        """Build human-readable schema description.

        Args:
            schema: Schema dictionary

        Returns:
            Formatted schema description
        """
        # Check for new 'fields' format first
        if "fields" in schema:
            return DocumentClassUtils.build_schema_description_from_fields(schema["fields"])

        # Fall back to old 'columns' format
        columns = schema.get("columns", {})
        if not columns:
            return ""

        lines: list[str] = []
        for col_name, col_type in columns.items():
            lines.append(f"  - {col_name} ({col_type})")

        return "\n".join(lines)

    def _build_json_template(self, *, schema: dict[str, Any]) -> dict[str, Any]:
        """Build JSON template from schema.

        Args:
            schema: Schema dictionary

        Returns:
            JSON template dictionary
        """
        # Check for new 'fields' format first
        if "fields" in schema:
            return DocumentClassUtils.build_json_template_from_fields(schema["fields"])

        # Fall back to old 'columns' format
        columns = schema.get("columns", {})
        if not columns:
            return {}

        template: dict[str, Any] = {}
        for col_name in columns.keys():
            if "." in col_name:
                # Build nested structure
                parts = col_name.split(".")
                current = template
                for part in parts[:-1]:
                    if part not in current:
                        current[part] = {}
                    current = current[part]
                current[parts[-1]] = None
            else:
                template[col_name] = None

        return template

    def _build_schema_free_prompt(self, *, content: str) -> str:
        """Build prompt for schema-free extraction.

        Args:
            content: Document text content

        Returns:
            Formatted user prompt string
        """
        return (
            f"Extract all named entities and key information from the following document text.\n\n"
            f"Document text:\n{content}"
        )

    def _parse_llm_json(self, *, raw_response: str) -> dict[str, Any]:
        """Parse JSON from LLM response with repair logic.

        Args:
            raw_response: Raw LLM response text

        Returns:
            Parsed JSON dictionary (empty dict if parsing fails)
        """
        import re

        text = raw_response.strip()

        # Strip markdown fences
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:]).strip()

        # Direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Regex extraction of first {...} block
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                repaired = self._try_repair_truncated_json(raw=match.group())
                if repaired is not None:
                    return repaired

        # Last-resort repair
        repaired = self._try_repair_truncated_json(raw=text)
        if repaired is not None:
            return repaired

        logger.warning("Failed to parse LLM response as JSON, returning empty dict")
        return {}

    def _try_repair_truncated_json(self, *, raw: str) -> dict[str, Any] | None:
        """Try to repair truncated JSON by closing unclosed braces/brackets.

        Args:
            raw: Raw JSON string (potentially truncated)

        Returns:
            Parsed JSON dictionary or None if repair fails
        """
        stack: list[str] = []
        in_string = False
        escape_next = False

        for char in raw:
            if escape_next:
                escape_next = False
                continue
            if char == "\\" and in_string:
                escape_next = True
                continue
            if char == '"':
                in_string = not in_string
                continue
            if not in_string:
                if char in "{[":
                    stack.append("}" if char == "{" else "]")
                elif char in "}]":
                    if stack and stack[-1] == char:
                        stack.pop()

        closing = "".join(reversed(stack))
        repaired = raw.rstrip() + closing

        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            return None
