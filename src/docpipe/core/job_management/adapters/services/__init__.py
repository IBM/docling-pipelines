"""
Service Adapters - Concrete implementations of service ports

This module contains adapters that implement service port interfaces.

Available Implementations:
- JobTrackerService: Wraps legacy JobTracker singleton (phase 1 bridge)

TODO Phase 2: Gradually migrate logic from JobTracker to new services
TODO Phase 3: Remove JobTracker dependency entirely
"""

from .job_tracker_service import JobTrackerService

__all__ = [
    "JobTrackerService",
]
