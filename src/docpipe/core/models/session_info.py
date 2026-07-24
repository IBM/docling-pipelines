from contextvars import ContextVar
from typing import Any

from docpipe.core.constants.constants import DocpipeConstants


class SessionInfo:
    """A class to store the attributes that do not change and needed in multiple places while executing the request"""

    def __init__(
        self,
        orchestrator=None,
        job_id=None,
        job_run_id=None,
        flow_id=None,
        transaction_id=None,
        track_perf: Any | None = False,
        application=None,
    ):  # NOSONAR
        self.orchestrator = orchestrator
        self.job_id = job_id
        self.job_run_id = job_run_id
        self.flow_id = flow_id
        self.transaction_id = transaction_id
        self.track_perf = track_perf
        self.application = application

    def get_common_log_arguments(self):
        return {
            DocpipeConstants.JOB_ID: self.job_id,
            DocpipeConstants.JOB_RUN_ID: self.job_run_id,
        }


session_info_var: ContextVar[SessionInfo | None] = ContextVar("session_info", default=None)


def create_session_info(
    orchestrator=None,
    job_id=None,
    job_run_id=None,
    flow_id=None,
    transaction_id=DocpipeConstants.DEFAULT_TRANSACTION_ID,
    track_perf: Any | None = False,
):  # NOSONAR
    session_info = SessionInfo(
        orchestrator=orchestrator,
        job_id=job_id,
        job_run_id=job_run_id,
        flow_id=flow_id,
        transaction_id=transaction_id,
        track_perf=track_perf,
    )
    session_info_var.set(session_info)
    return session_info


def set_session_info(session_info):
    session_info_var.set(session_info)


def get_session_info() -> SessionInfo:
    session_info = session_info_var.get()
    if session_info is None:
        return create_session_info(transaction_id=DocpipeConstants.DEFAULT_TRANSACTION_ID)
    return session_info


def update_session_info(**kwargs):
    session_info = get_session_info()
    for key, value in kwargs.items():
        if hasattr(session_info, key):
            setattr(session_info, key, value)
    return session_info
