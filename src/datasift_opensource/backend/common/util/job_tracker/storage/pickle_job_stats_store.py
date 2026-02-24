import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from filelock import FileLock
from datasift_opensource.backend.common.util.constants import DatasiftConstants
from datasift_opensource.backend.common.util.iceberg_util import get_warehouse_path
from datasift_opensource.backend.common.util.job_tracker.model.models import NodeStatsDto, JobStatsDto
from datasift_opensource.backend.common.util.job_tracker.storage.job_stats_store import JobStatsStore
from datasift_opensource.backend.common.util.log import get_logger

logger = get_logger()


def _lock_path(path: str) -> str:
    return f"{path}.lock"


def _get_job_run_pickle_file(file_path: str, file_lock_needed: bool = False) -> dict[str, Any] | None:
    import pickle
    path = Path(file_path)
    if not path.exists():
        logger.warning(f"Unable to locate the file {file_path}.")
        return None
    logger.debug(
        f"File {file_path} successfully found.")
    if file_lock_needed:
        with FileLock(_lock_path(file_path)):
            with open(file_path, "rb") as file:
                return pickle.load(file)
    else:
        with open(file_path, "rb") as file:
            return pickle.load(file)


def _save_job_run_pickle_file(data: dict[str, Any], json_data: str, file_path: str,
                              file_lock_needed: bool = False):
    import pickle
    # Ensure parent directory exists
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    if file_lock_needed:
        with FileLock(_lock_path(file_path)):
            with open(file_path, "wb") as file:
                pickle.dump(data, file)
    else:
        with open(file_path, "wb") as file:
            pickle.dump(data, file)


def _construct_job_run_job_stats_pickle_file_path(job_id: str, job_run_id: str):
    return os.path.join(get_warehouse_path(path=""), PickleJobStatsStore.JOBS_STATS_PATH, job_id, job_run_id,
                        PickleJobStatsStore.JOB_RUN_TO_JOB_STATS_PICKLE_FILE)


def _construct_job_run_node_stats_pickle_file_path(job_id: str, job_run_id: str):
    return os.path.join(get_warehouse_path(path=""), PickleJobStatsStore.NODE_STATS_PATH, job_id, job_run_id,
                        PickleJobStatsStore.JOB_RUN_TO_NODE_STATS_PICKLE_FILE)


def _construct_job_run_to_job_id_pickle_file_path():
    return os.path.join(get_warehouse_path(path=""), PickleJobStatsStore.JOB_RUN_TO_JOB_ID_PICKLE_FILE)


@lru_cache(maxsize=128)
def _get_job_id_for_job_run_cache(job_run_id: str):
    job_run_to_job_id_pickle_file_path = _construct_job_run_to_job_id_pickle_file_path()
    job_run_id_to_job_id_map: dict[str, str] | None = _get_job_run_pickle_file(
        file_path=job_run_to_job_id_pickle_file_path)
    if job_run_id_to_job_id_map is None:
        raise ValueError(f"Do not cache: No mapping file found for job_run_id '{job_run_id}'")
    job_id = job_run_id_to_job_id_map.get(job_run_id)

    common_log_arguments = {DatasiftConstants.JOB_ID: job_id, DatasiftConstants.JOB_RUN_ID: job_run_id}
    if job_id is None:
        logger.info(
            f"Not found any job_run_id record in the file {job_run_to_job_id_pickle_file_path} in bucket",
            extra=common_log_arguments)
        raise ValueError(f"Do not cache: No mapping file found for job_run_id '{job_run_id}'")
    logger.info(f"Successfully Fetched job_id for the job_run_id {job_run_id} job_id is {job_id}",
                extra=common_log_arguments)
    return job_id


def _get_job_id_for_job_run(job_run_id: str):
    """
    Retrieve the job_id associated with the given job_run_id from a cache.

    If the job_id is not found, None is returned.
    """
    try:
        job_id = _get_job_id_for_job_run_cache(job_run_id=job_run_id)
        return job_id
    except ValueError as exc:
        logger.error(msg=str(exc))
        return None
    except Exception as exc:
        logger.error(
            f"An error occurred while getting job id: {str(exc)}",
            exc_info=True, stack_info=True, extra={DatasiftConstants.JOB_RUN_ID: job_run_id})
        return None

