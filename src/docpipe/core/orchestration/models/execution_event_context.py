"""Lifecycle execution event contexts passed to ExecutionLifecycleObserverPort."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pyarrow as pa


@dataclass
class FlowStartContext:
    """Context delivered when flow execution is starting."""

    flow_id: str
    flow_name: str
    job_run_id: str
    flow_def: dict[str, Any]
    start_time: datetime | str | None = None


@dataclass
class FlowRunningContext:
    """Context delivered when the ingest stage completes and active processing begins."""

    flow_id: str
    flow_name: str
    job_run_id: str
    ingested_table: pa.Table | None = None
    ingest_node_id: str | None = None
    progress: dict[str, Any] = field(default_factory=dict)
    event_time: datetime | str | None = None


@dataclass
class FlowCompleteContext:
    """Context delivered when flow execution completes."""

    flow_id: str
    flow_name: str
    job_run_id: str
    flow_def: dict[str, Any]
    status: str = "Completed"
    output_tables: list[pa.Table] = field(default_factory=list)
    output_metadata: dict[str, Any] = field(default_factory=dict)
    start_time: datetime | str | None = None
    end_time: datetime | str | None = None


@dataclass
class FlowFailContext:
    """Context delivered when flow execution fails."""

    flow_id: str
    flow_name: str
    job_run_id: str
    error_message: str
    exception: Exception | None = None
    flow_def: dict[str, Any] = field(default_factory=dict)
    status: str = "Failed"
    start_time: datetime | str | None = None
    end_time: datetime | str | None = None


@dataclass
class FlowAbortContext:
    """Context delivered when flow execution is aborted/cancelled."""

    flow_id: str
    flow_name: str
    job_run_id: str
    reason: str | None = None
    flow_def: dict[str, Any] = field(default_factory=dict)
    status: str = "Canceled"
    start_time: datetime | str | None = None
    end_time: datetime | str | None = None


@dataclass
class NodeStartContext:
    """Context delivered when a DAG node step begins execution."""

    flow_id: str
    flow_name: str
    job_run_id: str
    node_id: str
    node_name: str
    operator_type: str
    operator_category: str | None = None
    input_table: pa.Table | None = None
    predecessor_node_ids: list[str] = field(default_factory=list)
    start_time: datetime | str | None = None


@dataclass
class NodeCompleteContext:
    """Context delivered when a DAG node step finishes execution."""

    flow_id: str
    flow_name: str
    job_run_id: str
    node_id: str
    node_name: str
    operator_type: str
    operator_category: str | None = None
    input_table: pa.Table | None = None
    output_tables: list[pa.Table] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    start_time: datetime | str | None = None
    end_time: datetime | str | None = None
    batch_id: str | None = None
    batch_num: int | None = None


@dataclass
class NodeFailContext:
    """Context delivered when a DAG node step execution fails."""

    flow_id: str
    flow_name: str
    job_run_id: str
    node_id: str
    node_name: str
    operator_type: str
    error_message: str
    exception: Exception | None = None
    input_table: pa.Table | None = None
    start_time: datetime | str | None = None
    end_time: datetime | str | None = None


@dataclass
class NodeSkipContext:
    """Context delivered when a DAG node step is skipped."""

    flow_id: str
    flow_name: str
    job_run_id: str
    node_id: str
    node_name: str
    operator_type: str
    reason: str
    operator_category: str | None = None
    start_time: datetime | str | None = None
    end_time: datetime | str | None = None
