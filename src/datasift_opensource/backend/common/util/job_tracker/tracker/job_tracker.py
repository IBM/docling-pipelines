"""
This module defines the JobTracker, a central Singleton class responsible for managing
the lifecycle, state, and statistics of data processing jobs within the application.
"""

import itertools
import os
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from common.constants.constants import (
    COMPLETED_JOB_STATUSES,
    DatasiftConstants,
    ExecutionStatus,
    Metrics,
)
from common.constants.operator_constants import OperatorConstants
from common.exceptions.datasift_exceptions import DatasiftException
from common.models.session_info import get_session_info, update_session_info
from common.util.common_utils import Singleton
from common.util.datasift_utils import delete_folders
from common.util.iceberg_util import get_warehouse_path
from common.util.job_tracker.model.models import JobStatsDto, NodeStatsDto
from common.util.job_tracker.storage.job_stats_store import JobStatsStore
from common.util.log import get_logger

logger = get_logger()


def _mark_failed_documents(*, job_stats: JobStatsDto, final_docs_status: dict[str, str]):
    """
    Marks documents as 'Failed' if they appear in any node's failed_docs list.

    Args:
        job_stats (JobStatsDto): Job statistics containing node-level data.
        final_docs_status (dict): Dictionary to store final status of each document.
    """
    logger.debug("Marking failed documents...")
    for node_id, node_stat in job_stats.node_stats.items():
        for doc_id in node_stat.failed_docs or []:
            final_docs_status[doc_id] = ExecutionStatus.FAILED.value
            logger.debug(f"Document {doc_id} marked as FAILED from node {node_id}")


def _identify_ingest_and_destination_nodes(*, dag_nodes: list[dict[str, Any]]) -> tuple[str, list[str]]:
    """
    Identifies the ingest node and destination nodes in the DAG.

    Args:
        dag_nodes (list): List of DAG nodes.

    Returns:
        tuple: (ingest_node_id, list of destination_node_ids)
    """
    logger.debug("Identifying ingest and destination nodes...")
    ingest_node_id = None
    destination_node_ids = []
    for node in dag_nodes:
        if not node.get(DatasiftConstants.INPUT_EDGES):
            ingest_node_id = node[OperatorConstants.Columns.ID]
            logger.debug(f"Ingest node identified: {ingest_node_id}")
        if not node.get(DatasiftConstants.OUTPUT_EDGES):
            destination_node_ids.append(node[OperatorConstants.Columns.ID])
            logger.debug(f"Destination node identified: {node[OperatorConstants.Columns.ID]}")
    return ingest_node_id, destination_node_ids


def _mark_completed_documents(
    *,
    job_stats: JobStatsDto,
    destination_node_ids: list[str],
    final_docs_status: dict[str, str],
):
    """
    Marks documents as 'Completed' if they reach any destination node and are not already marked as 'Failed'.

    Args:
        job_stats (JobStatsDto): Job statistics containing node-level data.
        destination_node_ids (list): List of destination node IDs.
        final_docs_status (dict): Dictionary to store final status of each document.
    """
    logger.debug("Marking completed documents...")
    for node_id in destination_node_ids:
        node_stat = job_stats.node_stats.get(node_id)
        if not node_stat:
            return

        for doc_id in node_stat.docs_completed or []:
            if doc_id not in final_docs_status:
                final_docs_status[doc_id] = ExecutionStatus.COMPLETED.value
                logger.debug(f"Document {doc_id} marked as COMPLETED from node {node_id}")


def _mark_skipped_documents(*, job_stats: JobStatsDto, ingest_node_id: str, final_docs_status: dict[str, str]):
    """
    Marks documents as 'Skipped' if they were part of the run but not marked as 'Failed' or 'Completed'.

    Args:
        job_stats (JobStatsDto): Job statistics containing node-level data.
        ingest_node_id (str): ID of the ingest node.
        final_docs_status (dict): Dictionary to store final status of each document.
    """
    logger.debug("Marking skipped documents...")
    ingest_node = job_stats.node_stats.get(ingest_node_id)
    total_docs = ingest_node.total_docs if ingest_node else []
    for doc_id in total_docs or []:
        if doc_id not in final_docs_status:
            final_docs_status[doc_id] = ExecutionStatus.SKIPPED.value
            logger.debug(f"Document {doc_id} marked as SKIPPED")


