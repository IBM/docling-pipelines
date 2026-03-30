# Copyright IBM Corp. 2025
# SPDX-License-Identifier: Apache-2.0

"""
Entity Extraction Operator using Ollama LLM.

Extracts structured entities from document text using a locally running
Ollama model, guided by a user-provided schema template.
"""

from __future__ import annotations

import json
import re
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from typing import Any

import pyarrow as pa

from common.constants.constants import (
    AttributeDataTypes,
    DatasiftConstants,
    ExecutionStatus,
    Metrics,
)
from common.constants.operator_constants import OperatorConstants
from common.util.infrastructure.logging import get_logger

# Import TransformUtils from centralized location
from common.util.data.transform import TransformUtils
from core.operators.abstract_operator import AbstractOperator, OperatorCategory
from core.operators.functional.doc_id_hash import DocIdHashOperator

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a precise document entity extraction assistant.
Your task is to extract structured information from document text and return it \
as valid JSON that exactly matches the provided schema template.

Rules:
1. Return ONLY a valid JSON object — no markdown fences, no explanation text.
2. Use null for any field that cannot be found in the document.
3. For NESTED fields, return a list of objects.
4. Do not add extra fields not in the template.
5. Preserve original values (dates, amounts, names) exactly as they appear.
"""

_SCHEMA_FREE_SYSTEM_PROMPT = """\
You are a precise document entity extraction assistant.
Your task is to identify and extract ALL named entities and key structured information
from the document text and return them as a valid JSON object.

