import json

from docpipe.api.dto.node_stats_dto import NodeMetadataItem, NodeStatsDto
from docpipe.core.constants.constants import STATUS_INDICATOR_MAP, TERMINAL_NODE_STATES, ExecutionStatus
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.job_management.domain.models import NodeStats


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
    def _build_batch_summary(batch_stats: dict[str, NodeStats]) -> list[str]:
        """Build batch execution summary lines from per-batch NodeStats."""
        if not batch_stats:
            return []

        sorted_batches = sorted(
            batch_stats.values(),
            key=lambda b: b.batch_num or 0,
        )

        lines: list[str] = [f"\nBatch Execution Summary ({len(sorted_batches)} batches):"]
        failed_batches: list[NodeStats] = []

        for batch in sorted_batches:
            status = batch.node_status or "Pending"
            indicator = STATUS_INDICATOR_MAP.get(status, "•")
            time_taken = batch.time_taken or 0
            doc_count = len(batch.total_docs) if batch.total_docs else 0
            doc_suffix = "s" if doc_count != 1 else ""
            batch_line = (
                f"  {indicator} Batch {batch.batch_num}: {status} ({time_taken:.2f}s, {doc_count} doc{doc_suffix})"
            )
            if status == ExecutionStatus.SKIPPED.value and batch.error:
                batch_line += f" - Reason: {batch.error}"
            lines.append(batch_line)
            if status in (ExecutionStatus.FAILED.value, ExecutionStatus.COMPLETED_WITH_ERRORS.value) and batch.error:
                failed_batches.append(batch)

        if failed_batches:
            lines.append("\nError Details:")
            for batch in failed_batches:
                lines.append(f"  Batch {batch.batch_num}: {batch.error}")

        return lines

    @staticmethod
    def to_log_string(*, node_id: str, node_stat: NodeStats, batch_stats: dict[str, NodeStats] | None = None) -> str:
        """Format NodeStats into a log string for API responses.

        Args:
            node_id: Node identifier.
            node_stat: Aggregated NodeStats for the node.
            batch_stats: Optional dict[batch_id, NodeStats] for micro-batching nodes.
        """
        name = node_stat.name
        time_taken = node_stat.time_taken or 0
        col_names = node_stat.col_names or []
        node_metadata = node_stat.node_metadata
        node_status = node_stat.node_status
        error = node_stat.error

        terminal_states_values = frozenset(state.value for state in TERMINAL_NODE_STATES)

        log_parts = []
        # 1. Starting execution
        log_parts.append(f"Starting execution: Step Name: {name}")

        # 2. Schema information
        if col_names:
            log_parts.append("\nSchema:")
            for col_name in col_names:
                log_parts.append(f"{col_name}: string")

        # 3. Batch execution summary (micro-batching nodes only)
        if batch_stats:
            log_parts.extend(NodeStatsMapper._build_batch_summary(batch_stats))

        # 4. Operator metadata if available
        if node_metadata:
            log_parts.append("\nOperator Metadata:")
            log_parts.append(
                json.dumps(
                    {OperatorConstants.Metadata.NODE_METADATA: node_metadata, "id": node_id, "operator": name}, indent=2
                )
            )

        # 5. Completion status (only for terminal states)
        status_value = node_status.value if isinstance(node_status, ExecutionStatus) else node_status

        if status_value in terminal_states_values:
            if status_value == ExecutionStatus.FAILED.value:
                log_parts.append(f"\nFailed execution: {name}, time= {time_taken:.2f} seconds")
            elif status_value == ExecutionStatus.SKIPPED.value:
                log_parts.append(f"\nSkipped execution: {name}, time= {time_taken:.2f} seconds")
            else:
                log_parts.append(f"\nCompleted execution: {name}, time= {time_taken:.2f} seconds")

        # 6. Error details if available
        if error:
            log_parts.append("\nError Details:")
            log_parts.append(f"  {error}")

        return "\n".join(log_parts)
