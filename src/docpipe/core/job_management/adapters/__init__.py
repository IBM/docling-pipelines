"""
Adapters Layer - Infrastructure implementations

This layer contains concrete implementations of ports (interfaces):
- Storage adapters (JobStatsStore implementations)
- Framework adapters (JobRunManager implementations)
- Service adapters (JobStatsService implementations)
- Configuration and dependency injection
"""

from .config import (
    FrameworkType,
    JobManagementFactory,
    StorageBackend,
    get_default_factory,
    reset_default_factory,
)
from .frameworks import DefaultJobRunManager
from .services import JobTrackerService
from .stores import InMemoryJobStatsStore

__all__ = [
    # Framework adapters
    "DefaultJobRunManager",
    "FrameworkType",
    # Storage adapters
    "InMemoryJobStatsStore",
    # Configuration and factory
    "JobManagementFactory",
    # Service adapters
    "JobTrackerService",
    "StorageBackend",
    "get_default_factory",
    "reset_default_factory",
]