Rules:
1. Return ONLY a valid JSON object — no markdown fences, no explanation text.
2. Use meaningful key names that describe the entity type (e.g. "invoice_number", "vendor_name", "total_amount").
3. Group related entities under nested objects where appropriate (e.g. "vendor": {"name": ..., "address": ...}).
4. Use null for any field that cannot be determined.
5. Preserve original values (dates, amounts, names) exactly as they appear.
6. Include all significant entities: people, organizations, dates, amounts, locations, identifiers, etc.
"""

# ---------------------------------------------------------------------------
# Helper functions (adapted from extract_entities.py reference)
# ---------------------------------------------------------------------------


def _build_schema_description(schema: dict[str, Any]) -> str:
    """Convert schema columns dict to human-readable description.

    Strips common prefix from column names to avoid double-nesting.
    """
    columns = schema.get("columns", {})
    if not columns:
        return ""

    # Check if all columns start with a common prefix (e.g., "invoice_entities.")
    col_names = list(columns.keys())
    first_parts = [name.split(".", 1)[0] for name in col_names if "." in name]

    # If all dotted columns share the same first part, strip it
    common_prefix = None
    if first_parts and all(part == first_parts[0] for part in first_parts):
        # Check if this prefix appears in most columns
        prefix_count = sum(1 for name in col_names if name.startswith(first_parts[0] + "."))
        if prefix_count > len(col_names) * 0.5:  # More than 50% have this prefix
            common_prefix = first_parts[0]

    lines: list[str] = []
    for col_name, col_type in columns.items():
        # Strip common prefix if present
        display_name = col_name
        if common_prefix and col_name.startswith(common_prefix + "."):
            display_name = col_name[len(common_prefix) + 1 :]
        lines.append(f"  - {display_name} ({col_type})")

    return "\n".join(lines)


def _build_json_template(schema: dict[str, Any]) -> dict[str, Any]:
    """Build skeleton JSON template matching schema structure.

    Handles nested paths by building a hierarchical structure.
    If all columns start with the same prefix (e.g., 'invoice_entities.'),
    that prefix is stripped to avoid double-nesting.
    """
    columns = schema.get("columns", {})
    if not columns:
        return {}

    # Check if all columns start with a common prefix (e.g., "invoice_entities.")
    col_names = list(columns.keys())
    first_parts = [name.split(".", 1)[0] for name in col_names if "." in name]

    # If all dotted columns share the same first part, strip it
    # BUT only if that first part is NOT itself a column (to avoid stripping parent objects)
    # AND only if there are also non-dotted columns (to avoid stripping when ALL columns are under same parent)
    common_prefix = None
    if first_parts and all(part == first_parts[0] for part in first_parts):
        potential_prefix = first_parts[0]
        # Check if this prefix appears in most columns AND is not itself a column
        prefix_count = sum(1 for name in col_names if name.startswith(potential_prefix + "."))
        non_dotted_count = len([name for name in col_names if "." not in name])
        # Only use as common prefix if:
        # 1. It's not a standalone column
        # 2. It appears in >50% of columns
        # 3. There are some non-dotted columns (otherwise it's just a parent object)
        if potential_prefix not in col_names and prefix_count > len(col_names) * 0.5 and non_dotted_count > 0:
            common_prefix = potential_prefix

    # Track which fields are NESTED type
    nested_fields = {col_name for col_name, col_type in columns.items() if col_type == "NESTED"}

    # Track parent fields that should be lists (when all children share same parent)
    parent_fields = {}
    for col_name in col_names:
        if "." in col_name:
            parent = col_name.split(".", 1)[0]
            if parent not in parent_fields:
                parent_fields[parent] = []
            parent_fields[parent].append(col_name)

    # Determine which parents should be lists (when they have multiple children and aren't standalone columns)
    list_parents = set()
    for parent, children in parent_fields.items():
        if len(children) > 1 and parent not in col_names:
            list_parents.add(parent)

    template: dict[str, Any] = {}
    for col_name, col_type in columns.items():
        # Strip common prefix if present
        original_col_name = col_name
        if common_prefix and col_name.startswith(common_prefix + "."):
            col_name = col_name[len(common_prefix) + 1 :]

        if "." in col_name:
            # Build nested structure
            parts: list[str] = col_name.split(".")
            current = template
            for i, part in enumerate(parts[:-1]):
                if part not in current:
                    # Check if this parent field is marked as NESTED or should be a list
                    parent_path = ".".join(parts[: i + 1])
                    if common_prefix:
                        full_parent_path = f"{common_prefix}.{parent_path}"
                    else:
                        full_parent_path = parent_path

                    if full_parent_path in nested_fields or part in nested_fields or part in list_parents:
                        # Create a list with a single dict element
                        current[part] = [{}]
                        current = current[part][0]
                    else:
                        current[part] = {}
                        current = current[part]
                elif isinstance(current[part], list):
                    # Already a list, ensure it has at least one element
                    if len(current[part]) == 0:
                        current[part].append({})
                    current = current[part][0]
                elif isinstance(current[part], dict):
                    current = current[part]
                else:
                    # If the value is not a dict or list, convert it to one
                    current[part] = {}
                    current = current[part]
            # Set the final value
            current[parts[-1]] = None
        else:
            # Check if this field itself is NESTED
            if original_col_name in nested_fields:
                template[col_name] = []
            else:
                template[col_name] = None

    return template


def _try_repair_truncated_json(raw: str) -> dict[str, Any] | None:
    """Try to repair truncated JSON by closing unclosed braces/brackets."""
    stack: list[str] = []
    in_string: bool = False
    escape_next: bool = False
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
    closing: str = "".join(reversed(stack))
    repaired: str = raw.rstrip() + closing
    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        return None


def _parse_llm_json(raw_response: str) -> dict[str, Any]:
    """Parse JSON from LLM response with repair logic."""
    text: str = raw_response.strip()
    # Strip markdown fences
    if text.startswith("```"):
        lines: list[str] = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:]).strip()
    # Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Regex extraction of first {...} block
    match: re.Match[str] | None = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            repaired: dict[str, Any] | None = _try_repair_truncated_json(match.group())
            if repaired is not None:
                return repaired
    # Last-resort repair
    repaired = _try_repair_truncated_json(text)
    if repaired is not None:
        return repaired
    return {}


def _load_schema_from_file(schema_file: str, table_name: str) -> dict[str, Any] | None:
    """Load a named schema from a JSON schema file."""
    try:
        with open(schema_file, encoding="utf-8") as fh:
            data: dict[str, Any] = json.load(fh)
        for schema in data.get("schemas", []):
            if schema.get("table") == table_name:
                return schema
        logger.warning("Schema table '%s' not found in '%s'", table_name, schema_file)
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("Failed to load schema file '%s': %s", schema_file, exc)
    return None


# ---------------------------------------------------------------------------
# Worker function (runs in thread pool)
# ---------------------------------------------------------------------------


def _extract_entities_worker(
    doc_id: str,
    doc_name: str,
    content: str,
    schema: dict[str, Any],
    ollama_model: str,
    temperature: float,
    max_doc_chars: int,
) -> dict[str, Any]:
    """
    Worker function: calls Ollama to extract entities from *content*.

    Returns a dict with keys: ``success``, ``entities`` (JSON string), ``error``.
    """
    try:
        import ollama  # lazy import — not available in all environments
    except ImportError as exc:
        return {
            "success": False,
            "entities": "{}",
            "error": f"ollama package not installed: {exc}",
        }

    try:
        truncated_content: str = content[:max_doc_chars] if len(content) > max_doc_chars else content
        has_schema: bool = bool(schema.get("columns"))

        if has_schema:
            schema_desc: str = _build_schema_description(schema)
            json_template: dict[str, Any] = _build_json_template(schema)
            system_prompt: str = _SYSTEM_PROMPT
            user_prompt: str = (
                f"Extract entities from the following document text.\n\n"
                f"Schema fields to extract:\n{schema_desc}\n\n"
                f"Return your answer as a JSON object matching this template exactly:\n"
                f"{json.dumps(json_template, indent=2)}\n\n"
                f"Document text:\n{truncated_content}"
            )
        else:
            system_prompt = _SCHEMA_FREE_SYSTEM_PROMPT
            user_prompt = (
                f"Extract all named entities and key information from the following document text.\n\n"
                f"Document text:\n{truncated_content}"
            )

        response: dict[str, Any] = ollama.chat(
            model=ollama_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            options={"temperature": temperature},
        )
        raw: str = response["message"]["content"]
        entities: dict[str, Any] = _parse_llm_json(raw)
        return {"success": True, "entities": entities, "error": None}

    except Exception as exc:
        logger.error("Entity extraction failed for doc '%s' (%s): %s", doc_name, doc_id, exc)
        return {"success": False, "entities": {}, "error": str(exc)}


# ---------------------------------------------------------------------------
# Operator
# ---------------------------------------------------------------------------


class ExtractEntitiesOllamaOperator(AbstractOperator):
    """
    Extract structured entities from document text using a local Ollama LLM.

    The operator reads the ``doc_column`` (plain text, typically produced by
    :class:`ExtractDoclingOperator`) and writes a JSON string of extracted
    entities into ``output_column``.

    A schema that describes the fields to extract must be supplied either
    inline via the ``schema`` config key or by pointing to a JSON file with
    ``schema_file`` + ``schema_table``.

    Schema JSON format (same as ``document_schemas.json`` in the reference)::

        {
          "schemas": [{
            "table": "purchase_orders",
            "description": "...",
            "columns": {
              "supplier.name": "STRING",
              "items": "NESTED",
              "items.item_id": "STRING",
              "total_amount": "DOUBLE"
            }
          }]
        }
    """

    short_name: str = OperatorConstants.Operators.EXTRACT_ENTITIES_OLLAMA
    category: OperatorCategory = OperatorCategory.Extract

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)

        self.doc_column: str = config.get(
            OperatorConstants.Columns.DOC_COLUMN, OperatorConstants.Columns.DOC_COLUMN_DEFAULT
        )
        self.doc_id_hash_column: str = config.get(
            OperatorConstants.Columns.DOC_ID_HASH, OperatorConstants.Columns.DOC_ID_HASH_DEFAULT
        )
        self.ollama_model: str = config.get("ollama_model", "granite4")
        self.output_column: str = config.get("output_column", "entities")
        self.max_doc_chars: int = int(config.get("max_doc_chars", 8000))
        self.temperature: float = float(config.get("temperature", 0.0))
        self.max_workers: int = int(config.get(OperatorConstants.Config.MAX_WORKERS, 4))
        _raw_expand = config.get(OperatorConstants.Config.EXPAND_EXTRACTED_DATA, False)
        self.expand_entities: bool = (
            _raw_expand if isinstance(_raw_expand, bool) else str(_raw_expand).lower() in ("true", "1", "yes")
        )

        # Schema: inline dict takes priority over file reference
        self.schema: dict[str, Any] | None = config.get("schema")
        self.schema_file: str | None = config.get("schema_file")
        self.schema_table: str = config.get("schema_table", "default")

        self._resolved_schema: dict[str, Any] | None = None

        self.common_log_arguments: dict[str, Any] = {
            DatasiftConstants.JOB_ID: self.job_id,
            DatasiftConstants.JOB_RUN_ID: self.job_run_id,
            DatasiftConstants.CONTEXT_ID: self.context_id,
        }

    # ------------------------------------------------------------------
    # Schema resolution
    # ------------------------------------------------------------------

    def _get_schema(self) -> dict[str, Any]:
        """Return the resolved schema, loading from file if necessary."""
        if self._resolved_schema is not None:
            return self._resolved_schema

        if self.schema is not None:
            self._resolved_schema = self.schema
        elif self.schema_file is not None:
            loaded = _load_schema_from_file(self.schema_file, self.schema_table)
            self._resolved_schema = loaded if loaded is not None else {"columns": {}}
        else:
            self._resolved_schema = {"columns": {}}

        return self._resolved_schema

    # ------------------------------------------------------------------
    # Entity expansion
    # ------------------------------------------------------------------

    def _expand_entities_columns(self, table: pa.Table, entities_list: list) -> pa.Table:
        """Expand entity dict into individual columns, one per entity key.

        Column values are cast to the appropriate Python type based on the
        schema column definition (DOUBLE/FLOAT → float, INT/INTEGER → int,
        everything else → str).  This ensures OpenSearch receives numeric
        values as numbers rather than strings so that SQL aggregations work.
        """

        # Collect all unique keys
        all_keys: set[str] = set()
        for entity in entities_list:
            if entity and isinstance(entity, dict):
                all_keys.update(entity.keys())

        if not all_keys:
            return table

        # Build a lookup: column_name → schema type string (upper-cased)
        schema_columns: dict[str, str] = {}
        resolved = self._get_schema()
        if resolved:
            for col_name, col_type in resolved.get("columns", {}).items():
                schema_columns[col_name.lower()] = str(col_type).upper()

        _FLOAT_TYPES = {"DOUBLE", "FLOAT", "FLOAT32", "FLOAT64", "DECIMAL", "NUMERIC"}
        _INT_TYPES = {"INT", "INTEGER", "BIGINT", "SMALLINT", "TINYINT", "LONG"}

        def _cast(key: str, val: Any) -> Any:
            """Cast *val* to the Python type implied by the schema for *key*."""
            if val is None:
                return None
            col_type = schema_columns.get(key.lower(), "STRING")
            if col_type in _FLOAT_TYPES:
                try:
                    return float(val)
                except (ValueError, TypeError):
                    return None
            if col_type in _INT_TYPES:
                try:
                    return int(float(val))
                except (ValueError, TypeError):
                    return None
            return str(val)

        # Create one column per key
        for key in sorted(all_keys):
            column_values = [
                (_cast(key, entity[key]) if (entity and isinstance(entity, dict) and key in entity) else None)
                for entity in entities_list
            ]
            table = TransformUtils.add_column(table, name=f"entity_{key}", content=column_values)

        return table

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    @staticmethod
    def is_available() -> bool:
        try:
            import ollama  # noqa: F401

            return True
        except ImportError:
            return False

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self, errors: list[str], warnings: list[str], available_features: list[str]) -> None:
        super().validate(errors, warnings, available_features)

        if self.should_validate_field(field_value=self.ollama_model):
            if not self.ollama_model or not isinstance(self.ollama_model, str):
                errors.append("ollama_model must be a non-empty string (e.g. 'llama3', 'mistral').")

        if self.should_validate_field(field_value=self.doc_column):
            if self.doc_column not in available_features:
                errors.append(
                    f"Required feature '{self.doc_column}' is not available. "
                    "Run ExtractDoclingOperator (or equivalent) before this operator."
                )

    # ------------------------------------------------------------------
    # Core transform
    # ------------------------------------------------------------------

    def transform(self, table: pa.Table) -> tuple[list[pa.Table], dict[str, Any]]:
        metadata: dict[str, Any] = self.create_base_metadata(total_docs_count=table.num_rows)

        schema: dict[str, Any] = self._get_schema()
        entities_list: list[dict[str, Any]] = [{}] * table.num_rows

        # Build task list
        doc_tasks: list[tuple[int, str, str, str]] = []  # (row_idx, doc_id, doc_name, content)
        for row_idx in range(table.num_rows):
            row = {col: table.column(col)[row_idx].as_py() for col in table.column_names}
            doc_id = str(row.get(OperatorConstants.Columns.ID, row_idx))
            doc_name = str(row.get(OperatorConstants.Columns.NAME, f"doc_{row_idx}"))
            content = row.get(self.doc_column) or ""

            if not content:
                self.record_skipped_document(
                    metadata=metadata,
                    doc_id=doc_id,
                    doc_name=doc_name,
                    reason=f"Column '{self.doc_column}' is empty or missing.",
                )
                continue
            doc_tasks.append((row_idx, doc_id, doc_name, content))

        # Process in parallel
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_task: dict[Future[dict[str, Any]], tuple[int, str, str]] = {
                executor.submit(
                    _extract_entities_worker,
                    doc_id,
                    doc_name,
                    content,
                    schema,
                    self.ollama_model,
                    self.temperature,
                    self.max_doc_chars,
                ): (row_idx, doc_id, doc_name)
                for row_idx, doc_id, doc_name, content in doc_tasks
            }

            for future in as_completed(future_to_task):
                row_idx, doc_id, doc_name = future_to_task[future]
                try:
                    result: dict[str, Any] = future.result()
                except Exception as exc:
                    self.record_failed_document(
                        metadata=metadata,
                        doc_id=doc_id,
                        doc_name=doc_name,
                        reason=str(exc),
                    )
                    continue

                if result["success"]:
                    entities_list[row_idx] = result["entities"]
                    metadata[Metrics.External.PROCESSED_DOCS] += 1
                else:
                    self.record_failed_document(
                        metadata=metadata,
                        doc_id=doc_id,
                        doc_name=doc_name,
                        reason=result["error"],
                    )

        # Optionally expand entities into individual columns
        if self.expand_entities:
            if entities_list:
                table = self._expand_entities_columns(table, entities_list)

        # Add entities column - convert to JSON strings for PyArrow compatibility
        entities_json_list: list[str] = [json.dumps(entity) if entity else "{}" for entity in entities_list]
        table = TransformUtils.add_column(table=table, name=self.output_column, content=entities_json_list)

        # Ensure doc_id_hash column exists
        if self.doc_id_hash_column not in table.column_names:
            doc_id_hash_op: DocIdHashOperator = DocIdHashOperator(
                {
                    OperatorConstants.Columns.DOC_COLUMN: self.doc_column,
                    OperatorConstants.Columns.DOC_ID_HASH: self.doc_id_hash_column,
                }
            )
            result_tables: list[pa.Table]
            result_tables, _ = doc_id_hash_op.transform(table)
            table = result_tables[0]

        # Set final node status
        if metadata.get(Metrics.External.FAILED_DOCS_COUNT, 0) > 0:
            metadata[Metrics.External.NODE_STATUS] = ExecutionStatus.COMPLETED_WITH_ERRORS
        else:
            metadata[Metrics.External.NODE_STATUS] = ExecutionStatus.COMPLETED

        return [table], metadata

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    def get_metadata(self) -> dict[str, Any]:
        return {
            OperatorConstants.Misc.CATEGORY: self.category.value,
            OperatorConstants.Misc.SDK: True,
            OperatorConstants.Misc.LABEL: "Entity Extraction (Ollama)",
            OperatorConstants.Config.DESCRIPTION: (
                "Extracts structured entities from document text using a locally running "
                "Ollama LLM, guided by a user-provided JSON schema template."
            ),
            OperatorConstants.Misc.IS_OPERATOR_AVAILABLE: self.is_available(),
            OperatorConstants.Config.FEATURES: {
                self.output_column: {
                    OperatorConstants.Misc.NAME: "Entities",
                    OperatorConstants.Config.DESCRIPTION: "JSON string of extracted entities matching the provided schema.",
                    OperatorConstants.Config.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                    OperatorConstants.Misc.TAGS: [],
                },
                OperatorConstants.Columns.DOC_ID_HASH_DEFAULT: {
                    OperatorConstants.Misc.NAME: "Document ID Hash",
                    OperatorConstants.Config.DESCRIPTION: "Unique hash identifier for the document.",
                    OperatorConstants.Config.AVAILABLE_FOR_VECTOR_DB: True,
                    OperatorConstants.Config.MANDATORY_FOR_VECTOR_DB: True,
                    OperatorConstants.Misc.IS_PRIMARY: True,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                    OperatorConstants.Misc.TAGS: [
                        OperatorConstants.Misc.MANDATORY,
                        OperatorConstants.Misc.PRIMARY,
                    ],
                },
            },
            OperatorConstants.Config.ATTRIBUTES: {
                "ollama_model": {
                    OperatorConstants.Misc.NAME: "Ollama Model",
                    OperatorConstants.Config.DESCRIPTION: "Name of the Ollama model to use (e.g. 'granite4', 'mistral').",
                    OperatorConstants.Config.REQUIRED: True,
                    OperatorConstants.Config.DEFAULT: "granite4",
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                "schema": {
                    OperatorConstants.Misc.NAME: "Schema (inline)",
                    OperatorConstants.Config.DESCRIPTION: "Inline schema dict with 'columns' key mapping field names to types.",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: None,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.JSON,
                },
                "schema_file": {
                    OperatorConstants.Misc.NAME: "Schema File",
                    OperatorConstants.Config.DESCRIPTION: "Path to a JSON file containing schema definitions.",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: None,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                "schema_table": {
                    OperatorConstants.Misc.NAME: "Schema Table Name",
                    OperatorConstants.Config.DESCRIPTION: "Name of the schema table to use from the schema file.",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: "default",
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                "max_doc_chars": {
                    OperatorConstants.Misc.NAME: "Max Document Characters",
                    OperatorConstants.Config.DESCRIPTION: "Maximum number of characters to send to the LLM per document.",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: 8000,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.INTEGER,
                },
                "temperature": {
                    OperatorConstants.Misc.NAME: "Temperature",
                    OperatorConstants.Config.DESCRIPTION: "LLM sampling temperature (0.0 = deterministic).",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: 0.0,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.FLOAT,
                },
                OperatorConstants.Columns.DOC_COLUMN: {
                    OperatorConstants.Misc.NAME: "Document Column",
                    OperatorConstants.Config.DESCRIPTION: "Name of the column containing document text.",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: OperatorConstants.Columns.DOC_COLUMN_DEFAULT,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                OperatorConstants.Config.MAX_WORKERS: {
                    OperatorConstants.Misc.NAME: "Max Workers",
                    OperatorConstants.Config.DESCRIPTION: "Number of parallel threads for entity extraction.",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: 4,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.INTEGER,
                },
                "output_column": {
                    OperatorConstants.Misc.NAME: "Output Column",
                    OperatorConstants.Config.DESCRIPTION: "Name of the output column that stores the extracted entities JSON string.",
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: OperatorConstants.Misc.ENTITIES,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.STRING,
                },
                OperatorConstants.Config.EXPAND_EXTRACTED_DATA: {
                    OperatorConstants.Misc.NAME: "Expand Extracted Data",
                    OperatorConstants.Config.DESCRIPTION: (
                        "When True, expands the extracted entities JSON into individual columns "
                        "(one per entity key, named 'entity_{key}')."
                    ),
                    OperatorConstants.Config.REQUIRED: False,
                    OperatorConstants.Config.DEFAULT: False,
                    OperatorConstants.Misc.TYPE: AttributeDataTypes.BOOLEAN,
                },
            },
        }


# Made with Bob
