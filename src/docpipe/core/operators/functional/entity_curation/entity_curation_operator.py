"""
Entity Curation Operator for Open Source Docpipe.

Transforms extracted entities using document class schemas with field filtering,
type transformations, and nested structure handling.
"""

import json
from typing import Any

import pyarrow as pa
from data_processing.utils import TransformUtils

from docpipe.core.constants.constants import (
    AttributeDataTypes,
    DocpipeConstants,
    ExecutionStatus,
    Metrics,
)
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.abstract_operator import AbstractOperator, OperatorCategory
from docpipe.utils.infrastructure.logging import get_logger

from .schema_processor import SchemaProcessor

logger = get_logger(__name__)


class EntityCurationOperator(AbstractOperator):
    """
    Entity Curation Operator.

    Transforms extracted entities using document class schemas with:
    - Field filtering (only schema-defined fields)
    - Type transformations (uppercase, date parsing, currency conversion, etc.)
    - Nested structure handling (line items, etc.)

    Configuration:
        entities_column (str): Column containing extracted entities JSON (default: "entities")
        document_type_column (str): Column containing document type (default: "document_type")

    Input:
        PyArrow table with columns:
        - entities: JSON string or dict with extracted KVPs from ExtractOperator
        - document_type: Document type name (optional, for schema-based curation)

    Output:
        PyArrow table with additional column:
        - transformed_entities: JSON string containing curated entities
          * With schema: Structured entities per document class schema
          * Without schema: Empty dict (no curation applied)

    Example Flow:
        Ingest → Extract (with entity extraction) → EntityCuration → Embeddings → VectorDB

        Where Extract operator is configured with:
        - text_extraction.provider: "docling_library" or "docling_serve"
        - entity_extraction.provider: "ollama", "docling", or "litellm"
    """

    short_name: str = "entity_curation"
    category: OperatorCategory = OperatorCategory.Functional
    owner = DocpipeConstants.OWNER_DOCPIPE

    def __init__(self, config: dict[str, Any]) -> None:
        """
        Initialize Entity Curation operator.

        Args:
            config: Configuration dictionary
        """
        super().__init__(config)

        self.entities_column: str = config.get("entities_column", OperatorConstants.Misc.ENTITIES)
        self.document_type_column: str = config.get("document_type_column", OperatorConstants.Columns.DOCUMENT_TYPE)

        # Initialize schema processor
        self.schema_processor = SchemaProcessor()

        self.common_log_arguments: dict[str, Any] = {
            DocpipeConstants.JOB_ID: self.job_id,
            DocpipeConstants.JOB_RUN_ID: self.job_run_id,
            DocpipeConstants.CONTEXT_ID: self.context_id,
        }

    def validate(self, errors: list[str], warnings: list[str], available_features: list[str]) -> None:
        """Validate operator configuration."""
        super().validate(errors, warnings, available_features)

        if self.should_validate_field(field_value=self.entities_column):
            if self.entities_column not in available_features:
                errors.append(
                    f"Required column '{self.entities_column}' not found. "
                    "Run ExtractOperator with entity extraction enabled before this operator."
                )

        if self.should_validate_field(field_value=self.document_type_column):
            if self.document_type_column not in available_features:
                errors.append(
                    f"Required column '{self.document_type_column}' not found. "
                    "Ensure document_type column is available in the input data."
                )

    @staticmethod
    def get_required_features() -> list[str]:
        """Return required input features."""
        return [OperatorConstants.Misc.ENTITIES]

    def transform(
        self, table: pa.Table, file_name: str | None = None
    ) -> tuple[list[pa.Table], dict[str, Any]]:  # NOSONAR python:S3776
        """
        Transform extracted entities using schemas.

        Args:
            table: Input PyArrow table
            file_name: Optional file name

        Returns:
            Tuple of (output tables, metadata)
        """
        metadata: dict[str, Any] = self.create_base_metadata(total_docs_count=table.num_rows)

        if table.num_rows == 0:
            logger.warning("Empty table provided", extra=self.common_log_arguments)
            return [table], metadata

        # Check for document_type column
        has_document_type = self.document_type_column in table.column_names

        # Load schemas if document types available
        if has_document_type:
            document_types = table.column(self.document_type_column).to_pylist()
            unique_types = list({dt for dt in document_types if dt})

            if unique_types:
                logger.info(f"Loading schemas for document types: {unique_types}", extra=self.common_log_arguments)
                self.schema_processor.load_schemas(document_types=unique_types)

        # Process each document
        curated_entities: list[dict[str, Any]] = []

        for idx in range(table.num_rows):
            # Initialize doc_id and doc_name before try block
            doc_id = str(idx)
            doc_name = f"doc_{idx}"

            try:
                # Get row data
                row = {col: table.column(col)[idx].as_py() for col in table.column_names}

                doc_id = str(row.get(OperatorConstants.Columns.ID, idx))
                doc_name = str(row.get(OperatorConstants.Columns.NAME, f"doc_{idx}"))

                # Parse entities JSON
                entities_json = row.get(self.entities_column)

                # Log raw entities column value
                logger.info(
                    f"Document {doc_name}: entities_column='{self.entities_column}', "
                    f"entities_json type={type(entities_json).__name__}, "
                    f"entities_json value={str(entities_json)[:200] if entities_json else 'None'}",
                    extra=self.common_log_arguments,
                )

                if not entities_json:
                    self.record_skipped_document(
                        metadata=metadata,
                        doc_id=doc_id,
                        doc_name=doc_name,
                        reason=f"Column '{self.entities_column}' is empty",
                    )
                    curated_entities.append({})
                    continue

                # Handle both string and dict (Ollama returns dict)
                if isinstance(entities_json, str):
                    entities = json.loads(entities_json)
                else:
                    entities = entities_json

                # Log parsed entities
                logger.info(
                    f"Document {doc_name}: Parsed entities type={type(entities).__name__}, "
                    f"keys={list(entities.keys()) if isinstance(entities, dict) else 'not_dict'}, "
                    f"value={str(entities)[:300]}",
                    extra=self.common_log_arguments,
                )

                # Get document type
                document_type = row.get(self.document_type_column) if has_document_type else None

                # Log entities for debugging
                logger.info(
                    f"Processing document {doc_name}: document_type={document_type}, "
                    f"entities_keys={list(entities.keys()) if isinstance(entities, dict) else 'not_dict'}",
                    extra=self.common_log_arguments,
                )

                # Process entities with schema (always structured format)
                if document_type:
                    curated = self.schema_processor.process_with_schema(entities=entities, document_type=document_type)
                else:
                    # No document type - return empty dict
                    curated = {}

                logger.info(
                    f"Curated entities for document {doc_name}: {list(curated.keys()) if curated else 'empty'}",
                    extra=self.common_log_arguments,
                )

                curated_entities.append(curated)
                metadata[Metrics.External.PROCESSED_DOCS] += 1

            except Exception as exc:
                logger.error(
                    f"Error processing document {doc_name}: {exc}", exc_info=True, extra=self.common_log_arguments
                )
                self.record_failed_document(metadata=metadata, doc_id=doc_id, doc_name=doc_name, reason=str(exc))
                curated_entities.append({})

        # Add transformed_entities column as JSON
        transformed_rows_json = [json.dumps(row) if row is not None else None for row in curated_entities]
        table = TransformUtils.add_column(
            table=table, name=OperatorConstants.Columns.TRANSFORMED_ENTITIES_COLUMN_NAME, content=transformed_rows_json
        )

        # Set final status
        if metadata.get(Metrics.External.FAILED_DOCS_COUNT, 0) > 0:
            metadata[Metrics.External.NODE_STATUS] = ExecutionStatus.COMPLETED_WITH_ERRORS
        else:
            metadata[Metrics.External.NODE_STATUS] = ExecutionStatus.COMPLETED

        return [table], metadata

    @staticmethod
    def get_metadata() -> dict[str, Any]:
        """Return operator metadata for UI."""
        return {
            OperatorConstants.Misc.SHORT_NAME: EntityCurationOperator.short_name,
            OperatorConstants.Misc.CATEGORY: EntityCurationOperator.category.value,
            OperatorConstants.Misc.SDK: True,
            OperatorConstants.Misc.LABEL: "Entity Curation",
            OperatorConstants.Config.DESCRIPTION: (
                "Transforms extracted entities using document class schemas. "
                "Applies field filtering, type transformations, and handles nested structures."
            ),
            OperatorConstants.Misc.IS_OPERATOR_AVAILABLE: EntityCurationOperator.is_available(),
            OperatorConstants.Config.FEATURES: {},
            OperatorConstants.Config.ATTRIBUTES: {
                "entities_column": {
                    OperatorConstants.Misc.NAME: "Entities Column",
                    OperatorConstants.Config.DESCRIPTION: "Column containing extracted entities JSON",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: OperatorConstants.Misc.ENTITIES,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                "document_type_column": {
                    OperatorConstants.Misc.NAME: "Document Type Column",
                    OperatorConstants.Config.DESCRIPTION: "Column containing document type",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: OperatorConstants.Columns.DOCUMENT_TYPE,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
            },
        }
