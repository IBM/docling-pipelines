#!/usr/bin/env python3
"""
Utility functions for working with document class definitions.
Converts document class JSON schemas to Docling extraction templates.
"""

import json
import logging
from pathlib import Path
from typing import Any

from common.util.log import get_logger

logger: logging.Logger = get_logger()


class DocumentClassUtils:
    """Utilities for document class schema operations."""

    # Type mapping from target_tables column types to Docling template types
    TYPE_MAPPING = {
        "string": "string",
        "date": "string",  # Extract as string, parse later
        "decimal": "float",
        "float": "float",
        "long": "int",
        "int": "int",
        "integer": "int",
        "boolean": "boolean",
        "bool": "boolean",
    }

    @staticmethod
    def load_document_class(doc_class_path: str | Path) -> dict[str, Any]:
        """
        Load document class JSON from file.

        Args:
            doc_class_path: Path to document class JSON file

        Returns:
            Document class dictionary

        Raises:
            FileNotFoundError: If file doesn't exist
            json.JSONDecodeError: If file is not valid JSON
        """
        doc_class_path = Path(doc_class_path)
        if not doc_class_path.exists():
            raise FileNotFoundError(f"Document class file not found: {doc_class_path}")

        with open(doc_class_path, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _get_field_type_from_target_tables(
        field_path: list[str], target_tables: list[dict]
    ) -> str | None:
        """
        Get the type of a field from target_tables section.

        Args:
            field_path: Path to field (e.g., ["invoice_date"] or ["line_items", "amount"])
            target_tables: List of target table definitions

        Returns:
            Type string from target_tables or None if not found
        """
        for table in target_tables:
            for column in table.get("columns", []):
                # Get the source field path
                source = column.get("source", {})

                # Handle direct field reference
                if "field" in source:
                    source_field = source["field"]
                    if source_field == field_path:
                        return column.get("type")

                # Handle transform with field reference
                if "transform" in source:
                    transform = source["transform"]
                    for arg in transform.get("arguments", []):
                        if "value" in arg and "field" in arg["value"]:
                            source_field = arg["value"]["field"]
                            if source_field == field_path:
                                return column.get("type")

        return None

    @staticmethod
    def _build_template_from_fields(
        fields: list[dict], target_tables: list[dict], parent_path: list[str] | None = None
    ) -> dict[str, Any]:
        """
        Recursively build template from document fields.

        Args:
            fields: List of field definitions
            target_tables: Target tables for type lookup
            parent_path: Parent field path for nested fields

        Returns:
            Template dictionary
        """
        template = {}
        parent_path = parent_path or []

        for field in fields:
            field_name = field.get("name")
            if not field_name:
                continue

            # Build field path
            field_path = parent_path + [field_name]

            # Check if field has nested fields (like line_items)
            if "fields" in field:
                # For nested fields, create a nested template structure
                nested_template = DocumentClassUtils._build_template_from_fields(
                    fields=field["fields"],
                    target_tables=target_tables,
                    parent_path=field_path,
                )
                if nested_template:
                    template[field_name] = nested_template
            else:
                # Get type from target_tables
                field_type = DocumentClassUtils._get_field_type_from_target_tables(
                    field_path=field_path, target_tables=target_tables
                )

                # Map to Docling type
                if field_type:
                    docling_type = DocumentClassUtils.TYPE_MAPPING.get(
                        field_type.lower(), "string"
                    )
                    template[field_name] = docling_type
                else:
                    # Default to string if type not found
                    logger.warning(
                        f"Type not found for field {'.'.join(field_path)}, defaulting to string"
                    )
                    template[field_name] = "string"

        return template

    @staticmethod
    def generate_docling_template(
        doc_class_path: str | Path,
        include_nested: bool = True,
        max_fields: int | None = None,
    ) -> dict[str, Any]:
        """
        Generate Docling extraction template from document class JSON.

        Args:
            doc_class_path: Path to document class JSON file
            include_nested: Whether to include nested fields (like line_items)
            max_fields: Maximum number of top-level fields to include (None for all)

        Returns:
            Docling template dictionary with field names and types

        Example:
            >>> template = DocumentClassUtils.generate_docling_template(
            ...     "src/datasift_opensource/backend/common/document_classes/invoice.json"
            ... )
            >>> print(template)
            {
                "invoice_number": "string",
                "invoice_date": "string",
                "customer_name": "string",
                "sub_total": "float",
                "tax": "float",
                "total": "float",
                "line_items": {
                    "amount": "float",
                    "description": "string",
                    "quantity": "int"
                }
            }
        """
        # Load document class
        doc_class = DocumentClassUtils.load_document_class(doc_class_path)

        # Extract schema components
        schema = doc_class.get("document_class_schema", {})
        document = schema.get("document", {})
        fields = document.get("fields", [])
        target_tables = schema.get("target_tables", [])

        if not fields:
            logger.warning(f"No fields found in document class: {doc_class_path}")
            return {}

        if not target_tables:
            logger.warning(
                f"No target_tables found in document class: {doc_class_path}"
            )
            return {}

        # Build template
        template = DocumentClassUtils._build_template_from_fields(
            fields=fields, target_tables=target_tables
        )

        # Filter nested fields if requested
        if not include_nested:
            template = {
                k: v for k, v in template.items() if not isinstance(v, dict)
            }

        # Limit number of fields if requested
        if max_fields and len(template) > max_fields:
            logger.info(
                f"Limiting template to {max_fields} fields (from {len(template)})"
            )
            # Keep first max_fields items
            template = dict(list(template.items())[:max_fields])

        logger.info(
            f"Generated Docling template with {len(template)} fields from {Path(doc_class_path).name}"
        )

        return template

    @staticmethod
    def generate_template_with_examples(
        doc_class_path: str | Path, include_nested: bool = True
    ) -> dict[str, Any]:
        """
        Generate Docling template with examples included as comments.

        Args:
            doc_class_path: Path to document class JSON file
            include_nested: Whether to include nested fields

        Returns:
            Dictionary with template and examples metadata

        Example:
            >>> result = DocumentClassUtils.generate_template_with_examples(
            ...     "src/datasift_opensource/backend/common/document_classes/invoice.json"
            ... )
            >>> print(result["template"])
            {"invoice_number": "string", ...}
            >>> print(result["examples"])
            {"invoice_number": ["INV-2024-001"], ...}
        """
        # Load document class
        doc_class = DocumentClassUtils.load_document_class(doc_class_path)

        # Generate base template
        template = DocumentClassUtils.generate_docling_template(
            doc_class_path=doc_class_path, include_nested=include_nested
        )

        # Extract examples
        schema = doc_class.get("document_class_schema", {})
        document = schema.get("document", {})
        fields = document.get("fields", [])

        examples = {}
        descriptions = {}

        def extract_field_metadata(fields_list: list[dict], prefix: str = ""):
            """Recursively extract examples and descriptions."""
            for field in fields_list:
                field_name = field.get("name")
                if not field_name:
                    continue

                full_name = f"{prefix}{field_name}" if prefix else field_name

                if "fields" in field:
                    # Nested field
                    extract_field_metadata(field["fields"], f"{full_name}.")
                else:
                    # Regular field
                    if "examples" in field and field["examples"]:
                        examples[full_name] = field["examples"]
                    if "description" in field and field["description"]:
                        descriptions[full_name] = field["description"]

        extract_field_metadata(fields)

        return {
            "template": template,
            "examples": examples,
            "descriptions": descriptions,
            "document_type": document.get("document_type"),
            "document_description": document.get("document_description"),
        }

    @staticmethod
    def list_available_document_classes(
        doc_classes_dir: str | Path | None = None,
    ) -> list[dict[str, str]]:
        """
        List all available document class JSON files.

        Args:
            doc_classes_dir: Directory containing document class files
                           (defaults to common/document_classes)

        Returns:
            List of dictionaries with document class info
        """
        if doc_classes_dir is None:
            # Default to common/document_classes
            current_file = Path(__file__)
            doc_classes_dir = current_file.parent.parent / "document_classes"

        doc_classes_dir = Path(doc_classes_dir)

        if not doc_classes_dir.exists():
            logger.warning(f"Document classes directory not found: {doc_classes_dir}")
            return []

        result = []
        for json_file in doc_classes_dir.glob("*.json"):
            try:
                doc_class = DocumentClassUtils.load_document_class(json_file)
                result.append(
                    {
                        "file": str(json_file),
                        "name": doc_class.get("document_class_name", json_file.stem),
                        "id": doc_class.get("document_class_id", ""),
                        "description": doc_class.get("document_class_schema", {})
                        .get("document", {})
                        .get("document_description", ""),
                    }
                )
            except Exception as e:
                logger.warning(f"Error loading {json_file}: {e}")
                continue

        return sorted(result, key=lambda x: x["name"])


    @staticmethod
    def build_schema_description_from_fields(
        fields: list[dict[str, Any]], indent: int = 0
    ) -> str:
        """
        Build rich schema description from fields array format.

        Args:
            fields: List of field definitions with name, description, examples, etc.
            indent: Current indentation level for nested fields

        Returns:
            Human-readable schema description with examples
        """
        lines: list[str] = []
        prefix = "  " * indent

        for field in fields:
            name = field.get("name", "")
            description = field.get("description", "")
            examples = field.get("examples", [])
            nested_fields = field.get("fields", [])

            # Build field line with description
            if description:
                line = f"{prefix}- {name}: {description}"
            else:
                line = f"{prefix}- {name}"

            # Add examples if available
            if examples:
                if len(examples) == 1:
                    line += f" (e.g., '{examples[0]}')"
                else:
                    examples_str = "', '".join(
                        str(ex) for ex in examples[:3]
                    )  # Show up to 3 examples
                    line += f" (e.g., '{examples_str}')"

            lines.append(line)

            # Recursively handle nested fields
            if nested_fields:
                lines.append(f"{prefix}  Contains:")
                lines.append(
                    DocumentClassUtils.build_schema_description_from_fields(
                        nested_fields, indent + 2
                    )
                )

        return "\n".join(lines)

    @staticmethod
    def build_json_template_from_fields(fields: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Build JSON template from fields array format.

        Args:
            fields: List of field definitions

        Returns:
            Nested dictionary template matching the schema structure
        """
        template: dict[str, Any] = {}

        for field in fields:
            name = field.get("name", "")
            nested_fields = field.get("fields", [])

            if nested_fields:
                # This is a nested object or array
                nested_template = DocumentClassUtils.build_json_template_from_fields(
                    nested_fields
                )
                # Check if it's an array type (like line_items)
                if isinstance(nested_fields, list):
                    template[name] = [nested_template]
                else:
                    template[name] = nested_template
            else:
                # Leaf field - set to None as placeholder
                template[name] = None

        return template

    @staticmethod
    def get_document_types(doc_classes_dir: str | Path | None = None) -> dict[str, str]:
        """
        Load document types from all JSON files in document classes directory.

        Args:
            doc_classes_dir: Directory containing document class files
                           (defaults to common/document_classes)

        Returns:
            Dictionary mapping document_type to document_description
        """
        if doc_classes_dir is None:
            # Default to common/document_classes
            current_file = Path(__file__)
            doc_classes_dir = current_file.parent.parent / "document_classes"

        doc_classes_dir = Path(doc_classes_dir)
        document_types = {}

        try:
            if not doc_classes_dir.exists():
                logger.warning(f"Document classes path not found: {doc_classes_dir}")
                return {}

            # Read all .json files in the directory
            json_files = list(doc_classes_dir.glob("*.json"))
            logger.info(
                f"Found {len(json_files)} document class files in {doc_classes_dir}"
            )

            for json_file in json_files:
                try:
                    with open(json_file, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    # Extract document_type and document_description from the schema
                    doc_schema = data.get("document_class_schema", {}).get(
                        "document", {}
                    )
                    doc_type = doc_schema.get("document_type")
                    doc_description = doc_schema.get("document_description")

                    if doc_type and doc_description:
                        document_types[doc_type] = doc_description
                        logger.debug(
                            f"Loaded document type '{doc_type}' from {json_file.name}"
                        )
                    else:
                        logger.warning(
                            f"Skipping {json_file.name}: missing document_type or document_description"
                        )

                except (OSError, json.JSONDecodeError) as e:
                    logger.warning(f"Failed to load {json_file.name}: {str(e)}")
                    continue

            logger.info(f"Successfully loaded {len(document_types)} document types")
            return document_types

        except Exception as e:
            logger.error(f"Error loading document types: {str(e)}")
            return {}

    @staticmethod
    def get_schema_templates(
        document_types: list[str], doc_classes_dir: str | Path | None = None
    ) -> dict[str, dict]:
        """
        Load document class schemas for given document types.

        Args:
            document_types: List of document type names to load
            doc_classes_dir: Directory containing document class files
                           (defaults to common/document_classes)

        Returns:
            Dictionary mapping document_type to schema dict
        """
        import re

        if doc_classes_dir is None:
            # Default to common/document_classes
            current_file = Path(__file__)
            doc_classes_dir = current_file.parent.parent / "document_classes"

        doc_classes_dir = Path(doc_classes_dir)
        schema_templates: dict[str, dict] = {}

        def normalize_filename(name: str) -> str:
            """Normalize document type name to filename."""
            name = name.lower()
            name = re.sub(r"[^a-z0-9]+", "_", name)
            name = re.sub(r"_+", "_", name)
            return name.strip("_")

        for document_type in document_types:
            if not document_type or document_type in schema_templates:
                continue

            file_name = doc_classes_dir / f"{normalize_filename(document_type)}.json"
            try:
                with open(file_name, "r", encoding="utf-8") as f:
                    doc_cls = json.load(f)
                    doc_cls = doc_cls.get("document_class_schema", {}).get(
                        "document", {}
                    )
                    if doc_cls:
                        schema_templates[document_type] = doc_cls
                        logger.info(
                            f"Loaded schema for document type '{document_type}' from {file_name}"
                        )
                    else:
                        logger.warning(f"No valid schema found in {file_name}")
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning(
                    f"Failed to load schema for '{document_type}' from {file_name}: {exc}"
                )

        return schema_templates
