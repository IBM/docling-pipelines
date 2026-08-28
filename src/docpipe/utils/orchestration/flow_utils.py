"""Flow execution utilities for node mapping, logging, and validation."""

import json
from pathlib import Path

from docpipe.core.constants.constants import DocpipeConstants
from docpipe.core.constants.operator_constants import OperatorConstants
from docpipe.exceptions.docpipe_exceptions import ErrorCode, ValidationAlert
from docpipe.exceptions.error_messages import ValidationMessage
from docpipe.utils.infrastructure.filesystem import get_data_path


def create_node_id_to_index_map(*, flow_def: dict) -> dict:
    """
    Return a mapping between each node ID and its corresponding index,
    representing the position where it appears in the original JSON node sequence.

    Args:
        flow_def: a dict holding a flow.

    Returns:
        dict: A mapping between node id and its index in the input flow.
    """
    node_id_to_index_map = {}
    index = 0
    for node in flow_def:
        node_id_to_index_map[node["id"]] = index
        index = index + 1
    return node_id_to_index_map


def create_log_folders(job_id, job_run_id, type):
    """
    Created folders for logs: <job_id>/<job_run_id>/docpipe_logs. The log for that job will be stored there
    """
    log_location_path = get_data_path()

    log_app_location = DocpipeConstants.DOCPIPE_LOGS

    log_job_location = Path(log_location_path) / job_id / str(job_run_id) / log_app_location
    log_job_location.mkdir(parents=True, exist_ok=True)
    if type == "job":
        log_job_run_file_name = "job_stats.json"
    elif type == "agg_logs":
        log_job_run_file_name = "flow_execute_aggregated.json"

    return str(log_job_location / log_job_run_file_name)


def write_job_logs(job_stats, job_log_path):
    """
    Write job statistics to a JSON log file.

    Args:
        job_stats: Job statistics object with __dict__ attribute
        job_log_path: Path to write the log file
    """
    with Path(job_log_path).open("w") as file:
        json.dump(job_stats.__dict__, file, indent=4)


def construct_deleted_rows_table_path(*, job_id: str, job_run_id):
    """
    Construct the path for storing deleted rows table.

    Args:
        job_id: Job identifier
        job_run_id: Job run identifier

    Returns:
        Path to the deleted rows parquet file
    """
    parquet_file_name = "unprocessed_docs.parquet"
    return str(
        Path(get_data_path()) / job_id / str(job_run_id) / DocpipeConstants.UNPROCESSED_DOCS_PATH / parquet_file_name
    )


def add_validation_alert(message: str | ValidationMessage, op_def: dict, alerts: list, **kwargs):
    """
    Add a validation alert to the alerts list.

    Parameters
    ----------
       message: Either a plain string or a ValidationMessage object.
        op_def: Dictionary with operator definition keys: ID, NAME, OPERATOR.
        alerts: List to which the new ValidationAlert will be appended.
        **kwargs: Optional extra parameters to include in the alert.

    Returns
    -------
    instance of ValidationAlert model
    """
    message_obj = message if isinstance(message, ValidationMessage) else ValidationMessage(message=message)

    alerts.append(
        ValidationAlert(
            code=ErrorCode.FLOW_VALIDATION_FAILED.value,
            node_id=op_def.get(OperatorConstants.Misc.ID),
            node_name=op_def.get(OperatorConstants.Misc.NAME),
            operator=op_def.get(OperatorConstants.Misc.OPERATOR),
            **message_obj.model_dump(mode="python"),
            **kwargs,
        )
    )


__all__ = [
    "add_validation_alert",
    "construct_deleted_rows_table_path",
    "create_log_folders",
    "create_node_id_to_index_map",
    "write_job_logs",
]
