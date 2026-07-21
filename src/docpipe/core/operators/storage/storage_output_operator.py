"""StorageOutputOperator — writes pipeline documents to storage destinations."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow as pa

# Import adapter so it self-registers via @register_destination_adapter
import docpipe.core.operators.storage.adapters.outbound.destinations.filesystem.adapter  # noqa: F401
from docpipe.core.constants.constants import DocpipeConstants, ExecutionStatus, Metrics
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.operators.abstract_operator import AbstractOperator, OperatorCategory
from docpipe.core.operators.operator_utils import OperatorUtils
from docpipe.core.operators.storage.adapters.outbound.destinations.factories.destination_factory import (
    DestinationAdapterFactory,
)
from docpipe.core.operators.storage.domain.models import ContentFormat, WriteMode, WriteResult
from docpipe.utils.infrastructure.logging import get_logger
from docpipe.utils.operators.binary_content_fetcher import get_binary_content

logger = get_logger()

_REQUIRED_COLUMNS_BY_MODE: dict[str, list[str]] = {
    WriteMode.PROCESSED_CONTENT: ["id", "name", "content"],
    WriteMode.REFETCH_ORIGINAL: ["id", "name", "path", "document_format"],
    WriteMode.COMPREHENSIVE_EXPORT: ["id", "name", "path", "content", "metadata", "document_format"],
}

_ALL_INPUT_COLUMNS = ["id", "name", "path", "content", "metadata", "document_format"]


def resolve_path_template(
    *,
    template: str | None,
    doc_id: str,
    name: str,
    ext: str,
    hierarchical: bool = False,
    source_relative_path: str | None = None,
) -> str:
    """Resolve a path template string with per-document variable substitution.

    Variables: {doc_id}, {name}, {ext}, {year}, {month}, {day}
    Falls back to "{name}.{ext}" (flat) or the source relative path (hierarchical)
    when template is None.

    When ``hierarchical=True`` and no template is provided, the source relative
    path is used to mirror the source directory structure at the destination.
    """
    now = datetime.now(tz=UTC)
    # Strip extension from name to get stem
    stem = Path(name).stem
    # Normalise ext: remove any leading dot so templates like "{doc_id}.{ext}" don't produce "..pdf"
    ext = ext.lstrip(".")

    variables = {
        "doc_id": doc_id,
        "name": stem,
        "ext": ext,
        "year": now.strftime("%Y"),
        "month": now.strftime("%m"),
        "day": now.strftime("%d"),
    }

    if not template:
        if hierarchical and source_relative_path:
            return source_relative_path
        return f"{stem}.{ext}"

    return template.format(**variables)


def _extract_source_relative_path(row: dict[str, Any]) -> str | None:
    """Extract ``relative_path`` from the JSON-serialised ``metadata`` column.

    Returns the value (e.g. ``sub01/report.pdf``) when present, else ``None``.
    """
    raw = row.get("metadata", "{}")
    try:
        parsed = json.loads(raw) if raw else {}
    except (json.JSONDecodeError, TypeError):
        parsed = {}
    return parsed.get("relative_path") or None


class StorageOutputOperator(AbstractOperator):
    """
    Writes pipeline documents to a storage destination.

    Supports three modes:
    - processed_content: write extracted content as .md / .txt / .json
    - refetch_original: re-fetch original binary from source and write to destination
    - comprehensive_export: write original + content + metadata sidecar per document
    """

    short_name: str = "storage_output"
    category: OperatorCategory = OperatorCategory.Storage
    owner = DocpipeConstants.OWNER_DOCPIPE
    # StorageOutputOperator does not produce extracted text content, so the
    # generic empty-document check (which keys off doc_column) must be skipped.
    doc_column: str | None = None

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.mode: str | None = config.get("mode")
        self.ingest_source: dict[str, Any] = config.get(OperatorConstants.Config.INGEST_SOURCE, {})
        self.destination_config: dict[str, Any] = config.get("destination_config", {})
        self.output_format: dict[str, Any] = config.get("output_format", {})
        self.output_structure: dict[str, Any] = config.get("output_structure", {})

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self, errors: list, warnings: list, available_features: list) -> None:
        if not self.mode:
            errors.append(f"{self.short_name}: 'mode' is required")
            return

        if self.mode not in list(WriteMode):
            errors.append(
                f"{self.short_name}: invalid mode '{self.mode}'. Must be one of: {[m.value for m in WriteMode]}"
            )
            return

        required_cols = _REQUIRED_COLUMNS_BY_MODE.get(self.mode, [])
        for col in required_cols:
            if col not in available_features:
                errors.append(f"{self.short_name}: required column '{col}' not found in available features")

        if not self.validating_flow and self.mode in (WriteMode.REFETCH_ORIGINAL, WriteMode.COMPREHENSIVE_EXPORT):
            if not self.ingest_source:
                errors.append(f"{self.short_name}: mode '{self.mode}' requires an upstream ingest_source operator")

    @staticmethod
    def get_metadata() -> dict[str, Any]:
        """Return operator metadata for flow validation and discovery."""
        return {
            OperatorConstants.Misc.IS_OPERATOR_AVAILABLE: StorageOutputOperator.is_available(),
            OperatorConstants.Misc.CATEGORY: StorageOutputOperator.category.value,
            OperatorConstants.Misc.LABEL: "Storage Output",
            OperatorConstants.Config.DESCRIPTION: (
                "Writes pipeline documents to a storage destination. "
                "Supports processed_content, refetch_original, and comprehensive_export modes."
            ),
        }

    @staticmethod
    def get_required_features() -> list[str]:
        return ["id", "name", "content"]

    # ------------------------------------------------------------------
    # Transform
    # ------------------------------------------------------------------

    def transform(self, table: pa.Table) -> tuple[list[pa.Table], dict[str, Any]]:
        span = self._create_operator_span()
        try:
            return self._transform(table)
        except Exception as e:
            self._telemetry.record_exception(e, span=span)
            raise
        finally:
            self._telemetry.end_span(span)

    def _transform(self, table: pa.Table) -> tuple[list[pa.Table], dict[str, Any]]:
        # --- parameter validation ---
        if not self.mode:
            raise ValueError(f"{self.short_name}: 'mode' is required")
        if not self.destination_config:
            raise ValueError(f"{self.short_name}: 'destination_config' is required")
        if self.mode in (WriteMode.REFETCH_ORIGINAL, WriteMode.COMPREHENSIVE_EXPORT):
            if not self.ingest_source:
                raise ValueError(f"{self.short_name}: mode '{self.mode}' requires an upstream ingest_source operator")

        total = table.num_rows if table is not None else 0
        metadata = self.create_base_metadata(total_docs_count=total)

        if total == 0:
            output_table = self._build_output_table(table, [])
            metadata[Metrics.External.NODE_STATUS] = ExecutionStatus.COMPLETED
            return [output_table], metadata

        # --- build adapter + config ---
        provider = self.destination_config.get("provider", "")
        adapter = DestinationAdapterFactory.create(provider)
        dest_cfg = adapter.build_config_from_operator_params(
            connection_params=self.destination_config.get("connection_params", {}),
            credentials=self.destination_config.get("credentials", {}),
        )

        content_format = self.output_format.get("content_format", ContentFormat.MD).lstrip(".")
        path_template = self.output_structure.get("path_template")
        overwrite = self.output_structure.get("overwrite_existing", True)
        hierarchical = self.output_structure.get("type", "flat") == "hierarchical"

        rows = table.to_pylist()
        write_results: list[WriteResult] = []

        for row in rows:
            doc_id = row.get("id", "")
            doc_name = row.get("name", "")

            try:
                result = self._write_row(
                    row=row,
                    adapter=adapter,
                    dest_cfg=dest_cfg,
                    content_format=content_format,
                    path_template=path_template,
                    overwrite=overwrite,
                    hierarchical=hierarchical,
                    doc_id=doc_id,
                    doc_name=doc_name,
                )
                result.doc_id = doc_id
                result.doc_name = doc_name
                write_results.append(result)

                if result.success:
                    metadata[Metrics.External.PROCESSED_DOCS] += 1
                elif result.write_status == "skipped":
                    self.record_skipped_document(
                        metadata=metadata,
                        doc_id=doc_id,
                        doc_name=doc_name,
                        reason=result.error_message or "skipped",
                    )
                else:
                    self.record_failed_document(
                        metadata=metadata,
                        doc_id=doc_id,
                        doc_name=doc_name,
                        reason=result.error_message or "unknown error",
                    )

            except Exception as e:
                logger.error(
                    f"Unexpected error writing document {doc_name}: {e}",
                    extra=self.common_log_arguments,
                )
                write_results.append(
                    WriteResult(
                        doc_id=doc_id,
                        doc_name=doc_name,
                        success=False,
                        error_message=str(e),
                    )
                )
                self.record_failed_document(
                    metadata=metadata,
                    doc_id=doc_id,
                    doc_name=doc_name,
                    reason=str(e),
                )

        metadata[Metrics.External.NODE_STATUS] = OperatorUtils.determine_execution_status(
            processed_count=metadata[Metrics.External.PROCESSED_DOCS],
            failed_count=metadata[Metrics.External.FAILED_DOCS_COUNT],
            skipped_count=metadata[Metrics.External.SKIPPED_DOCS_COUNT],
        )

        output_table = self._build_output_table(table, write_results)
        self._record_operator_metrics(span=None, metadata=metadata)
        return [output_table], metadata

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _write_row(
        self,
        *,
        row: dict[str, Any],
        adapter: Any,
        dest_cfg: Any,
        content_format: str,
        path_template: str | None,
        overwrite: bool,
        hierarchical: bool,
        doc_id: str,
        doc_name: str,
    ) -> WriteResult:
        if self.mode == WriteMode.PROCESSED_CONTENT:
            return self._write_processed_content(
                row=row,
                adapter=adapter,
                dest_cfg=dest_cfg,
                content_format=content_format,
                path_template=path_template,
                overwrite=overwrite,
                hierarchical=hierarchical,
                doc_id=doc_id,
                doc_name=doc_name,
            )
        if self.mode == WriteMode.REFETCH_ORIGINAL:
            return self._write_refetch_original(
                row=row,
                adapter=adapter,
                dest_cfg=dest_cfg,
                path_template=path_template,
                overwrite=overwrite,
                hierarchical=hierarchical,
                doc_id=doc_id,
                doc_name=doc_name,
            )
        if self.mode == WriteMode.COMPREHENSIVE_EXPORT:
            return self._write_comprehensive_export(
                row=row,
                adapter=adapter,
                dest_cfg=dest_cfg,
                content_format=content_format,
                path_template=path_template,
                overwrite=overwrite,
                hierarchical=hierarchical,
                doc_id=doc_id,
                doc_name=doc_name,
            )
        raise NotImplementedError(f"Mode '{self.mode}' not yet implemented")

    def _write_processed_content(
        self,
        *,
        row: dict[str, Any],
        adapter: Any,
        dest_cfg: Any,
        content_format: str,
        path_template: str | None,
        overwrite: bool,
        hierarchical: bool,
        doc_id: str,
        doc_name: str,
    ) -> WriteResult:
        content_str: str = row.get("content", "") or ""

        if content_format == ContentFormat.JSON:
            payload = {
                "id": doc_id,
                "name": doc_name,
                "content": content_str,
            }
            content_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        else:
            content_bytes = content_str.encode("utf-8")

        # Resolve base path using the original name, then apply the ".content.<ext>" infix
        # so naming is consistent with comprehensive_export mode.
        relative_path = resolve_path_template(
            template=path_template,
            doc_id=doc_id,
            name=doc_name,
            ext=content_format,
            hierarchical=hierarchical,
            source_relative_path=_extract_source_relative_path(row),
        )
        base_path = Path(dest_cfg.root_path) / relative_path
        destination_path = str(base_path.with_name(base_path.stem + f".content.{content_format}"))

        return adapter.write_document(
            content=content_bytes,
            destination_path=destination_path,
            overwrite=overwrite,
            config=dest_cfg,
        )

    def _write_refetch_original(
        self,
        *,
        row: dict[str, Any],
        adapter: Any,
        dest_cfg: Any,
        path_template: str | None,
        overwrite: bool,
        hierarchical: bool,
        doc_id: str,
        doc_name: str,
    ) -> WriteResult:
        ext = row.get("document_format", "") or Path(doc_name).suffix.lstrip(".")
        relative_path = resolve_path_template(
            template=path_template,
            doc_id=doc_id,
            name=doc_name,
            ext=ext,
            hierarchical=hierarchical,
            source_relative_path=_extract_source_relative_path(row),
        )
        destination_path = str(Path(dest_cfg.root_path) / relative_path)

        # Validate destination before fetching binary content
        dest_path = Path(destination_path)
        if not overwrite and dest_path.exists():
            return WriteResult(
                doc_id=doc_id,
                doc_name=doc_name,
                success=False,
                error_message="file exists, overwrite disabled",
            )
        create_dirs = dest_cfg.create_dirs if dest_cfg is not None else True
        if not dest_path.parent.exists() and not create_dirs:
            return WriteResult(
                doc_id=doc_id,
                doc_name=doc_name,
                success=False,
                error_message=f"destination directory does not exist and create_dirs is disabled: {dest_path.parent}",
            )

        binary = self._fetch_binary(row=row, doc_name=doc_name)

        if binary is None:
            return WriteResult(
                doc_id=doc_id,
                doc_name=doc_name,
                success=False,
                error_message=f"Could not fetch binary content for '{doc_name}' from source",
            )

        return adapter.write_document(
            content=binary,
            destination_path=destination_path,
            overwrite=overwrite,
            config=dest_cfg,
        )

    def _write_comprehensive_export(
        self,
        *,
        row: dict[str, Any],
        adapter: Any,
        dest_cfg: Any,
        content_format: str,
        path_template: str | None,
        overwrite: bool,
        hierarchical: bool,
        doc_id: str,
        doc_name: str,
    ) -> WriteResult:
        include_sidecar = self.output_format.get("include_metadata_sidecar", True)

        # 1. Fetch original binary
        binary = self._fetch_binary(row=row, doc_name=doc_name)

        if binary is None:
            return WriteResult(
                doc_id=doc_id,
                doc_name=doc_name,
                success=False,
                error_message=f"Could not fetch binary content for '{doc_name}' from source",
            )

        ext_original = row.get("document_format", "") or Path(doc_name).suffix.lstrip(".")

        # Resolve base path using the template (ext will be replaced per file type)
        base_relative = resolve_path_template(
            template=path_template,
            doc_id=doc_id,
            name=doc_name,
            ext=ext_original,
            hierarchical=hierarchical,
            source_relative_path=_extract_source_relative_path(row),
        )
        base_path = Path(dest_cfg.root_path) / base_relative

        # 2. Write original binary
        adapter.write_document(
            content=binary,
            destination_path=str(base_path),
            overwrite=overwrite,
            config=dest_cfg,
        )

        # 3. Write extracted content file — always "<stem>.content.<ext>" for consistent naming.
        content_str = row.get("content", "") or ""
        content_bytes = content_str.encode("utf-8")
        content_path = base_path.with_name(base_path.stem + f".content.{content_format}")
        adapter.write_document(
            content=content_bytes,
            destination_path=str(content_path),
            overwrite=overwrite,
            config=dest_cfg,
        )

        # 4. Write metadata sidecar JSON
        if include_sidecar:
            raw_metadata = row.get("metadata", "{}")
            try:
                parsed_metadata = json.loads(raw_metadata) if raw_metadata else {}
            except (json.JSONDecodeError, TypeError):
                parsed_metadata = {}

            # Merge scalar row columns (e.g. size, created_time, modified_time from
            # IngestLocalOperator) into parsed_metadata so the sidecar is always complete.
            _top_level_keys = {"id", "name", "document_format", "metadata", "content", "path"}
            for col, val in row.items():
                if col in _top_level_keys:
                    continue
                if val is not None and isinstance(val, (str, int, float, bool)):
                    parsed_metadata.setdefault(col, val)

            sidecar_payload = {
                "id": doc_id,
                "name": doc_name,
                "document_format": row.get("document_format", ""),
                "metadata": parsed_metadata,
            }
            sidecar_bytes = json.dumps(sidecar_payload, ensure_ascii=False).encode("utf-8")
            # Use ".meta.json" to avoid colliding with a source file that is itself a .json file.
            sidecar_path = base_path.with_name(base_path.stem + ".meta.json")
            adapter.write_document(
                content=sidecar_bytes,
                destination_path=str(sidecar_path),
                overwrite=overwrite,
                config=dest_cfg,
            )

        return WriteResult(
            doc_id=doc_id,
            doc_name=doc_name,
            success=True,
            destination_path=str(base_path.parent),
            bytes_written=len(binary),
        )

    def _fetch_binary(self, *, row: dict[str, Any], doc_name: str) -> bytes | None:
        """Fetch binary content for a row using ingest_source from global_config."""
        global_config = {OperatorConstants.Config.INGEST_SOURCE: self.ingest_source}

        return get_binary_content(
            doc_metadata={"path": row.get("path", ""), "name": doc_name},
            global_config=global_config,
        )

    @staticmethod
    def _build_output_table(
        input_table: pa.Table,
        write_results: list[WriteResult],
    ) -> pa.Table:
        """Append write-result columns to the input table, preserving all input columns."""
        num_rows = input_table.num_rows if input_table is not None else 0

        write_status = [r.write_status for r in write_results]
        destination_path = [r.destination_path for r in write_results]
        bytes_written = [r.bytes_written for r in write_results]
        write_error = [r.error_message for r in write_results]

        new_columns = pa.table(
            {
                "bytes_written": pa.array(bytes_written, type=pa.int64()),
                "write_status": pa.array(write_status, type=pa.string()),
                "write_error": pa.array(write_error, type=pa.string()),
                "destination_path": pa.array(destination_path, type=pa.string()),
            }
        )

        if input_table is None or num_rows == 0:
            return new_columns

        for col_name in new_columns.schema.names:
            input_table = input_table.append_column(
                new_columns.schema.field(col_name),
                new_columns.column(col_name),
            )

        return input_table
