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
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import pyarrow as pa

from common.util.constants import AttributeDataTypes, DatasiftConstants, ExecutionStatus, Metrics, OperatorConstants
from common.util.log import get_logger
from core.operators.abstract_operator import AbstractOperator, OperatorCategory
from core.operators.universal.doc_id.doc_id_hash import DocIdHashOperator

try:
    from data_processing.utils import TransformUtils
except ImportError:
    class TransformUtils:  # type: ignore[no-redef]
        @staticmethod
        def add_column(table: pa.Table, name: str, content: list) -> pa.Table:
            new_column = pa.array(content)
            new_field = pa.field(name, new_column.type)
            return table.append_column(new_field, new_column)

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
    """Convert schema columns dict to human-readable description."""
    lines = []
    for col_name, col_type in schema.get("columns", {}).items():
        lines.append(f"  - {col_name} ({col_type})")
    return "\n".join(lines)


def _build_json_template(schema: dict[str, Any]) -> dict[str, Any]:
    """Build skeleton JSON template matching schema structure."""
    template: dict[str, Any] = {}
    for col_name, col_type in schema.get("columns", {}).items():
        if "." in col_name:
            parts = col_name.split(".", 1)
            parent, child = parts[0], parts[1]
            if parent not in template:
                template[parent] = [{}]
            if isinstance(template[parent], list) and template[parent]:
                template[parent][0][child] = None
        else:
            template[col_name] = [{}] if col_type == "NESTED" else None
    return template


def _try_repair_truncated_json(raw: str) -> dict[str, Any] | None:
    """Try to repair truncated JSON by closing unclosed braces/brackets."""
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