class PickleJobStatsStore(JobStatsStore):
    JOB_RUN_TO_JOB_STATS_PICKLE_FILE = "job_run_to_job_stats.pkl"
    JOB_RUN_TO_NODE_STATS_PICKLE_FILE = "job_run_to_node_stats.pkl"
    JOB_RUN_TO_JOB_ID_PICKLE_FILE = "jobrunid-to-jobid.pkl"
    JOBS_STATS_PATH = "job-stats"
    NODE_STATS_PATH = "node-stats"
    JOB_METADATA = "job-metadata"

    @staticmethod
    def store_job_id(job_id: str, job_run_id: str):
        """
        Store the mapping of job_run_id to job_id in a pickle file.

        If the file does not exist, it will be created. If it exists, the job_id to job_run_id mapping will be updated.
        """
        common_log_arguments = {DatasiftConstants.JOB_ID: job_id, DatasiftConstants.JOB_RUN_ID: job_run_id}
        try:
            job_run_to_job_id_pickle_file_path = _construct_job_run_to_job_id_pickle_file_path()
            file_response: dict[str, str] | None = _get_job_run_pickle_file(
                file_path=job_run_to_job_id_pickle_file_path)
            job_run_to_job_id_map: dict[str, str] = dict()
            if file_response is None:
                logger.info(
                    f"File {job_run_to_job_id_pickle_file_path} not found",
                    extra=common_log_arguments)
            else:
                logger.info(
                    f"File {job_run_to_job_id_pickle_file_path} successfully found. Updating the job ID to job run ID mapping for job ID {job_id} and job run ID {job_run_id} in the pickle file.",
                    extra=common_log_arguments)
                job_run_to_job_id_map = file_response
            job_run_to_job_id_map[job_run_id] = job_id
            _save_job_run_pickle_file(data=job_run_to_job_id_map, json_data=json.dumps(job_run_to_job_id_map),
                                      file_path=job_run_to_job_id_pickle_file_path,
                                      file_lock_needed=True)
            logger.info(
                f"Successfully updated job ID to job run ID mapping for job ID {job_id} and job run ID {job_run_id} stored at {job_run_to_job_id_pickle_file_path}.",
                extra=common_log_arguments)
        except Exception as exc:
            logger.error(
                f"An error occurred while storing job id: {str(exc)}",
                exc_info=True, stack_info=True, extra=common_log_arguments)

    def store_job_stats(self, job_stats: JobStatsDto, merge = True):
        common_log_arguments = {DatasiftConstants.JOB_ID: job_stats.job_id,
                                DatasiftConstants.JOB_RUN_ID: job_stats.job_run_id}
        job_id = job_stats.job_id
        job_run_id = job_stats.job_run_id
        job_run_pickle_file_path = _construct_job_run_job_stats_pickle_file_path(job_id=job_id,
                                                                                 job_run_id=job_run_id)
        file_response: dict[str, JobStatsDto] | None = _get_job_run_pickle_file(file_path=job_run_pickle_file_path)
        job_run_to_job_stats: dict[str, JobStatsDto] = dict()

        if merge:
            # check if the statistics for this job run already exist
            old_stats = file_response.get(job_run_id) if file_response else None
            if old_stats:
                job_stats = JobStatsStore._roll_up_stats(old_stats, job_stats)

        if file_response is None:
            logger.debug(f"File {job_run_pickle_file_path} not found",
                         extra=common_log_arguments)
        else:
            logger.debug(
                f"File {job_run_pickle_file_path} successfully found. Updating job stats for job ID {job_id} and job run ID {job_run_id}.",
                extra=common_log_arguments)  # Handle successful
            job_run_to_job_stats = file_response
        job_run_to_job_stats[job_run_id] = job_stats
        json_data = json.dumps({
            key: value.model_dump() if isinstance(value, JobStatsDto) else value
            for key, value in job_run_to_job_stats.items()
        })
        _save_job_run_pickle_file(data=job_run_to_job_stats, json_data=json_data,
                                  file_path=job_run_pickle_file_path)

    def get_job_stats(self, job_run_id: str, cloud_client = None) -> JobStatsDto | None:
        logger.info(f"Getting job stats from Pickle job stats by job_run_id: {job_run_id}")
        try:
            job_id = _get_job_id_for_job_run(job_run_id=job_run_id)
            if job_id is None:
                logger.warning(f"Job id not found, job_run_id: {job_run_id}",
                               extra={DatasiftConstants.JOB_RUN_ID: job_run_id})
                return None
            else:
                common_log_arguments = {DatasiftConstants.JOB_ID: job_id, DatasiftConstants.JOB_RUN_ID: job_run_id}
                job_run_pickle_file_path = _construct_job_run_job_stats_pickle_file_path(job_id=job_id,
                                                                                         job_run_id=job_run_id)
                job_run_job_stats_pickle_file: dict[str, JobStatsDto] | None = _get_job_run_pickle_file(
                    file_path=job_run_pickle_file_path)
                if job_run_job_stats_pickle_file is None:
                    return None
                job_stats: JobStatsDto = job_run_job_stats_pickle_file.get(job_run_id, None)
                if job_stats is None:
                    return None
                logger.info(f"JobStats for the job run id : {job_run_id} :\n {job_stats}", extra=common_log_arguments)
                return job_stats if isinstance(job_stats, JobStatsDto) else JobStatsDto(**job_stats)
        except Exception as exc:
            logger.error(
                f"An error occurred while getting the job stats: {str(exc)}",
                exc_info=True, stack_info=True, extra={DatasiftConstants.JOB_RUN_ID: job_run_id})

    def get_node_stats(self, job_id: str, job_run_id: str) -> dict[str,NodeStatsDto] | None:
        common_log_arguments = {DatasiftConstants.JOB_ID: job_id, DatasiftConstants.JOB_RUN_ID: job_run_id}
        try:
            # Get the Pickle file
            job_run_node_stats_pickle_file_path = _construct_job_run_node_stats_pickle_file_path(job_id=job_id,
                                                                                                 job_run_id=job_run_id)
            job_run_node_stats_pickle_file: dict[str, NodeStatsDto] = _get_job_run_pickle_file(
                file_path=job_run_node_stats_pickle_file_path)
            if job_run_node_stats_pickle_file is None:
                return None

            return job_run_node_stats_pickle_file
        except Exception as exc:
            logger.error(f"Error Occurred while Getting the Nodes stats for {job_run_id} from COS Buckets: {str(exc)}",
                         exc_info=True,
                         stack_info=True, extra=common_log_arguments)
            return None

    def store_node_stats(self, job_id: str, job_run_id: str, node_stats: NodeStatsDto):
        common_log_arguments = {DatasiftConstants.JOB_ID: job_id, DatasiftConstants.JOB_RUN_ID: job_run_id}
        try:
            if node_stats is None  or node_stats.id is None:
                logger.info("Invalid node stat: " + str(node_stats), extra=common_log_arguments)
                return
            job_run_node_stats_pickle_file_path = _construct_job_run_node_stats_pickle_file_path(job_id=job_id,
                                                                                                 job_run_id=job_run_id)
            job_run_pickle_file = _get_job_run_pickle_file(file_path=job_run_node_stats_pickle_file_path)
            node_id_to_node_stats: dict[str, NodeStatsDto] = dict()
            if job_run_pickle_file is None:
                logger.debug(
                    f"Pickle file '{job_run_node_stats_pickle_file_path}' for job run node stats not found.",
                    extra=common_log_arguments)

            else:
                logger.debug(
                    f"Pickle file '{job_run_node_stats_pickle_file_path}' found. Updating node stats for job run ID: {job_run_id}.",
                    extra=common_log_arguments)
                node_id_to_node_stats = job_run_pickle_file
            node_id_to_node_stats[node_stats.id] = node_stats.model_dump() if isinstance(node_stats,
                                                                                         NodeStatsDto) else node_stats
            json_data = json.dumps(node_id_to_node_stats)
            _save_job_run_pickle_file(data=node_id_to_node_stats, json_data=json_data,
                                      file_path=job_run_node_stats_pickle_file_path)
            logger.debug(
                f"Successfully stored node stats for job run ID {job_run_id} in file '{job_run_node_stats_pickle_file_path}'.",
                extra=common_log_arguments)
        except Exception as exc:
            logger.error(f"Error Occurred while Storing the Nodes stats for {job_run_id}: {str(exc)}",
                         exc_info=True,
                         stack_info=True, extra=common_log_arguments)

    def atomic_increment_fields(self, *, job_run_id: str, increments: dict, updates: Optional[dict] = None):
        # Get current stats
        job_stats = self.get_job_stats(job_run_id=job_run_id)
        if job_stats is None:
            logger.warning(f"Job stats not found for job_run_id: {job_run_id}")
            return

        # Apply increments
        for field, increment_value in increments.items():
            current_value = getattr(job_stats, field, 0) or 0
            setattr(job_stats, field, current_value + increment_value)

        # Apply updates
        if updates:
            for field, new_value in updates.items():
                setattr(job_stats, field, new_value)

        # Save
        self.store_job_stats(job_stats=job_stats, merge=False)
