"""
Job Management Module - Hexagonal Architecture Implementation

This module implements job statistics tracking and management using hexagonal
architecture (ports and adapters pattern).

Architecture Layers:
1. Domain: Core business logic and models (DTOs, ports)
2. Application: Use cases and orchestration (services)
3. Adapters: Infrastructure implementations (stores, frameworks, services)


"""

# Domain exports
# Adapter exports
from .adapters import (
    DefaultJobRunManager,
    FrameworkType,
    InMemoryJobStatsStore,
    JobManagementFactory,
    JobTrackerService,
    StorageBackend,
    get_default_factory,
    reset_default_factory,
)

# Application exports
from .application import (
    JobManagementService,
    NodeStatsAggregator,
)
from .domain import (
    JobRunManager,
    JobStats,
    JobStatsService,
    JobStatsStore,
    NodeStats,
)

__all__ = [
    # Framework adapters
    "DefaultJobRunManager",
    "FrameworkType",
    # Storage adapters
    "InMemoryJobStatsStore",
    # Configuration and factory
    "JobManagementFactory",
    "JobManagementService",
    "JobRunManager",
    # Domain models
    "JobStats",
    # Domain ports
    "JobStatsService",
    "JobStatsStore",
    # Service adapters
    "JobTrackerService",
    "NodeStats",
    # Application services
    "NodeStatsAggregator",
    "StorageBackend",
    "get_default_factory",
    "reset_default_factory",
]
