"""Mapper functions for converting node statistics between domain models and DTOs."""

import json

from docpipe.api.dto.node_stats_dto import NodeMetadataItem, NodeStatsDto
from docpipe.core.constants.constants import STATUS_INDICATOR_MAP, ExecutionStatus
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.job_management.domain.models import NodeStats

_BORDER = "=" * 64
_THIN = "-" * 64
_END = f">>> {'=' * 61}"


class NodeStatsMapper:
    """Mapper for NodeStats domain models to DTOs."""

    @staticmethod
    def to_dto(node_stats: NodeStats) -> NodeStatsDto:
        """Convert NodeStats domain model to NodeStatsDto."""
        return NodeStatsDto(
            id=node_stats.id,
            name=node_stats.name,
            node_status=node_stats.node_status,
            error=node_stats.error,
            start_time=node_stats.start_time,
            end_time=node_stats.end_time,
            time_taken=node_stats.time_taken or 0,
            col_names=node_stats.col_names or [],
            total_docs=len(node_stats.total_docs) if node_stats.total_docs else 0,
            failed_docs=len(node_stats.failed_docs) if node_stats.failed_docs else 0,
            skipped_docs=len(node_stats.skipped_docs) if node_stats.skipped_docs else 0,
            docs_completed=len(node_stats.docs_completed) if node_stats.docs_completed else 0,
            docs_completed_count=node_stats.docs_completed_count,
            node_metadata=node_stats.node_metadata,
            batch_id=node_stats.batch_id,
            batch_num=node_stats.batch_num,
        )

    @staticmethod
    def to_node_metadata_item(node_id: str, node_stats: NodeStats) -> NodeMetadataItem:
        """Convert NodeStats to NodeMetadataItem DTO."""
        return NodeMetadataItem(
            id=node_id,
            operator=node_stats.name,
            node_metadata=node_stats.node_metadata.get(OperatorConstants.Metadata.NODE_METADATA)
            if node_stats.node_metadata
            else None,
        )

    @staticmethod
    def to_log_string(*, node_id: str, node_stat: NodeStats, batch_stats: dict[str, NodeStats] | None = None) -> str:
        """Format NodeStats into a human-readable log string for API responses."""
        status_value = (
            node_stat.node_status.value if isinstance(node_stat.node_status, ExecutionStatus) else node_stat.node_status
        )
        error = (node_stat.error or "").replace("\n", " ").strip()

        if status_value == ExecutionStatus.SKIPPED.value:
            return NodeStatsMapper._format_skipped(node_id=node_id, name=node_stat.name, error=error)

        return NodeStatsMapper._format_executed(
            node_id=node_id,
            node_stat=node_stat,
            batch_stats=batch_stats,
            status_value=status_value,
            error=error,
        )

    # ── private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _format_skipped(*, node_id: str, name: str, error: str) -> str:
        """Top border + header + skip message. No footer — executor never ran."""
        reason = error if error else "no input data available for processing"
        return "\n".join(
            [
                _BORDER,
                f"  Step: {name}",
                f"  ID:   {node_id}",
                _THIN,
                f"Step ID: {node_id}",
                f"Skipped execution for Step Name: {name} because {reason}",
            ]
        )

    @staticmethod
    def _format_executed(
        *,
        node_id: str,
        node_stat: NodeStats,
        batch_stats: dict[str, NodeStats] | None,
        status_value: str,
        error: str,
    ) -> str:
        """Full block format for completed / failed / in-progress nodes."""
        name = node_stat.name
        time_taken = node_stat.time_taken or 0
        indicator = STATUS_INDICATOR_MAP.get(status_value, "x")

        p: list[str] = []
        p += NodeStatsMapper._section_header(node_id=node_id, name=name)
        p += NodeStatsMapper._section_schema(col_names=node_stat.col_names or [])
        p += NodeStatsMapper._section_batches(batch_stats=batch_stats)
        p += NodeStatsMapper._section_metadata(node_metadata=node_stat.node_metadata)
        p += NodeStatsMapper._section_error(error=error, batch_stats=batch_stats)
        p += NodeStatsMapper._section_footer(
            name=name, time_taken=time_taken, status_value=status_value, indicator=indicator
        )
        return "\n".join(p)

    @staticmethod
    def _section_header(*, node_id: str, name: str) -> list[str]:
        return [_BORDER, f"  Step: {name}", f"  ID:   {node_id}", _THIN, f"Starting execution: Step Name: {name}"]

    @staticmethod
    def _section_schema(*, col_names: list[str]) -> list[str]:
        if not col_names:
            return []
        return ["", "Schema:"] + [f"{col}: string" for col in col_names]

    @staticmethod
    def _section_batches(*, batch_stats: dict[str, NodeStats] | None) -> list[str]:
        if not batch_stats:
            return []
        sorted_batches = sorted(batch_stats.values(), key=lambda b: b.batch_num or 0)
        p = ["", f"Batch Execution Summary ({len(sorted_batches)} batches):"]
        failed: list[NodeStats] = []
        for batch in sorted_batches:
            b_status = (
                batch.node_status.value
                if isinstance(batch.node_status, ExecutionStatus)
                else (batch.node_status or "Pending")
            )
            b_ind = STATUS_INDICATOR_MAP.get(b_status, "x")
            b_time = batch.time_taken or 0
            b_docs = len(batch.total_docs) if batch.total_docs else 0
            p.append(
                f"  {b_ind} Batch {batch.batch_num}: {b_status:<22} ({b_time:.2f}s, {b_docs} doc{'s' if b_docs != 1 else ''})"
            )
            if batch.error and b_status in (ExecutionStatus.FAILED.value, ExecutionStatus.COMPLETED_WITH_ERRORS.value):
                failed.append(batch)
        if failed:
            p += ["", "Error Details:"] + [
                f"  Batch {b.batch_num}: {b.error.replace(chr(10), ' ').strip()}" for b in failed
            ]
        return p

    @staticmethod
    def _section_metadata(*, node_metadata: dict | None) -> list[str]:
        if not node_metadata:
            return []
        inner = node_metadata.get(OperatorConstants.Metadata.NODE_METADATA)
        inner_meta = inner if isinstance(inner, dict) else node_metadata
        if not inner_meta:
            return []
        return ["", "Operator Metadata", json.dumps(inner_meta, indent=4)]

    @staticmethod
    def _section_error(*, error: str, batch_stats: dict[str, NodeStats] | None) -> list[str]:
        """Render a node-level error block for non-batched nodes only.

        For batched nodes (batch_stats is non-empty), per-batch errors are already
        rendered by _section_batches — emitting them here would duplicate output.
        """
        if not error or (batch_stats is not None and len(batch_stats) > 0):
            return []
        return ["", "Error Details", f"  {error}"]

    @staticmethod
    def _section_footer(*, name: str, time_taken: float, status_value: str, indicator: str) -> list[str]:
        verb = "Failed" if status_value == ExecutionStatus.FAILED.value else "Completed"
        return ["", _THIN, f"{indicator} {verb} execution: {name},  time= {time_taken:.2f} seconds", _END]
