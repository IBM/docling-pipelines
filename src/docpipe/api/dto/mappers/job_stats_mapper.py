from docpipe.api.dto.job_run_dto import JobRunStatusResponse
from docpipe.api.dto.job_stats_dto import JobStatsDto
from docpipe.core.job_management.domain.models import JobStats

from .node_stats_mapper import NodeStatsMapper


class JobStatsMapper:
    """Mapper for JobStats domain models to DTOs."""

    @staticmethod
    def to_dto(job_stats: JobStats) -> JobStatsDto:
        """Convert JobStats domain model to JobStatsDto."""
        # Convert nested node_stats
        node_stats_dto = {node_id: NodeStatsMapper.to_dto(stats) for node_id, stats in job_stats.node_stats.items()}

        # Convert nested batch_node_stats
        batch_node_stats_dto = {
            node_id: {batch_id: NodeStatsMapper.to_dto(stats) for batch_id, stats in batch_stats.items()}
            for node_id, batch_stats in job_stats.batch_node_stats.items()
        }

        return JobStatsDto(
            job_id=job_stats.job_id,
            job_run_id=job_stats.job_run_id,
            status=job_stats.status,
            message=job_stats.message,
            start_time=job_stats.start_time,
            end_time=job_stats.end_time,
            duration=job_stats.duration,
            heartbeat_timestamp=job_stats.heartbeat_timestamp,
            total_docs=job_stats.total_docs,
            processed_docs=job_stats.processed_docs,
            completed_docs=job_stats.completed_docs,
            failed_docs=job_stats.failed_docs,
            skipped_docs=job_stats.skipped_docs,
            deleted_doc_count=job_stats.deleted_doc_count,
            total_pages_processed=job_stats.total_pages_processed,
            page_type_stats=job_stats.page_type_stats,
            execution_time=job_stats.execution_time,
            orchestrator=job_stats.orchestrator,
            container_kind=job_stats.container_kind,
            container_id=job_stats.container_id,
            flow_id=job_stats.flow_id,
            user_id=job_stats.user_id,
            account_id=job_stats.account_id,
            user_entitlements=job_stats.user_entitlements,
            node_stats=node_stats_dto,
            batch_node_stats=batch_node_stats_dto,
        )

    @staticmethod
    def to_status_response(job_stats: JobStats, include_logs: bool = False) -> JobRunStatusResponse:
        """
        Convert JobStats domain model to a JobRunStatusResponse DTO.

        Args:
            job_stats: JobStats domain model
            include_logs: Whether to include individual node log strings as dynamic fields

        Returns:
            JobRunStatusResponse DTO ready for API response
        """
        from docpipe.api.dto.job_run_dto import JobRunStatusResponse

        # Calculate node_sequence (execution order based on start_time)
        sorted_nodes = sorted(
            job_stats.node_stats.items(),
            key=lambda item: (item[1].start_time, item[1].end_time, item[1].name),
        )
        node_sequence = [node_id for node_id, _ in sorted_nodes]

        # Build node_metadata array
        node_metadata = [
            NodeStatsMapper.to_node_metadata_item(node_id, stats) for node_id, stats in job_stats.node_stats.items()
        ]

        # Convert to DTO
        job_stats_dto = JobStatsMapper.to_dto(job_stats)

        response = JobRunStatusResponse(
            node_sequence=node_sequence, job_stats=job_stats_dto, node_metadata=node_metadata
        )

        # Add individual node log strings as dynamic fields (only if include_logs=True)
        if include_logs:
            for node_id in node_sequence:
                if node_id in job_stats.node_stats:
                    node_stat = job_stats.node_stats[node_id]
                    log_str = NodeStatsMapper.to_log_string(node_id=node_id, node_stat=node_stat)
                    # Set dynamic attribute on the Pydantic model
                    setattr(response, node_id, log_str)

        return response
