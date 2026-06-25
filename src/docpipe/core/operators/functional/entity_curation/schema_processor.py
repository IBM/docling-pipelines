"""
Schema-based processing for entity curation.

This module handles the transformation of extracted entities using document class schemas.
It applies field filtering, type transformations, and handles nested structures.
"""

import json
from pathlib import Path
from typing import Any

from docpipe.core.constants.constants import DocpipeConstants, DocumentConstants
from docpipe.utils.document_class_utils import DocumentClassUtils
from docpipe.utils.infrastructure.logging import get_logger

from .transforms import TRANSFORMS

logger = get_logger(__name__)


class SchemaProcessor:
    """Processes entities based on document class schemas."""

    def __init__(self):
        """Initialize the schema processor with an empty cache."""
        self.schema_cache: dict[str, dict] = {}

    def load_schemas(self, *, document_types: list[str]) -> None:
        """
        Load full schemas (with target_tables) for document types from file system.

        Args:
            document_types: List of document type names
        """
        # Load full schemas with target_tables for entity curation
        doc_classes_dir = Path(DocpipeConstants.DOCUMENT_CLASSES_PATH)

        for document_type in document_types:
            if not document_type or document_type in self.schema_cache:
                continue

            file_name = doc_classes_dir / f"{DocumentClassUtils.normalize_filename(document_type)}.json"
            try:
                with open(file_name, encoding="utf-8") as f:
                    doc_cls = json.load(f)
                    # Get the full document_class_schema (includes both document and target_tables)
                    doc_cls_schema = doc_cls.get("document_class_schema", {})
                    if doc_cls_schema:
                        self.schema_cache[document_type] = doc_cls_schema
                        logger.info(f"Loaded schema for document type '{document_type}' from {file_name}")
                    else:
                        logger.warning(f"No valid schema found in {file_name}")
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning(f"Failed to load schema for '{document_type}' from {file_name}: {exc}")

        logger.info(f"Loaded {len(self.schema_cache)} schemas: {list(self.schema_cache.keys())}")

    def process_with_schema(self, *, entities: dict[str, Any], document_type: str) -> dict[str, Any]:
        """
        Process entities using document class schema.

        Args:
            entities: Extracted entities dictionary
            document_type: Document type name

        Returns:
            Curated entities with transformations applied
        """
        schema = self.schema_cache.get(document_type)
        if not schema:
            logger.warning(f"No schema found for document type '{document_type}', returning empty dict")
            return {}

        # Get target tables from schema
        target_tables = schema.get(DocumentConstants.TARGET_TABLES, [])
        if not target_tables:
            logger.warning(f"No target tables in schema for '{document_type}'")
            return {}

        # Process each target table
        result = {}
        for table in target_tables:
            table_name = table.get(DocumentConstants.TABLE_NAME)
            columns = table.get(DocumentConstants.COLUMNS, [])

            logger.debug(f"Processing table '{table_name}' with {len(columns)} columns")

            # Create nested structure for table
            table_result = {}
            for column in columns:
                col_name = column.get(DocumentConstants.COLUMN_NAME)
                source = column.get(DocumentConstants.SOURCE, {})

                # Handle direct field reference
                if DocumentConstants.FIELD in source:
                    field_path = source[DocumentConstants.FIELD]
                    value = self._get_nested_value(obj=entities, path=field_path)
                    table_result[col_name] = value

                # Handle transformation
                elif DocumentConstants.TRANSFORM in source:
                    transform = source[DocumentConstants.TRANSFORM]
                    transform_name = transform.get(DocumentConstants.TRANSFORM_NAME)
                    arguments = transform.get(DocumentConstants.ARGUMENTS, [])

                    value = self._apply_transformation(
                        transform_name=transform_name, arguments=arguments, entities=entities
                    )
                    table_result[col_name] = value

            # Add table to result
            if table_name:
                result[table_name] = table_result

        return result

    def _apply_transformation(
        self, *, transform_name: str, arguments: list[dict[str, Any]], entities: dict[str, Any]
    ) -> Any:
        """
        Apply a transformation function with arguments.

        Args:
            transform_name: Name of the transformation function
            arguments: List of argument definitions from schema
            entities: Extracted entities dictionary

        Returns:
            Transformed value or None if transformation fails
        """
        func = TRANSFORMS.get(transform_name)
        if not func:
            logger.warning(f"Unknown transformation: {transform_name}")
            return None

        # Extract argument values from entities
        kwargs = {}
        for arg in arguments:
            arg_name = arg.get(DocumentConstants.ARG_NAME)
            arg_value = arg.get(DocumentConstants.ARG_VALUE, {})

            # Ensure arg_name is a string
            if not isinstance(arg_name, str):
                logger.warning(f"Invalid argument name type: {type(arg_name)}")
                continue

            if DocumentConstants.FIELD in arg_value:
                field_path = arg_value[DocumentConstants.FIELD]
                value = self._get_nested_value(obj=entities, path=field_path)
                kwargs[arg_name] = value
            else:
                kwargs[arg_name] = arg_value

        try:
            return func(**kwargs)
        except Exception as e:
            logger.warning(f"Transformation {transform_name} failed: {e}")
            return None

    @staticmethod
    def _get_nested_value(*, obj: dict, path: list[str]) -> Any:
        """
        Get value from nested dictionary using path.

        Args:
            obj: Dictionary to traverse
            path: List of keys representing the path

        Returns:
            Value at the path or None if not found
        """
        value: Any = obj
        for key in path:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None
        return value
