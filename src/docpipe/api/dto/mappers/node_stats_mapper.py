import json

from docpipe.api.dto.node_stats_dto import NodeMetadataItem, NodeStatsDto
from docpipe.core.constants.constants import TERMINAL_NODE_STATES, ExecutionStatus
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.core.job_management.domain.models import NodeStats


class NodeStatsMapper:
    """Mapper for NodeStats domain models to DTOs."""

    @staticmethod
    def to_dto(node_stats: NodeStats) -> NodeStatsDto:
        """Convert NodeStats domain model to NodeStatsDto."""
        return NodeStatsDto(
            node_id=node_stats.node_id,
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
    def to_log_string(*, node_id: str, node_stat: NodeStats) -> str:
        """Format NodeStats into a log string for API responses."""
        name = node_stat.name
        time_taken = node_stat.time_taken or 0
        col_names = node_stat.col_names or []
        node_metadata = node_stat.node_metadata
        node_status = node_stat.node_status
        error = node_stat.error

        # Convert TERMINAL_NODE_STATES enum values to strings for comparison if needed
        terminal_states_values = frozenset(state.value for state in TERMINAL_NODE_STATES)

        # Build log string parts in correct sequence
        log_parts = []
        # 1. Starting execution
        log_parts.append(f"Starting execution: Step Name: {name}")

        # 2. Schema information
        if col_names:
            log_parts.append("\nSchema:")
            for col_name in col_names:
                log_parts.append(f"{col_name}: string")

        # 3. Operator metadata if available
        if node_metadata:
            log_parts.append("\nOperator Metadata:")
            log_parts.append(
                json.dumps(
                    {OperatorConstants.Metadata.NODE_METADATA: node_metadata, "id": node_id, "operator": name}, indent=2
                )
            )

        # 4. Completion status (only for terminal states)
        # Handle both enum and string comparison
        status_value = node_status.value if isinstance(node_status, ExecutionStatus) else node_status

        if status_value in terminal_states_values:
            if status_value == ExecutionStatus.FAILED.value:
                log_parts.append(f"\nFailed execution: {name}, time= {time_taken:.2f} seconds")
            elif status_value == ExecutionStatus.SKIPPED.value:
                log_parts.append(f"\nSkipped execution: {name}, time= {time_taken:.2f} seconds")
            else:
                log_parts.append(f"\nCompleted execution: {name}, time= {time_taken:.2f} seconds")

        # 5. Error details if available
        if error:
            log_parts.append("\nError Details:")
            log_parts.append(f"  {error}")

        return "\n".join(log_parts)
