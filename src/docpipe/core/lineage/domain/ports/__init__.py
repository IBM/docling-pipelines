"""Domain port interfaces for Lineage package."""

from docpipe.core.lineage.domain.ports.execution_lifecycle_observer import ExecutionLifecycleObserverPort
from docpipe.core.lineage.domain.ports.lineage_publisher import LineagePublisherPort

__all__ = [
    "ExecutionLifecycleObserverPort",
    "LineagePublisherPort",
]