def _update_job_stats_counts(*, job_stats: JobStatsDto, final_docs_status: dict[str, str]):
    """
    Updates the processed, failed, and skipped document counts in job_stats.

    Args:
        job_stats (JobStatsDto): Job statistics object to update.
        final_docs_status (dict): Dictionary containing final status of each document.
    """
    logger.debug("Updating job statistics counts...")
    final_counts = Counter(final_docs_status.values())
    job_stats.processed_docs = final_counts.get(ExecutionStatus.COMPLETED.value, 0)
    job_stats.failed_docs = final_counts.get(ExecutionStatus.FAILED.value, 0)
    job_stats.skipped_docs = final_counts.get(ExecutionStatus.SKIPPED.value, 0)
    logger.info(
        f"Updated job stats: processed={job_stats.processed_docs}, failed={job_stats.failed_docs}, skipped={job_stats.skipped_docs}"
    )


def _log_inconsistencies(*, job_stats: JobStatsDto):
    """
    Logs inconsistencies in document counts if the total does not match the sum of processed, failed, and skipped.

    Args:
        job_stats (JobStatsDto): Job statistics object to validate.
    """
    # If job_stats is None, log warning and return early
    if job_stats is None:
        logger.warning("Cannot log: job_stats is None")
        return

    total = job_stats.total_docs
    sum_parts = job_stats.processed_docs + job_stats.failed_docs + job_stats.skipped_docs
    if total != sum_parts:
        logger.error(
            f"Total number of docs {total} does not match the sum of processed ({job_stats.processed_docs}), "
            f"skipped ({job_stats.skipped_docs}), and failed ({job_stats.failed_docs}) docs.",
            extra={DatasiftConstants.JOB_RUN_ID: job_stats.job_run_id},
        )