def _parse_llm_json(raw_response: str) -> dict[str, Any]:
    """Parse JSON from LLM response with repair logic."""
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
            repaired = _try_repair_truncated_json(match.group())
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
            data = json.load(fh)
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
        return {"success": False, "entities": "{}", "error": f"ollama package not installed: {exc}"}

    try:
        truncated_content = content[:max_doc_chars] if len(content) > max_doc_chars else content
        has_schema = bool(schema.get("columns"))

        if has_schema:
            schema_desc = _build_schema_description(schema)
            json_template = _build_json_template(schema)
            system_prompt = _SYSTEM_PROMPT
            user_prompt = (
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

        response = ollama.chat(
            model=ollama_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            options={"temperature": temperature},
        )
        raw = response["message"]["content"]
        entities = _parse_llm_json(raw)
        return {"success": True, "entities": json.dumps(entities), "error": None}

    except Exception as exc:  # noqa: BLE001
        logger.error("Entity extraction failed for doc '%s' (%s): %s", doc_name, doc_id, exc)
        return {"success": False, "entities": "{}", "error": str(exc)}


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

    short_name = OperatorConstants.EXTRACT_ENTITIES_OLLAMA
    category = OperatorCategory.Extract

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)

        self.doc_column: str = config.get(OperatorConstants.DOC_COLUMN, OperatorConstants.DOC_COLUMN_DEFAULT)
        self.doc_id_hash_column: str = config.get(
            OperatorConstants.DOC_ID_HASH, OperatorConstants.DOC_ID_HASH_DEFAULT
        )
        self.ollama_model: str = config.get("ollama_model", "granite4")
        self.output_column: str = config.get("output_column", "entities")
        self.max_doc_chars: int = int(config.get("max_doc_chars", 8000))
        self.temperature: float = float(config.get("temperature", 0.0))
        self.max_workers: int = int(config.get(OperatorConstants.MAX_WORKERS, 4))

        # Schema: inline dict takes priority over file reference
        self.schema: dict[str, Any] | None = config.get("schema", None)
        self.schema_file: str | None = config.get("schema_file", None)
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

    def validate(self, errors: list, warnings: list, available_features: list) -> None:
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
        metadata = self.create_base_metadata(total_docs_count=table.num_rows)

        schema = self._get_schema()
        entities_list: list[str] = ["{}"] * table.num_rows

        # Build task list
        doc_tasks: list[tuple[int, str, str, str]] = []  # (row_idx, doc_id, doc_name, content)
        for row_idx in range(table.num_rows):
            row = {col: table.column(col)[row_idx].as_py() for col in table.column_names}
            doc_id = str(row.get(OperatorConstants.ID, row_idx))
            doc_name = str(row.get(OperatorConstants.NAME, f"doc_{row_idx}"))
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
            future_to_task = {
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
                    result = future.result()
                except Exception as exc:  # noqa: BLE001
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

        # Add entities column
        table = TransformUtils.add_column(table=table, name=self.output_column, content=entities_list)

        # Ensure doc_id_hash column exists
        if self.doc_id_hash_column not in table.column_names:
            doc_id_hash_op = DocIdHashOperator(
                {
                    OperatorConstants.DOC_COLUMN: self.doc_column,
                    OperatorConstants.DOC_ID_HASH: self.doc_id_hash_column,
                }
            )
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
            OperatorConstants.CATEGORY: self.category.value,
            OperatorConstants.SDK: True,
            OperatorConstants.LABEL: "Entity Extraction (Ollama)",
            OperatorConstants.DESCRIPTION: (
                "Extracts structured entities from document text using a locally running "
                "Ollama LLM, guided by a user-provided JSON schema template."
            ),
            OperatorConstants.IS_OPERATOR_AVAILABLE: self.is_available(),
            OperatorConstants.FEATURES: {
                self.output_column: {
                    OperatorConstants.NAME: "Entities",
                    OperatorConstants.DESCRIPTION: "JSON string of extracted entities matching the provided schema.",
                    OperatorConstants.AVAILABLE_FOR_FILTER: True,
                    OperatorConstants.AVAILABLE_FOR_VECTOR_DB: True,
                    OperatorConstants.TYPE: AttributeDataTypes.STRING,
                    OperatorConstants.TAGS: [],
                },
                OperatorConstants.DOC_ID_HASH_DEFAULT: {
                    OperatorConstants.NAME: "Document ID Hash",
                    OperatorConstants.DESCRIPTION: "Unique hash identifier for the document.",
                    OperatorConstants.AVAILABLE_FOR_VECTOR_DB: True,
                    OperatorConstants.MANDATORY_FOR_VECTOR_DB: True,
                    OperatorConstants.IS_PRIMARY: True,
                    OperatorConstants.TYPE: AttributeDataTypes.STRING,
                    OperatorConstants.TAGS: [OperatorConstants.MANDATORY, OperatorConstants.PRIMARY],
                },
            },
            OperatorConstants.ATTRIBUTES: {
                "ollama_model": {
                    OperatorConstants.NAME: "Ollama Model",
                    OperatorConstants.DESCRIPTION: "Name of the Ollama model to use (e.g. 'granite4', 'mistral').",
                    OperatorConstants.REQUIRED: True,
                    OperatorConstants.DEFAULT: "granite4",
                    OperatorConstants.TYPE: AttributeDataTypes.STRING,
                },
                "schema": {
                    OperatorConstants.NAME: "Schema (inline)",
                    OperatorConstants.DESCRIPTION: "Inline schema dict with 'columns' key mapping field names to types.",
                    OperatorConstants.REQUIRED: False,
                    OperatorConstants.DEFAULT: None,
                    OperatorConstants.TYPE: AttributeDataTypes.JSON,
                },
                "schema_file": {
                    OperatorConstants.NAME: "Schema File",
                    OperatorConstants.DESCRIPTION: "Path to a JSON file containing schema definitions.",
                    OperatorConstants.REQUIRED: False,
                    OperatorConstants.DEFAULT: None,
                    OperatorConstants.TYPE: AttributeDataTypes.STRING,
                },
                "schema_table": {
                    OperatorConstants.NAME: "Schema Table Name",
                    OperatorConstants.DESCRIPTION: "Name of the schema table to use from the schema file.",
                    OperatorConstants.REQUIRED: False,
                    OperatorConstants.DEFAULT: "default",
                    OperatorConstants.TYPE: AttributeDataTypes.STRING,
                },
                "max_doc_chars": {
                    OperatorConstants.NAME: "Max Document Characters",
                    OperatorConstants.DESCRIPTION: "Maximum number of characters to send to the LLM per document.",
                    OperatorConstants.REQUIRED: False,
                    OperatorConstants.DEFAULT: 8000,
                    OperatorConstants.TYPE: AttributeDataTypes.INTEGER,
                },
                "temperature": {
                    OperatorConstants.NAME: "Temperature",
                    OperatorConstants.DESCRIPTION: "LLM sampling temperature (0.0 = deterministic).",
                    OperatorConstants.REQUIRED: False,
                    OperatorConstants.DEFAULT: 0.0,
                    OperatorConstants.TYPE: AttributeDataTypes.FLOAT,
                },
                OperatorConstants.DOC_COLUMN: {
                    OperatorConstants.NAME: "Document Column",
                    OperatorConstants.DESCRIPTION: "Name of the column containing document text.",
                    OperatorConstants.REQUIRED: False,
                    OperatorConstants.DEFAULT: OperatorConstants.DOC_COLUMN_DEFAULT,
                    OperatorConstants.TYPE: AttributeDataTypes.STRING,
                },
                OperatorConstants.MAX_WORKERS: {
                    OperatorConstants.NAME: "Max Workers",
                    OperatorConstants.DESCRIPTION: "Number of parallel threads for entity extraction.",
                    OperatorConstants.REQUIRED: False,
                    OperatorConstants.DEFAULT: 4,
                    OperatorConstants.TYPE: AttributeDataTypes.INTEGER,
                },
            },
        }

# Made with Bob
