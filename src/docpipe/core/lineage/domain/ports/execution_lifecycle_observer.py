"""Port interface for execution lifecycle observers."""

from abc import ABC, abstractmethod

from docpipe.core.orchestration.models.execution_event_context import (
    FlowAbortContext,
    FlowCompleteContext,
    FlowFailContext,
    FlowRunningContext,
    FlowStartContext,
    NodeCompleteContext,
    NodeFailContext,
    NodeSkipContext,
    NodeStartContext,
)


class ExecutionLifecycleObserverPort(ABC):
    """Lifecycle observer port interface called by orchestrators at execution milestones."""

    @abstractmethod
    def on_flow_start(self, *, context: FlowStartContext) -> None:
        """Called when flow execution begins."""
        ...

    @abstractmethod
    def on_flow_running(self, *, context: FlowRunningContext) -> None:
        """Called after the ingest stage completes and active processing begins."""
        ...

    @abstractmethod
    def on_flow_complete(self, *, context: FlowCompleteContext) -> None:
        """Called when flow execution completes successfully."""
        ...

    @abstractmethod
    def on_flow_fail(self, *, context: FlowFailContext) -> None:
        """Called when flow execution fails."""
        ...

    @abstractmethod
    def on_flow_abort(self, *, context: FlowAbortContext) -> None:
        """Called when flow execution is aborted/cancelled."""
        ...

    @abstractmethod
    def on_node_start(self, *, context: NodeStartContext) -> None:
        """Called when a DAG node step begins execution."""
        ...

    @abstractmethod
    def on_node_complete(self, *, context: NodeCompleteContext) -> None:
        """Called when a DAG node step completes execution."""
        ...

    @abstractmethod
    def on_node_fail(self, *, context: NodeFailContext) -> None:
        """Called when a DAG node step execution fails."""
        ...

    @abstractmethod
    def on_node_skip(self, *, context: NodeSkipContext) -> None:
        """Called when a DAG node step is skipped."""
        ...