class JobTracker(metaclass=Singleton):
    """
    A Singleton class that manages and tracks the state of all data processing jobs.

    This class acts as a central repository for job statistics, handling their creation,
    updating, and persistence. It maintains an in-memory cache for active jobs and
    delegates storage to a persistent JobStatsStore.
    """

    def __init__(self) -> None:
        """Initializes the JobTracker."""
        # A thread-safe counter for generating unique job IDs, although not currently used.
        self.next_job_id = itertools.count()
        next(self.next_job_id)  # Initialize the counter to start from 1.

        # In-memory cache for JobStatsDto objects, keyed by job_run_id.
        self.all_jobs: dict[str, JobStatsDto] = {}

        # Internal mapping of a job_run_id to its active orchestrator instance.
        # This is necessary for operations like cancellation.
        self.__jobs_to_orchestrator = {}

    def get_job(self, job_run_id: str | None, use_local_cache: bool = False) -> JobStatsDto | None:
        """
        Retrieves job statistics for a given job_run_id.

        It first checks the in-memory cache. If not found, it queries the
        persistent storage layer. It also fetches and attaches associated node stats.

        :param job_run_id: The unique identifier for the job run.
        :param use_local_cache: Flag to check if stats should be fetched from local cache or not. Default is false
        :return: A JobStatsDto object if found, otherwise None.
        """
        logger.info(f"Getting job stats by job_run_id: {job_run_id}")
        return self.all_jobs.get(job_run_id, None)

    @staticmethod
    def store_job_stats(job_stats: JobStatsDto):
        """
        Persists the given JobStatsDto object to the configured storage layer.

        :param job_stats: The job statistics object to store.
        """
        logger.info("Storing job stats")
        # Delegate to the abstract storage layer.
        JobStatsStore.get_job_stats_store().store_job_stats(job_stats, merge=False)

    def cancel_job_run_if_cancelling(self, job_run_id: str) -> bool:
        """
        Checks if a job is in the 'CANCELING' state and, if so, finalizes it as 'CANCELED'.

        :param job_run_id: The unique identifier for the job run.
        :return: True if the job was canceled, False otherwise.
        """
        job_stats = self.get_job(job_run_id)
        if job_stats is None:
            logger.warning(f"No job stats found for job_run_id: {job_run_id}")
            return False

        # If the job is already marked for cancellation, finalize the process.
        if ExecutionStatus(job_stats.status) == ExecutionStatus.CANCELING:
            self.end_job(job_run_id, status=ExecutionStatus.CANCELED, message="Job run Canceled")
            return True
        else:
            return False

    def start_tracking_job(self, orchestrator, job_id: str, job_run_id: str):
        """
        Starts tracking a new job, creating its initial statistics record.

        This method creates the initial JobStatsDto, sets its status to RUNNING,
        and stores it in both the in-memory cache and the persistent store.

        :param orchestrator: The orchestrator instance managing this job.
        :param job_id: The identifier for the job definition.
        :param job_run_id: The unique identifier for this specific run.
        """
        # Local imports to avoid potential circular dependency issues.
        from common.models.session_info import SessionInfo, get_session_info

        session_info: SessionInfo = get_session_info()
        # Map the run ID to the orchestrator instance to enable cancellation.
        self.__jobs_to_orchestrator[job_run_id] = orchestrator

        orchestrator_type = orchestrator.get_type()

        # Create the initial statistics object for the new job run.
        stat = JobStatsDto(
            job_id=job_id,
            job_run_id=job_run_id,
            start_time=round(datetime.now().timestamp()),
            status=ExecutionStatus.RUNNING,
            orchestrator=orchestrator_type,
            heartbeat_timestamp=round(datetime.now().timestamp()),
            flow_id=session_info.flow_id,
        )
        # Add to the in-memory cache and persist.
        self.all_jobs[job_run_id] = stat
        self.store_job_stats(stat)

        logger.info(
            f"Job started, job_id: {job_id}, job_run_id: {job_run_id}",
            extra={
                DatasiftConstants.JOB_ID: job_id,
                DatasiftConstants.JOB_RUN_ID: job_run_id,
            },
        )

    def update_doc_counts(self, job_run_id, metadata, operator_category):
        """
        Updates the document counts for a job based on pipeline mode (branching or non-branching).

        :param job_run_id: The unique identifier for the job run.
        :param metadata: A dictionary containing metrics from an operator.
        :param operator_category: The category of the operator (e.g., "Ingest").
        """
        session_info = get_session_info()

        # Separate aggregation metrics from replacement metrics
        increments = {}
        updates = {}

        if Metrics.External.TOTAL_DOCS in metadata and operator_category == "Ingest":
            updates["total_docs"] = metadata[Metrics.External.TOTAL_DOCS]

        if Metrics.External.TOTAL_PAGES_CONVERTED in metadata:
            increments["total_pages_processed"] = metadata[Metrics.External.TOTAL_PAGES_CONVERTED]
            updates["execution_time"] = int(datetime.now(UTC).timestamp())

        if Metrics.External.DELETED_DOC_COUNT in metadata:
            increments["deleted_doc_count"] = metadata[Metrics.External.DELETED_DOC_COUNT]

        # Only proceed if at least one metric was updated
        if not increments and not updates:
            return

        # Add metadata to updates
        updates["heartbeat_timestamp"] = round(datetime.now().timestamp())
        updates["flow_id"] = session_info.flow_id

        # Use atomic increment for thread-safe aggregation
        JobStatsStore.get_job_stats_store().atomic_increment_fields(
            job_run_id=job_run_id, increments=increments, updates=updates
        )

        # Update in-memory cache
        stat = self.get_job(job_run_id=job_run_id)
        if stat:
            # Apply increments to in-memory stats
            for field, value in increments.items():
                current_value = getattr(stat, field, 0)
                setattr(stat, field, current_value + value)
            # Apply updates to in-memory stats
            for field, value in updates.items():
                setattr(stat, field, value)
            self.all_jobs[job_run_id] = stat

        logger.info(f"Document count updated for the job_run_id: {job_run_id}")
        _log_inconsistencies(job_stats=stat)

    def update_node_stats(self, job_run_id: str, node_id: str, node_stats: dict):
        """
        Updates or creates statistics for a specific node within a job run.

        :param job_run_id: The unique identifier for the job run.
        :param node_id: The identifier for the node within the job.
        :param node_stats: A dictionary of statistics for the node.
        """
        stat = self.get_job(job_run_id=job_run_id)

        # If no job stats found, log warning and return early
        if stat is None:
            logger.warning(f"No job stats found for job_run_id: {job_run_id}. Cannot update node stats.")
            return

        # Get the existing node stats or create an empty dict if it's the first update.
        existing_node = stat.node_stats.get(node_id)
        if isinstance(existing_node, NodeStatsDto):
            base_stats = existing_node.model_dump()
        else:
            base_stats = existing_node or {}
        # Merge with new stats and ensure node_id is set
        target_node_stats = base_stats | node_stats | {"node_id": node_id}

        # Convert the raw dictionary into a structured DTO before persisting.
        data = NodeStatsDto(
            id=str(target_node_stats.get("node_id", node_id)),
            name=str(target_node_stats.get("name", f"name-{node_id}")),
            start_time=int(target_node_stats.get("start_time", 0.0)),
            end_time=int(target_node_stats.get("end_time", 0.0)),
            node_status=str(target_node_stats.get("node_status", "Unknown")),
            time_taken=int(target_node_stats.get("time_taken", 0.0)),
            col_names=target_node_stats.get("col_names", []),
            total_docs=target_node_stats.get("total_docs", []),
            failed_docs=target_node_stats.get("failed_docs", []),
            skipped_docs=target_node_stats.get("skipped_docs", []),
            docs_completed=target_node_stats.get("docs_completed", []),
            docs_completed_count=int(target_node_stats.get("docs_completed_count", 0)),
            node_metadata=target_node_stats.get("node_metadata", {}),
            error=str(target_node_stats.get("error", "")),
        )
        # Update in-memory node_stats for CMDLINE mode
        stat.node_stats[node_id] = data
        JobStatsStore.get_job_stats_store().store_node_stats(stat.job_id, job_run_id, data)
        logger.info(
            f"Node stats added for the job, job_run_id: {job_run_id}, node_id: {node_id}",
            extra={
                DatasiftConstants.JOB_ID: stat.job_id,
                DatasiftConstants.JOB_RUN_ID: job_run_id,
            },
        )

    def request_delete_job_run(self, *, job_run_id):
        logger.info(f"Requesting Deletion for job_run_id: {job_run_id}")

        log_location_path = get_warehouse_path(path="")
        log_app_location = DatasiftConstants.UDP_LOGS
        jobs_stats_path = DatasiftConstants.JOBS_STATS_PATH
        node_stats_path = DatasiftConstants.NODE_STATS_PATH
        stat = self.get_job(job_run_id=job_run_id)
        if not stat:
            raise DatasiftException(f"Could not find stats for job run ID: {job_run_id}", 400)
        job_id = stat.job_id
        log_final_path = os.path.join(log_location_path, log_app_location, job_id, job_run_id)
        data_job_id = os.path.join(log_location_path, job_id, job_run_id)
        job_stats = os.path.join(get_warehouse_path(path=""), jobs_stats_path, job_id, job_run_id)
        node_stats = os.path.join(get_warehouse_path(path=""), node_stats_path, job_id, job_run_id)
        del_folders = [log_final_path, data_job_id, job_stats, node_stats]
        delete_folders(paths_list=del_folders)
        return "Job run details deleted"

    def request_cancel_job(self, job_run_id) -> JobStatsDto:
        """
        Initiates the cancellation process for a running job.

        This sets the job's status to 'CANCELING' and triggers the orchestrator's
        cancellation logic.

        :param job_run_id: The unique identifier for the job run to cancel.
        :raises DatasiftException: If the job is not found or is in an invalid state.
        :return: The updated JobStatsDto.
        """
        from common.exceptions.datasift_exceptions import DatasiftException

        logger.info(f"Requesting cancellation for job_run_id: {job_run_id}")
        # jobs_client = JobsClient()
        session_info = get_session_info()
        persistent_store_stat = self.get_job(job_run_id=job_run_id)
        if not persistent_store_stat:
            raise DatasiftException(f"Could not find job id for job run ID: {job_run_id}", 400)
        # if not persistent_store_stat:
        #     # If job stats don't exist yet but job run is being cancelled,
        #     # Get job_id from Jobs Framework and assume that job run is in 'QUEUED' state
        #     job_id = _get_job_id_from_jobframework(job_run_id=job_run_id)
        #
        #     if not job_id:
        #         raise DatasiftException(f"Could not find job id for job run ID: {job_run_id}", 400)
        #
        #     persistent_store_stat = JobStatsDto(job_id=job_id, job_run_id=job_run_id, status=ExecutionStatus.QUEUED)
        #     update_session_info(job_id=job_id)

        common_log_arguments = {
            DatasiftConstants.JOB_ID: persistent_store_stat.job_id,
            DatasiftConstants.JOB_RUN_ID: job_run_id,
        }
        logger.info(
            f"Job run {job_run_id} associated with job {persistent_store_stat.job_id} is in {persistent_store_stat.status} state in persistent store",
            extra=common_log_arguments,
        )

        # job_run_response = jobs_client.get_job_run()
        # jobs_framework_state = job_run_response.get(OperatorConstants.Misc.ENTITY, {}).get(DatasiftConstants.JOB_RUN,
        #                                                                               {}).get(DatasiftConstants.STATE, ExecutionStatus.QUEUED.value)

        # Use pattern matching to handle different job states.
        match persistent_store_stat.status:
            # These are states from which cancellation is possible.
            case (
                ExecutionStatus.RUNNING.value
                | ExecutionStatus.STARTING.value
                | ExecutionStatus.PAUSED.value
                | ExecutionStatus.QUEUED.value
                | ExecutionStatus.RESUMING.value
            ):
                # If we have a reference to the orchestrator, ask it to cancel.
                if job_run_id in self.__jobs_to_orchestrator:
                    orchestrator = self.__jobs_to_orchestrator[job_run_id]
                    orchestrator.cancel()
                # Set the status to CANCELING to signify the process has started.
                persistent_store_stat.status = ExecutionStatus.CANCELING
                # Update the jobs framework to have state as CANCELING
                # jobs_client.update_job_run_status(status=persistent_store_stat.status,
                #                                   message=f"Cancelling job run {job_run_id}")
            # These are terminal states where cancellation is no longer possible.
            case (
                ExecutionStatus.COMPLETED.value
                | ExecutionStatus.CANCELED.value
                | ExecutionStatus.CANCELING.value
                | ExecutionStatus.FAILED.value
                | ExecutionStatus.SKIPPED.value
                | ExecutionStatus.COMPLETED_WITH_ERRORS.value
                | ExecutionStatus.COMPLETED_WITH_WARNINGS.value
            ):
                # check if state in Jobs Framework is same as in persistent store
                # if persistent_store_stat.status.value.lower() != jobs_framework_state.lower():
                #     logger.info(f"Updating state in jobs framework from {jobs_framework_state} to {persistent_store_stat.status.value}")
                #     jobs_client.update_job_run_status(status=persistent_store_stat.status,
                #                                       message=f"Updating job run {job_run_id} to state {persistent_store_stat.status.value}")
                logger.info(
                    f"Skipping cancellation since job run is already in {persistent_store_stat.status} state",
                    extra=common_log_arguments,
                )
                return persistent_store_stat
            # Handle any unexpected states.
            case _:
                raise DatasiftException(f"Job run is in invalid status: {persistent_store_stat.status}", 400)

        persistent_store_stat.heartbeat_timestamp = round(datetime.now().timestamp())
        persistent_store_stat.flow_id = session_info.flow_id
        self.store_job_stats(persistent_store_stat)
        return persistent_store_stat

    def end_job(
        self,
        job_run_id,
        status: ExecutionStatus = ExecutionStatus.COMPLETED,
        message=None,
    ):
        """
        Finalizes a job run, setting its terminal status and calculating duration.

        :param job_run_id: The unique identifier for the job run.
        :param status: The final status to set (e.g., COMPLETED, FAILED, CANCELED).
        :param message: An optional final message for the job.
        :raises DatasiftException: If the job is not found.
        """
        from common.exceptions.datasift_exceptions import DatasiftException

        # Clean up the orchestrator mapping as the job is no longer active.
        self.__jobs_to_orchestrator.pop(job_run_id, None)
        stat = self.get_job(job_run_id=job_run_id)
        if stat is None:
            raise DatasiftException(f"Stats not found for job_run_id: {job_run_id}")

        session_info = get_session_info()
        common_log_arguments = {
            DatasiftConstants.JOB_ID: stat.job_id,
            DatasiftConstants.JOB_RUN_ID: job_run_id,
        }

        # Only update status if the job is not already in a terminal state.
        if stat.status not in COMPLETED_JOB_STATUSES:
            stat.status = status
        if message is not None:
            stat.message = message

        # Calculate the total duration of the job run.
        if stat.start_time:
            stat.end_time = round(datetime.now().timestamp())
            stat.duration = stat.end_time - stat.start_time

        stat.heartbeat_timestamp = round(datetime.now().timestamp())
        stat.flow_id = session_info.flow_id

        self.all_jobs[job_run_id] = stat
        self.store_job_stats(stat)
        logger.warning(f"Job ended, job_run_id: {job_run_id}", extra=common_log_arguments)

    def is_job_run_complete(self, job_run_id: str) -> bool:
        """
        Checks if a job run has reached any terminal state.

        :param job_run_id: The unique identifier for the job run.
        :return: True if the job is complete, failed, or canceled. False otherwise.
        """
        job_stats = self.get_job(job_run_id=job_run_id)
        if job_stats is None:
            return False

        return job_stats.status in COMPLETED_JOB_STATUSES

    def determine_and_update_final_documents_count(self, *, job_stats: JobStatsDto, dag_nodes: list[dict[str, Any]]):
        """
        Determines the final status of each document in a DAG flow and updates job statistics.

        Documents are classified as:
        - 'Failed' if they appear in any node's failed_docs.
        - 'Completed' if they reach any destination node and are not failed.
        - 'Skipped' if they were part of the run but neither failed nor completed.

        Updates processed, failed, and skipped document counts in job_stats.
        Also persists the updated job stats and logs inconsistencies in document counts.

        Args:
            job_stats (JobStatsDto): Object containing job metadata and node-level statistics.
            dag_nodes (list[dict]): List of DAG nodes with input/output edges.
        """
        logger.info(f"Starting final document status determination for job_run_id: {job_stats.job_run_id}")
        final_docs_status: dict[str, str] = {}
        session_info = get_session_info()
        _mark_failed_documents(job_stats=job_stats, final_docs_status=final_docs_status)
        ingest_node_id, destination_node_ids = _identify_ingest_and_destination_nodes(dag_nodes=dag_nodes)
        _mark_completed_documents(
            job_stats=job_stats,
            destination_node_ids=destination_node_ids,
            final_docs_status=final_docs_status,
        )
        _mark_skipped_documents(
            job_stats=job_stats,
            ingest_node_id=ingest_node_id,
            final_docs_status=final_docs_status,
        )
        _update_job_stats_counts(job_stats=job_stats, final_docs_status=final_docs_status)
        job_stats.heartbeat_timestamp = round(datetime.now().timestamp())
        job_stats.flow_id = session_info.flow_id
        self.all_jobs[job_stats.job_run_id] = job_stats
        self.store_job_stats(job_stats)
        _log_inconsistencies(job_stats=job_stats)
        logger.info(f"Completed final document status update for job_run_id: {job_stats.job_run_id}")
