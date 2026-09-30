"""Lineage event types matching OpenLineage specification."""

from enum import StrEnum


class LineageEventType(StrEnum):
    """OpenLineage standard and lifecycle event types."""

    START = "START"
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    FAIL = "FAIL"
    ABORT = "ABORT"
    OTHER = "OTHER"
